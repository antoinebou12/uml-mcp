---
name: nomnoml
description: >-
  Writes valid nomnoml diagram source for uml-mcp (diagram_type=nomnoml). UML-style diagrams from shorthand syntax Use when the user asks for nomnoml or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# nomnoml diagram (uml-mcp)

**`diagram_type`:** `nomnoml`  
**Backend:** `nomnoml`  
**Output formats:** svg

UML-style diagrams from shorthand syntax

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Directive lines start with `#` (`#direction: down`, `#fill: #eee8d5`, `#stroke: #33322E`, `#lineWidth: 2`, `#padding: 12`, `#fontSize: 14`).
- Nodes are `[Label]`; edges `->`, `<->`, `--`; classifiers `[<actor> User]`, `[<database> DB]`, `[<package> P]`.
- One vertical stack (`#direction: down`) reads better in chat thumbnails.
- Prefer warm fill + dark stroke (Solarized-ish) so labels stay legible after PNG.

## Styling

- Directives: `#fill`, `#stroke`, `#lineWidth`, `#fontSize`, `#padding`.
- No MCP `theme` param — set colors in the source.

## Starter template

```nomnoml
#direction: down
[A] -> [B]
[B] -> [C]
```

## Example

```nomnoml
#stroke: #33322E
#fill: #eee8d5
#direction: down
[Client] -> [UML MCP]
[UML MCP] -> [Kroki]
[Kroki] -> [Artifact]
```

## Render with uml-mcp

1. Set `diagram_type` to `nomnoml` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
