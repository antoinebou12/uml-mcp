"""The agent-trace plugin: parsing, validation, OpenTelemetry mapping, SVG and the HTML page."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _name in ("trace", "d3"):
    _src = str(ROOT / "examples" / "plugins" / f"uml-mcp-plugin-{_name}" / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

from uml_mcp_plugin_trace import OTEL_EXAMPLE, TraceRenderer
from uml_mcp_plugin_trace import docs as trace_docs
from uml_mcp_plugin_trace.html import page_data
from uml_mcp_plugin_trace.samples import EXAMPLE, TEMPLATE
from uml_mcp_plugin_trace.spec import (
    MAX_TEXT,
    SpecError,
    _timestamp_ms,
    parse,
)
from uml_mcp_plugin_trace.svg import (
    fit,
    flow_svg,
    fmt_cost,
    fmt_ms,
    fmt_tokens,
    lanes_of,
    nice_step,
)

R = TraceRenderer()


def problems(source: object) -> list[str]:
    code = source if isinstance(source, str) else json.dumps(source)
    return R.validate("agent_trace", code)


def steps(*rows: object) -> dict:
    return {"steps": list(rows)}


def step(id: str, start: float = 0, end: float = 10, **extra) -> dict:
    return {
        "id": id,
        "kind": "tool",
        "name": id,
        "start_ms": start,
        "end_ms": end,
        **extra,
    }


# --------------------------------------------------------------------------- the example
def test_type_is_declared_with_both_formats_and_an_example():
    spec = R.diagram_types["agent_trace"]
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    assert R.validate("agent_trace", spec.example or "") == []
    assert R.validate("agent_trace", spec.template or "") == []
    assert R.validate("agent_trace", OTEL_EXAMPLE) == []


def test_the_rag_example_has_a_retrieval_two_tools_a_retry_and_a_reply():
    trace = parse(EXAMPLE)
    kinds = [s.kind for s in trace.steps]
    assert kinds.count("retrieval") == 1 and kinds.count("reply") == 1
    assert len({s.name for s in trace.steps if s.kind == "tool"}) == 2
    assert [s.status for s in trace.steps].count("retry") == 1
    totals = trace.totals()
    assert totals["duration_ms"] == 4210
    assert totals["tokens_in"] == 2922 and totals["tokens_cached"] == 1536
    assert (
        totals["tool_calls"] == 3 and totals["errors"] == 1 and totals["retries"] == 1
    )
    assert trace.steps[0].id == "agent" and all(s.depth == 1 for s in trace.steps[1:])


def test_static_svg_is_a_waterfall_with_a_summary_and_marks():
    svg = R.render("agent_trace", EXAMPLE, "svg")
    assert svg.mime_type == "image/svg+xml"
    text = svg.content.decode()
    assert text.startswith("<svg") and "<script" not in text
    for expected in ("TOTAL TIME", "4.21 s", "2.9k", "$0.0062", "TOOL CALLS", "1 · 1"):
        assert expected in text, expected
    assert text.count('class="row"') == 10
    assert text.count('class="mark mark-error"') >= 2  # the row and the legend
    assert 'class="mark mark-retry"' in text
    assert "<style>" in text and "var(" not in text  # literal colours for resvg
    assert 'class="bar k-llm"' in text and 'class="bar k-tool b-error"' in text


def test_static_svg_rasterises():
    from mcp_core.core.svg_raster import svg_to_png

    png = svg_to_png(R.render("agent_trace", EXAMPLE, "svg").content)
    assert png is None or png.startswith(b"\x89PNG")


def test_theme_picks_the_static_palette():
    light = json.dumps({**json.loads(EXAMPLE), "theme": "light"})
    assert "#ffffff" in R.render("agent_trace", light, "svg").content.decode()[:3000]
    dark = R.render("agent_trace", EXAMPLE, "svg").content.decode()
    assert ".bg{fill:#0b1220}" in dark


def test_html_page_is_locked_down_and_carries_the_data():
    page = R.render("agent_trace", EXAMPLE, "html")
    assert page.mime_type.startswith("text/html")
    html = page.content.decode()
    assert html.startswith("<!doctype html>")
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    assert csp and "default-src &#x27;none&#x27;" in csp.group(1)
    assert "unsafe-inline" not in html and "http://" not in csp.group(1)
    assert 'id="waterfall"' in html and 'id="flow"' in html
    block = re.search(r'id="trace">(.*?)</script>', html)
    assert block is not None
    data = json.loads(block.group(1))
    assert data["critical"][0] == "agent"
    by_id = {s["id"]: s for s in data["steps"]}
    assert by_id["search"]["docs"][0]["score"] == 0.91
    assert by_id["answer"]["docs_url"] == "https://platform.openai.com/docs"
    assert by_id["lookup"]["docs_url"] == "https://www.postgresql.org/docs/"


def test_unsupported_format_and_bad_source_raise_readable_errors():
    with pytest.raises(ValueError, match="html or svg"):
        R.render("agent_trace", EXAMPLE, "png")
    with pytest.raises(ValueError, match="unknown parent"):
        R.render("agent_trace", json.dumps(steps(step("a", parent="ghost"))), "svg")
    assert problems("{") and "not valid JSON" in problems("{")[0]
    assert R.validate("other", EXAMPLE) == ["unknown trace type: other"]


# --------------------------------------------------------------------------- validation
def test_validation_reports_every_problem_with_a_fix():
    got = problems(
        steps(
            step("a", 50, 10, kind="bot", status="maybe", colour="red"),
            step("a"),
            step("b", parent="nope"),
            step("c", tokens={"in": -1, "bogus": 2}, cost_usd="cheap"),
            {"name": "no id", "start_ms": 0, "end_ms": 1},
            "not an object",
        )
    )
    text = "\n".join(got)
    assert "kind 'bot' is not one of user, llm" in text
    assert "status 'maybe' is not one of ok, error, retry" in text
    assert "unknown field colour" in text
    assert "end_ms (10) is before start_ms (50)" in text
    assert "id 'a' is already used by step 1" in text
    assert "unknown parent 'nope'; known ids: a, b, c" in text
    assert "tokens.in must be a number >= 0" in text
    assert "tokens has unknown keys bogus" in text
    assert "cost_usd must be a number >= 0" in text
    assert "needs an 'id'" in text and "step 6: must be an object" in text


def test_cycles_self_parents_and_missing_times():
    text = "\n".join(
        problems(
            steps(step("a", parent="b"), step("b", parent="a"), step("c", parent="c"))
        )
    )
    assert "loops back" in text and "cannot be its own parent" in text
    missing = problems(steps({"id": "x", "kind": "llm"}))
    assert any("start_ms" in p for p in missing) and any("end_ms" in p for p in missing)


def test_top_level_shape_is_checked():
    assert "non-empty list" in problems({"steps": []})[0]
    assert "JSON object" in problems("3")[0]
    assert any(
        "unknown top-level field" in p for p in problems({"steps": [step("a")], "x": 1})
    )
    assert any("theme" in p for p in problems({"steps": [step("a")], "theme": "neon"}))
    assert any("not both" in p for p in problems({"steps": [step("a")], "spans": []}))
    assert "non-empty list" in problems({"spans": {}})[0]


def test_limits_and_configure():
    renderer = TraceRenderer()
    renderer.configure({"max_steps": 2})
    many = json.dumps(steps(step("a"), step("b"), step("c")))
    assert (
        "too many steps (3); the limit is 2"
        in renderer.validate("agent_trace", many)[0]
    )
    for bad in (0, 401, "5", True):
        with pytest.raises(ValueError, match="max_steps"):
            renderer.configure({"max_steps": bad})
    spans = json.dumps({"spans": [{"span_id": str(i)} for i in range(3)]})
    assert "too many spans" in renderer.validate("agent_trace", spans)[0]


def test_problem_list_is_capped():
    got = problems(
        steps(
            *[
                {"id": f"s{i}", "kind": "nope", "start_ms": 0, "end_ms": 1}
                for i in range(40)
            ]
        )
    )
    assert len(got) == 26 and got[-1] == "... and 15 more"
    assert SpecError(["x"]).problems == ["x"]


def test_long_text_is_capped_and_json_values_are_shown_as_text():
    long = "x" * (MAX_TEXT + 500)
    trace = parse(
        json.dumps(
            steps(
                step("a", input=long, output={"answer": [1, 2]}, docs=["plain title"])
            )
        )
    )
    s = trace.steps[0]
    assert len(s.input) < MAX_TEXT + 60 and s.input.endswith(
        "[500 more characters not kept]"
    )
    assert '"answer"' in s.output
    assert s.docs[0].title == "plain title" and s.docs[0].score is None
    assert any("docs" in p for p in problems(steps(step("a", docs="nope"))))
    assert any("docs[0]" in p for p in problems(steps(step("a", docs=[3]))))
    assert any(
        "score" in p
        for p in problems(steps(step("a", docs=[{"title": "t", "score": "hi"}])))
    )


def test_markup_in_the_source_is_never_markup_in_the_output():
    evil = "<img src=x onerror=alert(1)></script><script>alert(2)</script>"
    code = json.dumps(
        steps(
            step("a", name=evil, input=evil, note=evil),
            step("b", kind="user", name=evil),
        )
    )
    svg = R.render("agent_trace", code, "svg").content.decode()
    html = R.render("agent_trace", code, "html").content.decode()
    for text in (svg, html):
        assert "<img" not in text and "alert(2)</script>" not in text
    assert "&lt;img" in svg
    assert html.count("<script") == 3  # the two JSON blocks and the runtime


# --------------------------------------------------------------------------- critical path
def test_critical_path_follows_the_last_finishing_chain():
    trace = parse(
        json.dumps(
            steps(
                step("root", 0, 100, kind="subagent"),
                step("fast", 0, 30, parent="root"),
                step("slow", 0, 60, parent="root"),
                step("then", 60, 100, parent="root"),
                step("inner", 65, 90, parent="then"),
            )
        )
    )
    assert trace.critical == ["root", "slow", "then", "inner"]


def test_roots_are_ordered_by_start_and_children_nest():
    trace = parse(
        json.dumps(
            steps(
                step("late", 50, 60),
                step("early", 0, 10),
                step("kid", 1, 2, parent="early"),
            )
        )
    )
    assert [(s.id, s.depth) for s in trace.steps] == [
        ("early", 0),
        ("kid", 1),
        ("late", 0),
    ]
    assert trace.steps[0].children == ["kid"]


# --------------------------------------------------------------------------- OpenTelemetry
def test_otel_spans_map_onto_steps():
    trace = parse(OTEL_EXAMPLE)
    by_id = trace.by_id
    assert by_id["a1"].kind == "subagent" and by_id["c1"].kind == "llm"
    assert by_id["t1"].kind == "tool" and by_id["t1"].tool == "web_search"
    assert by_id["c1"].model == "claude-sonnet-5-5"
    assert (
        by_id["c1"].tokens_in,
        by_id["c1"].tokens_out,
        by_id["c1"].tokens_cached,
    ) == (1450, 120, 1200)
    assert by_id["a1"].start_ms == 0 and by_id["a1"].end_ms == pytest.approx(3400)
    assert by_id["c1"].parent == "a1"
    docs = page_data(trace)["steps"]
    assert {s["id"]: s["docs_url"] for s in docs}["c1"] == "https://docs.anthropic.com/"


def test_otlp_json_attributes_status_and_nanoseconds():
    base = 1_762_509_600_000_000_000  # ns
    spans = [
        {
            "spanId": "s1",
            "name": "retrieve chunks",
            "startTimeUnixNano": str(base),
            "endTimeUnixNano": str(base + 250_000_000),
            "attributes": [
                {"key": "db.system", "value": {"stringValue": "qdrant"}},
                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "12"}},
                {"key": "agent_trace.docs", "value": {"stringValue": "ignored"}},
                "junk",
            ],
            "status": {"code": "STATUS_CODE_ERROR", "message": "boom"},
        },
        {
            "span_id": "s2",
            "parentSpanId": "s1",
            "name": "x",
            "start": base // 1_000_000 + 10,
            "end": base // 1_000_000 + 20,
            "attributes": {
                "gen_ai.tool.name": "calc",
                "retry.attempt": 1,
                "gen_ai.usage.cost": "0.5",
            },
        },
    ]
    trace = parse(json.dumps(spans))  # a bare list works too
    s1, s2 = trace.by_id["s1"], trace.by_id["s2"]
    assert s1.kind == "retrieval" and s1.tool == "qdrant" and s1.tokens_in == 12
    assert s1.status == "error" and s1.note == "boom"
    assert s1.duration_ms == pytest.approx(250)
    assert s2.kind == "tool" and s2.status == "retry" and s2.cost_usd == 0.5
    assert s2.start_ms == pytest.approx(10)


@pytest.mark.parametrize(
    ("name", "attrs", "kind"),
    [
        ("input moderation", {}, "guardrail"),
        ("vector search", {}, "retrieval"),
        ("load memory", {}, "memory"),
        ("send reply", {}, "reply"),
        ("user message", {}, "user"),
        ("planner agent", {}, "subagent"),
        ("llm call", {}, "llm"),
        ("thing", {"gen_ai.request.model": "gpt-4o"}, "llm"),
        ("thing", {"db.system.name": "postgresql"}, "retrieval"),
        ("thing", {"agent_trace.kind": "memory"}, "memory"),
        ("thing", {"gen_ai.operation.name": "embeddings"}, "retrieval"),
        ("thing", {}, "tool"),
    ],
)
def test_span_kinds_are_inferred(name, attrs, kind):
    trace = parse(
        json.dumps(
            {
                "spans": [
                    {
                        "span_id": "x",
                        "name": name,
                        "start": 0,
                        "end": 5,
                        "attributes": attrs,
                    }
                ]
            }
        )
    )
    assert trace.steps[0].kind == kind


def test_span_problems_are_reported():
    got = problems(
        {
            "spans": [
                {"span_id": "a", "name": "n"},
                5,
                {"span_id": "b", "start": "nope", "end": 1},
            ]
        }
    )
    text = "\n".join(got)
    assert "needs a 'start' timestamp" in text and "needs an 'end' timestamp" in text
    assert "span 2: must be an object" in text


@pytest.mark.parametrize(
    ("value", "ms"),
    [
        (1_762_509_600_000_000_000, 1_762_509_600_000),
        (1_762_509_600_000_000, 1_762_509_600_000),
        (1_762_509_600_000, 1_762_509_600_000),
        (1_762_509_600, 1_762_509_600_000),
        (250, 250),
        ("250", 250),
        ("2.5", 2.5),
        ("1970-01-01T00:00:01Z", 1000),
        ("soon", None),
        (None, None),
    ],
)
def test_timestamps_are_read_by_magnitude(value, ms):
    assert _timestamp_ms(value) == (pytest.approx(ms) if ms is not None else None)


# --------------------------------------------------------------------------- flow and helpers
def test_flow_lanes_fold_the_root_agent_and_split_models_and_tools():
    lanes, _, host = lanes_of(parse(EXAMPLE))
    names = [lane.name for lane in lanes]
    assert host == "agent" and names[:2] == ["User", "Support agent"]
    assert "gpt-4o-mini" in names and "gpt-4o" in names and "elasticsearch" in names
    svg = flow_svg(parse(EXAMPLE), theme="dark")
    assert svg.count('class="msg"') == 9 and 'class="arrow ret' in svg


def test_flow_handles_sub_agents_errors_and_many_tools():
    rows = [
        step("root", 0, 100, kind="subagent"),
        step("sub", 0, 50, kind="subagent", parent="root"),
    ]
    rows += [step(f"t{i}", i, i + 1, parent="sub", tool=f"tool{i}") for i in range(8)]
    rows += [
        step("oops", 60, 61, kind="error", parent="root"),
        step("self", 70, 80, kind="llm", parent="root"),
    ]
    trace = parse(json.dumps(steps(*rows)))
    _, placed, _ = lanes_of(trace)
    assert placed["t0"] == placed["t7"] == "tool:*"
    assert placed["oops"] == ""
    svg = flow_svg(trace, theme="light")
    assert 'class="notebox"' in svg and "sub:sub" in svg
    # without a single root agent, there is a plain Agent lane
    two_roots = parse(json.dumps(steps(step("a"), step("b", 5, 9))))
    assert lanes_of(two_roots)[0][0].name == "Agent"


def test_formatting_helpers():
    assert fmt_ms(0) == "0 ms" and fmt_ms(0.5) == "0.50 ms" and fmt_ms(812) == "812 ms"
    assert fmt_ms(1240) == "1.24 s" and fmt_ms(125_000) == "2m 05.0s"
    assert fmt_tokens(999) == "999" and fmt_tokens(2310) == "2.3k"
    assert fmt_tokens(52_000) == "52k" and fmt_tokens(3_400_000) == "3.4M"
    assert (
        fmt_cost(None) == "—" and fmt_cost(0) == "$0" and fmt_cost(0.0042) == "$0.0042"
    )
    assert fmt_cost(1.5) == "$1.50" and fmt_cost(1234) == "$1,234"
    assert fit("short", 200) == "short" and fit("x" * 100, 50).endswith("…")
    assert nice_step(0) == 1.0 and nice_step(4210) == 1000 and nice_step(60) == 10


def test_docs_links_for_models_and_tools():
    assert trace_docs.model_docs("claude-opus-5-5") == "https://docs.anthropic.com/"
    assert trace_docs.model_docs("o3-mini") == "https://platform.openai.com/docs"
    assert (
        trace_docs.model_docs("gemini-2.5-pro")
        == "https://ai.google.dev/gemini-api/docs"
    )
    assert trace_docs.model_docs("mixtral-8x7b") == "https://docs.mistral.ai/"
    assert trace_docs.model_docs("command-r") == "https://docs.cohere.com/"
    assert (
        trace_docs.model_docs("my-own-model") is None
        and trace_docs.model_docs("") is None
    )
    assert trace_docs.tool_docs("aws:s3") == "https://docs.aws.amazon.com/s3/"
    assert trace_docs.tool_docs("redis") == "https://redis.io/docs/"
    assert (
        trace_docs.tool_docs("calculate_refund") is None
        and trace_docs.tool_docs("") is None
    )
    assert (
        trace_docs.step_docs("llm", "", "", "claude-haiku-5-5")
        == "https://docs.anthropic.com/"
    )
    assert (
        trace_docs.step_docs("guardrail", "", "omni-moderation", "")
        == "https://platform.openai.com/docs"
    )


def test_template_renders():
    assert R.render("agent_trace", TEMPLATE, "svg").content.startswith(b"<svg")
