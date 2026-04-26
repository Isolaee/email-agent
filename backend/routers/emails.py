from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from db.database import get_db
from db.models import Email, Account
import json

router = APIRouter()


@router.get("")
async def list_emails(
    account_id: int | None = None,
    search: str | None = None,
    unread_only: bool = False,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Email, Account.email.label("account_email"), Account.provider)
        .join(Account)
        .order_by(desc(Email.date))
        .limit(limit)
        .offset(offset)
    )
    if account_id:
        stmt = stmt.where(Email.account_id == account_id)
    if unread_only:
        stmt = stmt.where(Email.is_read == False)  # noqa: E712
    if search:
        term = f"%{search}%"
        stmt = stmt.where(
            or_(Email.subject.ilike(term), Email.sender.ilike(term), Email.body_text.ilike(term))
        )

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": e.id,
            "account_id": e.account_id,
            "account_email": account_email,
            "provider": provider,
            "message_id": e.message_id,
            "thread_id": e.thread_id,
            "subject": e.subject,
            "sender": e.sender,
            "recipients": json.loads(e.recipients) if e.recipients else [],
            "date": e.date.isoformat() if e.date else None,
            "is_read": e.is_read,
            "is_starred": e.is_starred,
            "labels": json.loads(e.labels) if e.labels else [],
            "snippet": e.raw_snippet,
        }
        for e, account_email, provider in rows
    ]


@router.get("/{email_id}")
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Email, Account.email.label("account_email"), Account.provider).join(Account).where(Email.id == email_id)
    row = (await db.execute(stmt)).first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Email not found")
    e, account_email, provider = row
    return {
        "id": e.id,
        "account_id": e.account_id,
        "account_email": account_email,
        "provider": provider,
        "message_id": e.message_id,
        "thread_id": e.thread_id,
        "subject": e.subject,
        "sender": e.sender,
        "recipients": json.loads(e.recipients) if e.recipients else [],
        "date": e.date.isoformat() if e.date else None,
        "body_text": e.body_text,
        "is_read": e.is_read,
        "is_starred": e.is_starred,
        "labels": json.loads(e.labels) if e.labels else [],
        "snippet": e.raw_snippet,
    }


@router.get("/accounts/list")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Account))).scalars().all()
    return [
        {
            "id": a.id,
            "email": a.email,
            "provider": a.provider,
            "display_name": a.display_name,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
        }
        for a in rows
    ]
