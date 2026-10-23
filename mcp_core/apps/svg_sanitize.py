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


def sanitize_svg(svg: str) -> str:
    """Return SVG with scripts, foreignObject, and event handlers removed.

    Malformed input that cannot be parsed is returned as an empty SVG so the
    viewer can fall back to URL/playground text instead of injecting junk.
    """
    text = (svg or "").strip()
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
