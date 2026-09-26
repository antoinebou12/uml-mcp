"""Regression checks for ChatGPT MCP smoke-test prompts, and real runs of them."""

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp_core.core.diagram_validation import validate_uml_inputs

SMOKE_PATH = Path(__file__).parent / "prompts" / "chatgpt_mcp_smoke_test.md"
ROOT = Path(__file__).resolve().parents[1]

_SMOKE_SEQUENCE = """sequenceDiagram
       participant Client
       participant Server
       Client->>Server: request
       Server-->>Client: response"""

_BATCH_SEQUENCE = """sequenceDiagram
  participant A
  participant B
  A->>B: MCP 2026 request
  B-->>A: Stateless response"""


def test_smoke_prompt_requires_image_url_and_playground():
    text = SMOKE_PATH.read_text(encoding="utf-8")
    assert "generate_uml_image" in text
    assert "Playground" in text
    assert "![diagram]" in text
    assert "output/*.png" in text
    assert "MCP_SMOKE_TEST: PASS" in text
    assert "MCP_BATCH_TEST: PASS" in text
    assert "sequenceDiagram; participant A" not in text
    assert "participant Client" in text
    assert "participant Server" in text
    assert "graph TD; Client-->MCP;" in text
    assert "If that tool is missing" in text


def test_smoke_client_server_fixture_validates_strict():
    assert validate_uml_inputs("mermaid", _SMOKE_SEQUENCE, "svg", strict=True)["valid"]


def test_smoke_batch_fixtures_validate_strict():
    flowchart = "graph TD; Client-->MCP; MCP-->Kroki; Kroki-->MCP; MCP-->Client;"
    assert validate_uml_inputs("mermaid", flowchart, "svg", strict=True)["valid"]
    assert validate_uml_inputs("mermaid", _BATCH_SEQUENCE, "svg", strict=True)["valid"]
    packed = (
        "sequenceDiagram; participant A; participant B; "
        "A->>B: MCP 2026 request; B-->>A: Stateless response;"
    )
    assert validate_uml_inputs("mermaid", packed, "svg", strict=True)["valid"] is False


def test_smoke_prompt_documents_enterprise_and_runner():
    text = SMOKE_PATH.read_text(encoding="utf-8")
    assert "MCP_AUTH_SMOKE_TEST: PASS" in text
    assert "scripts/run_mcp_smoke.py" in text
    assert "Never print" in text


def test_automated_smoke_runner_passes_in_process():
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    env: dict[str, str] = {
        **os.environ,
        "USE_REAL_FASTMCP": "1",
        "MOCK_FASTMCP": "0",
        "TESTING": "0",
        "MCP_URL_ONLY": "true",
        "PYTHONPATH": str(root),
    }
    env.pop("MCP_AUTH_MODE", None)
    proc = subprocess.run(
        [sys.executable, "scripts/run_mcp_smoke.py", "--offline"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert "MCP_SMOKE_TEST: PASS" in proc.stdout, proc.stdout + proc.stderr
    assert "MCP_BATCH_TEST: PASS" in proc.stdout, proc.stdout + proc.stderr


def _run_script(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    env = {**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1"}
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_smoke_prompt_against_real_stack(tier_stack, tmp_path):
    """The prompt's steps, run by a real MCP client against fake/local/public Kroki."""
    report = tmp_path / "smoke.json"
    proc = _run_script(
        [
            "scripts/run_mcp_smoke.py",
            "--url",
            f"{tier_stack['base']}/mcp",
            "--allow-http",
            "--json",
            str(report),
        ]
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "MCP_SMOKE_TEST: PASS" in out and "MCP_BATCH_TEST: PASS" in out, out
    steps = json.loads(report.read_text())["steps"]
    assert {s["status"] for s in steps} == {"PASS"}, steps  # nothing skipped
    assert any(s["name"] == "svg content" for s in steps)
    assert any("PNG" in s["detail"] for s in steps if s["name"] == "inline image")


def test_full_catalog_stress_against_real_stack(tier_stack, tmp_path):
    """tests/prompts/kroki_full_catalog_stress_test.md: all 37 types must render."""
    report = tmp_path / "stress.json"
    proc = _run_script(
        [
            "scripts/run_vercel_kroki_stress.py",
            "--url",
            f"{tier_stack['base']}/mcp",
            "--check-content",
            "--min-catalog",
            "37",
            "--json",
            str(report),
        ]
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0 and "STRESS_TEST: PASS" in out, out
    data = json.loads(report.read_text())
    assert data["catalog_passed"] == 37 and data["failed"] == [], data


def test_smoke_prompt_documents_the_real_kroki_runs():
    text = SMOKE_PATH.read_text(encoding="utf-8")
    assert "MCP_BATCH_TEST: PASS|FAIL" in text
    assert "--allow-http" in text and "--json" in text
    assert "decodable PNG" in text
