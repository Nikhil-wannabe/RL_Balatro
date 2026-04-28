import os


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value not in {"0", "false", "False", "no", "No"}


class Config:
    CPU_COUNT = max(1, os.cpu_count() or 1)
    HOST = os.getenv("AGENT_HOST", "127.0.0.1")
    PORT = int(os.getenv("AGENT_PORT", 12345))
    LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO")
    PROTOCOL_VERSION = "1.0.0"
    ASYNC_SELECTING_HAND = _env_flag("AGENT_ASYNC_SELECTING_HAND", True)
    SELECTING_HAND_TIME_BUDGET_MS = int(os.getenv("AGENT_SELECTING_HAND_TIME_BUDGET_MS", 4500))
    PLANNER_HEADROOM_MS = int(os.getenv("AGENT_PLANNER_HEADROOM_MS", 150))
    EARLY_GAME_ANTE_CUTOFF = int(os.getenv("AGENT_EARLY_GAME_ANTE_CUTOFF", 2))
    JS_ROUND_SOLVER_MIN_ANTE = int(os.getenv("AGENT_JS_ROUND_SOLVER_MIN_ANTE", 3))
    JS_ROUND_SOLVER_MIN_TIMEOUT_MS = int(os.getenv("AGENT_JS_ROUND_SOLVER_MIN_TIMEOUT_MS", 250))
    MC_ROLLOUTS = int(os.getenv("AGENT_MC_ROLLOUTS", 50))
    MC_SEED = int(os.getenv("AGENT_MC_SEED", 42))
    MC_MIN_ROLLOUTS = int(os.getenv("AGENT_MC_MIN_ROLLOUTS", 6))
    MC_MAX_CANDIDATES = int(os.getenv("AGENT_MC_MAX_CANDIDATES", 14))
    MC_REFINE_TOP_K = int(os.getenv("AGENT_MC_REFINE_TOP_K", 4))
    MC_CONFIDENCE_MULTIPLIER = float(os.getenv("AGENT_MC_CONFIDENCE_MULTIPLIER", 1.5))
    MC_STAGE_A_ROLLOUTS = int(os.getenv("AGENT_MC_STAGE_A_ROLLOUTS", 12))
    MC_STAGE_B_ROLLOUTS = int(os.getenv("AGENT_MC_STAGE_B_ROLLOUTS", 24))
    MC_STAGE_C_ROLLOUTS = int(os.getenv("AGENT_MC_STAGE_C_ROLLOUTS", 48))
    MC_RARE_EVENT_THRESHOLD = float(os.getenv("AGENT_MC_RARE_EVENT_THRESHOLD", 0.25))
    MC_IS_MIXTURE_EPSILON = float(os.getenv("AGENT_MC_IS_MIXTURE_EPSILON", 0.35))
    MC_MIN_ESS_RATIO = float(os.getenv("AGENT_MC_MIN_ESS_RATIO", 0.35))
    EXACT_DRAW_ENUM_CAP = int(os.getenv("AGENT_EXACT_DRAW_ENUM_CAP", 40000))
    EXACT_STATE_CAP = int(os.getenv("AGENT_EXACT_STATE_CAP", 150000))
    EXACT_CATEGORY_CAP = int(os.getenv("AGENT_EXACT_CATEGORY_CAP", 14))
    EXACT_MAX_CANDIDATES = int(os.getenv("AGENT_EXACT_MAX_CANDIDATES", 4))
    EXACT_PARALLEL_MIN_STATES = int(os.getenv("AGENT_EXACT_PARALLEL_MIN_STATES", 192))
    RISK_ALPHA = float(os.getenv("AGENT_RISK_ALPHA", 0.10))
    REGRET_EPSILON = float(os.getenv("AGENT_REGRET_EPSILON", 0.01))
    TACTICAL_GAMMA_BASE = float(os.getenv("AGENT_TACTICAL_GAMMA_BASE", 0.94))
    TACTICAL_GAMMA_BOSS_BONUS = float(os.getenv("AGENT_TACTICAL_GAMMA_BOSS_BONUS", 0.02))
    TACTICAL_GAMMA_HIGH_STAKE_BONUS = float(os.getenv("AGENT_TACTICAL_GAMMA_HIGH_STAKE_BONUS", 0.01))

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
    PARALLEL_JS_AND_PYTHON = _env_flag("AGENT_PARALLEL_JS_AND_PYTHON", True)
    PARALLEL_CANDIDATE_EVAL = _env_flag("AGENT_PARALLEL_CANDIDATE_EVAL", True)
    PARALLEL_WORKERS = int(os.getenv("AGENT_PARALLEL_WORKERS", min(8, max(2, CPU_COUNT - 1))))
    PARALLEL_PLAY_MIN_TASKS = int(os.getenv("AGENT_PARALLEL_PLAY_MIN_TASKS", 18))
    PARALLEL_DISCARD_MIN_TASKS = int(os.getenv("AGENT_PARALLEL_DISCARD_MIN_TASKS", 4))
    NODE_BIN = os.getenv("AGENT_NODE_BIN", "node")
    TRACE_ENABLED = _env_flag("AGENT_TRACE_ENABLED", True)
    TRACE_INCLUDE_STATE = _env_flag("AGENT_TRACE_INCLUDE_STATE", True)
    TRACE_INCLUDE_CANDIDATES = _env_flag("AGENT_TRACE_INCLUDE_CANDIDATES", True)
    TRACE_DIR = os.getenv("AGENT_TRACE_DIR", "logs")
    TEXT_LOG_FILE = os.getenv("AGENT_TEXT_LOG_FILE", "agent.log")
    TRACE_JSONL_FILE = os.getenv("AGENT_TRACE_JSONL_FILE", "decision_trace.jsonl")

config = Config()
