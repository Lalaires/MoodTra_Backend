# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy import select
# from sqlalchemy.orm import Session
# from uuid import UUID
# from ..deps import get_db, get_account_id
# from ..models import Account
# from ..schemas import AuthSessionOut
#
# router = APIRouter(prefix="/accounts", tags=["accounts"])
#
# @router.patch("/{account_id}", response_model=AuthSessionOut)
# def update_account(
#     account_id: UUID,
#     data: dict,
#     db: Session = Depends(get_db),
#     current_account_id = Depends(get_account_id),
# ):
#
#     if str(current_account_id) != str(account_id):
#         raise HTTPException(status_code=403, detail="Cannot update other accounts")
#
#     account = db.get(Account, account_id)
#     if not account:
#         raise HTTPException(status_code=404, detail="Account not found")
#
#
#     allowed_fields = {
#         "account_type": str,
#         "display_name": str,
#         "email": str,
#     }
#
#
#     for field, field_type in allowed_fields.items():
#         if field in data and data[field] is not None:
#             if field_type == str and not isinstance(data[field], str):
#                 raise HTTPException(status_code=400, detail=f"{field} must be a string")
#             setattr(account, field, data[field])
#
#     db.add(account)
#     db.flush()
#
#     return AuthSessionOut(
#         account_id=account.account_id,
#         email=account.email,
#         display_name=account.display_name,
#         account_type=account.account_type,
#         status=account.status,
#     )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID
import boto3
import os
from ..deps import get_db, get_account_id
from ..models import Account
from ..schemas import AuthSessionOut

router = APIRouter(prefix="/accounts", tags=["accounts"])

# Cognito client
cognito_client = boto3.client(
    'cognito-idp',
    region_name=os.getenv('COGNITO_REGION', 'ap-southeast-4')
)

@router.patch("/{account_id}", response_model=AuthSessionOut)
def update_account(
    account_id: UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_account_id = Depends(get_account_id),
):

    if str(current_account_id) != str(account_id):
        raise HTTPException(status_code=403, detail="Cannot update other accounts")

    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")


    if 'account_type' in data and data['account_type']:
        try:
            cognito_client.admin_update_user_attributes(
                UserPoolId=os.getenv('COGNITO_USER_POOL_ID'),
                Username=account.cognito_sub,
                UserAttributes=[
                    {'Name': 'custom:role', 'Value': data['account_type']}
                ]
            )
            print(f"✅ Updated Cognito custom:role for {account.cognito_sub}")
        except Exception as e:
            print(f"⚠️ Failed to update Cognito: {e}")



    allowed_fields = {
        "account_type": str,
        "display_name": str,
        "email": str,
    }

    for field, field_type in allowed_fields.items():
        if field in data and data[field] is not None:
            setattr(account, field, data[field])

    db.add(account)
    db.flush()

    return AuthSessionOut(
        account_id=account.account_id,
        email=account.email,
        display_name=account.display_name,
        account_type=account.account_type,
        status=account.status,
    )