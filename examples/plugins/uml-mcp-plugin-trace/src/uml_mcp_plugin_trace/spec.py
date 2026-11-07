"""The ``agent_trace`` source: parse, validate and analyse an agent run.

Two input shapes are accepted, both JSON objects:

* the native form, ``{"title", "model", "steps": [...]}`` with ``start_ms``/``end_ms``
  relative to the start of the run;
* a minimal OpenTelemetry span list, ``{"spans": [...]}`` (or a bare list of spans) with
  ``span_id``, ``parent_span_id``, ``name``, ``start``/``end`` timestamps and GenAI
  semantic-convention ``attributes`` (``gen_ai.request.model``,
  ``gen_ai.usage.input_tokens``...). Spans are mapped onto steps.

Every problem is collected, so a model can fix them all in one go. Free text (inputs,
outputs, notes, names) is capped, because a trace can carry whole prompts.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

KINDS = (
    "user",
    "llm",
    "tool",
    "retrieval",
    "subagent",
    "guardrail",
    "memory",
    "reply",
    "error",
)
STATUSES = ("ok", "error", "retry")
THEMES = ("auto", "dark", "light")

MAX_STEPS = 400
MAX_TEXT = 4000  # characters kept of an input or output
MAX_NAME = 160
MAX_NOTE = 600
MAX_DOCS = 20
MAX_PROBLEMS = 25


class SpecError(ValueError):
    """The source is not a valid trace; ``problems`` has one message per issue."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems[:MAX_PROBLEMS]
        if len(problems) > MAX_PROBLEMS:
            self.problems.append(f"... and {len(problems) - MAX_PROBLEMS} more")
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class Doc:
    title: str
    score: float | None
    source: str


@dataclass
class Step:
    id: str
    kind: str
    name: str
    start_ms: float
    end_ms: float
    parent: str | None = None
    input: str = ""
    output: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0
    has_tokens: bool = False
    cost_usd: float | None = None
    model: str = ""
    tool: str = ""
    docs: list[Doc] = field(default_factory=list)
    status: str = "ok"
    note: str = ""
    # derived
    depth: int = 0
    children: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms


@dataclass
class Trace:
    title: str
    model: str
    theme: str
    steps: list[Step]  # tree order: each step followed by its children, by start time
    by_id: dict[str, Step]
    start_ms: float
    end_ms: float
    critical: list[str]

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms

    def totals(self) -> dict[str, Any]:
        steps = self.steps
        costs = [s.cost_usd for s in steps if s.cost_usd is not None]
        return {
            "duration_ms": self.duration_ms,
            "tokens_in": sum(s.tokens_in for s in steps),
            "tokens_out": sum(s.tokens_out for s in steps),
            "tokens_cached": sum(s.tokens_cached for s in steps),
            "cost_usd": sum(costs) if costs else None,
            "tool_calls": sum(1 for s in steps if s.kind == "tool"),
            "llm_calls": sum(1 for s in steps if s.kind == "llm"),
            "errors": sum(1 for s in steps if s.status == "error" or s.kind == "error"),
            "retries": sum(1 for s in steps if s.status == "retry"),
            "steps": len(steps),
        }


# --------------------------------------------------------------------------- helpers
def _cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"… [{len(text) - limit} more characters not kept]"


def _text(value: Any) -> str:
    """Free text from a string, or any JSON value shown as compact JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=1)
    except (TypeError, ValueError):
        return str(value)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


class _Problems(list):
    def add(self, where: str, message: str) -> None:
        self.append(f"{where}: {message}" if where else message)


# --------------------------------------------------------------------------- native
_STEP_FIELDS = {
    "id",
    "parent",
    "kind",
    "name",
    "start_ms",
    "end_ms",
    "input",
    "output",
    "tokens",
    "cost_usd",
    "model",
    "tool",
    "docs",
    "status",
    "note",
}


def _where(index: int, raw: Any) -> str:
    ident = raw.get("id") if isinstance(raw, dict) else None
    return f"step {index + 1}" + (f" ({ident!r})" if isinstance(ident, str) else "")


def _native_step(index: int, raw: Any, problems: _Problems) -> Step | None:
    if not isinstance(raw, dict):
        problems.add(f"step {index + 1}", "must be an object")
        return None
    where = _where(index, raw)
    unknown = sorted(set(raw) - _STEP_FIELDS)
    if unknown:
        problems.add(
            where,
            f"unknown field{'s' if len(unknown) > 1 else ''} {', '.join(unknown)}; "
            f"use {', '.join(sorted(_STEP_FIELDS))}",
        )
    ident = raw.get("id")
    if not isinstance(ident, str) or not ident.strip():
        problems.add(where, "needs an 'id' (a non-empty string)")
        return None
    ident = ident.strip()
    kind = raw.get("kind", "tool")
    if kind not in KINDS:
        problems.add(where, f"kind {kind!r} is not one of {', '.join(KINDS)}")
        kind = "tool"
    status = raw.get("status", "ok")
    if status not in STATUSES:
        problems.add(where, f"status {status!r} is not one of {', '.join(STATUSES)}")
        status = "ok"
    start, end = _number(raw.get("start_ms")), _number(raw.get("end_ms"))
    if start is None:
        problems.add(where, "needs 'start_ms', a number of milliseconds")
    if end is None:
        problems.add(where, "needs 'end_ms', a number of milliseconds")
    if start is not None and end is not None and end < start:
        problems.add(where, f"end_ms ({end:g}) is before start_ms ({start:g})")
    parent = raw.get("parent")
    if parent is not None and (not isinstance(parent, str) or not parent.strip()):
        problems.add(where, "'parent' must be the id of another step")
        parent = None
    step = Step(
        id=ident,
        kind=kind,
        name=_cap(_text(raw.get("name")) or ident, MAX_NAME),
        start_ms=start or 0.0,
        end_ms=end
        if end is not None and start is not None and end >= start
        else (start or 0.0),
        parent=parent.strip() if isinstance(parent, str) else None,
        input=_cap(_text(raw.get("input")), MAX_TEXT),
        output=_cap(_text(raw.get("output")), MAX_TEXT),
        model=_cap(_text(raw.get("model")), MAX_NAME),
        tool=_cap(_text(raw.get("tool")), MAX_NAME),
        status=status,
        note=_cap(_text(raw.get("note")), MAX_NOTE),
    )
    tokens = raw.get("tokens")
    if tokens is not None:
        if not isinstance(tokens, dict):
            problems.add(where, "'tokens' must be an object {in, out, cached}")
        else:
            extra = sorted(set(tokens) - {"in", "out", "cached"})
            if extra:
                problems.add(
                    where,
                    f"tokens has unknown keys {', '.join(extra)}; use in, out, cached",
                )
            for key in ("in", "out", "cached"):
                if key not in tokens:
                    continue
                value = _number(tokens[key])
                if value is None or value < 0:
                    problems.add(where, f"tokens.{key} must be a number >= 0")
                    continue
                setattr(step, f"tokens_{key}", int(value))
            step.has_tokens = True
    cost = raw.get("cost_usd")
    if cost is not None:
        value = _number(cost)
        if value is None or value < 0:
            problems.add(where, "cost_usd must be a number >= 0")
        else:
            step.cost_usd = value
    step.docs = _docs(raw.get("docs"), where, problems)
    return step


def _docs(raw: Any, where: str, problems: _Problems) -> list[Doc]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        problems.add(where, "'docs' must be a list of {title, score, source}")
        return []
    docs: list[Doc] = []
    for i, item in enumerate(raw[:MAX_DOCS]):
        if isinstance(item, str):
            docs.append(Doc(_cap(item, MAX_NAME), None, ""))
            continue
        if not isinstance(item, dict):
            problems.add(where, f"docs[{i}] must be an object {{title, score, source}}")
            continue
        score = item.get("score")
        value = _number(score) if score is not None else None
        if score is not None and value is None:
            problems.add(where, f"docs[{i}].score must be a number")
        docs.append(
            Doc(
                _cap(
                    _text(item.get("title"))
                    or _text(item.get("source"))
                    or f"document {i + 1}",
                    MAX_NAME,
                ),
                value,
                _cap(_text(item.get("source")), 400),
            )
        )
    return docs


# --------------------------------------------------------------------------- OpenTelemetry
def _attributes(raw: Any) -> dict[str, Any]:
    """OTel attributes as a flat dict; accepts a mapping or the OTLP JSON key/value list."""
    if isinstance(raw, dict):
        return raw
    out: dict[str, Any] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or "key" not in item:
                continue
            value = item.get("value")
            if isinstance(value, dict):
                for typed in ("stringValue", "intValue", "doubleValue", "boolValue"):
                    if typed in value:
                        value = value[typed]
                        break
            out[str(item["key"])] = value
    return out


def _timestamp_ms(value: Any) -> float | None:
    """A span timestamp in milliseconds since the epoch (or an arbitrary origin).

    Numbers are read by magnitude: nanoseconds (>= 1e17), microseconds (>= 1e14),
    milliseconds (>= 1e11), seconds (>= 1e8), else milliseconds from an arbitrary origin.
    Strings are ISO 8601 times or numbers.
    """
    if isinstance(value, str):
        text = value.strip()
        try:
            return _timestamp_ms(int(text))
        except ValueError:
            pass
        try:
            return _timestamp_ms(float(text))
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(text).timestamp() * 1000
        except ValueError:
            return None
    number = _number(value)
    if number is None:
        return None
    if number >= 1e17:
        return number / 1e6
    if number >= 1e14:
        return number / 1e3
    if number >= 1e11:
        return number
    if number >= 1e8:
        return number * 1e3
    return number


_OPERATION_KIND = {
    "chat": "llm",
    "text_completion": "llm",
    "generate_content": "llm",
    "completion": "llm",
    "execute_tool": "tool",
    "invoke_agent": "subagent",
    "create_agent": "subagent",
    "embeddings": "retrieval",
    "retrieval": "retrieval",
    "retrieve": "retrieval",
    "search": "retrieval",
}


def _span_kind(name: str, attrs: dict[str, Any], has_children: bool) -> str:
    explicit = attrs.get("agent_trace.kind") or attrs.get("kind")
    if explicit in KINDS:
        return str(explicit)
    op = str(attrs.get("gen_ai.operation.name", "")).lower()
    if op in _OPERATION_KIND:
        return _OPERATION_KIND[op]
    low = name.lower()
    for words, kind in (
        (("guard", "moderat", "safety"), "guardrail"),
        (("retriev", "vector", "search", "rerank", "embed"), "retrieval"),
        (("memory",), "memory"),
        (("reply", "respond", "response to user"), "reply"),
        (("user", "input message"), "user"),
        (("agent",), "subagent"),
        (("llm", "chat", "completion", "generate"), "llm"),
    ):
        if any(w in low for w in words):
            return kind
    if "gen_ai.tool.name" in attrs:
        return "tool"
    if any(k in attrs for k in ("gen_ai.request.model", "gen_ai.response.model")):
        return "llm"
    if "db.system" in attrs or "db.system.name" in attrs:
        return "retrieval"
    return "subagent" if has_children else "tool"


def _span_status(span: dict[str, Any], attrs: dict[str, Any]) -> str:
    status = span.get("status")
    code = status.get("code") if isinstance(status, dict) else status
    text = str(code).upper() if code is not None else ""
    if attrs.get("agent_trace.status") in STATUSES:
        return str(attrs["agent_trace.status"])
    if text in ("ERROR", "STATUS_CODE_ERROR", "2") or "error.type" in attrs:
        return "error"
    retry = attrs.get("retry.attempt", attrs.get("http.request.resend_count"))
    if isinstance(retry, int | float) and not isinstance(retry, bool) and retry > 0:
        return "retry"
    return "ok"


def _numeric(value: Any) -> Any:
    """OTLP JSON carries 64-bit integers as strings; read those back as numbers."""
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _first(attrs: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in attrs and attrs[key] not in (None, ""):
            return attrs[key]
    return None


def _otel_steps(spans: list[Any], problems: _Problems) -> list[dict[str, Any]]:
    """Map spans onto native step dicts (validated afterwards like any other step)."""
    rows: list[dict[str, Any]] = []
    parents: set[str] = set()
    for raw in spans:
        if isinstance(raw, dict):
            parent = raw.get("parent_span_id", raw.get("parentSpanId"))
            if isinstance(parent, str) and parent:
                parents.add(parent)
    origin: float | None = None
    stamped: list[tuple[int, Any, dict[str, Any], float | None, float | None]] = []
    for i, raw in enumerate(spans):
        if not isinstance(raw, dict):
            problems.add(f"span {i + 1}", "must be an object")
            continue
        attrs = _attributes(raw.get("attributes"))
        start = _timestamp_ms(
            _first(
                raw,
                "start",
                "start_time",
                "startTime",
                "start_time_unix_nano",
                "startTimeUnixNano",
            )
        )
        end = _timestamp_ms(
            _first(
                raw,
                "end",
                "end_time",
                "endTime",
                "end_time_unix_nano",
                "endTimeUnixNano",
            )
        )
        sid = raw.get("span_id", raw.get("spanId"))
        where = f"span {i + 1}" + (f" ({sid!r})" if isinstance(sid, str) else "")
        if start is None:
            problems.add(where, "needs a 'start' timestamp (ISO 8601 or a number)")
        if end is None:
            problems.add(where, "needs an 'end' timestamp (ISO 8601 or a number)")
        if start is not None:
            origin = start if origin is None else min(origin, start)
        stamped.append((i, raw, attrs, start, end))
    for i, raw, attrs, start, end in stamped:
        sid = raw.get("span_id", raw.get("spanId"))
        name = _text(raw.get("name")) or str(sid or f"span {i + 1}")
        parent = raw.get("parent_span_id", raw.get("parentSpanId")) or None
        tokens = {
            "in": _first(
                attrs, "gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens"
            ),
            "out": _first(
                attrs, "gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens"
            ),
            "cached": _first(
                attrs,
                "gen_ai.usage.cache_read.input_tokens",
                "gen_ai.usage.cache_read_input_tokens",
                "gen_ai.usage.cached_tokens",
            ),
        }
        tokens = {k: v for k, v in tokens.items() if v is not None}
        row: dict[str, Any] = {
            "id": sid,
            "name": name,
            "kind": _span_kind(name, attrs, isinstance(sid, str) and sid in parents),
            "status": _span_status(raw, attrs),
            "start_ms": None
            if start is None or origin is None
            else round(start - origin, 3),
            "end_ms": None if end is None or origin is None else round(end - origin, 3),
        }
        if parent:
            row["parent"] = parent
        if tokens:
            row["tokens"] = {k: _numeric(v) for k, v in tokens.items()}
        model = _first(attrs, "gen_ai.response.model", "gen_ai.request.model")
        if model is not None:
            row["model"] = str(model)
        tool = _first(attrs, "gen_ai.tool.name", "db.system.name", "db.system")
        if tool is not None:
            row["tool"] = str(tool)
        cost = _first(
            attrs,
            "gen_ai.usage.cost",
            "gen_ai.usage.cost_usd",
            "cost_usd",
            "llm.usage.cost",
        )
        if cost is not None:
            row["cost_usd"] = _numeric(cost)
        text_in = _first(
            attrs,
            "gen_ai.input.messages",
            "gen_ai.prompt",
            "gen_ai.tool.call.arguments",
            "input.value",
            "input",
        )
        text_out = _first(
            attrs,
            "gen_ai.output.messages",
            "gen_ai.completion",
            "gen_ai.tool.call.result",
            "output.value",
            "output",
        )
        if text_in is not None:
            row["input"] = text_in
        if text_out is not None:
            row["output"] = text_out
        error = _first(attrs, "error.type", "exception.message")
        status = raw.get("status")
        message = status.get("message") if isinstance(status, dict) else None
        if error or message:
            row["note"] = " · ".join(str(x) for x in (error, message) if x)
        docs = attrs.get("agent_trace.docs") or attrs.get("retrieval.documents")
        if isinstance(docs, list):
            row["docs"] = docs
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- parse
def parse(code: str, *, max_steps: int = MAX_STEPS) -> Trace:
    try:
        data = json.loads(code)
    except ValueError as exc:
        raise SpecError([f"source is not valid JSON: {exc}"]) from exc
    problems = _Problems()
    if isinstance(data, list):
        data = {"spans": data}
    if not isinstance(data, dict):
        raise SpecError(["source must be a JSON object with 'steps' (or 'spans')"])
    allowed = {"title", "model", "theme", "steps", "spans", "$schema"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        problems.add(
            "",
            f"unknown top-level field{'s' if len(unknown) > 1 else ''} {', '.join(unknown)}; use title, model, theme, steps (or spans)",
        )
    theme = data.get("theme", "auto")
    if theme not in THEMES:
        problems.add("", f"theme {theme!r} is not one of {', '.join(THEMES)}")
        theme = "auto"
    if "steps" in data and "spans" in data:
        problems.add("", "give either 'steps' or 'spans', not both")
    if "spans" in data and "steps" not in data:
        spans = data["spans"]
        if not isinstance(spans, list) or not spans:
            raise SpecError([*problems, "'spans' must be a non-empty list"])
        if len(spans) > max_steps:
            raise SpecError(
                [*problems, f"too many spans ({len(spans)}); the limit is {max_steps}"]
            )
        raw_steps: list[Any] = _otel_steps(spans, problems)
    else:
        raw_steps = data.get("steps")  # type: ignore[assignment]
        if not isinstance(raw_steps, list) or not raw_steps:
            raise SpecError([*problems, "'steps' must be a non-empty list of steps"])
        if len(raw_steps) > max_steps:
            raise SpecError(
                [
                    *problems,
                    f"too many steps ({len(raw_steps)}); the limit is {max_steps}",
                ]
            )

    steps: list[Step] = []
    seen: dict[str, int] = {}
    for i, raw in enumerate(raw_steps):
        step = _native_step(i, raw, problems)
        if step is None:
            continue
        if step.id in seen:
            problems.add(
                _where(i, raw),
                f"id {step.id!r} is already used by step {seen[step.id] + 1}; ids must be unique",
            )
            continue
        seen[step.id] = i
        steps.append(step)
    by_id = {s.id: s for s in steps}
    known = ", ".join(sorted(by_id)[:20]) + ("..." if len(by_id) > 20 else "")
    for s in steps:
        if s.parent is None:
            continue
        if s.parent == s.id:
            problems.add(f"step {s.id!r}", "cannot be its own parent")
            s.parent = None
        elif s.parent not in by_id:
            problems.add(
                f"step {s.id!r}", f"unknown parent {s.parent!r}; known ids: {known}"
            )
            s.parent = None
    # cycles
    for s in steps:
        trail, cursor = {s.id}, s.parent
        while cursor is not None:
            if cursor in trail:
                problems.add(
                    f"step {s.id!r}", f"parent chain loops back through {cursor!r}"
                )
                s.parent = None
                break
            trail.add(cursor)
            cursor = by_id[cursor].parent
    if problems:
        raise SpecError(list(problems))

    title = _cap(_text(data.get("title")) or "Agent trace", MAX_NAME)
    model = _cap(_text(data.get("model")), MAX_NAME)
    return _build(title, model, theme, steps)


def _build(title: str, model: str, theme: str, steps: list[Step]) -> Trace:
    by_id = {s.id: s for s in steps}
    original = {s.id: i for i, s in enumerate(steps)}
    for s in steps:
        if s.parent:
            by_id[s.parent].children.append(s.id)

    def key(sid: str) -> tuple[float, int]:
        return (by_id[sid].start_ms, original[sid])

    ordered: list[Step] = []

    def walk(sid: str, depth: int) -> None:
        step = by_id[sid]
        step.depth = depth
        step.children.sort(key=key)
        ordered.append(step)
        for child in step.children:
            walk(child, depth + 1)

    roots = sorted((s.id for s in steps if s.parent is None), key=key)
    for root in roots:
        walk(root, 0)
    start = min(s.start_ms for s in steps)
    end = max(s.end_ms for s in steps)
    return Trace(
        title=title,
        model=model,
        theme=theme,
        steps=ordered,
        by_id=by_id,
        start_ms=start,
        end_ms=end,
        critical=critical_path(by_id, roots, start, end),
    )


def critical_path(
    by_id: dict[str, Step], roots: list[str], start: float, end: float
) -> list[str]:
    """The chain of steps that decides the run's total time.

    Walk back from the end: the child that finished last is on the path, then the child
    that finished last before that one started, and so on; recurse into each chosen step.
    """
    path: list[str] = []

    def chain(ids: list[str], lo: float, hi: float) -> None:
        cursor = hi
        picked: list[str] = []
        pool = sorted(ids, key=lambda i: (by_id[i].end_ms, by_id[i].start_ms))
        while pool:
            candidates = [i for i in pool if by_id[i].end_ms <= cursor + 1e-6]
            if not candidates:
                break
            best = candidates[-1]
            picked.append(best)
            cursor = by_id[best].start_ms
            pool = [i for i in pool if by_id[i].end_ms <= cursor + 1e-6 and i != best]
            if cursor <= lo + 1e-6:
                break
        for sid in reversed(picked):
            path.append(sid)
            step = by_id[sid]
            if step.children:
                chain(step.children, step.start_ms, step.end_ms)

    chain(roots, start, end)
    return path
