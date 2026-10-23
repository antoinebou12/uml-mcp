"""SEP-2322 MRTR helpers for diagram tools (unit-level, no live client)."""

from __future__ import annotations

from unittest.mock import MagicMock

from mcp.types import ElicitResult, InputRequiredResult

from mcp_core.tools import mrtr


def test_resolve_known_diagram_type():
    assert mrtr.resolve_diagram_type("Mermaid") == "mermaid"


def test_resolve_unknown_without_elicitation_returns_suggestions():
    err = mrtr.resolve_diagram_type("sequnce")
    assert isinstance(err, dict)
    assert "error" in err
    assert "sequence" in err.get("suggestions", [])


def test_resolve_theme_passthrough_and_background_autopick(monkeypatch):
    monkeypatch.setattr(mrtr, "client_supports_form_elicitation", lambda: False)
    assert mrtr.resolve_theme("class", "cerulean") == "cerulean"
    assert mrtr.resolve_theme("class", "dark") == "blueprint"
    assert mrtr.resolve_theme("mermaid", None) is None


def test_resolve_unknown_with_elicitation_returns_input_required(monkeypatch):
    monkeypatch.setattr(mrtr, "client_supports_form_elicitation", lambda: True)
    monkeypatch.setattr(mrtr, "elicit_content", lambda _k: None)
    result = mrtr.resolve_diagram_type("not-a-real-type")
    assert isinstance(result, InputRequiredResult)
    assert result.result_type == "input_required"
    assert mrtr.PICK_TYPE_KEY in (result.input_requests or {})


def test_resolve_diagram_type_from_elicit_accept(monkeypatch):
    monkeypatch.setattr(
        mrtr,
        "elicit_content",
        lambda key: {"diagram_type": "class"} if key == mrtr.PICK_TYPE_KEY else None,
    )
    assert mrtr.resolve_diagram_type("garbage") == "class"


def test_resolve_diagram_type_declined(monkeypatch):
    monkeypatch.setattr(mrtr, "elicit_content", lambda _k: False)
    err = mrtr.resolve_diagram_type("garbage")
    assert isinstance(err, dict) and "declined" in err["error"].lower()


def test_batch_confirm_threshold(monkeypatch):
    monkeypatch.setenv("MCP_BATCH_CONFIRM_MIN", "3")
    monkeypatch.setattr(mrtr, "client_supports_form_elicitation", lambda: True)
    monkeypatch.setattr(mrtr, "elicit_content", lambda _k: None)
    assert mrtr.maybe_confirm_batch([1, 2]) is None
    ask = mrtr.maybe_confirm_batch([1, 2, 3])
    assert isinstance(ask, InputRequiredResult)

    monkeypatch.setattr(
        mrtr,
        "elicit_content",
        lambda key: {"confirm": True} if key == mrtr.CONFIRM_BATCH_KEY else None,
    )
    assert mrtr.maybe_confirm_batch([1, 2, 3, 4]) is None


def test_elicit_content_reads_context(monkeypatch):
    result = ElicitResult(action="accept", content={"diagram_type": "d2"})
    ctx = MagicMock()
    ctx.input_responses = {mrtr.PICK_TYPE_KEY: result}
    monkeypatch.setattr(mrtr, "_request_context", lambda: ctx)
    assert mrtr.elicit_content(mrtr.PICK_TYPE_KEY) == {"diagram_type": "d2"}


def test_is_input_required():
    assert mrtr.is_input_required(
        mrtr.form_elicit(
            key="k",
            message="m",
            schema={"type": "object", "properties": {"a": {"type": "boolean"}}},
        )
    )
    assert not mrtr.is_input_required({"error": "x"})


def test_batch_confirm_disabled(monkeypatch):
    monkeypatch.setenv("MCP_BATCH_CONFIRM_MIN", "0")
    monkeypatch.setattr(mrtr, "client_supports_form_elicitation", lambda: True)
    assert mrtr.maybe_confirm_batch(list(range(20))) is None
