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

    # ========================================
    # 步驟 1: 用 code 換 tokens
    # ========================================
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

    # ========================================
    # 步驟 2: 驗證 JWT 並解析 claims
    # ========================================
    print(f"🔍 Verifying ID token...")
    claims = verify_id_token(id_token)

    # ✅ 關鍵：Cognito sub 是用戶的唯一 ID
    sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name") or (email.split("@")[0] if email else "user")
    role = claims.get("custom:role")

    # ✅ 額外資訊（用於 debug）
    identities = claims.get("identities")  # Google 登入時會有這個

    print(f"📝 Claims from Cognito:")
    print(f"  ✅ sub (Cognito User ID): {sub}")
    print(f"  📧 email: {email}")
    print(f"  👤 name: {name}")
    print(f"  🎭 custom:role: {role}")
    if identities:
        print(f"  🔗 identities: {identities}")

    if not sub:
        raise HTTPException(status_code=400, detail="sub missing in ID token")

    # ========================================
    # 步驟 3: Upsert Account（重要修正）
    # ========================================
    print(f"🔄 Looking up user by cognito_sub: {sub}")

    # ✅ 先用 cognito_sub 查詢
    acct = db.scalar(select(Account).where(Account.cognito_sub == sub))

    if not acct:
        print(f"👤 New user - checking if email exists...")

        # ✅ 檢查 email 是否已被佔用
        if email:
            existing = db.scalar(select(Account).where(Account.email == email))
            if existing:
                print(f"⚠️ Email {email} exists with different cognito_sub")
                print(f"   Old sub: {existing.cognito_sub}")
                print(f"   New sub: {sub}")

                # ✅ 更新舊帳號的 cognito_sub
                acct = existing
                acct.cognito_sub = sub  # 🔥 關鍵：更新 sub
                acct.last_login_at = func.now()

                # ✅ 如果舊帳號沒有 display_name，更新它
                if not acct.display_name:
                    acct.display_name = name
            else:
                # ✅ 完全新用戶
                print(f"✅ Creating new account for {email}")
                acct = Account(
                    account_id=uuid4(),
                    cognito_sub=sub,  # 🔥 關鍵：必須設定 sub
                    email=email,
                    display_name=name,
                    account_type=role if role in ("guardian", "child", "parent") else None,
                    status="active",
                )
                db.add(acct)
        else:
            # ✅ 沒有 email 的用戶（少見）
            print(f"⚠️ No email in claims, creating account with sub only")
            acct = Account(
                account_id=uuid4(),
                cognito_sub=sub,  # 🔥 關鍵：必須設定 sub
                email=None,
                display_name=name,
                account_type=role if role in ("guardian", "child", "parent") else None,
                status="active",
            )
            db.add(acct)
    else:
        # ✅ 既有用戶：更新資料
        print(f"✅ Existing user found: {acct.email}")

        # 確保 cognito_sub 存在（防止舊資料）
        if not acct.cognito_sub:
            print(f"🔧 Fixing missing cognito_sub for account {acct.account_id}")
            acct.cognito_sub = sub

        if email and not acct.email:
            acct.email = email

        if name and not acct.display_name:
            acct.display_name = name

        # ✅ 更新 role（如果 Cognito 有設定）
        if role and role in ("guardian", "child", "parent"):
            if acct.account_type != role:
                print(f"🔄 Updating account_type: {acct.account_type} -> {role}")
                acct.account_type = role

        acct.last_login_at = func.now()

    # ========================================
    # 步驟 4: 提交到資料庫
    # ========================================
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

    # ========================================
    # 步驟 5: 回傳給前端
    # ========================================
    return AuthSessionOut(
        account_id=acct.account_id,
        email=acct.email,
        display_name=acct.display_name,
        account_type=acct.account_type,
        status=acct.status,
        cognito_sub=sub,  # 🔥 關鍵：回傳 Cognito sub
        username=sub,  # 🔥 關鍵：Lambda 需要這個
        id_token=id_token  # ✅ 讓前端可以呼叫其他 API
    )