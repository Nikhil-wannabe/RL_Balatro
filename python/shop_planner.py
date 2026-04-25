from action_types import ActionResponse
from logging_utils import get_logger
from state import BalatroState, ShopItemState
from strategy_model import StrategyModel

logger = get_logger("Shop")


VOUCHER_SCORES = {
    "Clearance Sale": 12.0,
    "Liquidation": 18.0,
    "Overstock": 16.0,
    "Overstock Plus": 20.0,
    "Grabber": 14.0,
    "Nacho Tong": 16.0,
    "Paint Brush": 10.0,
    "Palette": 12.0,
    "Reroll Surplus": 10.0,
    "Reroll Glut": 12.0,
    "Seed Money": 18.0,
    "Money Tree": 20.0,
    "Wasteful": 8.0,
    "Recyclomancy": 8.0,
    "Crystal Ball": 10.0,
    "Telescope": 12.0,
}

JOKER_SCORES = {
    "Joker": 5.0,
    "Half Joker": 9.5,
    "Banner": 8.0,
    "Abstract Joker": 8.0,
    "Green Joker": 13.0,
    "Blue Joker": 11.0,
    "Supernova": 11.0,
    "Runner": 12.0,
    "Square Joker": 12.0,
    "Spare Trousers": 11.0,
    "Scary Face": 8.0,
    "Smiley Face": 8.0,
    "Scholar": 8.0,
    "Fibonacci": 8.5,
    "Photograph": 10.0,
    "Card Sharp": 11.0,
    "Acrobat": 11.0,
    "Bull": 10.5,
    "Blackboard": 9.0,
    "Baron": 12.0,
    "Cavendish": 13.0,
    "Hologram": 13.5,
    "Constellation": 12.0,
    "Ride the Bus": 11.0,
    "Ancient Joker": 11.0,
    "Campfire": 10.0,
    "Fortune Teller": 8.0,
    "Steel Joker": 8.0,
    "Stone Joker": 7.0,
    "Lucky Cat": 8.5,
    "Bull": 10.5,
    "To the Moon": 9.0,
    "Rocket": 10.0,
    "Delayed Gratification": 9.0,
    "Business Card": 7.0,
    "Burglar": 9.0,
}

PLANET_TO_HAND = {
    "Mercury": "Pair",
    "Venus": "Three of a Kind",
    "Earth": "Full House",
    "Mars": "Four of a Kind",
    "Jupiter": "Flush",
    "Saturn": "Straight",
    "Uranus": "Two Pair",
    "Neptune": "Straight Flush",
    "Pluto": "High Card",
    "Planet X": "Five of a Kind",
    "Ceres": "Flush House",
    "Eris": "Flush Five",
}


class ShopPlanner:
    def __init__(self):
        self.strategy_model = StrategyModel()
        self.last_trace = {}

    def _preferred_hand(self, state: BalatroState) -> str:
        if not state.hand_levels:
            return "Pair"
        best_name = "Pair"
        best_score = float("-inf")
        for name, info in state.hand_levels.items():
            score = info.played * 2 + info.level
            if score > best_score:
                best_score = score
                best_name = name
        return best_name

    def _sticker_penalty(self, item: ShopItemState, money: int) -> float:
        penalty = 0.0
        if item.is_rental:
            penalty += 6.0 if money < 20 else 3.5
        if item.is_perishable:
            penalty += 2.5
        if item.is_eternal:
            penalty += 1.0
        return penalty

    def _score_item(self, state: BalatroState, item: ShopItemState) -> float:
        if item.set == "Voucher":
            score = VOUCHER_SCORES.get(item.name, 4.0)
        elif item.set == "Joker":
            score = JOKER_SCORES.get(item.name, 4.5)
        elif item.set == "Planet":
            preferred = self._preferred_hand(state)
            score = 7.0 if PLANET_TO_HAND.get(item.name) == preferred else 4.0
        else:
            # Booster packs and unsupported consumables are intentionally deprioritized.
            score = -2.0

        if item.edition == "Negative":
            score += 5.0
        elif item.edition == "Foil":
            score += 1.0
        elif item.edition == "Holo":
            score += 1.5
        elif item.edition == "Polychrome":
            score += 2.5

        score -= self._sticker_penalty(item, state.economy.money)
        score -= max(0, item.cost - 4) * 0.35
        return score

    def plan_action(self, state: BalatroState) -> ActionResponse:
        inference = self.strategy_model.infer(state)
        if not state.shop_items:
            self.last_trace = {
                "phase": "SHOP",
                "strategy": inference,
                "item_scores": [],
                "decision_reason": "shop_empty",
            }
            return ActionResponse(action="NEXT_ROUND")

        affordable = [item for item in state.shop_items if item.cost <= state.economy.money]
        scored_items = []
        for item in affordable:
            model_breakdown = self.strategy_model.score_item(state, item, inference)
            legacy = self._score_item(state, item)
            total = legacy * 0.45 + model_breakdown["total"] * 0.55
            scored_items.append({
                "item": item,
                "name": item.name,
                "set": item.set,
                "cost": item.cost,
                "legacy_score": legacy,
                "model": model_breakdown,
                "total_score": total,
            })

        scored_items.sort(key=lambda entry: entry["total_score"], reverse=True)

        reserve_cash = 10 if (state.meta.stake or 0) >= 5 else 6
        top_score = scored_items[0]["total_score"] if scored_items else float("-inf")
        if scored_items and top_score >= 7.2:
            best_item = scored_items[0]["item"]
            logger.info("Buying shop item '%s' (score %.2f).", best_item.name, top_score)
            self.last_trace = {
                "phase": "SHOP",
                "strategy": inference,
                "item_scores": [
                    {
                        "name": entry["name"],
                        "set": entry["set"],
                        "cost": entry["cost"],
                        "legacy_score": round(entry["legacy_score"], 3),
                        "model_score": round(entry["model"]["total"], 3),
                        "total_score": round(entry["total_score"], 3),
                        "vector": entry["model"]["vector"],
                    }
                    for entry in scored_items[:8]
                ],
                "decision_reason": "buy_top_item",
            }
            return ActionResponse(action="BUY_CARD", target_id=best_item.id, message=best_item.name)

        wants_more_quality = len(state.jokers) < 4 or not scored_items or top_score < 5.5
        if wants_more_quality and state.economy.money >= max(state.economy.interest_cap, reserve_cash) + state.economy.reroll_cost:
            logger.info("Rerolling shop for a stronger board.")
            self.last_trace = {
                "phase": "SHOP",
                "strategy": inference,
                "item_scores": [
                    {
                        "name": entry["name"],
                        "set": entry["set"],
                        "cost": entry["cost"],
                        "total_score": round(entry["total_score"], 3),
                    }
                    for entry in scored_items[:8]
                ],
                "decision_reason": "reroll_low_quality_shop",
            }
            return ActionResponse(action="REROLL_SHOP")

        logger.info("Leaving shop without purchase.")
        self.last_trace = {
            "phase": "SHOP",
            "strategy": inference,
            "item_scores": [
                {
                    "name": entry["name"],
                    "set": entry["set"],
                    "cost": entry["cost"],
                    "total_score": round(entry["total_score"], 3),
                }
                for entry in scored_items[:8]
            ],
            "decision_reason": "save_money_or_no_value",
        }
        return ActionResponse(action="NEXT_ROUND")
