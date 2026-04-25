# Mathematics Documentation

This folder documents the mathematical model behind the autonomous Balatro agent.

Files:
- `balatro_mechanics_research.md`: distilled research notes on the Balatro rules that matter for autonomy.
- `deckbuilding_strategy_research.md`: deck-building archetypes, synergy notes, and how they inform the statistical shop model.
- `round_search_math.md`: the finite-horizon decision model, Monte Carlo rollout policy, and utility function used by the runtime.
- `implementation_notes.md`: how the mathematical ideas map onto the code in this repository.

The guiding principle is practical control under a short inference budget:
- exact or near-exact scoring where it matters most,
- stochastic lookahead for discard/play decisions,
- conservative fallback logic when the expensive model would exceed the live game timeout.
