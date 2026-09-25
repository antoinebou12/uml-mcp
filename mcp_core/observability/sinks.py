"""Audit sinks: rotating JSONL file, JSON stream (stdout / stderr), memory ring."""

from __future__ import annotations

import gzip
import json
import logging
import logging.handlers
import os
import shutil
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any, Protocol, TextIO

from ..core.settings_file import RotationConfig


class Sink(Protocol):
    def write(self, record: dict[str, Any]) -> None: ...

    def close(self) -> None: ...


def _gzip_namer(name: str) -> str:
    return name + ".gz"


def _gzip_rotator(source: str, dest: str) -> None:
    # ``dest`` already carries ``.gz`` (namer), so backups shift like plain ones.
    with open(source, "rb") as src, gzip.open(dest, "wb") as dst:
        shutil.copyfileobj(src, dst)
    _private(dest)
    os.remove(source)


def _private(path: str | Path) -> None:
    try:
        os.chmod(path, 0o600)  # logs and audit trails are owner-only
    except OSError:
        pass


class _PrivateRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def _open(self):  # every (re)opened file, including after rollover
        stream = super()._open()
        _private(self.baseFilename)
        return stream


class _PrivateTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def _open(self):
        stream = super()._open()
        _private(self.baseFilename)
        return stream


def build_rotating_handler(cfg: RotationConfig) -> logging.Handler:
    """Size-based rotation when ``max_bytes`` > 0, otherwise time-based."""
    path = Path(cfg.path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler: logging.Handler
    if cfg.max_bytes > 0:
        handler = _PrivateRotatingFileHandler(
            path, maxBytes=cfg.max_bytes, backupCount=cfg.backup_count, encoding="utf-8"
        )
    else:
        handler = _PrivateTimedRotatingFileHandler(
            path,
            when=cfg.when,
            interval=cfg.interval,
            backupCount=cfg.backup_count,
            encoding="utf-8",
            utc=True,
        )
    if cfg.compress:
        handler.namer = _gzip_namer  # type: ignore[attr-defined]
        handler.rotator = _gzip_rotator  # type: ignore[attr-defined]
    return handler


class JsonlFileSink:
    def __init__(self, cfg: RotationConfig):
        self.handler = build_rotating_handler(cfg)
        self.handler.setFormatter(logging.Formatter("%(message)s"))

    def write(self, record: dict[str, Any]) -> None:
        self.handler.emit(
            logging.LogRecord(
                "uml_mcp.audit",
                logging.INFO,
                "",
                0,
                json.dumps(record, separators=(",", ":"), default=str),
                None,
                None,
            )
        )

    def close(self) -> None:
        self.handler.close()


class StreamSink:
    """JSON lines on stdout, or stderr when stdout carries MCP stdio JSON-RPC."""

    def __init__(self, stream: TextIO | None = None, *, stdio_transport: bool = False):
        self._stream = stream
        self._stdio = stdio_transport
        self._lock = threading.Lock()

    @property
    def stream(self) -> TextIO:
        if self._stream is not None:
            return self._stream
        return sys.stderr if self._stdio else sys.stdout

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps({"audit": record}, separators=(",", ":"), default=str)
        with self._lock:
            self.stream.write(line + "\n")
            self.stream.flush()

    def close(self) -> None:
        return None


class MemorySink:
    def __init__(self, size: int = 500):
        self.records: deque[dict[str, Any]] = deque(maxlen=size)

    def write(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    def close(self) -> None:
        return None

    def query(
        self,
        *,
        status: str | None = None,
        decision: str | None = None,
        operation: str | None = None,
        user: str | None = None,
        since: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        out = []
        for rec in reversed(self.records):
            if status and rec.get("operation_status") != status:
                continue
            if decision and rec.get("policy_decision") != decision:
                continue
            if operation and operation not in str(rec.get("operation_name", "")):
                continue
            if user and user != rec.get("user_id"):
                continue
            if since and str(rec.get("timestamp", "")) < since:
                continue
            out.append(rec)
        return out[offset : offset + limit]


__all__ = [
    "JsonlFileSink",
    "MemorySink",
    "Sink",
    "StreamSink",
    "build_rotating_handler",
]
