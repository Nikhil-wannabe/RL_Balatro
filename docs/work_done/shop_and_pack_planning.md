# Shop and Pack Planning

The shop and pack planners use the same strategic context as the hand planner, but their action spaces are different: buy, reroll, leave, or select a pack item.

## Shop Flow

```mermaid
flowchart TD
    A["SHOP state"] --> B["StrategyModel.infer"]
    B --> C["Build pressure"]
    B --> D["Run plan"]
    A --> E{"Shop items present?"}
    E -->|"no"| F["NO_OP shop_inventory_pending"]
    E -->|"yes"| G["Filter affordable items"]
    G --> H["Score each item"]
    H --> I["Reserve cash and buy thresholds"]
    I --> J{"Buy top item?"}
    J -->|"yes"| K["BUY_CARD target_id"]
    J -->|"no"| L{"Reroll worthwhile and affordable?"}
    L -->|"yes"| M["REROLL_SHOP"]
    L -->|"no"| N["NEXT_ROUND"]
```

## Item Score Blend

```mermaid
flowchart LR
    A["Shop item"] --> B["Legacy heuristic score"]
    A --> C["StrategyModel.score_item"]
    C --> D["Synergy vector"]
    C --> E["RunPlanner adjustment"]
    C --> F["Edition/sticker/cost adjustments"]
    B --> G["0.45 legacy"]
    C --> H["0.55 model"]
    G --> I["total_score"]
    H --> I
```

## Run Plan Influence

```mermaid
flowchart TD
    A["RunPlanner"] --> B["stage"]
    A --> C["target_hand"]
    A --> D["role_deficits"]
    A --> E["hard_needs"]
    A --> F["pack_preferences"]
    A --> G["economy_floor"]
    B --> H["Buy threshold"]
    C --> I["Planet and pack preference"]
    D --> J["Role-cover buys"]
    E --> K["Conversion buys"]
    F --> L["Booster scoring"]
    G --> M["Reserve cash"]
```

## Pack Choice Flow

```mermaid
flowchart TD
    A["PACK_CHOICE state"] --> B["StrategyModel.infer"]
    A --> C{"Pack items present?"}
    C -->|"no"| D["NO_OP pack_inventory_pending"]
    C -->|"yes"| E["Score pack items"]
    E --> F{"Pack kind"}
    F -->|"Celestial"| G["Planet alignment"]
    F -->|"Arcana"| H["Tarot utility"]
    F -->|"Spectral"| I["Spectral utility"]
    F -->|"Standard"| J["Playing-card utility"]
    F -->|"Buffoon"| K["Joker utility"]
    G --> L["Take highest score"]
    H --> L
    I --> L
    J --> L
    K --> L
    L --> M["TAKE_PACK_CARD target_id"]
```

## Booster Preference Map

```mermaid
flowchart LR
    A["Run need"] --> B{"Immediate tempo needed?"}
    B -->|"high"| C["Buffoon priority rises"]
    B -->|"medium"| D["Arcana or Celestial stays attractive"]
    B -->|"low"| E["Prefer shaping packs"]

    E --> F{"Long-run shaping needed?"}
    F -->|"planet scaling"| G["Celestial priority rises"]
    F -->|"deck editing"| H["Arcana or Standard priority rises"]
    F -->|"spectral support"| I["Spectral priority rises"]
    F -->|"joker slots open"| J["Buffoon remains viable"]
```

The code computes preferences from stage, target hand, deck flags, and deck-specific blueprints.
