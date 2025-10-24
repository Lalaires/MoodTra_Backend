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
CLIENT_ID = os.getenv("COGNITO_AUDIENCE", "")
REDIRECT_URI = os.getenv("COGNITO_REDIRECT_URI")


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
        form["code_verifier"] = payload.code_verifier

    print(f"🔐 Exchanging code for tokens...")
    resp = requests.post(
        token_url,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"❌ Token exchange failed: {resp.text}")
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {resp.text}"
        )

    tokens = resp.json()
    id_token = tokens.get("id_token")

    if not id_token:
        raise HTTPException(
            status_code=400,
            detail="id_token missing in token response"
        )


    print(f"🔍 Verifying ID token...")
    claims = verify_id_token(id_token)

    sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name") or (email.split("@")[0] if email else "user")
    role = claims.get("custom:role")


    identities = claims.get("identities")

    print(f"📝 Claims from Cognito:")
    print(f"  ✅ sub (Cognito User ID): {sub}")
    print(f"  📧 email: {email}")
    print(f"  👤 name: {name}")
    print(f"  🎭 custom:role: {role}")
    if identities:
        print(f"  🔗 identities: {identities}")

    if not sub:
        raise HTTPException(status_code=400, detail="sub missing in ID token")


    print(f"🔄 Looking up user by cognito_sub: {sub}")


    acct = db.scalar(select(Account).where(Account.cognito_sub == sub))

    if not acct:
        print(f"👤 New user - checking if email exists...")


        if email:
            existing = db.scalar(select(Account).where(Account.email == email))
            if existing:
                print(f"⚠️ Email {email} exists with different cognito_sub")
                print(f"   Old sub: {existing.cognito_sub}")
                print(f"   New sub: {sub}")


                acct = existing
                acct.cognito_sub = sub
                acct.last_login_at = func.now()


                if not acct.display_name:
                    acct.display_name = name
            else:

                print(f"✅ Creating new account for {email}")
                acct = Account(
                    account_id=uuid4(),
                    cognito_sub=sub,
                    email=email,
                    display_name=name,
                    account_type=role if role in ("guardian", "child", "parent") else None,
                    status="active",
                )
                db.add(acct)
        else:

            print(f"⚠️ No email in claims, creating account with sub only")
            acct = Account(
                account_id=uuid4(),
                cognito_sub=sub,
                email=None,
                display_name=name,
                account_type=role if role in ("guardian", "child", "parent") else None,
                status="active",
            )
            db.add(acct)
    else:

        print(f"✅ Existing user found: {acct.email}")


        if not acct.cognito_sub:
            print(f"🔧 Fixing missing cognito_sub for account {acct.account_id}")
            acct.cognito_sub = sub

        if email and not acct.email:
            acct.email = email

        if name and not acct.display_name:
            acct.display_name = name


        if role and role in ("guardian", "child", "parent"):
            if acct.account_type != role:
                print(f"🔄 Updating account_type: {acct.account_type} -> {role}")
                acct.account_type = role

        acct.last_login_at = func.now()


    try:
        db.flush()
        db.commit()
        print(f"✅ Account saved to database")
        print(f"   account_id: {acct.account_id}")
        print(f"   cognito_sub: {acct.cognito_sub}")
        print(f"   email: {acct.email}")
        print(f"   account_type: {acct.account_type}")
    except Exception as e:
        db.rollback()
        print(f"❌ Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


    return AuthSessionOut(
        account_id=acct.account_id,
        email=acct.email,
        display_name=acct.display_name,
        account_type=acct.account_type,
        status=acct.status,
        cognito_sub=sub,
        username=sub,
        id_token=id_token
    )