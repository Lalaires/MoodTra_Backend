from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from uuid import UUID as UUIDT
from datetime import datetime
from ..deps import get_db, get_account_id
from ..models import ChatSession, ChatMessage
from ..schemas import ChatSessionCreate, ChatSessionUpdate, ChatSessionOut, ChatSessionListItem

router = APIRouter(prefix="/api/chat/sessions", tags=["chat"])

# ---------------------------------------------------------------------------
# POST /api/chat/sessions
# Create a new chat session for the authenticated account.
# Optional 'name' allows UI to label a conversation (can be null and later auto‑named).
# ---------------------------------------------------------------------------
@router.post("", response_model=ChatSessionOut, status_code=201)
def create_session(
    payload: ChatSessionCreate,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    obj = ChatSession(account_id=account_id, name=payload.name)
    db.add(obj)
    db.flush()
    db.refresh(obj)
    return obj

# ---------------------------------------------------------------------------
# GET /api/chat/sessions
# List recent chat sessions for the account (sorted by last_active_at desc).
# Optional status filter: active | archived | closed
# 'limit' caps number of sessions for lightweight dashboards.
# ---------------------------------------------------------------------------
@router.get("", response_model=List[ChatSessionListItem])
def list_sessions(
    status: Optional[str] = Query(None, pattern="^(active|archived|closed)$"),
    limit: int = Query(20, ge=1, le=100),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    stmt = select(ChatSession).where(ChatSession.account_id == account_id)
    if status:
        stmt = stmt.where(ChatSession.status == status)
    stmt = stmt.order_by(desc(ChatSession.last_active_at)).limit(limit)
    sessions = list(db.scalars(stmt).all())
    return [
        ChatSessionListItem(
            session_id=s.session_id,
            name=s.name,
            last_active_at=s.last_active_at,
            status=s.status,
        )
        for s in sessions
    ]

# ---------------------------------------------------------------------------
# GET /api/chat/sessions/{session_id}
# Fetch full details of a single session.
# ---------------------------------------------------------------------------
@router.get("/{session_id}", response_model=ChatSessionOut)
def get_session(
    session_id: UUIDT,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    s = db.get(ChatSession, session_id)
    if not s or s.account_id != account_id:
        raise HTTPException(status_code=404, detail="session not found")
    return s

# ---------------------------------------------------------------------------
# PATCH /api/chat/sessions/{session_id}
# Update session name and/or status. Status can archive or close a session.
# Closed sessions should not accept new messages (enforced in chat endpoint).
# ---------------------------------------------------------------------------
@router.patch("/{session_id}", response_model=ChatSessionOut)
def update_session(
    session_id: UUIDT,
    payload: ChatSessionUpdate,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    s = db.get(ChatSession, session_id)
    if not s or s.account_id != account_id:
        raise HTTPException(status_code=404, detail="session not found")
    if payload.name is not None:
        s.name = payload.name.strip() or None
    if payload.status is not None:
        s.status = payload.status
    db.add(s)
    db.flush()
    db.refresh(s)
    return s

# ---------------------------------------------------------------------------
# GET /api/chat/sessions/{session_id}/messages
# List chat messages for a session (newest first) with simple pagination.
# Query params:
#   limit: max messages to return (default 50)
#   before_ts: ISO8601 timestamp – return messages strictly older than this
# Use successive calls with before_ts = oldest message_ts received to page backwards.
# ---------------------------------------------------------------------------
@router.get("/{session_id}/messages")
def list_session_messages(
    session_id: UUIDT,
    limit: int = Query(50, ge=1, le=200),
    before_ts: Optional[datetime] = Query(
        None,
        description="Return messages with message_ts < before_ts (ISO8601). For pagination."
    ),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    sess = db.get(ChatSession, session_id)
    if not sess or sess.account_id != account_id:
        raise HTTPException(status_code=404, detail="session not found")

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.message_ts))
        .limit(limit)
    )
    if before_ts:
        stmt = stmt.where(ChatMessage.message_ts < before_ts)

    rows = list(db.scalars(stmt).all())

    # Minimal inline shape (define a Pydantic schema later if needed)
    return [
        {
            "message_id": m.message_id,
            "message_ts": m.message_ts,
            "message_role": m.message_role,
            "message_text": m.message_text,
        }
        for m in rows
    ]