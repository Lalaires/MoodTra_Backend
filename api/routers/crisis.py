from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from ..deps import get_db, get_account_id
from ..models import CrisisAlert
from ..schemas import CrisisAlertOut

router = APIRouter(prefix="/api", tags=["crisis"])

logger = logging.getLogger(__name__)

@router.get("/crisis", response_model=CrisisAlertOut)
def get_latest_crisis_alert(
    account_id: UUID = Depends(get_account_id),
    db: Session = Depends(get_db)
):
    """
    Get the latest crisis alert for the specified account.
    
    Args:
        account_id: The account ID to get the latest crisis alert for
        
    Returns:
        CrisisAlertOut: The latest crisis alert for the account
        
    Raises:
        HTTPException: 404 if no crisis alert found for the account
    """
    try:
        # Query for the latest crisis alert for the given account
        stmt = (
            select(CrisisAlert)
            .where(CrisisAlert.account_id == account_id)
            .order_by(desc(CrisisAlert.crisis_alert_ts))
            .limit(1)
        )
        
        result = db.execute(stmt).scalar_one_or_none()
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No crisis alert found for account {account_id}"
            )
        
        logger.info(f"Retrieved latest crisis alert {result.crisis_alert_id} for account {account_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving latest crisis alert for account {account_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving crisis alert"
        )

