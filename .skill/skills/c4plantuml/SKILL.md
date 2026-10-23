---
name: c4plantuml
description: >-
  Writes valid c4plantuml diagram source for uml-mcp (diagram_type=c4plantuml). C4 model diagrams using PlantUML Use when the user asks for c4plantuml or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# c4plantuml diagram (uml-mcp)

**`diagram_type`:** `c4plantuml`  
**Backend:** `c4plantuml`  
**Output formats:** png, svg, pdf, txt, base64

C4 model diagrams using PlantUML

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Use PlantUML C4 includes; pick context or container view.
- Keep relationships labeled; stay under ~30 elements or split views.

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

```c4plantuml
!include <C4/C4_Context>
title System Context
Person(user, "User")
System(system, "My System")
Rel(user, system, "Uses")
```

## Example

```c4plantuml
!include <C4/C4_Context>
title System Context diagram for Internet Banking System
Person(customer, "Banking Customer", "A customer of the bank, with personal bank accounts.")
System(banking_system, "Internet Banking System", "Allows customers to check their accounts.")
System_Ext(mail_system, "E-mail system", "The internal Microsoft Exchange e-mail system.")
System_Ext(mainframe, "Mainframe Banking System", "Stores all of the core banking information.")
Rel(customer, banking_system, "Uses")
Rel_Back(customer, mail_system, "Sends e-mails to")
Rel_Neighbor(banking_system, mail_system, "Sends e-mails", "SMTP")
Rel(banking_system, mainframe, "Uses")
```

## Render with uml-mcp

1. Set `diagram_type` to `c4plantuml` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
