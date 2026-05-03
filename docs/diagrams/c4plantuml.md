---
title: C4 (PlantUML)
description: C4 model diagrams using PlantUML stdlib includes and generate_uml.
tags:
  - reference
  - diagrams
---

# C4 (PlantUML)

[C4-PlantUML](https://github.com/plantuml-stdlib/C4-PlantUML) adds people, containers, and relationships on top of PlantUML. Use `diagram_type: c4plantuml` and include the stdlib URLs as in the example below (Kroki resolves them at render time).

## Example

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

Person(user, "User")
System_Boundary(c1, "UML-MCP") {
  Container(api, "FastAPI app", "Python")
  Container(mcp, "MCP server", "FastMCP")
}
Rel(user, api, "HTTPS")
Rel(api, mcp, "HTTP /mcp")
@enduml
```

## Parameters

| Property | Value |
| --- | --- |
| `diagram_type` | `c4plantuml` |
| Backend | PlantUML with C4 includes |
| Output formats | `png`, `svg`, `pdf`, `txt`, `base64` |

## See also

- [UML (PlantUML)](uml.md) for non-C4 PlantUML types
- [More diagram backends](general.md)
- [Structurizr](structurizr.md) for the Structurizr DSL
- [Diagram catalog](index.md)
