from __future__ import annotations

import datetime
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)

_status: dict = {
    "status": "starting",
    "mode": "unknown",
    "last_cycle": None,
    "open_positions": 0,
    "scheduler_running": False,
}


def update_status(**kwargs) -> None:
    _status.update(kwargs)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            payload = json.dumps(_status, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress noisy HTTP logs


def start_health_server(port: int = 8080) -> threading.Thread:
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server started on port %d", port)
    return thread
