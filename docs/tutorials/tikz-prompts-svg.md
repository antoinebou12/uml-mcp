---
title: TikZ prompts and SVG
description: Natural-language prompts, optional Sequential Thinking MCP, and generate_uml for TikZ/PGF diagrams as SVG.
tags:
  - tikz
  - tutorials
  - mcp
---

# TikZ prompts and SVG

[TikZ](https://tikz.dev/) is ideal for **precise** figures (geometry, plots, finite automata, publication-quality output). UML-MCP sends snippets or full documents to Kroki. See [TikZ](../diagrams/tikz.md) for templates, preamble hoisting, and Docker options.

## Prerequisites

- Connected **UML-MCP** ([Getting started](getting-started.md)).
- Optional **Sequential Thinking** MCP to plan libraries, coordinates, and labels before generating TikZ source.

There is **no** TikZ-specific named prompt on UML-MCP; use **`uml_diagram_with_thinking`** and insist on `diagram_type: "tikz"` in the final `generate_uml` call.

## Natural-language prompts (copy-paste)

```
Generate TikZ for a simple state machine: states Idle, Running, Stopped with transitions
start -> Idle, Idle -> Running on begin, Running -> Stopped on halt, Stopped -> Idle on reset.
Use tikzpicture and draw circles for states with labeled arrows.
```

```
TikZ snippet only: draw the unit circle, axes from -1.5 to 1.5, label the axes x and y,
place a node at (0,-1.35) with text "UML-MCP".
```

```
TikZ mind map style (simple): root node "Server", children "MCP", "Kroki", "Clients"; use mindmap if appropriate or manual nodes.
```

## Example Sequential Thinking flow (then `generate_uml`)

1. **Scope:** Single `tikzpicture`, no full `\documentclass` needed (Kroki wraps snippets).
2. **Libraries:** Default draw suffices for circles and nodes; add `\usetikzlibrary{...}` on its own line if required.
3. **Coordinates:** Keep bounding box modest for SVG clarity.
4. **Text:** ASCII labels preferred inside nodes for portability.
5. **Generate:** `diagram_type: "tikz"`, `output_format: "svg"`.

## Named prompts

Use **`uml_diagram_with_thinking`** with context that specifies TikZ output and `diagram_type` **`tikz`**. Cross-check allowed types with **`uml://types`**.

## Direct `tools/call` (JSON-RPC)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "generate_uml",
    "arguments": {
      "diagram_type": "tikz",
      "output_format": "svg",
      "code": "\\begin{tikzpicture}\n\\draw (0,0) circle (1cm);\n\\node at (0,-1.35) {UML-MCP};\n\\end{tikzpicture}"
    }
  }
}
```

## Example output (server-rendered SVG)

![TikZ diagram example](../assets/tutorials/tikz-tutorial.svg)
