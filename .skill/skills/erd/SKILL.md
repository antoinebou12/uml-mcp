---
name: erd
description: >-
  Writes valid erd diagram source for uml-mcp (diagram_type=erd). Entity-relationship diagrams Use when the user asks for erd or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# erd diagram (uml-mcp)

**`diagram_type`:** `erd`  
**Backend:** `erd`  
**Output formats:** png, svg, jpeg, pdf

Entity-relationship diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Entity titles and attribute lists are the main visual cues; keep names short.
- No MCP `theme` param — layout clarity beats color.

## Starter template

```erd
[Person]
*name
height
weight

[Order]
*id
date

Person 1--* Order
```

## Example

```erd
[Person]
*name
height
weight

[Order]
*id
date

Person 1--* Order
```

## Render with uml-mcp

1. Set `diagram_type` to `erd` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
