from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc, func, bindparam
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime, timezone
import logging

from AI.pipeline import MindPal_Pipeline

from ..deps import get_db, get_session_id
from ..models import ChatMessage, Strategy, StrategyEmotion, EmotionLabel
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
        history_context = ""
        lines = []
        for role, msg in history:
            # guard against None and trim overly long single messages
            safe_msg = (msg or "").strip()
            if len(safe_msg) > 800:
                safe_msg = safe_msg[:800] + " ..."
            lines.append(f"{role}: {safe_msg}")
        history_context = "\n".join(lines)
        
        # Fetch 3 most recent messages from child only
        child_messages = db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.message_role == "child"
            )
            .order_by(desc(ChatMessage.message_ts))
            .limit(3)
        ).scalars().all()
        child_history_rows = list(reversed(child_messages))
        child_history: list[str] = [msg.message_text for msg in child_history_rows]
        child_history_context = ""
        lines = []
        for msg in child_history:
            # guard against None and trim overly long single messages
            safe_msg = (msg or "").strip()
            if len(safe_msg) > 800:
                safe_msg = safe_msg[:800] + " ..."
            lines.append(f"{safe_msg}")
        child_history_context = "\n".join(lines)

        emotion= get_pipeline().emotion_detection(child_history_context)
        top_emotion = emotion[0]["label"]

        strategies = db.execute(
            select(Strategy)
            .join(StrategyEmotion, StrategyEmotion.strategy_id == Strategy.strategy_id)
            .join(EmotionLabel, EmotionLabel.emotion_id == StrategyEmotion.emotion_id)
            .where(func.lower(EmotionLabel.name) == func.lower(bindparam("emotion")))
            .params(emotion=top_emotion)
        ).scalars().all()

        # Convert strategies to string format
        strategies_string = ""
        if strategies:
            strategy_lines = []
            for i, strategy in enumerate(strategies):
                strategy_info = f"{i+1}. Name: {strategy.strategy_name}, Description: {strategy.strategy_desc}, Instruction: {strategy.strategy_instruction}, Duration: {strategy.strategy_duration}, Requirements: {strategy.strategy_requirements}."
                strategy_lines.append(strategy_info)
            strategies_string = "\n".join(strategy_lines)
            print(f"Strategies string: {strategies_string}")

        # Generate reply via AI pipeline with history context
        reply_text = get_pipeline().chat(message_text, detected_emotion=emotion, history_context=history_context, strategies=strategies_string)

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
