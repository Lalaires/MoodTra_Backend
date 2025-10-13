
from .db import SessionLocal
from fastapi import Header, HTTPException
from uuid import UUID
import os
from typing import Generator


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()


def get_account_id(x_account_id: str | None = Header(default=None)):
    raw = x_account_id or os.getenv("MOCK_ACCOUNT_ID")


    if not raw:
        return None

    try:
        return UUID(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid account_id format")



def get_session_id(x_session_id: str | None = Header(default=None)):

    raw = x_session_id or os.getenv("MOCK_SESSION_ID")

    if not raw:
        raise HTTPException(
            status_code=401,
            detail="x-session-id header required"
        )

    try:
        return UUID(raw)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id format"
        )