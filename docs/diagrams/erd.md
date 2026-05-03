---
title: ERD
description: Entity-relationship diagrams via Kroki erd backend and generate_uml.
tags:
  - reference
  - diagrams
---

# ERD

[ERD](https://github.com/BurntSushi/erd) notation describes entities and relationships in plain text. UML-MCP renders it through Kroki with `diagram_type: erd`.

## Example

```erd
[Person]
*id
name
+account_id

[Account]
*id
balance

Person *--1 Account
```

## Parameters

| Property | Value |
| --- | --- |
| `diagram_type` | `erd` |
| Backend | erd (via Kroki) |
| Output formats | `png`, `svg`, `jpeg`, `pdf` |

## See also

- [More diagram backends](general.md)
- [DBML](dbml.md) for schema markup
- [Diagram catalog](index.md)
