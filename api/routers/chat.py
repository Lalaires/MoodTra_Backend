from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime, timezone
import logging

from AI.pipeline import MindPal_Pipeline

from ..deps import get_db, get_session_id
from ..models import ChatMessage
from ..schemas import ChatAskIn, ChatReplyOut

router = APIRouter(prefix="/api", tags=["chat"])

logger = logging.getLogger(__name__)

# Lazy-initialized pipeline to avoid heavy import-time cost
_pipeline: MindPal_Pipeline | None = None

def get_pipeline() -> MindPal_Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MindPal_Pipeline()
    return _pipeline

@router.post("/chat", response_model=ChatReplyOut, status_code=200)
def chat_endpoint(
    payload: ChatAskIn,
    session_id = Depends(get_session_id),
    db: Session = Depends(get_db)
):
    message_text = (payload.message_text or "").strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    now = datetime.now(timezone.utc)
    try:
        # Store user's message
        user_msg = ChatMessage(
            message_id=uuid4(),
            session_id=session_id,
            message_ts=now,
            message_role="child",
            message_text=message_text,
        )
        db.add(user_msg)
        db.flush()

        # Fetch only recent session history (most recent first), then reverse to chronological
        MAX_HISTORY_MESSAGES = 20  # roughly 10 user-assistant exchanges
        history_rows_desc = db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.message_ts))
            .limit(MAX_HISTORY_MESSAGES)
        ).scalars().all()
        history_rows = list(reversed(history_rows_desc))
        history: list[tuple[str, str]] = [(r.message_role, r.message_text) for r in history_rows]

        # Generate reply via AI pipeline with history context
        reply_text = get_pipeline().chat(message_text, history_messages=history)

        # Store assistant's reply
        assistant_msg = ChatMessage(
            message_id=uuid4(),
            session_id=session_id,
            message_ts=datetime.now(timezone.utc),
            message_role="assistant",
            message_text=reply_text,
        )
        db.add(assistant_msg)
        db.flush()
        db.commit() # Many

        return ChatReplyOut(reply_text=reply_text)
    except Exception as e:
        db.rollback() # Many
        logger.exception("chat ask failed")
        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}: {e}")
