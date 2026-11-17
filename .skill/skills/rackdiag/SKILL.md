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
  8U;
  1: UPS [2U, color = "#f4a261"];
  3: DB [color = "#2a9d8f"];
  4: App [color = "#264653"];
  5: LB [color = "#e76f51"];
  6: Switch [color = "#457b9d"];
}
```

## Example

```rackdiag
rackdiag {
  12U;
  default_fontsize = 11;

  1: UPS [2U, color = "#f4a261"];
  3: DB Primary [color = "#2a9d8f"];
  4: DB Replica [color = "#2a9d8f"];
  5: Redis Cache [color = "#e9c46a"];
  6: App Server [color = "#264653"];
  7: App Server [color = "#264653"];
  8: App Server [color = "#264653"];
  9: Load Balancer [color = "#e76f51"];
  10: L3 Switch [color = "#457b9d"];
  11: Firewall [color = "#1d3557"];
}
```

## Render with uml-mcp

1. Set `diagram_type` to `rackdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
