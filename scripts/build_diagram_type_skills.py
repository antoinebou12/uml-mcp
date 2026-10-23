"""Generate one agent skill per catalog ``diagram_type``.

Writes ``.skill/skills/<diagram_type>/SKILL.md`` from ``DIAGRAM_TYPES``,
``DiagramTemplates``, and ``DiagramExamples``. These are agent files for the
agent-skills index; they are not registered on MCP ``skills/list``.

Each skill includes a **Themes** or **Styling** section (PlantUML/Mermaid/D2
theme args, or inline style tips for other backends).

Run from the repo root::

    uv run python scripts/build_diagram_type_skills.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_core.core.config import DIAGRAM_TYPES
from mcp_core.core.diagram_themes import (
    MERMAID_THEMES,
    PLANTUML_RECOMMENDED_THEMES,
)
from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates

SKILLS_ROOT = ROOT / ".skill" / "skills"
MAX_DESCRIPTION = 500

#: Extra notation tips migrated from unpublished per-type MCP prompts.
NOTATION_TIPS: dict[str, str] = {
    "class": (
        "- Visibility: `+` public, `-` private, `#` protected.\n"
        "- Inheritance: empty triangle; composition filled diamond; "
        "aggregation empty diamond; multiplicities on associations.\n"
        "- Prefer `skinparam linetype ortho` and `left to right direction` "
        "when the graph is dense."
    ),
    "sequence": (
        "- Declare participants left-to-right in contact order; "
        "`autoactivate on`; `hide footbox` when no returns.\n"
        "- Messages top→bottom only; activate/deactivate pairs; notes for asides."
    ),
    "activity": (
        "- Use `start`/`stop`, decisions (`if`/`endif`), `fork`/`join`, "
        "and swimlanes when multiple actors.\n"
        "- Label every branch exit."
    ),
    "usecase": (
        "- Actors outside the system rectangle; use cases as ovals inside.\n"
        "- `<<include>>` / `<<extend>>` as dashed arrows; associations as solid lines."
    ),
    "mermaid": (
        "- Pick an opening kind: `flowchart`, `sequenceDiagram`, `classDiagram`, "
        "`stateDiagram-v2`, `erDiagram`, `gantt`, `pie`, `mindmap`.\n"
        "- One statement per line for `sequenceDiagram` (no `;`-packed lines).\n"
        "- API sequence: Client / API / optional Auth·DB with `alt` for errors.\n"
        "- Gantt: `title`, `dateFormat`, sections, `after` dependencies.\n"
        "- Class conversion: `classDiagram` with `<|--`, `*--`, `o--`, `-->`."
    ),
    "bpmn": (
        "- Prefer executable BPMN 2.0 XML with start, tasks, gateways, end, "
        "and `sequenceFlow` (see tutorials/bpmn.md).\n"
        "- Use `uml://templates` / `uml://examples` key `bpmn` as a starter."
    ),
    "c4plantuml": (
        "- Use PlantUML C4 includes; pick context or container view.\n"
        "- Keep relationships labeled; stay under ~30 elements or split views."
    ),
    "wireviz": (
        "- WireViz YAML: connectors, cables, colors, pins.\n"
        "- Keep harness size modest; one connector family per diagram when possible."
    ),
    "svgbob": (
        "- Prefer axis-aligned `+---+` boxes and `---->` arrows; diagonal `/ \\` "
        "\"balloon\" shapes often mis-render in Kroki's svgbob.\n"
        "- Keep labels short; pad with spaces so left/right edges stay aligned.\n"
        "- One horizontal pipeline (Client → MCP → Kroki) reads best in chat thumbnails.\n"
        "- Good for quick architecture sketches; use PlantUML/Mermaid for formal UML."
    ),
    "nomnoml": (
        "- Directive lines start with `#` (`#direction: down`, `#fill: #eee8d5`, "
        "`#stroke: #33322E`, `#lineWidth: 2`, `#padding: 12`, `#fontSize: 14`).\n"
        "- Nodes are `[Label]`; edges `->`, `<->`, `--`; classifiers "
        "`[<actor> User]`, `[<database> DB]`, `[<package> P]`.\n"
        "- One vertical stack (`#direction: down`) reads better in chat thumbnails.\n"
        "- Prefer warm fill + dark stroke (Solarized-ish) so labels stay legible after PNG."
    ),
    "nwdiag": (
        "- Declare `network name { address = \"…\"; node [address = \"…\"]; }` blocks.\n"
        "- Reuse the same node id in two networks to draw a gateway between them.\n"
        "- Prefer short node ids (`mcp`, `gateway`); put detail in `address` / `description`.\n"
        "- Two networks (DMZ + internal) with a shared gateway is the clearest default layout."
    ),
    "umlet": (
        "- Source is UMLet UXF XML (`<umlet_diagram>` + `<element>` with "
        "`panel_attributes`).\n"
        "- Class boxes: name, `--`, then attributes/methods. Visibility is a **single** "
        "`+` / `-` / `#` (never `++` — UMLet treats `++` as invalid and clips).\n"
        "- Size `<w>` ≥ ~8× longest line length (zoom 10) or labels clip at the box edge."
    ),
    "symbolator": (
        "- Input is a Verilog/SystemVerilog module; Symbolator draws the pin symbol.\n"
        "- Group ports with `//# {{group|Title}}` before related ports "
        "(e.g. `clocks`, `ctrl`, `data`).\n"
        "- Name clocks `clk` and active-low resets `rst_n` so wedges render; "
        "buses as `[7:0]`.\n"
        "- Put inputs on the left groups and outputs on the right of the last group "
        "for a readable IC-style symbol."
    ),
}

#: Per-type styling when the backend has no MCP ``theme`` argument.
STYLING_TIPS: dict[str, str] = {
    "graphviz": (
        "- Use `bgcolor`, `color`, `fillcolor`, `fontname`, `style=filled` on "
        "`graph`/`node`/`edge`.\n"
        "- Example: `node [shape=box, style=filled, fillcolor=\"#E8F4FC\"];`"
    ),
    "erd": (
        "- Entity titles and attribute lists are the main visual cues; keep names short.\n"
        "- No MCP `theme` param — layout clarity beats color."
    ),
    "blockdiag": (
        "- Optional `default_shape`, `node_width`, colors via `color = \"…\"` on nodes.\n"
        "- Keep to one row/column flow for chat thumbnails."
    ),
    "packetdiag": (
        "- Field lengths drive the layout; label every span.\n"
        "- No MCP `theme` — use short field names for contrast."
    ),
    "actdiag": (
        "- Same family as blockdiag; label lanes and edges clearly.\n"
        "- No MCP `theme` param."
    ),
    "seqdiag": (
        "- Participant order left-to-right; keep messages short.\n"
        "- No MCP `theme` param."
    ),
    "nwdiag": (
        "- Network bars + short node ids read best on dark Kroki backgrounds.\n"
        "- No MCP `theme` — structure is the styling."
    ),
    "rackdiag": (
        "- `NU;` height and `[NU]` item sizes; keep labels ≤ rack width.\n"
        "- No MCP `theme` param."
    ),
    "bpmn": (
        "- BPMN XML has no Kroki theme switch; use clear task names and gateway labels.\n"
        "- Prefer executable BPMN 2.0 with `sequenceFlow`."
    ),
    "bytefield": (
        "- Use `(defattrs … {:fill \"#…\"})` for row colors.\n"
        "- No MCP `theme` param."
    ),
    "dbml": (
        "- Table/column names and `ref:` drive the diagram; no color theme API.\n"
        "- Keep PK/FK annotations for scanability."
    ),
    "ditaa": (
        "- ASCII boxes + `{c}` / `{d}` color tags when needed.\n"
        "- No MCP `theme` param."
    ),
    "excalidraw": (
        "- Hand-drawn look is built-in; keep stroke colors high-contrast.\n"
        "- No MCP `theme` param."
    ),
    "goat": (
        "- ASCII art styling only; align in monospace.\n"
        "- No MCP `theme` param."
    ),
    "nomnoml": (
        "- Directives: `#fill`, `#stroke`, `#lineWidth`, `#fontSize`, `#padding`.\n"
        "- No MCP `theme` param — set colors in the source."
    ),
    "pikchr": (
        "- Use `color`, `fill`, `font` attributes on objects.\n"
        "- No MCP `theme` param."
    ),
    "structurizr": (
        "- Views + `autoLayout`; branding via Structurizr themes in the DSL when needed.\n"
        "- MCP `theme` is not applied for Structurizr."
    ),
    "svgbob": (
        "- Styling = ASCII geometry; prefer rounded `.--.` boxes for polish.\n"
        "- No MCP `theme` param."
    ),
    "symbolator": (
        "- Port groups color the symbol bands; naming drives clock/reset glyphs.\n"
        "- No MCP `theme` param."
    ),
    "tikz": (
        "- Use TikZ styles (`\\tikzset`) and `xcolor` for palettes.\n"
        "- No MCP `theme` param."
    ),
    "umlet": (
        "- UXF has no theme switch; sizing and `+`/`-`/`#` visibility are the polish.\n"
        "- No MCP `theme` param."
    ),
    "vega": (
        "- Set `background`, `config.axis`, `config.view`, and mark `fill`/`stroke`.\n"
        "- No MCP `theme` param."
    ),
    "vegalite": (
        "- Use `config` + `mark.color` / encoding colors; set explicit `width`/`height`.\n"
        "- No MCP `theme` param."
    ),
    "wavedrom": (
        "- Signal names and `skin` (when supported by the renderer) control look.\n"
        "- No MCP `theme` param."
    ),
    "wireviz": (
        "- Cable colors come from the YAML color names/codes.\n"
        "- No MCP `theme` param."
    ),
}


def _description(name: str, catalog_desc: str) -> str:
    text = (
        f"Writes valid {name} diagram source for uml-mcp "
        f"(diagram_type={name}). {catalog_desc.strip()} "
        f"Use when the user asks for {name} or that notation; then call "
        f"validate_uml / generate_uml / generate_uml_image."
    )
    text = " ".join(text.split())
    if len(text) <= MAX_DESCRIPTION:
        return text
    return text[: MAX_DESCRIPTION - 1].rstrip() + "…"


def _fence(lang: str, body: str) -> str:
    body = body.rstrip() + "\n"
    return f"```{lang}\n{body}```"


def _plantuml_theme_section() -> str:
    from mcp_core.core.diagram_themes import (
        PLANTUML_BW_BG,
        PLANTUML_DARK_BG,
        PLANTUML_LIGHT_BG,
    )

    themes = ", ".join(f"`{t}`" for t in PLANTUML_RECOMMENDED_THEMES)
    light = ", ".join(f"`{t}`" for t in PLANTUML_LIGHT_BG[:5])
    dark = ", ".join(f"`{t}`" for t in PLANTUML_DARK_BG[:5])
    bw = ", ".join(f"`{t}`" for t in PLANTUML_BW_BG[:5])
    return f"""## Themes

Pass **`theme`** to `generate_uml` / `generate_uml_image` (PlantUML built-in name).
The server injects `!theme <name>` after `@startuml` when the source has no `!theme` yet.

Recommended: {themes}.

Match the **page background** (also see MCP prompt **`diagram_theme`**):
- light / white: {light}
- dark / black: {dark}
- B&W / print: {bw}

Or embed in source:

```plantuml
@startuml
!theme cerulean
' … diagram …
@enduml
```
"""


def _mermaid_theme_section() -> str:
    themes = ", ".join(f"`{t}`" for t in sorted(MERMAID_THEMES))
    return f"""## Themes

Pass **`theme`** to `generate_uml` / `generate_uml_image`. Allowed values: {themes}.
The server prepends `%%{{init: {{'theme': '<name>'}}}}%%` when the source has no init/frontmatter theme.

Match the **page background** (MCP prompt **`diagram_theme`**):
- light / white: `default`, `forest`, `neutral`, `base`
- dark / black: `dark`
- B&W / print: `neutral`, `base`, `default`

```mermaid
%%{{init: {{'theme': 'forest'}}}}%%
sequenceDiagram
    A->>B: hello
```
"""


def _d2_theme_section() -> str:
    return """## Themes

Pass **`theme`** to `generate_uml` / `generate_uml_image` as `default` / `0` or `dark` / `103`
(or another numeric D2 `theme-id`). The server prefixes:

```d2
vars: {
  d2-config: {
    theme-id: 103
  }
}
```

when the source has no `d2-config` / `theme-id` yet. You can also set `theme-id` yourself.

Match the **page background** (MCP prompt **`diagram_theme`**):
- light / white / B&W: `default` (`0`)
- dark / black: `dark` (`103`)
"""


def _theme_or_styling_section(name: str, backend: str) -> str:
    if backend in ("plantuml", "c4plantuml"):
        return _plantuml_theme_section()
    if backend == "mermaid":
        return _mermaid_theme_section()
    if backend == "d2":
        return _d2_theme_section()
    tips = STYLING_TIPS.get(name)
    if tips:
        return f"## Styling\n\n{tips}\n"
    return (
        "## Styling\n\n"
        "- This backend has no MCP `theme` argument; keep labels short and high-contrast.\n"
    )


def render_skill(name: str) -> str:
    cfg = DIAGRAM_TYPES[name]
    backend = cfg.backend
    formats = ", ".join(cfg.formats)
    catalog_desc = cfg.description
    template = DiagramTemplates.get_template(name)
    example = DiagramExamples.get_example(name)
    fence_lang = backend if backend in ("mermaid", "plantuml", "d2") else name
    desc = _description(name, catalog_desc)
    tips = ""
    if name in NOTATION_TIPS:
        tips = f"## Notation tips\n\n{NOTATION_TIPS[name]}\n\n"
    theme_block = _theme_or_styling_section(name, backend)
    return f"""---
name: {name}
description: >-
  {desc}
---

# {name} diagram (uml-mcp)

**`diagram_type`:** `{name}`  
**Backend:** `{backend}`  
**Output formats:** {formats}

{catalog_desc}

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

{tips}{theme_block}
## Starter template

{_fence(fence_lang, template)}

## Example

{_fence(fence_lang, example)}

## Render with uml-mcp

1. Set `diagram_type` to `{name}` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
"""


def write_all(*, check: bool = False) -> int:
    """Write all type skills. With ``check=True``, exit 1 if any file would change."""
    dirty: list[str] = []
    for name in sorted(DIAGRAM_TYPES):
        path = SKILLS_ROOT / name / "SKILL.md"
        content = render_skill(name)
        encoded = content.encode("utf-8")
        if path.is_file() and path.read_bytes() == encoded:
            continue
        if check:
            dirty.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        print(f"Wrote {path.relative_to(ROOT)}")
    if check and dirty:
        print(
            "Stale diagram-type skills (re-run scripts/build_diagram_type_skills.py): "
            + ", ".join(dirty),
            file=sys.stderr,
        )
        return 1
    if check:
        print(f"OK: {len(DIAGRAM_TYPES)} diagram-type skills match the catalog")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    return write_all(check=check)


if __name__ == "__main__":
    raise SystemExit(main())
