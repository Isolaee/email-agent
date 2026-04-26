"""AI agent using Ollama via OpenAI-compatible API with tool use."""

import json
from datetime import datetime
from typing import AsyncGenerator

from openai import AsyncOpenAI
from sqlalchemy import select, desc, or_

from config import get_settings
from db.database import SessionLocal
from db.models import Email, Account, CalendarEvent

SYSTEM_PROMPT = f"""You are a personal email and calendar assistant. Today is {datetime.utcnow().strftime('%Y-%m-%d')}.

You have access to the user's emails (read-only) and Google Calendar (read and write).

When answering questions about emails, always search first. When creating or modifying calendar events, confirm with the user before acting unless they explicitly say to go ahead.

Be concise. Use markdown for formatting. Dates and times are in UTC unless the user specifies otherwise."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search emails by keyword, sender, or subject. Returns a list of matching emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (matches subject, sender, or body)"},
                    "account_email": {"type": "string", "description": "Filter by specific account email (optional)"},
                    "unread_only": {"type": "boolean", "description": "Only return unread emails"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_email_body",
            "description": "Get the full body text of a specific email by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "integer", "description": "The email's numeric ID"},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_emails",
            "description": "List the most recent emails across all accounts or a specific account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_email": {"type": "string", "description": "Filter by account (optional)"},
                    "unread_only": {"type": "boolean", "description": "Only unread emails"},
                    "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "List calendar events in a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"},
                    "end_date": {"type": "string", "description": "End date in ISO format"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a new calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string", "default": ""},
                    "location": {"type": "string", "default": ""},
                    "start_time": {"type": "string", "description": "ISO datetime e.g. 2024-01-15T14:00:00"},
                    "end_time": {"type": "string", "description": "ISO datetime e.g. 2024-01-15T15:00:00"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee email addresses"},
                },
                "required": ["title", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Delete a calendar event by its Google event ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send a new email from one of the user's accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_email": {"type": "string", "description": "The sender account email address"},
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string"},
                    "body": {"type": "string", "description": "Plain text email body"},
                },
                "required": ["account_email", "to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_email",
            "description": "Reply to an existing email. The recipient, subject, and thread are derived from the original.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "integer", "description": "ID of the email to reply to"},
                    "body": {"type": "string", "description": "Plain text reply body"},
                },
                "required": ["email_id", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "label_email",
            "description": (
                "Apply or remove labels on an email and sync the change to the provider. "
                "For Gmail use Gmail label IDs (e.g. 'STARRED', 'UNREAD', or a custom label ID like 'Label_xxx'). "
                "For IMAP use IMAP flag names (e.g. '\\\\Flagged', '\\\\Seen')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "integer", "description": "The email's numeric ID"},
                    "add_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to add",
                        "default": [],
                    },
                    "remove_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to remove",
                        "default": [],
                    },
                },
                "required": ["email_id"],
            },
        },
    },
]


async def _call_tool(name: str, args: dict) -> str:
    if name == "search_emails":
        return await _search_emails(**args)
    if name == "get_email_body":
        return await _get_email_body(**args)
    if name == "list_recent_emails":
        return await _list_recent_emails(**args)
    if name == "list_calendar_events":
        return await _list_calendar_events(**args)
    if name == "create_calendar_event":
        return await _create_calendar_event(**args)
    if name == "delete_calendar_event":
        return await _delete_calendar_event(**args)
    if name == "send_email":
        return await _send_email(**args)
    if name == "reply_to_email":
        return await _reply_to_email(**args)
    if name == "label_email":
        return await _label_email(**args)
    return f"Unknown tool: {name}"


async def _search_emails(query: str, account_email: str | None = None, unread_only: bool = False, limit: int = 10) -> str:
    async with SessionLocal() as db:
        term = f"%{query}%"
        stmt = (
            select(Email, Account.email.label("acc_email"))
            .join(Account)
            .where(or_(Email.subject.ilike(term), Email.sender.ilike(term), Email.body_text.ilike(term)))
            .order_by(desc(Email.date))
            .limit(limit)
        )
        if account_email:
            stmt = stmt.where(Account.email == account_email)
        if unread_only:
            stmt = stmt.where(Email.is_read == False)  # noqa: E712
        rows = (await db.execute(stmt)).all()
        if not rows:
            return "No emails found matching that query."
        results = []
        for e, acc in rows:
            results.append(f"ID:{e.id} | {e.date} | From: {e.sender} | Subject: {e.subject} | Account: {acc}")
        return "\n".join(results)


async def _get_email_body(email_id: int) -> str:
    async with SessionLocal() as db:
        e = (await db.execute(select(Email).where(Email.id == email_id))).scalar_one_or_none()
        if not e:
            return f"Email {email_id} not found."
        return f"Subject: {e.subject}\nFrom: {e.sender}\nDate: {e.date}\n\n{e.body_text[:8000]}"


async def _list_recent_emails(account_email: str | None = None, unread_only: bool = False, limit: int = 20) -> str:
    async with SessionLocal() as db:
        stmt = (
            select(Email, Account.email.label("acc_email"))
            .join(Account)
            .order_by(desc(Email.date))
            .limit(limit)
        )
        if account_email:
            stmt = stmt.where(Account.email == account_email)
        if unread_only:
            stmt = stmt.where(Email.is_read == False)  # noqa: E712
        rows = (await db.execute(stmt)).all()
        if not rows:
            return "No emails found."
        results = []
        for e, acc in rows:
            read_marker = "" if e.is_read else "[UNREAD] "
            results.append(f"ID:{e.id} | {e.date} | {read_marker}From: {e.sender} | Subject: {e.subject}")
        return "\n".join(results)


async def _list_calendar_events(start_date: str, end_date: str) -> str:
    async with SessionLocal() as db:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        stmt = (
            select(CalendarEvent)
            .where(CalendarEvent.start_time >= start, CalendarEvent.start_time <= end)
            .order_by(CalendarEvent.start_time)
        )
        events = (await db.execute(stmt)).scalars().all()
        if not events:
            return f"No events between {start_date} and {end_date}."
        results = []
        for ev in events:
            results.append(f"ID:{ev.google_event_id} | {ev.start_time} → {ev.end_time} | {ev.title} | {ev.location or 'no location'}")
        return "\n".join(results)


async def _create_calendar_event(title: str, start_time: str, end_time: str, description: str = "", location: str = "", attendees: list | None = None) -> str:
    from services.google_calendar import create_calendar_event
    try:
        event = await create_calendar_event(
            title=title,
            description=description,
            location=location,
            start_time=datetime.fromisoformat(start_time),
            end_time=datetime.fromisoformat(end_time),
            attendees=attendees or [],
        )
        return f"Event created: {event.get('id')} — {title} at {start_time}"
    except Exception as e:
        return f"Failed to create event: {e}"


def _parse_addr(sender: str) -> str:
    if "<" in sender and ">" in sender:
        return sender.split("<")[1].rstrip(">").strip()
    return sender.strip()


async def _send_email(account_email: str, to: str, subject: str, body: str) -> str:
    async with SessionLocal() as db:
        account = (await db.execute(select(Account).where(Account.email == account_email))).scalar_one_or_none()
        if not account:
            return f"Account {account_email} not found."

    try:
        if account.provider == "gmail":
            from services.gmail_sync import gmail_send
            sent_id = gmail_send(to, subject, body)
            return f"Email sent via Gmail. Message ID: {sent_id}"
        elif account.provider == "outlook":
            from services.outlook_sync import outlook_send
            await outlook_send(account_email, to, subject, body)
            return "Email sent via Outlook."
        elif account.provider == "imap":
            from services.imap_sync import imap_send
            await imap_send(to, subject, body)
            return "Email sent via SMTP."
        else:
            return f"Unsupported provider: {account.provider}"
    except Exception as exc:
        return f"Failed to send email: {exc}"


async def _reply_to_email(email_id: int, body: str) -> str:
    async with SessionLocal() as db:
        stmt = select(Email, Account).join(Account).where(Email.id == email_id)
        row = (await db.execute(stmt)).first()
        if not row:
            return f"Email {email_id} not found."
        email, account = row
        reply_to = _parse_addr(email.sender)
        reply_subject = email.subject if email.subject.startswith("Re:") else f"Re: {email.subject}"
        thread_id = email.thread_id
        message_id = email.message_id

    try:
        if account.provider == "gmail":
            from services.gmail_sync import gmail_send
            sent_id = gmail_send(reply_to, reply_subject, body, thread_id=thread_id)
            return f"Reply sent via Gmail. Message ID: {sent_id}"
        elif account.provider == "outlook":
            from services.outlook_sync import outlook_reply
            await outlook_reply(account.email, message_id, body)
            return "Reply sent via Outlook."
        elif account.provider == "imap":
            from services.imap_sync import imap_send
            await imap_send(reply_to, reply_subject, body, reply_to_message_id=thread_id)
            return "Reply sent via SMTP."
        else:
            return f"Unsupported provider: {account.provider}"
    except Exception as exc:
        return f"Failed to send reply: {exc}"


async def _label_email(
    email_id: int,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
) -> str:
    add = add_labels or []
    remove = remove_labels or []

    async with SessionLocal() as db:
        stmt = select(Email, Account).join(Account).where(Email.id == email_id)
        row = (await db.execute(stmt)).first()
        if not row:
            return f"Email {email_id} not found."
        email, account = row

        current = set(json.loads(email.labels) if email.labels else [])
        current.update(add)
        current.difference_update(remove)
        email.labels = json.dumps(sorted(current))

        if account.provider == "gmail":
            if "UNREAD" in add:
                email.is_read = False
            if "UNREAD" in remove:
                email.is_read = True
            if "STARRED" in add:
                email.is_starred = True
            if "STARRED" in remove:
                email.is_starred = False
        elif account.provider == "imap":
            if "\\Seen" in add:
                email.is_read = True
            if "\\Seen" in remove:
                email.is_read = False
            if "\\Flagged" in add:
                email.is_starred = True
            if "\\Flagged" in remove:
                email.is_starred = False

        await db.commit()

    try:
        if account.provider == "gmail":
            from services.gmail_sync import modify_gmail_labels
            modify_gmail_labels(email.message_id, add, remove)
        elif account.provider == "imap":
            from services.imap_sync import modify_imap_flags
            uid = email.message_id.rsplit("_", 1)[-1]
            await modify_imap_flags(uid, add, remove)
    except Exception as exc:
        return f"Labels updated locally but provider sync failed: {exc}"

    return (
        f"Labels updated for email {email_id}. "
        f"Added: {add}. Removed: {remove}. Current labels: {sorted(current)}"
    )


async def _delete_calendar_event(event_id: str) -> str:
    from services.google_calendar import delete_calendar_event
    try:
        await delete_calendar_event(event_id)
        return f"Event {event_id} deleted."
    except Exception as e:
        return f"Failed to delete event: {e}"


async def run_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
    from openai import APIConnectionError, APIStatusError
    settings = get_settings()
    client = AsyncOpenAI(base_url=f"{settings.ollama_base_url}/v1", api_key="ollama", timeout=300.0)

    conversation = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    try:
        while True:
            response = await client.chat.completions.create(
                model=settings.ollama_model,
                messages=conversation,
                tools=TOOLS,
                stream=False,
            )

            choice = response.choices[0]
            message = choice.message

            if message.tool_calls:
                conversation.append({"role": "assistant", "content": message.content or "", "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ]})

                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = await _call_tool(tc.function.name, args)
                    conversation.append({"role": "tool", "tool_call_id": tc.id, "content": result})

                continue

            content = message.content or ""
            conversation.append({"role": "assistant", "content": content})
            for char in content:
                yield f"data: {json.dumps({'delta': char})}\n\n"
            yield "data: [DONE]\n\n"
            break
    except APIConnectionError:
        msg = f"Cannot reach Ollama at {settings.ollama_base_url}. Make sure Ollama is running."
        yield f"data: {json.dumps({'delta': msg})}\n\n"
        yield "data: [DONE]\n\n"
    except APIStatusError as e:
        msg = f"Ollama error {e.status_code}: {e.message}"
        yield f"data: {json.dumps({'delta': msg})}\n\n"
        yield "data: [DONE]\n\n"
