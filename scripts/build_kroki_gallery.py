"""Render each Kroki catalog example for the README gallery.

Run with ``uv run python scripts/build_kroki_gallery.py``.
Requires network access to ``KROKI_SERVER`` (default ``https://kroki.io``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.svg_raster import svg_to_png
from tools.kroki.kroki import LANGUAGE_OUTPUT_SUPPORT, Kroki
from tools.kroki.kroki_templates import DiagramExamples


def main() -> None:
    destination = ROOT / "docs" / "assets" / "kroki"
    destination.mkdir(parents=True, exist_ok=True)
    kroki = Kroki()
    client = httpx.Client(timeout=60.0, follow_redirects=True)
    failures: list[str] = []
    for name, cfg in MCP_SETTINGS.diagram_types.items():
        backend = cfg.backend
        formats = LANGUAGE_OUTPUT_SUPPORT.get(backend, list(cfg.formats))
        code = DiagramExamples.get_example(name)
        if not isinstance(code, str) or len(code.strip()) < 8:
            failures.append(f"{name}: missing example")
            continue
        if "No specific example" in code:
            failures.append(f"{name}: placeholder example")
            continue
        preferred = "png" if "png" in formats else "svg"
        content: bytes | None = None
        used = preferred
        for fmt in (preferred, "svg") if preferred != "svg" else ("svg",):
            if fmt not in formats and fmt != preferred:
                continue
            url = kroki.get_url(backend, code, fmt)
            try:
                response = client.get(url)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - collect and continue
                if fmt == preferred:
                    print(f"retry {name} after {exc}")
                continue
            if len(response.content) < 40:
                continue
            content = response.content
            used = fmt
            break
        if content is None:
            failures.append(f"{name}: render failed")
            continue
        if used == "svg":
            png = svg_to_png(content, zoom=1.5)
            if not png:
                failures.append(f"{name}: svg rasterize failed")
                continue
            content = png
        (destination / f"{name}.png").write_bytes(content)
        print(name)

    if failures:
        print("failures:", *failures, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
