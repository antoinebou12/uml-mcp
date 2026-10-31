"""Generate bounded raster previews without changing the original render URL."""

import base64
import re
from io import BytesIO

from PIL import Image, UnidentifiedImageError


def compact_preview(
    data: str, mime_type: str, limit: int, *, max_dimension: int = 1200
) -> str | None:
    """Return a complete PNG thumbnail, or None for unsupported/invalid input."""
    if mime_type not in {"image/png", "image/jpeg", "image/svg+xml"}:
        return None
    # Bound decoding work as well as the outgoing response.
    if len(data) > 16_000_000:
        return None
    try:
        raw = base64.b64decode(data, validate=True)
        if mime_type == "image/svg+xml":
            import resvg_py

            from mcp_core.core.svg_raster import _resvg_kwargs

            svg = raw.decode("utf-8")
            # Previews must not resolve files, URLs or XML entities on the host.
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", svg, re.IGNORECASE):
                return None
            # Navigation links cannot load resources during rasterization.
            # Strip only anchor hrefs, retaining the image/use resource checks.
            svg = re.sub(
                r"""(<a\b[^>]*?)\s(?:xlink:)?href\s*=\s*["'][^"']*["']""",
                r"\1",
                svg,
                flags=re.IGNORECASE,
            )

            def check_embedded_raster(match: re.Match[str]) -> str:
                payload = match[2].split(",", 1)[1]
                embedded = base64.b64decode(payload, validate=True)
                with Image.open(BytesIO(embedded)) as image:
                    if (
                        image.format not in {"PNG", "JPEG", "WEBP"}
                        or image.width * image.height > 16_000_000
                    ):
                        raise ValueError("Unsupported embedded preview image")
                    image.verify()
                # Exempt validated, self-contained raster data from the URL guard.
                # The original data URI remains in the SVG passed to resvg.
                return match[1] + "#" + match[3]

            checked_svg = re.sub(
                r"""(href\s*=\s*["'])(data:image/(?:png|jpeg|webp);base64,[^"']+)(["'])""",
                check_embedded_raster,
                svg,
                flags=re.IGNORECASE,
            )
            if re.search(
                r"""(?:href\s*=\s*["']\s*(?!\#)|url\(\s*["']?(?!\#))""",
                checked_svg,
                re.IGNORECASE,
            ):
                return None
            kwargs = _resvg_kwargs(svg, zoom=1.0)
            kwargs.update(width=1200, height=1200)
            raw = resvg_py.svg_to_bytes(**kwargs)
        with Image.open(BytesIO(raw)) as original:
            if original.width * original.height > 16_000_000:
                return None
            preview = original.convert("RGBA")
        for size in (1200, 960, 720, 480, 320, 160, 96):
            if size > max_dimension:
                continue
            preview.thumbnail((size, size), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            preview.save(buffer, format="PNG", optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            if len(encoded) <= limit:
                return encoded
            # Diagram palettes are small. Quantize before reducing dimensions so
            # labels remain readable within the initial-response byte budget.
            indexed = preview.quantize(
                colors=128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
            )
            buffer = BytesIO()
            indexed.save(buffer, format="PNG", optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            if len(encoded) <= limit:
                return encoded
    except (
        ValueError,
        OSError,
        UnicodeError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        SyntaxError,
    ):
        return None
    return None
