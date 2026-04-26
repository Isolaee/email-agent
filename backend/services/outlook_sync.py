"""Outlook sync via Microsoft Graph API with MSAL OAuth2."""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import msal
import html2text

from config import get_settings
from db.database import SessionLocal
from db.models import Account, Email, SyncState
from sqlalchemy import select

TOKENS_DIR = Path("tokens")
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read", "User.Read"]
REDIRECT_URI = "http://localhost:8000/api/auth/microsoft/callback"

_msal_apps: dict[str, msal.ConfidentialClientApplication] = {}


def _get_msal_app() -> msal.ConfidentialClientApplication:
    settings = get_settings()
    key = settings.microsoft_client_id
    if key not in _msal_apps:
        _msal_apps[key] = msal.ConfidentialClientApplication(
            settings.microsoft_client_id,
            authority=f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}",
            client_credential=settings.microsoft_client_secret,
        )
    return _msal_apps[key]


def _token_file(account: str) -> Path:
    safe = account.replace("@", "_at_").replace(".", "_")
    return TOKENS_DIR / f"outlook_{safe}.json"


def _load_token(account: str) -> dict | None:
    f = _token_file(account)
    if not f.exists():
        return None
    return json.loads(f.read_text())


def _save_token(account: str, token: dict):
    TOKENS_DIR.mkdir(exist_ok=True)
    _token_file(account).write_text(json.dumps(token))


def is_outlook_authenticated(account: str) -> bool:
    return _load_token(account) is not None


def get_outlook_auth_url(account: str | None = None) -> str:
    app = _get_msal_app()
    result = app.initiate_auth_code_flow(SCOPES, redirect_uri=REDIRECT_URI, state=account or "")
    # Store flow state so callback can complete it
    flow_file = TOKENS_DIR / "outlook_flow.json"
    TOKENS_DIR.mkdir(exist_ok=True)
    flow_file.write_text(json.dumps(result))
    return result["auth_uri"]


async def handle_outlook_callback(code: str, state: str | None):
    app = _get_msal_app()
    flow_file = TOKENS_DIR / "outlook_flow.json"
    if not flow_file.exists():
        raise RuntimeError("No pending OAuth flow")
    flow = json.loads(flow_file.read_text())
    token = app.acquire_token_by_auth_code_flow(flow, {"code": code, "state": state or ""})
    if "error" in token:
        raise RuntimeError(f"OAuth error: {token['error_description']}")

    # Discover the actual email address from the token claims
    account_email = token.get("id_token_claims", {}).get("preferred_username", state or "unknown")
    _save_token(account_email, token)
    flow_file.unlink(missing_ok=True)


async def _get_access_token(account: str) -> str:
    token_data = _load_token(account)
    if not token_data:
        raise RuntimeError(f"Outlook account {account} not authenticated")

    app = _get_msal_app()
    # Try silent refresh
    accounts = app.get_accounts(username=account)
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_token(account, result)
            return result["access_token"]

    # Use stored refresh token
    if "refresh_token" in token_data:
        result = app.acquire_token_by_refresh_token(token_data["refresh_token"], SCOPES)
        if result and "access_token" in result:
            _save_token(account, result)
            return result["access_token"]

    raise RuntimeError(f"Cannot refresh token for {account} — re-authenticate at /api/auth/microsoft")


async def sync_outlook():
    settings = get_settings()
    for account in settings.outlook_account_list:
        try:
            await _sync_account(account)
        except Exception as e:
            print(f"[outlook] Error syncing {account}: {e}")


async def _sync_account(account_email: str):
    access_token = await _get_access_token(account_email)
    headers = {"Authorization": f"Bearer {access_token}"}

    async with SessionLocal() as db:
        acc = (await db.execute(select(Account).where(Account.email == account_email))).scalar_one_or_none()
        if not acc:
            acc = Account(email=account_email, provider="outlook", display_name=account_email)
            db.add(acc)
            await db.commit()
            await db.refresh(acc)

        state_key = f"outlook_delta_{account_email}"
        state_row = (await db.execute(select(SyncState).where(SyncState.key == state_key))).scalar_one_or_none()
        delta_link = state_row.value if state_row else None

        async with httpx.AsyncClient() as client:
            url = delta_link or f"{GRAPH_BASE}/me/messages/delta?$select=id,subject,from,toRecipients,receivedDateTime,isRead,body&$top=50"
            fetched = 0
            new_delta_link = delta_link

            while url:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                for msg in data.get("value", []):
                    existing = (await db.execute(select(Email).where(Email.message_id == msg["id"]))).scalar_one_or_none()
                    if existing:
                        continue

                    body_content = msg.get("body", {}).get("content", "")
                    body_type = msg.get("body", {}).get("contentType", "text")
                    body_text = html2text.html2text(body_content) if body_type == "html" else body_content

                    sender = msg.get("from", {}).get("emailAddress", {})
                    sender_str = f"{sender.get('name', '')} <{sender.get('address', '')}>"

                    recipients = [
                        r.get("emailAddress", {}).get("address", "")
                        for r in msg.get("toRecipients", [])
                    ]

                    date_str = msg.get("receivedDateTime")
                    try:
                        date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        date = None

                    db.add(Email(
                        account_id=acc.id,
                        message_id=msg["id"],
                        subject=msg.get("subject", ""),
                        sender=sender_str,
                        recipients=json.dumps(recipients),
                        date=date,
                        body_text=body_text[:50_000],
                        is_read=msg.get("isRead", False),
                        is_starred=False,
                        labels=json.dumps([]),
                        raw_snippet=body_text[:200],
                    ))
                    fetched += 1

                new_delta_link = data.get("@odata.deltaLink", new_delta_link)
                url = data.get("@odata.nextLink")

            if fetched:
                await db.commit()

            if state_row:
                state_row.value = new_delta_link or ""
                state_row.updated_at = datetime.utcnow()
            elif new_delta_link:
                db.add(SyncState(key=state_key, value=new_delta_link))

            acc.last_synced_at = datetime.utcnow()
            await db.commit()
            print(f"[outlook] Synced {fetched} new messages for {account_email}")
