# Deck-Building Strategy Research

This document distills the internet research that informed the current shop and deck-building policy.

## High-Level Conclusions

Across wiki pages, strategy guides, and high-stake community discussion, the same themes repeat:

1. High stakes reward consistency more than flashy five-card lines.
2. Economy is a major hidden scaling vector because it buys rerolls, Vouchers, and pivots.
3. The strongest runs usually commit to one hand family or one Joker engine, then stack synergies around it.
4. Orange and Gold Stake force sticker-aware buying because Perishable and Rental punish low-discipline shopping.

## Archetypes Used By The Strategy Model

The code in `python/strategy_model.py` models the run as a soft mixture over these archetypes.

### 1. Economy-first

Core ideas:
- hold interest thresholds,
- buy income engines and reroll enablers,
- avoid Rentals too early on Gold Stake,
- use shop flexibility to pivot into a scaling board later.

Research signals:
- economy guides strongly emphasize preserving interest and valuing Seed Money, Money Tree, and To the Moon.
- Gold Stake discussion repeatedly points to economy as the difference between surviving the early game and dying before a real engine appears.

Operational rules now encoded:
- stronger value for `Seed Money`, `Money Tree`, `To the Moon`, `Reroll Surplus`, `Reroll Glut`,
- stronger Rental penalties while money is low,
- higher reroll willingness once bankroll is safely above interest thresholds.

### 2. Small-hand consistency

Core ideas:
- High Card and Pair are stable at higher stakes because they need fewer discards and fewer specific cards.
- small hands preserve deck-dependent Jokers like Blue Joker and leave more cards held in hand for held effects.

Research signals:
- `Blue Joker` explicitly favors High Card and Pair because fewer cards are spent.
- `Green Joker` wiki strategy strongly favors repeated cheap hands.
- community Gold Stake advice repeatedly emphasizes stable hands over forcing five-card patterns under Blue Stake and above.

Operational rules now encoded:
- higher prior for small-hand strategies at higher stakes,
- stronger value for `Green Joker`, `Blue Joker`, `Half Joker`, `Jolly Joker`, `Sly Joker`, `Square Joker`, `Blackboard`,
- stronger value for `Pluto` and `Mercury`,
- stronger value for `Telescope` and `Observatory` when the preferred hand is already compact.

### 3. Held-in-hand scaling

Core ideas:
- hold powerful cards instead of spending them,
- multiply Steel, Baron, Shoot the Moon, or Raised Fist effects through Mime and larger hand size,
- often pairs naturally with High Card or Pair.

Research signals:
- `Mime` specifically retriggers Steel cards, Blue Seals, Baron, Raised Fist, Reserved Parking, and Shoot the Moon.
- `Steel Joker` wiki strategy recommends smaller hands to maximize cards held.
- `Baron` and `Mime` are highlighted as a premium synergy shell.

Operational rules now encoded:
- explicit archetype for held-in-hand engines,
- deck metrics that reward steel density and blue-seal density,
- stronger value for `Mime`, `Baron`, `Shoot the Moon`, `Reserved Parking`, `Steel Joker`, and hand-size Vouchers.

### 4. Flush and suit engines

Core ideas:
- commit to suit concentration,
- exploit suit-specific Jokers,
- use deck manipulation or favorable decks to raise flush frequency.

Research signals:
- `Arrowhead`, `Bloodstone`, `Onyx Agate`, and `Rough Gem` all scale directly with suit concentration.
- `Smeared Joker` broadens suit compatibility.
- `Checkered Deck` strongly amplifies flush and straight-flush consistency.

Operational rules now encoded:
- suit concentration of the full visible deck increases the flush posterior,
- flush-specific Jokers and planets get higher value under that posterior,
- `Smeared Joker` gets a large synergy score in flush-leaning runs.

### 5. Straight engines

Core ideas:
- Straights become much more viable once `Shortcut` or `Four Fingers` appears.
- straight support cards are strongest as packages, not isolated pickups.

Research signals:
- `Shortcut` and `Four Fingers` have repeated documented synergy.
- `Runner`, `Devious Joker`, `Crazy Joker`, `Superposition`, and `Seance` all improve once straights become reliable.
- `Abandoned Deck` and `Checkered Deck` improve straight odds.

Operational rules now encoded:
- explicit straight archetype,
- high synergy value for `Shortcut` and `Four Fingers`,
- stronger downstream value for straight payoff Jokers once the posterior shifts toward straights.

### 6. Deck-growth packages

Core ideas:
- add cards on purpose when the board is built to profit from it,
- avoid uncontrolled bloat if your scoring plan needs precision.

Research signals:
- `Hologram`, `DNA`, `Certificate`, `Marble Joker`, and `Blue Joker` repeatedly appear together in synergy notes.
- Hologram specifically favors smaller hands because they tolerate bloat better.

Operational rules now encoded:
- deck size above 52 raises the deck-growth posterior,
- higher value for `Hologram`, `DNA`, `Certificate`, `Marble Joker`, and related support when the board already leans that way.

### 7. Face-card packages

Core ideas:
- exploit cards that care about Kings, Queens, Jacks, or all faces,
- often overlaps with held-in-hand strategies.

Research signals:
- `Baron` plus Kings,
- `Shoot the Moon` plus Queens,
- `Photograph`, `Smiley Face`, `Pareidolia`, and other face-centered payoffs.

Operational rules now encoded:
- face density increases the face-card posterior,
- face-card Jokers receive stronger item scores when the deck already leans there.

## Why This Is Statistical Rather Than Rule-Only

The current model does not hard-commit to a single archetype. Instead it estimates a posterior-like weight over several archetypes using:
- stake,
- money and discard pressure,
- hand-level history,
- current Joker evidence,
- visible deck composition.

Then each shop candidate is scored by:

```math
\text{item value} =
\text{base value}
+ \text{edition bonus}
+ \text{stage bonus}
- \text{sticker penalty}
- \text{cost penalty}
+ 4 \cdot \mathbb{E}_{a \sim p(a \mid s)}[\text{synergy}(a, \text{item})]
```

This is not a trained model yet, but it is already much more expressive than a static buy-list.

## Sources Used

- [Balatro Economy Guide](https://games.gg/balatro/guides/balatro-economy-guide/)
- [Balatro Joker Guide](https://games.gg/balatro/guides/balatro-advanced-joker-guide/)
- [Balatro Wiki: Stakes](https://balatrogame.fandom.com/wiki/Stakes)
- [Balatro Wiki: Vouchers](https://balatrogame.fandom.com/wiki/Vouchers)
- [Balatro Wiki: Guide: General strategy](https://balatrogame.fandom.com/wiki/Guide%3A_General_strategy)
- [Balatro Wiki: Blue Joker](https://balatrogame.fandom.com/wiki/Blue_Joker)
- [Balatro Wiki: Green Joker](https://balatrogame.fandom.com/wiki/Green_Joker)
- [Balatro Wiki: Mime](https://balatrogame.fandom.com/wiki/Mime_%28Joker%29)
- [Balatro Wiki: Baron](https://balatrogame.fandom.com/wiki/Baron_%28Joker%29)
- [Balatro Wiki: Steel Joker](https://balatrogame.fandom.com/wiki/Steel_Joker)
- [Balatro Wiki: Hologram](https://balatrogame.fandom.com/wiki/Hologram)
- [Balatro Wiki: DNA](https://balatrogame.fandom.com/wiki/DNA_%28Joker%29)
- [Balatro Wiki: Burnt Joker](https://balatrogame.fandom.com/wiki/Burnt_Joker)
- [Balatro Wiki: Shortcut](https://balatrogame.fandom.com/wiki/Shortcut)
- [Balatro Wiki: Four Fingers](https://balatrogame.fandom.com/wiki/Four_Fingers)
- [Balatro Wiki: Card Modifiers](https://balatrogame.fandom.com/wiki/Card_Modifiers)
- [Balatro Wiki: Checkered Deck](https://balatrogame.fandom.com/wiki/Checkered_Deck)
- [Balatro Wiki: Smeared Joker](https://balatrogame.fandom.com/wiki/Smeared_Joker)
- [Reddit: Gold Stake deck discussion](https://www.reddit.com/r/balatro/comments/1qh9rl4/how_i_rank_balatro_decks_at_gold_stake/)
- [GameStrategyHub: Gold Stake unlock guide](https://gamestrategyhub.com/games/balatro/guides/how-to-unlock-gold-stake-fast/)

