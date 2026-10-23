---
title: MCP resources
description: Full catalog of uml:// resources, what each URI returns, when to use it, and the source of truth.
tags:
  - reference
  - resources
---

# MCP resources

Resources are read-only data that an MCP client can fetch with `resources/read`. UML-MCP serves seven `uml://` URIs. Source of truth: [`mcp_core/resources/diagram_resources.py`](https://github.com/antoinebou12/uml-mcp/blob/main/mcp_core/resources/diagram_resources.py).

## Calling a resource

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/read",
  "params": { "uri": "uml://types" }
}
```

The response wraps a JSON string in MCP's standard envelope. The `uml://` resources return JSON inside `contents[0].text`; the skill resource below returns Markdown.

## Diagram skill over MCP

UML-MCP implements the [MCP Skills extension](https://modelcontextprotocol.io/extensions/skills/overview)
(`io.modelcontextprotocol/skills`). Clients discover the extension alongside the
Resources capability in `server/discover`, then call `skills/list` with empty
params or `skills/get` with
`{"uri": "skill://uml-mcp-diagrams/SKILL.md"}`.

Both methods return complete skill metadata, unchanged YAML frontmatter, and a
manifest containing the SHA-256 digest and byte size of the bundled `SKILL.md`.
Results have a five-minute TTL and public cache scope (private when enterprise
auth is enabled). These discovery methods require read permission.

Load the instructions with `resources/read` at
`skill://uml-mcp-diagrams/SKILL.md` (`text/markdown`). Clients without Skills
support can read this resource directly. Reading is not activation: the host
controls skill loading, integrity checks, and any user approval. Directory
reading is not advertised or implemented.

The installed package includes a byte-identical copy of the canonical
`.skill/skills/uml-mcp-diagrams/SKILL.md`, checked by tests. After editing the
canonical skill, update `mcp_core/skills/uml-mcp-diagrams/SKILL.md` as well as its
existing client mirrors. Repository navigation and contributor-only skills are
not served.

## Per-type agent skills

Every catalog `diagram_type` (the keys in `DIAGRAM_TYPES`) has an on-demand agent
skill at `.skill/skills/<diagram_type>/SKILL.md`. Those files appear in
[`/.well-known/agent-skills/index.json`](https://github.com/antoinebou12/uml-mcp/blob/main/.well-known/agent-skills/index.json)
for Cursor and other index clients. They are **not** registered on MCP
`skills/list`, so connect-time stays one skill and within the lint token budget.
Regenerate them with `uv run python scripts/build_diagram_type_skills.py`.

## Resource catalog

| URI | Purpose | When to use |
| --- | --- | --- |
| [`uml://types`](#umltypes) | Available diagram types with backend, description, and supported formats | Discover valid `diagram_type` values before calling `generate_uml` |
| [`uml://templates`](#umltemplates) | Starter templates (PlantUML, Mermaid, D2, …) per type | Get minimal valid code to customize |
| [`uml://examples`](#umlexamples) | Realistic example diagrams per type | Reference for syntax and structure |
| [`uml://formats`](#umlformats) | Supported `output_format` values per type | Pick a valid format before render |
| [`uml://capabilities`](#umlcapabilities) | `diagram_type` → backend + formats matrix | Tooling and validation use case |
| [`uml://server-info`](#umlserver-info) | Server name, version, tools, prompts, Kroki URL | Discovery and health checks |
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
  "prompts": ["uml_diagram", "algorithm_explainer", "paper_concept_diagram", "architecture_report"],
  "kroki_server": "https://kroki.io",
  "plantuml_server": "..."
}
```

### `uml://workflow`

The plan-then-generate workflow text. Add it to agent prompts when you want the model to plan before calling `generate_uml`.

---

## Tips

!!! tip "Cache resources client-side"

    Resource payloads are stable across requests within a server version. Cache them on the client to avoid repeated round-trips inside a multi-step flow.

!!! note "What if my client cannot read resources?"

    Use the `list_diagram_types` tool; it returns the same payload as `uml://types`. For other resources, the data is also embedded in the documentation site (see linked pages above).
