---
name: ditaa
description: >-
  Writes valid ditaa diagram source for uml-mcp (diagram_type=ditaa). Diagrams Through ASCII Art Use when the user asks for ditaa or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# ditaa diagram (uml-mcp)

**`diagram_type`:** `ditaa`  
**Backend:** `ditaa`  
**Output formats:** png, svg

Diagrams Through ASCII Art

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- ASCII boxes + `{c}` / `{d}` color tags when needed.
- No MCP `theme` param.

## Starter template

```ditaa
+------+     +------+
|  A   +---->+  B   |
+------+     +------+
```

## Example

```ditaa
+--------+   +-------+   +----------+
| Client |   |  API  |   | Database |
+----+---+   +---+---+   +----+-----+
     |            |              |
     |  request   |   query      |
     +----------->+------------->
     |            |              |
     |  response  |   result     |
     <------------+<-------------+
     |            |              |
```

## Render with uml-mcp

1. Set `diagram_type` to `ditaa` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
