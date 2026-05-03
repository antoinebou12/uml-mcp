---
title: TikZ
description: Render TikZ/PGF graphics through Kroki.
tags:
  - tikz
  - latex
---

# TikZ Diagrams

UML-MCP supports [TikZ/PGF](https://tikz.dev/) graphics via [Kroki](https://kroki.io/#tikz). You can render TikZ and LaTeX snippets to SVG, PDF, PNG, or JPEG without installing TeX locally.

!!! note "When to use TikZ"

    Pick TikZ when you need precise mathematical drawings, scientific figures, or LaTeX-quality output. For software-engineering UML, prefer [class/sequence diagrams](uml.md). For quick web diagrams, [Mermaid](mermaid.md) is faster and renders directly in the browser.

## Overview

- **Backend**: Kroki (default). No local LaTeX installation required.
- **Output formats**: SVG, PDF, PNG, JPEG.

Use `diagram_type: "tikz"` with the **`generate_uml`** tool. The `code` parameter is your TikZ/LaTeX source (snippet or full document). Omit **`output_dir`** if you only need a URL or base64.

## Available templates and examples

TikZ support in UML-MCP includes templates and auto-wrapping:

- **Snippets**: If you pass only `\begin{tikzpicture}...\end{tikzpicture}`, the server wraps it in a minimal standalone LaTeX document and infers required TikZ libraries where possible.
- **Preamble lines in snippets**: If you paste `\usetikzlibrary{...}` and/or `\usepackage{tikz}` / `\usepackage{pgfplots}` on their own lines *before* the picture (without a full document), those lines are **hoisted** into the generated preamble so they are not duplicated inside `\begin{document}` (which would break LaTeX on Kroki).
- **Full documents**: If your `code` already contains `\documentclass`, it is sent as-is to Kroki.

Templates (via `tools.kroki.tikz.TikZTemplateLibrary`) include:

| Template           | Description                |
|--------------------|----------------------------|
| flowchart          | Decision/process flowchart |
| graph              | Simple node-and-edge graph |
| math_plot          | 2D function plot (pgfplots)|
| tree               | Tree structure             |
| automata           | Finite state machine       |
| geometry_circle    | Circle and axes            |
| mindmap_simple     | Mind map                   |
| circuit_simple     | Simple circuit (IEC)       |
| coordinate_grid    | XY grid                    |
| block_diagram      | Input-Process-Output blocks|

Example files are in `examples/`:

- `example-tikz-flowchart.tex`, `example-tikz-math.tex`, `example-tikz-graph.tex`
- `example-tikz-automata.tex`, `example-tikz-tree.tex`, `example-tikz-3d.tex`
- `example-tikz-mindmap.tex`, `example-tikz-circuit.tex`, `example-tikz-block.tex`

## Output format comparison

| Format | Best for           | Notes                    |
|--------|--------------------|--------------------------|
| SVG    | Web, scaling       | Vector, small size       |
| PDF    | Print, documents   | Vector, high quality     |
| PNG    | Presentations, UI  | Raster, good compatibility |
| JPEG   | Photos, large areas| Raster, smaller files    |

Use `output_format` in the tool call (e.g. `"svg"`, `"pdf"`, `"png"`, `"jpeg"`).

## Common patterns

**Flowchart** (uses `shapes`, `arrows`, `positioning`):

```latex
\begin{tikzpicture}[node distance=2cm]
  \node[rectangle, draw] (start) {Start};
  \node[diamond, draw, below of=start] (dec) {OK?};
  \draw[->] (start) -- (dec);
\end{tikzpicture}
```

**Math plot** (uses `pgfplots`):

```latex
\begin{tikzpicture}
  \begin{axis}[xlabel=$x$, ylabel=$f(x)$, grid=major]
    \addplot[blue, domain=-2:2] {x^2};
  \end{axis}
\end{tikzpicture}
```

**Automata** (uses `automata`, `positioning`):

```latex
\begin{tikzpicture}[shorten >=1pt, node distance=2cm]
  \node[state, initial] (q0) {$q_0$};
  \node[state, accepting, right of=q0] (q1) {$q_1$};
  \draw[->] (q0) to node {1} (q1);
\end{tikzpicture}
```

## Tips for complex diagrams

- Add `\usetikzlibrary{...}` in your code when you use features from a library; the server can also infer some libraries from common commands.
- For pgfplots, the wrapper adds `\usepackage{pgfplots}` and `\pgfplotsset{compat=1.18}` when needed.
- Use a full standalone document if you need custom packages or fonts (e.g. `\documentclass{standalone}\usepackage{tikz}\usepackage{pgfplots}...`).

## Rendering

UML-MCP sends TikZ code to your configured Kroki gateway (see [Configuration](../configuration.md) for `KROKI_SERVER` and related settings). There is no separate local LaTeX compile path in the server.

---

## Related

- [Diagram catalog](index.md): all supported types.
- [D2](d2.md) and [Graphviz](graphviz.md) (with SVG examples); [more backends overview](general.md); [ERD](erd.md), [DBML](dbml.md), [BlockDiag family](blockdiag.md), [BPMN XML](bpmn.md), [C4 (PlantUML)](c4plantuml.md), [Structurizr](structurizr.md), [specialty types](specialty.md).
- [MCP tools reference](../api/tools.md): `generate_uml` parameters.
