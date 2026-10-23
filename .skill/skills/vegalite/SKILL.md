---
name: vegalite
description: >-
  Writes valid vegalite diagram source for uml-mcp (diagram_type=vegalite). Vega-Lite visualization grammar Use when the user asks for vegalite or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# vegalite diagram (uml-mcp)

**`diagram_type`:** `vegalite`  
**Backend:** `vegalite`  
**Output formats:** png, svg, pdf

Vega-Lite visualization grammar

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Use `config` + `mark.color` / encoding colors; set explicit `width`/`height`.
- No MCP `theme` param.

## Starter template

```vegalite
{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"a":1},{"a":2}]},"mark":"bar","encoding":{"x":{"field":"a","type":"quantitative"}}}
```

## Example

```vegalite
{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":[{"a":1,"b":2},{"a":2,"b":4}]},"mark":"point","encoding":{"x":{"field":"a","type":"quantitative"},"y":{"field":"b","type":"quantitative"}}}
```

## Render with uml-mcp

1. Set `diagram_type` to `vegalite` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
