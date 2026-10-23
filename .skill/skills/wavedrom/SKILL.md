---
name: wavedrom
description: >-
  Writes valid wavedrom diagram source for uml-mcp (diagram_type=wavedrom). Waveform and digital timing diagrams Use when the user asks for wavedrom or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# wavedrom diagram (uml-mcp)

**`diagram_type`:** `wavedrom`  
**Backend:** `wavedrom`  
**Output formats:** svg

Waveform and digital timing diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Signal names and `skin` (when supported by the renderer) control look.
- No MCP `theme` param.

## Starter template

```wavedrom
{ "signal": [
  { "name": "clk", "wave": "p...." },
  { "name": "sig", "wave": "01.0." }
]}
```

## Example

```wavedrom
{ "signal": [
  { "name": "clk", "wave": "p...." },
  { "name": "data", "wave": "x.345.", "data": ["head", "body", "tail"] }
]}
```

## Render with uml-mcp

1. Set `diagram_type` to `wavedrom` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
