"""Contract tests for docker-compose.yml.

The point of the `plantuml` / `mermaid-ink` profiles is that they change nothing
until you ask for them, so these assert the default stack is byte-for-byte the
same set of services and environment it has always been, and that the opt-in
services are pinned and health-checked.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
PLANTUML_IMAGE = "plantuml/plantuml-server:jetty-v1.2026.6"
MERMAID_INK_IMAGE = "ghcr.io/jihchi/mermaid.ink:v16.0.0"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def services(compose: dict) -> dict:
    return compose["services"]


def _environment(service: dict) -> dict[str, str]:
    """Compose list-form environment (`KEY=value`) as a mapping."""
    entries = service["environment"]
    if isinstance(entries, dict):
        return {key: str(value) for key, value in entries.items()}
    return dict(entry.split("=", 1) for entry in entries)


def test_default_stack_is_unchanged(services: dict) -> None:
    default = {
        name for name, service in services.items() if not service.get("profiles")
    }
    assert default == {"uml-mcp", "kroki", "mermaid", "blockdiag"}


def test_plantuml_server_is_opt_in_and_pinned(services: dict) -> None:
    plantuml = services["plantuml-server"]

    assert plantuml["profiles"] == ["plantuml", "fallback"]
    assert plantuml["image"] == PLANTUML_IMAGE
    # A floating tag would silently change the renderer under users.
    assert not plantuml["image"].endswith((":latest", ":jetty"))


def test_plantuml_server_has_an_http_health_check(services: dict) -> None:
    healthcheck = services["plantuml-server"]["healthcheck"]

    # curl is verified present at /usr/bin/curl in the pinned image.
    assert healthcheck["test"] == ["CMD", "curl", "-fsS", "http://127.0.0.1:8080/"]
    assert healthcheck["retries"] >= 3
    assert healthcheck["start_period"]


def test_plantuml_server_does_not_collide_with_existing_ports(services: dict) -> None:
    published = [
        mapping.split(":")[0].strip('"')
        for service in services.values()
        for mapping in service.get("ports", [])
    ]

    assert "8002" in published
    assert "8003" in published
    assert len(published) == len(set(published)), f"duplicate host ports: {published}"


def test_uml_mcp_optional_dependency_keeps_the_default_startup(services: dict) -> None:
    depends_on = services["uml-mcp"]["depends_on"]

    assert set(depends_on) == {
        "kroki",
        "blockdiag",
        "mermaid",
        "plantuml-server",
        "mermaid-ink",
    }
    for name in ("kroki", "blockdiag", "mermaid"):
        assert depends_on[name].get("required", True) is True
    assert depends_on["plantuml-server"]["required"] is False
    assert depends_on["mermaid-ink"]["required"] is False


def test_existing_uml_mcp_environment_is_preserved(services: dict) -> None:
    environment = _environment(services["uml-mcp"])

    assert environment["MCP_OUTPUT_DIR"] == "/app/output"
    assert environment["USE_LOCAL_KROKI"] == "true"
    assert environment["KROKI_SERVER"] == "http://kroki:8000"
    assert environment["FASTMCP_STATELESS_HTTP"] == "true"


def test_new_environment_passthrough_defaults_to_current_behaviour(
    services: dict,
) -> None:
    """Overridable from the shell, but identical to today when left alone.

    The defaults mirror mcp_core/core/config.py: USE_LOCAL_PLANTUML off,
    PLANTUML_SERVER at the compose service name, fallback chain disabled because
    the stack runs a local Kroki.
    """
    environment = _environment(services["uml-mcp"])

    assert environment["USE_LOCAL_PLANTUML"] == "${USE_LOCAL_PLANTUML:-false}"
    assert (
        environment["PLANTUML_SERVER"]
        == "${PLANTUML_SERVER:-http://plantuml-server:8080}"
    )
    assert environment["MCP_DIAGRAM_FALLBACK"] == "${MCP_DIAGRAM_FALLBACK:-false}"
    assert environment["USE_LOCAL_MERMAID_INK"] == "${USE_LOCAL_MERMAID_INK:-false}"
    # Empty keeps public mermaid.ink unless USE_LOCAL_MERMAID_INK is set.
    assert environment["MERMAID_INK_SERVER"] == "${MERMAID_INK_SERVER:-}"


def test_plantuml_server_default_resolves_to_the_compose_service(
    services: dict,
) -> None:
    """The PLANTUML_SERVER default is a hostname, so the service must match it.

    Renaming the service without updating the default would leave the fallback
    pointing at a host that does not exist.
    """
    default = _environment(services["uml-mcp"])["PLANTUML_SERVER"]
    host = default.split("//", 1)[1].split(":")[0]

    assert host in services
    assert host == "plantuml-server"


def test_mermaid_ink_is_opt_in_and_pinned(services: dict) -> None:
    mermaid_ink = services["mermaid-ink"]

    assert mermaid_ink["profiles"] == ["mermaid-ink", "fallback"]
    assert mermaid_ink["image"] == MERMAID_INK_IMAGE
    assert not mermaid_ink["image"].endswith(":latest")


def test_mermaid_ink_can_launch_chromium_and_reports_health(services: dict) -> None:
    mermaid_ink = services["mermaid-ink"]

    # Upstream's documented alternative to --cap-add=SYS_ADMIN.
    assert mermaid_ink["security_opt"] == ["seccomp=unconfined"]
    # The image has node but no curl.
    healthcheck = mermaid_ink["healthcheck"]
    assert healthcheck["test"][:2] == ["CMD", "node"]
    assert "http://127.0.0.1:3000/" in healthcheck["test"][-1]


def test_mermaid_ink_local_default_resolves_to_the_compose_service(
    services: dict,
) -> None:
    """USE_LOCAL_MERMAID_INK falls back to http://mermaid-ink:3000 in config.py."""
    config = (ROOT / "mcp_core" / "core" / "config.py").read_text(encoding="utf-8")

    assert '"http://mermaid-ink:3000"' in config
    assert "mermaid-ink" in services
    assert services["mermaid-ink"]["ports"] == ["8003:3000"]


def test_extra_kroki_companions_are_opt_in(services: dict) -> None:
    for name in ("bpmn", "excalidraw"):
        assert services[name]["profiles"] == ["kroki-extra"]
        assert services[name]["image"] == f"yuzutech/kroki-{name}"
    environment = _environment(services["kroki"])
    assert environment["KROKI_BPMN_HOST"] == "bpmn"
    assert environment["KROKI_EXCALIDRAW_HOST"] == "excalidraw"
