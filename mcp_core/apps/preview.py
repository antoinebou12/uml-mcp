"""Generate bounded raster previews without changing the original render URL."""

import base64
import re
from io import BytesIO

from PIL import Image, UnidentifiedImageError


def compact_preview(data: str, mime_type: str, limit: int) -> str | None:
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

            svg = raw.decode("utf-8")
            # Previews must not resolve files, URLs or XML entities on the host.
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", svg, re.IGNORECASE):
                return None
            if re.search(
                r"""(?:href\s*=\s*["']\s*(?!\#)|url\(\s*["']?(?!\#))""",
                svg,
                re.IGNORECASE,
            ):
                return None
            raw = resvg_py.svg_to_bytes(svg_string=svg, width=1200, height=1200)
        with Image.open(BytesIO(raw)) as original:
            if original.width * original.height > 16_000_000:
                return None
            preview = original.convert("RGBA")
        for size in (1200, 960, 720, 480, 320, 160):
            preview.thumbnail((size, size), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            preview.save(buffer, format="PNG", optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            if len(encoded) <= limit:
                return encoded
    except (
        ValueError,
        OSError,
        UnicodeError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ):
        return None
    return None
