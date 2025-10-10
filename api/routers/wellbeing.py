from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..deps import get_db
from ..models import WellbeingConvTip
from ..schemas import WellbeingConvTipOut

router = APIRouter(prefix="/wellbeing", tags=["wellbeing"])

@router.get(
    "/tips/{score}",
    response_model=WellbeingConvTipOut,
    summary="Get parent communication tips for a wellbeing score (1-5)",
)
def get_wellbeing_tips(
    score: int = Path(..., ge=1, le=5, description="Wellbeing score from 1 (low) to 5 (high)"),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(WellbeingConvTip).where(WellbeingConvTip.wellbeing_score == score))
    if not row:
        raise HTTPException(status_code=404, detail="No tips found for this score")
    return WellbeingConvTipOut(
        wellbeing_score=row.wellbeing_score,
        wellbeing_conv_text=row.wellbeing_conv_text,
    )