# Verification

The current verification story is mostly deterministic Python tests plus a JavaScript solver smoke check. The latest full run passed after the audit fixes.

## Verification Pipeline

```mermaid
flowchart TD
    A["Code change"] --> B["compileall"]
    B --> C["Focused tests"]
    C --> D["Full pytest suite"]
    D --> E["Node solver smoke test"]
    E --> F["Review git diff"]
    F --> G["Document behavior and gaps"]
```

## Latest Audit Result

```mermaid
pie title Latest Full Test Suite
    "Passed" : 74
    "Failed" : 0
```

Commands run:

```powershell
python -m compileall -q python tests
python -m pytest
Get-Content examples\sample_playable.json | node scripts\balatro_round_solver.js --samples 8 --beam 6
```

Result:

```text
74 passed
```

## Test Coverage Map

```mermaid
flowchart LR
    A["tests/"] --> B["Lua bridge source contracts"]
    A --> C["Boss logic"]
    A --> D["Scorer mechanics"]
    A --> E["Brain ranking"]
    A --> F["Planner scenarios"]
    A --> G["Monte Carlo repeatability"]
    A --> H["Server async/cache behavior"]
    A --> I["Shop planner"]
    A --> J["Strategy model"]
    A --> K["State parsing"]
    A --> L["JS solver boss flag regression"]
```

## Audit Fixes Covered

```mermaid
flowchart TD
    A["Audit finding"] --> B["Debuffed cards removed before classification"]
    B --> C["Fix scorer classification/scoring split"]
    C --> D["tests/test_scorer.py regression"]

    A --> E["JS solver missed blind.boss_modifier"]
    E --> F["Add bossName(state) helper"]
    F --> G["tests/test_js_solver.py regression"]
```

## Remaining Test Gaps

```mermaid
flowchart TD
    A["Known gaps"] --> B["Full in-game UI automation"]
    A --> C["High-fidelity retriggers"]
    A --> D["Blueprint/Brainstorm copy effects"]
    A --> E["More pack-selection fixtures"]
    A --> F["Long-run trace replay tests"]
```

These are not current blockers, but they are the next useful places to add coverage as mechanics support grows.

## Documentation Maintenance Checklist

```mermaid
flowchart LR
    A["When code changes"] --> B{"Which subsystem?"}
    B -->|"Lua bridge"| C["Update runtime_flow.md"]
    B -->|"Planner/Brain"| D["Update decision_engine.md"]
    B -->|"Scorer/Boss"| E["Update scoring_and_boss_mechanics.md"]
    B -->|"Search"| F["Update search_stack.md"]
    B -->|"Shop/Pack"| G["Update shop_and_pack_planning.md"]
    B -->|"Tests"| H["Update verification.md"]
```

