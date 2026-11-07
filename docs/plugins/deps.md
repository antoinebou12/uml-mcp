---
title: Dependency graphs
description: "The deps plugin draws a project's dependency tree from package.json, package-lock.json, pyproject.toml, requirements.txt or uv.lock, as an interactive page or a static SVG."
---

# Dependency graph plugin

`uml-mcp-plugin-deps` adds one diagram type, `dependency_graph`: the dependency tree of a
project, drawn from the manifest or lock file you already have. It ships with uml-mcp and is on
by default (`plugins.bundled`).

| Type | Output | Opens as |
| --- | --- | --- |
| `dependency_graph` | `html`, `svg` | A layered tree from the project to its deepest dependency, with a force-graph view in the page |

Parsing uses the Python standard library (`json`, `tomllib`) and never fetches anything: no
registry lookups, no CDN. The page runs in the sandboxed plugin frame under a hash-based
Content-Security-Policy.

## Inputs

Send the file text as `code`. The kind is detected from the text:

| File | Detected by | What it adds |
| --- | --- | --- |
| `package.json` | JSON with `name`, `version` or `dependencies` | `dependencies`, `devDependencies`, `peerDependencies` (optional ones via `peerDependenciesMeta`) and `optionalDependencies`, with their ranges |
| `package-lock.json` v2/v3 | JSON with `lockfileVersion` and `packages` | The installed tree: nested `node_modules` resolved like Node does, workspace links followed, versions, licences and the `dev`, `optional`, `peer` flags |
| `pyproject.toml` | TOML with `[project]`, `[tool]` or `[dependency-groups]` | PEP 621 `dependencies` and `optional-dependencies` (each extra is a group), PEP 735 `dependency-groups` (with `include-group`), Poetry `dependencies`, `dev-dependencies` and `group.<name>.dependencies` |
| `requirements.txt` | anything else | Pins, ranges, extras, environment markers, `name @ url`, `-e ...#egg=name`; `-r`/`-c` includes are noted, not read; `--hash` and index options are skipped |
| `uv.lock` | TOML with `[[package]]` | The resolved tree from the project (`source = { editable = "." }` or `virtual`), its extras and dev groups, the extras its dependencies ask for, and the ranges from `[package.metadata]` |
| JSON graph | JSON with a `nodes` list | Anything else, see below |

A `package-lock.json` with `lockfileVersion` 1 and a `poetry.lock` are refused with a message
saying what to send instead. Keep the source under the server's limit (`MCP_MAX_CODE_LENGTH`,
500,000 characters by default); the lock files of most applications fit.

### JSON graph

```json
{
  "title": "billing-service dependencies",
  "ecosystem": "pypi",
  "root": "billing-service",
  "nodes": [
    {"id": "billing-service", "version": "1.0.0", "license": "Apache-2.0"},
    {"id": "fastapi@0.115.4", "version": "0.115.4", "license": "MIT"},
    {"id": "pytest@8.3.3", "version": "8.3.3", "dev": true}
  ],
  "edges": [
    {"from": "billing-service", "to": "fastapi@0.115.4", "range": ">=0.115"},
    {"from": "billing-service", "to": "pytest@8.3.3", "range": ">=8"}
  ]
}
```

| Field | Notes |
| --- | --- |
| `root` | The id of the project node (added when it is not in `nodes`) |
| `nodes[]` | `id` (required, unique), `name` (defaults to the id without `@version`), `version`, `license`, `dev` (true makes it a dev dependency), `kind` (`runtime`, `dev`, `optional`, `peer`), `group`, `ecosystem`, `docs` (an `https://` link) |
| `edges[]` | `from`, `to` (node ids), `range`, `kind` |
| `ecosystem` | `npm` or `pypi`: each package's **Open documentation** goes to its npm or PyPI page |
| `title`, `theme` | Any JSON source also takes `title` and `theme` (`auto`, `light`, `dark`) |

## Reading the picture

- The project sits at the left; direct dependencies form the next column and, with a lock
  file, each transitive level the one after. A package reached along several paths appears
  once, at its shallowest level, under the first parent that reaches it.
- Pills read `name@version`, or `name range` when only a range is known (a manifest).
- Colour is the kind: **runtime**, **dev**, **optional**, **peer**. A transitive package takes
  the strongest kind of the direct dependencies that pull it in, unless the lock file says
  otherwise.
- A licence badge sits at the right of the pill when the source knows it (lock files and the
  JSON graph).
- A dashed amber outline and `×N` flag a package installed in several versions.
- The header counts the packages, direct and transitive, and the legend counts each kind.

## The interactive page

| Action | How |
| --- | --- |
| Collapse or expand a subtree | The `−`/`+` beside a package (with the number of hidden packages), or ← / → on a focused package; **Expand** and **Collapse** for all |
| Search | Type in the box: matches are highlighted and their subtrees opened. **Enter** selects the first one. `/` focuses the box |
| Hide dev, optional or peer dependencies | The kind buttons in the toolbar |
| Details | Click a package: version, requested range, licence, registry, level, the path from the project, other versions, **Required by**, **Depends on**, and **Open documentation** |
| Path | The selected package's path from the project is highlighted, the rest dimmed |
| Views | **Tree** (layered) or **Graph** (force-directed, every edge) |
| Zoom and pan | Wheel, drag, `+`/`−`, **Fit** |
| Theme | ◐ switches light and dark; `auto` follows the system |
| Export | **Export** → SVG image, PNG image, HTML page (the page as it is, theme included) |

Pages open fitted to their frame. A tree too tall to read when fitted opens at a readable
scale with the project in view; large graphs start with the third level and below collapsed.
Inside the MCP App viewer the page drops its own title and **Open documentation** goes through
the host (`ui/open-link`).

## Size limit

Graphs are cut to the packages closest to the project, breadth first, with a notice
(*Showing 300 of 1,204 packages*). The default is 300; raise or lower it:

```yaml
# uml-mcp.yaml
plugins:
  settings:
    deps:
      max_nodes: 600   # 1 to 2000
```

## Example prompts

| Prompt | Source |
| --- | --- |
| *"Show the dependency tree of this project, with dev dependencies."* | `uv.lock` or `package-lock.json` |
| *"Which of our direct dependencies are dev-only?"* | `pyproject.toml` or `package.json` |
| *"Do we have duplicate versions of anything?"* | A lock file; look for the amber outline |
