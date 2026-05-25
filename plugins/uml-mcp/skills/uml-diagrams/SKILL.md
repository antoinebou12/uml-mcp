---
name: uml-diagrams
description: >-
  Create and validate diagrams with the uml-mcp MCP server (generate_uml,
  validate_uml, list_diagram_types, generate_uml_batch). Use for UML, Mermaid,
  D2, Graphviz, Kroki URLs, or diagram_type questions.
---

> **Maintainers:** Canonical long-form copy also lives in [`.skill/skills/uml-mcp-diagrams/SKILL.md`](https://github.com/antoinebou12/uml-mcp/blob/main/.skill/skills/uml-mcp-diagrams/SKILL.md). Keep tool tables and `output_dir` wording aligned with the Smithery bundle [uml-skill](https://github.com/antoinebou12/uml-skill).

# UML-MCP in Claude Code

## Goal

Produce valid `diagram_type` and DSL `code`, call **generate_uml**, and give the user the **`url`** (and **`playground`** when present). Prefer URL-first output: omit **`output_dir`** / use `null` unless the user wants files on disk (local stdio only).

## Do

- If **`diagram_type`** is unclear, use **`list_diagram_types`** or read **`uml://types`** / **`uml://formats`** before **generate_uml**.
- Match **`diagram_type`** to the language of **`code`** (e.g. Mermaid body → `mermaid`; `@startuml` → `plantuml` or the specific Kroki PlantUML subtype when applicable).
- Use **`validate_uml`** before heavy retry loops or on pasted diagram source.
- Return the **`url`** plus a short copy of **`code`** so the user can edit and regenerate.

## Do not

- Invent **`diagram_type`** or **`output_format`**; confirm from **`uml://types`** / **`uml://formats`** or **`list_diagram_types`**.
- Put prose inside **`code`**—only valid diagram DSL.
- Set **`output_dir`** unless the user asked for saved files (not applicable to the default HTTP deployment).

## Before generating

1. Read **`uml://types`** / **`uml://capabilities`** when the type is ambiguous.
2. Use **`uml://templates`**, **`uml://examples`**, or **`uml://recipes`** for starters.
3. Optional: **`validate_uml`** with **`strict: true`** for stricter Mermaid/D2 checks.

## Tools and resources

- **Tools:** `generate_uml`, `validate_uml`, `list_diagram_types`, `generate_uml_batch`
- **Resources:** `uml://types`, `uml://formats`, `uml://templates`, `uml://examples`, `uml://capabilities`, `uml://recipes`, `uml://server-info`, `uml://workflow`, plus URIs from **`resources/list`**

**Prompts** (when exposed): `uml_diagram`, `uml_diagram_with_thinking`, `class_diagram`, `sequence_diagram`, `activity_diagram`, `usecase_diagram`, `mermaid_sequence_api`, `mermaid_gantt`, `bpmn_process_guide`, `c4_model`, `wireviz_harness`, `bpmn_executable_process`, `convert_class_to_mermaid`, `algorithm_explainer`, `paper_concept_diagram`.

## generate_uml inputs

| Field | Notes |
| --- | --- |
| `diagram_type` | Required; must match server-supported keys. |
| `code` | Required; DSL only. |
| `output_dir` | Omit for HTTP MCP (URL + base64 in response). |
| `output_format` | Often `svg`; check **`uml://formats`** for the type. |
| `theme` | PlantUML types only. |
| `scale` | SVG only. |

## After generation

Highlight **`url`**, then **`playground`** if present, then **`local_path`** only when `output_dir` was used. On **`error`**, fix DSL or types and retry or run **`validate_uml`**.

## Intent → type hints

| Intent | Typical `diagram_type` |
| --- | --- |
| Classes / associations | `class` or Mermaid `classDiagram` |
| Lifelines / messages | `sequence` or Mermaid sequence |
| Flow / BPMN | `activity`, `bpmn`, or Mermaid flowchart |
| Quick charts | `mermaid` |
| Declarative layout | `d2` |

When several fit, prefer what the user named; otherwise prefer the clearest match from **`uml://types`**.
