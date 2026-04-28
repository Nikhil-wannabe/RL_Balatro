#!/bin/bash

echo "========================================"
echo "Starting Balatro Agent Server (Fast)"
echo "========================================"

cd "$(dirname "$0")/.."

export PYTHONPATH="python"
export AGENT_HOST="127.0.0.1"
export AGENT_PORT=12345
export AGENT_LOG_LEVEL="INFO"
export AGENT_ASYNC_SELECTING_HAND=1
export AGENT_SELECTING_HAND_TIME_BUDGET_MS=900
export AGENT_PLANNER_HEADROOM_MS=125
export AGENT_JS_ROUND_SOLVER_MIN_TIMEOUT_MS=250
export AGENT_MC_ROLLOUTS=24
export AGENT_MC_SEED=42
export AGENT_MC_MIN_ROLLOUTS=4
export AGENT_MC_MAX_CANDIDATES=10
export AGENT_MC_REFINE_TOP_K=3
export AGENT_MC_CONFIDENCE_MULTIPLIER=1.5
export AGENT_JS_ROUND_SOLVER=0
export AGENT_JS_ROUND_SOLVER_TIMEOUT_MS=600
export AGENT_TRACE_ENABLED=1
export AGENT_TRACE_DIR="logs"

python3 python/main.py
