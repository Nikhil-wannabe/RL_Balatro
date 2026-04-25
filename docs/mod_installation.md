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

The bundled scripts also enable:
- structured logging in `logs/agent.log`,
- decision traces in `logs/decision_trace.jsonl`,
- deterministic state-seeded rollout search for discard planning.

## Step 6. Launch Balatro

1. Start Balatro normally.
2. Lovely should load `agent.lua`.
3. Start a run.
4. The mod should begin acting automatically during:
   - blind selection,
   - hand/discard turns,
   - round cash out,
   - supported shop decisions.

## Step 7. Verify the installation

Check all of the following:
- The Python terminal shows `Agent Server active on 127.0.0.1:12345`.
- The file `logs/agent.log` appears in the repository.
- The file `logs/decision_trace.jsonl` appears after the first in-game decision.
- Balatro does not stall on the first blind.

## Troubleshooting

- Game crashes on startup: validate `lovely.toml` syntax and make sure the file was copied exactly.
- Agent does nothing: confirm the Python server is already running before Balatro reaches an actionable phase.
- Connection refused: verify `agent.lua` and `config.py` still agree on `127.0.0.1:12345`.
- No exact solver: install Node.js or let the bot use the Python fallback.
- No logs created: check that `AGENT_TRACE_ENABLED=1` and that the repository is writable.

For the full runtime guide, see [running_the_agent.md](/C:/Users/nkris/OneDrive/Documents/RL_Balatro/docs/running_the_agent.md).
