"""Redaction of audit input data (never log secrets, tokens or full diagram code)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

SECRET_KEY = re.compile(
    r"(token|secret|password|passwd|authorization|api[_-]?key|assertion|cookie|credential)",
    re.IGNORECASE,
)
JWT_LIKE = re.compile(r"eyJ[A-Za-z0-9_\-]{6,}(\.[A-Za-z0-9_\-]*){0,2}")
CODE_KEYS = frozenset({"code", "source", "diagram", "content", "content_base64"})
MASK = "***"


def _summarize_text(value: str, preview: int) -> dict[str, Any]:
    return {
        "sha256": hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16],
        "chars": len(value),
        "preview": JWT_LIKE.sub("<redacted>", value[:preview]),
    }


def redact(
    value: Any,
    *,
    mode: str = "redacted",
    max_chars: int = 2000,
    depth: int = 0,
    key: str | None = None,
) -> Any:
    """Return a JSON-safe, redacted copy of ``value``.

    ``mode``: ``none`` drops inputs, ``redacted`` masks secrets and summarizes
    diagram code (hash + length + 80 char preview), ``full`` keeps values but
    still masks secrets and truncates to ``max_chars``.
    """
    if mode == "none":
        return None
    if key is not None and SECRET_KEY.search(key):
        return MASK
    if depth > 6:
        return "<max-depth>"
    if isinstance(value, dict):
        return {
            str(k): redact(
                v, mode=mode, max_chars=max_chars, depth=depth + 1, key=str(k)
            )
            for k, v in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple, set)):
        items = list(value)[:50]
        return [
            redact(v, mode=mode, max_chars=max_chars, depth=depth + 1) for v in items
        ]
    if isinstance(value, str):
        if mode == "redacted" and key in CODE_KEYS:
            return _summarize_text(value, 80)
        text = JWT_LIKE.sub("<redacted>", value)
        return text if len(text) <= max_chars else text[:max_chars] + "…"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(str(value), mode=mode, max_chars=max_chars, depth=depth + 1, key=key)


__all__ = ["MASK", "redact"]
