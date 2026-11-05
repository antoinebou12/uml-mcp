"""Generate skills for the bundled plugin diagram types.

* One agent skill per plugin ``diagram_type`` at ``.skill/skills/<diagram_type>/SKILL.md``
  (agent-skills index; not on MCP ``skills/list``), like the built-in types.
* One focused guide per plugin family, served over MCP through the existing template
  ``skill://uml-mcp-guides/{topic}/SKILL.md`` (no extra connect-time tokens) and mirrored,
  byte for byte, under ``.skill``, ``.github``, ``mcp_core`` and ``plugins/uml-mcp``.

Every example source is the plugin's own sample, so it always validates.

Run from the repo root::

    uv run python scripts/build_plugin_skills.py           # write
    uv run python scripts/build_plugin_skills.py --check   # fail if out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _name in ("d3", "stack-diagram", "archify", "llm-visualizer"):
    _src = ROOT / "examples" / "plugins" / f"uml-mcp-plugin-{_name}" / "src"
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SKILLS = ROOT / ".skill" / "skills"
GUIDE_BASES = (
    ".skill/skills",
    ".github/skills",
    "mcp_core/skills",
    "plugins/uml-mcp/skills",
)
MAX_DESCRIPTION = 500


def renderers() -> dict[str, Any]:
    from uml_mcp_plugin_archify import ArchifyRenderer
    from uml_mcp_plugin_d3 import D3Renderer
    from uml_mcp_plugin_llm_visualizer import LLMVisualizerRenderer
    from uml_mcp_plugin_stack_diagram import StackDiagramRenderer

    return {
        "d3": D3Renderer(),
        "stack-diagram": StackDiagramRenderer(),
        "archify": ArchifyRenderer(),
        "llm-visualizer": LLMVisualizerRenderer(),
    }


#: diagram_type -> (plugin, guide topic, when to use, example prompt, notation tips)
TYPES: dict[str, tuple[str, str, str, str, str]] = {
    "d3_force": (
        "d3",
        "d3-plugins",
        "a force-directed network or dependency graph",
        "Show our microservices as a force graph, grouped by team.",
        (
            "- `nodes` (`id`, `label`, `group`) and `links` (`from`, `to`, `label`).\n"
            "- Keep it under a few hundred nodes; the page lets readers drag and pin them."
        ),
    ),
    "d3_architecture": (
        "d3",
        "d3-plugins",
        "a cloud or system architecture with provider and brand logos",
        "Our AI app: Cloudflare in front of a Vercel app, a LangChain agent calling Claude, OpenAI and Gemini, Postgres for data.",
        (
            "- Node `service` keys draw real logos: `aws:s3`, `gcp:run`, `tech:claude`, `tech:github`, `tech:vercel`...\n"
            "- `groups` nest (`region` > `vpc` > `subnet`); `provider` is a top-level field, never a node field.\n"
            "- Call `d3_catalog` (when enabled) for every service key before writing source."
        ),
    ),
    "d3_topology": (
        "d3",
        "d3-plugins",
        "a deployment or network topology flowing top to bottom",
        "Draw our Kubernetes deployment: ingress, two services, a database and a cache, top to bottom.",
        (
            "- Same JSON as `d3_architecture`; the layout runs top to bottom.\n"
            "- Use zones and tiers as groups; ports (`inputs`, `outputs`) pin where arrows attach."
        ),
    ),
    "stack_diagram": (
        "stack-diagram",
        "stack-diagram",
        "a stack or cloud diagram with icon tiles, nested vendor and region groups",
        "Draw my stack: Next.js and Hono on Vercel, Neon Postgres, Clerk for auth, Stripe for payments, GitHub Actions deploys. Left to right.",
        (
            "- `nodes` (`id`, `name`, `role`, `icon`, `group`, `tag`), `groups` (`id`, `name`, `parent`, `style`), `edges` (`from`, `to`, `label`, `style`, `step`).\n"
            "- `icon` takes a brand (`github`, `vercel`, `aws`, `claude`...) for a real logo, or a glyph (`database`, `cache`, `queue`...).\n"
            "- `direction`: `LR`, `RL`, `TB`, `BT`. Add `step` numbers to show a request path."
        ),
    ),
    "archify_architecture": (
        "archify",
        "archify",
        "an architecture overview with colour-coded dashed groups, legend and presets",
        "Show our platform as an archify architecture with security, frontend, backend, message bus and database groups, blueprint preset.",
        (
            "- Group `style` sets the colour: `security`, `frontend`, `backend`, `bus`, `workers`, `database`, `cloud`, `external`.\n"
            "- `preset`: `classic`, `blueprint`, `flow`; `subtitle` and node `tag` (an owning team) add context.\n"
            "- Same `nodes`/`groups`/`edges` JSON as `stack_diagram`."
        ),
    ),
    "archify_workflow": (
        "archify",
        "archify",
        "a workflow or process with steps grouped into stages, top to bottom",
        "Draw our order fulfilment workflow: place order, take payment, pick and pack, ship, notify the customer.",
        (
            "- Same JSON as `archify_architecture`; flows top down by default.\n"
            "- Use groups for stages and `step` numbers on edges for the order of hand-offs."
        ),
    ),
    "archify_sequence": (
        "archify",
        "archify",
        "a sequence diagram of calls and replies between participants",
        "Sequence diagram of a cache-miss request through web, API, auth, Redis and Postgres.",
        (
            "- `participants` (`id`, `name`, `role`, `icon`, `tone`) and ordered `messages` (`from`, `to`, `label`, `style`, `note`).\n"
            '- `style: "dashed"` marks a reply; a message to the same participant draws a loop; `autonumber: true` numbers them.'
        ),
    ),
    "llm_2d": (
        "llm-visualizer",
        "llm-visualizer",
        "a neural network or LLM architecture as a 2D map, or an autoencoder, VAE or GAN",
        "Draw a transformer with encoder and decoder blocks repeated 6 times, top to bottom.",
        (
            "- `layers` (`id`, `label`, `kind`, `shape`, `repeat`, `group`) and `connections` (`from`, `to`, `label`, `style`).\n"
            '- `layout: "flow"` draws shaped kinds: `encoder`/`decoder` trapezoids, `bottleneck`, `vector`, `decision`, `token`.\n'
            "- `groups` (`id`, `label`, `repeat`) draw `N×` containers; `direction`: `LR` or `TB`."
        ),
    ),
    "llm_3d": (
        "llm-visualizer",
        "llm-visualizer",
        "the same model as a rotatable 3D scene of glass layer panels",
        "Show the transformer as a 3D scene I can rotate.",
        (
            "- Same JSON as `llm_2d`; the page switches between 2D and 3D.\n"
            "- `repeat` stacks panels; groups become tinted slabs on the floor."
        ),
    ),
}

#: topic -> (description, title, short intro). d3-plugins already exists; it is not generated.
GUIDES: dict[str, tuple[str, str, str]] = {
    "stack-diagram": (
        "Draw auto-laid-out stack and cloud architecture diagrams with real logos (stack_diagram).",
        "Stack diagrams",
        (
            "Icon tiles on engineered paper, nested vendor and region groups and labelled right-angled "
            "edges, laid out for you left to right, right to left, top down or bottom up."
        ),
    ),
    "archify": (
        "Draw archify architecture, workflow and sequence diagrams with colour-coded groups.",
        "Archify diagrams",
        (
            "Dashed, colour-coded containers, icon cards, a legend and three presets. The page lets "
            "readers click a node to focus it and shift-click another for the shortest path."
        ),
    ),
    "llm-visualizer": (
        "Draw LLM and neural-network architectures in 2D and 3D (llm_2d, llm_3d).",
        "LLM visualizer",
        (
            "Layer maps, autoencoder and GAN shapes, grouped N× blocks, and a rotatable 3D scene from "
            "one JSON source."
        ),
    ),
}


def _compact(source: str) -> str:
    return json.dumps(json.loads(source), separators=(",", ":"), ensure_ascii=False)


def type_skill(name: str, spec: Any) -> str:
    plugin, topic, when, prompt, tips = TYPES[name]
    description = (
        f"Writes valid {name} JSON for uml-mcp (diagram_type={name}, bundled plugin {plugin}). "
        f"Use when the user asks for {when}; then call validate_uml, then generate_uml_image "
        "(chat PNG) or generate_uml with output_format html (interactive MCP App page)."
    )
    assert len(description) <= MAX_DESCRIPTION, name
    formats = ", ".join(spec.formats)
    return (
        "---\n"
        f"name: {name}\n"
        "description: >-\n"
        f"  {description}\n"
        "---\n\n"
        f"# {name} diagram (uml-mcp plugin `{plugin}`)\n\n"
        f"**`diagram_type`:** `{name}`  \n"
        f"**Backend:** `plugin:{plugin}` (bundled with uml-mcp, on by default)  \n"
        f"**Output formats:** {formats}\n\n"
        f"{spec.description}\n\n"
        "Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the "
        f"focused guide `skill://uml-mcp-guides/{topic}/SKILL.md`. This file is notation only; "
        "it does not add an MCP tool.\n\n"
        "## Example prompt\n\n"
        f"> {prompt}\n\n"
        "## Notation tips\n\n"
        f"{tips}\n\n"
        "## Styling\n\n"
        "Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, "
        "or set it in the source. `auto` follows the reader's system in the HTML page and is dark "
        "in static SVG and PNG.\n\n"
        "## Example source\n\n"
        "```json\n"
        f"{_compact(spec.example)}\n"
        "```\n"
    )


def guide(topic: str, specs: dict[str, Any]) -> str:
    description, title, intro = GUIDES[topic]
    names = [t for t, v in TYPES.items() if v[1] == topic]
    rows = "\n".join(f"| `{t}` | {TYPES[t][2]} | {TYPES[t][3]} |" for t in names)
    first = names[0]
    return (
        "---\n"
        f"name: uml-mcp-{topic}\n"
        f"description: {description}\n"
        "---\n\n"
        f"# {title}\n\n"
        "Follow `skill://uml-mcp-diagrams/SKILL.md`. "
        f"{intro}\n\n"
        "## Types\n\n"
        "| Type | Use for | Example prompt |\n"
        "| --- | --- | --- |\n"
        f"{rows}\n\n"
        "## Steps\n\n"
        "1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are "
        "on by default, but a server may turn them off with `plugins.bundled: false`.\n"
        "2. Read the type's example from `uml://examples` and keep its field names.\n"
        "3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known "
        "ids, so fix it and validate again.\n"
        "4. Render with `generate_uml_image` for a chat image, or `generate_uml` with "
        '`output_format: "html"` for the interactive page in the MCP App viewer. Clients without '
        "MCP Apps still get the PNG and SVG.\n"
        "5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.\n\n"
        "## Example\n\n"
        "```json\n"
        f"{_compact(specs[first].example)}\n"
        "```\n"
    )


def outputs() -> dict[Path, str]:
    specs: dict[str, Any] = {}
    for renderer in renderers().values():
        specs.update(renderer.diagram_types)
    missing = set(specs) - set(TYPES)
    assert not missing, f"add skills metadata for: {sorted(missing)}"
    out: dict[Path, str] = {
        SKILLS / name / "SKILL.md": type_skill(name, specs[name]) for name in TYPES
    }
    for topic in GUIDES:
        text = guide(topic, specs)
        for base in GUIDE_BASES:
            out[ROOT / base / f"uml-mcp-{topic}" / "SKILL.md"] = text
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        if check:
            stale.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    if stale:
        print(
            "Out of date (run scripts/build_plugin_skills.py):\n  " + "\n  ".join(stale)
        )
        return 1
    print(f"OK: {len(TYPES)} plugin type skills and {len(GUIDES)} guides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
