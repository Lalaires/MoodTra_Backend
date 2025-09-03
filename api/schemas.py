from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime, date

# ---------- Chat ----------

class ChatAskIn(BaseModel):
    message_text: str

class ChatReplyOut(BaseModel):
    reply_text: str

# ---------- Mood ----------
class MoodCreate(BaseModel):
    mood_date: date | None = None
    mood_emoji: str
    mood_intensity: int = Field(ge=1, le=3)
    note: Optional[str] = None

class MoodOut(BaseModel):
    mood_id: UUID
    account_id: UUID
    mood_date: date
    mood_emoji: str
    mood_intensity: int
    note: Optional[str]
    linked_emotion_id: Optional[int]
    created_at: datetime

class MoodSummaryItem(BaseModel):
    emotion_id: Optional[int]
    emoji: str
    count: int
