from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _coerce_empty_dict(value: Any) -> Any:
    if value is None:
        return {}
    if value == []:
        return {}
    return value


def _lookup_nested(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_string_field(value: Any, *, fallback_paths: List[tuple[str, ...]]) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for path in fallback_paths:
            candidate = _lookup_nested(value, *path)
            if isinstance(candidate, str):
                return candidate
            if isinstance(candidate, (int, float)):
                return str(candidate)
    return value


class MetaState(BaseModel):
    protocol_version: str
    seed: str
    ante: int
    round: int
    phase: str
    stake: Optional[int] = None
    blind_on_deck: Optional[str] = None
    deck_name: Optional[str] = None
    deck_key: Optional[str] = None
    no_interest: bool = False
    pack_kind: Optional[str] = None

    @field_validator("blind_on_deck", "pack_kind", mode="before")
    @classmethod
    def _normalize_meta_simple_strings(cls, value: Any) -> Any:
        return _coerce_string_field(
            value,
            fallback_paths=[
                ("key",),
                ("name",),
                ("id",),
            ],
        )

    @field_validator("deck_name", mode="before")
    @classmethod
    def _normalize_deck_name(cls, value: Any) -> Any:
        return _coerce_string_field(
            value,
            fallback_paths=[
                ("name",),
                ("label",),
                ("key",),
                ("config", "center", "name"),
                ("config", "center", "key"),
                ("center", "name"),
                ("center", "key"),
                ("effect", "center", "name"),
                ("effect", "center", "key"),
            ],
        )

    @field_validator("deck_key", mode="before")
    @classmethod
    def _normalize_deck_key(cls, value: Any) -> Any:
        return _coerce_string_field(
            value,
            fallback_paths=[
                ("key",),
                ("deck_key",),
                ("slug",),
                ("id",),
                ("config", "center", "key"),
                ("center", "key"),
                ("effect", "center", "key"),
                ("name",),
            ],
        )


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
    joker_slots: int = 5
    consumable_slots: int = 2


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

    @field_validator("internal_state", mode="before")
    @classmethod
    def _normalize_internal_state(cls, value: Any) -> Any:
        return _coerce_empty_dict(value)


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
    rank: Optional[str] = None
    suit: Optional[str] = None
    base_chips: Optional[int] = None
    enhancement: str = "None"
    seal: str = "None"
    is_debuffed: bool = False
    is_eternal: bool = False
    is_perishable: bool = False
    is_rental: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: Any) -> Any:
        return _coerce_empty_dict(value)


class BalatroState(BaseModel):
    meta: MetaState
    blind: BlindState
    economy: EconomyState
    hand: List[Card] = Field(default_factory=list)
    jokers: List[Joker] = Field(default_factory=list)
    deck: List[Card] = Field(default_factory=list)
    discard_pile: List[Card] = Field(default_factory=list)
    consumables: List[ShopItemState] = Field(default_factory=list)
    hand_levels: Dict[str, HandLevelState] = Field(default_factory=dict)
    blind_choices: Dict[str, str] = Field(default_factory=dict)
    shop_items: List[ShopItemState] = Field(default_factory=list)
    pack_items: List[ShopItemState] = Field(default_factory=list)

    @field_validator("hand_levels", "blind_choices", mode="before")
    @classmethod
    def _normalize_mapping_fields(cls, value: Any) -> Any:
        return _coerce_empty_dict(value)
