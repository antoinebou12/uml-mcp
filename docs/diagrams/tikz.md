# TikZ Diagrams

UML-MCP supports [TikZ/PGF](https://tikz.dev/) graphics via [Kroki](https://kroki.io/#tikz). You can render TikZ and LaTeX snippets to SVG, PDF, PNG, or JPEG without installing TeX locally.

## Overview

- **Backend**: Kroki (default). No local LaTeX installation required.
- **Optional**: Local compilation with Docker; see [Optional Docker](#optional-docker) below.
- **Output formats**: SVG, PDF, PNG, JPEG.

Use `diagram_type: "tikz"` with the **`generate_uml`** tool. The `code` parameter is your TikZ/LaTeX source (snippet or full document). Omit **`output_dir`** if you only need a URL or base64.

## Available templates and examples

The TikZ module provides a template library and auto-wrapping:

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
| block_diagram      | Input–Process–Output blocks|

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

## Local vs Kroki rendering

| Aspect       | Kroki (default)     | Local (Docker)        |
|-------------|---------------------|------------------------|
| Setup       | None                | Docker build/run       |
| Network     | Required            | Optional               |
| Custom TeX  | Kroki’s environment | Your image            |
| Use case    | Most diagrams       | Offline or custom deps |

To use optional local compilation, set `USE_LOCAL_LATEX=true` and use the LaTeX Docker setup under `tools/docker/` (see [Optional Docker](#optional-docker)).

## Optional Docker

For local LaTeX/TikZ compilation without Kroki:

1. Build and start the container from the project root:
   ```bash
   docker compose -f tools/docker/docker-compose.latex.yml build
   docker compose -f tools/docker/docker-compose.latex.yml up -d
   ```
2. Compile a `.tex` file inside the container (e.g. from `examples/`):
   ```bash
   docker exec -it uml-mcp-latex xelatex -interaction=nonstopmode /workspace/examples/example-tikz-flowchart.tex
   ```

See `tools/docker/README.md` for details and volume mounts.
