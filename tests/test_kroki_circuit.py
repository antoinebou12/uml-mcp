"""Mermaid through a Kroki engine that hangs: skip it, use the fallback, and recover.

Reproduces what public kroki.io did: Mermaid requests hang, so every render (and, in
URL-only mode, every link check) waited out the fail-fast timeout before falling back.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp_core.core import diagram_rendering
from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.diagram_rendering import (
    MERMAID_ENGINE,
    DiagramRenderContext,
    _handle_diagram_error,
    run_diagram_pipeline,
)
from mcp_core.core.engine_health import EngineUnavailable
from tools.kroki.kroki import KrokiConnectionError, KrokiHTTPError

SOURCE = "graph TD; A-->B;"
KROKI_LINK = "https://kroki.example/mermaid/svg/abc"
INK = {
    "code": SOURCE,
    "url": "https://mermaid.ink/svg/abc",
    "playground": "https://mermaid.live/edit#abc",
    "local_path": None,
    "source": "mermaid_ink",
}
KROKI_OK = {
    "content": b"<svg/>",
    "url": "https://kroki.io/mermaid/svg/abc",
    "playground": None,
}
GET_PATCH = "mcp_core.core.diagram_rendering.httpx.get"


class Clock:
    def __init__(self) -> None:
        self.now = 5000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(MERMAID_ENGINE, "_clock", fake)
    return fake


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", True)
    monkeypatch.setattr(MCP_SETTINGS, "kroki_circuit_cooldown_seconds", 60.0)
    monkeypatch.setattr(MCP_SETTINGS, "url_only", False)


@pytest.fixture
def ink():
    """The mermaid.ink fallback, stubbed so no test touches the network."""
    with patch.object(
        diagram_rendering, "_generate_diagram_mermaid_fallback", return_value=dict(INK)
    ) as stub:
        yield stub


def ctx(backend: str = "mermaid", force_fetch: bool = False) -> DiagramRenderContext:
    return DiagramRenderContext(
        diagram_type=backend,
        backend_type=backend,
        prepared_code=SOURCE,
        output_format="svg",
        output_dir=None,
        theme=None,
        scale=1.0,
        force_fetch=force_fetch,
    )


def http_error(status: int) -> KrokiHTTPError:
    response = MagicMock()
    response.status_code = status
    response.url = "https://kroki.io/mermaid/svg"
    return KrokiHTTPError(response, b"Error")


def hanging() -> MagicMock:
    client = MagicMock()
    client.generate_diagram.side_effect = KrokiConnectionError("timed out")
    return client


def trip() -> None:
    MERMAID_ENGINE.failure()
    MERMAID_ENGINE.failure()


# --------------------------------------------------------------------- fetch mode
def test_two_timeouts_open_the_breaker_and_later_calls_skip_kroki(ink) -> None:
    client = hanging()

    results = [run_diagram_pipeline(ctx(), kroki_client=client) for _ in range(4)]

    # Only the first two paid the timeout; the rest went straight to the fallback.
    assert client.generate_diagram.call_count == 2
    assert [r["source"] for r in results] == ["mermaid_ink"] * 4
    third = results[2]
    assert third["fallback_used"] is True
    assert third["attempts"][0]["ok"] is False
    assert "skipped" in third["attempts"][0]["error_summary"]
    assert ink.call_count == 4


def test_server_errors_count_as_engine_failures() -> None:
    client = MagicMock()
    client.generate_diagram.side_effect = http_error(500)

    with patch.object(
        diagram_rendering, "_generate_diagram_mermaid_fallback", return_value=dict(INK)
    ):
        run_diagram_pipeline(ctx(), kroki_client=client)
        run_diagram_pipeline(ctx(), kroki_client=client)
        run_diagram_pipeline(ctx(), kroki_client=client)

    assert client.generate_diagram.call_count == 2


def test_syntax_errors_prove_the_engine_is_alive_and_never_open_it(ink) -> None:
    client = MagicMock()
    client.generate_diagram.side_effect = http_error(400)

    for _ in range(5):
        run_diagram_pipeline(ctx(), kroki_client=client)

    assert client.generate_diagram.call_count == 5  # never skipped
    assert not MERMAID_ENGINE.is_open()


def test_the_engine_is_tried_again_after_the_cooldown_and_recovers(ink, clock) -> None:
    client = hanging()
    run_diagram_pipeline(ctx(), kroki_client=client)
    run_diagram_pipeline(ctx(), kroki_client=client)
    assert MERMAID_ENGINE.is_open()

    clock.now += 61
    client.generate_diagram.side_effect = None
    client.generate_diagram.return_value = KROKI_OK
    out = run_diagram_pipeline(ctx(), kroki_client=client)

    assert out["source"] == "kroki"
    assert not MERMAID_ENGINE.is_open()
    assert client.generate_diagram.call_count == 3


def test_still_down_after_the_cooldown_reopens_after_one_try(ink, clock) -> None:
    client = hanging()
    run_diagram_pipeline(ctx(), kroki_client=client)
    run_diagram_pipeline(ctx(), kroki_client=client)
    clock.now += 61

    run_diagram_pipeline(ctx(), kroki_client=client)  # one more try...
    run_diagram_pipeline(ctx(), kroki_client=client)  # ...and now skipped again

    assert client.generate_diagram.call_count == 3


def test_not_used_when_there_is_no_fallback_to_route_to(monkeypatch) -> None:
    """Without a fallback, skipping Kroki would only turn slow errors into fast ones."""
    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", False)
    client = hanging()

    for _ in range(5):
        run_diagram_pipeline(ctx(), kroki_client=client)

    assert client.generate_diagram.call_count == 5
    assert not MERMAID_ENGINE.is_open()


def test_cooldown_zero_turns_it_off(monkeypatch, ink) -> None:
    monkeypatch.setattr(MCP_SETTINGS, "kroki_circuit_cooldown_seconds", 0.0)
    client = hanging()

    for _ in range(5):
        run_diagram_pipeline(ctx(), kroki_client=client)

    assert client.generate_diagram.call_count == 5


def test_other_diagram_types_are_unaffected() -> None:
    client = hanging()

    with patch.object(
        diagram_rendering, "_generate_diagram_plantuml_fallback", return_value=dict(INK)
    ):
        for _ in range(5):
            run_diagram_pipeline(ctx("plantuml"), kroki_client=client)

    assert client.generate_diagram.call_count == 5
    assert not MERMAID_ENGINE.is_open()


# ------------------------------------------------------------- URL-only (hosted) mode
@pytest.fixture
def url_only(monkeypatch):
    monkeypatch.setattr(MCP_SETTINGS, "url_only", True)


def url_client() -> MagicMock:
    client = MagicMock()
    client.get_url.return_value = KROKI_LINK
    client.get_playground_url.return_value = None
    return client


def response(status: int) -> httpx.Response:
    return httpx.Response(
        status,
        request=httpx.Request("GET", KROKI_LINK),
        content=b"<svg/>" if status < 400 else b"Error",
    )


def test_url_only_a_hung_link_check_opens_the_breaker_for_later_diagrams(
    url_only, ink
) -> None:
    """The check waits out its deadline once or twice, not once per new diagram."""
    client = url_client()

    with patch(GET_PATCH, side_effect=httpx.ReadTimeout("timed out")) as get:
        results = [run_diagram_pipeline(ctx(), kroki_client=client) for _ in range(4)]

    assert get.call_count == 2
    assert client.get_url.call_count == 2  # skipped diagrams do not even build a link
    assert [r["source"] for r in results] == ["mermaid_ink"] * 4
    assert results[3]["url"] == INK["url"]
    assert results[3]["fallback_used"] is True


def test_url_only_connection_errors_count_too(url_only, ink) -> None:
    client = url_client()

    with patch(GET_PATCH, side_effect=httpx.ConnectError("refused")) as get:
        for _ in range(3):
            run_diagram_pipeline(ctx(), kroki_client=client)

    assert get.call_count == 2


@pytest.mark.parametrize("status", [500, 503, 429])
def test_url_only_server_errors_count_as_failures(url_only, ink, status: int) -> None:
    client = url_client()

    with patch(GET_PATCH, return_value=response(status)) as get:
        for _ in range(3):
            run_diagram_pipeline(ctx(), kroki_client=client)

    assert get.call_count == 2


@pytest.mark.parametrize("status", [400, 413, 422, 404])
def test_url_only_answers_that_are_not_an_outage_never_open_it(
    url_only, ink, status: int
) -> None:
    """A syntax error means the engine is alive; a 404 is a misconfigured URL, not a
    dead engine. Neither should hide Kroki behind mermaid.ink for everyone."""
    client = url_client()

    with patch(GET_PATCH, return_value=response(status)) as get:
        for _ in range(5):
            run_diagram_pipeline(ctx(), kroki_client=client)

    assert get.call_count == 5
    assert not MERMAID_ENGINE.is_open()


def test_url_only_healthy_links_keep_the_engine_closed(url_only, ink) -> None:
    client = url_client()
    MERMAID_ENGINE.failure()  # one earlier blip

    with patch(GET_PATCH, return_value=response(200)):
        out = run_diagram_pipeline(ctx(), kroki_client=client)
    MERMAID_ENGINE.failure()  # the blip was forgotten, so this is only the first again

    assert out["source"] == "kroki"
    assert out["url"] == KROKI_LINK
    assert not MERMAID_ENGINE.is_open()
    ink.assert_not_called()


def test_url_only_checks_the_link_again_after_the_cooldown(
    url_only, ink, clock
) -> None:
    client = url_client()
    trip()

    clock.now += 61
    with patch(GET_PATCH, return_value=response(200)) as get:
        out = run_diagram_pipeline(ctx(), kroki_client=client)

    assert get.call_count == 1
    assert out["source"] == "kroki"
    assert not MERMAID_ENGINE.is_open()


def test_url_only_while_open_never_contacts_kroki(url_only, ink) -> None:
    client = url_client()
    trip()

    with patch(GET_PATCH) as get:
        out = run_diagram_pipeline(ctx(), kroki_client=client)

    get.assert_not_called()
    assert out["source"] == "mermaid_ink"


def test_url_only_without_a_fallback_never_contacts_kroki(
    url_only, monkeypatch
) -> None:
    """Unchanged behaviour: nothing to fall back to, so no link check and no breaker."""
    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", False)
    client = url_client()

    with patch(GET_PATCH) as get:
        out = run_diagram_pipeline(ctx(), kroki_client=client)

    assert out["source"] == "kroki"
    get.assert_not_called()


def test_forced_fetch_in_url_only_mode_uses_the_normal_path(url_only, ink) -> None:
    client = hanging()

    run_diagram_pipeline(ctx(force_fetch=True), kroki_client=client)

    client.get_url.assert_not_called()
    assert client.generate_diagram.call_count == 1


# --------------------------------------------------------------------- housekeeping
def test_switching_the_kroki_server_forgets_the_old_ones_health(monkeypatch) -> None:
    from mcp_core.core import utils

    monkeypatch.setattr(MCP_SETTINGS, "kroki_server", MCP_SETTINGS.kroki_server)
    monkeypatch.setattr(utils, "_kroki_client", None)
    trip()
    assert MERMAID_ENGINE.is_open()

    utils.use_kroki_server("http://another-kroki:8000")

    assert not MERMAID_ENGINE.is_open()


def test_the_skip_message_says_how_to_turn_it_off() -> None:
    message = _handle_diagram_error(EngineUnavailable("Mermaid", 42.0), SOURCE)

    assert "Mermaid" in message and "42s" in message
    assert "MCP_KROKI_CIRCUIT_COOLDOWN_SECONDS=0" in message
