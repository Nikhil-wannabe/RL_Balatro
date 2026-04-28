@echo off
setlocal

echo ========================================
echo Starting Balatro Agent Server
echo ========================================

:: Change directory to the project root (parent of the scripts directory)
cd /d "%~dp0\.."

:: Set environment variables for the agent configuration
set PYTHONPATH=python
set AGENT_HOST=127.0.0.1
set AGENT_PORT=12345
set AGENT_LOG_LEVEL=INFO
set AGENT_ASYNC_SELECTING_HAND=1
set AGENT_SELECTING_HAND_TIME_BUDGET_MS=12000
set AGENT_PLANNER_HEADROOM_MS=200
set AGENT_EARLY_GAME_ANTE_CUTOFF=3
set AGENT_JS_ROUND_SOLVER_MIN_TIMEOUT_MS=300
set AGENT_JS_ROUND_SOLVER_MIN_ANTE=1
set AGENT_MC_ROLLOUTS=96
set AGENT_MC_SEED=42
set AGENT_MC_MIN_ROLLOUTS=10
set AGENT_MC_MAX_CANDIDATES=18
set AGENT_MC_REFINE_TOP_K=5
set AGENT_MC_CONFIDENCE_MULTIPLIER=1.5
set AGENT_JS_ROUND_SOLVER=1
set AGENT_JS_ROUND_SOLVER_TIMEOUT_MS=9000
set AGENT_JS_ROUND_SOLVER_SAMPLES=256
set AGENT_JS_ROUND_SOLVER_BEAM=32
set AGENT_PARALLEL_JS_AND_PYTHON=1
set AGENT_PARALLEL_CANDIDATE_EVAL=1
set AGENT_PARALLEL_WORKERS=6
set AGENT_TRACE_ENABLED=1
set AGENT_TRACE_DIR=logs

:: Run the Python server module
:: Ensure your virtual environment is active if you use one!
python python/main.py
endlocal
