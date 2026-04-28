# Scoring and Boss Mechanics

The scorer estimates Balatro hand outcomes for planner search. It handles hand classification, scoring-card selection, a growing set of joker hooks, held-card effects, editions, hand levels, and boss modifiers.

## Scoring Pipeline

```mermaid
flowchart TD
    A["Played cards"] --> B["Classify poker hand"]
    B --> C["Select scoring subset"]
    C --> D{"Boss invalidates play?"}
    D -->|"yes"| Z["score = 0"]
    D -->|"no"| E["Get hand level chips/mult"]
    E --> F["Apply boss base score scales"]
    F --> G["Score non-debuffed scoring cards"]
    G --> H["Apply held-card effects"]
    H --> I["Apply joker effects"]
    I --> J["Apply joker editions"]
    J --> K["round(chips * mult * x_mult)"]
```

## Hand Classification

```mermaid
flowchart LR
    A["All played cards"] --> B["Try hands by priority"]
    B --> C["Flush Five"]
    B --> D["Flush House"]
    B --> E["Five of a Kind"]
    B --> F["Straight Flush"]
    B --> G["Four of a Kind"]
    B --> H["Full House"]
    B --> I["Flush/Straight/etc."]
    C --> Z["Best subset"]
    D --> Z
    E --> Z
    F --> Z
    G --> Z
    H --> Z
    I --> Z
```

The latest audit fixed an important detail: debuffed cards still participate in this classification step. They are filtered only when card chips, card enhancements, held-card effects, and card-triggered joker checks are applied.

## Debuffed-Card Semantics

```mermaid
flowchart TD
    A["Played card"] --> B{"Is debuffed?"}
    B -->|"no"| C["Can classify and score"]
    B -->|"yes"| D["Can classify hand"]
    D --> E["Does not add chips"]
    D --> F["Does not trigger enhancement/edition/card effects"]
    D --> G["Does not count for face/suit scoring triggers"]
```

The scorer recognizes both explicit serialized card debuffs and boss-driven debuffs:

```mermaid
flowchart LR
    A["_card_is_debuffed"] --> B["card.is_debuffed"]
    A --> C["The Plant face-card debuff"]
    A --> D["Suit boss debuffs"]
    D --> E["The Club"]
    D --> F["The Goad"]
    D --> G["The Head"]
    D --> H["The Window"]
```

## Boss Mechanics

```mermaid
classDiagram
    class BossProfile {
      string name
      string debuffed_suit
      bool face_cards_debuffed
      bool require_five_card_play
      bool forbid_repeat_hands
      bool lock_to_first_hand_type
      bool money_to_zero_on_most_played
      float base_chips_scale
      float base_mult_scale
      float future_penalty
    }

    class Scorer {
      evaluate_play()
      classify_hand()
      estimate_money_delta()
    }

    class Planner {
      plan_selecting_hand()
      _apply_round_viability_biases()
    }

    BossProfile --> Scorer
    BossProfile --> Planner
```

## Current Coverage

```mermaid
flowchart TD
    A["tests/test_scorer.py"] --> B["Hand classification"]
    A --> C["Scoring-card subset"]
    A --> D["Hand levels"]
    A --> E["Joker hooks"]
    A --> F["Boss invalidation"]
    A --> G["Debuffed card regression"]
    H["tests/test_boss_logic.py"] --> I["Boss profiles"]
    H --> J["Money changes"]
    H --> K["Boss constraints"]
```

This page should be updated whenever new joker mechanics are added, especially retriggers and copy effects such as Blueprint or Brainstorm.

For the full code-mapped formulas behind classification, debuffs, boss constraints, and scoring order, see [Runtime Mathematical Specification](../../mathematics%20documentation/runtime_mathematical_spec.md).
