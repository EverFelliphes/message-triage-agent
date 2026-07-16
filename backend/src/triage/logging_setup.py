"""Structured JSON logging (BE-07).

structlog with a JSON renderer so every line is machine-parseable and carries a
``trace_id``. Two sinks: stdout (for ``docker logs`` / stdout capture) and a
persistent daily JSONL file under ``storage/logs`` so events survive the process.

Every line carries a timezone-aware ISO-8601 ``timestamp`` (local offset, e.g.
``-03:00``). Message *content* is never logged (LGPD) — only ids, lengths, the
stage/outcome, and timing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path

import structlog

# Set by ``configure_logging``; the file sink appends here. ``None`` disables it.
_LOG_FILE: Path | None = None


def _tz_timestamper(logger, method_name, event_dict):
    """Stamp a timezone-aware ISO-8601 timestamp (includes the UTC offset)."""
    event_dict["timestamp"] = datetime.now().astimezone().isoformat()
    return event_dict


def _persist_to_file(logger, method_name, event: str) -> str:
    """Append the rendered JSON line to the daily log file (best-effort).

    Runs last in the chain, so ``event`` is already the JSON string produced by
    ``JSONRenderer``. Logging must never break a request, so I/O errors are
    swallowed. Returns the line unchanged for the stdout sink.
    """
    if _LOG_FILE is not None:
        try:
            with _LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(event + "\n")
        except OSError:
            pass
    return event


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure structlog to emit tz-aware JSON to stdout and (optionally) a file.

    ``log_dir`` is created if missing; events go to ``events-YYYY-MM-DD.jsonl``.
    """
    global _LOG_FILE
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=lvl)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().astimezone().date().isoformat()
        _LOG_FILE = log_dir / f"events-{today}.jsonl"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _tz_timestamper,
            structlog.processors.JSONRenderer(),
            _persist_to_file,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
        cache_logger_on_first_use=True,
    )


def current_log_file() -> Path | None:
    """Path of the active daily log file, if a file sink is configured."""
    return _LOG_FILE


def new_trace_id() -> str:
    """Fresh request/classification trace id."""
    return uuid.uuid4().hex
