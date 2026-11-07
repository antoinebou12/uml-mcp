"""Example sources: a RAG agent run, the same kind of run as OpenTelemetry spans, a template."""

from __future__ import annotations

import json

_RAG = {
    "title": "Support agent: refund window question",
    "model": "gpt-4o",
    "steps": [
        {
            "id": "agent",
            "kind": "subagent",
            "name": "Support agent",
            "start_ms": 0,
            "end_ms": 4210,
        },
        {
            "id": "ask",
            "parent": "agent",
            "kind": "user",
            "name": "What is the refund window for annual plans?",
            "start_ms": 0,
            "end_ms": 15,
            "input": "Hi! I bought the annual Pro plan three weeks ago. What is the refund window for annual plans, and can I still get my money back?",
        },
        {
            "id": "moderate",
            "parent": "agent",
            "kind": "guardrail",
            "name": "Input moderation",
            "tool": "omni-moderation",
            "start_ms": 15,
            "end_ms": 140,
            "output": "flagged: false",
        },
        {
            "id": "plan",
            "parent": "agent",
            "kind": "llm",
            "name": "Plan the answer",
            "model": "gpt-4o-mini",
            "start_ms": 140,
            "end_ms": 910,
            "tokens": {"in": 612, "out": 74, "cached": 512},
            "cost_usd": 0.00014,
            "output": 'Call search_policies("refund annual plan"), then get_customer_plan(customer_id), then calculate_refund.',
        },
        {
            "id": "search",
            "parent": "agent",
            "kind": "retrieval",
            "name": "Search policy docs",
            "tool": "elasticsearch",
            "start_ms": 910,
            "end_ms": 1270,
            "input": "refund window annual plan",
            "docs": [
                {
                    "title": "Refunds and cancellations",
                    "score": 0.91,
                    "source": "https://example.com/help/refunds",
                },
                {
                    "title": "Annual plan terms",
                    "score": 0.84,
                    "source": "https://example.com/legal/annual-terms",
                },
                {
                    "title": "Changing your plan",
                    "score": 0.42,
                    "source": "https://example.com/help/change-plan",
                },
            ],
        },
        {
            "id": "lookup",
            "parent": "agent",
            "kind": "tool",
            "name": "get_customer_plan",
            "tool": "postgres",
            "start_ms": 1270,
            "end_ms": 1730,
            "input": '{"customer_id": "c_4821"}',
            "status": "error",
            "note": "Connection timed out after 450 ms",
        },
        {
            "id": "lookup-retry",
            "parent": "agent",
            "kind": "tool",
            "name": "get_customer_plan",
            "tool": "postgres",
            "start_ms": 1730,
            "end_ms": 1980,
            "input": '{"customer_id": "c_4821"}',
            "output": '{"plan": "pro-annual", "purchased": "2026-10-17", "paid_usd": 240}',
            "status": "retry",
            "note": "Second attempt succeeded",
        },
        {
            "id": "refund",
            "parent": "agent",
            "kind": "tool",
            "name": "calculate_refund",
            "start_ms": 1980,
            "end_ms": 2140,
            "input": '{"plan": "pro-annual", "days_since_purchase": 21}',
            "output": '{"eligible": true, "amount_usd": 240, "window_days": 30}',
        },
        {
            "id": "answer",
            "parent": "agent",
            "kind": "llm",
            "name": "Compose the answer",
            "model": "gpt-4o",
            "start_ms": 2140,
            "end_ms": 4120,
            "tokens": {"in": 2310, "out": 186, "cached": 1024},
            "cost_usd": 0.0061,
            "input": "System: answer from the retrieved policy only.\nContext: Refunds and cancellations; Annual plan terms.\nCustomer plan: pro-annual, 21 days ago.",
            "output": "Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now.",
        },
        {
            "id": "reply",
            "parent": "agent",
            "kind": "reply",
            "name": "Full refund available (21 of 30 days)",
            "start_ms": 4120,
            "end_ms": 4210,
            "output": "Annual plans can be refunded in full within 30 days of purchase. You bought yours 21 days ago, so you are still inside the window: I can refund the full $240 now.",
        },
    ],
}

_OTEL = {
    "title": "Research agent (OpenTelemetry spans)",
    "spans": [
        {
            "span_id": "a1",
            "name": "invoke_agent researcher",
            "start": "2026-11-07T10:00:00.000Z",
            "end": "2026-11-07T10:00:03.400Z",
            "attributes": {
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": "researcher",
            },
        },
        {
            "span_id": "c1",
            "parent_span_id": "a1",
            "name": "chat claude-sonnet-5-5",
            "start": "2026-11-07T10:00:00.050Z",
            "end": "2026-11-07T10:00:01.100Z",
            "attributes": {
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": "claude-sonnet-5-5",
                "gen_ai.usage.input_tokens": 1450,
                "gen_ai.usage.output_tokens": 120,
                "gen_ai.usage.cache_read.input_tokens": 1200,
            },
        },
        {
            "span_id": "t1",
            "parent_span_id": "a1",
            "name": "execute_tool web_search",
            "start": "2026-11-07T10:00:01.100Z",
            "end": "2026-11-07T10:00:02.000Z",
            "attributes": {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "web_search",
            },
        },
        {
            "span_id": "c2",
            "parent_span_id": "a1",
            "name": "chat claude-sonnet-5-5",
            "start": "2026-11-07T10:00:02.000Z",
            "end": "2026-11-07T10:00:03.350Z",
            "attributes": {
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": "claude-sonnet-5-5",
                "gen_ai.usage.input_tokens": 2900,
                "gen_ai.usage.output_tokens": 410,
            },
        },
    ],
}

_TEMPLATE = {
    "title": "My agent run",
    "model": "gpt-4o",
    "steps": [
        {
            "id": "q",
            "kind": "user",
            "name": "User question",
            "start_ms": 0,
            "end_ms": 10,
        },
        {
            "id": "llm",
            "kind": "llm",
            "name": "Answer",
            "start_ms": 10,
            "end_ms": 900,
            "tokens": {"in": 500, "out": 120},
        },
        {"id": "out", "kind": "reply", "name": "Reply", "start_ms": 900, "end_ms": 920},
    ],
}

EXAMPLE = json.dumps(_RAG, indent=2, ensure_ascii=False)
OTEL_EXAMPLE = json.dumps(_OTEL, indent=2)
TEMPLATE = json.dumps(_TEMPLATE, indent=2)
