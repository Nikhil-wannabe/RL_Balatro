from action_types import ActionResponse
from logging_utils import get_logger
from pack_planner import PackPlanner
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
    "Jolly Joker": 8.5,
    "Sly Joker": 8.5,
    "Wily Joker": 8.5,
    "Clever Joker": 8.5,
    "Crafty Joker": 8.5,
    "Devious Joker": 8.5,
    "Lusty Joker": 7.5,
    "Wrathful Joker": 7.5,
    "Gluttonous Joker": 7.5,
    "Greedy Joker": 7.5,
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
        self.pack_planner = PackPlanner()
        self.last_trace = {}

    def _build_pressure(self, state: BalatroState, inference) -> float:
        ante = state.meta.ante or 1
        joker_count = len(state.jokers)
        money = state.economy.money
        posterior = inference["posterior"]
        deck_flags = inference.get("deck_profile", {}).get("flags", {})
        run_plan = inference.get("run_plan", {})
        role_deficits = run_plan.get("role_deficits", {})

        pressure = 0.0
        if joker_count <= 0:
            pressure += 3.0
        elif joker_count == 1:
            pressure += 2.0
        elif joker_count == 2:
            pressure += 1.0

        if ante <= 2:
            pressure += 1.5
        elif ante <= 4:
            pressure += 0.6

        if money >= 10 and joker_count < 4:
            pressure += 0.5

        pressure += posterior.get("economy", 0.0) * 0.8
        pressure += posterior.get("deck_growth", 0.0) * 0.5
        pressure += role_deficits.get("chips", 0.0) * 1.1
        pressure += role_deficits.get("mult", 0.0) * 1.2
        pressure += role_deficits.get("xmult", 0.0) * (0.6 if (run_plan.get("stage") == "stabilization") else 1.25)
        pressure += role_deficits.get("economy", 0.0) * 0.6
        if deck_flags.get("need_early_tempo"):
            pressure += 0.9
        if deck_flags.get("high_scaling_pressure"):
            pressure += 0.8
        if deck_flags.get("spend_aggressively") or state.meta.no_interest:
            pressure += 0.8
        return pressure

    def _reserve_cash(self, state: BalatroState, build_pressure: float, inference) -> int:
        ante = state.meta.ante or 1
        deck_flags = inference.get("deck_profile", {}).get("flags", {})
        run_plan = inference.get("run_plan", {})
        stage = run_plan.get("stage")
        plan_floor = int(run_plan.get("economy_floor", 0) or 0)
        if deck_flags.get("spend_aggressively") or state.meta.no_interest:
            if ante <= 2:
                return max(0, min(4, plan_floor))
            return max(plan_floor, 2 if build_pressure < 2.5 else 0)
        if stage == "endgame":
            return max(plan_floor, 4 if build_pressure < 1.8 else 0)
        if stage == "conversion":
            return max(plan_floor, 6 if state.economy.money >= 20 else 4)
        if ante <= 1:
            return max(plan_floor, 0 if build_pressure >= 2.0 else 2)
        if ante <= 2:
            if build_pressure >= 2.5:
                return max(plan_floor, 0)
            return max(plan_floor, 2 if state.economy.money >= 8 else 0)
        if build_pressure >= 2.0:
            return max(plan_floor, 4)
        return max(plan_floor, 10 if (state.meta.stake or 0) >= 5 else 6)

    def _buy_threshold(self, state: BalatroState, build_pressure: float, inference) -> float:
        base = 5.8 if (state.meta.ante or 1) <= 2 else 7.2
        deck_flags = inference.get("deck_profile", {}).get("flags", {})
        run_plan = inference.get("run_plan", {})
        stage = run_plan.get("stage")
        hard_needs = run_plan.get("hard_needs", [])
        reroll_aggression = float(run_plan.get("reroll_aggression", 0.0))
        if deck_flags.get("need_early_tempo") or deck_flags.get("spend_aggressively") or state.meta.no_interest:
            base -= 0.4
        if deck_flags.get("high_scaling_pressure"):
            base -= 0.3
        if stage == "stabilization":
            base -= 0.2
        if stage in {"conversion", "endgame"} and "xmult" in hard_needs:
            base -= 0.35
        if {"chips", "mult"} & set(hard_needs):
            base -= 0.3
        base += max(0.0, reroll_aggression - 0.55) * 0.45
        if build_pressure >= 3.0:
            return base - 1.0
        if build_pressure >= 2.0:
            return base - 0.6
        if build_pressure >= 1.0:
            return base - 0.3
        return base

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

    def _score_item(self, state: BalatroState, item: ShopItemState, inference=None) -> float:
        if item.set == "Voucher":
            score = VOUCHER_SCORES.get(item.name, 4.0)
        elif item.set == "Joker":
            score = JOKER_SCORES.get(item.name, 4.5)
        elif item.set == "Planet":
            preferred = self._preferred_hand(state)
            score = 7.0 if PLANET_TO_HAND.get(item.name) == preferred else 4.0
        elif item.set == "Booster":
            inference = inference or self.strategy_model.infer(state)
            booster_breakdown = self.pack_planner.score_shop_booster(state, item, inference)
            score = booster_breakdown["total"]
        else:
            score = -2.0

        if item.set == "Joker" and (state.meta.ante or 1) <= 2 and item.cost <= 4:
            score += 1.4
        if item.set == "Voucher" and (state.meta.ante or 1) <= 2:
            score += 1.0

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
        run_plan = inference.get("run_plan", {})
        build_pressure = self._build_pressure(state, inference)
        if not state.shop_items:
            self.last_trace = {
                "phase": "SHOP",
                "strategy": inference,
                "item_scores": [],
                "decision_reason": "shop_inventory_pending",
                "build_pressure": round(build_pressure, 3),
                "run_plan": run_plan,
            }
            logger.info("Waiting for shop inventory to populate before deciding.")
            return ActionResponse(action="NO_OP", message="shop_inventory_pending")

        affordable = [item for item in state.shop_items if item.cost <= state.economy.money]
        scored_items = []
        for item in affordable:
            model_breakdown = self.strategy_model.score_item(state, item, inference)
            legacy = self._score_item(state, item, inference)
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

        reserve_cash = self._reserve_cash(state, build_pressure, inference)
        buy_threshold = self._buy_threshold(state, build_pressure, inference)
        premium_threshold = buy_threshold + 2.0
        top_score = scored_items[0]["total_score"] if scored_items else float("-inf")
        hard_needs = set(run_plan.get("hard_needs", []))
        reroll_aggression = float(run_plan.get("reroll_aggression", 0.0))
        if scored_items:
            best_item = scored_items[0]["item"]
            can_hold_reserve = (state.economy.money - best_item.cost) >= reserve_cash
            best_kind = str((best_item.metadata or {}).get("kind") or "")
            booster_pref = float(run_plan.get("pack_preferences", {}).get(best_kind, 0.0))
            early_tempo_buy = (
                (state.meta.ante or 1) <= 2
                and best_item.set in {"Joker", "Voucher", "Planet", "Booster"}
                and best_item.cost <= max(5, state.economy.money)
                and top_score >= 5.2
            )
            forced_board_upgrade = (
                build_pressure >= 2.5
                and best_item.set in {"Joker", "Voucher", "Planet", "Booster"}
                and top_score >= (buy_threshold - 0.5)
            )
            role_cover_buy = (
                best_item.set in {"Joker", "Voucher", "Planet", "Booster"}
                and top_score >= (buy_threshold - 0.35)
                and any(
                    entry["model"].get("plan_adjustment", {}).get("role_bonus", 0.0) >= 0.4
                    for entry in scored_items[:1]
                )
            )
            xmult_conversion_buy = (
                run_plan.get("stage") in {"conversion", "endgame"}
                and "xmult" in hard_needs
                and best_item.set in {"Joker", "Booster"}
                and top_score >= (buy_threshold - 0.15)
            )
            preferred_booster_buy = (
                best_item.set == "Booster"
                and booster_pref >= 1.0
                and top_score >= (buy_threshold - 0.3)
            )
        else:
            best_item = None
            can_hold_reserve = False
            early_tempo_buy = False
            forced_board_upgrade = False
            role_cover_buy = False
            xmult_conversion_buy = False
            preferred_booster_buy = False

        if scored_items and (
            top_score >= premium_threshold
            or (top_score >= buy_threshold and can_hold_reserve)
            or early_tempo_buy
            or forced_board_upgrade
            or role_cover_buy
            or xmult_conversion_buy
            or preferred_booster_buy
        ):
            logger.info("Buying shop item '%s' (score %.2f).", best_item.name, top_score)
            self.last_trace = {
                "phase": "SHOP",
                "strategy": inference,
                "build_pressure": round(build_pressure, 3),
                "run_plan": run_plan,
                "item_scores": [
                    {
                        "name": entry["name"],
                        "set": entry["set"],
                        "cost": entry["cost"],
                        "legacy_score": round(entry["legacy_score"], 3),
                        "model_score": round(entry["model"]["total"], 3),
                        "plan_score": round(entry["model"].get("plan_adjustment", {}).get("total", 0.0), 3),
                        "total_score": round(entry["total_score"], 3),
                        "vector": entry["model"]["vector"],
                    }
                    for entry in scored_items[:8]
                ],
                "decision_reason": "buy_top_item",
            }
            return ActionResponse(action="BUY_CARD", target_id=best_item.id, message=best_item.name)

        wants_more_quality = (
            len(state.jokers) < 4
            or not scored_items
            or top_score < 5.5
            or bool(hard_needs)
            or (run_plan.get("stage") in {"conversion", "endgame"} and run_plan.get("role_deficits", {}).get("xmult", 0.0) > 0.45)
        )
        reroll_floor = max(state.economy.interest_cap, reserve_cash) + state.economy.reroll_cost
        if (state.meta.ante or 1) <= 2:
            reroll_floor = max(reserve_cash + state.economy.reroll_cost + 2, 8)
        if build_pressure >= 2.5:
            reroll_floor = max(reserve_cash + state.economy.reroll_cost, 6)
        if run_plan.get("stage") in {"conversion", "endgame"} and "xmult" in hard_needs:
            reroll_floor = max(reserve_cash + state.economy.reroll_cost, 5)
        reroll_floor = max(
            reserve_cash + state.economy.reroll_cost,
            int(round(reroll_floor + max(0.0, 0.55 - reroll_aggression) * 4.0 - max(0.0, reroll_aggression - 0.55) * 3.0)),
        )

        if wants_more_quality and state.economy.money >= reroll_floor:
            logger.info("Rerolling shop for a stronger board.")
            self.last_trace = {
                "phase": "SHOP",
                "strategy": inference,
                "build_pressure": round(build_pressure, 3),
                "run_plan": run_plan,
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
            "build_pressure": round(build_pressure, 3),
            "run_plan": run_plan,
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
