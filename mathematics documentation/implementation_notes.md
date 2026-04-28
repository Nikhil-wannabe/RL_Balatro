# Implementation Notes

## Runtime Architecture

### Lua bridge

File:
- `lua/agent.lua`

Responsibilities:
- detect the current Balatro phase,
- serialize the live game state into JSON,
- send that JSON to Python over TCP,
- execute the returned action in-game.

The bridge now serializes much more context than before:
- current hand,
- Joker board,
- remaining draw pile,
- discard pile,
- hand levels,
- current phase,
- shop inventory,
- blind-selection context.

### Python coordinator

Files:
- `python/server.py`
- `python/planner.py`
- `python/shop_planner.py`
- `python/js_solver.py`

Responsibilities:
- route by phase,
- call the exact JavaScript round solver when appropriate,
- fall back to Python heuristics when exact search would be too slow,
- make shop decisions,
- return a concrete action for Lua to execute.

### Exact round solver

File:
- `scripts/balatro_round_solver.js`

This script loads the vendored Balatro calculator under `_third_party/balatro-calculator/` and uses it as a higher-fidelity scoring core for hand-play decisions.

## Why The Solver Is Hybrid

The exact JavaScript search is strongest when:
- the current state is tactically dense,
- the visible deck information is rich,
- the time budget is still sufficient.

The Python fallback is preferred when:
- the target is huge and exact search is likely to exceed the live turn timeout,
- the state is too expensive for exact rollouts,
- we still need a safe answer immediately.

## Shop Policy

The shop planner is intentionally conservative.

It currently supports:
- buying high-value Jokers,
- buying strong Vouchers,
- buying matching Planet cards,
- rerolling when bankroll and interest margin justify it,
- leaving the shop automatically when nothing attractive is present.

It intentionally deprioritizes:
- booster packs,
- complex consumable lines,
- highly speculative purchases.

That is a quality-of-control choice, not a claim that packs are bad in Balatro. It simply keeps the autonomous loop stable while the rest of the run logic matures.

## Remaining Gaps

The repository is materially stronger than before, but it is not yet a proven "beats every stake on every seed" system.

The biggest remaining gaps are:
- deeper shop/planning logic across many rounds,
- broader exact boss-blind modeling,
- fuller support for booster packs and consumable usage,
- a stronger late-game exact solver that fits the live latency budget,
- systematic empirical benchmarking on gold-stake runs.

That is the right next layer of work if the goal is a truly competitive autonomous bot rather than a strong tactical autoplayer.

