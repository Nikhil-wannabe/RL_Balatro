# Balatro Mod-Assisted AI Agent

A deterministic Balatro autoplayer that combines:
- a Lua mod bridge for live game control,
- a Python coordinator for phase routing and shop decisions,
- a hybrid search stack for hand/discard play,
- mathematical documentation for the search model.

## Repository Layout
- `lua/`: Lovely mod files. Deploy to `%APPDATA%/Balatro/Mods/`.
- `python/`: Core decision engine. Run `run.bat` to boot.
- `tests/`: Pytest suite for deterministic logic.
- `mathematics documentation/`: research notes and mathematical design docs.
- `docs/`: practical installation, runtime, and tuning guides.
- `docs-site/`: Docusaurus documentation.
- `examples/`: JSON representations of game states for debugging.
- `_third_party/balatro-calculator/`: vendored high-fidelity scoring engine used by the exact round solver.

## Usage
1. Place `lua/` contents in Steam Balatro Mods folder.
2. Run `scripts/run_agent.bat` or `scripts/run_agent.sh` for the quality-first server profile.
   Use `scripts/run_agent_fast.bat` or `scripts/run_agent_fast.sh` if you want lower latency instead.
3. Open Balatro. The agent will autonomously:
   - select blinds,
   - play and discard cards,
   - cash out after rounds,
   - make basic shop purchases and rerolls.
4. Inspect `logs/decision_trace.jsonl` after runs to tune the algorithm.

Practical setup guides:
- [Running the Agent](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/running_the_agent.md)
- [Mod Installation](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/mod_installation.md)
- [Work Done So Far](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/work_done/README.md)
