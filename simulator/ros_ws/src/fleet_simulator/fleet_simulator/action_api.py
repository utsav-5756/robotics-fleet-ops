"""Internal HTTP adapter for one allowlisted simulated action."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, Callable


class SimulatorActionServer:
    """Expose a tiny action endpoint on the Compose-only network."""

    def __init__(
        self,
        host: str,
        port: int,
        action_handler: Callable[[dict[str, Any]], tuple[int, dict[str, Any]]],
    ) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/v1/actions/reconnect":
                    self._reply(404, {"accepted": False, "message": "Unknown action path."})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 1 or length > 4096:
                        self._reply(400, {"accepted": False, "message": "Invalid request size."})
                        return
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("Expected a JSON object.")
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._reply(400, {"accepted": False, "message": "Invalid JSON request."})
                    return
                status_code, result = action_handler(payload)
                self._reply(status_code, result)

            def do_GET(self) -> None:
                self._reply(405, {"accepted": False, "message": "Method not allowed."})

            def _reply(self, status_code: int, body: dict[str, Any]) -> None:
                encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.thread = Thread(
            target=self.server.serve_forever,
            name="simulator-action-api",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)