# Round Search Mathematics

## 1. Decision Problem

Inside a blind, the agent solves a finite-horizon stochastic control problem.

We write the round state as:

$$
s = (h, d, D, X, y, H, R)
$$

where:
- $h$ is the current hand,
- $d$ is the remaining draw pile,
- $D$ is the discard pile,
- $X$ is the current score already banked into the blind,
- $y$ is the target score,
- $H$ is hands left,
- $R$ is discards left.

An action $a$ is either:
- a playable subset of 1 to 5 cards, or
- a discard subset of 1 to 5 cards.

## 2. Transition Model

For a play action:

$$
T_{\text{play}}(s, a) \to s'
$$

does all of the following:
- computes the score of the selected subset,
- increments $X$,
- decrements $H$,
- moves played cards into the discard pile,
- refills the hand from the draw pile.

For a discard action:

$$
T_{\text{discard}}(s, a) \to s'
$$

does:
- decrements $R$,
- moves discarded cards into the discard pile,
- refills from the draw pile.

When the draw pile is empty, the solver can reshuffle the discard pile back into the deck for continued simulation.

## 3. Hybrid Fidelity Model

This repo now uses two fidelity tiers.

### Tier A: Exact root scoring

When the state is tractable and time budget allows it, the planner calls a JavaScript round solver backed by the open-source Balatro calculator. That gives much more faithful hand evaluation for:
- hand classification,
- scoring-card order,
- held-card effects,
- many Joker interactions,
- major modifier interactions.

### Tier B: Fast fallback search

When the exact solver is likely to time out, the planner falls back to Python. The Python fallback is faster but more approximate. It has still been upgraded in two important ways:
- discard rollouts now sample from the exact visible draw pile when available,
- discard candidate generation now explores a wider subset space instead of only low-card prefixes.

This is a standard multi-fidelity control pattern:

$$
V(s, a) \approx
\begin{cases}
V_{\text{exact}}(s, a), & \text{if latency budget allows} \\
V_{\text{fast}}(s, a), & \text{otherwise}
\end{cases}
$$

## 4. Root Action Evaluation

At the root, we evaluate a beam of candidate actions:
- top play actions ranked by exact immediate score,
- top discard actions ranked by discard desirability heuristics.

For each root action $a$, the solver runs Monte Carlo rollouts:

$$
\hat{V}(s, a) = \frac{1}{N} \sum_{i=1}^{N} U(\tau_i)
$$

where each trajectory $\tau_i$ is sampled from the draw process induced by the current remaining deck.

The root action score is risk-sensitive:

$$
\text{Score}(s,a) = \mathbb{E}[U(\tau)] + \lambda \cdot Q_{0.2}(U)
$$

where:
- $Q_{0.2}$ is the lower 20th percentile of rollout utility,
- $\lambda > 0$ is a conservative weight.

In code, this behaves like a soft CVaR-style penalty against brittle lines that spike high on average but collapse too often.

## 5. Utility Function

The rollout utility is designed around survival first:

$$
U =
\begin{cases}
B_{\text{clear}} + \alpha H + \beta R - \gamma \cdot \text{overkill}, & \text{if blind is cleared} \\
-B_{\text{fail}} + \eta \cdot \frac{X}{y} + \alpha' H + \beta' R, & \text{otherwise}
\end{cases}
$$

Interpretation:
- clearing the blind dominates the objective,
- leftover hands and discards are useful because they imply margin,
- excessive overkill is mildly penalized because it often corresponds to wasting resources,
- partial progress still matters in losing trajectories so the search prefers lines that remain live longer.

## 6. Variance Control

The JavaScript round solver uses seeded pseudo-randomness. Root actions are evaluated using the same base seed structure, which gives a crude common-random-numbers effect:

$$
\tau_i(a_1), \tau_i(a_2), \ldots
$$

share similar randomness across actions. That reduces noise in action ranking compared with using unrelated randomness for each candidate.

## 7. Why We Do Not Solve The Full Run Exactly

In principle, a full-run policy would solve:

$$
V^*(s) = \max_a \left( r(s,a) + \mathbb{E}[V^*(s')] \right)
$$

over:
- blind states,
- shop states,
- consumables,
- booster outcomes,
- Joker board changes,
- deck edits,
- stake-specific constraints.

That state space is far too large for exact dynamic programming under live mod latency. So the implementation uses:
- exact local scoring,
- stochastic lookahead for the current blind,
- heuristic but stake-aware shop control.

That is the core mathematical compromise in this repository.
