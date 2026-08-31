"""Contract tests for the Claude Desktop MCPB bundle.

These guard the packaging surface: the manifest must stay valid MCPB 0.4, stay in
sync with pyproject and the live tool registry, and the staging step must never
copy anything that does not belong in a published archive.
"""

import importlib.util
import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "packaging" / "mcpb" / "manifest.json"


def _load_build_script():
    """Load scripts/build_mcpb.py without putting scripts/ on sys.path."""
    spec = importlib.util.spec_from_file_location(
        "build_mcpb", ROOT / "scripts" / "build_mcpb.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_mcpb = _load_build_script()


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registered_tool_names() -> set[str]:
    """Tool names the server actually registers at runtime."""
    from mcp_core.tools import diagram_tools  # noqa: F401  (populates the registry)
    from mcp_core.tools.tool_decorator import get_tool_registry

    return set(get_tool_registry())


def test_manifest_is_mcpb_04_uv_bundle(manifest: dict) -> None:
    assert manifest["manifest_version"] == "0.4"
    assert manifest["name"] == "uml-mcp"
    assert manifest["server"]["type"] == "uv"
    assert manifest["server"]["entry_point"] == "server.py"
    assert manifest["license"] == "MIT"
    assert manifest["author"]["name"] == "Antoine Boucher"


def test_manifest_launches_the_repository_stdio_entry_point(manifest: dict) -> None:
    config = manifest["server"]["mcp_config"]
    assert config["command"] == "uv"
    # `--directory ${__dirname}` is what makes uv resolve the *bundle's* pyproject
    # and lockfile rather than whatever directory Claude Desktop happens to start in.
    assert config["args"] == [
        "run",
        "--directory",
        "${__dirname}",
        "python",
        "server.py",
    ]
    assert (ROOT / "server.py").is_file()


def test_manifest_version_matches_project_version(
    manifest: dict, pyproject: dict
) -> None:
    from mcp_core.core.config import MCPSettings

    assert manifest["version"] == pyproject["project"]["version"]
    assert manifest["version"] == MCPSettings().version


def test_manifest_advertises_exactly_the_registered_tools(
    manifest: dict, registered_tool_names: set[str]
) -> None:
    advertised = {tool["name"] for tool in manifest["tools"]}
    assert advertised == registered_tool_names
    assert manifest["tools_generated"] is False
    assert all(tool["description"].strip() for tool in manifest["tools"])


def test_every_substituted_setting_is_declared(manifest: dict) -> None:
    env = manifest["server"]["mcp_config"]["env"]
    referenced = {
        name
        for value in env.values()
        for name in re.findall(r"\$\{user_config\.([a-z_]+)\}", value)
    }
    assert referenced <= set(manifest["user_config"])
    assert referenced == {"output_dir", "kroki_server", "plantuml_server"}


def test_server_url_settings_declare_defaults(manifest: dict) -> None:
    """Unset settings substitute as an empty string.

    ``KROKI_SERVER``/``PLANTUML_SERVER`` are read with ``os.environ.get(name,
    fallback)``, so an empty value would win over the code default and break
    rendering. ``output_dir`` is safe without one because ``_get_output_dir``
    or-chains through to ``cwd/output``.
    """
    user_config = manifest["user_config"]
    for name in ("kroki_server", "plantuml_server"):
        assert user_config[name]["default"].startswith("http")
    assert "default" not in user_config["output_dir"]
    assert user_config["output_dir"]["type"] == "directory"
    assert all(not entry.get("required") for entry in user_config.values())


def test_output_directory_setting_also_scopes_the_write_sandbox(
    manifest: dict,
) -> None:
    """A directory the user picked in the host UI must be writable.

    ``GenerateUMLInput.validate_output_location`` sandboxes writes to
    ``MCP_OUTPUT_ROOT``; pointing that at the same folder keeps the sandbox intact
    instead of disabling it with ``MCP_ALLOW_ARBITRARY_OUTPUT_DIR``.
    """
    env = manifest["server"]["mcp_config"]["env"]
    assert (
        env["MCP_OUTPUT_DIR"] == env["MCP_OUTPUT_ROOT"] == "${user_config.output_dir}"
    )
    assert "MCP_ALLOW_ARBITRARY_OUTPUT_DIR" not in env


def test_manifest_declares_cross_platform_compatibility(manifest: dict) -> None:
    compatibility = manifest["compatibility"]
    assert set(compatibility["platforms"]) == {"darwin", "linux", "win32"}
    assert compatibility["runtimes"]["python"].startswith(">=3.12")


def test_generated_bundle_pyproject_copies_dependencies_verbatim(
    pyproject: dict,
) -> None:
    generated = tomllib.loads(build_mcpb.build_bundle_pyproject(pyproject))

    assert generated["project"]["dependencies"] == pyproject["project"]["dependencies"]
    assert (
        generated["project"]["requires-python"]
        == pyproject["project"]["requires-python"]
    )
    # Without this, `uv run` would try to build UML-MCP itself, which needs
    # poetry-core and a README that the bundle deliberately does not ship.
    assert generated["tool"]["uv"]["package"] is False
    assert "build-system" not in generated


def test_staging_copies_only_runtime_files(tmp_path: Path, pyproject: dict) -> None:
    stage_dir = tmp_path / "mcpb-stage"
    build_mcpb.stage(stage_dir, pyproject)

    assert build_mcpb.audit(stage_dir) == []

    for expected in (
        "manifest.json",
        "pyproject.toml",
        ".mcpbignore",
        "server.py",
        "LICENSE",
        "mcp_core/core/config.py",
        "tools/kroki/kroki.py",
    ):
        assert (stage_dir / expected).is_file(), expected

    staged = {
        str(p.relative_to(stage_dir)) for p in stage_dir.rglob("*") if p.is_file()
    }
    assert not any(
        name.startswith(("tests", "docs", ".env", "logs")) for name in staged
    )
    assert not any(name.endswith((".pyc", ".log", ".pdf")) for name in staged)


def test_staged_manifest_is_stamped_with_the_project_version(
    tmp_path: Path, pyproject: dict
) -> None:
    stage_dir = tmp_path / "mcpb-stage"
    build_mcpb.stage(stage_dir, pyproject)

    staged = json.loads((stage_dir / "manifest.json").read_text(encoding="utf-8"))
    assert staged["version"] == pyproject["project"]["version"]


def test_audit_rejects_a_polluted_stage(tmp_path: Path, pyproject: dict) -> None:
    """Running the bundle in place leaves .venv/ and logs/ behind."""
    stage_dir = tmp_path / "mcpb-stage"
    build_mcpb.stage(stage_dir, pyproject)

    (stage_dir / ".venv").mkdir()
    (stage_dir / ".venv" / "pyvenv.cfg").write_text("", encoding="utf-8")
    (stage_dir / ".env").write_text("SECRET=1", encoding="utf-8")

    offenders = build_mcpb.audit(stage_dir)
    assert any(".venv" in offender for offender in offenders)
    assert any(".env" in offender for offender in offenders)
