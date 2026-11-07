---
name: agent_trace
description: >-
  Writes valid agent_trace JSON for uml-mcp (diagram_type=agent_trace, bundled plugin trace). Use when the user asks for an agent run trace: LLM calls, tool calls, retrievals and sub-agents on a timeline with tokens and cost; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# agent_trace diagram (uml-mcp plugin `trace`)

**`diagram_type`:** `agent_trace`  
**Backend:** `plugin:trace` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

Agent run trace: steps (user, llm, tool, retrieval, subagent, guardrail, memory, reply, error) as a waterfall on a time axis with tokens, cost, errors and retries; the html page adds a flow view, folding, step details and the critical path. JSON steps or OpenTelemetry GenAI spans; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/agent-trace/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> Show this agent run as a trace: the user question, a retrieval, two tool calls (one retried), the LLM calls and the reply, with tokens and cost.

## Notation tips

- `steps`: `id`, `parent`, `kind` (`user`, `llm`, `tool`, `retrieval`, `subagent`, `guardrail`, `memory`, `reply`, `error`), `name`, `start_ms`, `end_ms` (relative to the run start).
- Optional per step: `tokens` (`in`, `out`, `cached`), `cost_usd`, `model`, `tool`, `input`, `output`, `docs` (`title`, `score`, `source`), `status` (`ok`, `error`, `retry`), `note`.
- Nest steps with `parent` (a sub-agent's calls under it); `end_ms` must not be before `start_ms` and ids are unique.
- OpenTelemetry works too: `spans` with `span_id`, `parent_span_id`, `name`, `start`, `end` (ISO 8601 or epoch numbers) and GenAI `attributes` (`gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.tool.name`).
- `svg` is the waterfall with a summary header; `html` adds a flow view, folding, step details and the critical path.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Support agent: refund window question","model":"gpt-4o","steps":[{"id":"agent","kind":"subagent","name":"Support agent","start_ms":0,"end_ms":4210},{"id":"ask","parent":"agent","kind":"user","name":"What is the refund window for annual plans?","start_ms":0,"end_ms":15,"input":"Hi! I bought the annual Pro plan three weeks ago. What is the refund window for annual plans, and can I still get my money back?"},{"id":"moderate","parent":"agent","kind":"guardrail","name":"Input moderation","tool":"omni-moderation","start_ms":15,"end_ms":140,"output":"flagged: false"},{"id":"plan","parent":"agent","kind":"llm","name":"Plan the answer","model":"gpt-4o-mini","start_ms":140,"end_ms":910,"tokens":{"in":612,"out":74,"cached":512},"cost_usd":0.00014,"output":"Call search_policies(\"refund annual plan\"), then get_customer_plan(customer_id), then calculate_refund."},{"id":"search","parent":"agent","kind":"retrieval","name":"Search policy docs","tool":"elasticsearch","start_ms":910,"end_ms":1270,"input":"refund window annual plan","docs":[{"title":"Refunds and cancellations","score":0.91,"source":"https://example.com/help/refunds"},{"title":"Annual plan terms","score":0.84,"source":"https://example.com/legal/annual-terms"},{"title":"Changing your plan","score":0.42,"source":"https://example.com/help/change-plan"}]},{"id":"lookup","parent":"agent","kind":"tool","name":"get_customer_plan","tool":"postgres","start_ms":1270,"end_ms":1730,"input":"{\"customer_id\": \"c_4821\"}","status":"error","note":"Connection timed out after 450 ms"},{"id":"lookup-retry","parent":"agent","kind":"tool","name":"get_customer_plan","tool":"postgres","start_ms":1730,"end_ms":1980,"input":"{\"customer_id\": \"c_4821\"}","output":"{\"plan\": \"pro-annual\", \"purchased\": \"2026-10-17\", \"paid_usd\": 240}","status":"retry","note":"Second attempt succeeded"},{"id":"refund","parent":"agent","kind":"tool","name":"calculate_refund","start_ms":1980,"end_ms":2140,"input":"{\"plan\": \"pro-annual\", \"days_since_purchase\": 21}","output":"{\"eligible\": true, \"amount_usd\": 240, \"window_days\": 30}"},{"id":"answer","parent":"agent","kind":"llm","name":"Compose the answer","model":"gpt-4o","start_ms":2140,"end_ms":4120,"tokens":{"in":2310,"out":186,"cached":1024},"cost_usd":0.0061,"input":"System: answer from the retrieved policy only.\nContext: Refunds and cancellations; Annual plan terms.\nCustomer plan: pro-annual, 21 days ago.","output":"Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now."},{"id":"reply","parent":"agent","kind":"reply","name":"Full refund available (21 of 30 days)","start_ms":4120,"end_ms":4210,"output":"Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now."}]}
```
