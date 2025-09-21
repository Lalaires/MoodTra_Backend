from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from uuid import UUID as UUIDT
from datetime import date, datetime, time as dt_time, timedelta, timezone

from ..deps import get_db, get_account_id
from ..models import Activity
from ..schemas import ActivityCreate, ActivityUpdate, ActivityOut

router = APIRouter(prefix="/activity", tags=["activity"])

# Create a new activity
@router.post("", response_model=ActivityOut, status_code=201)
def create_activity(
    payload: ActivityCreate,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    obj = Activity(
        account_id=account_id,
        strategy_id=payload.strategy_id,
        emotion_before=payload.emotion_before,
        activity_status="pending",
    )
    db.add(obj)
    db.flush()
    db.refresh(obj)
    return obj

# Update activity (status and/or emotion_after)
@router.patch("/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: UUIDT = Path(..., description="Activity UUID"),
    payload: ActivityUpdate = ...,
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    obj = db.get(Activity, activity_id)
    if not obj or obj.account_id != account_id:
        raise HTTPException(status_code=404, detail="Activity not found")

    if payload.activity_status is not None:
        obj.activity_status = payload.activity_status
    if payload.emotion_after is not None:
        obj.emotion_after = payload.emotion_after

    db.add(obj)
    db.flush()
    db.refresh(obj)
    return obj

# List activities in a date range (default: current month)
@router.get("", response_model=List[ActivityOut])
def list_activities(
    start_date: Optional[date] = Query(None, description="YYYY-MM-DD (defaults to first day of current month)"),
    end_date: Optional[date] = Query(None, description="YYYY-MM-DD (defaults to last day of current month)"),
    limit: int = Query(50, ge=1, le=200),
    account_id = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    # Defaults: current month
    today = date.today()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(days=1)

    start_date = start_date or month_start
    end_date = end_date or month_end
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    # Use half-open range on timestamp to keep index-friendly filter
    start_dt = datetime.combine(start_date, dt_time.min).replace(tzinfo=timezone.utc)
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), dt_time.min).replace(tzinfo=timezone.utc)

    stmt = (
        select(Activity)
        .where(
            Activity.account_id == account_id,
            Activity.activity_ts >= start_dt,
            Activity.activity_ts < end_dt_exclusive,
        )
        .order_by(desc(Activity.activity_ts))
        .limit(limit)
    )
    return list(db.scalars(stmt).all())