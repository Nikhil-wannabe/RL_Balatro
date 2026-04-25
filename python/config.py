import os


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value not in {"0", "false", "False", "no", "No"}


class Config:
    HOST = os.getenv("AGENT_HOST", "127.0.0.1")
    PORT = int(os.getenv("AGENT_PORT", 12345))
    LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO")
    PROTOCOL_VERSION = "1.0.0"
    MC_ROLLOUTS = int(os.getenv("AGENT_MC_ROLLOUTS", 50))
    MC_SEED = int(os.getenv("AGENT_MC_SEED", 42))
    MC_MIN_ROLLOUTS = int(os.getenv("AGENT_MC_MIN_ROLLOUTS", 6))
    MC_MAX_CANDIDATES = int(os.getenv("AGENT_MC_MAX_CANDIDATES", 14))
    MC_REFINE_TOP_K = int(os.getenv("AGENT_MC_REFINE_TOP_K", 4))
    MC_CONFIDENCE_MULTIPLIER = float(os.getenv("AGENT_MC_CONFIDENCE_MULTIPLIER", 1.5))

    WEIGHT_SURVIVAL = float(os.getenv("AGENT_WEIGHT_SURVIVAL", 10000.0))
    WEIGHT_PRESERVATION = float(os.getenv("AGENT_WEIGHT_PRESERVATION", 50.0))
    WEIGHT_EFFICIENCY = float(os.getenv("AGENT_WEIGHT_EFFICIENCY", 10.0))
    WEIGHT_RISK = float(os.getenv("AGENT_WEIGHT_RISK", -5.0))
    WEIGHT_OVERKILL = float(os.getenv("AGENT_WEIGHT_OVERKILL", -2.0))
    WEIGHT_FUTURE = float(os.getenv("AGENT_WEIGHT_FUTURE", 20.0))
    JS_ROUND_SOLVER = os.getenv("AGENT_JS_ROUND_SOLVER", "1") not in {"0", "false", "False"}
    JS_ROUND_SOLVER_TIMEOUT_MS = int(os.getenv("AGENT_JS_ROUND_SOLVER_TIMEOUT_MS", 1500))
    JS_ROUND_SOLVER_SAMPLES = int(os.getenv("AGENT_JS_ROUND_SOLVER_SAMPLES", 96))
    JS_ROUND_SOLVER_BEAM = int(os.getenv("AGENT_JS_ROUND_SOLVER_BEAM", 18))
    NODE_BIN = os.getenv("AGENT_NODE_BIN", "node")
    TRACE_ENABLED = _env_flag("AGENT_TRACE_ENABLED", True)
    TRACE_INCLUDE_STATE = _env_flag("AGENT_TRACE_INCLUDE_STATE", True)
    TRACE_INCLUDE_CANDIDATES = _env_flag("AGENT_TRACE_INCLUDE_CANDIDATES", True)
    TRACE_DIR = os.getenv("AGENT_TRACE_DIR", "logs")
    TEXT_LOG_FILE = os.getenv("AGENT_TEXT_LOG_FILE", "agent.log")
    TRACE_JSONL_FILE = os.getenv("AGENT_TRACE_JSONL_FILE", "decision_trace.jsonl")

config = Config()
