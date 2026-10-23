"""Theme catalogs for diagram skills and MCP ``theme`` tool arguments.

PlantUML and Mermaid themes are applied by ``prepare_diagram_code``. D2 themes are
injected as ``vars.d2-config.theme-id`` when the source has no config yet. Other
backends document inline styling in per-type agent skills only.

Background-aware picks (light / dark-black / black-and-white) feed the
``diagram_theme`` MCP prompt and catalog smoke sheets.
"""

from __future__ import annotations

from mcp_core.core.mermaid_source import MERMAID_THEMES

#: Curated PlantUML built-ins (full enum lives in ``tools.kroki.plantuml_themes``).
PLANTUML_RECOMMENDED_THEMES: tuple[str, ...] = (
    "cerulean",
    "materia",
    "sketchy",
    "cyborg",
    "plain",
    "aws-orange",
    "blueprint",
    "sandstone",
)

#: Light / white page or chat canvas (pastel fills, dark ink).
PLANTUML_LIGHT_BG: tuple[str, ...] = (
    "cerulean",
    "materia",
    "plain",
    "sketchy",
    "sandstone",
    "minty",
    "spacelab",
)

#: Dark or black page (light strokes; avoid pale-on-white themes).
PLANTUML_DARK_BG: tuple[str, ...] = (
    "blueprint",
    "cyborg",
    "black-knight",
    "carbon-gray",
    "crt-green",
    "crt-amber",
    "hacker",
    "superhero",
)

#: True black-and-white / print (high contrast, little chroma).
PLANTUML_BW_BG: tuple[str, ...] = (
    "plain",
    "sketchy",
    "sketchy-outline",
    "mimeograph",
    "lightgray",
    "black-knight",
)

MERMAID_LIGHT_BG: tuple[str, ...] = ("default", "forest", "neutral", "base")
MERMAID_DARK_BG: tuple[str, ...] = ("dark",)
MERMAID_BW_BG: tuple[str, ...] = ("neutral", "base", "default")

D2_LIGHT_BG: tuple[str, ...] = ("default", "0")
D2_DARK_BG: tuple[str, ...] = ("dark", "103")
D2_BW_BG: tuple[str, ...] = ("default", "0")

#: D2 playground / Kroki theme-id aliases accepted by ``theme=``.
D2_THEME_ALIASES: dict[str, str] = {
    "default": "0",
    "0": "0",
    "dark": "103",
    "103": "103",
}

#: Catalog smoke cases: ``(diagram_type, theme)`` rendered with skill-documented themes.
THEME_CATALOG_SMOKE: tuple[tuple[str, str], ...] = (
    ("class", "cerulean"),
    ("sequence", "sketchy"),
    ("activity", "cerulean"),
    ("usecase", "plain"),
    ("state", "sandstone"),
    ("component", "blueprint"),
    ("deployment", "aws-orange"),
    ("object", "cerulean"),
    ("plantuml", "cyborg"),
    ("c4plantuml", "cerulean"),
    ("mermaid", "forest"),
    ("d2", "dark"),
)

#: Background-aware smoke: light, dark/black, and B/W print picks.
THEME_BG_CATALOG_SMOKE: tuple[tuple[str, str, str], ...] = (
    # (background, diagram_type, theme)
    ("light", "class", "cerulean"),
    ("light", "mermaid", "forest"),
    ("light", "sequence", "sketchy"),
    ("dark", "component", "blueprint"),
    ("dark", "plantuml", "cyborg"),
    ("dark", "mermaid", "dark"),
    ("dark", "d2", "dark"),
    ("dark", "c4plantuml", "black-knight"),
    ("bw", "class", "plain"),
    ("bw", "sequence", "sketchy"),
    ("bw", "usecase", "mimeograph"),
    ("bw", "mermaid", "neutral"),
    ("bw", "activity", "sketchy-outline"),
    ("bw", "state", "lightgray"),
)

#: Full visual-sheet matrix lives in ``scripts.catalog_sheet_fixtures.theme_catalog_full``
#: (every PlantUML built-in + all Mermaid themes + D2 aliases).

_BG_ALIASES = {
    "light": "light",
    "white": "light",
    "bright": "light",
    "dark": "dark",
    "black": "dark",
    "night": "dark",
    "bw": "bw",
    "b&w": "bw",
    "black-and-white": "bw",
    "black_and_white": "bw",
    "mono": "bw",
    "monochrome": "bw",
    "print": "bw",
    "grayscale": "bw",
    "grey": "bw",
    "gray": "bw",
}


def normalize_background(background: str | None) -> str:
    """Map free-text background to ``light``, ``dark``, or ``bw`` (default light)."""
    if not background:
        return "light"
    key = background.strip().lower().replace(" ", "-")
    return _BG_ALIASES.get(key, "light")


def themes_for_background(backend: str, background: str | None) -> tuple[str, ...]:
    """Recommended ``theme`` values for a backend + page background."""
    bg = normalize_background(background)
    family = backend if backend != "c4plantuml" else "plantuml"
    if family == "plantuml":
        return {
            "light": PLANTUML_LIGHT_BG,
            "dark": PLANTUML_DARK_BG,
            "bw": PLANTUML_BW_BG,
        }[bg]
    if family == "mermaid":
        return {
            "light": MERMAID_LIGHT_BG,
            "dark": MERMAID_DARK_BG,
            "bw": MERMAID_BW_BG,
        }[bg]
    if family == "d2":
        return {
            "light": D2_LIGHT_BG,
            "dark": D2_DARK_BG,
            "bw": D2_BW_BG,
        }[bg]
    return ()


def pick_theme(backend: str, background: str | None) -> str | None:
    """Default theme for a backend + background (first recommended pick)."""
    picks = themes_for_background(backend, background)
    return picks[0] if picks else None


def resolve_d2_theme_id(theme: str | None) -> str | None:
    """Return a numeric D2 theme-id, or None if ``theme`` is not a D2 theme."""
    if not theme:
        return None
    key = theme.strip().lower()
    if key in D2_THEME_ALIASES:
        return D2_THEME_ALIASES[key]
    if key.isdigit():
        return key
    return None


def theme_backends() -> frozenset[str]:
    """Backends that honour the MCP ``theme`` tool argument."""
    return frozenset({"plantuml", "c4plantuml", "mermaid", "d2"})


__all__ = [
    "D2_BW_BG",
    "D2_DARK_BG",
    "D2_LIGHT_BG",
    "D2_THEME_ALIASES",
    "MERMAID_BW_BG",
    "MERMAID_DARK_BG",
    "MERMAID_LIGHT_BG",
    "MERMAID_THEMES",
    "PLANTUML_BW_BG",
    "PLANTUML_DARK_BG",
    "PLANTUML_LIGHT_BG",
    "PLANTUML_RECOMMENDED_THEMES",
    "THEME_BG_CATALOG_SMOKE",
    "THEME_CATALOG_SMOKE",
    "normalize_background",
    "pick_theme",
    "resolve_d2_theme_id",
    "theme_backends",
    "themes_for_background",
]
