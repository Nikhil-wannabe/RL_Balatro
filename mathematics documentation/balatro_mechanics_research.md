# Balatro Mechanics Research

## Objective

A Balatro run is a sequence of blinds. For each blind, the agent must accumulate enough score before it runs out of hands. Surviving high stakes depends on two things at once:
- tactical correctness inside a blind,
- strategic resource growth across the whole run.

This repository now models both, but at different fidelity levels.

## Mechanics That Directly Affect Search

### 1. Blind target and current score

The immediate control problem is:

```math
\text{clear blind} \iff \text{current score} + \sum_{t=1}^{T} \text{hand score}_t \ge \text{target score}
```

where the horizon length `T` is bounded by `hands_left`.

### 2. Hands, discards, and redraws

At the round level, Balatro behaves like a finite-horizon stochastic process.

State variables that matter most:
- current score,
- hands left,
- discards left,
- current hand,
- remaining draw pile,
- discard pile,
- hand-size cap,
- Joker and hand-level state.

Each action is either:
- `PLAY_HAND`: consume a subset of cards, score them, then refill to hand size.
- `DISCARD`: throw away a subset of cards, then refill to hand size.

This repo now serializes the exact visible draw pile and discard pile from Lua when that data is available, which is much stronger than the old "assume a fresh 52-card deck minus hand" approximation.

### 3. Hand levels

Balatro does not score poker hands with a fixed chips/mult pair for the whole run. The chips and multiplier of each hand type increase with upgrades. That means the true value of:
- `Pair`,
- `High Card`,
- `Flush`,
- `Straight`,
- `Full House`,
- and so on

is run-dependent, not static.

The Lua bridge now serializes `G.GAME.hands[...]`, so the search layer can incorporate current hand levels instead of relying only on base defaults.

### 4. Joker and modifier order

Scoring is order-sensitive. At a high level:
1. determine the scoring hand,
2. initialize chips and mult from the hand type,
3. score played cards,
4. score held-in-hand effects,
5. score Jokers,
6. apply deck-level modifiers.

That order is why an exact scorer matters: late-game Joker boards are not well approximated by "raw chips plus a few bonuses".

### 5. Stakes

The stake system matters because higher stakes reduce the agent's error budget.

Practical implications for the agent:
- weaker economy recovery,
- harsher sticker constraints in the shop,
- less tolerance for low-EV rerolls or bad temporary buys,
- more importance on preserving interest thresholds.

The shop policy in this repo therefore scores rental/perishable/eternal stickers explicitly instead of treating all shop cards as equally clean.

## What The Runtime Models Exactly vs Approximately

### Exact or near-exact

- visible hand contents,
- visible draw pile when serialized by Lua,
- visible discard pile when serialized by Lua,
- hands/discards remaining,
- hand-level state,
- phase routing between hand play, blind select, round cash-out, and shop,
- many vanilla scoring interactions through the external Balatro calculator integration.

### Approximate

- not every boss blind is modeled as a special-case constraint yet,
- not every shop object class is acted on yet,
- pack-opening lines are intentionally deprioritized,
- the economic long-horizon shop policy is heuristic rather than solved by full dynamic programming,
- the fallback Python search still uses an approximate scorer when the exact JavaScript search is too slow for a live turn.

## Why Gold Stake Is Hard

Gold-stake autonomy is difficult because the control problem is not "find the biggest hand now". It is:

```math
\max_\pi \Pr(\text{survive all antes} \mid \text{stake, deck, joker board, economy})
```

subject to:
- hidden future draws,
- combinatorial hand/discard branching,
- shop decisions with delayed payoff,
- non-linear Joker synergies,
- strict real-time latency inside the game loop.

That is why this implementation uses a hybrid approach instead of one monolithic solver.

## External References Used

- [Balatro Wiki: Stakes](https://balatrogame.fandom.com/wiki/Stakes)
- [Balatro Wiki: Blinds and Antes](https://balatrogame.fandom.com/wiki/Blinds_and_Antes)
- [Balatro Calculator (EFHIII)](https://github.com/EFHIII/balatro-calculator)
- [Balatro Calculator DeepWiki: Hand Scoring System](https://deepwiki.com/EFHIII/balatro-calculator/3.1-hand-scoring-system)

