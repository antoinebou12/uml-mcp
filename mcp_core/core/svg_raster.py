"""Rasterize SVG bytes to PNG/JPEG for chat clients when Kroki is SVG-only."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

_RASTER_REQUESTS = frozenset({"png", "jpeg", "jpg"})
# Graphviz/DBML SVGs often use width="788pt"; resvg rejects non-px lengths.
_PT_SIZE = re.compile(
    r"""(?P<attr>width|height)\s*=\s*(?P<q>['"])(?P<val>[\d.]+)pt(?P=q)""",
    re.IGNORECASE,
)
_ROOT_SVG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE | re.DOTALL)
_ATTR = re.compile(
    r"""(?P<name>width|height|viewBox)\s*=\s*(?P<q>['"])(?P<val>.*?)(?P=q)""",
    re.IGNORECASE,
)
# Nomnoml emits <text> with no fill; a parent fill="transparent" makes glyphs invisible.
_TEXT_OPEN = re.compile(r"<text\b([^>]*)>", re.IGNORECASE)
_MISSING_FONTS = re.compile(
    r"""font-family\s*:\s*['"]?(?:Helvetica|Verdana|Dialog|Sans|sans)['"]?""",
    re.IGNORECASE,
)
_ATTR_FONTS = re.compile(
    r"""font-family=(?P<q>['"])(?:Helvetica|Verdana|'Dialog'|Dialog|Sans)(?P=q)""",
    re.IGNORECASE,
)
# resvg often skips glyphs when font-size uses ``pt`` (nomnoml / symbolator).
_FONT_SIZE_PT = re.compile(
    r"""font-size=(?P<q>['"])(?P<val>[\d.]+)pt(?P=q)""",
    re.IGNORECASE,
)
_CSS_FONT_SIZE_PT = re.compile(
    r"""font-size\s*:\s*(?P<val>[\d.]+)pt""",
    re.IGNORECASE,
)


def is_raster_format(fmt: str) -> bool:
    return fmt.lower().strip() in _RASTER_REQUESTS


def normalize_raster_format(fmt: str) -> str:
    value = fmt.lower().strip()
    return "jpeg" if value in {"jpeg", "jpg"} else "png"


@lru_cache(maxsize=1)
def _system_font_files() -> tuple[str, ...]:
    candidates = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "fonts"
        / "NotoSans-Regular.ttf",
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    )
    return tuple(str(p) for p in candidates if p.is_file())


def _root_size_hints(text: str) -> tuple[int | None, int | None]:
    """Width/height from the root ``<svg>`` only (ignore nested marker viewBoxes)."""
    root = _ROOT_SVG.search(text)
    if not root:
        return None, None
    attrs = {
        m.group("name").lower(): m.group("val") for m in _ATTR.finditer(root.group(0))
    }
    width = height = None
    for key, dest in (("width", "w"), ("height", "h")):
        raw = attrs.get(key)
        if not raw:
            continue
        try:
            value = int(float(re.sub(r"(?i)pt|px|%", "", raw).strip()) + 0.5)
        except ValueError:
            continue
        if dest == "w":
            width = max(1, value)
        else:
            height = max(1, value)
    if width and height:
        return width, height
    view = attrs.get("viewbox")
    if view:
        parts = view.replace(",", " ").split()
        if len(parts) == 4:
            try:
                return (
                    max(1, int(float(parts[2]) + 0.5)),
                    max(1, int(float(parts[3]) + 0.5)),
                )
            except ValueError:
                return None, None
    return width, height


def _ensure_text_fill(text: str) -> str:
    """Give ``<text>`` an opaque fill when none is set (fixes nomnoml)."""

    def repl(match: re.Match[str]) -> str:
        attrs = match.group(1)
        lowered = attrs.lower()
        if "fill=" in lowered or "style=" in lowered and "fill:" in lowered:
            return match.group(0)
        return f'<text{attrs} fill="#222222">'

    return _TEXT_OPEN.sub(repl, text)


def _remap_missing_fonts(text: str) -> str:
    """Point Helvetica/Verdana/Dialog at a family resvg can load with system fonts."""
    out = _MISSING_FONTS.sub("font-family:Arial", text)
    out = _ATTR_FONTS.sub(r"font-family=\g<q>Arial\g<q>", out)
    # Catch any remaining bare Helvetica tokens in attributes/CSS.
    return re.sub(r"\bHelvetica\b", "Arial", out, flags=re.IGNORECASE)


def _normalize_font_size_pt(text: str) -> str:
    """Convert ``12pt`` font sizes to unitless numbers resvg accepts as px."""
    out = _FONT_SIZE_PT.sub(
        lambda m: f"font-size={m.group('q')}{m.group('val')}{m.group('q')}",
        text,
    )
    return _CSS_FONT_SIZE_PT.sub(lambda m: f"font-size:{m.group('val')}px", out)


def _prepare_svg_for_resvg(text: str) -> tuple[str, int | None, int | None]:
    """Rewrite sizes/fonts/fills so resvg can paint Kroki SVGs reliably."""
    prepared = _PT_SIZE.sub(
        lambda m: f"{m.group('attr')}={m.group('q')}{m.group('val')}{m.group('q')}",
        text,
    )
    prepared = _normalize_font_size_pt(prepared)
    prepared = _remap_missing_fonts(prepared)
    prepared = _ensure_text_fill(prepared)
    return prepared, *_root_size_hints(prepared)


def _resvg_kwargs(prepared: str, *, zoom: float) -> dict:
    kwargs: dict = {"svg_string": prepared, "zoom": zoom}
    fonts = _system_font_files()
    if fonts:
        kwargs["font_files"] = list(fonts)
        kwargs["font_family"] = "Noto Sans"
        kwargs["sans_serif_family"] = "Noto Sans"
        kwargs["serif_family"] = "Noto Sans"
        kwargs["monospace_family"] = "Noto Sans"
    return kwargs


def svg_to_png(svg_bytes: bytes, *, zoom: float = 1.0) -> bytes | None:
    """Convert SVG to PNG. Prefers resvg; falls back to cairosvg when Cairo works."""
    text = svg_bytes.decode("utf-8", errors="replace")
    prepared, width, height = _prepare_svg_for_resvg(text)
    z = zoom if zoom > 0 else 1.0
    try:
        import resvg_py

        png = resvg_py.svg_to_bytes(**_resvg_kwargs(prepared, zoom=z))
        if png and png[:8] == b"\x89PNG\r\n\x1a\n":
            return png
    except Exception as exc:  # noqa: BLE001 - optional backend
        logger.debug("resvg rasterize failed: %s", exc)

    if width and height:
        try:
            import resvg_py

            kwargs = _resvg_kwargs(prepared, zoom=z)
            kwargs["width"] = width
            kwargs["height"] = height
            png = resvg_py.svg_to_bytes(**kwargs)
            if png and png[:8] == b"\x89PNG\r\n\x1a\n":
                return png
        except Exception as exc:  # noqa: BLE001
            logger.debug("resvg sized retry failed: %s", exc)

    try:
        import cairosvg

        png = cairosvg.svg2png(bytestring=prepared.encode("utf-8"))
        if png and png[:8] == b"\x89PNG\r\n\x1a\n":
            return png
    except Exception as exc:  # noqa: BLE001 - optional backend / missing Cairo
        logger.debug("cairosvg rasterize failed: %s", exc)
    return None


def png_to_jpeg(png_bytes: bytes) -> bytes:
    from PIL import Image

    image = Image.open(BytesIO(png_bytes)).convert("RGB")
    out = BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


def rasterize_svg(
    svg_bytes: bytes, output_format: str = "png"
) -> tuple[bytes, str] | None:
    """Return ``(bytes, mime_type)`` for png/jpeg, or ``None`` if unavailable."""
    target = normalize_raster_format(output_format)
    png = svg_to_png(svg_bytes)
    if png is None:
        return None
    if target == "jpeg":
        return png_to_jpeg(png), "image/jpeg"
    return png, "image/png"


__all__ = [
    "is_raster_format",
    "normalize_raster_format",
    "png_to_jpeg",
    "rasterize_svg",
    "svg_to_png",
]
