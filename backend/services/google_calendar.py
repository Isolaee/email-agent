"""Google Calendar sync and CRUD via Google API."""

import json
from datetime import datetime, timezone, timedelta

from googleapiclient.discovery import build

from db.database import SessionLocal
from db.models import CalendarEvent
from sqlalchemy import select


def _get_service():
    from services.gmail_sync import _load_credentials
    creds = _load_credentials()
    if not creds:
        raise RuntimeError("Google not authenticated — visit /api/auth/google first")
    return build("calendar", "v3", credentials=creds)


async def sync_events() -> int:
    try:
        service = _get_service()
    except RuntimeError:
        print("[calendar] Not authenticated, skipping sync")
        return 0

    # Sync events from 30 days ago to 90 days ahead
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    time_min = (now - timedelta(days=30)).isoformat()
    time_max = (now + timedelta(days=90)).isoformat()

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
        maxResults=500,
    ).execute()

    items = result.get("items", [])
    synced = 0

    async with SessionLocal() as db:
        event_ids = [item["id"] for item in items]
        existing_rows = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.google_event_id.in_(event_ids))
        )).scalars().all()
        existing_map = {row.google_event_id: row for row in existing_rows}

        for item in items:
            event_id = item["id"]
            existing = existing_map.get(event_id)

            start = item.get("start", {})
            end = item.get("end", {})
            is_all_day = "date" in start and "dateTime" not in start

            start_time = _parse_dt(start.get("dateTime") or start.get("date"))
            end_time = _parse_dt(end.get("dateTime") or end.get("date"))

            attendees = [a.get("email", "") for a in item.get("attendees", [])]

            if existing:
                existing.title = item.get("summary", "")
                existing.description = item.get("description", "")
                existing.location = item.get("location", "")
                existing.start_time = start_time
                existing.end_time = end_time
                existing.is_all_day = is_all_day
                existing.attendees = json.dumps(attendees)
                existing.updated_at = datetime.utcnow()
            else:
                db.add(CalendarEvent(
                    google_event_id=event_id,
                    title=item.get("summary", ""),
                    description=item.get("description", ""),
                    location=item.get("location", ""),
                    start_time=start_time,
                    end_time=end_time,
                    is_all_day=is_all_day,
                    attendees=json.dumps(attendees),
                    calendar_id="primary",
                    updated_at=datetime.utcnow(),
                ))
                synced += 1

        await db.commit()

    print(f"[calendar] Synced {synced} new events ({len(items)} total in range)")
    return synced


async def create_calendar_event(
    title: str,
    description: str,
    location: str,
    start_time: datetime,
    end_time: datetime,
    attendees: list[str],
    calendar_id: str = "primary",
    reminder_minutes: int | None = None,
) -> dict:
    service = _get_service()
    body = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        "attendees": [{"email": e} for e in attendees],
        "reminders": {
            "useDefault": reminder_minutes is None,
            "overrides": (
                [{"method": "popup", "minutes": reminder_minutes}]
                if reminder_minutes is not None else []
            ),
        },
    }
    event = service.events().insert(calendarId=calendar_id, body=body).execute()
    await sync_events()
    return event


async def update_calendar_event(event_id: str, updates: dict) -> dict:
    service = _get_service()
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()

    if "title" in updates:
        existing["summary"] = updates["title"]
    if "description" in updates:
        existing["description"] = updates["description"]
    if "location" in updates:
        existing["location"] = updates["location"]
    if "start_time" in updates:
        existing["start"] = {"dateTime": updates["start_time"].isoformat(), "timeZone": "UTC"}
    if "end_time" in updates:
        existing["end"] = {"dateTime": updates["end_time"].isoformat(), "timeZone": "UTC"}
    if "attendees" in updates:
        existing["attendees"] = [{"email": e} for e in updates["attendees"]]

    event = service.events().update(calendarId="primary", eventId=event_id, body=existing).execute()
    await sync_events()
    return event


async def delete_calendar_event(event_id: str):
    from googleapiclient.errors import HttpError
    service = _get_service()
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status not in (404, 410):
            raise
    async with SessionLocal() as db:
        row = (await db.execute(select(CalendarEvent).where(CalendarEvent.google_event_id == event_id))).scalar_one_or_none()
        if row:
            await db.delete(row)
            await db.commit()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None
