from typing import List
from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models import Strategy, StrategyEmotion, EmotionLabel
from ..schemas import StrategyOut

router = APIRouter(
    prefix="/strategy",
    tags=["strategy"],
    responses={404: {"description": "Not found"}},
)

# List strategies recommended for a given emoji
@router.get(
    "/emojis/{emoji}",
    response_model=List[StrategyOut],
    summary="List strategies recommended for a given emoji",
)
def list_strategies_for_emoji(
    emoji: str = Path(..., min_length=1, description="Emoji from emotion_label.emoji"),
    db: Session = Depends(get_db),
):
    stmt = (
        select(
            Strategy.strategy_id,
            Strategy.strategy_name,
            Strategy.strategy_desc,
            Strategy.strategy_duration,
            Strategy.strategy_requirements,   # JSONB -> dict automatically
            Strategy.strategy_instruction,
            Strategy.strategy_source,         # JSONB -> dict automatically
            Strategy.strategy_category,
        )
        .join(StrategyEmotion, StrategyEmotion.strategy_id == Strategy.strategy_id)
        .join(EmotionLabel, EmotionLabel.emotion_id == StrategyEmotion.emotion_id)
        .where(EmotionLabel.emoji == emoji)
        .order_by(Strategy.strategy_name.asc())
    )
    rows = db.execute(stmt).all()
    return [StrategyOut(**dict(r._mapping)) for r in rows]

# List all strategies for client-side mapping
@router.get(
    "",
    response_model=List[StrategyOut],
    summary="List all strategies",
)
def list_all_strategies(db: Session = Depends(get_db)):
    stmt = select(
        Strategy.strategy_id,
        Strategy.strategy_name,
        Strategy.strategy_desc,
        Strategy.strategy_duration,
        Strategy.strategy_requirements,
        Strategy.strategy_instruction,
        Strategy.strategy_source,
        Strategy.strategy_category,
    ).order_by(Strategy.strategy_name.asc())
    rows = db.execute(stmt).all()
    return [StrategyOut(**dict(r._mapping)) for r in rows]