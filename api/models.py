from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, TIMESTAMP, SmallInteger, Numeric, ForeignKey, Date, UniqueConstraint, func, text, CheckConstraint
from uuid import uuid4, UUID as UUIDT
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import JSONB

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

# Table: strategy
class Strategy(Base):
    __tablename__ = "strategy"
    strategy_id: Mapped[str] = mapped_column(primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_desc: Mapped[str | None] = mapped_column(Text)
    strategy_duration: Mapped[int | None] = mapped_column(SmallInteger)
    strategy_requirements: Mapped[dict | None] = mapped_column(JSONB)
    strategy_instruction: Mapped[str | None] = mapped_column(Text)
    strategy_source: Mapped[dict | None] = mapped_column(JSONB)
    strategy_category: Mapped[str | None] = mapped_column(Text)

# Link table: strategy_emotion
class StrategyEmotion(Base):
    __tablename__ = "strategy_emotion"
    
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategy.strategy_id", ondelete="CASCADE"), primary_key=True)
    emotion_id: Mapped[int] = mapped_column(ForeignKey("emotion_label.emotion_id", ondelete="CASCADE"), primary_key=True)

# Table: activity
class Activity(Base):
    __tablename__ = "activity"

    # DB column has no server default, so supply a Python-side default
    activity_id: Mapped[UUIDT] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUIDT] = mapped_column(ForeignKey("account.account_id", ondelete="CASCADE"), nullable=False)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategy.strategy_id", ondelete="RESTRICT"), nullable=False)
    activity_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    activity_status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"), nullable=False)
    emotion_before: Mapped[str] = mapped_column(Text, nullable=False)  # emoji
    emotion_after: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[UUIDT | None] = mapped_column(ForeignKey("chat_message.message_id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint(
            "activity_status IN ('pending','completed','abandoned')",
            name="activity_status_chk",
        ),
    )

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
    __table_args__ = (
        UniqueConstraint("account_id", "mood_date", name="uq_mood_log_account_date"),
    )

    mood_id: Mapped[UUIDT] = mapped_column(primary_key=True)
    account_id: Mapped[UUIDT] = mapped_column(ForeignKey("account.account_id", ondelete="CASCADE"), nullable=False)
    mood_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood_emoji: Mapped[str] = mapped_column(Text, nullable=False)
    mood_intensity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    linked_emotion_id: Mapped[int | None] = mapped_column(ForeignKey("emotion_label.emotion_id"))

    # timestamps
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

# Table: crisis_alert
class CrisisAlert(Base):
    __tablename__ = "crisis_alert"
    crisis_alert_id: Mapped[UUIDT] = mapped_column(primary_key=True)
    account_id: Mapped[UUIDT] = mapped_column(ForeignKey("account.account_id", ondelete="CASCADE"), nullable=False)
    crisis_id: Mapped[int] = mapped_column(ForeignKey("crisis.crisis_id", ondelete="CASCADE"), nullable=False)
    crisis_alert_severity: Mapped[str] = mapped_column(Text, nullable=False)
    crisis_alert_status: Mapped[str] = mapped_column(Text, nullable=False)
    crisis_alert_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    crisis_alert_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_msg_ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
