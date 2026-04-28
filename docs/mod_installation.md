# Installing the Balatro Agent Mod with Lovely

This guide explains how to install the Lua portion of the agent into Balatro using the **Lovely** mod loader. The result is a live autoplayer that sends game state to the Python server and receives back executable actions.

## Prerequisites

1. A legal copy of Balatro.
2. Python 3.10+ installed.
3. Node.js installed if you want the exact JavaScript round solver enabled.
4. Lovely installed.
   - Download Lovely from the [Lovely GitHub releases page](https://github.com/ethangreen-dev/lovely-injector/releases).
   - Follow the release instructions so Balatro loads Lovely when it starts.

## Step 1. Verify the repository locally

From this project directory:

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

## Step 2. Locate the Balatro Mods folder

Typical locations:
- Windows: `%AppData%\Balatro\Mods\`
- macOS: `~/Library/Application Support/Balatro/Mods/`
- Linux: `~/.steam/steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/`

If `Mods` does not exist, create it after Lovely is installed.

## Step 3. Create the mod folder

Create:

```text
%AppData%\Balatro\Mods\AgentMod\
```

## Step 4. Copy the Lua files

Copy these two files from the repository:
- `lua/agent.lua`
- `lua/lovely.toml`

into the folder above so the final structure is:

```text
Balatro/
  Mods/
    AgentMod/
      agent.lua
      lovely.toml
```

If you already installed an older version of this mod, overwrite both files in `%AppData%\Balatro\Mods\AgentMod\`. Do not update only `agent.lua` or only `lovely.toml`; they are meant to ship together.

## Step 5. Start the Python backend

From the repository root:

**Windows**
```powershell
.\scripts\run_agent.bat
```

**Linux/macOS**
```bash
./scripts/run_agent.sh
```

This launches the local TCP server on `127.0.0.1:12345`.

The default launcher is quality-first. It enables:
- structured logging in `logs/agent.log`,
- decision traces in `logs/decision_trace.jsonl`,
- deterministic state-seeded rollout search for discard planning,
- deeper Monte Carlo and JavaScript round search budgets,
- asynchronous hand planning so the game keeps rendering while the backend searches.

If you prefer a lower-latency profile, use:
- `.\scripts\run_agent_fast.bat`
- `./scripts/run_agent_fast.sh`

## Step 6. Launch Balatro

1. Start Balatro normally.
2. Lovely should load `agent.lua`.
3. At the main menu, choose `Continue` or start a run yourself.
4. Once a run reaches gameplay, the mod acts automatically during:
   - blind selection,
   - hand/discard turns,
   - round cash out,
   - supported shop decisions.

Lovely should now report `Applied 1 patch to 'game.lua'` for this mod. If you still see `Applied 2 patches to 'game.lua'`, the installed `lovely.toml` is from an older build and should be replaced with the current one from this repository.

## Step 7. Verify the installation

Check all of the following:
- The Python terminal shows `Agent Server active on 127.0.0.1:12345`.
- The file `logs/agent.log` appears in the repository.
- The file `logs/decision_trace.jsonl` appears after the first in-game decision.
- Balatro does not stall on the first blind.
- After clearing a blind, the game proceeds into round evaluation without crashing on `round_eval`.

## Troubleshooting

- Game crashes on startup: validate `lovely.toml` syntax and make sure the file was copied exactly.
- Error mentions `missing field match_indent`: your installed `lovely.toml` is from an older broken build. Recopy both `lua/agent.lua` and `lua/lovely.toml` from this repository into `%AppData%\Balatro\Mods\AgentMod\`.
- Agent does nothing: confirm the Python server is already running before Balatro reaches an actionable phase.
- The menu appears but the run does not start: fully close Balatro, overwrite `%AppData%\Balatro\Mods\AgentMod\agent.lua` from this repo, restart the backend, then relaunch Balatro.
- The game pauses briefly but does not act yet: in quality mode this can be normal. The server may answer with temporary `NO_OP` responses while a deeper hand search is still running in the background.
- Connection refused: verify `agent.lua` and `config.py` still agree on `127.0.0.1:12345`.
- No exact solver: install Node.js or let the bot use the Python fallback.
- No logs created: check that `AGENT_TRACE_ENABLED=1` and that the repository is writable.
- Actions feel too slow: lower `AGENT_SELECTING_HAND_TIME_BUDGET_MS` or use `run_agent_fast`.
- Blind selection fails after the shop: make sure you copied the latest `agent.lua`; newer builds resolve blinds through `G.GAME.round_resets.blind_choices` instead of guessing blind keys.

For the full runtime guide, see [running_the_agent.md](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/running_the_agent.md).
