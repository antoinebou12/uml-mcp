"""Configure Python logging from the ``logging`` section of ``uml-mcp.yaml``."""

from __future__ import annotations

import json
import logging
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
        logging.basicConfig(level=level, handlers=handlers, force=True)
    else:
        root.setLevel(level)
    for name, lvl in cfg.loggers.items():
        logging.getLogger(name).setLevel(lvl.upper())
    return handlers


__all__ = ["JsonFormatter", "build_formatter", "configure_logging", "is_configured"]
