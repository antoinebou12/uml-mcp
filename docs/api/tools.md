# MCP Tools Reference

**`generate_uml`** renders diagrams (optional save to disk). **`validate_uml`** checks inputs locally without calling Kroki. Both use the diagram types under `uml://types`; allowed output formats per type are in `uml://formats`.

## Rendering fallback

The server tries **Kroki** first. If Kroki fails or is unreachable, the pipeline can fall back to a **PlantUML server** (see `PLANTUML_SERVER` / `USE_LOCAL_PLANTUML` in [Configuration](../configuration.md)) or **Mermaid.ink** for Mermaid diagrams. On success, responses may include a `source` field (`kroki`, `plantuml_server`, or `mermaid_ink`) indicating which backend produced the image.

## `generate_uml`

Generates a diagram. Pass **`output_dir`** only when you need a file on disk; if you omit it, you get `url`, `playground`, and `content_base64` (no file write). On read-only deployments (`MCP_READ_ONLY=true`), `output_dir` is rejected—omit it and use URL/base64 only.

**Parameters:**

- `diagram_type` (string): Supported type (class, sequence, mermaid, d2, tikz, bpmn, graphviz, etc.). See `uml://types`.
- `code` (string): Diagram source in the syntax for that type.
- `output_dir` (string, optional): Directory to write the image. Omit for URL/base64 only.
- `output_format` (string, optional): svg, png, pdf, jpeg, txt, or base64 (default: svg). Allowed values depend on the diagram type; see `uml://formats`.
- `theme` (string, optional): PlantUML theme (e.g. cerulean) for PlantUML-based types.
- `scale` (number, optional): Scale factor for SVG only (default: 1.0, min: 0.1). Ignored for png, pdf, jpeg, etc.

**Returns:** JSON with `code`, `url`, `playground`; `local_path` when `output_dir` was set; `content_base64` when not saving; or `error` on failure.

**Example (save to disk):**

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

**Example (URL / base64 only):**

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

## `validate_uml`

Validates `diagram_type`, `code`, and `output_format` locally (no network). Use before `generate_uml` to catch unsupported types or formats.

**Parameters:** `diagram_type`, `code`, `output_format` (default `svg`).

## TikZ support

For `diagram_type: "tikz"`, `code` is TikZ/LaTeX source. You can pass a snippet (e.g. `\begin{tikzpicture}...\end{tikzpicture}`) or a full document; snippets are wrapped in a minimal standalone document. Supported output formats: **svg**, **pdf**, **png**, **jpeg**. Common TikZ libraries (e.g. shapes, arrows, positioning, pgfplots, automata) are inferred when possible. See [TikZ diagrams](../diagrams/tikz.md) for templates and examples.

**Example (TikZ):**

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
