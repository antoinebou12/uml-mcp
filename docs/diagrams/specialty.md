---
title: Specialty diagram types
description: Excalidraw, bytefield, wavedrom, pikchr, nomnoml, svgbob, goat, umlet, Vega, and related Kroki-backed types.
tags:
  - reference
  - diagrams
---

# Specialty diagram types

These `diagram_type` values are supported through Kroki (or the same pipeline as other types). Each uses its own input language; check the upstream project for full syntax. Use `generate_uml` with the matching `diagram_type` and `code`.

| `diagram_type` | Use case |
| --- | --- |
| `excalidraw` | Hand-drawn whiteboard look |
| `bytefield` | Binary protocol byte layouts |
| `wavedrom` | Digital timing / waveform |
| `pikchr` | Pikchr diagram scripting language (Fossil-style) |
| `nomnoml` | UML in shorthand |
| `svgbob` | ASCII art to SVG |
| `goat` | GoAT Markdeep-style ASCII art to SVG |
| `umlet` | UMLet UML diagrams from UXF XML |
| `vega` / `vegalite` | Visualization grammars |

Output formats vary by type; use `validate_uml` or `uml://formats` before rendering.

## See also

- [More diagram backends](general.md)
- [Diagram catalog](index.md) for the full table
- [TikZ](tikz.md) for LaTeX-driven graphics
