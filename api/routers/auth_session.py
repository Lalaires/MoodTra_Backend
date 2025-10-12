from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from uuid import uuid4
from ..deps import get_db
from ..models import Account
from ..schemas import AuthSessionOut, CodeLoginIn
from ..auth.cognito import verify_id_token
import os, requests

router = APIRouter(prefix="/auth", tags=["auth"])

COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN")
CLIENT_ID = os.getenv("COGNITO_AUDIENCE", "")  # your app client id
REDIRECT_URI = os.getenv("COGNITO_REDIRECT_URI")
if not COGNITO_DOMAIN or not REDIRECT_URI:
    print("Warning: COGNITO_DOMAIN or REDIRECT_URI not set in environment, /auth/code endpoint will not work properly")

@router.post("/code-login", response_model=AuthSessionOut)
def login_with_code(payload: CodeLoginIn, db: Session = Depends(get_db)):
    if not COGNITO_DOMAIN or not CLIENT_ID:
        raise HTTPException(status_code=500, detail="Cognito not configured")

    token_url = f"https://{COGNITO_DOMAIN}/oauth2/token"
    redirect_uri = payload.redirect_uri or REDIRECT_URI
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri required")

    form = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": payload.code,
        "redirect_uri": redirect_uri,
    }
    if payload.code_verifier:
        form["code_verifier"] = payload.code_verifier  # PKCE

    resp = requests.post(
        token_url,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"token exchange failed: {resp.text}")

    tokens = resp.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token missing in token response")

    # Verify JWT and upsert account (same logic as /auth/session)
    claims = verify_id_token(id_token)
    sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name") or (email.split("@")[0] if email else "user")
    role = claims.get("custom:role")

    acct = db.scalar(select(Account).where(Account.cognito_sub == sub))
    if not acct:
        acct = Account(
            account_id=uuid4(),
            cognito_sub=sub,
            email=email,
            display_name=name,
            account_type=role if role in ("guardian","child","parent") else "pending",
            status="active",
        )
        db.add(acct)
    else:
        if email and not acct.email:
            acct.email = email
        acct.last_login_at = func.now()
    db.flush()

    return AuthSessionOut(
        account_id=acct.account_id,
        email=acct.email,
        display_name=acct.display_name,
        account_type=acct.account_type,
        status=acct.status,
    )