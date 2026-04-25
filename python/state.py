from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class MetaState(BaseModel):
    protocol_version: str
    seed: str
    ante: int
    round: int
    phase: str
    stake: Optional[int] = None
    blind_on_deck: Optional[str] = None
    deck_name: Optional[str] = None

class BlindState(BaseModel):
    name: str
    target_score: int
    current_score: int
    boss_modifier: Optional[str] = None
    is_boss: bool = False

class EconomyState(BaseModel):
    money: int
    hands_left: int
    discards_left: int
    hand_size: int
    reroll_cost: int = 5
    interest_cap: int = 25
    interest_amount: int = 1

class Card(BaseModel):
    id: str
    rank: str
    suit: str
    base_chips: int
    enhancement: str = "None"
    edition: str = "None"
    seal: str = "None"
    is_debuffed: bool = False

class Joker(BaseModel):
    id: str
    name: str
    edition: str = "None"
    sell_value: int = 0
    is_debuffed: bool = False
    is_eternal: bool = False
    is_perishable: bool = False
    is_rental: bool = False
    internal_state: Dict[str, Any] = Field(default_factory=dict)

class HandLevelState(BaseModel):
    level: int = 1
    planets: int = 0
    played: int = 0
    played_this_round: int = 0
    chips: Optional[int] = None
    mult: Optional[int] = None

class ShopItemState(BaseModel):
    id: str
    name: str
    set: str
    cost: int = 0
    edition: str = "None"
    is_eternal: bool = False
    is_perishable: bool = False
    is_rental: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BalatroState(BaseModel):
    meta: MetaState
    blind: BlindState
    economy: EconomyState
    hand: List[Card] = Field(default_factory=list)
    jokers: List[Joker] = Field(default_factory=list)
    deck: List[Card] = Field(default_factory=list)
    discard_pile: List[Card] = Field(default_factory=list)
    hand_levels: Dict[str, HandLevelState] = Field(default_factory=dict)
    blind_choices: Dict[str, str] = Field(default_factory=dict)
    shop_items: List[ShopItemState] = Field(default_factory=list)
