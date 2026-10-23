---
name: wireviz
description: >-
  Writes valid wireviz diagram source for uml-mcp (diagram_type=wireviz). Cable and wiring diagrams Use when the user asks for wireviz or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# wireviz diagram (uml-mcp)

**`diagram_type`:** `wireviz`  
**Backend:** `wireviz`  
**Output formats:** png, svg

Cable and wiring diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- WireViz YAML: connectors, cables, colors, pins.
- Keep harness size modest; one connector family per diagram when possible.

## Styling

- Cable colors come from the YAML color names/codes.
- No MCP `theme` param.

## Starter template

```wireviz
connectors:
  P1:
    pinlabels: [GND, VCC]
  P2:
    pinlabels: [GND, VCC]
cables:
  C1:
    wirecount: 2
    gauge: 0.5 mm2
    length: 1
    colors: [BK, RD]
connections:
  -
    - P1: [1-2]
    - C1: [1-2]
    - P2: [1-2]
```

## Example

```wireviz
connectors:
  J1:
    pinlabels: [GND, VCC, SDA, SCL]
  J2:
    pinlabels: [GND, VCC, SDA, SCL]
cables:
  C1:
    wirecount: 4
    gauge: 0.25 mm2
    length: 0.5
    colors: [BK, RD, YE, GN]
connections:
  -
    - J1: [1-4]
    - C1: [1-4]
    - J2: [1-4]
```

## Render with uml-mcp

1. Set `diagram_type` to `wireviz` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
