from dataclasses import dataclass
from state import BalatroState
from typing import List, Optional
from logging_utils import get_logger
from config import config

logger = get_logger("Brain")

class TacticalMode:
    LETHAL = "LETHAL"
    SAFE_CLEAR = "SAFE_CLEAR"
    DESPERATION = "DESPERATION"
    SCALING_PRESERVE = "SCALING_PRESERVE"

@dataclass
class ActionFeatures:
    action_type: str
    cards: List[str]
    clear_probability: float
    expected_score: float
    score_variance: float
    score_margin_vs_blind: float
    hands_remaining: int
    discards_remaining: int
    money_after_action: float
    cards_used: int
    discard_quality: float
    future_hand_strength_estimate: float
    overkill: float

class Brain:
    def __init__(self):
        pass

    def determine_mode(self, state: BalatroState, best_immediate_score: float, estimated_clear_prob: float) -> str:
        target = state.blind.target_score - state.blind.current_score
        
        if best_immediate_score >= target:
            return TacticalMode.LETHAL
            
        if estimated_clear_prob >= 0.8:
            if state.economy.hands_left > 1 and state.economy.discards_left > 0 and (best_immediate_score * state.economy.hands_left >= target * 1.5):
                return TacticalMode.SCALING_PRESERVE
            return TacticalMode.SAFE_CLEAR
            
        return TacticalMode.DESPERATION

    def calculate_utility(self, features: ActionFeatures, mode: str) -> float:
        w_survival = config.WEIGHT_SURVIVAL
        w_preserve = config.WEIGHT_PRESERVATION
        w_efficiency = config.WEIGHT_EFFICIENCY
        w_risk = config.WEIGHT_RISK
        w_overkill = config.WEIGHT_OVERKILL
        w_future = config.WEIGHT_FUTURE

        if mode == TacticalMode.LETHAL:
            w_preserve *= 2.0
            w_efficiency *= 1.5
            w_overkill *= 2.0
        elif mode == TacticalMode.SAFE_CLEAR:
            w_efficiency *= 2.0
            w_preserve *= 1.5
        elif mode == TacticalMode.DESPERATION:
            w_risk *= 0.1
            w_survival *= 2.0
        elif mode == TacticalMode.SCALING_PRESERVE:
            w_future *= 3.0
            w_preserve *= 2.0

        utility = 0.0
        utility += features.clear_probability * w_survival
        utility += (features.hands_remaining + features.discards_remaining) * w_preserve
        if features.cards_used > 0:
            utility += (features.expected_score / features.cards_used) * w_efficiency
        utility += features.score_variance * w_risk
        utility += features.overkill * w_overkill
        utility += features.future_hand_strength_estimate * w_future
        utility += features.discard_quality * 5.0
        
        return utility

    def estimate_clear_probability(self, state: BalatroState, expected_score_per_hand: float) -> float:
        target = state.blind.target_score - state.blind.current_score
        if target <= 0:
            return 1.0
        if state.economy.hands_left == 0:
            return 0.0
            
        projected_total = expected_score_per_hand * state.economy.hands_left
        
        if projected_total >= target * 1.2:
            return 0.95
        elif projected_total >= target:
            return 0.80
        elif projected_total >= target * 0.8:
            return 0.50
        else:
            return 0.10
