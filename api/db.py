from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv
import os

from sqlalchemy import text
from contextlib import contextmanager

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

# SQLAlchemy (sync) engine + session factory
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_db():
    """Context manager to get/close a session safely."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()

def upsert_account_by_sub(db, *, sub: str, email: str | None, name: str | None):
    """
    Insert if new; else update last_login_at/email/name.
    Defaults account_type to 'child' for now.
    Returns: dict with account_id, account_type, email
    """
    sql = text("""
        INSERT INTO account (cognito_sub, email, display_name, account_type, created_at, last_login_at, status)
        VALUES (:sub, LOWER(:email), :name, 'child', NOW(), NOW(), 'active')
        ON CONFLICT (cognito_sub)
        DO UPDATE SET
          email = COALESCE(LOWER(EXCLUDED.email), account.email),
          display_name = COALESCE(EXCLUDED.display_name, account.display_name),
          last_login_at = NOW()
        RETURNING account_id, account_type, email
    """)
    row = db.execute(sql, {"sub": sub, "email": email, "name": name}).mappings().first()
    return dict(row) if row else None