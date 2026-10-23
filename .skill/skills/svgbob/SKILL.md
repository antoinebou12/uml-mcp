---
name: svgbob
description: >-
  Writes valid svgbob diagram source for uml-mcp (diagram_type=svgbob). ASCII art to SVG diagrams Use when the user asks for svgbob or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# svgbob diagram (uml-mcp)

**`diagram_type`:** `svgbob`  
**Backend:** `svgbob`  
**Output formats:** svg

ASCII art to SVG diagrams

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Prefer axis-aligned `+---+` boxes and `---->` arrows; diagonal `/ \` "balloon" shapes often mis-render in Kroki's svgbob.
- Keep labels short; pad with spaces so left/right edges stay aligned.
- One horizontal pipeline (Client → MCP → Kroki) reads best in chat thumbnails.
- Good for quick architecture sketches; use PlantUML/Mermaid for formal UML.

## Styling

- Styling = ASCII geometry; prefer rounded `.--.` boxes for polish.
- No MCP `theme` param.

## Starter template

```svgbob
+--------+     +---------+     +-------+
| Client |---->| UML MCP |---->| Kroki |
+--------+     +---------+     +-------+
```

## Example

```svgbob
+--------+     +---------+     +-------+
| Client |---->| UML MCP |---->| Kroki |
+--------+     +---------+     +-------+
```

## Render with uml-mcp

1. Set `diagram_type` to `svgbob` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
