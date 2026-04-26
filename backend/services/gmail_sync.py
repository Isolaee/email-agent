"""Gmail sync via Google API with OAuth2. Tokens stored in tokens/ directory."""

import json
import os
import base64
import email as email_lib
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import html2text

from config import get_settings
from db.database import SessionLocal
from db.models import Account, Email, SyncState
from sqlalchemy import select

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]
TOKENS_DIR = Path("tokens")
GMAIL_TOKEN_FILE = TOKENS_DIR / "gmail_token.json"
REDIRECT_URI = "http://localhost:8000/api/auth/google/callback"


def _ensure_tokens_dir():
    TOKENS_DIR.mkdir(exist_ok=True)


def _load_credentials() -> Credentials | None:
    if not GMAIL_TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)
    return creds if creds and creds.valid else None


def _save_credentials(creds: Credentials):
    _ensure_tokens_dir()
    GMAIL_TOKEN_FILE.write_text(creds.to_json())


def is_gmail_authenticated() -> bool:
    return _load_credentials() is not None


def get_gmail_auth_url() -> str:
    settings = get_settings()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return url


async def handle_gmail_callback(code: str):
    settings = get_settings()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    flow.fetch_token(code=code)
    _save_credentials(flow.credentials)


def _get_service():
    creds = _load_credentials()
    if not creds:
        raise RuntimeError("Gmail not authenticated — visit /api/auth/google first")
    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    """Recursively extract plain text from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
        return html2text.html2text(html)
    parts = payload.get("parts", [])
    for part in parts:
        text = _decode_body(part)
        if text:
            return text
    return ""


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


async def sync_gmail():
    creds = _load_credentials()
    if not creds:
        print("[gmail] Not authenticated, skipping sync")
        return

    service = _get_service()

    # Ensure accounts exist in DB
    async with SessionLocal() as db:
        profile = service.users().getProfile(userId="me").execute()
        gmail_email = profile["emailAddress"]

        acc = (await db.execute(select(Account).where(Account.email == gmail_email))).scalar_one_or_none()
        if not acc:
            acc = Account(email=gmail_email, provider="gmail", display_name=gmail_email)
            db.add(acc)
            await db.commit()
            await db.refresh(acc)

        # Get last history ID for incremental sync
        state_key = f"gmail_history_{gmail_email}"
        state_row = (await db.execute(select(SyncState).where(SyncState.key == state_key))).scalar_one_or_none()
        history_id = state_row.value if state_row else None

        fetched = 0
        if history_id:
            try:
                history = service.users().history().list(userId="me", startHistoryId=history_id).execute()
                msg_ids = []
                for record in history.get("history", []):
                    for msg in record.get("messagesAdded", []):
                        msg_ids.append(msg["message"]["id"])
                fetched = await _fetch_and_store_messages(service, acc.id, msg_ids, db)
                new_history_id = history.get("historyId", history_id)
            except Exception:
                # Full sync fallback
                fetched, new_history_id = await _full_sync(service, acc.id, db)
        else:
            fetched, new_history_id = await _full_sync(service, acc.id, db)

        # Update sync state
        if state_row:
            state_row.value = str(new_history_id)
            state_row.updated_at = datetime.utcnow()
        else:
            db.add(SyncState(key=state_key, value=str(new_history_id)))

        acc.last_synced_at = datetime.utcnow()
        await db.commit()
        print(f"[gmail] Synced {fetched} new messages for {gmail_email}")


async def _full_sync(service, account_id: int, db) -> tuple[int, str]:
    """Fetch last 500 messages on first sync."""
    results = service.users().messages().list(userId="me", maxResults=500).execute()
    msg_ids = [m["id"] for m in results.get("messages", [])]
    history_id = results.get("historyId", "0")
    fetched = await _fetch_and_store_messages(service, account_id, msg_ids, db)
    return fetched, history_id


async def _fetch_and_store_messages(service, account_id: int, msg_ids: list[str], db) -> int:
    fetched = 0
    for msg_id in msg_ids:
        existing = (await db.execute(select(Email).where(Email.message_id == msg_id))).scalar_one_or_none()
        if existing:
            continue

        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        date_str = _header(headers, "Date")
        try:
            date = email_lib.utils.parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            date = None

        body = _decode_body(payload)
        label_ids = msg.get("labelIds", [])

        db.add(Email(
            account_id=account_id,
            message_id=msg_id,
            thread_id=msg.get("threadId"),
            subject=_header(headers, "Subject"),
            sender=_header(headers, "From"),
            recipients=json.dumps([_header(headers, "To")]),
            date=date,
            body_text=body[:50_000],  # cap at 50k chars
            is_read="UNREAD" not in label_ids,
            is_starred="STARRED" in label_ids,
            labels=json.dumps(label_ids),
            raw_snippet=msg.get("snippet", ""),
        ))
        fetched += 1

    if fetched:
        await db.commit()
    return fetched
