---
name: uml-mcp-agent-trace
description: Draw agent run traces with LLM, tool, retrieval and sub-agent steps on a timeline (agent_trace).
---

# Agent traces

Follow `skill://uml-mcp-diagrams/SKILL.md`. A waterfall of an agent run with tokens, cost, errors and retries, and an interactive page with a flow view, folding sub-agents, a detail card per step and the critical path.

## Types

| Type | Use for | Example prompt |
| --- | --- | --- |
| `agent_trace` | an agent run trace: LLM calls, tool calls, retrievals and sub-agents on a timeline with tokens and cost | Show this agent run as a trace: the user question, a retrieval, two tool calls (one retried), the LLM calls and the reply, with tokens and cost. |

## Steps

1. Check the live catalog (`list_diagram_types` or `uml://types`); the bundled plugins are on by default, but a server may turn them off with `plugins.bundled: false`.
2. Read the type's example from `uml://examples` and keep its field names.
3. Call `validate_uml`; an error names the field and, for a bad reference, lists the known ids, so fix it and validate again.
4. Render with `generate_uml_image` for a chat image, or `generate_uml` with `output_format: "html"` for the interactive page in the MCP App viewer. Clients without MCP Apps still get the PNG and SVG.
5. Pass `theme` (`auto`, `dark`, `light`) rather than editing colours.

## Example

```json
{"title":"Support agent: refund window question","model":"gpt-4o","steps":[{"id":"agent","kind":"subagent","name":"Support agent","start_ms":0,"end_ms":4210},{"id":"ask","parent":"agent","kind":"user","name":"What is the refund window for annual plans?","start_ms":0,"end_ms":15,"input":"Hi! I bought the annual Pro plan three weeks ago. What is the refund window for annual plans, and can I still get my money back?"},{"id":"moderate","parent":"agent","kind":"guardrail","name":"Input moderation","tool":"omni-moderation","start_ms":15,"end_ms":140,"output":"flagged: false"},{"id":"plan","parent":"agent","kind":"llm","name":"Plan the answer","model":"gpt-4o-mini","start_ms":140,"end_ms":910,"tokens":{"in":612,"out":74,"cached":512},"cost_usd":0.00014,"output":"Call search_policies(\"refund annual plan\"), then get_customer_plan(customer_id), then calculate_refund."},{"id":"search","parent":"agent","kind":"retrieval","name":"Search policy docs","tool":"elasticsearch","start_ms":910,"end_ms":1270,"input":"refund window annual plan","docs":[{"title":"Refunds and cancellations","score":0.91,"source":"https://example.com/help/refunds"},{"title":"Annual plan terms","score":0.84,"source":"https://example.com/legal/annual-terms"},{"title":"Changing your plan","score":0.42,"source":"https://example.com/help/change-plan"}]},{"id":"lookup","parent":"agent","kind":"tool","name":"get_customer_plan","tool":"postgres","start_ms":1270,"end_ms":1730,"input":"{\"customer_id\": \"c_4821\"}","status":"error","note":"Connection timed out after 450 ms"},{"id":"lookup-retry","parent":"agent","kind":"tool","name":"get_customer_plan","tool":"postgres","start_ms":1730,"end_ms":1980,"input":"{\"customer_id\": \"c_4821\"}","output":"{\"plan\": \"pro-annual\", \"purchased\": \"2026-10-17\", \"paid_usd\": 240}","status":"retry","note":"Second attempt succeeded"},{"id":"refund","parent":"agent","kind":"tool","name":"calculate_refund","start_ms":1980,"end_ms":2140,"input":"{\"plan\": \"pro-annual\", \"days_since_purchase\": 21}","output":"{\"eligible\": true, \"amount_usd\": 240, \"window_days\": 30}"},{"id":"answer","parent":"agent","kind":"llm","name":"Compose the answer","model":"gpt-4o","start_ms":2140,"end_ms":4120,"tokens":{"in":2310,"out":186,"cached":1024},"cost_usd":0.0061,"input":"System: answer from the retrieved policy only.\nContext: Refunds and cancellations; Annual plan terms.\nCustomer plan: pro-annual, 21 days ago.","output":"Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now."},{"id":"reply","parent":"agent","kind":"reply","name":"Full refund available (21 of 30 days)","start_ms":4120,"end_ms":4210,"output":"Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now."}]}
```
