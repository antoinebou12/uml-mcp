---
title: MCP tools
description: "generate_uml, validate_uml, list_diagram_types, generate_uml_batch: parameters, returns, examples."
tags:
  - reference
  - tools
---

# MCP Tools Reference

`generate_uml` renders diagrams and can save to disk. `validate_uml` checks inputs locally without calling Kroki. `list_diagram_types` returns the same metadata as the `uml://types` resource. `generate_uml_batch` renders several diagrams in one call (see [Configuration](../configuration.md) for `MCP_BATCH_MAX_ITEMS`). For diagram types and formats, use `uml://types` and `uml://formats`.

!!! tip "Looking for the underlying Python signatures?"

    Every tool is implemented in [`mcp_core.tools.diagram_tools`](../reference/python/tools.md). The auto-generated Python API page lists the live function signature, return type, and docstring from the source.

## Rendering fallback

The server tries Kroki first. If Kroki fails or is unreachable, the pipeline can use a PlantUML server (see `PLANTUML_SERVER` and `USE_LOCAL_PLANTUML` in [Configuration](../configuration.md)) or Mermaid.ink for Mermaid diagrams. Successful responses may include a `source` field (`kroki`, `plantuml_server`, or `mermaid_ink`) naming the backend that produced the image.

## `generate_uml`

Generates a diagram. Pass `output_dir` only when you need a file on disk; if you omit it, you get `url`, `playground`, and `content_base64` (no file write). On read-only deployments (`MCP_READ_ONLY=true`), `output_dir` is rejected; omit it and use URL/base64 only.

Parameters:

- `diagram_type` (string): Supported type (class, sequence, mermaid, d2, tikz, bpmn, graphviz, etc.). See `uml://types`.
- `code` (string): Diagram source in the syntax for that type.
- `output_dir` (string, optional): Directory to write the image. Omit for URL/base64 only.
- `output_format` (string, optional): svg, png, pdf, jpeg, txt, or base64 (default: svg). Allowed values depend on the diagram type; see `uml://formats`.
- `theme` (string, optional): PlantUML theme (e.g. cerulean) for PlantUML-based types.
- `scale` (number, optional): Scale factor for SVG only (default: 1.0, min: 0.1). Ignored for png, pdf, jpeg, etc.

Returns JSON with `code`, `url`, `playground`; `local_path` when `output_dir` was set; `content_base64` when not saving; or `error` on failure.

Example (save to disk):

```json
{
  "type": "tool",
  "name": "generate_uml",
  "args": {
    "diagram_type": "class",
    "code": "@startuml\nclass User\n@enduml",
    "output_dir": "./output"
  }
}
```

Example (URL / base64 only):

```json
{
  "type": "tool",
  "name": "generate_uml",
  "args": {
    "diagram_type": "mermaid",
    "code": "graph TD; A-->B;"
  }
}
```

## `list_diagram_types`

Returns a JSON object whose keys are diagram type names and whose values include `backend`, `description`, and `formats` (same as `uml://types`). No parameters.

## `generate_uml_batch`

Parameters:

- `items` (array of objects): each object supports the same fields as `generate_uml` except `output_dir` (not per item). Required: `diagram_type`, `code`. Optional: `output_format`, `theme`, `scale`.
- `output_dir` (string, optional): shared output directory for all items; omit for URL/base64 only.

Returns `{ "results": [ { "index": 0, ... }, ... ] }` where each entry matches `generate_uml` output or includes `error` for that index. Empty `items` or exceeding `MCP_BATCH_MAX_ITEMS` yields an `error` at the top level.

## `validate_uml`

Validates `diagram_type`, `code`, and `output_format` locally (no network). Use before `generate_uml` to catch unsupported types or formats.

Parameters: `diagram_type`, `code`, `output_format` (default `svg`), `strict` (boolean, default `false`). When `true`, applies extra Mermaid/D2 checks only (no extra PlantUML rules beyond existing `@startuml`/`@enduml` balance).

## TikZ support

For `diagram_type: "tikz"`, `code` is TikZ/LaTeX source. You can pass a snippet (e.g. `\begin{tikzpicture}...\end{tikzpicture}`) or a full document; snippets are wrapped in a minimal standalone document. Supported output formats: svg, pdf, png, jpeg. Common TikZ libraries (e.g. shapes, arrows, positioning, pgfplots, automata) are inferred when possible. See [TikZ diagrams](../diagrams/tikz.md) for templates and examples.

Example (TikZ):

```json
{
  "type": "tool",
  "name": "generate_uml",
  "args": {
    "diagram_type": "tikz",
    "code": "\\\\begin{tikzpicture}\\\\draw (0,0) circle (1cm);\\\\end{tikzpicture}",
    "output_format": "svg"
  }
}
```
