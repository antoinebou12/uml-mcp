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

    Live gallery (flowchart, sequence, class, state, Gantt, ER) plus a section on **prompts**, optional **Sequential Thinking** MCP, and **server SVG** via `generate_uml`.

    [:octicons-arrow-right-24: Browse Mermaid](mermaid.md)

-   :material-chart-box-outline:{ .lg .middle } **PlantUML prompts and SVG**

    ---

    Copy-paste prose prompts, example Sequential Thinking steps, named MCP prompts (`class_diagram`, `sequence_diagram`, …), and a committed SVG sample.

    [:octicons-arrow-right-24: Open PlantUML tutorial](plantuml-prompts-svg.md)

-   :material-graph-outline:{ .lg .middle } **D2 prompts and SVG**

    ---

    Service-style sketches, planning with Sequential Thinking, `uml_diagram_with_thinking`, and a D2 SVG example.

    [:octicons-arrow-right-24: Open D2 tutorial](d2-prompts-svg.md)

-   :material-drawing:{ .lg .middle } **TikZ prompts and SVG**

    ---

    Precision figures with TikZ, optional Sequential Thinking, and a minimal circle SVG from Kroki.

    [:octicons-arrow-right-24: Open TikZ tutorial](tikz-prompts-svg.md)

-   :material-sitemap:{ .lg .middle } **BPMN guide**

    ---

    A short, structured BPMN 2.0.2 reference: events, tasks, gateways, sequence flow, lanes and pools.

    [:octicons-arrow-right-24: Read the BPMN guide](bpmn.md)

-   :material-file-image-outline:{ .lg .middle } **BPMN prompts and SVG**

    ---

    Copy-paste prose prompts, named MCP prompts (`bpmn_process_guide`, `bpmn_executable_process`), a full `tools/call` JSON example with BPMN-DI XML, and a committed Kroki SVG sample.

    [:octicons-arrow-right-24: Open BPMN prompts tutorial](bpmn-prompts-svg.md)

</div>

## Prerequisites

- An MCP-compatible client (Cursor, Claude Desktop, an HTTP client, or `curl`).
- A running UML-MCP server. Use the public endpoint at `https://uml-mcp.vercel.app/mcp`, install via Smithery, or run locally; see [Deploy](../deploy/index.md).

!!! tip "Plan before you generate"

    The default prompts (`uml_diagram`, `uml_diagram_with_thinking`) ask the model to plan (type, elements, relationships) before calling `generate_uml`. The `uml://workflow` resource summarises the same flow.
