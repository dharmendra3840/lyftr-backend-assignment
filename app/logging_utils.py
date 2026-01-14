from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


def utc_now_iso() -> str:
    # ISO-8601 UTC with Z
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_logger(name: str, level: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level.upper())
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))  # we log pre-serialized JSON
        logger.addHandler(handler)

    return logger


def log_json(logger: logging.Logger, level: int, payload: dict) -> None:
    # single-line JSON
    logger.log(level, json.dumps(payload, separators=(",", ":"), ensure_ascii=False))