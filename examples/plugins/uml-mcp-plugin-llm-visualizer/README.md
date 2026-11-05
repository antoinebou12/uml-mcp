# uml-mcp-plugin-llm-visualizer

Interactive 2D and 3D LLM architecture diagrams for
[UML-MCP](https://github.com/antoinebou12/uml-mcp). The plugin renders the same JSON
source as either `llm_2d` or `llm_3d`.

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-llm-visualizer
uml-mcp plugins enable llm-visualizer
```

Restart the server after enabling the plugin. Both diagram types support a static SVG
preview and a standalone HTML viewer. The viewer runs locally, has no external
dependencies, and can switch between 2D and 3D.

```json
{
  "title": "Decoder-only transformer",
  "layers": [
    {"id": "tokens", "label": "Token IDs", "kind": "input", "shape": [2048]},
    {"id": "embed", "label": "Embedding", "kind": "embedding", "shape": [2048, 4096]},
    {"id": "blocks", "label": "Transformer block", "kind": "attention", "repeat": 32},
    {"id": "logits", "label": "Vocabulary logits", "kind": "output", "shape": [32000]}
  ],
  "connections": [
    {"from": "tokens", "to": "embed"},
    {"from": "embed", "to": "blocks", "label": "hidden states"},
    {"from": "blocks", "to": "logits"}
  ]
}
```

See [`docs/plugins/llm-visualizer.md`](../../../docs/plugins/llm-visualizer.md) for the
source reference and controls.
