"""Validation of embedded node icons (base64 image data URIs).

SVG icons are rejected when they carry scripts, event handlers, entities or external
references, so an icon cannot run code or fetch anything when a diagram is opened.
"""

from __future__ import annotations

import base64
import binascii
import re
from xml.etree import ElementTree

MIME = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def validate_icon(uri: str) -> None:
    """Accept bounded embedded images; reject active or external SVG content."""
    if not isinstance(uri, str) or len(uri) > 1_400_000:
        raise ValueError("Icon must be an embedded image smaller than 1 MB")
    header, separator, payload = uri.partition(",")
    if not separator or header not in {f"data:{mime};base64" for mime in MIME.values()}:
        raise ValueError("Icon must be a base64 SVG, PNG, JPEG or WebP data URI")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Icon contains invalid base64") from exc
    if not raw or len(raw) > 1_000_000:
        raise ValueError("Icon must contain between 1 and 1000000 bytes")
    if header != "data:image/svg+xml;base64":
        return
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("SVG declarations and entities are not supported")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid SVG icon") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValueError("SVG icon needs an svg root")
    forbidden = {
        "script",
        "foreignobject",
        "iframe",
        "animate",
        "animatetransform",
        "set",
    }
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() in forbidden:
            raise ValueError("SVG icon contains active content")
        for name, value in element.attrib.items():
            local = name.rsplit("}", 1)[-1].lower()
            if local.startswith("on"):
                raise ValueError("SVG icon contains event handlers")
            if local in {"href", "src"} and not value.startswith("#"):
                raise ValueError("SVG icon references external content")
        css = " ".join(element.attrib.values()) + (element.text or "")
        if "@import" in css.lower() or re.search(
            r"url\(\s*['\"]?(?!#)[^\s]", css, re.IGNORECASE
        ):
            raise ValueError("SVG icon references external styles or images")
