from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import timedelta, date 

from ..deps import get_db, get_account_id
from ..models import MoodLog, EmotionLabel
from ..schemas import MoodCreate, MoodOut, MoodSummaryItem
from ..utils import start_of_day, end_of_day, to_utc_now

router = APIRouter(prefix="/mood", tags=["mood"])

# EndPoint for moods each day for date range
@router.get("/entries", response_model=list[MoodOut])
def list_entries(
    account_id = Depends(get_account_id),
    start: date | None = Query(default=None, description="Start of date range (YYYY-MM-DD)"),
    end:   date | None = Query(default=None, description="End of date range (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    q = select(MoodLog).where(MoodLog.account_id == account_id)
    if start:
        q = q.where(MoodLog.mood_date >= start)
    if end:
        q = q.where(MoodLog.mood_date <= end)
    q = q.order_by(MoodLog.mood_date.desc(), MoodLog.created_at.desc())
    return db.execute(q).scalars().all()

# EndPoint for latest mood each day for date range
@router.get("/entries/latest", response_model=list[MoodOut])
def list_latest_per_day(
    account_id = Depends(get_account_id),
    start: date | None = Query(default=None, description="Start of date range (YYYY-MM-DD)"),
    end: date | None = Query(default=None, description="End of date range (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    day_col = MoodLog.mood_date
    rn = func.row_number().over(
        partition_by=[MoodLog.account_id, day_col],
        order_by=MoodLog.created_at.desc()
    ).label("rn")

    q = select(
        MoodLog.mood_id, MoodLog.account_id, MoodLog.mood_date,
        MoodLog.mood_emoji, MoodLog.mood_intensity, MoodLog.note,
        MoodLog.linked_emotion_id, MoodLog.created_at, rn
    ).where(MoodLog.account_id == account_id)

    if start: q = q.where(MoodLog.mood_date >= start)
    if end:   q = q.where(MoodLog.mood_date <=  end)

    sub = q.subquery()
    rows = db.execute(select(sub).where(sub.c.rn == 1).order_by(sub.c.mood_date.desc())).mappings().all()

    return [dict(
        mood_id=r["mood_id"], account_id=r["account_id"], mood_date=r["mood_date"],
        mood_emoji=r["mood_emoji"], mood_intensity=r["mood_intensity"], note=r["note"],
        linked_emotion_id=r["linked_emotion_id"], created_at=r["created_at"]
    ) for r in rows]

# EndPoint for latest mood for today
@router.get("/entries/today/latest", response_model=MoodOut | None)
def latest_for_today(account_id = Depends(get_account_id), db: Session = Depends(get_db)):
    today = to_utc_now().date()
    row = db.execute(
        select(MoodLog)
        .where(MoodLog.account_id == account_id, MoodLog.mood_date == today)
        .order_by(MoodLog.created_at.desc())
        .limit(1)
    ).scalars().first()
    return row


@router.post("/entries", response_model=MoodOut, status_code=201)
def create_entry(
    payload: MoodCreate,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    day: date = payload.mood_date or to_utc_now().date()

    # Look up emotion_id by emoji
    emotion_id = db.execute(
        select(EmotionLabel.emotion_id).where(EmotionLabel.emoji == payload.mood_emoji)
    ).scalar_one_or_none()
    if emotion_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"No emotion_label found for emoji '{payload.mood_emoji}'."
        )

    row = MoodLog(
        mood_id=uuid4(),
        account_id=account_id,
        mood_date=day,
        mood_emoji=payload.mood_emoji,
        mood_intensity=payload.mood_intensity,
        note=payload.note,
        linked_emotion_id=emotion_id,     # auto-mapped
        created_at=to_utc_now(),
    )
    db.add(row)
    db.flush()
    return row

# Summary End Points

def _latest_per_day_counts(
    db: Session,
    account_id,
    start: date,
    end: date,
) -> list[tuple[str, int]]:
    """
    Returns [(emoji, count)] counting only the latest row per day in [start, end).
    """
    # Window function to rank rows within each (account_id, mood_date) by created_at desc
    rn = func.row_number().over(
        partition_by=(MoodLog.account_id, MoodLog.mood_date),
        order_by=MoodLog.created_at.desc()
    ).label("rn")

    sub = (
        select(
            MoodLog.mood_date.label("mood_date"),
            MoodLog.mood_emoji.label("mood_emoji"),
            rn
        )
        .where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date >= start,
            MoodLog.mood_date <  end,
        )
        .subquery()
    )

    rows = db.execute(
        select(sub.c.mood_emoji, func.count().label("count"))
        .where(sub.c.rn == 1)
        .group_by(sub.c.mood_emoji)
        .order_by(func.count().desc())
    ).all()
    return rows

def start_of_week(as_of: date, week_start: int = 0) -> date:
    delta = (as_of.weekday() - week_start) % 7  # 0=Mon..6=Sun
    return as_of - timedelta(days=delta)

def week_bounds(as_of: date, week_start: int, full_week: bool) -> tuple[date, date]:
    start = start_of_week(as_of, week_start)
    end = start + timedelta(days=7) if full_week else as_of + timedelta(days=1)
    return start, end

def month_bounds(as_of: date, full_month: bool) -> tuple[date, date]:
    start = as_of.replace(day=1)
    if full_month:
        # first day of next month
        end = start.replace(year=start.year + (start.month // 12),
                            month=(start.month % 12) + 1, day=1)
    else:
        end = as_of + timedelta(days=1)  # month-to-date (include as_of)
    return start, end

@router.get("/summary/weekly", response_model=list[MoodSummaryItem])
def weekly_summary(
    account_id = Depends(get_account_id),
    as_of: date = Query(default_factory=date.today,
                        description="Anchor date (YYYY-MM-DD). Defaults to today."),
    week_start: int = Query(0, ge=0, le=6, description="0=Mon .. 6=Sun"),
    full_week: bool = Query(False, description="True = full calendar week; False = week-to-date"),
    latest_only: bool = Query(True, description="Count only the latest mood per day"),
    db: Session = Depends(get_db),
):
    start, end = week_bounds(as_of, week_start, full_week)
    if latest_only:
        rows = _latest_per_day_counts(db, account_id, start, end)
    else:
        rows = db.execute(
            select(MoodLog.mood_emoji, func.count())
            .where(MoodLog.account_id == account_id,
                   MoodLog.mood_date >= start,
                   MoodLog.mood_date <  end)
            .group_by(MoodLog.mood_emoji)
            .order_by(func.count().desc())
        ).all()
    return [{"emoji": r[0], "count": r[1], "emotion_id": None} for r in rows]

@router.get("/summary/monthly", response_model=list[MoodSummaryItem])
def monthly_summary(
    account_id = Depends(get_account_id),
    as_of: date = Query(default_factory=date.today,
                        description="Anchor date (YYYY-MM-DD). Defaults to today."),
    full_month: bool = Query(False, description="True = full calendar month; False = month-to-date"),
    latest_only: bool = Query(True, description="Count only the latest mood per day"),
    db: Session = Depends(get_db),
):
    start, end = month_bounds(as_of, full_month)
    if latest_only:
        rows = _latest_per_day_counts(db, account_id, start, end)
    else:
        rows = db.execute(
            select(MoodLog.mood_emoji, func.count())
            .where(MoodLog.account_id == account_id,
                   MoodLog.mood_date >= start,
                   MoodLog.mood_date <  end)
            .group_by(MoodLog.mood_emoji)
            .order_by(func.count().desc())
        ).all()
    return [{"emoji": r[0], "count": r[1], "emotion_id": None} for r in rows]