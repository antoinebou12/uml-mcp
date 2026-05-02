"""Tests for static discovery artifacts written by build_static_server_card."""

import json
from pathlib import Path

from mcp_core.build_static_server_card import _write_discovery_artifacts


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
