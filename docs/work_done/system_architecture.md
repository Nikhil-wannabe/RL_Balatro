# System Architecture

The project is a mod-assisted Balatro agent. The Lua side observes and acts in the game; the Python side decides what to do; the optional JavaScript solver provides an additional high-fidelity search hint for difficult hand states.

## Component Map

```mermaid
flowchart TB
    subgraph Game["Balatro Runtime"]
        G["Balatro UI and game state"]
        L["lua/agent.lua"]
        T["lua/lovely.toml"]
        T --> L
        L <--> G
    end

    subgraph Backend["Python Backend"]
        S["server.AgentServer"]
        ST["state.BalatroState"]
        P["planner.Planner"]
        SC["scorer.Scorer"]
        BR["brain.Brain"]
        SM["strategy_model.StrategyModel"]
        SP["shop_planner.ShopPlanner"]
        PP["pack_planner.PackPlanner"]
        DT["decision_trace.DecisionTracer"]
    end

    subgraph Search["Search and Evaluation"]
        HS["hand_solver.HandSolver"]
        DB["discard_bounds.DiscardBounder"]
        EX["exact_clear.ExactClearSolver"]
        MC["monte_carlo.MonteCarloSimulator"]
        RV["robust_value"]
        JS["scripts/balatro_round_solver.js"]
    end

    L -- "JSON state over TCP" --> S
    S -- "JSON action" --> L
    S --> ST --> P
    P --> SC
    P --> BR
    P --> SM
    P --> SP
    P --> PP
    P --> HS
    P --> DB --> EX
    P --> MC
    P --> RV
    P -. "optional hint" .-> JS
    P --> DT
```

## Repository Ownership

```mermaid
flowchart LR
    R["Repo Root"] --> Lua["lua/"]
    R --> Py["python/"]
    R --> Tests["tests/"]
    R --> Scripts["scripts/"]
    R --> Docs["docs/"]
    R --> Math["mathematics documentation/"]
    R --> Third["third-party calculator"]

    Lua --> LuaA["Game bridge and UI actions"]
    Py --> PyA["Decision engine and schemas"]
    Tests --> TestsA["Regression and integration coverage"]
    Scripts --> ScriptsA["Launch profiles and JS solver"]
    Docs --> DocsA["Operator and architecture docs"]
    Math --> MathA["Research notes and model rationale"]
    Third --> ThirdA["Vendored scoring calculator"]
```

## Runtime Boundaries

| Boundary | Producer | Consumer | Format |
| --- | --- | --- | --- |
| Game state snapshot | `lua/agent.lua` | `python/server.py` | JSON line |
| Action response | `python/planner.py` | `lua/agent.lua` | JSON line |
| Decision trace | `python/decision_trace.py` | developer/operator | JSONL |
| JS solver hint | `python/js_solver.py` | `python/planner.py` | JSON stdout |
| Tests | `tests/` | pytest | deterministic fixtures |

## Design Intent

```mermaid
flowchart TD
    A["Live game state"] --> B["Normalize into schema"]
    B --> C["Choose phase-specific planner"]
    C --> D["Use deterministic ranking first"]
    D --> E["Spend search budget only where useful"]
    E --> F["Return executable UI action"]
    F --> G["Trace decision for tuning"]
```

The system favors deterministic, inspectable decisions. Search is bounded by time budgets, and stochastic components use state-derived seeds so repeated states reproduce the same action.

