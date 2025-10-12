# api/routers/auth_session.py
import os
import requests
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..deps import get_db
from ..models import Account
from ..schemas import AuthSessionOut
from ..auth.cognito import verify_id_token

router = APIRouter(prefix="/auth", tags=["auth"])

# --- ENV: prefer standard names, keep backward-compat fallback ---
COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN", "")  # can be full URL or just host
CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID") or os.getenv("COGNITO_AUDIENCE", "")
DEFAULT_REDIRECT_URI = os.getenv("COGNITO_REDIRECT_URI")  # optional default

class CodeLoginIn(BaseModel):
    code: str
    code_verifier: str | None = None
    redirect_uri: str | None = None

def build_token_url(domain: str) -> str:
    """Accepts either a full https URL or just the hosted domain; returns <base>/oauth2/token."""
    d = domain.strip().rstrip("/")
    if not d:
        raise HTTPException(status_code=500, detail="COGNITO_DOMAIN not configured")
    if d.startswith("http://") or d.startswith("https://"):
        base = d
    else:
        base = f"https://{d}"
    return f"{base}/oauth2/token"

@router.post("/code-login", response_model=AuthSessionOut)
def login_with_code(payload: CodeLoginIn, db: Session = Depends(get_db)):
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail="Cognito client id not configured")
    token_url = build_token_url(COGNITO_DOMAIN)

    redirect_uri = payload.redirect_uri or DEFAULT_REDIRECT_URI
    if not redirect_uri:
        # Cognito requires the same redirect_uri used during /login; make it explicit
        raise HTTPException(status_code=400, detail="redirect_uri required")

    # --- Exchange authorization code -> tokens ---
    form = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": payload.code,
        "redirect_uri": redirect_uri,
    }
    if payload.code_verifier:  # PKCE (recommended)
        form["code_verifier"] = payload.code_verifier

    try:
        resp = requests.post(
            token_url,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"token exchange network error: {e!s}")

    if resp.status_code != 200:
        # Common causes: callback URL mismatch, code reused/expired, wrong client_id/domain
        raise HTTPException(status_code=401, detail=f"token exchange failed: {resp.text}")

    tokens = resp.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=401, detail="id_token missing in token response")

    # --- Verify JWT (your verify_id_token should do JWKS signature & claims checks) ---
    try:
        claims = verify_id_token(id_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"invalid id_token: {e!s}")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="invalid id_token payload: sub missing")

    email = (claims.get("email") or "").lower() or None
    name = claims.get("name") or (email.split("@")[0] if email else "user")
    role = claims.get("custom:role")  # optional custom attribute

    # --- Upsert account ---
    acct = db.scalar(select(Account).where(Account.cognito_sub == sub))
    if not acct:
        acct = Account(
            account_id=uuid4(),
            cognito_sub=sub,
            email=email,
            display_name=name,
            account_type=role if role in ("guardian", "child", "admin") else "guardian",
            status="active",
        )
        db.add(acct)
    else:
        if email and not acct.email:
            acct.email = email
        acct.last_login_at = func.now()

    # IMPORTANT: commit (unless your get_db() dependency already handles it)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return AuthSessionOut(
        account_id=acct.account_id,
        email=acct.email,
        display_name=acct.display_name,
        account_type=acct.account_type,
        status=acct.status,
    )
