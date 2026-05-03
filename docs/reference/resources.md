---
title: MCP resources
description: Full catalog of uml:// resources, what each URI returns, when to use it, and the source of truth.
tags:
  - reference
  - resources
---

# MCP resources

Resources are read-only data that an MCP client can fetch with `resources/read`. UML-MCP serves nine `uml://` URIs. Source of truth: [`mcp_core/resources/diagram_resources.py`](https://github.com/antoinebou12/uml-mcp/blob/main/mcp_core/resources/diagram_resources.py).

## Calling a resource

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/read",
  "params": { "uri": "uml://types" }
}
```

The response wraps a JSON string in MCP's standard envelope. Every UML-MCP resource returns valid JSON inside `contents[0].text`.

## Resource catalog

| URI | Purpose | When to use |
| --- | --- | --- |
| [`uml://types`](#umltypes) | Available diagram types with backend, description, and supported formats | Discover valid `diagram_type` values before calling `generate_uml` |
| [`uml://templates`](#umltemplates) | Starter templates (PlantUML, Mermaid, D2, …) per type | Get minimal valid code to customize |
| [`uml://examples`](#umlexamples) | Realistic example diagrams per type | Reference for syntax and structure |
| [`uml://formats`](#umlformats) | Supported `output_format` values per type | Pick a valid format before render |
| [`uml://capabilities`](#umlcapabilities) | `diagram_type` → backend + formats matrix | Tooling and validation use case |
| [`uml://server-info`](#umlserver-info) | Server name, version, tools, prompts, Kroki URL | Discovery and health checks |
| [`uml://mermaid-examples`](#umlmermaid-examples) | Named Mermaid examples (`sequence_api`, `gantt`) | Reference for `mermaid_sequence_api` / `mermaid_gantt` prompts |
| [`uml://bpmn-guide`](#umlbpmn-guide) | Structured BPMN 2.0.2 reference | Pair with `generate_uml(diagram_type="bpmn")` |
| [`uml://workflow`](#umlworkflow) | Recommended plan-then-generate workflow | Add to agent system prompts |

---

### `uml://types`

Returns a JSON object: `{ <type>: { backend, description, formats }, ... }`. Same payload as the `list_diagram_types` tool, which helps when a client cannot call resources but can call tools.

### `uml://templates`

Minimal starter snippets keyed by `diagram_type`. Use when the user is new to a notation; modify the template instead of writing from scratch.

### `uml://examples`

More realistic example diagrams keyed by `diagram_type`. Heavier than templates; useful as few-shot context for an LLM.

### `uml://formats`

Format whitelist per type:

```json
{
  "class": ["png", "svg", "pdf", "txt", "base64"],
  "mermaid": ["svg", "png"],
  "d2": ["svg"]
}
```

### `uml://capabilities`

Combines backend, formats, and description into a single matrix. Same shape `validate_uml` uses internally to catch unsupported `output_format` values.

### `uml://server-info`

Server identity and runtime metadata:

```json
{
  "server_name": "uml-mcp",
  "version": "...",
  "description": "...",
  "tools": ["generate_uml", "validate_uml", "list_diagram_types", "generate_uml_batch"],
  "prompts": ["uml_diagram", "uml_diagram_with_thinking", "..."],
  "kroki_server": "https://kroki.io",
  "plantuml_server": "..."
}
```

### `uml://mermaid-examples`

Two named keys: `sequence_api` (an API call sequence) and `gantt` (a Gantt schedule). These are the same examples consumed by the `mermaid_sequence_api` and `mermaid_gantt` prompts.

### `uml://bpmn-guide`

Structured BPMN 2.0.2 reference with `core_elements`, `flow_rules`, `tool`, and `template_uri` keys. Mirrors the [BPMN guide tutorial page](../tutorials/bpmn.md).

### `uml://workflow`

The plan-then-generate workflow text. Add it to agent prompts when you want the model to plan before calling `generate_uml`.

---

## Tips

!!! tip "Cache resources client-side"

    Resource payloads are stable across requests within a server version. Cache them on the client to avoid repeated round-trips inside a multi-step flow.

!!! note "What if my client cannot read resources?"

    Use the `list_diagram_types` tool; it returns the same payload as `uml://types`. For other resources, the data is also embedded in the documentation site (see linked pages above).
