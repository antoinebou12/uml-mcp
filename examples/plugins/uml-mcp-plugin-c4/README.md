# uml-mcp-plugin-c4

A C4 model you can drill into, for [UML-MCP](https://github.com/antoinebou12/uml-mcp). One JSON
model covers people, software systems, containers and components; the `c4_model` type draws
any level in C4 notation (`svg`) or as a page (`html`) where a click on a system opens its
containers, a click on a container opens its components, and breadcrumbs lead back up.

It ships inside the `uml-mcp` package and is on by default. From a checkout:

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-c4
uml-mcp plugins enable c4
```

```json
{
  "title": "My system",
  "people": [{"id": "user", "name": "User"}],
  "systems": [{"id": "app", "name": "My System", "containers": [
    {"id": "api", "name": "API", "technology": "Python"},
    {"id": "db", "name": "Database", "technology": "PostgreSQL", "kind": "db", "service": "postgres"}
  ]}],
  "relations": [
    {"from": "user", "to": "api", "label": "Uses", "technology": "HTTPS"},
    {"from": "api", "to": "db", "label": "Reads and writes", "technology": "SQL"}
  ],
  "view": {"level": "container", "focus": "app"}
}
```

See [`docs/plugins/c4.md`](../../../docs/plugins/c4.md) for the source reference, how relations
are lifted between levels, and the page controls. Documentation links reuse the D3 plugin's
map of official vendor docs.
