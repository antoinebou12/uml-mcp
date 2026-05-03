---
title: BlockDiag family
description: blockdiag, seqdiag, actdiag, nwdiag, packetdiag, and rackdiag via Kroki.
tags:
  - reference
  - diagrams
---

# BlockDiag family

The [blockdiag](https://blockdiag.com/en/) family covers `blockdiag`, `seqdiag`, `actdiag`, `nwdiag`, `packetdiag`, and `rackdiag`. Types share similar DSL conventions; pick the `diagram_type` that matches your diagram.

## Example (`blockdiag`)

```blockdiag
{
  Browser -> CDN -> WebApp -> Database;
  WebApp -> Cache;
}
```

## Types

| `diagram_type` | Description | Output formats |
| --- | --- | --- |
| `blockdiag` | Generic blocks | `png`, `svg`, `pdf` |
| `seqdiag` | Sequence | `png`, `svg`, `pdf` |
| `actdiag` | Activity | `png`, `svg`, `pdf` |
| `nwdiag` | Network | `png`, `svg`, `pdf` |
| `packetdiag` | Packet layout | `png`, `svg`, `pdf` |
| `rackdiag` | Server racks | `png`, `svg`, `pdf` |

## See also

- [More diagram backends](general.md)
- [Diagram catalog](index.md)
