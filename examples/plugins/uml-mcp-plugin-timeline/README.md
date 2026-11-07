# uml-mcp-plugin-timeline

Project timelines and product roadmaps for [UML-MCP](https://github.com/antoinebou12/uml-mcp):
swimlanes, task bars with progress and status, phases, milestones, releases, dependency arrows
and a today line, as a static SVG or an interactive page that zooms from quarters to days.

It ships inside the `uml-mcp` package and is on by default. From a checkout:

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-timeline
uml-mcp plugins enable timeline
```

```json
{
  "title": "Roadmap",
  "lanes": [{"id": "eng", "name": "Engineering"}, {"id": "design", "name": "Design"}],
  "items": [
    {"id": "spec", "lane": "design", "name": "Design spec", "start": "2027-01-04", "end": "2027-01-22"},
    {"id": "build", "lane": "eng", "name": "Build", "start": "2027-01-25", "end": "2027-03-19", "depends_on": ["spec"]},
    {"id": "ship", "lane": "eng", "name": "Ship", "kind": "release", "start": "2027-03-22", "depends_on": ["build"]}
  ]
}
```

See [`docs/plugins/timeline.md`](../../../docs/plugins/timeline.md) for the source reference
and the page controls.
