# api/routers/mood.py
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..deps import get_db, get_account_id
from ..models import MoodLog, EmotionLabel
from ..schemas import MoodCreate, MoodUpdate, MoodOut, MoodSummaryItem

router = APIRouter(
    prefix="/mood",
    tags=["mood"],
    responses={404: {"description": "Not found"}},
)

"""
Mood Log API (one entry per day, per account)

- POST /entries
  Create a new mood entry for a specific date. Returns 409 if that date already exists.

- PUT /entries/{mood_date}
  Update the existing mood entry for a specific date. Returns 404 if missing.

- DELETE /entries/{mood_date}
  Delete the mood entry for a specific date. Idempotent (returns 204 even if not found).

- GET /entries/{mood_date}
  Fetch the mood entry for a single date. Returns 404 if none.

- GET /entries?start=YYYY-MM-DD&end=YYYY-MM-DD
  List entries in an inclusive date range (sorted newest-first).

- GET /summary/weekly?as_of=YYYY-MM-DD&week_start=0
  Week-to-date summary for the week containing `as_of`. `week_start`: 0=Mon .. 6=Sun.

- GET /summary/monthly?as_of=YYYY-MM-DD
  Month-to-date summary for the month containing `as_of`.
"""


# ---------- Helpers ----------

def _map_emoji_to_emotion_id(db: Session, emoji: str) -> int | None:
    """Map UI emoji to emotion_label.emotion_id (returns None if not found)."""
    return db.execute(
        select(EmotionLabel.emotion_id).where(EmotionLabel.emoji == emoji)
    ).scalar_one_or_none()


# ---------- CREATE ----------

@router.post(
    "/entries",
    response_model=MoodOut,
    status_code=201,
    summary="Create a new mood entry (one per day)",
)
def create_entry(
    payload: MoodCreate,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    Create a new mood entry for the given `mood_date`.

    - Enforces one entry per account per day; returns **409 Conflict** if an entry already exists.
    - Automatically maps `mood_emoji` to `linked_emotion_id` using the `emotion_label` table.
    """
    # uniqueness check
    existing = db.execute(
        select(MoodLog).where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date == payload.mood_date,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Mood entry already exists for this date.")

    linked_id = _map_emoji_to_emotion_id(db, payload.mood_emoji)
    if linked_id is None:
        raise HTTPException(status_code=400, detail=f"No emotion_label found for emoji '{payload.mood_emoji}'.")

    row = MoodLog(
        account_id=account_id,
        mood_date=payload.mood_date,
        mood_emoji=payload.mood_emoji,
        mood_intensity=payload.mood_intensity,
        note=payload.note,
        linked_emotion_id=linked_id,
    )
    db.add(row)
    db.flush()     # assign mood_id
    db.refresh(row)
    db.commit()
    return row


# ---------- UPDATE ----------

@router.put(
    "/entries/{mood_date}",
    response_model=MoodOut,
    summary="Update an existing mood entry for a date",
)
def update_entry(
    mood_date: date = Path(..., description="The calendar date (YYYY-MM-DD) of the mood entry to update."),
    payload: MoodUpdate = ...,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    Update the mood entry for a specific `mood_date`.

    - Returns **404 Not Found** if no entry exists for that date.
    - Updates `mood_emoji`, `mood_intensity`, `note`, and refreshes `updated_at`.
    """
    row = db.execute(
        select(MoodLog).where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date == mood_date,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No mood entry for this date.")

    linked_id = _map_emoji_to_emotion_id(db, payload.mood_emoji)
    if linked_id is None:
        raise HTTPException(status_code=400, detail=f"No emotion_label found for emoji '{payload.mood_emoji}'.")

    row.mood_emoji = payload.mood_emoji
    row.mood_intensity = payload.mood_intensity
    row.note = payload.note
    row.linked_emotion_id = linked_id
    row.updated_at = func.now()
    db.flush()
    db.refresh(row)
    db.commit()
    return row


# ---------- DELETE ----------

@router.delete(
    "/entries/{mood_date}",
    status_code=204,
    summary="Delete a mood entry for a date",
)
def delete_entry(
    mood_date: date = Path(..., description="The calendar date (YYYY-MM-DD) of the mood entry to delete."),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    Delete the mood entry for `mood_date`.

    - Idempotent: returns **204 No Content** even if the entry does not exist.
    """
    row = db.execute(
        select(MoodLog).where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date == mood_date,
        )
    ).scalar_one_or_none()

    if row:
        db.delete(row)
        db.commit()

    return Response(status_code=204)


# ---------- GET single date ----------

@router.get(
    "/entries/{mood_date}",
    response_model=MoodOut,
    summary="Get the mood entry for a specific date",
)
def get_entry_for_date(
    mood_date: date = Path(..., description="The calendar date (YYYY-MM-DD) to fetch."),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """Return the mood entry for `mood_date` or **404** if it doesn't exist."""
    row = db.execute(
        select(MoodLog).where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date == mood_date,
        )
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="No mood entry for this date.")
    return row


# ---------- GET range (inclusive) ----------

@router.get(
    "/entries",
    response_model=List[MoodOut],
    summary="List mood entries for an inclusive date range",
)
def list_entries(
    start: date = Query(..., description="Inclusive start date (YYYY-MM-DD)."),
    end: date = Query(..., description="Inclusive end date (YYYY-MM-DD)."),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    List all entries between `start` and `end` (inclusive), newest first.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="`end` must be on or after `start`.")

    q = (
        select(MoodLog)
        .where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date >= start,
            MoodLog.mood_date <= end,
        )
        .order_by(MoodLog.mood_date.desc())
    )
    return db.execute(q).scalars().all()


# ---------- WEEKLY SUMMARY (week-to-date for anchor week) ----------

@router.get(
    "/summary/weekly",
    response_model=List[MoodSummaryItem],
    summary="Weekly mood summary (week-to-date for the week containing `as_of`)",
)
def weekly_summary(
    as_of: date = Query(
        default_factory=date.today,
        description="Anchor date; the **week containing this date** is summarized (week-to-date, inclusive).",
    ),
    week_start: int = Query(
        0,
        ge=0,
        le=6,
        description="Which weekday begins the week? 0=Monday .. 6=Sunday. Default: 0 (Monday).",
    ),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    For the week that contains `as_of`, count entries from the start of that week **through `as_of` (inclusive)**.
    Returns items like: `{ "emoji": "🙂", "emotion_id": 8, "count": 3 }`.
    """
    # Compute start-of-week containing as_of
    dow = (as_of.weekday() - week_start) % 7
    start = as_of - timedelta(days=dow)
    end = as_of

    q = (
        select(MoodLog.mood_emoji, MoodLog.linked_emotion_id, func.count().label("count"))
        .where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date >= start,
            MoodLog.mood_date <= end,
        )
        .group_by(MoodLog.mood_emoji, MoodLog.linked_emotion_id)
        .order_by(func.count().desc(), MoodLog.mood_emoji)
    )
    rows = db.execute(q).all()
    return [{"emoji": e, "emotion_id": eid, "count": c} for (e, eid, c) in rows]


# ---------- MONTHLY SUMMARY (month-to-date for anchor month) ----------

@router.get(
    "/summary/monthly",
    response_model=List[MoodSummaryItem],
    summary="Monthly mood summary (month-to-date for the month containing `as_of`)",
)
def monthly_summary(
    as_of: date = Query(
        default_factory=date.today,
        description="Anchor date; the **month containing this date** is summarized (month-to-date, inclusive).",
    ),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    """
    For the month that contains `as_of`, count entries from the 1st of that month **through `as_of` (inclusive)**.
    Returns items like: `{ "emoji": "🙂", "emotion_id": 8, "count": 10 }`.
    """
    start = as_of.replace(day=1)
    end = as_of

    q = (
        select(MoodLog.mood_emoji, MoodLog.linked_emotion_id, func.count().label("count"))
        .where(
            MoodLog.account_id == account_id,
            MoodLog.mood_date >= start,
            MoodLog.mood_date <= end,
        )
        .group_by(MoodLog.mood_emoji, MoodLog.linked_emotion_id)
        .order_by(func.count().desc(), MoodLog.mood_emoji)
    )
    rows = db.execute(q).all()
    return [{"emoji": e, "emotion_id": eid, "count": c} for (e, eid, c) in rows]
