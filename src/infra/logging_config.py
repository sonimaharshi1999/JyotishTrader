from __future__ import annotations

import logging
import sys
import uuid


def setup_logging(json_output: bool = False, level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_output:
        import json
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "cycle_id": getattr(record, "cycle_id", None),
                }
                if record.exc_info and record.exc_info[1]:
                    log_entry["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_entry)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


def generate_cycle_id() -> str:
    return uuid.uuid4().hex[:8]
