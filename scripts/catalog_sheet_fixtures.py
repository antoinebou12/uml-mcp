"""Extra contact-sheet fixtures: PlantUML/Mermaid kinds, skills, prompts, themes.

Used by ``scripts/build_catalog_sheet.py``. Keeps stress catalog fixtures unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from mcp_core.core.config import DIAGRAM_TYPES
from mcp_core.core.diagram_themes import (
    D2_THEME_ALIASES,
    MERMAID_THEMES,
    THEME_BG_CATALOG_SMOKE,
    THEME_CATALOG_SMOKE,
)
from mcp_core.resources.diagram_resources import get_diagram_recipes
from tools.kroki.kroki_templates import DiagramExamples
from tools.kroki.plantuml_themes import THEMES

#: PlantUML catalog subtypes (UML + raw + C4).
PLANTUML_CATALOG_TYPES: tuple[str, ...] = tuple(
    name
    for name, info in DIAGRAM_TYPES.items()
    if info.backend in ("plantuml", "c4plantuml")
)

#: Extra PlantUML diagram kinds rendered with ``diagram_type=plantuml``.
PLANTUML_EXTRA_KINDS: list[dict[str, str]] = [
    {
        "diagram_type": "plantuml",
        "label": "plantuml:timing",
        "code": """@startuml
robust "Web UI" as W
concise "API" as A
@0
W is Idle
A is Idle
@100
W is Busy
A is Processing
@200
W is Idle
A is Idle
@enduml""",
    },
    {
        "diagram_type": "plantuml",
        "label": "plantuml:salt",
        "code": """@startsalt
{
  Login
  [Username     ]
  [Password     ]
  [Cancel] | [OK]
}
@endsalt""",
    },
    {
        "diagram_type": "plantuml",
        "label": "plantuml:mindmap",
        "code": """@startmindmap
* UML-MCP
** Tools
*** generate_uml
*** validate_uml
** Backends
*** PlantUML
*** Mermaid
@endmindmap""",
    },
    {
        "diagram_type": "plantuml",
        "label": "plantuml:wbs",
        "code": """@startwbs
* Diagram pipeline
** Discover
** Validate
** Render
*** Kroki
*** Fallback
@endwbs""",
    },
    {
        "diagram_type": "plantuml",
        "label": "plantuml:gantt",
        "code": """@startgantt
Project starts 2026-01-01
[Discover] lasts 2 days
[Validate] lasts 3 days and starts at [Discover]'s end
[Render] lasts 4 days and starts at [Validate]'s end
@endgantt""",
    },
]

#: Mermaid diagram kinds (single backend; opening directive varies).
MERMAID_KIND_FIXTURES: list[dict[str, str]] = [
    {
        "diagram_type": "mermaid",
        "label": "mermaid:flowchart",
        "code": "flowchart LR\n  Client --> MCP --> Kroki\n  Kroki --> MCP --> Client",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:sequence",
        "code": """sequenceDiagram
    participant U as User
    participant M as UML-MCP
    participant K as Kroki
    U->>M: generate_uml
    M->>K: render
    K-->>M: SVG
    M-->>U: url""",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:class",
        "code": """classDiagram
    class Diagram {
      +String type
      +String code
      +render() Result
    }
    class Result {
      +String url
    }
    Diagram --> Result""",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:state",
        "code": """stateDiagram-v2
    [*] --> Validate
    Validate --> Render: ok
    Validate --> Error: invalid
    Render --> [*]
    Error --> [*]""",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:er",
        "code": """erDiagram
    USER ||--o{ DIAGRAM : owns
    USER {
      int id
      string email
    }
    DIAGRAM {
      int id
      string type
    }""",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:gantt",
        "code": """gantt
    title Diagram pipeline
    dateFormat YYYY-MM-DD
    section Flow
    Discover :a1, 2026-01-01, 2d
    Validate :after a1, 3d
    Render   :after a1, 4d""",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:pie",
        "code": """pie showData
    title Render backends
    "Kroki" : 70
    "PlantUML" : 20
    "mermaid.ink" : 10""",
    },
    {
        "diagram_type": "mermaid",
        "label": "mermaid:mindmap",
        "code": """mindmap
  root((UML-MCP))
    Tools
      generate_uml
      validate_uml
    Formats
      PlantUML
      Mermaid""",
    },
]


#: PlantUML themes that current public Kroki rejects with a bare "Syntax Error?".
_KROKI_UNRELIABLE_PLANTUML_THEMES = frozenset({"materia", "materia-outline"})


def plantuml_theme_names() -> tuple[str, ...]:
    return tuple(
        t.value
        for t in THEMES
        if t.value != "none" and t.value not in _KROKI_UNRELIABLE_PLANTUML_THEMES
    )


def theme_catalog_full() -> tuple[tuple[str, str], ...]:
    """All built-in PlantUML themes + Mermaid + D2 aliases (for visual sheet)."""
    plantuml = tuple(("class", name) for name in plantuml_theme_names())
    mermaid = tuple(("mermaid", name) for name in sorted(MERMAID_THEMES))
    d2_names = sorted({k for k in D2_THEME_ALIASES if not k.isdigit()})
    d2 = tuple(("d2", name) for name in d2_names)
    return plantuml + mermaid + d2


def theme_fixtures(
    *, full: bool = True, background: bool = False
) -> list[dict[str, str]]:
    from scripts.run_vercel_kroki_stress import FIXTURES_1_20, FIXTURES_21_37

    code_by_type = {
        fx["diagram_type"]: fx["code"]
        for fx in list(FIXTURES_1_20) + list(FIXTURES_21_37)
    }
    out: list[dict[str, str]] = []
    if background:
        for bg, diagram_type, theme in THEME_BG_CATALOG_SMOKE:
            code = code_by_type.get(diagram_type)
            if not code:
                continue
            out.append(
                {
                    "diagram_type": diagram_type,
                    "code": code,
                    "theme": theme,
                    "label": f"theme:{bg}:{diagram_type}:{theme}",
                }
            )
        return out

    pairs = theme_catalog_full() if full else THEME_CATALOG_SMOKE
    for diagram_type, theme in pairs:
        code = code_by_type.get(diagram_type)
        if not code:
            continue
        out.append(
            {
                "diagram_type": diagram_type,
                "code": code,
                "theme": theme,
                "label": f"theme:{diagram_type}:{theme}",
            }
        )
    return out


def recipe_fixtures() -> list[dict[str, str]]:
    recipes = json.loads(get_diagram_recipes())
    return [
        {
            "diagram_type": str(recipe["diagram_type"]),
            "code": str(recipe["template"]),
            "label": f"recipe:{key}",
        }
        for key, recipe in recipes.items()
    ]


def skill_fixtures() -> list[dict[str, str]]:
    """One tile per catalog type using ``DiagramExamples`` (skill starter content)."""
    out: list[dict[str, str]] = []
    for name in DIAGRAM_TYPES:
        try:
            code = DiagramExamples.get_example(name)
        except Exception:  # noqa: BLE001, S112
            continue
        if not isinstance(code, str) or len(code.strip()) < 8:
            continue
        if "No specific example" in code:
            continue
        out.append(
            {
                "diagram_type": name,
                "code": code,
                "label": f"skill:{name}",
            }
        )
    return out


def prompt_fixtures() -> list[dict[str, str]]:
    """Representative renders for published prompts (+ demoted type helpers)."""
    recipes = {r["label"]: r for r in recipe_fixtures()}
    algo = recipes.get("recipe:algorithm_flowchart")
    paper = recipes.get("recipe:paper_concept")
    out: list[dict[str, str]] = [
        {
            "diagram_type": "class",
            "label": "prompt:uml_diagram",
            "code": (
                "@startuml\n"
                "skinparam linetype ortho\n"
                "left to right direction\n"
                "class Client\nclass UmlMcp\nclass Kroki\n"
                "Client --> UmlMcp : generate_uml\n"
                "UmlMcp --> Kroki : render\n"
                "@enduml"
            ),
        },
        {
            "diagram_type": "c4plantuml",
            "label": "prompt:architecture_report",
            "code": (
                "!include <C4/C4_Context>\n"
                "title Architecture report sample\n"
                'Person(user, "User")\n'
                'System(mcp, "UML MCP")\n'
                'System_Ext(kroki, "Kroki")\n'
                'Rel(user, mcp, "Uses")\n'
                'Rel(mcp, kroki, "Renders")'
            ),
        },
        # diagram_theme prompt — B&W / dark / light defaults
        {
            "diagram_type": "class",
            "theme": "plain",
            "label": "prompt:diagram_theme:bw",
            "code": (
                "@startuml\nclass Client\nclass Server\nClient --> Server\n@enduml"
            ),
        },
        {
            "diagram_type": "component",
            "theme": "blueprint",
            "label": "prompt:diagram_theme:dark",
            "code": (
                "@startuml\ncomponent [Web]\ncomponent [API]\n[Web] --> [API]\n@enduml"
            ),
        },
        {
            "diagram_type": "mermaid",
            "theme": "forest",
            "label": "prompt:diagram_theme:light",
            "code": "flowchart LR\n  Client --> MCP --> Kroki\n",
        },
    ]
    if algo:
        out.append({**algo, "label": "prompt:algorithm_explainer"})
    if paper:
        out.append({**paper, "label": "prompt:paper_concept_diagram"})
    # Demoted per-type prompts → still useful visual checks
    for name in (
        "class",
        "sequence",
        "activity",
        "usecase",
        "state",
        "component",
        "deployment",
        "object",
        "mermaid",
        "bpmn",
        "c4plantuml",
        "wireviz",
    ):
        if name not in DIAGRAM_TYPES:
            continue
        try:
            code = DiagramExamples.get_example(name)
        except Exception:  # noqa: BLE001, S112
            continue
        out.append(
            {
                "diagram_type": name,
                "code": code,
                "label": f"prompt:{name}_diagram",
            }
        )
    return out


def plantuml_subtype_fixtures(
    catalog_by_type: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Relabel PlantUML-family catalog tiles + extra PlantUML kinds."""
    out: list[dict[str, str]] = []
    for name in PLANTUML_CATALOG_TYPES:
        fx = catalog_by_type.get(name)
        if not fx:
            continue
        out.append(
            {
                "diagram_type": name,
                "code": fx["code"],
                "label": f"plantuml:{name}",
            }
        )
    out.extend(PLANTUML_EXTRA_KINDS)
    return out


def assemble_fixtures(
    *,
    catalog: bool = True,
    plantuml_kinds: bool = False,
    mermaid_kinds: bool = False,
    recipes: bool = False,
    skills: bool = False,
    prompts: bool = False,
    themes: bool = False,
    themes_full: bool = True,
    themes_background: bool = False,
) -> list[dict[str, Any]]:
    from scripts.run_vercel_kroki_stress import FIXTURES_1_20, FIXTURES_21_37

    base = list(FIXTURES_1_20) + list(FIXTURES_21_37)
    by_type = {fx["diagram_type"]: fx for fx in base}
    fixtures: list[dict[str, Any]] = []

    if catalog:
        fixtures.extend(dict(fx) for fx in base)
    if plantuml_kinds:
        fixtures.extend(plantuml_subtype_fixtures(by_type))
    if mermaid_kinds:
        fixtures.extend(dict(fx) for fx in MERMAID_KIND_FIXTURES)
    if recipes:
        fixtures.extend(recipe_fixtures())
    if skills:
        fixtures.extend(skill_fixtures())
    if prompts:
        fixtures.extend(prompt_fixtures())
    if themes_background:
        fixtures.extend(theme_fixtures(background=True))
    elif themes:
        fixtures.extend(theme_fixtures(full=themes_full))
    return fixtures


__all__ = [
    "MERMAID_KIND_FIXTURES",
    "PLANTUML_CATALOG_TYPES",
    "PLANTUML_EXTRA_KINDS",
    "assemble_fixtures",
    "plantuml_theme_names",
    "theme_catalog_full",
    "theme_fixtures",
]
