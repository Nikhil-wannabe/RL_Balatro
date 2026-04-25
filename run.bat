@echo off
echo Starting Balatro Agent Server...
cd python
pip install -r ../requirements.txt
set AGENT_TRACE_ENABLED=1
set AGENT_TRACE_DIR=..\logs
python main.py
pause
