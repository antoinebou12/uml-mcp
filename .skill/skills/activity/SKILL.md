---
name: activity
description: >-
  Writes valid activity diagram source for uml-mcp (diagram_type=activity). Shows workflows or business processes Use when the user asks for activity or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# activity diagram (uml-mcp)

**`diagram_type`:** `activity`  
**Backend:** `plantuml`  
**Output formats:** png, svg, pdf, txt, base64

Shows workflows or business processes

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Use `start`/`stop`, decisions (`if`/`endif`), `fork`/`join`, and swimlanes when multiple actors.
- Label every branch exit.

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
start
:Do something;
if (OK?) then (yes)
  :Continue;
else (no)
  :Handle error;
endif
stop
@enduml
```

## Example

```plantuml
@startuml
start
:Receive order;
:Validate order;
if (Valid?) then (yes)
  :Process payment;
  if (Payment OK?) then (yes)
    :Ship order;
    stop
  else (no)
    :Notify customer;
    stop
  endif
else (no)
  :Reject order;
  stop
endif
@enduml
```

## Render with uml-mcp

1. Set `diagram_type` to `activity` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
