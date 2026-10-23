---
name: sequence
description: >-
  Writes valid sequence diagram source for uml-mcp (diagram_type=sequence). Shows object interactions arranged in time sequence Use when the user asks for sequence or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# sequence diagram (uml-mcp)

**`diagram_type`:** `sequence`  
**Backend:** `plantuml`  
**Output formats:** png, svg, pdf, txt, base64

Shows object interactions arranged in time sequence

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Declare participants left-to-right in contact order; `autoactivate on`; `hide footbox` when no returns.
- Messages top→bottom only; activate/deactivate pairs; notes for asides.

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
participant User
participant System

User -> System: Request
System --> User: Response
@enduml
```

## Example

```plantuml
@startuml
participant Client
participant API
participant Database

Client -> API: GET /resource
activate API
API -> Database: query
activate Database
Database --> API: result
deactivate Database
API --> Client: 200 JSON
deactivate API

alt Error
  API --> Client: 500
end
@enduml
```

## Render with uml-mcp

1. Set `diagram_type` to `sequence` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
