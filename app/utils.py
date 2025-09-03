from datetime import datetime, timezone, timedelta

def start_of_day(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

def end_of_day(dt: datetime) -> datetime:
    return start_of_day(dt) + timedelta(days=1)

def to_utc_now() -> datetime:
    return datetime.now(timezone.utc)
