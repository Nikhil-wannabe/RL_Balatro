import json
import subprocess
from pathlib import Path
from typing import Optional

from action_types import ActionResponse
from config import config
from logging_utils import get_logger
from state import BalatroState

logger = get_logger("JSSolver")


class JSRoundSolver:
    def __init__(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.script_path = self.repo_root / "scripts" / "balatro_round_solver.js"
        self.last_diagnostics = None
        self.last_failure = None

    def is_available(self) -> bool:
        return config.JS_ROUND_SOLVER and self.script_path.exists()

    def solve(self, state: BalatroState, *, timeout_ms: Optional[int] = None) -> Optional[ActionResponse]:
        self.last_diagnostics = None
        self.last_failure = None
        if not self.is_available():
            return None
        remaining_target = state.blind.target_score - state.blind.current_score
        if remaining_target > 2000 and not state.deck:
            self.last_failure = "skipped_large_target_without_exact_deck"
            return None

        payload = state.model_dump()
        cmd = [
            config.NODE_BIN,
            str(self.script_path),
            "--samples",
            str(config.JS_ROUND_SOLVER_SAMPLES),
            "--beam",
            str(config.JS_ROUND_SOLVER_BEAM),
        ]
        effective_timeout_ms = timeout_ms if timeout_ms is not None else config.JS_ROUND_SOLVER_TIMEOUT_MS

        try:
            result = subprocess.run(
                cmd,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=max(0.2, effective_timeout_ms / 1000.0),
                cwd=self.repo_root,
                check=False,
            )
        except FileNotFoundError:
            logger.warning("Node runtime '%s' was not found; falling back to Python planner.", config.NODE_BIN)
            self.last_failure = "node_missing"
            return None
        except subprocess.TimeoutExpired:
            logger.warning("JS round solver timed out after %sms; falling back to Python planner.", effective_timeout_ms)
            self.last_failure = "timeout"
            return None
        except Exception as exc:
            logger.warning("JS round solver failed unexpectedly: %s", exc)
            self.last_failure = f"exception:{exc}"
            return None

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                logger.warning("JS round solver exited with code %s: %s", result.returncode, stderr)
            self.last_failure = f"exit_code:{result.returncode}"
            return None

        stdout = result.stdout.strip()
        if not stdout:
            logger.warning("JS round solver returned no output.")
            self.last_failure = "no_output"
            return None

        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and "diagnostics" in data:
                self.last_diagnostics = data.get("diagnostics")
            if isinstance(data, dict) and "action" in data:
                return ActionResponse(
                    action=data["action"],
                    cards=data.get("cards"),
                    target_id=data.get("target_id"),
                    message=data.get("message"),
                )
            return ActionResponse(**data)
        except Exception as exc:
            logger.warning("Failed to parse JS round solver output: %s | raw=%r", exc, stdout[:400])
            self.last_failure = "parse_error"
            return None
