# Scoring Engine Design

The scoring pipeline explicitly aligns with Balatro's exact order of operations. It separates hand classification, subset determination, and effect triggering.

```mermaid
graph TD
    A[Determine Hand Type] --> B[Extract Scoring-Card Subset]
    B --> C[Fetch Base Chips/Mult]
    C --> D[Loop: SCORING Cards left-to-right]
    D --> E[Loop: Held in Hand Cards]
    E --> F[Loop: Jokers left-to-right]
    F --> G[Apply Deck Rules e.g. Plasma]
    G --> H[Final Score calculation]
```

## Critical Mechanisms
* **Chips × Mult**: Final score is the product of accumulated chips and multiplier.
* **Scoring Subset**: Only the cards forming the valid poker hand are scored. If you play a Pair alongside 3 unrelated cards, only the Pair cards trigger their base chips and enhancements.
* **Retriggers**: Currently implemented with placeholders, but structurally anticipated. A Red Seal card must retrigger exactly during the scoring card loop.
