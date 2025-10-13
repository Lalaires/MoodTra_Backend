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
        current_account_id: UUID | None = Depends(get_account_id),
):
    print(f"🔄 PATCH /accounts/{account_id}")
    print(f"👤 Current account ID from header: {current_account_id}")
    print(f"📝 Request data: {data.model_dump()}")


    account = db.get(Account, account_id)
    if not account:
        print(f"❌ Account not found: {account_id}")
        raise HTTPException(status_code=404, detail="Account not found")

    print(f"✅ Account found:")
    print(f"   - account_id: {account.account_id}")
    print(f"   - cognito_sub: {account.cognito_sub}")
    print(f"   - email: {account.email}")
    print(f"   - current account_type: {account.account_type}")


    if current_account_id:
        if str(current_account_id) != str(account_id):
            print(f"❌ Permission denied: {current_account_id} != {account_id}")
            raise HTTPException(status_code=403, detail="Cannot update other accounts")
        print(f"✅ Permission check passed")
    else:
        print(f"ℹ️ Skipping permission check (no x-account-id header)")


    if data.account_type:
        if not account.cognito_sub:
            print(f"⚠️ Account {account_id} has no cognito_sub, skipping Cognito update")
        else:
            try:
                user_pool_id = os.getenv('COGNITO_USER_POOL_ID')
                if not user_pool_id:
                    raise ValueError("COGNITO_USER_POOL_ID not set")

                print(f"⏳ Updating Cognito custom:role...")
                print(f"   - UserPoolId: {user_pool_id}")
                print(f"   - Username (cognito_sub): {account.cognito_sub}")
                print(f"   - New role: {data.account_type}")

                cognito_client.admin_update_user_attributes(
                    UserPoolId=user_pool_id,
                    Username=account.cognito_sub,
                    UserAttributes=[
                        {'Name': 'custom:role', 'Value': data.account_type}
                    ]
                )
                print(f"✅ Cognito updated successfully")

            except cognito_client.exceptions.UserNotFoundException:
                print(f"⚠️ User not found in Cognito: {account.cognito_sub}")
                raise HTTPException(
                    status_code=404,
                    detail=f"User {account.cognito_sub} not found in Cognito"
                )
            except cognito_client.exceptions.NotAuthorizedException:
                print(f"❌ Lambda lacks Cognito permissions")
                raise HTTPException(
                    status_code=500,
                    detail="Backend lacks permission to update Cognito"
                )
            except Exception as e:
                print(f"❌ Cognito update failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update Cognito: {str(e)}"
                )


    print(f"⏳ Updating database...")

    if data.account_type is not None:
        old_type = account.account_type
        account.account_type = data.account_type
        print(f"   account_type: {old_type} -> {data.account_type}")

    if data.display_name is not None:
        account.display_name = data.display_name
        print(f"   display_name: -> {data.display_name}")

    if data.email is not None:
        account.email = data.email
        print(f"   email: -> {data.email}")

    try:
        db.add(account)
        db.commit()
        db.refresh(account)
        print(f"✅ Database updated successfully")
    except Exception as e:
        db.rollback()
        print(f"❌ Database update failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database update failed: {str(e)}"
        )


    return AuthSessionOut(
        account_id=account.account_id,
        email=account.email,
        display_name=account.display_name,
        account_type=account.account_type,
        status=account.status,
        cognito_sub=account.cognito_sub,
    )

