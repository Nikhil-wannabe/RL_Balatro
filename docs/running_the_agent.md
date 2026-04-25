# Running the Balatro Agent

This is the fastest way to get the mod running end to end.

## Quickstart

1. Install Python 3.10+.
2. Install Node.js if you want the JavaScript round solver enabled. The agent still runs without it.
3. From the repository root, install dependencies and run tests.
4. Start the Python backend with one of the provided scripts.
5. Copy the Lua mod into your Balatro `Mods` folder and launch the game.

## 1. Prepare the Repository

**Windows PowerShell**
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="python"
python -m pytest tests/
```

**Linux/macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=python python3 -m pytest tests/
```

## 2. Start the Agent Backend

**Windows**
```powershell
.\scripts\run_agent.bat
```

**Linux/macOS**
```bash
./scripts/run_agent.sh
```

The backend listens on `127.0.0.1:12345` by default.

Expected startup output:

```text
========================================
Starting Balatro Agent Server
========================================
2026-04-25 19:00:00 | INFO    | Server   | === Agent Server active on 127.0.0.1:12345 ===
2026-04-25 19:00:00 | INFO    | Server   | Waiting for game connection...
```

## 3. Install the Lua Mod

Follow [mod_installation.md](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/mod_installation.md) to install `agent.lua` and `lovely.toml` with Lovely.

Once installed, the mod will hand control to the Python backend during these phases:
- `BLIND_SELECT`
- `SELECTING_HAND`
- `ROUND_EVAL`
- `SHOP`

## 4. Verify That It Is Working

After the first in-game decision, confirm that these files exist:
- `logs/agent.log`
- `logs/decision_trace.jsonl`

The JSONL trace is the main tuning artifact. Each row records:
- the summarized game state,
- the chosen action,
- the solver backend used,
- the top discard candidates,
- rollout counts, confidence margins, and seed information.

## 5. How Randomness Works Now

The runtime no longer depends on a single mutable RNG stream.

Instead:
- Python Monte Carlo rollouts use a seed derived from the live game state, round metadata, visible cards, jokers, and draw count.
- Candidates with the same draw count share the same rollout stream. This is a common-random-numbers setup, which makes comparisons less noisy.
- The planner evaluates many discard options with a small first-stage budget, then spends extra rollouts only on the close contenders.
- The JavaScript round solver uses the same approach: state-derived root seeds plus staged refinement for top root actions.

The practical result is that replaying the same state should reproduce the same action, even if the planner explores candidates in a different internal order.

## 6. Runtime Controls

These environment variables are the main tuning knobs:

- `AGENT_HOST` and `AGENT_PORT`: TCP endpoint used by the Lua mod.
- `AGENT_LOG_LEVEL`: `INFO` by default.
- `AGENT_MC_SEED`: base seed mixed into all stochastic search.
- `AGENT_MC_ROLLOUTS`: maximum refined rollout count for a promising discard line.
- `AGENT_MC_MIN_ROLLOUTS`: first-pass rollout count per discard candidate.
- `AGENT_MC_MAX_CANDIDATES`: cap on discard candidates considered in Python fallback search.
- `AGENT_MC_REFINE_TOP_K`: number of close discard candidates that receive extra rollouts.
- `AGENT_MC_CONFIDENCE_MULTIPLIER`: widens or narrows the uncertainty band used in diagnostics.
- `AGENT_TRACE_ENABLED`: enable structured JSONL traces.
- `AGENT_TRACE_DIR`: output directory for text logs and traces.
- `AGENT_JS_ROUND_SOLVER`: enable or disable the Node.js exact round solver.

The provided run scripts already set reasonable defaults.

## 7. Common Problems

- No response in game: make sure the backend is already running before Balatro reaches a playable phase.
- Connection refused: confirm that `lua/agent.lua` and the backend both use `127.0.0.1:12345`.
- No exact solver: install Node.js, or leave the JS solver disabled and let the Python fallback run.
- Slow decisions: reduce `AGENT_MC_ROLLOUTS` or `AGENT_MC_MAX_CANDIDATES`.
- No logs: ensure the repository is writable and `AGENT_TRACE_ENABLED=1`.

## 8. Recommended Workflow For Tuning

1. Run a real game.
2. Save `logs/decision_trace.jsonl`.
3. Filter for failed blinds, weak shop buys, or suspicious discard choices.
4. Compare the chosen line against nearby candidates and their rollout confidence margins.
5. Adjust heuristics or rollout budgets, then rerun.

For a step-by-step install guide, see [mod_installation.md](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/mod_installation.md).
