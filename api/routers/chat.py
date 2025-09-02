import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from AI.pipeline import MindPal_Pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])
pipeline = MindPal_Pipeline()

class ChatIn(BaseModel):
    message: str

class ChatOut(BaseModel):
    reply: str

@router.post("/chat", response_model=ChatOut)
def chat_endpoint(body: ChatIn):
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        reply = pipeline.chat(msg)
        return ChatOut(reply=reply)
    except Exception as e:

        logger.exception("chat failed")

        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}: {e}")
