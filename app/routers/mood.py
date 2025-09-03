from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import timedelta, date 

from ..deps import get_db, get_account_id
from ..models import MoodLog
from ..schemas import MoodCreate, MoodOut, MoodUpdate, MoodSummaryItem
from ..utils import start_of_day, end_of_day, to_utc_now

router = APIRouter(prefix="/mood", tags=["mood"])

# EndPoint for moods each day for date range
@router.get("/entries", response_model=list[MoodOut])
def list_entries(
    account_id = Depends(get_account_id),
    start: date | None = Query(default=None, description="Include moods on/after this date (YYYY-MM-DD)"),
    end:   date | None = Query(default=None, description="Exclude moods on/after this date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    q = select(MoodLog).where(MoodLog.account_id == account_id)
    if start:
        q = q.where(MoodLog.mood_date >= start)
    if end:
        q = q.where(MoodLog.mood_date < end)
    q = q.order_by(MoodLog.mood_date.desc(), MoodLog.created_at.desc())
    return db.execute(q).scalars().all()

# EndPoint for latest mood each day for date range
@router.get("/entries/latest", response_model=list[MoodOut])
def list_latest_per_day(
    account_id = Depends(get_account_id),
    start: date | None = Query(default=None, description="Include latest moods each day on/after this date (YYYY-MM-DD)"),
    end: date | None = Query(default=None, description="Exclude moods each day on/after this date (YYYY-MM-DD)"),
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
    if end:   q = q.where(MoodLog.mood_date <  end)

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
def create_entry(payload: MoodCreate, account_id = Depends(get_account_id), db: Session = Depends(get_db)):
    # default mood_date = today (server side)
    day = payload.mood_date or to_utc_now().date()
    row = MoodLog(
        mood_id=uuid4(),
        account_id=account_id,
        mood_date=day,
        mood_emoji=payload.mood_emoji,
        mood_intensity=payload.mood_intensity,
        note=payload.note,
        linked_emotion_id=payload.linked_emotion_id,
        created_at=to_utc_now(),   # precise creation time
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

def _range_for_week_ending(today: date):
    start = today - timedelta(days=6)   # last 7 calendar days including today
    end   = today + timedelta(days=1)   # half-open end
    return start, end

def _range_for_month(today: date):
    first = today.replace(day=1)
    # simple next-month calculation
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1)
    else:
        next_first = first.replace(month=first.month + 1)
    return first, next_first

@router.get("/summary/weekly", response_model=list[MoodSummaryItem])
def weekly_summary(
    account_id = Depends(get_account_id),
    latest_only: bool = True,
    db: Session = Depends(get_db),
):
    start, end = _range_for_week_ending(date.today())
    rows = (_latest_per_day_counts if latest_only else _all_counts)(db, account_id, start, end)
    return [{"emoji": r[0], "count": r[1]} for r in rows]

@router.get("/summary/monthly", response_model=list[MoodSummaryItem])
def monthly_summary(
    account_id = Depends(get_account_id),
    latest_only: bool = True,
    db: Session = Depends(get_db),
):
    start, end = _range_for_month(date.today())
    rows = (_latest_per_day_counts if latest_only else _all_counts)(db, account_id, start, end)
    return [{"emoji": r[0], "count": r[1]} for r in rows]
