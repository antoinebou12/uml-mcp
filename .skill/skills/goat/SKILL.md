---
name: goat
description: >-
  Writes valid goat diagram source for uml-mcp (diagram_type=goat). GoAT ASCII art to SVG diagrams (Markdeep-style) Use when the user asks for goat or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# goat diagram (uml-mcp)

**`diagram_type`:** `goat`  
**Backend:** `goat`  
**Output formats:** svg

GoAT ASCII art to SVG diagrams (Markdeep-style)

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- ASCII art styling only; align in monospace.
- No MCP `theme` param.

## Starter template

```goat
.-------.
| Start +--->| End |
'-------'     '----'
```

## Example

```goat
.---.     .-.       .-.
| A +--->| 1 |<--->| B |
'---'     '-'       '-'
```

## Render with uml-mcp

1. Set `diagram_type` to `goat` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
