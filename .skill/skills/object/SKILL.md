---
name: object
description: >-
  Writes valid object diagram source for uml-mcp (diagram_type=object). Shows instances of classes and their relationships Use when the user asks for object or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# object diagram (uml-mcp)

**`diagram_type`:** `object`  
**Backend:** `plantuml`  
**Output formats:** png, svg, pdf, txt, base64

Shows instances of classes and their relationships

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Themes

Pass **`theme`** to `generate_uml` / `generate_uml_image` (PlantUML built-in name).
The server injects `!theme <name>` after `@startuml` when the source has no `!theme` yet.

Recommended: `cerulean`, `materia`, `sketchy`, `cyborg`, `plain`, `aws-orange`, `blueprint`, `sandstone`.

Match the **page background** (also see MCP prompt **`diagram_theme`**):
- light / white: `cerulean`, `materia`, `plain`, `sketchy`, `sandstone`
- dark / black: `blueprint`, `cyborg`, `black-knight`, `carbon-gray`, `crt-green`
- B&W / print: `plain`, `sketchy`, `sketchy-outline`, `mimeograph`, `lightgray`

Or embed in source:

```plantuml
@startuml
!theme cerulean
' … diagram …
@enduml
```

## Starter template

```plantuml
@startuml
object user1 as "User"
object sys1 as "System"
user1 --> sys1: uses
@enduml
```

## Example

```plantuml
@startuml
object order1 as "Order #1"
object item1 as "Item A"
object item2 as "Item B"
object customer as "Customer"
order1 --> item1: contains
order1 --> item2: contains
order1 --> customer: placed by
@enduml
```

## Render with uml-mcp

1. Set `diagram_type` to `object` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
