import socket
import json
from state import BalatroState
from planner import Planner
from action_types import ActionResponse
from config import config
from logging_utils import get_logger

logger = get_logger("Server")

class AgentServer:
    def __init__(self):
        self.planner = Planner()
        
    def handle_request(self, data: str) -> str:
        try:
            raw_json = json.loads(data)
            
            if "meta" not in raw_json or raw_json["meta"].get("protocol_version") != config.PROTOCOL_VERSION:
                logger.warning("Protocol version mismatch or missing.")
                
            state = BalatroState(**raw_json)
            logger.info(f"[Server] Received State | Blind: {state.blind.name} | Score: {state.blind.current_score}/{state.blind.target_score} | Hand: {len(state.hand)} cards")
            
            action = self.planner.plan_action(state)
            
            logger.info(f"[Server] Sending Action: {action.action}")
            return action.model_dump_json()
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
