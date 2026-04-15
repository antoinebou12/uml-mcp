---
name: uml-mcp-diagrams
description: >-
  Creates diagrams via the uml-mcp MCP server (generate_uml, validate_uml,
  list_diagram_types, generate_uml_batch) and
  returns shareable Kroki URLs plus optional playground links. Use when the user
  wants a diagram, asks for PlantUML/Mermaid/D2/UML, wants a URL instead of a
  saved file, or mentions uml-mcp, Kroki, or diagram_type.
---

# uml-mcp diagram workflow

## Goal

Turn the user’s intent into valid `diagram_type` + source `code`, call **generate_uml**, and surface the **`url`** (and **`playground`** when present). Prefer **URL-only** output unless the user explicitly asks to save a file.

## Before generating

1. **If `diagram_type` is unknown or ambiguous**, read the **`uml://types`** resource (or **`uml://capabilities`**) to list valid types and supported backends.
2. **For starter syntax**, use **`uml://templates`** or **`uml://examples`**; for Mermaid specifics, **`uml://mermaid-examples`** when relevant.
3. **Optional quality pass**: call **`validate_uml`** with the same `diagram_type`, `code`, and planned `output_format` to catch local errors before render. Use **`strict: true`** for stricter Mermaid/D2 checks when needed.
4. If you cannot read **`uml://types`**, call **`list_diagram_types`** for the same metadata.

## Calling generate_uml

| Input | Guidance |
|-------|----------|
| `diagram_type` | Required. Must match a key from `uml://types` (e.g. `class`, `sequence`, `mermaid`, `d2`). |
| `code` | Required. Source in the language that matches `diagram_type`. |
| `output_dir` | Omit or `null` for **URL / base64 only** (no write to disk). Set only if the user wants a saved image. |
| `output_format` | Default `svg` is usually best for URLs; use `png`/`pdf`/`jpeg`/`txt` only if valid for that type (see **`uml://formats`**). |
| `theme` | PlantUML types only; omit otherwise. |
| `scale` | SVG only; optional size multiplier. |

## After generating

1. If the result includes **`error`**, fix `code` or `diagram_type` / `output_format` and retry (or run **`validate_uml`** again).
2. Present clearly:
   - **`url`** — primary Kroki link to the rendered diagram.
   - **`playground`** — if present, link for interactive editing.
   - **`local_path`** — only when `output_dir` was set.
3. Keep a short copy of the **`code`** in the reply so the user can edit and regenerate.

## Choosing a language from intent

| User intent | Typical `diagram_type` |
|-------------|------------------------|
| Classes, associations, packages | `class` (PlantUML) or `mermaid` with classDiagram |
| Messages over time, lifelines | `sequence` or Mermaid sequence |
| Flows, swimlanes, BPMN | `activity`, `bpmn`, or Mermaid flowchart |
| Components, deployment | `component`, `deployment`, or C4-style types if listed in `uml://types` |
| Quick graphs, Gantt, pie | `mermaid` |
| Declarative layout / modern DSL | `d2` |

When several types fit, pick the one the user named; otherwise prefer the type with the clearest template in **`uml://templates`**.

## MCP tools and resources

- **Tools**: `generate_uml`, `validate_uml`, `list_diagram_types`, `generate_uml_batch`
- **Resources**: `uml://types`, `uml://formats`, `uml://templates`, `uml://examples`, `uml://capabilities`, `uml://server-info`, `uml://mermaid-examples`, `uml://bpmn-guide`, `uml://workflow`

**Prompts** (when the client exposes them): `uml_diagram`, `uml_diagram_with_thinking`, and type-specific prompts (`class_diagram`, `sequence_diagram`, `activity_diagram`, `usecase_diagram`, `mermaid_sequence_api`, `mermaid_gantt`, `bpmn_process_guide`, `c4_model`, `wireviz_harness`, `bpmn_executable_process`, `convert_class_to_mermaid`) help structure code before `generate_uml`.

Always use the **MCP tool/resource APIs** exposed in the environment; do not guess unsupported `diagram_type` or `output_format` values when unsure—confirm with `uml://types` / `uml://formats`.
