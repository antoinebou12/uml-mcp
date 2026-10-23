---
name: excalidraw
description: >-
  Writes valid excalidraw diagram source for uml-mcp (diagram_type=excalidraw). Excalidraw whiteboard-style diagrams Use when the user asks for excalidraw or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# excalidraw diagram (uml-mcp)

**`diagram_type`:** `excalidraw`  
**Backend:** `excalidraw`  
**Output formats:** svg

Excalidraw whiteboard-style diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Hand-drawn look is built-in; keep stroke colors high-contrast.
- No MCP `theme` param.

## Starter template

```excalidraw
{"type":"excalidraw","version":2,"source":"kroki","elements":[{"id":"r1","type":"rectangle","x":50,"y":50,"width":150,"height":80,"angle":0,"strokeColor":"#000","backgroundColor":"#fff","fillStyle":"solid"},{"id":"t1","type":"text","x":80,"y":78,"text":"Label","fontSize":20}],"appState":{"viewBackgroundColor":"#fff"},"files":{}}
```

## Example

```excalidraw
{"type":"excalidraw","version":2,"source":"kroki","elements":[{"id":"rect","type":"rectangle","x":100,"y":100,"width":200,"height":100,"angle":0,"strokeColor":"#000","backgroundColor":"#fff","fillStyle":"solid"},{"id":"text","type":"text","x":150,"y":130,"text":"Hello","fontSize":20}],"appState":{"viewBackgroundColor":"#fff"},"files":{}}
```

## Render with uml-mcp

1. Set `diagram_type` to `excalidraw` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
