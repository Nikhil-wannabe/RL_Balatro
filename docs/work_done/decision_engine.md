# Decision Engine

The Python planner is a phase router plus several decision layers. `Planner.plan_action` selects the relevant subsystem, then records the result through `DecisionTracer`.

## Phase Router

```mermaid
flowchart TD
    A["BalatroState.meta.phase"] --> B{Phase}
    B -->|"SELECTING_HAND"| C["Planner.plan_selecting_hand"]
    B -->|"BLIND_SELECT"| D["Planner.plan_blind_select"]
    B -->|"ROUND_EVAL"| E["CASH_OUT"]
    B -->|"SHOP"| F["ShopPlanner.plan_action"]
    B -->|"PACK_CHOICE"| G["PackPlanner.plan_action"]
    B -->|"unknown"| H["NO_OP with reason"]
    C --> I["Decision trace"]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

## Selecting-Hand Decision Stack

```mermaid
flowchart TB
    A["State"] --> B["StrategyModel.infer"]
    A --> C["BeliefModel.from_state"]
    A --> D["Enumerate play combos"]
    D --> E["Scorer.evaluate_play"]
    E --> F["Play entries"]
    A --> G{"Discards available and budget remains?"}
    G -->|"yes"| H["Evaluate discard actions"]
    G -->|"no"| I["Play only"]
    H --> J["Entry list"]
    F --> J
    I --> J
    J --> K["Round viability biases"]
    K --> L["Robust aggregates and minimax regret"]
    L --> M["Brain.determine_mode"]
    M --> N["Brain.rank_action"]
    N --> O["Optional JS hint preference"]
    O --> P["ActionResponse"]
```

## Tactical Modes

```mermaid
stateDiagram-v2
    [*] --> LETHAL: immediate score >= target
    [*] --> PANIC: low clear probability and no resources
    [*] --> SCALING_PRESERVE: conservative clear very high
    [*] --> SAFE_CLEAR: conservative clear high
    [*] --> DESPERATION: default under pressure

    LETHAL --> RankActions: prefer clear and efficiency
    SAFE_CLEAR --> RankActions: prefer stable play
    DESPERATION --> RankActions: boost survival
    SCALING_PRESERVE --> RankActions: preserve future value
    PANIC --> RankActions: ignore elegance, survive
```

## Ranking Inputs

```mermaid
flowchart LR
    A["ActionFeatures"] --> B["clear_probability"]
    A --> C["clear_probability_lcb"]
    A --> D["expected_score"]
    A --> E["resource remaining"]
    A --> F["future hand strength"]
    A --> G["discard quality"]
    A --> H["cvar loss"]
    A --> I["minimax regret"]
    B --> J["Rank tuple"]
    C --> J
    D --> J
    E --> J
    F --> J
    G --> J
    H --> J
    I --> J
    J --> K["Sorted RankedAction list"]
```

## Strategy Layer

```mermaid
flowchart TD
    A["Visible run state"] --> B["Deck profile"]
    A --> C["Deck metrics"]
    A --> D["Draw metrics"]
    A --> E["Joker evidence"]
    A --> F["Consumable evidence"]
    B --> G["Archetype scores"]
    C --> G
    D --> G
    E --> G
    F --> G
    G --> H["Softmax posterior"]
    H --> I["RunPlanner.build"]
    I --> J["target_hand"]
    I --> K["role deficits"]
    I --> L["pack preferences"]
    I --> M["economy floor"]
```

The decision engine is designed so tactical survival, long-run strategy, and exact scoring each have a clear place. That separation makes future tuning safer because a shop heuristic should not need to know about socket behavior, and a scoring mechanic should not need to know about run-stage strategy.

