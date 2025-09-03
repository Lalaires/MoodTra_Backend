from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime

from ..deps import get_db, get_session_id
from ..models import ChatMessage
from ..schemas import ChatMessageIn, ChatMessageOut

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/messages", response_model=list[ChatMessageOut])
def get_messages(
    session_id = Depends(get_session_id),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.message_ts)
    if limit:
        q = q.limit(limit)
    return db.execute(q).scalars().all()

@router.post("/messages", response_model=ChatMessageOut, status_code=201)
def post_message(
    payload: ChatMessageIn,
    session_id = Depends(get_session_id),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    msg = ChatMessage(
        message_id=uuid4(),
        session_id=session_id,
        message_ts=now,
        message_role=payload.message_role,
        message_text=payload.message_text,
        message_emotion_id=payload.message_emotion_id,
        confidence=payload.confidence,
    )
    db.add(msg)      # now "db" is a real Session
    db.flush()
    return msg
