---
name: dbml
description: >-
  Writes valid dbml diagram source for uml-mcp (diagram_type=dbml). Database Markup Language schema diagrams Use when the user asks for dbml or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# dbml diagram (uml-mcp)

**`diagram_type`:** `dbml`  
**Backend:** `dbml`  
**Output formats:** svg

Database Markup Language schema diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Table/column names and `ref:` drive the diagram; no color theme API.
- Keep PK/FK annotations for scanability.

## Starter template

```dbml
Table users {
  id int [pk]
  name varchar
}

Table posts {
  id int [pk]
  user_id int [ref: > users.id]
}
```

## Example

```dbml
Table users {
  id int [pk, increment]
  name varchar
  email varchar [unique]
}

Table orders {
  id int [pk, increment]
  user_id int [ref: > users.id]
  amount decimal
}
```

## Render with uml-mcp

1. Set `diagram_type` to `dbml` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
