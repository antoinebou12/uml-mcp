---
name: uml-diagrams
description: >-
  Create and validate diagrams with the uml-mcp MCP server (generate_uml,
  validate_uml, list_diagram_types, generate_uml_batch). Use for UML, Mermaid,
  D2, Graphviz, Kroki URLs, or diagram_type questions.
---

# UML-MCP in Claude Code

## Goal

Produce valid `diagram_type` and DSL `code`, call **generate_uml**, and give the user the **`url`** (and **`playground`** when present). Prefer URL-first output: omit **`output_dir`** / use `null` unless the user wants files on disk (local stdio servers only).

## Do

- If **`diagram_type`** is unclear, use **`list_diagram_types`** or read **`uml://types`** / **`uml://formats`** before **generate_uml**.
- Match **`diagram_type`** to the language of **`code`** (e.g. Mermaid body → `mermaid`; `@startuml` → `plantuml` or the specific Kroki PlantUML subtype when applicable).
- Use **`validate_uml`** before heavy retry loops or on pasted diagram source.
- Return the **`url`** plus a short copy of **`code`** so the user can edit and regenerate.

## Do not

- Invent **`diagram_type`** or **`output_format`**; confirm from **`uml://types`** / **`uml://formats`** or **`list_diagram_types`**.
- Put prose inside **`code`**—only valid diagram DSL.
- Set **`output_dir`** unless the user asked for saved files (not applicable to the default HTTP deployment).

## Tools and resources

- **Tools:** `generate_uml`, `validate_uml`, `list_diagram_types`, `generate_uml_batch`
- **Resources:** `uml://types`, `uml://formats`, `uml://templates`, `uml://examples`, `uml://capabilities`, `uml://server-info`, `uml://mermaid-examples`, and related `uml://` URIs

## generate_uml inputs

| Field | Notes |
| --- | --- |
| `diagram_type` | Required; must match server-supported keys. |
| `code` | Required; DSL only. |
| `output_dir` | Omit for HTTP MCP (URL + base64 in response). |
| `output_format` | Often `svg`; check **`uml://formats`** for the type. |

## After generation

On success, highlight **`url`**, then **`playground`** if present, then **`local_path`** only when `output_dir` was used. On **`error`**, fix DSL or types and retry or run **`validate_uml`**.

## Intent → type hints

| Intent | Typical `diagram_type` |
| --- | --- |
| Classes / associations | `class` or Mermaid `classDiagram` |
| Lifelines / messages | `sequence` or Mermaid sequence |
| Flow / BPMN | `activity`, `bpmn`, or Mermaid flowchart |
| Quick charts | `mermaid` |
| Declarative layout | `d2` |

When several fit, prefer what the user named; otherwise prefer the clearest match from **`uml://types`**.
