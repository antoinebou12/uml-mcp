# uml-mcp-plugin-trace

Agent run traces for [UML-MCP](https://github.com/antoinebou12/uml-mcp): the `agent_trace`
diagram type draws LLM calls, tool calls, retrievals, sub-agents, guardrails, memory, replies
and errors on a time axis, nested under their parent, with durations, tokens and cost.

It ships inside the `uml-mcp` package and is on by default. From a checkout:

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-trace
uml-mcp plugins enable trace
```

* `svg`: a static waterfall with a summary header (total time, tokens in, out and cached,
  cost, tool calls, errors and retries), errors and retries marked.
* `html`: an interactive page with a waterfall and a flow view, folding sub-agents, a detail
  card per step, the critical path, light and dark, and SVG, PNG and HTML export.

```json
{
  "title": "My agent run",
  "model": "gpt-4o",
  "steps": [
    {"id": "q", "kind": "user", "name": "User question", "start_ms": 0, "end_ms": 10},
    {"id": "llm", "kind": "llm", "name": "Answer", "start_ms": 10, "end_ms": 900,
     "tokens": {"in": 500, "out": 120}},
    {"id": "out", "kind": "reply", "name": "Reply", "start_ms": 900, "end_ms": 920}
  ]
}
```

OpenTelemetry span lists with the GenAI semantic conventions (`gen_ai.request.model`,
`gen_ai.usage.input_tokens`...) are accepted as `spans`. The full format is in
[docs/plugins/trace.md](../../../docs/plugins/trace.md).
