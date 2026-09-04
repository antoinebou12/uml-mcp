"""Stable chat-facing fields for diagram render results."""

from __future__ import annotations

from typing import Any


def build_display_markdown(result: dict[str, Any]) -> str | None:
    """Stable chat packet: markdown image + URL + playground links."""
    extras: list[str] = []
    url = result.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        extras.append(f"![diagram]({url})")
        extras.append(f"- **URL:** {url}")
    playground = result.get("playground")
    if isinstance(playground, str) and playground.startswith(("http://", "https://")):
        extras.append(f"- **Playground:** {playground}")
    if not extras:
        return None
    return "\n\n".join(extras)
