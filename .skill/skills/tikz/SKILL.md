---
name: tikz
description: >-
  Writes valid tikz diagram source for uml-mcp (diagram_type=tikz). TikZ/PGF graphics (LaTeX) Use when the user asks for tikz or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# tikz diagram (uml-mcp)

**`diagram_type`:** `tikz`  
**Backend:** `tikz`  
**Output formats:** png, svg, jpeg, pdf

TikZ/PGF graphics (LaTeX)

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Use TikZ styles (`\tikzset`) and `xcolor` for palettes.
- No MCP `theme` param.

## Starter template

```tikz
\documentclass[border=2pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{shapes,arrows,positioning}
\begin{document}
\begin{tikzpicture}[node distance=2cm, auto]
  \node[rectangle, draw] (start) {Start};
  \node[diamond, draw, below of=start, aspect=2] (decision) {Decision?};
  \node[rectangle, draw, below left=1.2cm and 1cm of decision] (yes) {Yes};
  \node[rectangle, draw, below right=1.2cm and 1cm of decision] (no) {No};
  \draw[->] (start) -- (decision);
  \draw[->] (decision) -- node[near start, left] {Y} (yes);
  \draw[->] (decision) -- node[near start, right] {N} (no);
\end{tikzpicture}
\end{document}
```

## Example

```tikz
\documentclass[border=2pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{shapes,arrows,positioning}
\begin{document}
\begin{tikzpicture}[node distance=1.8cm, auto]
  \node[rectangle, draw] (start) {Start};
  \node[diamond, draw, aspect=2, below of=start] (dec) {OK?};
  \node[rectangle, draw, below left=1.2cm and 1cm of dec] (yes) {Yes};
  \node[rectangle, draw, below right=1.2cm and 1cm of dec] (no) {No};
  \draw[->] (start) -- (dec);
  \draw[->] (dec) -- node[near start, left] {Y} (yes);
  \draw[->] (dec) -- node[near start, right] {N} (no);
\end{tikzpicture}
\qquad
\begin{tikzpicture}
  \node[circle, draw] (a) at (0,0) {1};
  \node[circle, draw] (b) at (2,0) {2};
  \node[circle, draw] (c) at (1,1.5) {3};
  \draw (a) -- (b) -- (c) -- (a);
\end{tikzpicture}
\qquad
\begin{tikzpicture}[scale=0.7]
  \draw[step=1, gray, thin] (-1,-1) grid (1,1);
  \draw[thick, ->] (-1.2,0) -- (1.2,0) node[right] {$x$};
  \draw[thick, ->] (0,-1.2) -- (0,1.2) node[above] {$y$};
  \fill (0,0) circle (2pt);
\end{tikzpicture}
\end{document}
```

## Render with uml-mcp

1. Set `diagram_type` to `tikz` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
