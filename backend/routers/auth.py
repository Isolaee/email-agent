from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from services.gmail_sync import get_gmail_auth_url, handle_gmail_callback
from services.outlook_sync import get_outlook_auth_url, handle_outlook_callback

router = APIRouter()


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/google")
async def google_auth(request: Request):
    url = get_gmail_auth_url(_base_url(request))
    return {"url": url}


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str | None = None):
    await handle_gmail_callback(code, _base_url(request))
    from services.gmail_sync import sync_gmail
    import asyncio
    asyncio.get_event_loop().create_task(sync_gmail())
    return RedirectResponse("/?auth=google_ok")


@router.get("/microsoft")
async def microsoft_auth(account: str | None = None):
    url = get_outlook_auth_url(account)
    return {"url": url}


@router.get("/microsoft/callback")
async def microsoft_callback(code: str, state: str | None = None):
    await handle_outlook_callback(code, state)
    return RedirectResponse("/?auth=microsoft_ok")


@router.get("/status")
async def auth_status():
    from services.gmail_sync import is_gmail_authenticated
    from services.outlook_sync import is_outlook_authenticated
    from config import get_settings
    s = get_settings()
    return {
        "google": is_gmail_authenticated(),
        "microsoft": {acc: is_outlook_authenticated(acc) for acc in s.outlook_account_list},
    }
