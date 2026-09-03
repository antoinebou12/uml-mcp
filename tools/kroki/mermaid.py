"""Mermaid diagram URL and state serialization.

Provides encoding compatible with mermaid.ink (image URLs) and
mermaid.live (editor URLs) using pako/base64 state.
"""

import base64
import json
import logging
import zlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote

logger = logging.getLogger(__name__)

# Base URL for direct image rendering (mermaid.ink)
MERMAID_INK_BASE = "https://mermaid.ink"
# Base URL for the live editor
MERMAID_LIVE_EDIT_BASE = "https://mermaid.live/edit#"


@dataclass(frozen=True)
class MermaidUrls:
    """URLs and code for a Mermaid diagram (image, editor, and source)."""

    image_url: str
    """URL to the rendered SVG image (mermaid.ink)."""
    edit_url: str
    """URL to open the diagram in mermaid.live editor."""
    code: str
    """The Mermaid diagram source code."""


def _js_encode_uri_component(data: str) -> str:
    return quote(data, safe="~()*!.'")


def _js_decode_uri_component(data: str) -> str:
    return unquote(data)


class Serde:
    """Base class for state serialization/deserialization (e.g. pako, base64)."""

    def serialize(self, state: str) -> str:
        raise NotImplementedError

    def deserialize(self, state: str) -> str:
        raise NotImplementedError


class Base64Serde(Serde):
    def serialize(self, state: str) -> str:
        result = base64.b64encode(state.encode()).decode()
        return result + "=" * ((4 - len(result) % 4) % 4)

    def deserialize(self, state: str) -> str:
        return base64.b64decode(state.encode()).decode()


class PakoSerde(Serde):
    """Pako-compatible deflate serialization (used by mermaid.live)."""

    def serialize(self, state: str) -> str:
        compressed = self._pako_deflate(state.encode("utf-8"))
        result = base64.urlsafe_b64encode(compressed).decode("utf-8")
        return result + "=" * ((4 - len(result) % 4) % 4)

    def deserialize(self, state: str) -> str:
        data = base64.urlsafe_b64decode(state)
        decompressed = self._pako_inflate(data)
        return decompressed.decode("utf-8")

    def _pako_deflate(self, data: bytes) -> bytes:
        compress = zlib.compressobj(
            level=9,
            method=zlib.DEFLATED,
            wbits=15,
            memLevel=8,
            strategy=zlib.Z_DEFAULT_STRATEGY,
        )
        compressed_data = compress.compress(data)
        compressed_data += compress.flush()
        return compressed_data

    def _pako_inflate(self, data: bytes) -> bytes:
        decompress = zlib.decompressobj(15)
        decompressed_data = decompress.decompress(data)
        decompressed_data += decompress.flush()
        return decompressed_data


_SERDES: dict[str, Serde] = {
    "base64": Base64Serde(),
    "pako": PakoSerde(),
}


def serialize_state(state: dict[str, Any], serde: str = "pako") -> str:
    """Serialize a Mermaid editor state dict to a string for use in URLs.

    Args:
        state: State dict with at least "code" and optionally "mermaid" theme.
        serde: "pako" (default) or "base64".

    Returns:
        String in the form "serde:payload" for mermaid.ink / mermaid.live URLs.
    """
    if serde not in _SERDES:
        raise ValueError(f"Unknown serde type: {serde}")
    json_str = json.dumps(state)
    serialized = _SERDES[serde].serialize(json_str)
    return f"{serde}:{serialized}"


def deserialize_state(state: str) -> dict[str, Any]:
    """Deserialize a state string back to a dict."""
    serde, serialized = state.split(":", 1) if ":" in state else ("base64", state)
    if serde not in _SERDES:
        raise ValueError(f"Unknown serde type: {serde}")
    required_padding = len(serialized) % 4
    if required_padding > 0:
        serialized += "=" * (4 - required_padding)
    json_str = _SERDES[serde].deserialize(serialized)
    return json.loads(json_str)


def generate_diagram_state(
    diagram_text: str,
    theme: str = "default",
    *,
    update_editor: bool = True,
    auto_sync: bool = True,
    update_diagram: bool = True,
) -> dict[str, Any]:
    """Build the state dict used by mermaid.live / mermaid.ink."""
    return {
        "code": diagram_text.strip(),
        "mermaid": {"theme": theme},
        "updateEditor": update_editor,
        "autoSync": auto_sync,
        "updateDiagram": update_diagram,
    }


def generate_mermaid_urls(
    diagram_state: dict[str, Any] | None = None,
    diagram_text: str | None = None,
    theme: str = "default",
    serde: str = "pako",
    image_format: str = "svg",
) -> MermaidUrls:
    """Generate image and editor URLs for a Mermaid diagram.

    Either pass diagram_state (full state dict) or diagram_text (and optional theme).
    If both are provided, diagram_state takes precedence.

    Raster formats use mermaid.ink ``/img/`` with ``?type=`` (not ``/png/``, which 404s).
    """
    if diagram_state is None:
        if diagram_text is None:
            raise ValueError("Provide either diagram_state or diagram_text")
        diagram_state = generate_diagram_state(diagram_text, theme=theme)
    serialized = serialize_state(diagram_state, serde=serde)
    code = diagram_state.get("code", "")
    fmt = (image_format or "svg").lower().strip()
    if fmt in {"svg"}:
        image_url = f"{MERMAID_INK_BASE}/svg/{serialized}"
    else:
        # mermaid.ink serves raster via /img/?type=png|jpeg|webp (default jpeg).
        # Paths like /png/... return 404.
        type_param = {"jpg": "jpeg", "img": "jpeg"}.get(fmt, fmt)
        if type_param not in {"png", "jpeg", "webp"}:
            type_param = "png"
        image_url = f"{MERMAID_INK_BASE}/img/{serialized}?type={type_param}"
    edit_url = f"{MERMAID_LIVE_EDIT_BASE}{serialized}"
    return MermaidUrls(image_url=image_url, edit_url=edit_url, code=code)


def get_image_url(
    diagram_text: str, theme: str = "default", image_format: str = "svg"
) -> str:
    """Return the mermaid.ink image URL for the given diagram code."""
    urls = generate_mermaid_urls(
        diagram_text=diagram_text, theme=theme, image_format=image_format
    )
    return urls.image_url


def get_edit_url(diagram_text: str, theme: str = "default") -> str:
    """Return the mermaid.live editor URL for the given diagram code."""
    urls = generate_mermaid_urls(diagram_text=diagram_text, theme=theme)
    return urls.edit_url


def generate_mermaid_live_editor_url(
    diagram_state: dict[str, Any], serde: str = "pako"
) -> MermaidUrls:
    """Generate image and editor URLs from a state dict. Prefer generate_mermaid_urls."""
    return generate_mermaid_urls(diagram_state=diagram_state, serde=serde)


if __name__ == "__main__":
    diagram_text = """graph TD
  A[Christmas] -->|Get money| B(Go shopping)
  B --> C{Let me think}
  C -->|One| D[Laptop]
  C -->|Two| E[iPhone]
  C -->|Three| F[fa:fa-car Car]"""
    diagram_text = "\n".join(line.strip() for line in diagram_text.split("\n")).strip()

    urls = generate_mermaid_urls(diagram_text=diagram_text)
    print("Image URL:", urls.image_url)
    print("Edit URL:", urls.edit_url)
