# Agent trace plugin

`uml-mcp-plugin-trace` adds one diagram type, `agent_trace`: the steps of an agent run on a
time axis. User turns, LLM calls, tool calls, retrievals, sub-agents, guardrails, memory,
replies and errors each get a colour and an icon, nested under the step that started them,
with their duration, tokens and cost.

| Output | What you get |
| --- | --- |
| `svg` | A static waterfall: a summary header (total time, tokens in, out and cached, cost, tool calls, errors and retries), one bar per step, errors and retries marked, and a legend |
| `html` | An interactive page: the waterfall and a flow (sequence) view, folding sub-agents, a detail card per step, the critical path, light and dark, SVG, PNG and HTML export |

The page runs locally with no network access, in the sandboxed plugin frame, under a
hash-based Content-Security-Policy. It ships with uml-mcp and is on by default
(`plugins.bundled`); with `plugins.bundled: false`, list `trace` in `plugins.enabled` to keep it.

## Source format

```json
{
  "title": "Support agent: refund window question",
  "model": "gpt-4o",
  "steps": [
    {"id": "agent", "kind": "subagent", "name": "Support agent", "start_ms": 0, "end_ms": 4210},
    {"id": "ask", "parent": "agent", "kind": "user", "name": "What is the refund window?", "start_ms": 0, "end_ms": 15},
    {"id": "search", "parent": "agent", "kind": "retrieval", "name": "Search policy docs", "tool": "elasticsearch",
     "start_ms": 910, "end_ms": 1270,
     "docs": [{"title": "Refunds and cancellations", "score": 0.91, "source": "https://example.com/help/refunds"}]},
    {"id": "lookup", "parent": "agent", "kind": "tool", "name": "get_customer_plan", "tool": "postgres",
     "start_ms": 1270, "end_ms": 1730, "status": "error", "note": "Connection timed out"},
    {"id": "lookup-2", "parent": "agent", "kind": "tool", "name": "get_customer_plan", "tool": "postgres",
     "start_ms": 1730, "end_ms": 1980, "status": "retry"},
    {"id": "answer", "parent": "agent", "kind": "llm", "name": "Compose the answer", "model": "gpt-4o",
     "start_ms": 2140, "end_ms": 4120, "tokens": {"in": 2310, "out": 186, "cached": 1024}, "cost_usd": 0.0061},
    {"id": "reply", "parent": "agent", "kind": "reply", "name": "Full refund available", "start_ms": 4120, "end_ms": 4210}
  ]
}
```

| Field | Notes |
| --- | --- |
| `title`, `model`, `theme` | `model` is the run's default model; `theme` is `auto` (default), `dark` or `light`. `auto` follows the system in the page and is dark in static output |
| `steps[].id` | Required and unique |
| `steps[].parent` | The id of the step that started this one; children are drawn under it and fold with it |
| `steps[].kind` | `user`, `llm`, `tool`, `retrieval`, `subagent`, `guardrail`, `memory`, `reply` or `error` |
| `steps[].name` | What the row and the flow arrow say |
| `steps[].start_ms`, `end_ms` | Milliseconds from any origin (usually the start of the run); `end_ms` is never before `start_ms` |
| `steps[].tokens` | `{in, out, cached}`, all optional numbers |
| `steps[].cost_usd`, `model`, `tool` | Shown in the row and the detail card; `model` and `tool` also pick the documentation link |
| `steps[].input`, `output` | Free text or any JSON value; kept up to 4000 characters, previewed in the card with **Show all** |
| `steps[].docs` | Retrieved documents: `[{title, score, source}]`, up to 20; an `https://` source opens on click |
| `steps[].status` | `ok` (default), `error` (the attempt failed) or `retry` (a later attempt after a failure) |
| `steps[].note` | A short remark, such as the error message |

Validation collects every problem at once and says how to fix it: unknown fields or kinds,
an unknown parent (with the known ids), a parent chain that loops, `end_ms` before
`start_ms`, and an id used twice. A trace has at most 400 steps
(`plugins.settings.trace.max_steps` lowers that).

### OpenTelemetry spans

A trace exported with the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
works as is: give `spans` (or a bare list of spans) instead of `steps`.

```json
{
  "title": "Research agent",
  "spans": [
    {"span_id": "a1", "name": "invoke_agent researcher",
     "start": "2026-11-07T10:00:00.000Z", "end": "2026-11-07T10:00:03.400Z",
     "attributes": {"gen_ai.operation.name": "invoke_agent"}},
    {"span_id": "c1", "parent_span_id": "a1", "name": "chat claude-sonnet-5-5",
     "start": "2026-11-07T10:00:00.050Z", "end": "2026-11-07T10:00:01.100Z",
     "attributes": {"gen_ai.operation.name": "chat", "gen_ai.request.model": "claude-sonnet-5-5",
                    "gen_ai.usage.input_tokens": 1450, "gen_ai.usage.output_tokens": 120}}
  ]
}
```

| Span field | Becomes |
| --- | --- |
| `span_id` / `spanId`, `parent_span_id` / `parentSpanId` | `id`, `parent` |
| `start`, `end` (or `start_time_unix_nano`...) | `start_ms`, `end_ms` from the earliest span. ISO 8601 strings, or numbers read by size as nanoseconds, microseconds, milliseconds or seconds since the epoch |
| `gen_ai.operation.name` | `chat`, `text_completion`, `generate_content` → `llm`; `execute_tool` → `tool`; `invoke_agent`, `create_agent` → `subagent`; `embeddings`, `retrieval` → `retrieval`. Without it the span name decides (`guard`, `retriev`, `memory`...) |
| `gen_ai.request.model`, `gen_ai.response.model` | `model` |
| `gen_ai.usage.input_tokens`, `output_tokens`, `cache_read.input_tokens` | `tokens` |
| `gen_ai.tool.name` | `tool` |
| `status.code: ERROR`, `error.type` | `status: error` and the `note` |

Attributes may be a plain mapping or the OTLP JSON `[{key, value: {stringValue}}]` list.

## The page

- **Waterfall / Flow** switch the view. The flow view draws one lane for the user, the agent,
  each model, each tool or retriever and each sub-agent, with a call arrow and a dashed return
  arrow per step carrying its duration and tokens.
- **Click a step** (in either view, or press Enter on a focused row) for its card: kind, model,
  tool, start, duration, status, tokens, cost, the note, the input and output (as plain text,
  long text folded behind **Show all**), the retrieved documents with score bars, and links to
  the parent and the steps inside it.
- **Open documentation** appears when the step names a known model (Claude, OpenAI, Gemini,
  Mistral, Cohere) or a known service as its tool (`postgres`, `elasticsearch`, `redis`,
  `aws:s3`...). It uses the [D3 plugin's](d3.md) map of official docs and opens through the host
  (`ui/open-link`) inside the MCP App.
- **Hover** a row for its start, end and duration.
- The **caret** next to a step with children folds it (or **ArrowLeft** / **ArrowRight** on a
  focused row); **Collapse** folds every sub-agent.
- **Critical path** dims everything but the chain of steps that decides the total time: the
  last child to finish, then the last to finish before it started, and so on, inside every step.
- **Fit**, **−** / **+**, drag and scroll pan and zoom; the page opens fitted to its frame.
- **Export** saves the current view as SVG or PNG (in the current theme, folded rows left out),
  or the whole page as HTML.

Inside the MCP App viewer the page drops its own title, since the viewer shows one.

## Try these prompts

| Ask | Notes |
| --- | --- |
| *"Show this agent run as a trace: the user question, a retrieval, two tool calls (one retried), the LLM calls and the reply, with tokens and cost."* | The bundled example |
| *"Here are my OpenTelemetry spans, draw the trace and highlight the critical path."* | Paste the spans as `spans` |
| *"Compare where the time goes in this multi-agent run: a planner and two researcher sub-agents."* | Nest each sub-agent's steps under it with `parent` |
