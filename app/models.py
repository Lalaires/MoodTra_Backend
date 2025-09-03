from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, TIMESTAMP, SmallInteger, Numeric, ForeignKey, Date
from uuid import uuid4, UUID as UUIDT
from datetime import datetime, date

class Base(DeclarativeBase):
    pass

# Table: account
class Account(Base):
    __tablename__ = "account"
    account_id: Mapped[UUIDT] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

# Table: chat_session
class ChatSession(Base):
    __tablename__ = "chat_session"
    session_id: Mapped[UUIDT] = mapped_column(primary_key=True)
    account_id: Mapped[UUIDT] = mapped_column(ForeignKey("account.account_id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

# Table: emotion_label
class EmotionLabel(Base):
    __tablename__ = "emotion_label"
    emotion_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    emoji: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)

# Table: chat_message
class ChatMessage(Base):
    __tablename__ = "chat_message"
    message_id: Mapped[UUIDT] = mapped_column(primary_key=True)
    session_id: Mapped[UUIDT | None] = mapped_column(ForeignKey("chat_session.session_id", ondelete="SET NULL"))
    message_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    message_role: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

# Table: mood_log
class MoodLog(Base):
    __tablename__ = "mood_log"
    mood_id: Mapped[UUIDT] = mapped_column(primary_key=True)
    account_id: Mapped[UUIDT] = mapped_column(ForeignKey("account.account_id", ondelete="CASCADE"), nullable=False)
    mood_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood_emoji: Mapped[str] = mapped_column(Text, nullable=False)
    mood_intensity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    linked_emotion_id: Mapped[int | None] = mapped_column(ForeignKey("emotion_label.emotion_id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
