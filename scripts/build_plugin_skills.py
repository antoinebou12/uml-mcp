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
for _name in ("d3", "stack-diagram", "archify", "llm-visualizer", "schema", "deps", "statechart", "trace"):
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
    from uml_mcp_plugin_deps import DepsRenderer
    from uml_mcp_plugin_llm_visualizer import LLMVisualizerRenderer
    from uml_mcp_plugin_schema import SchemaRenderer
    from uml_mcp_plugin_stack_diagram import StackDiagramRenderer
    from uml_mcp_plugin_statechart import StatechartRenderer
    from uml_mcp_plugin_trace import TraceRenderer

    return {
        "d3": D3Renderer(),
        "stack-diagram": StackDiagramRenderer(),
        "archify": ArchifyRenderer(),
        "llm-visualizer": LLMVisualizerRenderer(),
        "schema": SchemaRenderer(),
        "deps": DepsRenderer(),
        "statechart": StatechartRenderer(),
        "trace": TraceRenderer(),
    }


#: diagram_type -> (plugin, guide topic, when to use, example prompt, notation tips)
TYPES: dict[str, tuple[str, str, str, str, str]] = {
    "d3_force": (
        "d3",
        "d3-plugins",
        "a force-directed network or dependency graph",
        "Show our microservices as a force graph, grouped by team.",
        (
            "- `nodes` (`id`, `label`, `group`, `service`, `docs`) and `links` (`source`, `target`, `label`).\n"
            "- `service` (`postgres`, `kafka`, `aws:lambda`, `database`) draws an icon in the circle and links its docs.\n"
            "- Keep it under a few hundred nodes; readers drag, pin, and click a node for its details."
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
            "- Call `d3_catalog` (when enabled) for every service key before writing source.\n"
            "- The `service` kind sets the shape (database cylinder, queue pipe, function slant, gateway chamfer) "
            "and the docs link a click opens; `docs` overrides it with your own `https://` page."
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
        "Draw a VAE: input image, encoder, 2D latent z, decoder, reconstruction.",
        (
            "- Each layer: `id`, `label`, `kind`, optional `shape` (e.g. `[784]`), `repeat`, `note`, `group`. "
            "`connections`: `from`, `to`, `label`, `style` (`solid`, `dashed`); omit them for a straight chain.\n"
            "- Set `kind` on every layer. Encoders are `encoder` (a trapezoid that narrows), decoders `decoder` "
            "(one that widens), a latent code `vector` (a bar) or `bottleneck` (a square), a sampler or "
            "classifier `decision` (a circle).\n"
            "- With an encoder, decoder, vector or bottleneck the layout switches to `flow` (shapes left to "
            'right); set `layout: "grid"` for cards, `direction: "TB"` for top down.\n'
            '- Give `shape` so each layer shows its size; label the edges with what flows (`"predict μ"`).\n'
            "- Branches share a column: connect the encoder to both a `mean` and a `log σ²` `vector` and both "
            "into the sampled `bottleneck` z, and they stack as two parallel heads.\n"
            "- `groups` (`id`, `label`, `repeat`) draw `N×` containers around repeated blocks."
        ),
    ),
    "llm_3d": (
        "llm-visualizer",
        "llm-visualizer",
        "the same model as a rotatable 3D scene: layer panels, with encoder and decoder funnels",
        "Show the VAE as a 3D scene I can rotate, encoder narrowing to the latent and decoder widening back.",
        (
            "- Same JSON as `llm_2d`; the page switches between 2D and 3D.\n"
            "- `encoder` and `decoder` layers become frustums that narrow and widen along the flow; other "
            "kinds are glass panels, `repeat` stacks them and groups become tinted slabs on the floor.\n"
            "- The static SVG/PNG is an oblique view with every label on one row under the solids."
        ),
    ),
    "db_schema": (
        "schema",
        "db-schema",
        "a database schema or ER diagram from SQL DDL or a list of tables",
        "Draw the schema of my shop database from this CREATE TABLE script.",
        (
            "- Paste SQL DDL as is: `CREATE TABLE` with `PRIMARY KEY`, `REFERENCES`, `FOREIGN KEY`, "
            "`UNIQUE`, `NOT NULL`, `DEFAULT` (Postgres, MySQL, SQLite); other statements are skipped.\n"
            "- Comment directives: `-- title: Shop`, `-- theme: dark`, `-- group: Billing` (tables below it "
            "go in a tinted container; `-- group:` ends it).\n"
            "- Or JSON: `tables` (`name`, `group`, `note`, `columns`: `name`, `type`, `pk`, `fk` "
            '`{"table","column"}` or `"table.column"`, `nullable`, `unique`, `note`) and optional '
            "`relations` (`from`, `to`, `kind`: `one-to-one`, `one-to-many`, `many-to-many`, `label`).\n"
            "- A unique or primary-key foreign key draws one-to-one; a table keyed by two foreign keys "
            "is marked as an M:N join table. `validate_uml` lists every bad reference with its line."
        ),
    ),
    "dependency_graph": (
        "deps",
        "deps",
        "the dependency tree of a project from its package.json, pyproject.toml, requirements.txt or a lock file",
        "Show the dependency tree of this project from its uv.lock, with dev dependencies and duplicate versions.",
        (
            "- Paste the file as it is: `package.json`, `package-lock.json` (v2/v3), `pyproject.toml`, "
            "`requirements.txt` or `uv.lock`; the kind is detected. A lock file adds the transitive levels.\n"
            "- Or write a graph: `root`, `nodes` (`id`, `version`, `license`, `dev`, `group`) and `edges` "
            "(`from`, `to`, `range`); a top-level `ecosystem` (`npm`, `pypi`) links each package to its registry.\n"
            "- Colours: runtime, dev, optional, peer. A dashed amber outline marks a package present in "
            "several versions.\n"
            "- Nothing is fetched: licences come from the lock file or the graph. Large locks are capped "
            "(300 packages by default, `plugins.settings.deps.max_nodes`)."
        ),
    ),
    "state_machine": (
        "statechart",
        "statechart",
        "a state machine or statechart (order lifecycle, traffic light, UI flow) to read or step through",
        (
            "Model our order lifecycle as a state machine: checkout with address and payment steps, "
            "packing and invoicing in parallel, cancelled and delivered as final states."
        ),
        (
            "- XState-like JSON: `id`, `title`, `initial`, `context`, `states`. Each state: `on` "
            "(`EVENT: target` or `{target, guard, actions}`, or a list of guarded alternatives), "
            "`entry`, `exit`, `type` (`atomic`, `compound`, `parallel`, `final`, `history`), "
            "`initial`, `states`, `description`, `onDone`.\n"
            "- Every compound state needs `initial`; a parallel state has none (all regions start).\n"
            "- Targets: a sibling name, a dotted path (`checkout.payment`), `.child`, or `#id.path`. "
            "A transition with no target runs its actions and stays (drawn inside the state).\n"
            '- `{"type": "history"}` in a compound remembers the last step; target it to resume '
            '(`"history": "deep"` for nested steps).\n'
            "- Guards are labels: the simulator shows one button per guarded alternative.\n"
            "- `direction`: `LR` (default) or `TB`. `validate_uml` warns about unreachable states."
        ),
    ),
    "agent_trace": (
        "trace",
        "agent-trace",
        "an agent run trace: LLM calls, tool calls, retrievals and sub-agents on a timeline with tokens and cost",
        "Show this agent run as a trace: the user question, a retrieval, two tool calls (one retried), the LLM calls and the reply, with tokens and cost.",
        (
            "- `steps`: `id`, `parent`, `kind` (`user`, `llm`, `tool`, `retrieval`, `subagent`, `guardrail`, "
            "`memory`, `reply`, `error`), `name`, `start_ms`, `end_ms` (relative to the run start).\n"
            "- Optional per step: `tokens` (`in`, `out`, `cached`), `cost_usd`, `model`, `tool`, `input`, "
            "`output`, `docs` (`title`, `score`, `source`), `status` (`ok`, `error`, `retry`), `note`.\n"
            "- Nest steps with `parent` (a sub-agent's calls under it); `end_ms` must not be before `start_ms` and ids are unique.\n"
            "- OpenTelemetry works too: `spans` with `span_id`, `parent_span_id`, `name`, `start`, `end` "
            "(ISO 8601 or epoch numbers) and GenAI `attributes` (`gen_ai.operation.name`, "
            "`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.tool.name`).\n"
            "- `svg` is the waterfall with a summary header; `html` adds a flow view, folding, step details and the critical path."
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
    "db-schema": (
        "Draw database schema (ER) diagrams from SQL DDL or JSON tables (db_schema).",
        "Database schema diagrams",
        (
            "Table cards with key, link, null and unique markers and crow's-foot relationships "
            "attached at the column rows, laid out by foreign-key direction with groups as tinted "
            "containers. The page focuses a table, traces a column's keys and searches."
        ),
    ),
    "deps": (
        "Draw dependency graphs from package.json, pyproject.toml, requirements.txt and lock files (dependency_graph).",
        "Dependency graphs",
        (
            "A layered tree from the project to its deepest dependency, coloured by kind (runtime, dev, "
            "optional, peer), with licences and duplicate versions flagged. The page searches, collapses, "
            "filters kinds, switches to a force graph and opens each package's PyPI or npm page."
        ),
    ),
    "statechart": (
        "Draw state machines as statecharts with a step-through simulator (state_machine).",
        "Statecharts",
        (
            "Rounded states, compound containers, parallel regions split by dashed lines, initial, "
            "final and history pseudo-states and labelled orthogonal transitions. The HTML page is a "
            "simulator: it highlights the active states and offers a button for every enabled event, "
            "with a step log, Undo and Reset."
        ),
    ),
    "agent-trace": (
        "Draw agent run traces with LLM, tool, retrieval and sub-agent steps on a timeline (agent_trace).",
        "Agent traces",
        (
            "A waterfall of an agent run with tokens, cost, errors and retries, and an interactive "
            "page with a flow view, folding sub-agents, a detail card per step and the critical path."
        ),
    ),
}


#: Extra guide sections, appended before the example.
GUIDE_EXTRAS: dict[str, str] = {
    "llm-visualizer": (
        "## Recipes\n\n"
        "| Model | Layers (`kind`) |\n"
        "| --- | --- |\n"
        "| Autoencoder | `input` → `encoder` → `bottleneck` → `decoder` → `output` |\n"
        "| VAE | `input` → `encoder` → two `vector` heads (μ, log σ²) → `bottleneck` (z = μ + σ ⊙ ε) → `decoder` → `output` |\n"
        "| GAN | `token` (noise) → `decoder` (generator) → `vector` (fake sample) → `decision` (discriminator); "
        "a `dashed` edge for real data |\n"
        "| Decoder-only LLM | `input` → `embedding` → `attention` and `feedforward` (`repeat: 32`) → "
        "`normalization` → `output`; a `dashed` residual edge |\n"
        "| Encoder-decoder transformer | two `groups` with `repeat: 6`: `encoder` and `decoder` layers inside, "
        "a cross-attention edge between them |\n\n"
        "Use `label` and `kind`. The parser also accepts `name` and `type` and infers a missing kind from "
        "the id and label (`encoder`, `decoder`, `latent`, `input`, `output`...), but explicit kinds give "
        'the shapes you expect. Give a `title` (the default is "Model architecture").\n\n'
        "```json\n"
        '{"title":"Variational autoencoder","layers":['
        '{"id":"x","label":"Input x","kind":"input","shape":[784]},'
        '{"id":"enc","label":"Encoder qφ(z|x)","kind":"encoder","shape":[256]},'
        '{"id":"mu","label":"Mean μ","kind":"vector","shape":[2]},'
        '{"id":"logvar","label":"Log variance log σ²","kind":"vector","shape":[2]},'
        '{"id":"z","label":"z = μ + σ ⊙ ε","kind":"bottleneck","shape":[2]},'
        '{"id":"dec","label":"Decoder pθ(x|z)","kind":"decoder","shape":[256]},'
        '{"id":"xr","label":"Reconstruction x̂","kind":"output","shape":[784]}],'
        '"connections":[{"from":"x","to":"enc"},{"from":"enc","to":"mu","label":"predict μ"},'
        '{"from":"enc","to":"logvar","label":"predict log σ²"},'
        '{"from":"mu","to":"z","label":"reparameterize"},'
        '{"from":"logvar","to":"z","label":"σ = exp(½ log σ²)"},'
        '{"from":"z","to":"dec"},{"from":"dec","to":"xr"}]}\n'
        "```\n\n"
    ),
    "deps": (
        "## Inputs\n\n"
        "| File | What it adds |\n"
        "| --- | --- |\n"
        "| `package.json` | Direct `dependencies`, `devDependencies`, `peerDependencies` and "
        "`optionalDependencies` with their ranges |\n"
        "| `package-lock.json` v2/v3 | The installed tree: versions, licences, dev/optional/peer flags |\n"
        "| `pyproject.toml` | PEP 621 `dependencies`, `optional-dependencies` (extras), "
        "`dependency-groups`, Poetry tables |\n"
        "| `requirements.txt` | Pins, ranges, extras and markers (`-r` includes are noted, not read) |\n"
        "| `uv.lock` | The resolved tree with extras, dev groups and the ranges asked for |\n"
        '| JSON graph | `{"root", "nodes": [{"id", "version", "license", "dev", "group"}], '
        '"edges": [{"from", "to", "range"}]}` |\n\n'
        "Send the file text as `code`. Validation names the file kind it detected and the line or "
        "field that failed.\n\n"
    ),
}


def _compact(source: str) -> str:
    return json.dumps(json.loads(source), separators=(",", ":"), ensure_ascii=False)


def _is_json(source: str) -> bool:
    return source.lstrip().startswith("{")


def _example(source: str) -> str:
    """A fenced block: compact JSON, or SQL DDL as written."""
    if _is_json(source):
        return f"```json\n{_compact(source)}\n```\n"
    return f"```sql\n{source.strip()}\n```\n"


def type_skill(name: str, spec: Any) -> str:
    plugin, topic, when, prompt, tips = TYPES[name]
    language = "JSON" if _is_json(spec.example) else "SQL DDL or JSON"
    description = (
        f"Writes valid {name} {language} for uml-mcp (diagram_type={name}, bundled plugin {plugin}). "
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
        f"{_example(spec.example)}"
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
        f"{GUIDE_EXTRAS.get(topic, '')}"
        "## Example\n\n"
        f"{_example(specs[first].example)}"
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
