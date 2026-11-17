"""Tests for local PlantUML JAR rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tools.kroki import plantuml_jar as jar_mod


def test_resolve_jar_path_uses_explicit(tmp_path: Path) -> None:
    jar = tmp_path / "plantuml.jar"
    jar.write_bytes(b"jar")
    assert jar_mod.resolve_jar_path(str(jar)) == jar


def test_resolve_jar_path_missing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PLANTUML_JAR_PATH", raising=False)
    monkeypatch.setattr(jar_mod, "DEFAULT_VENDOR_JAR", tmp_path / "missing.jar")
    with pytest.raises(
        jar_mod.PlantUMLJarNotFoundError, match="plantuml.jar not found"
    ):
        jar_mod.resolve_jar_path(None)


def test_resolve_java_path_prefers_explicit(tmp_path: Path) -> None:
    java = tmp_path / ("java.exe" if __import__("os").name == "nt" else "java")
    java.write_text("#!/bin/sh\n", encoding="utf-8")
    assert jar_mod.resolve_java_path(str(java)) == str(java)


def test_jar_available_false_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PLANTUML_JAR_PATH", raising=False)
    monkeypatch.delenv("JAVA_PATH", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(jar_mod, "DEFAULT_VENDOR_JAR", tmp_path / "nope.jar")
    monkeypatch.setattr(jar_mod.shutil, "which", lambda _name: None)
    assert jar_mod.jar_available() is False


def test_render_plantuml_jar_rejects_unknown_format() -> None:
    with pytest.raises(jar_mod.PlantUMLJarError, match="Unsupported"):
        jar_mod.render_plantuml_jar("@startuml\nA -> B\n@enduml", "base64")


def test_render_plantuml_jar_runs_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    java = tmp_path / "java"
    java.write_text("x", encoding="utf-8")
    jar = tmp_path / "plantuml.jar"
    jar.write_bytes(b"jar")

    def fake_run(cmd: list[str], **_kwargs: Any) -> MagicMock:
        # PlantUML writes diagram.<fmt> into -o dir; recreate that.
        out_dir = Path(cmd[cmd.index("-o") + 1])
        (out_dir / "diagram.svg").write_text("<svg/>", encoding="utf-8")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        return result

    monkeypatch.setattr(jar_mod.subprocess, "run", fake_run)
    data = jar_mod.render_plantuml_jar(
        "@startuml\nclass A\n@enduml",
        "svg",
        jar_path=str(jar),
        java_path=str(java),
    )
    assert data == b"<svg/>"


def test_plantuml_fallback_prefers_jar(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp_core.core import diagram_rendering as rendering

    monkeypatch.setattr(
        "tools.kroki.plantuml_jar.jar_available",
        lambda **_kwargs: True,
    )

    def fake_jar(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "code": "x",
            "url": "https://www.plantuml.com/plantuml/uml/x",
            "playground": "https://www.plantuml.com/plantuml/uml/x",
            "local_path": None,
            "source": "plantuml_jar",
            "content_base64": "YQ==",
        }

    monkeypatch.setattr(rendering, "_generate_diagram_plantuml_jar", fake_jar)
    result = rendering._generate_diagram_plantuml_fallback(
        "class",
        "@startuml\nclass A\n@enduml",
        "svg",
        None,
        1.0,
        force_fetch=True,
    )
    assert result["source"] == "plantuml_jar"


def test_plantuml_fallback_jar_error_uses_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp_core.core import diagram_rendering as rendering

    monkeypatch.setattr(
        "tools.kroki.plantuml_jar.jar_available",
        lambda **_kwargs: True,
    )

    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("jar broken")

    monkeypatch.setattr(rendering, "_generate_diagram_plantuml_jar", boom)

    class FakePlantUML:
        def __init__(self, url: str) -> None:
            self.url = url

        def deflate_and_encode(self, _code: str) -> str:
            return "encoded"

    class FakeResponse:
        content = b"<svg/>"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("tools.kroki.plantuml.PlantUML", FakePlantUML)
    monkeypatch.setattr(
        rendering.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    monkeypatch.setattr(rendering.MCP_SETTINGS, "url_only", False)
    monkeypatch.setattr(
        rendering.MCP_SETTINGS, "plantuml_server", "http://plantuml.test"
    )

    result = rendering._generate_diagram_plantuml_fallback(
        "class",
        "@startuml\nclass A\n@enduml",
        "svg",
        None,
        1.0,
        force_fetch=True,
    )
    assert result["source"] == "plantuml_server"
    assert result["url"].startswith("http://plantuml.test/svg/")
