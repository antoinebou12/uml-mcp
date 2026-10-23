---
name: actdiag
description: >-
  Writes valid actdiag diagram source for uml-mcp (diagram_type=actdiag). Activity and workflow diagrams (blockdiag family) Use when the user asks for actdiag or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# actdiag diagram (uml-mcp)

**`diagram_type`:** `actdiag`  
**Backend:** `actdiag`  
**Output formats:** png, svg, pdf

Activity and workflow diagrams (blockdiag family)

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Same family as blockdiag; label lanes and edges clearly.
- No MCP `theme` param.

## Starter template

```actdiag
actdiag {
  input -> process -> output
  lane user {
    input [label = "Input"];
    output [label = "Output"];
  }
  lane system {
    process [label = "Process"];
  }
}
```

## Example

```actdiag
actdiag {
  write -> convert -> image
  lane user {
    label = "User"
    write [label = "Writing text"];
    image [label = "Get diagram image"];
  }
  lane Kroki {
    convert [label = "Convert text to image"];
  }
}
```

## Render with uml-mcp

1. Set `diagram_type` to `actdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
