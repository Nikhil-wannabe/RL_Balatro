# Logging and Tuning

This project now writes two kinds of logs by default into the `logs/` folder at the repository root.

## 1. Human-readable run log

File:
- `logs/agent.log`

This mirrors the normal console output and is useful for quickly reading what the agent did during a run.

## 2. Structured decision trace

File:
- `logs/decision_trace.jsonl`

This is the important tuning artifact. It writes one JSON object per decision and includes:
- phase,
- blind and economy summary,
- current hand/deck/discard summaries,
- Joker summary,
- inferred strategy/archetype posterior,
- solver backend used,
- chosen action,
- candidate diagnostics where available.

For the Python fallback planner, the trace includes:
- tactical mode,
- estimated clear probability,
- top ranked play/discard candidates,
- discard rollout statistics.

For the JavaScript exact round solver, the trace includes:
- top immediate plays,
- rollout search options,
- risk-adjusted root candidate evaluations,
- chosen line.

## Environment Variables

These are the main logging controls:

- `AGENT_TRACE_ENABLED=1`
- `AGENT_TRACE_DIR=logs`
- `AGENT_TRACE_INCLUDE_STATE=1`
- `AGENT_TRACE_INCLUDE_CANDIDATES=1`
- `AGENT_LOG_LEVEL=INFO`

## Recommended Tuning Workflow

1. Run the bot for real games and keep the generated `decision_trace.jsonl`.
2. Filter for losses, especially Gold Stake losses.
3. Group failures by:
   - phase,
   - boss blind,
   - inferred archetype,
   - shop miss,
   - exact-solver fallback,
   - economy collapse.
4. Compare winning and losing traces to identify:
   - bad buys,
   - over-aggressive rerolls,
   - weak pivots,
   - late-game solver timeouts,
   - strategy posterior mistakes.
5. Convert repeated failure patterns into:
   - new unit tests,
   - new shop/archetype features,
   - tighter solver thresholds.

## Practical Note

The trace file includes raw serialized state by default because it is much more useful for debugging. If the file size becomes too large, set:

**Windows PowerShell**
```powershell
$env:AGENT_TRACE_INCLUDE_STATE="0"
```

**Linux/macOS**
```bash
export AGENT_TRACE_INCLUDE_STATE=0
```
