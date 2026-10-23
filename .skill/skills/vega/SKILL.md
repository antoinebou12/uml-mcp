---
name: vega
description: >-
  Writes valid vega diagram source for uml-mcp (diagram_type=vega). Vega visualization grammar Use when the user asks for vega or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# vega diagram (uml-mcp)

**`diagram_type`:** `vega`  
**Backend:** `vega`  
**Output formats:** png, svg, pdf

Vega visualization grammar

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Set `background`, `config.axis`, `config.view`, and mark `fill`/`stroke`.
- No MCP `theme` param.

## Starter template

```vega
{"$schema":"https://vega.github.io/schema/vega/v5.json","width":200,"height":200,"data":[{"name":"d","values":[{"v":1},{"v":2}]}],"marks":[{"type":"rect","from":{"data":"d"},"encode":{"enter":{"x":{"value":0},"y":{"scale":"y","field":"v"},"width":{"value":20},"height":{"scale":"y","band":1}}}}],"scales":[{"name":"y","type":"band","range":"height","domain":{"data":"d","field":"v"}}],"axes":[{"orient":"left","scale":"y","title":"v"}]}
```

## Example

```vega
{"$schema":"https://vega.github.io/schema/vega/v5.json","width":200,"height":200,"data":[{"name":"table","values":[{"x":1,"y":2},{"x":2,"y":4}]}],"scales":[{"name":"x","type":"linear","range":"width","nice":true,"domain":{"data":"table","field":"x"}},{"name":"y","type":"linear","range":"height","nice":true,"domain":{"data":"table","field":"y"}}],"axes":[{"orient":"bottom","scale":"x","title":"x"},{"orient":"left","scale":"y","title":"y"}],"marks":[{"type":"symbol","from":{"data":"table"},"encode":{"enter":{"x":{"scale":"x","field":"x"},"y":{"scale":"y","field":"y"},"size":{"value":50}}}}]}
```

## Render with uml-mcp

1. Set `diagram_type` to `vega` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
