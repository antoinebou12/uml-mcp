---
name: class
description: >-
  Writes valid class diagram source for uml-mcp (diagram_type=class). Shows classes, attributes, methods and relationships between classes Use when the user asks for class or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# class diagram (uml-mcp)

**`diagram_type`:** `class`  
**Backend:** `plantuml`  
**Output formats:** png, svg, pdf, txt, base64

Shows classes, attributes, methods and relationships between classes

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Visibility: `+` public, `-` private, `#` protected.
- Inheritance: empty triangle; composition filled diamond; aggregation empty diamond; multiplicities on associations.
- Prefer `skinparam linetype ortho` and `left to right direction` when the graph is dense.

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
class Car {
  - brand: string
  - speed: int
  + drive(): void
}
class Engine {
  - horsepower: int
  + start(): void
}
Car --> Engine
@enduml
```

## Example

```plantuml
@startuml
class Account {
  - balance: decimal
  - accountNumber: string
  + deposit(amount: decimal): void
  + withdraw(amount: decimal): boolean
}
class Customer {
  - name: string
  - id: string
  + getAccounts(): List<Account>
}
class Transaction {
  - amount: decimal
  - date: DateTime
}
Customer "1" --> "*" Account : owns
Account "1" --> "*" Transaction : contains
@enduml
```

## Render with uml-mcp

1. Set `diagram_type` to `class` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
