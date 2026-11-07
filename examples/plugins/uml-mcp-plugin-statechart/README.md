# uml-mcp-plugin-statechart

A UML-MCP renderer for the `state_machine` diagram type: XState-like JSON drawn as a
statechart (compound containers, parallel regions, initial, final and history states,
labelled orthogonal transitions), as a static SVG or an HTML simulator that fires events,
highlights the active states and keeps an undoable step log.

It ships inside `uml-mcp` and is on by default. See
[docs/plugins/statechart.md](../../../docs/plugins/statechart.md) for the source format.

```json
{"id": "light", "initial": "green", "states": {
  "green": {"on": {"TIMER": "yellow"}},
  "yellow": {"on": {"TIMER": "red"}},
  "red": {"on": {"TIMER": "green"}}}}
```
