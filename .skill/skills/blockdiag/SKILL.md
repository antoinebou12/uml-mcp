---
name: blockdiag
description: >-
  Writes valid blockdiag diagram source for uml-mcp (diagram_type=blockdiag). Simple block diagram images Use when the user asks for blockdiag or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# blockdiag diagram (uml-mcp)

**`diagram_type`:** `blockdiag`  
**Backend:** `blockdiag`  
**Output formats:** png, svg, pdf

Simple block diagram images

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Optional `default_shape`, `node_width`, colors via `color = "…"` on nodes.
- Keep to one row/column flow for chat thumbnails.

## Starter template

```blockdiag
blockdiag {
  User -> System -> Database;
  System -> User;
}
```

## Example

```blockdiag
blockdiag {
  Kroki -> generates -> "Block diagrams";
  Kroki -> is -> "very easy!";
  Kroki [color = "greenyellow"];
  "Block diagrams" [color = "pink"];
  "very easy!" [color = "orange"];
}
```

## Render with uml-mcp

1. Set `diagram_type` to `blockdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
