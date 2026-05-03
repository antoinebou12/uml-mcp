---
title: Structurizr
description: Structurizr DSL workspace diagrams via Kroki and generate_uml.
tags:
  - reference
  - diagrams
---

# Structurizr

[Structurizr](https://structurizr.com/) DSL describes workspaces, models, and views in text. UML-MCP renders Structurizr through Kroki with `diagram_type: structurizr`.

## Example

```structurizr
workspace {
  model {
    user = person "User"
    system = softwareSystem "UML-MCP" {
      api = container "FastAPI"
      mcp = container "MCP server"
    }
    user -> api "HTTPS"
    api -> mcp "HTTP /mcp"
  }
  views { systemContext system { include * } }
}
```

## Parameters

| Property | Value |
| --- | --- |
| `diagram_type` | `structurizr` |
| Backend | Structurizr (via Kroki) |
| Output formats | `png`, `svg`, `pdf`, `txt`, `base64` |

## See also

- [C4 (PlantUML)](c4plantuml.md) for C4 via PlantUML
- [More diagram backends](general.md)
- [Diagram catalog](index.md)
