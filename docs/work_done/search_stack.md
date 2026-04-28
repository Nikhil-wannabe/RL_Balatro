# Search Stack

The agent uses layered search. Cheap exact play scoring is always evaluated. Discard search escalates from bounded candidate generation to exact enumeration when possible, then deterministic shared-pool Monte Carlo when exact solving is too expensive.

## Search Overview

```mermaid
flowchart TD
    A["SELECTING_HAND state"] --> B["Enumerate all 1-5 card plays"]
    B --> C["Exact scorer evaluates every play"]
    C --> D["Best immediate play score"]
    D --> E{"Discards available?"}
    E -->|"no"| F["Rank plays"]
    E -->|"yes"| G["Branch-and-bound discard candidates"]
    G --> H{"Known deck and small draw?"}
    H -->|"yes"| I["ExactClearSolver"]
    H -->|"no"| J["MonteCarloSimulator"]
    I --> K["Discard entries"]
    J --> K
    C --> L["Play entries"]
    K --> M["Robust ranking"]
    L --> M
```

## Discard Candidate Funnel

```mermaid
flowchart LR
    A["All discard subsets"] --> B["DiscardBounder"]
    B --> C["Sound optimistic upper bound"]
    B --> D["Heuristic priority"]
    C --> E["Candidate cap"]
    D --> E
    E --> F["Exact pending"]
    E --> G["MC pending by draw count"]
```

## Exact Discard Solver

```mermaid
flowchart TD
    A["Discard IDs"] --> B["Known deck required"]
    B --> C{"comb(deck, draw_count) <= cap?"}
    C -->|"no"| Z["Return None"]
    C -->|"yes"| D["Group equivalent mutated cards"]
    D --> E{"category states <= cap?"}
    E -->|"yes"| F["Hypergeometric category aggregation"]
    E -->|"no"| G["Raw combination enumeration"]
    F --> H["Weighted MonteCarloStats"]
    G --> H
```

## Shared-Pool Monte Carlo

```mermaid
sequenceDiagram
    participant Planner
    participant MC as MonteCarloSimulator
    participant Pool as Shared Draw Pool
    participant Scorer

    Planner->>MC: build_shared_pool(draw_count)
    MC-->>Pool: deterministic samples
    Planner->>MC: evaluate candidate A with same pool
    MC->>Scorer: best score after each draw
    Planner->>MC: evaluate candidate B with same pool
    MC->>Scorer: best score after each draw
    MC-->>Planner: comparable stats with reduced noise
```

## Robust Ranking

```mermaid
flowchart TD
    A["Action entry"] --> B["Base clear probability"]
    A --> C["Expected score"]
    D["Belief rule models"] --> E["Lower model"]
    D --> F["Nominal model"]
    D --> G["Upper model"]
    B --> H["Aggregate candidate"]
    C --> H
    E --> H
    F --> H
    G --> H
    H --> I["BMA clear probability"]
    H --> J["Conservative clear probability"]
    H --> K["Model values"]
    K --> L["Minimax regret"]
```

## Optional JavaScript Solver

```mermaid
flowchart LR
    A["Planner budget allows JS"] --> B["JSRoundSolver.solve"]
    B --> C["scripts/balatro_round_solver.js"]
    C --> D["Vendored calculator"]
    C --> E["Rollout search"]
    E --> F["Action hint with diagnostics"]
    F --> G{"Matches Python-ranked action?"}
    G -->|"yes and strong enough"| H["Prefer JS hint"]
    G -->|"no"| I["Use Python ranking"]
```

The latest audit fixed the JS solver boss flag path so it reads `blind.boss_modifier` as well as `blind.name` before enabling The Flint or The Eye behavior.

