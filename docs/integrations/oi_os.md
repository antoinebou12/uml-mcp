---
title: OI OS
description: "Community integration: route natural-language requests to UML-MCP tools through an OI OS intent manifest."
tags:
  - integrations
  - community
---

# OI OS integration

!!! note "Community integration"

    This is metadata for a third-party agent runtime. It is maintained here as a
    convenience and is not officially supported by the OI OS project.

[OI OS](https://github.com/OI-OS) routes natural-language requests to MCP tools using an
intent manifest. UML-MCP ships one as `oi-manifest.json` at the repository root.

## Setup

UML-MCP is consumed as an ordinary stdio MCP server — no OI-specific dependency, no fork, no
changes to the Python package:

```bash
git clone https://github.com/antoinebou12/uml-mcp
cd uml-mcp
uv sync
uv run python server.py
```

Register it with your OI OS installation the way you register any stdio MCP server, and point
the runtime at `oi-manifest.json` for intent routing.

## What the manifest contains

```json
{
  "server_name": "uml_mcp",
  "version": "1.3.0",
  "intents": [
    { "keyword": "generate uml", "tool_name": "generate_uml", "priority": 10 }
  ],
  "parameter_extractors": {},
  "reminder_message": "..."
}
```

| Field | Purpose |
|---|---|
| `server_name` | Matches `MCPSettings.server_name`, so routing binds to the right server |
| `version` | Kept in lockstep with `pyproject.toml`; a test fails if they drift |
| `intents` | Keyword → tool mappings covering all four tools |
| `parameter_extractors` | Intentionally empty — see below |
| `reminder_message` | Guidance shown to the agent: which tool does what, and to render returned URLs as links |

Intents cover every registered tool: `generate_uml` (generation), `validate_uml` (validation),
`list_diagram_types` (type discovery) and `generate_uml_batch` (batch generation). Keywords are
unique, so a request never routes ambiguously.

## Why parameter extraction is empty

Regex-based parameter extraction cannot safely reconstruct diagram source. The upstream OI OS
fork extracted the `code` argument with a rule that deletes the literal words *generate*,
*create*, *uml*, *diagram* and *plantuml* from the request — which quietly corrupts any valid
PlantUML that happens to contain them, for example a class named `Diagram`.

Building `diagram_type` and `code` is the MCP client's job. The tools already validate their own
inputs and `validate_uml` will report syntax problems before you spend a render on them, so an
agent that assembles arguments properly needs no extraction layer.

## Related

- [MCP tools reference](../api/tools.md)
- [Configuration](../configuration.md)
- [Installation](../installation.md)
