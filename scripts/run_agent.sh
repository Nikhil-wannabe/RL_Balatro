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
export AGENT_MC_ROLLOUTS=50
export AGENT_MC_SEED=42
export AGENT_MC_MIN_ROLLOUTS=6
export AGENT_MC_MAX_CANDIDATES=14
export AGENT_MC_REFINE_TOP_K=4
export AGENT_MC_CONFIDENCE_MULTIPLIER=1.5
export AGENT_TRACE_ENABLED=1
export AGENT_TRACE_DIR="logs"

# Run the Python server module
# Ensure your virtual environment is active if you use one!
python3 python/main.py
