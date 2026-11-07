---
name: uml-mcp-deps
description: Draw dependency graphs from package.json, pyproject.toml, requirements.txt and lock files (dependency_graph).
---

# Dependency graphs

Follow `skill://uml-mcp-diagrams/SKILL.md`. A layered tree from the project to its deepest dependency, coloured by kind (runtime, dev, optional, peer), with licences and duplicate versions flagged. The page searches, collapses, filters kinds, switches to a force graph and opens each package's PyPI or npm page.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `dependency_graph` | the dependency tree of a project from its package.json, pyproject.toml, requirements.txt or a lock file | Show the dependency tree of this project from its uv.lock, with dev dependencies and duplicate versions. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Inputs

| File | What it adds |
| --- | --- |
| `package.json` | Direct `dependencies`, `devDependencies`, `peerDependencies` and `optionalDependencies` with their ranges |
| `package-lock.json` v2/v3 | The installed tree: versions, licences, dev/optional/peer flags |
| `pyproject.toml` | PEP 621 `dependencies`, `optional-dependencies` (extras), `dependency-groups`, Poetry tables |
| `requirements.txt` | Pins, ranges, extras and markers (`-r` includes are noted, not read) |
| `uv.lock` | The resolved tree with extras, dev groups and the ranges asked for |
| JSON graph | `{"root", "nodes": [{"id", "version", "license", "dev", "group"}], "edges": [{"from", "to", "range"}]}` |

Send the file text as `code`. Validation names the file kind it detected and the line or field that failed.

## Example

```json
{"name":"storefront","version":"2.4.0","license":"MIT","dependencies":{"react":"^18.3.1","react-dom":"^18.3.1","zod":"^3.23.8","@tanstack/react-query":"^5.59.0"},"peerDependencies":{"typescript":">=5.4"},"optionalDependencies":{"fsevents":"^2.3.3"},"devDependencies":{"vite":"^5.4.10","vitest":"^2.1.4","eslint":"^9.14.0"}}
```
