"""Bundled brand marks; no runtime requests to icon CDNs."""

import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def brand_svg(provider: str, name: str) -> str:
    key = {"aws": "aws-color", "gcp": "googlecloud-color"}.get(provider)
    if provider == "tech":
        key = {
            "openai": "openai",
            "chatgpt": "openai",
            "anthropic": "claude-color",
            "claude": "claude-color",
        }.get(name.lower())
    if not key:
        return ""
    svg = (Path(__file__).parent / "assets" / "brands" / f"{key}.svg").read_text()

    svg = re.sub(r'\sstyle="[^"]*"', "", svg)

    def root(match):
        attrs = re.sub(r'\s(?:width|height)="[^"]*"', "", match[1])
        return (
            '<svg class="brand-logo" x="10" y="8" width="20" height="20"' + attrs + ">"
        )

    return re.sub(r"<svg([^>]*)>", root, svg, count=1)
