import socket
import json
import threading
import time
from typing import Callable, Optional
from state import BalatroState
from planner import Planner
from action_types import ActionResponse
from config import config
from logging_utils import get_logger

logger = get_logger("Server")

class AgentServer:
    def __init__(self, *, planner_factory: Optional[Callable[[], Planner]] = None, async_selecting_hand: Optional[bool] = None):
        self._planner_factory = planner_factory or Planner
        self.planner = self._planner_factory()
        self.async_selecting_hand = config.ASYNC_SELECTING_HAND if async_selecting_hand is None else async_selecting_hand
        self._last_request_data = None
        self._last_response_json = None
        self._last_response_meta = None
        self._pending_request_data = None
        self._pending_response_json = None
        self._pending_response_meta = None
        self._pending_started_at = None
        self._pending_thread = None
        self._pending_log_at = 0.0
        self._lock = threading.Lock()

    def _no_op_response(self, message: str) -> str:
        return ActionResponse(action="NO_OP", message=message).model_dump_json()

    def _clear_pending_unlocked(self) -> None:
        self._pending_request_data = None
        self._pending_response_json = None
        self._pending_response_meta = None
        self._pending_started_at = None
        self._pending_thread = None
        self._pending_log_at = 0.0

    def _run_async_plan(self, request_data: str, state: BalatroState) -> None:
        started_at = time.perf_counter()
        try:
            planner = self._planner_factory()
            action = planner.plan_action(state)
            response_json = action.model_dump_json()
            result_meta = {
                "phase": state.meta.phase,
                "blind": state.blind.name,
                "action": action.action,
                "latency_s": time.perf_counter() - started_at,
            }
        except Exception as exc:
            logger.error("[Server] Background planner error: %s", exc, exc_info=True)
            response_json = ActionResponse(action="ERROR", message=str(exc)).model_dump_json()
            result_meta = {
                "phase": state.meta.phase,
                "blind": state.blind.name,
                "action": "ERROR",
                "latency_s": time.perf_counter() - started_at,
            }

        with self._lock:
            if self._pending_request_data == request_data:
                self._pending_response_json = response_json
                self._pending_response_meta = result_meta

    def _maybe_return_cached_response(self, data: str) -> Optional[str]:
        if data == self._last_request_data and self._last_response_json is not None:
            if self._last_response_meta:
                logger.info(
                    "[Server] Cache hit | Phase: %s | Blind: %s | Cached action: %s | Last latency: %.3fs",
                    self._last_response_meta.get("phase"),
                    self._last_response_meta.get("blind"),
                    self._last_response_meta.get("action"),
                    self._last_response_meta.get("latency_s", 0.0),
                )
            return self._last_response_json
        return None

    def _handle_async_selecting_hand(self, data: str, state: BalatroState) -> str:
        cached = self._maybe_return_cached_response(data)
        if cached is not None:
            return cached

        with self._lock:
            if self._pending_request_data == data:
                if self._pending_response_json is not None:
                    response_json = self._pending_response_json
                    response_meta = self._pending_response_meta or {
                        "phase": state.meta.phase,
                        "blind": state.blind.name,
                        "action": "UNKNOWN",
                        "latency_s": 0.0,
                    }
                    self._last_request_data = data
                    self._last_response_json = response_json
                    self._last_response_meta = response_meta
                    self._clear_pending_unlocked()
                    logger.info(
                        "[Server] Async result ready | Phase: %s | Blind: %s | Action: %s | Latency: %.3fs",
                        response_meta.get("phase"),
                        response_meta.get("blind"),
                        response_meta.get("action"),
                        response_meta.get("latency_s", 0.0),
                    )
                    return response_json

                now = time.perf_counter()
                if now - self._pending_log_at >= 1.0:
                    logger.info(
                        "[Server] Planning pending | Phase: %s | Blind: %s | Elapsed: %.3fs",
                        state.meta.phase,
                        state.blind.name,
                        now - (self._pending_started_at or now),
                    )
                    self._pending_log_at = now
                return self._no_op_response("planning_pending")

            if self._pending_thread is not None and self._pending_thread.is_alive():
                now = time.perf_counter()
                if now - self._pending_log_at >= 1.0:
                    logger.info(
                        "[Server] Planner busy on previous state; yielding NO_OP | New blind: %s | Elapsed: %.3fs",
                        state.blind.name,
                        now - (self._pending_started_at or now),
                    )
                    self._pending_log_at = now
                return self._no_op_response("planner_busy")

            self._clear_pending_unlocked()
            self._pending_request_data = data
            self._pending_started_at = time.perf_counter()
            self._pending_thread = threading.Thread(
                target=self._run_async_plan,
                args=(data, state),
                daemon=True,
            )
            self._pending_thread.start()

        logger.info(
            "[Server] Async planning started | Phase: %s | Blind: %s | Budget: %sms",
            state.meta.phase,
            state.blind.name,
            config.SELECTING_HAND_TIME_BUDGET_MS,
        )
        return self._no_op_response("planning_started")
        
    def handle_request(self, data: str) -> str:
        try:
            cached = self._maybe_return_cached_response(data)
            if cached is not None:
                return cached

            started_at = time.perf_counter()
            raw_json = json.loads(data)
            
            if "meta" not in raw_json or raw_json["meta"].get("protocol_version") != config.PROTOCOL_VERSION:
                logger.warning("Protocol version mismatch or missing.")
                
            state = BalatroState(**raw_json)
            phase = (state.meta.phase or "").upper()
            if self.async_selecting_hand and phase == "SELECTING_HAND":
                return self._handle_async_selecting_hand(data, state)
            logger.info(f"[Server] Received State | Blind: {state.blind.name} | Score: {state.blind.current_score}/{state.blind.target_score} | Hand: {len(state.hand)} cards")
            
            action = self.planner.plan_action(state)
            latency_s = time.perf_counter() - started_at
            
            logger.info("[Server] Sending Action: %s | Latency: %.3fs", action.action, latency_s)
            response_json = action.model_dump_json()
            self._last_request_data = data
            self._last_response_json = response_json
            self._last_response_meta = {
                "phase": state.meta.phase,
                "blind": state.blind.name,
                "action": action.action,
                "latency_s": latency_s,
            }
            return response_json
        except json.JSONDecodeError as e:
            logger.error(f"[Server] Malformed JSON payload received: {e}")
            return ActionResponse(action="ERROR", message="Malformed JSON").model_dump_json()
        except Exception as e:
            logger.error(f"[Server] Error handling request: {e}", exc_info=True)
            return ActionResponse(action="ERROR", message=str(e)).model_dump_json()

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((config.HOST, config.PORT))
            s.listen()
            logger.info(f"=== Agent Server active on {config.HOST}:{config.PORT} ===")
            logger.info("Waiting for game connection...")
            
            while True:
                try:
                    conn, addr = s.accept()
                    with conn:
                        data = b""
                        while True:
                            chunk = conn.recv(8192)
                            if not chunk: break
                            data += chunk
                            if b'\n' in chunk: break
                        
                        if data:
                            decoded = data.decode('utf-8').strip()
                            response = self.handle_request(decoded)
                            # Ensure we append a newline so lua socket.receive("*l") triggers
                            conn.sendall((response + "\n").encode('utf-8'))
                except Exception as e:
                    logger.error(f"[Server] Socket error: {e}", exc_info=True)
