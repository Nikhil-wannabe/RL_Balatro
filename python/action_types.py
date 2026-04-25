from pydantic import BaseModel
from typing import List, Optional

class ActionResponse(BaseModel):
    action: str  # PLAY_HAND, DISCARD, SELECT_BLIND, CASH_OUT, REROLL_SHOP, BUY_CARD, NEXT_ROUND, SKIP, NO_OP, ERROR
    cards: Optional[List[str]] = None
    target_id: Optional[str] = None
    message: Optional[str] = None
