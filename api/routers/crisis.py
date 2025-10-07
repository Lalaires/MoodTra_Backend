from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from ..deps import get_db, get_account_id
from ..models import CrisisAlert, CrisisStrategy
from ..schemas import CrisisAlertOut

router = APIRouter(prefix="/api", tags=["crisis"])

logger = logging.getLogger(__name__)

@router.get("/crisis", response_model=CrisisAlertOut)
def get_latest_crisis_alert(
    account_id: UUID = Depends(get_account_id),
    db: Session = Depends(get_db)
):
    """
    Get the latest crisis alert and associated strategy text for the specified account.
    
    Args:
        account_id: The account ID to get the latest crisis alert
        
    Returns:
        CrisisAlertOut: The latest crisis alert id, severity, status, and associated strategy text for the account
        
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
        # Fetch matching crisis strategy text using crisis_id and crisis_alert_severity
        strategy_stmt = select(CrisisStrategy.crisis_strategy_text).where(
            and_(
                CrisisStrategy.crisis_id == result.crisis_id,
                CrisisStrategy.crisis_severity == result.crisis_alert_severity,
            )
        )
        strategy_text = db.execute(strategy_stmt).scalar_one_or_none()

        logger.info(f"Retrieved latest crisis alert {result.crisis_alert_id} for account {account_id}")

        # Build response model explicitly to include joined field
        return CrisisAlertOut(
            crisis_alert_id=result.crisis_alert_id,
            crisis_alert_severity=result.crisis_alert_severity,
            crisis_alert_status=result.crisis_alert_status,
            crisis_strategy_text=strategy_text
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving latest crisis alert for account {account_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving crisis alert"
        )


@router.put("/crisis/{crisis_alert_id}", status_code=204)
def acknowledge_crisis_alert(
    crisis_alert_id: UUID,
    account_id: UUID = Depends(get_account_id),
    db: Session = Depends(get_db),
):
    try:
        # Fetch by id and ensure it belongs to the account
        stmt = (
            select(CrisisAlert)
            .where(
                CrisisAlert.crisis_alert_id == crisis_alert_id,
                CrisisAlert.account_id == account_id,
            )
            .limit(1)
        )
        row = db.execute(stmt).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Crisis alert not found")

        # Update status to acknowledged
        row.crisis_alert_status = "acknowledged"
        db.flush()
        db.refresh(row)
        db.commit()

        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging crisis alert {crisis_alert_id} for account {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while acknowledging crisis alert")

