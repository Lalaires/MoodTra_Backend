from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
import boto3
import os
from pydantic import BaseModel
from ..deps import get_db, get_account_id
from ..models import Account
from ..schemas import AuthSessionOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


class UpdateAccountRequest(BaseModel):
    account_type: str | None = None
    display_name: str | None = None
    email: str | None = None

# Cognito client
cognito_client = boto3.client(
    'cognito-idp',
    region_name=os.getenv('COGNITO_REGION', 'ap-southeast-4')
)

@router.patch("/{account_id}", response_model=AuthSessionOut)
def update_account(
    account_id: UUID,
    data: UpdateAccountRequest,
    db: Session = Depends(get_db),
    current_account_id = Depends(get_account_id),
):
    # 認證檢查
    if str(current_account_id) != str(account_id):
        raise HTTPException(status_code=403, detail="Cannot update other accounts")

    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")


    if data.account_type:
        try:
            cognito_client.admin_update_user_attributes(
                UserPoolId=os.getenv('COGNITO_USER_POOL_ID'),
                Username=account.cognito_sub,
                UserAttributes=[
                    {'Name': 'custom:role', 'Value': data.account_type}
                ]
            )
            print(f"✅ Updated Cognito custom:role for {account.cognito_sub}")
        except Exception as e:
            print(f"⚠️ Failed to update Cognito: {e}")


    allowed_fields = {
        "account_type": data.account_type,
        "display_name": data.display_name,
        "email": data.email,
    }

    for field, value in allowed_fields.items():
        if value is not None:
            setattr(account, field, value)

    db.add(account)
    db.commit()

    return AuthSessionOut(
        account_id=account.account_id,
        email=account.email,
        display_name=account.display_name,
        account_type=account.account_type,
        status=account.status,
    )