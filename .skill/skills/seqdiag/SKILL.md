---
name: seqdiag
description: >-
  Writes valid seqdiag diagram source for uml-mcp (diagram_type=seqdiag). Sequence diagrams (blockdiag family) Use when the user asks for seqdiag or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# seqdiag diagram (uml-mcp)

**`diagram_type`:** `seqdiag`  
**Backend:** `seqdiag`  
**Output formats:** png, svg, pdf

Sequence diagrams (blockdiag family)

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Participant order left-to-right; keep messages short.
- No MCP `theme` param.

## Starter template

```seqdiag
seqdiag {
  client -> server [label = "Request"];
  server <-- client [label = "Response"];
}
```

## Example

```seqdiag
seqdiag {
  browser  -> webserver [label = "GET /seqdiag/svg/base64"];
  webserver  -> processor [label = "Convert text to image"];
  webserver <-- processor;
  browser <-- webserver;
}
```

## Render with uml-mcp

1. Set `diagram_type` to `seqdiag` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
