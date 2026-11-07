# uml-mcp-plugin-deps

A UML-MCP renderer for one diagram type, `dependency_graph`: the dependency tree of a
project, drawn from the file you already have.

| Input | Detected by | What it adds |
| --- | --- | --- |
| `package.json` | JSON with `name` / `dependencies` | Direct dependencies by kind, with their ranges |
| `package-lock.json` v2/v3 | JSON with `lockfileVersion` and `packages` | The installed tree, versions, licences |
| `pyproject.toml` | TOML with `[project]` or `[tool.poetry]` | Dependencies, extras, dependency groups |
| `requirements.txt` | anything else | Pins, ranges, extras, markers |
| `uv.lock` | TOML with `[[package]]` | The resolved tree, extras and dev groups |
| JSON graph | JSON with `nodes` | `{root, nodes: [{id, version, license, dev, group}], edges: [{from, to, range}]}` |

* `svg`: a layered tree, the project at the left, then direct and transitive levels.
  Pills read `name@version`, coloured by kind (runtime, dev, optional, peer), with a
  licence badge when known; packages present in several versions get a dashed amber
  outline and a `×N` mark. A legend and counts head the picture.
* `html`: a standalone page (strict Content-Security-Policy, no network) with collapse and
  expand, search, kind filters, a detail card (version, requested range, licence, who
  depends on it, what it pulls in, the path from the project, Open documentation on PyPI
  or npm), a force-graph view, light and dark themes, and SVG, PNG and HTML export.

Parsing uses the Python standard library only (`json`, `tomllib`) and never fetches
anything. Graphs larger than `plugins.settings.deps.max_nodes` (default 300, at most 2000)
are cut to the packages closest to the project, with a notice.

```yaml
plugins:
  settings:
    deps:
      max_nodes: 500
```

See `docs/plugins/deps.md` in the uml-mcp repository.
