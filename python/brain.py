from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from config import config
from logging_utils import get_logger
from risk_metrics import clamp01, normalize_ratio, stable_desc_tuple
from state import BalatroState

logger = get_logger("Brain")


class TacticalMode:
    LETHAL = "LETHAL"
    SAFE_CLEAR = "SAFE_CLEAR"
    DESPERATION = "DESPERATION"
    SCALING_PRESERVE = "SCALING_PRESERVE"
    PANIC = "PANIC"


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
    clear_probability_lcb: float = 0.0
    minimax_regret: float = 0.0
    cvar_loss: float = 0.0
    confidence_margin: float = 0.0
    ess: float = 0.0
    decision_method: str = "heuristic"
    hand_name: str = ""


@dataclass
class RankedAction:
    features: ActionFeatures
    mode: str
    rank_tuple: Tuple
    utility: float


class Brain:
    def __init__(self):
        pass

    def _mode_thresholds(self, state: BalatroState) -> Tuple[float, float, float]:
        base = config.TACTICAL_GAMMA_BASE
        boss_bonus = config.TACTICAL_GAMMA_BOSS_BONUS if state.blind.is_boss else 0.0
        high_stake_bonus = config.TACTICAL_GAMMA_HIGH_STAKE_BONUS if (state.meta.stake or 1) >= 5 else 0.0
        low_hands_bonus = 0.01 if state.economy.hands_left <= 2 else 0.0
        gamma_target = min(0.99, base + boss_bonus + high_stake_bonus + low_hands_bonus)
        gamma_scale = min(0.995, gamma_target + 0.02)
        gamma_panic = max(0.35, gamma_target - 0.40)
        return gamma_target, gamma_scale, gamma_panic

    def determine_mode(
        self,
        state: BalatroState,
        best_immediate_score: float,
        estimated_clear_prob: float,
        conservative_clear_prob: Optional[float] = None,
    ) -> str:
        target = state.blind.target_score - state.blind.current_score
        conservative = estimated_clear_prob if conservative_clear_prob is None else conservative_clear_prob
        gamma_target, gamma_scale, gamma_panic = self._mode_thresholds(state)

        if best_immediate_score >= target:
            return TacticalMode.LETHAL
        if conservative < gamma_panic and state.economy.hands_left <= 1 and state.economy.discards_left <= 0:
            return TacticalMode.PANIC
        if conservative >= gamma_scale and state.economy.hands_left > 1:
            return TacticalMode.SCALING_PRESERVE
        if conservative >= gamma_target:
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
        elif mode == TacticalMode.PANIC:
            w_risk *= 0.05
            w_survival *= 2.5
        elif mode == TacticalMode.SCALING_PRESERVE:
            w_future *= 3.0
            w_preserve *= 2.0

        utility = 0.0
        utility += features.clear_probability_lcb * (w_survival * 1.15)
        utility += features.clear_probability * w_survival
        utility += (features.hands_remaining + features.discards_remaining) * w_preserve
        if features.cards_used > 0:
            utility += (features.expected_score / features.cards_used) * w_efficiency
        utility += features.score_variance * w_risk
        utility += features.overkill * w_overkill
        utility += features.future_hand_strength_estimate * w_future
        utility += features.discard_quality * 5.0
        utility -= features.cvar_loss * 0.6
        utility -= features.minimax_regret * 4.0

        return utility

    def estimate_clear_probability(
        self,
        state: BalatroState,
        expected_score_per_hand: float,
        *,
        target_override: Optional[float] = None,
        hands_override: Optional[int] = None,
    ) -> float:
        target = (
            float(target_override)
            if target_override is not None
            else float(state.blind.target_score - state.blind.current_score)
        )
        if target <= 0:
            return 1.0
        hands_left = state.economy.hands_left if hands_override is None else int(hands_override)
        if hands_left <= 0:
            return 0.0

        projected_total = float(expected_score_per_hand) * hands_left
        if projected_total >= target * 1.2:
            return 0.95
        if projected_total >= target:
            return 0.80
        if projected_total >= target * 0.8:
            return 0.50
        return 0.10

    def _action_priority(self, features: ActionFeatures, mode: str) -> int:
        if features.action_type == "PLAY_HAND" and features.score_margin_vs_blind >= 0:
            return 4
        if mode == TacticalMode.LETHAL:
            return 3 if features.action_type == "PLAY_HAND" else 0
        if mode in {TacticalMode.DESPERATION, TacticalMode.PANIC}:
            if features.action_type == "DISCARD":
                return 3 if features.future_hand_strength_estimate > 0 else 1
            return 1
        if mode == TacticalMode.SCALING_PRESERVE:
            return 2 if features.action_type == "DISCARD" else 1
        return 2 if features.action_type == "PLAY_HAND" else 1

    def build_rank_tuple(self, state: BalatroState, features: ActionFeatures, mode: str) -> Tuple:
        target = max(1.0, float(state.blind.target_score - state.blind.current_score))
        resource_score = (
            float(features.hands_remaining)
            + (0.6 * float(features.discards_remaining))
            + (0.05 * float(features.money_after_action))
        )
        per_hand_target = max(1.0, target / max(1, state.economy.hands_left))
        card_efficiency = features.expected_score / max(1, features.cards_used)
        overkill_norm = max(0.0, min(1.0, features.overkill / target))
        q10_proxy = features.expected_score - features.cvar_loss
        future_strength = normalize_ratio(features.future_hand_strength_estimate, per_hand_target, clip=False)
        discard_quality = normalize_ratio(features.discard_quality, per_hand_target, clip=False)
        action_priority = self._action_priority(features, mode)
        immediate_resolution_priority = 1 if features.action_type == "PLAY_HAND" and features.score_margin_vs_blind >= 0 else 0
        mode_bonus = {
            TacticalMode.LETHAL: 4,
            TacticalMode.SAFE_CLEAR: 3,
            TacticalMode.SCALING_PRESERVE: 2,
            TacticalMode.DESPERATION: 1,
            TacticalMode.PANIC: 0,
        }.get(mode, 0)

        return (
            *stable_desc_tuple(
                (
                    clamp01(features.clear_probability_lcb),
                    clamp01(features.clear_probability),
                    -normalize_ratio(features.minimax_regret, 1000.0, clip=False),
                    immediate_resolution_priority,
                    normalize_ratio(q10_proxy, target, clip=False),
                    future_strength,
                    normalize_ratio(features.expected_score, target, clip=False),
                    discard_quality,
                    normalize_ratio(resource_score, 10.0, clip=False),
                    -overkill_norm,
                    normalize_ratio(card_efficiency, per_hand_target, clip=False),
                )
            ),
            mode_bonus,
            action_priority,
            -features.cards_used,
            tuple(sorted(features.cards)),
        )

    def rank_action(self, state: BalatroState, features: ActionFeatures, mode: str) -> RankedAction:
        utility = self.calculate_utility(features, mode)
        rank_tuple = self.build_rank_tuple(state, features, mode)
        return RankedAction(features=features, mode=mode, rank_tuple=rank_tuple, utility=utility)

    def sort_ranked_actions(self, ranked_actions: List[RankedAction]) -> List[RankedAction]:
        return sorted(ranked_actions, key=lambda ranked: ranked.rank_tuple, reverse=True)
