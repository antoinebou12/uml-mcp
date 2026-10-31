"""Strip executable content from SVG before the Apps viewer inserts it into the DOM.

Hosts run the Apps iframe with script enabled for the postMessage bridge, so raw
Kroki SVG must never be assigned via ``innerHTML`` without sanitization. Keep the
rules here in sync with the inline JavaScript in ``diagram_viewer.py``.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

# Event-handler attributes (onload, onclick, …) and legacy href javascript: URLs.
_EVENT_ATTR = re.compile(r"^on", re.IGNORECASE)
_JS_HREF = re.compile(r"^\s*javascript:", re.IGNORECASE)

# Local-name tags removed entirely (and their descendants).
_STRIP_TAGS = frozenset(
    {
        "script",
        "foreignobject",
        "iframe",
        "object",
        "embed",
        "link",
        "meta",
        "base",
    }
)


def _local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1].lower()
    return tag.lower()


def flatten_svg_labels(svg: str) -> str:
    """Convert HTML-backed SVG labels to inert, portable SVG text."""
    if "foreignobject" not in svg.lower() or re.search(
        r"<!\s*ENTITY", svg, re.IGNORECASE
    ):
        return svg
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return svg
    ns = "{http://www.w3.org/2000/svg}"
    ET.register_namespace("", ns[1:-1])
    color = re.search(r"color:\s*(#[0-9a-fA-F]{3,8}|black|white)\b", svg)
    for parent in list(root.iter()):
        for node in list(parent):
            if _local_name(node.tag) != "foreignobject":
                continue
            for owner in list(node.iter()):
                for child in list(owner):
                    if _local_name(child.tag) in _STRIP_TAGS:
                        owner.remove(child)
            paragraphs = [p for p in node.iter() if _local_name(p.tag) == "p"]
            lines = [" ".join("".join(p.itertext()).split()) for p in paragraphs]
            lines = [line for line in lines if line] or [
                " ".join("".join(node.itertext()).split())
            ]
            try:
                x, y, w, h = (
                    float(node.get(k, d))
                    for k, d in (
                        ("x", "0"),
                        ("y", "0"),
                        ("width", "80"),
                        ("height", "24"),
                    )
                )
            except ValueError:
                continue
            size = min(16.0, max(10.0, h / max(1, len(lines)) / 1.5))
            text = ET.Element(
                ns + "text",
                {
                    "x": str(x + w / 2),
                    "y": str(y + h / 2 - (len(lines) - 1) * size * 0.6),
                    "text-anchor": "middle",
                    "dominant-baseline": "central",
                    "font-family": "sans-serif",
                    "font-size": str(size),
                    "fill": color[1] if color else "#111827",
                },
            )
            for i, line in enumerate(lines):
                ET.SubElement(
                    text,
                    ns + "tspan",
                    {"x": str(x + w / 2), "dy": "0" if i == 0 else str(size * 1.2)},
                ).text = line
            text.tail = node.tail
            parent.insert(list(parent).index(node), text)
            parent.remove(node)
    return ET.tostring(root, encoding="unicode")


def sanitize_svg(svg: str) -> str:
    """Return SVG with scripts, foreignObject, and event handlers removed.

    Malformed input that cannot be parsed is returned as an empty SVG so the
    viewer can fall back to URL/playground text instead of injecting junk.
    """
    text = flatten_svg_labels((svg or "").strip())
    if not text:
        return ""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # Kroki sometimes returns a fragment; wrap and retry once.
        try:
            root = ET.fromstring(
                f"<svg xmlns='http://www.w3.org/2000/svg'>{text}</svg>"
            )
        except ET.ParseError:
            return ""

    # Walk a snapshot so we can remove nodes while iterating.
    for parent in list(root.iter()):
        for child in list(parent):
            if _local_name(child.tag) in _STRIP_TAGS:
                parent.remove(child)

    if _local_name(root.tag) in _STRIP_TAGS:
        return ""

    for element in root.iter():
        for attr in list(element.attrib):
            key = attr.rsplit("}", 1)[-1] if attr.startswith("{") else attr
            value = element.attrib[attr] or ""
            if _EVENT_ATTR.match(key) or (
                key.lower() in {"href", "xlink:href"} and _JS_HREF.match(value)
            ):
                del element.attrib[attr]

    return ET.tostring(root, encoding="unicode")
