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
set AGENT_MC_ROLLOUTS=50
set AGENT_MC_SEED=42
set AGENT_MC_MIN_ROLLOUTS=6
set AGENT_MC_MAX_CANDIDATES=14
set AGENT_MC_REFINE_TOP_K=4
set AGENT_MC_CONFIDENCE_MULTIPLIER=1.5
set AGENT_TRACE_ENABLED=1
set AGENT_TRACE_DIR=logs

:: Run the Python server module
:: Ensure your virtual environment is active if you use one!
python python/main.py
endlocal
