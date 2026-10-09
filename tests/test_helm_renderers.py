"""Contract tests for the optional in-cluster renderers in deploy/helm/uml-mcp.

Static checks always run; the rendering checks need `helm` on PATH and are skipped
otherwise (the CI `helm` job lints and renders every ci/*-values.yaml either way).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy" / "helm" / "uml-mcp"
COMPOSE = ROOT / "docker-compose.yml"
RENDERERS_VALUES = CHART / "ci" / "renderers-values.yaml"
NONE_VALUES = CHART / "ci" / "none-values.yaml"
SERVER = "demo-uml-mcp"


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_renderers_are_opt_in(values: dict[str, Any]) -> None:
    """The chart must render exactly as before until a renderer is enabled."""
    assert values["kroki"]["enabled"] is False
    assert values["plantuml"]["enabled"] is False
    assert values["mermaidInk"]["enabled"] is False
    assert values["plantuml"]["externalUrl"] == ""
    assert values["mermaidInk"]["externalUrl"] == ""
    # null = derived from the configured fallback renderers.
    assert values["diagramFallback"] is None


def test_renderer_images_are_pinned_like_compose(values: dict[str, Any]) -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]

    def image(component: dict[str, Any]) -> str:
        return f"{component['image']['repository']}:{component['image']['tag']}"

    assert image(values["plantuml"]) == compose["plantuml-server"]["image"]
    assert image(values["mermaidInk"]) == compose["mermaid-ink"]["image"]
    for component in (
        values["kroki"],
        values["kroki"]["companions"]["mermaid"],
        values["kroki"]["companions"]["blockdiag"],
    ):
        assert component["image"]["tag"] not in ("", "latest")


def test_mermaid_ink_seccomp_matches_compose(values: dict[str, Any]) -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]

    assert compose["mermaid-ink"]["security_opt"] == ["seccomp=unconfined"]
    assert values["mermaidInk"]["securityContext"] == {
        "seccompProfile": {"type": "Unconfined"}
    }


def _helm_template(*args: str) -> list[dict[str, Any]]:
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm not installed")
    out = subprocess.run(
        [helm, "template", "demo", str(CHART), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [doc for doc in yaml.safe_load_all(out) if doc]


def _server(docs: list[dict[str, Any]]) -> dict[str, Any]:
    return next(
        d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"] == SERVER
    )


def _server_env_entries(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _server(docs)["spec"]["template"]["spec"]["containers"][0]["env"]


def _server_env(docs: list[dict[str, Any]]) -> dict[str, str | None]:
    return {e["name"]: e.get("value") for e in _server_env_entries(docs)}


def test_default_render_has_no_renderers() -> None:
    docs = _helm_template("-f", str(NONE_VALUES))
    env = _server_env(docs)

    assert env["KROKI_SERVER"] == "https://kroki.io"
    for name in (
        "PLANTUML_SERVER",
        "MERMAID_INK_SERVER",
        "USE_LOCAL_KROKI",
        "MCP_DIAGRAM_FALLBACK",
    ):
        assert name not in env
    assert [d["metadata"]["name"] for d in docs if d["kind"] == "Deployment"] == [
        SERVER
    ]


def test_all_renderers_are_wired_and_isolated() -> None:
    docs = _helm_template("-f", str(RENDERERS_VALUES))
    env = _server_env(docs)

    assert env["USE_LOCAL_KROKI"] == "true"
    assert env["KROKI_SERVER"] == f"http://{SERVER}-kroki:8000"
    assert env["PLANTUML_SERVER"] == f"http://{SERVER}-plantuml:8080"
    assert env["MERMAID_INK_SERVER"] == f"http://{SERVER}-mermaid-ink:3000"
    assert env["USE_LOCAL_MERMAID_INK"] == "true"
    assert env["MCP_DIAGRAM_FALLBACK"] == "true"

    # The server Service must not select renderer pods, or MCP traffic reaches them.
    selector = next(
        d for d in docs if d["kind"] == "Service" and d["metadata"]["name"] == SERVER
    )["spec"]["selector"]
    for deployment in docs:
        if deployment["kind"] != "Deployment" or deployment["metadata"]["name"] == (
            SERVER
        ):
            continue
        labels = deployment["spec"]["template"]["metadata"]["labels"]
        assert not all(labels.get(k) == v for k, v in selector.items()), (
            f"{deployment['metadata']['name']} is selected by the server Service"
        )

    # Kroki runs its engines as sidecars, pinned (blockdiag versions independently).
    kroki = next(
        d
        for d in docs
        if d["kind"] == "Deployment" and d["metadata"]["name"] == f"{SERVER}-kroki"
    )
    containers = {
        c["name"]: c["image"] for c in kroki["spec"]["template"]["spec"]["containers"]
    }
    assert set(containers) == {"kroki", "mermaid", "blockdiag"}
    assert not any(image.endswith(":latest") for image in containers.values())


def test_network_policy_allows_the_server_to_reach_renderers() -> None:
    docs = _helm_template("-f", str(RENDERERS_VALUES))
    policy = next(d for d in docs if d["kind"] == "NetworkPolicy")

    reachable = {
        rule["to"][0]["podSelector"]["matchLabels"]["app.kubernetes.io/name"]: rule[
            "ports"
        ][0]["port"]
        for rule in policy["spec"]["egress"]
        if "to" in rule
    }
    # Container ports, not Service ports.
    assert reachable == {
        "uml-mcp-kroki": 8000,
        "uml-mcp-plantuml": 8080,
        "uml-mcp-mermaid-ink": 3000,
    }


def test_env_names_are_never_duplicated() -> None:
    """A duplicate env name is last-wins for kubectl but rejected by server-side apply."""
    docs = _helm_template(
        "-f",
        str(RENDERERS_VALUES),
        "--set-string",
        "env.MCP_DIAGRAM_FALLBACK=false,env.PLANTUML_SERVER=http://old:1",
    )
    names = [e["name"] for e in _server_env_entries(docs)]

    assert len(names) == len(set(names)), sorted(
        n for n in set(names) if names.count(n) > 1
    )
    # Renderer values own these; the colliding env entries are ignored.
    assert _server_env(docs)["PLANTUML_SERVER"] == f"http://{SERVER}-plantuml:8080"


def test_external_url_and_forced_fallback() -> None:
    external = _server_env(
        _helm_template(
            "-f", str(NONE_VALUES), "--set", "plantuml.externalUrl=http://p.corp:8080"
        )
    )
    assert external["PLANTUML_SERVER"] == "http://p.corp:8080"
    assert external["MCP_DIAGRAM_FALLBACK"] == "true"

    forced = _server_env(
        _helm_template("-f", str(RENDERERS_VALUES), "--set", "diagramFallback=false")
    )
    assert forced["MCP_DIAGRAM_FALLBACK"] == "false"
