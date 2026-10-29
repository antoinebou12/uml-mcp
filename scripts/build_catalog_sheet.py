"""Render stress fixtures to PNGs and an aspect-aware contact sheet.

uv run python scripts/build_catalog_sheet.py
uv run python scripts/build_catalog_sheet.py --out .tmp/catalog-images
uv run python scripts/build_catalog_sheet.py --full
uv run python scripts/build_catalog_sheet.py --plantuml-kinds --mermaid-kinds
uv run python scripts/build_catalog_sheet.py --recipes --skills --prompts --themes
uv run python scripts/build_catalog_sheet.py --themes-only
uv run python scripts/build_catalog_sheet.py --themes-bg
uv run python scripts/build_catalog_sheet.py --validate-only --full
"""

from __future__ import annotations

import argparse
import base64
import math
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_core.core.diagram_service import DiagramRequest, generate_from_request
from mcp_core.core.diagram_validation import validate_uml_inputs
from mcp_core.core.svg_raster import svg_to_png
from scripts.catalog_sheet_fixtures import assemble_fixtures


def _content_bbox(img: Image.Image, threshold: int = 250) -> tuple[int, int, int, int]:
    """Tight bbox of non-near-white opaque pixels (left, top, right, bottom)."""
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    assert pixels is not None
    width, height = rgba.size
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            assert isinstance(pixel, tuple)
            r, g, b, a = pixel
            if a > 10 and (r < threshold or g < threshold or b < threshold):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x:
        return 0, 0, width, height
    pad = 4
    return (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(width, max_x + 1 + pad),
        min(height, max_y + 1 + pad),
    )


def _crop_content(img: Image.Image) -> Image.Image:
    box = _content_bbox(img)
    cropped = img.crop(box)
    cw, ch = cropped.size
    # Reject degenerate crops (near-white SVGs with only faint anti-alias).
    if cw < 24 or ch < 24:
        return img
    area_ratio = (cw * ch) / max(1, img.width * img.height)
    # Drop absurd viewport padding while keeping normal diagrams intact.
    if area_ratio < 0.35 or img.width >= 1000 or img.height >= 700:
        return cropped
    return cropped if cropped.size != img.size else img


def _as_image(result: dict) -> Image.Image:
    data = result.get("content_base64")
    if not data:
        raise RuntimeError(f"no content_base64 ({result.get('format_note') or result})")
    raw = base64.b64decode(data)
    if raw.lstrip().startswith((b"<", b"<?xml")):
        png = svg_to_png(raw)
        if png is None:
            raise RuntimeError("SVG rasterize unavailable")
        raw = png
    return Image.open(BytesIO(raw)).convert("RGBA")


def _render_tile(name: str, code: str, *, theme: str | None = None) -> Image.Image:
    result = generate_from_request(
        DiagramRequest(
            diagram_type=name,
            code=code,
            output_format="png",
            theme=theme,
            force_fetch=True,
        )
    )
    err = str(result.get("error") or "").lower()
    # svgbob (and a few backends) are SVG-only — rasterize locally.
    if (
        result.get("error")
        and not result.get("content_base64")
        and ("not supported" in err or "png" in err)
    ):
        result = generate_from_request(
            DiagramRequest(
                diagram_type=name,
                code=code,
                output_format="svg",
                theme=theme,
                force_fetch=True,
            )
        )
    if result.get("error") and not result.get("content_base64"):
        raise RuntimeError(str(result.get("error")))
    return _crop_content(_as_image(result))


def _row_heights(
    tiles: list[tuple[str, Image.Image]], cols: int, cell_w: int, base_h: int
) -> list[int]:
    """Per-row cell height from the tallest letterboxed thumbnail in that row."""
    heights: list[int] = []
    rows = math.ceil(len(tiles) / cols)
    for r in range(rows):
        chunk = tiles[r * cols : (r + 1) * cols]
        needed = base_h
        for _, img in chunk:
            if img.width <= 0:
                continue
            scaled_h = math.ceil(img.height * (cell_w - 16) / img.width)
            # Cap very tall diagrams so one rackdiag doesn't dominate the sheet.
            needed = max(needed, min(scaled_h + 8, int(base_h * 1.8)))
        heights.append(needed)
    return heights


def _build_sheet(tiles: list[tuple[str, Image.Image]], cols: int = 4) -> Image.Image:
    cell_w = 320
    label_h = 22
    pad = 8
    base_h = 200
    row_hs = _row_heights(tiles, cols, cell_w, base_h)
    total_h = sum(h + label_h for h in row_hs)
    sheet = Image.new("RGB", (cols * cell_w, total_h), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    y_cursor = 0
    for r, row_h in enumerate(row_hs):
        for c in range(cols):
            idx = r * cols + c
            if idx >= len(tiles):
                break
            name, img = tiles[idx]
            x0 = c * cell_w
            y0 = y_cursor
            draw.rectangle(
                [x0, y0, x0 + cell_w - 1, y0 + label_h + row_h - 1],
                outline=(220, 220, 220),
                fill=(245, 245, 245),
            )
            draw.text(
                (x0 + pad, y0 + 4), f"{idx + 1}. {name}", fill=(20, 20, 20), font=font
            )
            fit = img.copy()
            fit.thumbnail((cell_w - 2 * pad, row_h - 2 * pad), Image.Resampling.LANCZOS)
            # Letterbox: center on a white tile so wide/tall diagrams stay readable.
            tile = Image.new(
                "RGBA", (cell_w - 2 * pad, row_h - 2 * pad), (255, 255, 255, 255)
            )
            ix = (tile.width - fit.width) // 2
            iy = (tile.height - fit.height) // 2
            tile.paste(fit, (ix, iy), fit)
            sheet.paste(tile.convert("RGB"), (x0 + pad, y0 + label_h + pad))
        y_cursor += label_h + row_h
    return sheet


def _validate_only(fixtures: list[dict[str, str]]) -> int:
    failed = 0
    for i, fx in enumerate(fixtures, 1):
        name = fx.get("label") or fx["diagram_type"]
        result = validate_uml_inputs(
            fx["diagram_type"], fx["code"], "svg", strict=False
        )
        ok = bool(result.get("valid"))
        print(("OK" if ok else "FAIL"), f"{i:02d}", name)
        if not ok:
            failed += 1
            print(" ", result.get("errors") or result.get("diagnostics"))
    print(
        "VALIDATE", "pass" if failed == 0 else f"{failed} failed", "of", len(fixtures)
    )
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    # Sheet builds hammer public Kroki; don't skip Mermaid for a minute mid-run.
    from mcp_core.core.config import MCP_SETTINGS

    MCP_SETTINGS.kroki_circuit_cooldown_seconds = 0.0

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / ".tmp" / "catalog-images",
        help="Directory for per-type PNGs and catalog-contact-sheet.png",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "Catalog + PlantUML/Mermaid kinds + recipes + skills + prompts + all themes"
        ),
    )
    parser.add_argument(
        "--catalog",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include FIXTURES_1_20/21_37 (default on unless --themes-only)",
    )
    parser.add_argument(
        "--plantuml-kinds",
        action="store_true",
        help="PlantUML-family subtypes + timing/salt/mindmap/wbs/gantt",
    )
    parser.add_argument(
        "--mermaid-kinds",
        action="store_true",
        help="Mermaid kinds: flowchart, sequence, class, state, er, gantt, pie, …",
    )
    parser.add_argument(
        "--recipes",
        action="store_true",
        help="Append uml://recipes templates as extra tiles",
    )
    parser.add_argument(
        "--skills",
        action="store_true",
        help="Append DiagramExamples per catalog type (skill starters)",
    )
    parser.add_argument(
        "--prompts",
        action="store_true",
        help="Append representative tiles for published/demoted prompts",
    )
    parser.add_argument(
        "--themes",
        action="store_true",
        help="Append theme tiles (all PlantUML + Mermaid + D2 by default)",
    )
    parser.add_argument(
        "--themes-only",
        action="store_true",
        help="Render only theme tiles (no catalog)",
    )
    parser.add_argument(
        "--themes-smoke",
        action="store_true",
        help="With --themes/--themes-only, use THEME_CATALOG_SMOKE instead of full",
    )
    parser.add_argument(
        "--themes-bg",
        action="store_true",
        help="Render light/dark/B&W background theme smoke (diagram_theme prompt picks)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Offline validate_uml on fixtures (no Kroki / no sheet)",
    )
    args = parser.parse_args(argv)

    if args.themes_bg:
        fixtures = assemble_fixtures(catalog=False, themes_background=True)
    elif args.full:
        fixtures = assemble_fixtures(
            catalog=True,
            plantuml_kinds=True,
            mermaid_kinds=True,
            recipes=True,
            skills=True,
            prompts=True,
            themes=True,
            themes_full=not args.themes_smoke,
        )
    elif args.themes_only:
        fixtures = assemble_fixtures(
            catalog=False,
            themes=True,
            themes_full=not args.themes_smoke,
        )
    else:
        catalog = True if args.catalog is None else args.catalog
        any_extra = any(
            (
                args.plantuml_kinds,
                args.mermaid_kinds,
                args.recipes,
                args.skills,
                args.prompts,
                args.themes,
            )
        )
        fixtures = assemble_fixtures(
            catalog=catalog,
            plantuml_kinds=args.plantuml_kinds,
            mermaid_kinds=args.mermaid_kinds,
            recipes=args.recipes,
            skills=args.skills,
            prompts=args.prompts,
            themes=args.themes,
            themes_full=not args.themes_smoke,
        )
        if not fixtures and not any_extra:
            fixtures = assemble_fixtures(catalog=True)

    if args.validate_only:
        return _validate_only(fixtures)

    out_dir: Path = args.out
    if args.themes_bg and args.out == ROOT / ".tmp" / "catalog-images":
        out_dir = ROOT / ".tmp" / "catalog-themes-bg"
    if args.themes_only and args.out == ROOT / ".tmp" / "catalog-images":
        out_dir = ROOT / ".tmp" / "catalog-themes"
    out_dir.mkdir(parents=True, exist_ok=True)

    tiles: list[tuple[str, Image.Image]] = []
    errors: list[tuple[str, str]] = []

    for i, fx in enumerate(fixtures, 1):
        name = fx.get("label") or fx["diagram_type"]
        try:
            img = _render_tile(fx["diagram_type"], fx["code"], theme=fx.get("theme"))
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name)
            img.save(out_dir / f"{i:02d}-{safe}.png")
            tiles.append((name, img))
            print(f"OK {i:02d} {name} {img.size}")
        except Exception as exc:  # noqa: BLE001 - continue the sheet
            errors.append((name, str(exc)[:160]))
            print(f"FAIL {i:02d} {name}: {exc}")

    if not tiles:
        print("SHEET skipped (no tiles)")
        return 1

    sheet = _build_sheet(tiles)
    path = out_dir / "catalog-contact-sheet.png"
    try:
        sheet.save(path, "PNG")
    except OSError:
        path = out_dir / "catalog-contact-sheet-new.png"
        sheet.save(path, "PNG")
    print("SHEET", path, sheet.size, "tiles", len(tiles), "errors", len(errors))
    for name, err in errors:
        print("ERR", name, err)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
