"""A small pictogram for every layer kind, in a unit box, shared by the SVG and the page.

Each glyph is a list of primitives with coordinates from 0 to 1. Fills use the layer's
colour at the given opacity ``o``; ``path`` primitives are stroked polylines. The static
SVG renders them with :func:`glyph_svg`; the interactive page receives the same data and
draws it on the canvas, so both show the same shapes.
"""

from __future__ import annotations

import math
from html import escape
from typing import Any

Glyph = list[dict[str, Any]]


def _rect(x: float, y: float, w: float, h: float, o: float, r: float = 0.0) -> dict:
    return {"t": "rect", "x": x, "y": y, "w": w, "h": h, "o": round(o, 2), "r": r}


def _poly(points: list[tuple[float, float]], o: float) -> dict:
    return {"t": "poly", "p": [list(p) for p in points], "o": o}


def _path(points: list[tuple[float, float]]) -> dict:
    return {"t": "path", "p": [[round(x, 3), round(y, 3)] for x, y in points]}


def _ellipse(x: float, y: float, rx: float, ry: float, o: float) -> dict:
    return {"t": "ellipse", "x": x, "y": y, "rx": rx, "ry": ry, "o": o}


def _bell() -> Glyph:
    curve = [
        (x, 0.88 - 0.72 * math.exp(-(((x - 0.5) / 0.15) ** 2) / 2))
        for x in (i / 20 for i in range(1, 20))
    ]
    return [_path([(0.05, 0.88), (0.95, 0.88)]), _path(curve)]


GLYPHS: dict[str, Glyph] = {
    # a sequence of token chips
    "input": [
        _rect(0.02 + 0.25 * k, 0.36, 0.2, 0.28, 1 - 0.2 * k, 0.3) for k in range(4)
    ],
    # a lookup table with the active row lit
    "embedding": [
        _rect(0.1 + 0.28 * c, 0.06 + 0.23 * r, 0.24, 0.19, 1 if r == 1 else 0.3)
        for r in range(4)
        for c in range(3)
    ],
    # a causal attention mask: the lower triangle of a score matrix
    "attention": [
        _rect(
            0.04 + 0.24 * j,
            0.04 + 0.24 * i,
            0.2,
            0.2,
            0.3 + 0.7 * ((i * 3 + j * 5) % 7) / 6,
        )
        for i in range(4)
        for j in range(i + 1)
    ],
    # up-projection then down-projection
    "feedforward": [
        _poly(
            [
                (0, 0.34),
                (0.3, 0.06),
                (0.7, 0.06),
                (1, 0.34),
                (1, 0.66),
                (0.7, 0.94),
                (0.3, 0.94),
                (0, 0.66),
            ],
            0.55,
        ),
        _path([(0.3, 0.06), (0.3, 0.94)]),
        _path([(0.7, 0.06), (0.7, 0.94)]),
    ],
    # a normalised distribution
    "normalization": _bell(),
    # the residual sum
    "residual": [
        _ellipse(0.5, 0.5, 0.42, 0.42, 0.25),
        _path([(0.5, 0.2), (0.5, 0.8)]),
        _path([(0.2, 0.5), (0.8, 0.5)]),
    ],
    # a gate that sends tokens one way or another
    "router": [
        _poly([(0.5, 0.06), (0.94, 0.5), (0.5, 0.94), (0.06, 0.5)], 0.5),
        _path([(0.5, 0.06), (0.5, 0.94)]),
    ],
    # a pool of experts, one selected
    "expert": [
        _rect(
            0.06 + 0.48 * c,
            0.06 + 0.48 * r,
            0.4,
            0.4,
            1 if (r, c) == (1, 0) else 0.3,
            0.12,
        )
        for r in range(2)
        for c in range(2)
    ],
    # a store (KV cache, retrieval memory)
    "memory": [
        _rect(0.15, 0.2, 0.7, 0.6, 0.4),
        _ellipse(0.5, 0.8, 0.35, 0.12, 0.4),
        _ellipse(0.5, 0.2, 0.35, 0.12, 0.9),
    ],
    # a softmax over the vocabulary
    "output": [
        _path([(0.02, 0.95), (0.98, 0.95)]),
        *(
            _rect(0.06 + 0.18 * k, 0.95 - h, 0.14, h, 0.85 if h > 0.6 else 0.5)
            for k, h in enumerate((0.34, 0.82, 0.5, 0.24, 0.14))
        ),
    ],
    "encoder": [_poly([(0.05, 0.05), (0.95, 0.27), (0.95, 0.73), (0.05, 0.95)], 0.6)],
    "decoder": [_poly([(0.05, 0.27), (0.95, 0.05), (0.95, 0.95), (0.05, 0.73)], 0.6)],
    "bottleneck": [_rect(0.3, 0.3, 0.4, 0.4, 0.85)],
    "vector": [_rect(0.4, 0.05, 0.2, 0.9, 0.75)],
    "decision": [_ellipse(0.5, 0.5, 0.4, 0.4, 0.6)],
    "generic": [_rect(0.1, 0.1, 0.8, 0.8, 0.35, 0.2)],
}
GLYPHS["token"] = GLYPHS["input"]


def glyph_svg(kind: str, color: str, x: float, y: float, size: float) -> str:
    """The glyph for ``kind`` as SVG elements inside the box at ``x``, ``y``."""
    out = []
    c = escape(color, quote=True)
    for g in GLYPHS.get(kind, GLYPHS["generic"]):
        if g["t"] == "rect":
            r = f' rx="{g["r"] * g["w"] * size:.1f}"' if g["r"] else ""
            out.append(
                f'<rect x="{x + g["x"] * size:.1f}" y="{y + g["y"] * size:.1f}" '
                f'width="{g["w"] * size:.1f}" height="{g["h"] * size:.1f}"{r} '
                f'fill="{c}" fill-opacity="{g["o"]}"/>'
            )
        elif g["t"] == "ellipse":
            out.append(
                f'<ellipse cx="{x + g["x"] * size:.1f}" cy="{y + g["y"] * size:.1f}" '
                f'rx="{g["rx"] * size:.1f}" ry="{g["ry"] * size:.1f}" '
                f'fill="{c}" fill-opacity="{g["o"]}" stroke="{c}"/>'
            )
        else:
            pts = " ".join(
                f"{x + px * size:.1f},{y + py * size:.1f}" for px, py in g["p"]
            )
            if g["t"] == "poly":
                out.append(
                    f'<polygon points="{pts}" fill="{c}" fill-opacity="{g["o"]}" stroke="{c}"/>'
                )
            else:
                out.append(
                    f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2" '
                    'stroke-linecap="round" stroke-linejoin="round"/>'
                )
    return f'<g class="glyph">{"".join(out)}</g>'
