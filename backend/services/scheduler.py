from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import get_settings

_scheduler = AsyncIOScheduler()


async def _sync_all():
    from services.gmail_sync import sync_gmail
    from services.outlook_sync import sync_outlook
    from services.imap_sync import sync_imap
    from services.google_calendar import sync_events

    try:
        await sync_gmail()
    except Exception as e:
        print(f"[scheduler] Gmail sync error: {e}")

    try:
        await sync_outlook()
    except Exception as e:
        print(f"[scheduler] Outlook sync error: {e}")

    try:
        await sync_imap()
    except Exception as e:
        print(f"[scheduler] IMAP sync error: {e}")

    try:
        await sync_events()
    except Exception as e:
        print(f"[scheduler] Calendar sync error: {e}")


async def start_scheduler():
    settings = get_settings()
    _scheduler.add_job(_sync_all, "interval", seconds=settings.sync_interval_seconds, id="sync_all")
    _scheduler.start()
    # Run an initial sync shortly after startup
    _scheduler.add_job(_sync_all, "date", id="sync_initial")


async def stop_scheduler():
    _scheduler.shutdown(wait=False)
