"""IMAP sync for Roundcube (or any IMAP server)."""

import json
import email as email_lib
import email.policy
from datetime import datetime, timezone

import aioimaplib
import html2text

from config import get_settings
from db.database import SessionLocal
from db.models import Account, Email, SyncState
from sqlalchemy import select


async def sync_imap():
    settings = get_settings()
    if not settings.imap_host or not settings.imap_username:
        print("[imap] Not configured, skipping")
        return
    await _sync_account()


async def _sync_account():
    settings = get_settings()

    if settings.imap_use_ssl:
        client = aioimaplib.IMAP4_SSL(host=settings.imap_host, port=settings.imap_port)
    else:
        client = aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port)

    await client.wait_hello_from_server()
    await client.login(settings.imap_username, settings.imap_password)

    async with SessionLocal() as db:
        acc = (await db.execute(select(Account).where(Account.email == settings.imap_username))).scalar_one_or_none()
        if not acc:
            acc = Account(email=settings.imap_username, provider="imap", display_name=settings.imap_username)
            db.add(acc)
            await db.commit()
            await db.refresh(acc)

        state_key = f"imap_uidvalidity_{settings.imap_username}"
        state_row = (await db.execute(select(SyncState).where(SyncState.key == state_key))).scalar_one_or_none()
        last_uid = int(state_row.value) if state_row and state_row.value else 0

        await client.select("INBOX")

        # Search for messages newer than last synced UID
        if last_uid > 0:
            _, data = await client.uid("search", f"UID {last_uid + 1}:*")
        else:
            _, data = await client.uid("search", "ALL")

        uid_list = data[0].decode().split() if data[0] else []
        uid_list = [u for u in uid_list if int(u) > last_uid]

        fetched = 0
        max_uid = last_uid

        for uid in uid_list[-200:]:  # cap at 200 per sync
            uid_int = int(uid)
            msg_id_key = f"imap_uid_{settings.imap_username}_{uid}"
            existing = (await db.execute(select(Email).where(Email.message_id == msg_id_key))).scalar_one_or_none()
            if existing:
                max_uid = max(max_uid, uid_int)
                continue

            _, msg_data = await client.uid("fetch", uid, "(RFC822 FLAGS)")
            if not msg_data or not msg_data[0]:
                continue

            raw = None
            flags = []
            for part in msg_data:
                if isinstance(part, bytes) and part != b")":
                    raw = part
                elif isinstance(part, str) and "FLAGS" in part:
                    flags = part.split("FLAGS")[1].strip().strip("()").split()

            if not raw:
                continue

            msg = email_lib.message_from_bytes(raw, policy=email_lib.policy.default)

            date = None
            try:
                date_str = msg.get("Date", "")
                date = email_lib.utils.parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass

            body_text = _extract_body(msg)

            db.add(Email(
                account_id=acc.id,
                message_id=msg_id_key,
                thread_id=msg.get("Message-ID", uid),
                subject=str(msg.get("Subject", "")),
                sender=str(msg.get("From", "")),
                recipients=json.dumps([str(msg.get("To", ""))]),
                date=date,
                body_text=body_text[:50_000],
                is_read="\\Seen" in flags,
                is_starred="\\Flagged" in flags,
                labels=json.dumps(flags),
                raw_snippet=body_text[:200],
            ))
            fetched += 1
            max_uid = max(max_uid, uid_int)

        if fetched:
            await db.commit()

        if max_uid > last_uid:
            if state_row:
                state_row.value = str(max_uid)
                state_row.updated_at = datetime.utcnow()
            else:
                db.add(SyncState(key=state_key, value=str(max_uid)))

        acc.last_synced_at = datetime.utcnow()
        await db.commit()

    await client.logout()
    print(f"[imap] Synced {fetched} new messages for {settings.imap_username}")


def _extract_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                break
            if ct == "text/html" and not body:
                html = part.get_payload(decode=True).decode("utf-8", errors="replace")
                body = html2text.html2text(html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            raw = payload.decode("utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                body = html2text.html2text(raw)
            else:
                body = raw
    return body
