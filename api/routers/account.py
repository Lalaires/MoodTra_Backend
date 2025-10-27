from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.deps import get_db, get_account_id
from api import models, schemas

router = APIRouter(prefix="/account", tags=["account"])

@router.post("/type", status_code=status.HTTP_200_OK)
def set_account_type(
    payload: schemas.AccountTypeSet,
    db: Session = Depends(get_db),
    account_id: int = Depends(get_account_id),
):
    account = db.query(models.Account).filter_by(account_id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.account_type is not None:
        raise HTTPException(status_code=400, detail="account_type already set")
    account.account_type = payload.account_type
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"account_id": account.account_id, "account_type": account.account_type}