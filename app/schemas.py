from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime, date

# ---------- Chat ----------
class ChatMessageIn(BaseModel):
    message_text: str = Field(min_length=1)
    message_role: str = Field(pattern="^(child|assistant)$")

class ChatMessageOut(BaseModel):
    message_id: UUID
    session_id: Optional[UUID]
    message_ts: datetime
    message_role: str
    message_text: str

# ---------- Mood ----------
class MoodCreate(BaseModel):
    mood_date: date | None = None
    mood_emoji: str
    mood_intensity: int = Field(ge=1, le=3)
    note: Optional[str] = None

class MoodOut(BaseModel):
    mood_id: UUID
    account_id: UUID
    mood_date: datetime
    mood_emoji: str
    mood_intensity: int
    note: Optional[str]
    linked_emotion_id: Optional[int]
    created_at: datetime

class MoodSummaryItem(BaseModel):
    emoji: str
    count: int
