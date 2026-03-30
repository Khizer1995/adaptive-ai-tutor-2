import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional


LOG_DIR = "logs"


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str, filename: str) -> logging.Logger:
    _ensure_log_dir()
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler(os.path.join(LOG_DIR, filename), encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_jsonl(filename: str, payload: Dict[str, Any]) -> None:
    _ensure_log_dir()
    payload = dict(payload)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = os.path.join(LOG_DIR, filename)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def trace_event(event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    log_jsonl(
        "langgraph_trace.jsonl",
        {
            "event": event_type,
            "payload": payload or {},
        },
    )


class Timer:
    def __init__(self):
        self.start = perf_counter()

    def elapsed_ms(self) -> float:
        return (perf_counter() - self.start) * 1000.0
