#!/bin/bash

echo "========================================"
echo "Starting Balatro Agent Server"
echo "========================================"

# Change directory to the project root (parent of the scripts directory)
cd "$(dirname "$0")/.."

# Set environment variables for the agent configuration
export PYTHONPATH="python"
export AGENT_HOST="127.0.0.1"
export AGENT_PORT=12345
export AGENT_LOG_LEVEL="INFO"
export AGENT_ASYNC_SELECTING_HAND=1
export AGENT_SELECTING_HAND_TIME_BUDGET_MS=12000
export AGENT_PLANNER_HEADROOM_MS=200
export AGENT_EARLY_GAME_ANTE_CUTOFF=3
export AGENT_JS_ROUND_SOLVER_MIN_TIMEOUT_MS=300
export AGENT_JS_ROUND_SOLVER_MIN_ANTE=1
export AGENT_MC_ROLLOUTS=96
export AGENT_MC_SEED=42
export AGENT_MC_MIN_ROLLOUTS=10
export AGENT_MC_MAX_CANDIDATES=18
export AGENT_MC_REFINE_TOP_K=5
export AGENT_MC_CONFIDENCE_MULTIPLIER=1.5
export AGENT_JS_ROUND_SOLVER=1
export AGENT_JS_ROUND_SOLVER_TIMEOUT_MS=9000
export AGENT_JS_ROUND_SOLVER_SAMPLES=256
export AGENT_JS_ROUND_SOLVER_BEAM=32
export AGENT_PARALLEL_JS_AND_PYTHON=1
export AGENT_PARALLEL_CANDIDATE_EVAL=1
export AGENT_PARALLEL_WORKERS=6
export AGENT_TRACE_ENABLED=1
export AGENT_TRACE_DIR="logs"

# Run the Python server module
# Ensure your virtual environment is active if you use one!
python3 python/main.py
