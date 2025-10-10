from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Any, Dict
from uuid import UUID
from datetime import datetime, date

# ---------- Chat ----------


class ChatAskIn(BaseModel):
    message_text: str


class ChatReplyOut(BaseModel):
    reply_text: str


# ---------- ChatSession ----------
class ChatSessionCreate(BaseModel):
    name: str | None = None  # optional custom title


class ChatSessionUpdate(BaseModel):
    name: str | None = None
    status: str | None = Field(default=None, pattern="^(active|archived|closed)$")


class ChatSessionOut(BaseModel):
    session_id: UUID
    account_id: UUID
    name: str | None
    created_at: datetime
    last_active_at: datetime
    status: str


class ChatSessionListItem(BaseModel):
    session_id: UUID
    name: str | None
    last_active_at: datetime
    status: str


# ---------- Mood ----------
class MoodCreate(BaseModel):
    mood_date: date
    mood_emoji: str
    mood_intensity: int = Field(ge=1, le=3)
    note: Optional[str] = None


class MoodUpdate(BaseModel):
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
    updated_at: datetime


class MoodSummaryItem(BaseModel):
    emotion_id: Optional[int]
    emoji: str
    count: int


# ---------- Strategy ----------


class StrategyOut(BaseModel):
    strategy_id: str
    strategy_name: str
    strategy_desc: Optional[str] = None
    strategy_duration: Optional[int] = None
    strategy_requirements: Optional[Dict[str, Any]] = None
    strategy_instruction: Optional[str] = None
    strategy_source: Optional[Dict[str, Any]] = None
    strategy_category: Optional[str] = None


# ---------- Activity ----------
class ActivityCreate(BaseModel):
    strategy_id: str
    emotion_before: str


class ActivityUpdate(BaseModel):
    activity_status: Optional[str] = Field(
        default=None, pattern="^(pending|completed|abandoned)$"
    )
    emotion_after: Optional[str] = None


class ActivityOut(BaseModel):
    activity_id: UUID
    account_id: UUID
    strategy_id: str
    activity_ts: datetime
    activity_status: str
    emotion_before: str
    emotion_after: Optional[str] = None
    message_id: Optional[UUID] = None


# ---------- Crisis ----------
class CrisisAlertOut(BaseModel):
    crisis_alert_id: UUID
    crisis_alert_severity: str
    crisis_alert_status: str
    crisis_strategy_text: Optional[dict] = None


# ---------- Auth ----------
class AuthSessionOut(BaseModel):
    account_id: UUID
    email: str | None
    display_name: str
    account_type: str
    status: str


# --------- Invites ----------
class InviteCreateIn(BaseModel):
    invitee_email: EmailStr


class InviteOut(BaseModel):
    invite_id: UUID
    invitee_email: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None
    accepted_account_id: UUID | None = None
    share_url: str | None = None  # only on creation response


class InviteAcceptIn(BaseModel):
    token: str  # raw invite token from link


class InviteListItem(BaseModel):
    invite_id: UUID
    invitee_email: str
    status: str
    expires_at: datetime
    accepted_at: datetime | None = None


# --------- Links ----------
class LinkedChild(BaseModel):
    account_id: UUID
    display_name: str
    email: str | None


class LinkedGuardian(BaseModel):
    account_id: UUID
    display_name: str
    email: str | None
