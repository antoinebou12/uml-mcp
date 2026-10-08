"""Tests for static discovery artifacts written by build_static_server_card."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mcp_core.build_static_server_card import (
    _DEFAULT_PUBLIC_BASE,
    _write_discovery_artifacts,
)
from mcp_core.core.agent_discovery import (
    build_agent_skills_index,
    build_api_catalog,
    build_oauth_protected_resource,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WELL_KNOWN_ROOTS = (REPO_ROOT / ".well-known", REPO_ROOT / "public" / ".well-known")
ARTIFACTS = (
    "api-catalog",
    "oauth-protected-resource",
    "agent-skills/index.json",
    "mcp/server-card.json",
    "mcp/config-schema.json",
)
REGENERATE = "uv run python -m mcp_core.build_static_server_card"
RAW_PREFIX = "https://raw.githubusercontent.com/antoinebou12/uml-mcp/main/"


def _fresh_server_card() -> dict:
    """Build the server card exactly as the build step does, in a clean interpreter."""
    code = (
        "import json; import mcp_core.build_static_server_card; "
        "from mcp_core.core.server_card import build_server_card; "
        "print(json.dumps(build_server_card(strict=True)))"
    )
    base = {k: v for k, v in os.environ.items() if k != "USE_REAL_FASTMCP"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env={**base, "UML_MCP_CONFIG": "none"},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_write_discovery_artifacts_creates_files(tmp_path: Path):
    skill_dir = tmp_path / ".skill" / "skills" / "x"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# H\n\nBody text\n", encoding="utf-8")

    _write_discovery_artifacts(str(tmp_path), "https://example.com")

    wk = tmp_path / ".well-known"
    assert (wk / "api-catalog").is_file()
    assert (wk / "oauth-protected-resource").is_file()
    assert (wk / "agent-skills" / "index.json").is_file()

    catalog = json.loads((wk / "api-catalog").read_text(encoding="utf-8"))
    assert "linkset" in catalog
    assert catalog["linkset"][0]["anchor"] == "https://example.com/"

    oauth = json.loads((wk / "oauth-protected-resource").read_text(encoding="utf-8"))
    assert oauth["resource"] == "https://example.com/"

    idx = json.loads((wk / "agent-skills" / "index.json").read_text(encoding="utf-8"))
    assert "$schema" in idx
    assert len(idx["skills"]) == 1
    assert len(idx["skills"][0]["sha256"]) == 64


def test_write_discovery_artifacts_uses_lf_newlines(tmp_path: Path):
    """A Windows run must not emit CRLF (Vercel rebuilds these files on Linux)."""
    skill_dir = tmp_path / ".skill" / "skills" / "x"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"# H\n\nBody text\n")

    _write_discovery_artifacts(str(tmp_path), "https://example.com")

    for wk in (tmp_path / ".well-known", tmp_path / "public" / ".well-known"):
        for name in (
            "api-catalog",
            "oauth-protected-resource",
            "agent-skills/index.json",
        ):
            assert b"\r" not in (wk / name).read_bytes(), f"CR in {wk / name}"


@pytest.mark.parametrize("name", ARTIFACTS)
@pytest.mark.parametrize("root", WELL_KNOWN_ROOTS, ids=("root", "public"))
def test_committed_discovery_artifacts_use_lf_newlines(root: Path, name: str):
    assert b"\r" not in (root / name).read_bytes(), (
        f"{root / name} has CRLF line endings; regenerate with `{REGENERATE}`"
    )


def test_committed_discovery_artifacts_are_current():
    """Committed copies must equal what the build step generates (no stale digests)."""
    expected: dict[str, object] = {
        "api-catalog": build_api_catalog(_DEFAULT_PUBLIC_BASE),
        "oauth-protected-resource": build_oauth_protected_resource(
            _DEFAULT_PUBLIC_BASE
        ),
        "agent-skills/index.json": build_agent_skills_index(str(REPO_ROOT)),
        "mcp/server-card.json": _fresh_server_card(),
        "mcp/config-schema.json": json.loads(
            (REPO_ROOT / "smithery-config-schema.json").read_text(encoding="utf-8")
        ),
    }
    stale = [
        str((root / name).relative_to(REPO_ROOT))
        for root in WELL_KNOWN_ROOTS
        for name in ARTIFACTS
        if json.loads((root / name).read_text(encoding="utf-8")) != expected[name]
    ]
    assert not stale, (
        f"stale discovery artifacts, run `{REGENERATE}` and commit: {stale}"
    )


@pytest.mark.parametrize("root", WELL_KNOWN_ROOTS, ids=("root", "public"))
def test_agent_skills_digests_match_published_files(root: Path):
    """Each sha256 must be the digest of the exact bytes GitHub raw serves."""
    index = json.loads((root / "agent-skills" / "index.json").read_text("utf-8"))
    assert index["skills"], f"empty agent-skills index in {root}"
    for skill in index["skills"]:
        assert skill["url"].startswith(RAW_PREFIX), skill["url"]
        path = REPO_ROOT / skill["url"].removeprefix(RAW_PREFIX)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert skill["sha256"] == digest, f"{skill['name']}: stale digest in {root}"


def test_write_discovery_artifacts_refuses_empty_skills_index(tmp_path: Path):
    """No .skill/ (e.g. excluded from a Vercel upload) must fail, not publish []."""
    with pytest.raises(SystemExit) as excinfo:
        _write_discovery_artifacts(str(tmp_path), "https://example.com")

    assert excinfo.value.code == 1
    assert not (tmp_path / ".well-known" / "agent-skills" / "index.json").exists()
    assert not (tmp_path / "public" / ".well-known").exists()


def test_vercelignore_keeps_skills_for_the_build_step():
    """The buildCommand reads .skill/skills; ignoring it empties the live index."""
    ignored = {
        line.strip().rstrip("/")
        for line in (REPO_ROOT / ".vercelignore").read_text("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert ".skill" not in ignored, ".vercelignore must not exclude .skill/"
