# Optional LaTeX / TikZ local compilation

This directory provides an optional Docker setup for compiling LaTeX/TikZ locally when you do not want to use the Kroki service.

- **Default**: The UML-MCP server uses [Kroki](https://kroki.io) for TikZ rendering (no local TeX required).
- **Optional**: Set `USE_LOCAL_LATEX=true` and use this container to compile `.tex` files on your machine.

## Quick start

```bash
# From project root
docker compose -f tools/docker/docker-compose.latex.yml build
docker compose -f tools/docker/docker-compose.latex.yml up -d

# Compile an example (inside container)
docker exec -it uml-mcp-latex bash -c "cd /workspace/examples && xelatex -interaction=nonstopmode example-tikz-flowchart.tex"

# Output appears in ./output if you mount it; or copy from container.
```

## Environment

- `LATEX_ENGINE`: `xelatex` (default) or `pdflatex`, `lualatex`.

## Volumes

- `../../output` → project `output/` directory for generated PDFs.
- `../../examples` → read-only mount of `examples/` for sample `.tex` files.

## See also

- [docs/diagrams/tikz.md](../../docs/diagrams/tikz.md) — TikZ support and formats.
- [Kroki TikZ](https://kroki.io/#tikz) — default online rendering.
