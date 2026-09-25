"""Tiny, dependency-free environment parsing helpers shared across modules."""

from __future__ import annotations

import json


def parse_env_list(value: str | None) -> list[str]:
    """Accept either a JSON array or a comma-separated list."""
    raw = (value or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_env_bool(value: str | None, default: bool = False) -> bool:
    """Parse a boolean env value (true/1/yes/on vs false/0/no/off)."""
    raw = (value or "").strip().lower()
    if not raw:
        return default
    if raw in ("true", "1", "yes", "on"):
        return True
    if raw in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"not a boolean: {value!r}")


__all__ = ["parse_env_bool", "parse_env_list"]
