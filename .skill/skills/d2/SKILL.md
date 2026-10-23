---
name: d2
description: >-
  Writes valid d2 diagram source for uml-mcp (diagram_type=d2). A modern diagram scripting language Use when the user asks for d2 or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# d2 diagram (uml-mcp)

**`diagram_type`:** `d2`  
**Backend:** `d2`  
**Output formats:** svg

A modern diagram scripting language

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Themes

Pass **`theme`** to `generate_uml` / `generate_uml_image` as `default` / `0` or `dark` / `103`
(or another numeric D2 `theme-id`). The server prefixes:

```d2
vars: {
  d2-config: {
    theme-id: 103
  }
}
```

when the source has no `d2-config` / `theme-id` yet. You can also set `theme-id` yourself.

Match the **page background** (MCP prompt **`diagram_theme`**):
- light / white / B&W: `default` (`0`)
- dark / black: `dark` (`103`)

## Starter template

```d2
User -> System: Request
System -> User: Response
```

## Example

```d2
title: Request flow
User -> API: HTTP Request
API -> Database: Query
Database -> API: Result
API -> User: JSON Response
```

## Render with uml-mcp

1. Set `diagram_type` to `d2` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
