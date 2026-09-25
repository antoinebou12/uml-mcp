"""Configure Python logging from the ``logging`` section of ``uml-mcp.yaml``."""

from __future__ import annotations

import collections
import datetime as _dt
import json
import logging
import re
import threading
from typing import Any

from ..core.settings_file import LoggingConfig
from .redaction import JWT_LIKE
from .sinks import build_rotating_handler


class JsonFormatter(logging.Formatter):
    """One JSON object per line; bearer tokens are scrubbed from messages."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": JWT_LIKE.sub("<redacted>", record.getMessage()),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


TEXT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_SECRET_ASSIGN = re.compile(
    r"(?i)((?:token|secret|password|authorization|api[_-]?key|assertion)"
    r"[\"']?\s*[:=]\s*[\"']?)([^\s\"',&]+)"
)


def scrub(text: str) -> str:
    """Remove bearer tokens and ``secret=...`` style values from a log line."""
    return _SECRET_ASSIGN.sub(r"\1***", JWT_LIKE.sub("<redacted>", text))


class RingBufferHandler(logging.Handler):
    """Last N log records (redacted) for the admin console Logs page."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: collections.deque[dict[str, Any]] = collections.deque(
            maxlen=capacity
        )
        self.seq = 0
        self._cond = threading.Condition()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = scrub(record.getMessage())
            if record.exc_info:
                message += "\n" + scrub(
                    logging.Formatter().formatException(record.exc_info)
                )
        except Exception:  # noqa: BLE001 - logging must never raise
            message = "<unformattable log record>"
        with self._cond:
            self.seq += 1
            self.records.append(
                {
                    "seq": self.seq,
                    "timestamp": _dt.datetime.fromtimestamp(record.created, _dt.UTC)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": message,
                }
            )
            self._cond.notify_all()

    def query(
        self,
        *,
        after: int = 0,
        level: str | None = None,
        q: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        floor = logging.getLevelName(level.upper()) if level else 0
        floor = floor if isinstance(floor, int) else 0
        with self._cond:
            items = [r for r in self.records if r["seq"] > after]
        items = [
            r
            for r in items
            if logging.getLevelName(r["level"]) >= floor
            and (not q or q.lower() in (r["message"] + r["logger"]).lower())
        ]
        return items[-max(1, min(limit, 2000)) :]


#: Process-wide ring (always attached by :func:`configure_logging`).
RING = RingBufferHandler()


_CONFIGURED = False


def is_configured() -> bool:
    """True once :func:`configure_logging` ran (the CLI configures before app import)."""
    return _CONFIGURED


def build_formatter(cfg: LoggingConfig) -> logging.Formatter:
    return JsonFormatter() if cfg.format == "json" else logging.Formatter(TEXT_FORMAT)


def configure_logging(
    cfg: LoggingConfig,
    *,
    console_handler: logging.Handler | None = None,
    debug: bool = False,
) -> list[logging.Handler]:
    """Apply level, format, per-logger levels and an optional rotating file."""
    global _CONFIGURED
    _CONFIGURED = True
    level = logging.DEBUG if debug else getattr(logging, cfg.level)
    handlers: list[logging.Handler] = []
    if console_handler is not None:
        if cfg.format == "json":
            console_handler.setFormatter(build_formatter(cfg))
        handlers.append(console_handler)
    if cfg.file is not None:
        file_handler = build_rotating_handler(cfg.file)
        file_handler.setFormatter(build_formatter(cfg))
        handlers.append(file_handler)
    root = logging.getLogger()
    for handler in handlers:
        handler.setLevel(level)
    if handlers:
        logging.basicConfig(level=level, handlers=[*handlers, RING], force=True)
    else:
        root.setLevel(level)
        attach_ring()
    for name, lvl in cfg.loggers.items():
        logging.getLogger(name).setLevel(lvl.upper())
    return handlers


def attach_ring() -> RingBufferHandler:
    root = logging.getLogger()
    if RING not in root.handlers:
        root.addHandler(RING)
    return RING


def ensure_console_logging() -> RingBufferHandler:
    """For hosts that never configured logging (``uvicorn app:app``, the console).

    Captures INFO+ in the admin Logs ring while stderr keeps printing only
    WARNING+ (what Python's last-resort handler did before), so nothing changes
    for operators reading the terminal.
    """
    root = logging.getLogger()
    if not _CONFIGURED and not any(h is not RING for h in root.handlers):
        stderr = logging.StreamHandler()
        stderr.setLevel(logging.WARNING)
        root.addHandler(stderr)
        if root.level > logging.INFO or root.level == logging.NOTSET:
            root.setLevel(logging.INFO)
    return attach_ring()


__all__ = [
    "RING",
    "JsonFormatter",
    "RingBufferHandler",
    "attach_ring",
    "build_formatter",
    "configure_logging",
    "ensure_console_logging",
    "is_configured",
    "scrub",
]
