---
name: dependency_graph
description: >-
  Writes valid dependency_graph JSON for uml-mcp (diagram_type=dependency_graph, bundled plugin deps). Use when the user asks for the dependency tree of a project from its package.json, pyproject.toml, requirements.txt or a lock file; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# dependency_graph diagram (uml-mcp plugin `deps`)

**`diagram_type`:** `dependency_graph`  
**Backend:** `plugin:deps` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Dependency graph of a project from its package.json, package-lock.json, pyproject.toml, requirements.txt or uv.lock (auto-detected): layered tree, kind colours, licences, duplicate versions; html (search, collapse, force view) or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/deps/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Show the dependency tree of this project from its uv.lock, with dev dependencies and duplicate versions.

## Notation tips

- Paste the file as it is: `package.json`, `package-lock.json` (v2/v3), `pyproject.toml`, `requirements.txt` or `uv.lock`; the kind is detected. A lock file adds the transitive levels.
- Or write a graph: `root`, `nodes` (`id`, `version`, `license`, `dev`, `group`) and `edges` (`from`, `to`, `range`); a top-level `ecosystem` (`npm`, `pypi`) links each package to its registry.
- Colours: runtime, dev, optional, peer. A dashed amber outline marks a package present in several versions.
- Nothing is fetched: licences come from the lock file or the graph. Large locks are capped (300 packages by default, `plugins.settings.deps.max_nodes`).

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"name":"storefront","version":"2.4.0","license":"MIT","dependencies":{"react":"^18.3.1","react-dom":"^18.3.1","zod":"^3.23.8","@tanstack/react-query":"^5.59.0"},"peerDependencies":{"typescript":">=5.4"},"optionalDependencies":{"fsevents":"^2.3.3"},"devDependencies":{"vite":"^5.4.10","vitest":"^2.1.4","eslint":"^9.14.0"}}
```
