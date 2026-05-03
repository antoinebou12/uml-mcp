---
title: DBML
description: Database Markup Language schemas via Kroki and generate_uml.
tags:
  - reference
  - diagrams
---

# DBML

[DBML](https://dbml.dbdiagram.io/) describes tables, columns, and references. UML-MCP renders DBML through Kroki with `diagram_type: dbml`.

## Example

```dbml
Table users {
  id uuid [pk]
  email varchar [unique]
}

Table posts {
  id uuid [pk]
  author_id uuid [ref: > users.id]
  title varchar
}
```

## Parameters

| Property | Value |
| --- | --- |
| `diagram_type` | `dbml` |
| Backend | DBML (via Kroki) |
| Output formats | `svg` |

## See also

- [More diagram backends](general.md)
- [ERD](erd.md) for entity-relationship text
- [Diagram catalog](index.md)
