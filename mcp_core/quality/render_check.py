"""Check that rendered bytes are a real diagram, not an error page or placeholder.

Used by the smoke runner (``scripts/run_mcp_smoke.py``) and the real-Kroki tests:
an SVG must parse and carry the diagram's labels, a PNG must decode with a
plausible size.
"""

from __future__ import annotations

import io
import re
from xml.etree import ElementTree

MIN_PNG_SIDE = 20
_SKIP_TAGS = {"style", "script", "title", "desc", "metadata", "defs"}


class RenderCheckError(ValueError):
    """Rendered content is not what a diagram renderer should return."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def svg_text(data: bytes | str) -> str:
    """Visible text of an SVG (labels, including HTML labels in foreignObject)."""
    raw = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    # A plain ``<!DOCTYPE svg PUBLIC ...>`` (Graphviz, blockdiag) is fine; entity
    # declarations / internal subsets are refused so nothing can expand.
    if re.search(r"<!ENTITY|<!DOCTYPE[^>]*\[", raw, re.IGNORECASE):
        raise RenderCheckError("SVG with an internal DTD subset is not accepted")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise RenderCheckError(f"not well-formed SVG: {exc}") from exc
    if _local(root.tag) != "svg":
        raise RenderCheckError(f"root element is <{_local(root.tag)}>, not <svg>")
    parts: list[str] = []

    def walk(node: ElementTree.Element) -> None:
        if _local(node.tag) in _SKIP_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(root)
    return " ".join(" ".join(parts).split())


def check_svg(data: bytes | str, labels: tuple[str, ...] = ()) -> str:
    """Raise unless ``data`` is an SVG showing every label; return its text."""
    text = svg_text(data)
    missing = [label for label in labels if label not in text]
    if missing:
        raise RenderCheckError(f"SVG is missing labels {missing}: {text[:120]!r}")
    return text


def png_size(data: bytes) -> tuple[int, int]:
    """Decode a PNG and return ``(width, height)``."""
    from PIL import Image

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RenderCheckError("missing PNG signature")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            return image.size
    except Exception as exc:
        raise RenderCheckError(f"PNG does not decode: {exc}") from exc


def check_png(data: bytes, min_side: int = MIN_PNG_SIDE) -> tuple[int, int]:
    """Raise unless ``data`` is a decodable PNG at least ``min_side`` px each way."""
    width, height = png_size(data)
    if width < min_side or height < min_side:
        raise RenderCheckError(f"PNG is only {width}x{height} px")
    return width, height
