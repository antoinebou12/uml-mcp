---
name: pikchr
description: >-
  Writes valid pikchr diagram source for uml-mcp (diagram_type=pikchr). Pikchr diagram scripting language Use when the user asks for pikchr or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# pikchr diagram (uml-mcp)

**`diagram_type`:** `pikchr`  
**Backend:** `pikchr`  
**Output formats:** svg

Pikchr diagram scripting language

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Use `color`, `fill`, `font` attributes on objects.
- No MCP `theme` param.

## Starter template

```pikchr
box "A" fit
arrow
box "B" fit
```

## Example

```pikchr
box "Service" fit
arrow
box "Database" fit
```

## Render with uml-mcp

1. Set `diagram_type` to `pikchr` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
