# Balatro Agent Testing Guide

This guide explains how to run the deterministic test suite for the Balatro AI agent and how to add new scenarios.

## Running the Tests

The tests are written in Python using the `pytest` framework. 

To run all tests, use the following command from the root directory of the project. We recommend setting the `PYTHONPATH` so imports resolve correctly:

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH="python"; python -m pytest tests/
```

**Linux/macOS/Git Bash:**
```bash
PYTHONPATH=python python3 -m pytest tests/
```

### What Tests Exist?

1. **Scenario Tests** (`tests/test_scenarios.py`):
   These feed fixed, deterministic game states into the Python `Planner` and assert that the returned action is logically correct.
   - `test_lethal_case`: Checks that an immediate clear is always preferred.
   - `test_desperation_discard`: Verifies that a discard is prioritized when the target is unreachable and only 1 hand remains.
   - `test_preserve_scaling_case`: Ensures that if a blind can be cleared efficiently (e.g., using a Pair instead of 5 cards), the agent prefers efficiency.
   - `test_deterministic_tie_breaking`: Verifies that if multiple equal actions exist, one is chosen consistently.
   - `test_mc_repeatability`: Checks that Monte Carlo evaluations yield identical choices under the same seed.
   - `test_no_hands_fallback`: Ensures a graceful NO_OP fallback when no hands remain.

2. **Integration Tests** (`tests/test_integration.py`):
   Validates the end-to-end `AgentServer` JSON payload parsing, ensuring that missing/bad fields don't crash the server and return a valid JSON `ERROR` action.

3. **Phase Tests** (`tests/test_phase_planner.py` and `tests/test_shop_planner.py`):
   Validate that non-hand phases remain autonomous:
   - blind select returns a valid blind action,
   - round evaluation cashes out,
   - the shop planner buys strong vouchers when affordable.

### What Does "Passing" Mean?

A test run is considered "passing" if all assertions succeed and the test suite exits with code `0`. 
This guarantees that:
- The core math and logic for evaluating cards doesn't throw exceptions.
- The `calculate_utility` weighting correctly balances immediate score vs survival probability.
- Server payload parsing matches the expected `BalatroState` schema.
- The phase router continues to produce executable actions outside the hand-playing phase.

## Adding a New Scenario Test

When you encounter a bug or an edge case where the agent makes a questionable decision, you should capture the state and add it as a deterministic scenario.

1. Open `tests/test_scenarios.py`.
2. Create a new test function starting with `test_`.
3. Call `state = create_base_state()` to get a standard mock state.
4. Modify the `state` object (e.g., set `state.blind.target_score`, modify `state.economy.hands_left`, or populate `state.hand` with specific `Card` objects).
5. Instantiate `Planner()`.
6. Call `action = planner.plan_action(state)`.
7. Assert on `action.action` and `action.cards`.

**Example:**
```python
def test_new_edge_case():
    state = create_base_state()
    state.blind.target_score = 500
    # ... setup state.hand ...
    
    planner = Planner()
    action = planner.plan_action(state)
    
    assert action.action == "PLAY_HAND"
    assert "c1" in action.cards
```
