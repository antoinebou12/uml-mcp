---
name: uml-mcp-diagrams
description: >-
  Creates diagrams via the uml-mcp MCP server (generate_uml, generate_uml_image,
  validate_uml, list_diagram_types, generate_uml_batch) and returns shareable
  Kroki URLs or inline chat images. Use when the user wants diagrams,
  PlantUML/Mermaid/D2/UML, URLs, Kroki, goat/umlet, or diagram_type.
---

> **Maintainers:** Keep tool tables and `output_dir` wording aligned with the Smithery bundle **[uml-skill/SKILL.md](https://github.com/antoinebou12/uml-skill/blob/main/SKILL.md)** (`diagramming-uml`) and the Claude Code plugin skill **`plugins/uml-mcp/skills/uml-diagrams/SKILL.md`** when you edit any of them.

# uml-mcp diagram workflow

## Goal

Turn the user’s intent into valid `diagram_type` + source `code`, call **generate_uml** (or **generate_uml_image** for chat-visible pictures), and surface the **`url`** (and **`playground`** when present). Prefer **URL-first** output (omit `output_dir` / use `null`) unless the user explicitly asks to save a file. When the user asks to **show the diagram in chat**, prefer **`generate_uml_image`** with `output_format: png`.

## Positive patterns (do)

- **Confirm types first** when unsure: read **`uml://types`** / **`uml://formats`** or call **`list_diagram_types`** before **`generate_uml`**. Catalog includes ~37 Kroki-backed types (including **`goat`**, **`umlet`**).
- **Match `diagram_type` to the language** of `code` (e.g. Mermaid body → `mermaid`; PlantUML with `@startuml` → `plantuml` or the specific Kroki PlantUML subtype if applicable).
- **Use `validate_uml`** before an expensive retry loop or when the user pastes untrusted LLM output. Prefer **`strict: true`** for Mermaid sequence diagrams.
- **Mermaid sequence**: put each statement on its **own line**. Do **not** pack `sequenceDiagram; participant A; A->>B: hi` on one line — strict validation rejects that; flowcharts may still use end-of-statement `;`.
- **Return the `url` plus a short copy of `code`** so the user can edit and regenerate.
- For **inline chat images**, call **`generate_uml_image`** (`png` default). It fetches bytes even on hosted Vercel when `MCP_URL_ONLY` is on. **`generate_uml`** with `output_format: png`/`jpeg` also force-fetches. SVG replies include a markdown `![diagram](url)` in the tool text for chat preview.
- When an LLM produces the diagram text first, prefer **fenced or raw** source that downstream tools accept; strip ``` fences from pasted input when needed, but still prefer clean DSL without prose **inside** the diagram.

## Negative patterns (avoid)

- **Do not invent** `diagram_type` or `output_format` values; confirm against **`uml://types`** / **`uml://formats`**.
- **Do not** set **`output_dir`** unless the user asked for files on disk (MCP).
- **Do not** mix human-readable essays **into** `code`—Kroki expects valid DSL only (prose belongs in the chat message, not inside PlantUML/Mermaid source).
- **Do not** pass invalid JSON for **`diagram_options`** when the API expects a JSON **object**—never use a bare array or malformed string.
- **Do not** pack Mermaid **`sequenceDiagram`** statements with `;` on a single physical line.
- Prefer not to stampede Mermaid-heavy **`generate_uml_batch`** calls on hosted MCP (server caps concurrency when most items are Mermaid); recover failed Mermaid items with solo **`generate_uml`**.
- **Do not** embed local filesystem paths like `output/foo.png` in chat markdown; use MCP image content or the returned HTTPS URL.
## Before generating

1. **If `diagram_type` is unknown or ambiguous**, read **`uml://types`** (or **`uml://capabilities`**) to list valid types and supported backends.
2. **For starter syntax**, use **`uml://templates`** or **`uml://examples`**; use **`resources/list`** for extra guides (e.g. named Mermaid samples, BPMN 2.0.2 reference) when those URIs are registered.
3. **Optional quality pass**: call **`validate_uml`** with the same `diagram_type`, `code`, and planned `output_format`. Use **`strict: true`** for stricter Mermaid/D2 checks when needed.
4. If you cannot read **`uml://types`**, call **`list_diagram_types`** for the same metadata.

## Complex requests

For ambiguous specs, large diagrams, or many actors/states/messages, plan before coding:

1. Use an **ordered plan** (participants, scope, emphasis), revise when wrong, and split the work when one diagram would be too large for a single canvas.
2. If the client exposes a **sequential-thinking** tool or an installed **sequential-thinking** skill, prefer it for that planning phase, then produce diagram source and call **`validate_uml`** / **`generate_uml`**.

## Readability (Kroki / DSL)

These rules apply to **diagram source** (Mermaid, PlantUML, D2, etc.), not to HTML layout:

- **Complexity**: Aim for roughly &lt;25 nodes in Mermaid and &lt;30 in PlantUML; fewer lifelines in sequence diagrams. If the user’s scope exceeds that, split into two diagrams or an overview plus a detail view.
- **Sequence**: Time flows **top → bottom**. Do not model upward message arrows. Use activation where the notation supports it (PlantUML `activate` / `deactivate`; Mermaid `activate` / `deactivate` when appropriate). Close every activation interval you open. Mermaid: **one statement per line**.
- **State and flowchart**: Label **every** transition or decision branch (event/guard or yes/no). Avoid drawing the same “to error” edge from every state; prefer one note, a group, or a single `*` / global exception path where the DSL allows.
- **Emphasis**: At most **one** strong visual highlight when the backend allows it (e.g. one Mermaid `classDef` / highlighted participant, one PlantUML `skinparam` / styled element, one D2 node style). Avoid rainbow or per-node rainbow fills — hierarchy and labels carry meaning.
- **Arrow overlap**: Set one layout direction (`flowchart TD`/`LR`, PlantUML `left to right direction` + `skinparam linetype ortho`, D2 `direction: right`), group related nodes (`subgraph` / `together { }` / D2 container), and use directional arrows (`-down->`, `-right->`) on edges that would otherwise cross. Canonical per-backend rules live in the `algorithm_explainer` and `paper_concept_diagram` prompt outputs (and `uml_diagram_with_thinking`).

## LLM prompt channels: positive vs negative

When the user (or pipeline) splits **positive** (must follow) and **negative** (must refuse) instructions for an LLM that emits diagram source, keep both sides short and non-overlapping.

| Channel | Purpose | Good content |
|---------|---------|----------------|
| **positive** | Additive constraints on the model | “Output only valid Mermaid.” “Use `sequenceDiagram`.” “One statement per line.” “No prose outside the diagram.” |
| **negative** | Things to refuse | “No markdown fences.” “No YAML front matter.” “No semicolon-packed sequenceDiagram lines.” “No explanation after the diagram.” |

**Positive pattern:** short, imperative, DSL-focused. **Negative pattern:** forbid specific failure modes you see in logs (fences, preamble, wrong diagram type keyword).

Do **not** duplicate the entire user spec in both positive and negative—negatives should be *exclusions*, not a second copy of the task.

## Prose around URLs

For **assistant-facing** explanations (summaries, caveats, next steps), you may use a **Humanizer** skill if it is installed in the client. Do **not** run humanizer output through diagram `code` — Kroki needs valid DSL only.

## Calling generate_uml

| Input | Guidance |
|-------|----------|
| `diagram_type` | Required. Must match a key from `uml://types` (e.g. `class`, `sequence`, `mermaid`, `d2`, `goat`, `umlet`). |
| `code` | Required. Source in the language that matches `diagram_type`. |
| `output_dir` | Omit or `null` for **URL-first** output (no write to disk; responses may include **`content_base64`** when no directory is set and URL-only mode is off). Set only if the user wants a saved image. |
| `output_format` | Default `svg` is usually best for URLs. Use **`png`/`jpeg`** when you want MCP `ImageContent` in chat (force-fetch even under URL-only). Mermaid raster uses mermaid.ink `/img/?type=png` (not `/png/`). |
| `theme` | PlantUML types only; omit otherwise. |
| `scale` | SVG only; optional size multiplier. |

## Calling generate_uml_image

Use when the user wants the **picture visible in chat** (Cursor, Copilot, ChatGPT image-capable clients).

| Input | Guidance |
|-------|----------|
| Same as `generate_uml` | `diagram_type`, `code`, optional `theme` / `scale` |
| `output_format` | Default **`png`** (widest client support); `svg` / `jpeg` also allowed |
| `output_dir` | Always omitted (memory-only) |

On hosted deployments with **`MCP_URL_ONLY=true`**, this tool still **force-fetches** rendered bytes so MCP **`ImageContent`** / `content_base64` is present. Prefer this over asking the user to open a URL when they asked to “show” or “render in chat”.

## generate_uml_batch

- Same per-item fields as `generate_uml` (no per-item `output_dir`).
- Env: **`MCP_BATCH_MAX_ITEMS`** (default 20), **`MCP_BATCH_CONCURRENCY`** (default 4, clamped 1–16).
- When a **majority** of items are Mermaid, the server caps workers at **2** to reduce Mermaid.ink stampedes on Vercel.
- Isolate failures per index; recover failed Mermaid items with solo **`generate_uml`**.

## After generating

1. If the result includes **`error`**, fix `code` or `diagram_type` / `output_format` and retry (or run **`validate_uml`** again). Prefer **`svg`** if hosted Mermaid PNG fails until the deployment includes the `/img/?type=png` fix.
2. Present clearly in the chat reply (always as markdown links, never bare paths):
   - **Diagram** — show the MCP image / `![diagram](url)` from the tool text.
   - **[URL](…)** — primary rendered diagram link (`url`).
   - **[Playground](…)** — interactive editor when `playground` is present (Mermaid → mermaid.live; PlantUML → plantuml.com). Always include this when the tool returns it.
   - **`local_path`** — only when `output_dir` was set.
3. Keep a short copy of the **`code`** in a fenced block so the user can edit and regenerate.

### Reply template

```markdown
![diagram](<url>)

- **URL:** <url>
- **Playground:** <playground>

\`\`\`mermaid
<code>
\`\`\`
```

## Choosing a language from intent

| User intent | Typical `diagram_type` |
|-------------|------------------------|
| Classes, associations, packages | `class` (PlantUML) or `mermaid` with classDiagram |
| Messages over time, lifelines | `sequence` or Mermaid sequence |
| Flows, swimlanes, BPMN | `activity`, `bpmn`, or Mermaid flowchart |
| Components, deployment | `component`, `deployment`, or C4-style types if listed in `uml://types` |
| Quick graphs, Gantt, pie | `mermaid` |
| Declarative layout / modern DSL | `d2` |
| ASCII box drawings, monospace diagrams | `ditaa`, `svgbob`, or **`goat`** (GoAT Markdeep-style ASCII → SVG) |
| UMLet UXF XML | **`umlet`** |

When several types fit, pick the one the user named; otherwise prefer the type with the clearest template in **`uml://templates`**.

## MCP tools and resources

- **Tools**: `generate_uml`, `generate_uml_image`, `validate_uml`, `list_diagram_types`, `generate_uml_batch`
- **Resources**: `uml://types`, `uml://formats`, `uml://templates`, `uml://examples`, `uml://capabilities`, `uml://recipes`, `uml://server-info`, `uml://workflow`, plus type-specific URIs from **`resources/list`** (named Mermaid samples, BPMN guide, …)

**Prompts** (when the client exposes them): `uml_diagram`, `uml_diagram_with_thinking`, and type-specific prompts (`class_diagram`, `sequence_diagram`, `activity_diagram`, `usecase_diagram`, `mermaid_sequence_api`, `mermaid_gantt`, `bpmn_process_guide`, `c4_model`, `wireviz_harness`, `bpmn_executable_process`, `convert_class_to_mermaid`, `algorithm_explainer`, `paper_concept_diagram`) help structure code before `generate_uml`.

Manual ChatGPT / client smoke prompts live under **`tests/prompts/`** (e.g. `chatgpt_mcp_smoke_test.md`).

Always use the **MCP tool/resource APIs** exposed in the environment; do not guess unsupported `diagram_type` or `output_format` values when unsure—confirm with `uml://types` / `uml://formats`.
