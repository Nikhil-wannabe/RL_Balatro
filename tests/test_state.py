import json
from python.state import BalatroState

def test_state_parsing():
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "TEST", "ante": 1, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Small Blind", "target_score": 300, "current_score": 0},
        "economy": {"money": 5, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [{"id": "C1", "rank": "10", "suit": "Spades", "base_chips": 10}],
        "jokers": []
    }
    state = BalatroState(**payload)
    assert state.hand[0].rank == "10"
    assert state.meta.ante == 1


def test_state_coerces_empty_list_to_mapping_fields():
    payload = {
        "meta": {"protocol_version": "1.0.0", "seed": "TEST", "ante": 1, "round": 1, "phase": "SELECTING_HAND"},
        "blind": {"name": "Small Blind", "target_score": 300, "current_score": 0},
        "economy": {"money": 5, "hands_left": 4, "discards_left": 3, "hand_size": 8},
        "hand": [],
        "jokers": [{"id": "J1", "name": "Joker", "internal_state": []}],
        "blind_choices": [],
        "hand_levels": [],
        "shop_items": [{"id": "S1", "name": "Voucher", "set": "Voucher", "metadata": []}],
    }
    state = BalatroState(**payload)
    assert state.blind_choices == {}
    assert state.hand_levels == {}
    assert state.jokers[0].internal_state == {}
    assert state.shop_items[0].metadata == {}


def test_state_parses_consumables_and_pack_items():
    payload = {
        "meta": {
            "protocol_version": "1.0.0",
            "seed": "PACK",
            "ante": 1,
            "round": 1,
            "phase": "PACK_CHOICE",
            "pack_kind": "Buffoon",
        },
        "blind": {"name": "Small Blind", "target_score": 300, "current_score": 0},
        "economy": {
            "money": 5,
            "hands_left": 4,
            "discards_left": 3,
            "hand_size": 8,
            "joker_slots": 5,
            "consumable_slots": 2,
        },
        "consumables": [{"id": "CNS_1", "name": "Hermit", "set": "Tarot", "cost": 0}],
        "pack_items": [
            {"id": "PK_1", "name": "Green Joker", "set": "Joker", "cost": 0},
            {
                "id": "PK_2",
                "name": "7 of Hearts",
                "set": "Playing Card",
                "rank": "7",
                "suit": "Hearts",
                "base_chips": 7,
                "enhancement": "None",
                "seal": "Blue",
            },
        ],
    }
    state = BalatroState(**payload)
    assert state.meta.pack_kind == "Buffoon"
    assert state.consumables[0].name == "Hermit"
    assert state.pack_items[1].rank == "7"
    assert state.pack_items[1].seal == "Blue"


def test_state_coerces_object_shaped_deck_metadata():
    payload = {
        "meta": {
            "protocol_version": "1.0.0",
            "seed": "DECK",
            "ante": 1,
            "round": 1,
            "phase": "SELECTING_HAND",
            "deck_name": {"name": "Red Deck"},
            "deck_key": {
                "alerted": True,
                "config": {
                    "center": {
                        "key": "b_red",
                        "name": "Red Deck",
                    }
                },
                "unlocked": True,
            },
        },
        "blind": {"name": "Small Blind", "target_score": 300, "current_score": 0},
        "economy": {"money": 5, "hands_left": 4, "discards_left": 3, "hand_size": 8},
    }
    state = BalatroState(**payload)
    assert state.meta.deck_name == "Red Deck"
    assert state.meta.deck_key == "b_red"
