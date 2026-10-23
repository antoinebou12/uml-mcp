---
name: rackdiag
description: >-
  Writes valid rackdiag diagram source for uml-mcp (diagram_type=rackdiag). Rack and server layout diagrams (blockdiag family) Use when the user asks for rackdiag or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# rackdiag diagram (uml-mcp)

**`diagram_type`:** `rackdiag`  
**Backend:** `rackdiag`  
**Output formats:** png, svg, pdf

Rack and server layout diagrams (blockdiag family)

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- `NU;` height and `[NU]` item sizes; keep labels ≤ rack width.
- No MCP `theme` param.

## Starter template

```rackdiag
rackdiag {
  16U;
  1: Server 1;
  2: Server 2;
  3: Switch;
}
```

## Example

```rackdiag
rackdiag {
  16U;
  1: UPS [2U];
  3: DB Server;
  4: Web Server;
  5: Web Server;
  6: Web Server;
  7: Load Balancer;
  8: L3 Switch;
}
```

## Render with uml-mcp

1. Set `diagram_type` to `rackdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
