---
title: Tutorials
description: Step-by-step guides for connecting clients, generating diagrams, and using the MCP tools, resources, and prompts.
---

# Tutorials

Pick a starting point. Each tutorial is self-contained and assumes you have a working UML-MCP server (hosted, local, or Docker). If you don't, start with [Getting started](getting-started.md).

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting started**

    ---

    Connect a client, generate your first diagram, save vs URL, validate, batch, and use themes/scale. The end-to-end path from zero to a rendered PNG.

    [:octicons-arrow-right-24: Start the tutorial](getting-started.md)

-   :material-puzzle-outline:{ .lg .middle } **Diagram Assistant**

    ---

    Mermaid sequence/Gantt, BPMN process modeling, and converting class diagrams into Mermaid using named prompts and `uml://` resources.

    [:octicons-arrow-right-24: Read the guide](../diagram-assistant.md)

-   :material-chart-timeline-variant:{ .lg .middle } **Mermaid live examples**

    ---

    A gallery of ready-to-copy Mermaid diagrams (flowchart, sequence, class, state, Gantt, ER), rendered live on this page.

    [:octicons-arrow-right-24: Browse Mermaid](mermaid.md)

-   :material-sitemap:{ .lg .middle } **BPMN guide**

    ---

    A short, structured BPMN 2.0.2 reference: events, tasks, gateways, sequence flow, lanes and pools (same content as the `uml://bpmn-guide` resource).

    [:octicons-arrow-right-24: Read the BPMN guide](bpmn.md)

</div>

## Prerequisites

- An MCP-compatible client (Cursor, Claude Desktop, an HTTP client, or `curl`).
- A running UML-MCP server. Use the public endpoint at `https://uml-mcp.vercel.app/mcp`, install via Smithery, or run locally; see [Deploy](../deploy/index.md).

!!! tip "Plan before you generate"

    The default prompts (`uml_diagram`, `uml_diagram_with_thinking`) ask the model to plan (type, elements, relationships) before calling `generate_uml`. The `uml://workflow` resource summarises the same flow.
