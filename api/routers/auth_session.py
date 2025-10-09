from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from uuid import uuid4
from ..deps import get_db
from ..models import Account
from ..schemas import AuthSessionOut
from ..auth.cognito import verify_id_token

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=True)

@router.post("/session", response_model=AuthSessionOut)
def establish_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    id_token = credentials.credentials   # Swagger will prepend Bearer automatically
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
            account_type=role if role in ("guardian","child","admin") else "guardian",
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