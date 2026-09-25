"""``uml-mcp.yaml``: discovery, precedence, validation, tool gating and the config CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mcp_core.core import commands
from mcp_core.core.settings_file import (
    AppConfig,
    ConfigFileError,
    apply_to_environ,
    find_config_path,
    get_config,
    load_config,
    parse_app_config,
    read_config_file,
    reset_config_cache,
)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Empty cwd + XDG home so real user/system files are never discovered."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("UML_MCP_CONFIG", raising=False)
    yield tmp_path
    reset_config_cache()


# ------------------------------------------------------------------ discovery
def test_discovery_order(isolated):
    env = {"XDG_CONFIG_HOME": str(isolated / "xdg")}
    assert find_config_path(None, env) in (None, Path("/etc/uml-mcp/config.yaml"))
    xdg = write(isolated / "xdg" / "uml-mcp" / "config.yaml", "version: 1\n")
    assert find_config_path(None, env) == xdg
    local = write(isolated / "uml-mcp.yaml", "version: 1\n")
    assert find_config_path(None, env) == Path("uml-mcp.yaml")
    other = write(isolated / "other.yaml", "version: 1\n")
    assert find_config_path(None, {**env, "UML_MCP_CONFIG": str(other)}) == other
    assert find_config_path(str(local), {**env, "UML_MCP_CONFIG": str(other)}) == local
    assert find_config_path(None, {**env, "UML_MCP_CONFIG": "none"}) is None


def test_missing_explicit_files_are_errors(isolated):
    with pytest.raises(ConfigFileError, match="not found"):
        find_config_path("nope.yaml", {})
    with pytest.raises(ConfigFileError, match="missing file"):
        find_config_path(None, {"UML_MCP_CONFIG": "nope.yaml"})


def test_invalid_files_are_rejected(isolated):
    with pytest.raises(ConfigFileError, match="unknown section"):
        read_config_file(write(isolated / "a.yaml", "servr: {}\n"))
    with pytest.raises(ConfigFileError, match="mapping"):
        read_config_file(write(isolated / "b.yaml", "- 1\n"))
    with pytest.raises(ConfigFileError, match="cannot read"):
        read_config_file(write(isolated / "c.yaml", "a: [\n"))
    with pytest.raises(ConfigFileError, match="rate_limit.default.requests_per_minute"):
        parse_app_config({"rate_limit": {"default": {"requests_per_minute": 0}}})
    with pytest.raises(ConfigFileError, match="audit.sinks"):
        parse_app_config({"audit": {"sinks": ["syslog"]}})


# ----------------------------------------------------------------- precedence
def test_file_fills_env_but_env_wins(isolated):
    path = write(
        isolated / "uml-mcp.yaml",
        "rendering:\n  kroki_server: https://kroki.file\n  url_only: true\n"
        "  output_dir: ~/diagrams\nserver:\n  allowed_hosts: [a.example, b.example]\n",
    )
    env = {"KROKI_SERVER": "https://kroki.env"}
    loaded = load_config(str(path), env)
    assert env["KROKI_SERVER"] == "https://kroki.env"  # env wins
    assert env["MCP_URL_ONLY"] == "true"
    assert json.loads(env["MCP_ALLOWED_HOSTS"]) == ["a.example", "b.example"]
    assert env["MCP_OUTPUT_DIR"] == str(Path("~/diagrams").expanduser())
    assert loaded.source_of("KROKI_SERVER", {"KROKI_SERVER": "x"}) == "env"
    assert loaded.source_of("MCP_URL_ONLY", {}).startswith("file:")
    assert loaded.source_of("MCP_READ_ONLY", {}) == "default"


def test_apply_to_environ_skips_nulls_and_unmapped_keys():
    env: dict[str, str] = {}
    applied = apply_to_environ({"rendering": {"url_only": None, "unknown": 1}}, env)
    assert applied == {} and env == {}


def test_load_without_apply_leaves_env_untouched(isolated):
    path = write(isolated / "x.yaml", "rendering:\n  memory_only: true\n")
    env: dict[str, str] = {}
    loaded = load_config(str(path), env, apply_env=False)
    assert env == {} and loaded.applied_env == {}
    assert loaded.app.rendering == {"memory_only": True}


def test_get_config_is_cached_and_resettable(isolated, monkeypatch):
    write(isolated / "uml-mcp.yaml", "audit:\n  enabled: true\n")
    monkeypatch.delenv("UML_MCP_CONFIG", raising=False)
    reset_config_cache()
    assert get_config() is get_config()
    assert get_config().app.audit.enabled is True
    monkeypatch.setenv("UML_MCP_CONFIG", "none")
    reset_config_cache()
    assert get_config().path is None and get_config().app == AppConfig()


# ------------------------------------------------------------------ templates
@pytest.mark.parametrize("profile", commands.PROFILES)
def test_shipped_profiles_are_valid(profile, isolated):
    path = write(isolated / f"{profile}.yaml", commands._template(profile))
    loaded = load_config(str(path), {}, apply_env=False)
    assert loaded.data["version"] == 1
    if profile == "enterprise":
        assert loaded.app.audit.enabled and loaded.app.rate_limit.enabled
        assert loaded.data["auth"]["mode"] == "jwt"


# --------------------------------------------------------------- tool gating
def _register(app_config: AppConfig, monkeypatch) -> list[str]:
    from mcp_core.tools import tool_decorator

    monkeypatch.setattr(
        "mcp_core.core.settings_file.get_app_config", lambda: app_config
    )
    server = MagicMock()
    server.tool.return_value = lambda f: f
    return tool_decorator.register_tools_with_server(server)


def test_disabled_tools_are_not_registered(monkeypatch):
    names = _register(
        parse_app_config({"tools": {"disabled": ["generate_uml_batch"]}}), monkeypatch
    )
    assert "generate_uml_batch" not in names and "generate_uml" in names
    only = _register(
        parse_app_config({"tools": {"enabled": ["validate_uml"]}}), monkeypatch
    )
    assert only == ["validate_uml"]


# ---------------------------------------------------------------- auth parity
def test_yaml_auth_section_matches_json(tmp_path):
    from mcp_core.auth.settings import load_auth_settings

    section = {
        "resource_url": "https://mcp.contoso.com/mcp",
        "entra": {
            "tenant_id": "11111111-2222-3333-4444-555555555555",
            "client_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        },
    }
    from_yaml = load_auth_settings({"MCP_AUTH_MODE": "jwt"}, file_data=section)
    json_file = tmp_path / "auth.json"
    json_file.write_text(json.dumps(section), encoding="utf-8")
    from_json = load_auth_settings(
        {"MCP_AUTH_MODE": "jwt", "MCP_AUTH_CONFIG_FILE": str(json_file)}
    )
    assert from_yaml.redacted_dict() == from_json.redacted_dict()


@pytest.mark.parametrize("secret", ["client_secret", "public_key_pem"])
def test_yaml_auth_secrets_rejected(secret):
    from mcp_core.auth import AuthConfigError
    from mcp_core.auth.settings import load_auth_settings

    with pytest.raises(AuthConfigError, match="secrets must not be stored"):
        load_auth_settings({"MCP_AUTH_MODE": "jwt"}, file_data={secret: "x"})


def test_auth_mode_read_from_yaml(isolated, monkeypatch):
    from mcp_core.auth import auth_mode_from_env

    write(isolated / "uml-mcp.yaml", "auth:\n  mode: jwt\n")
    monkeypatch.delenv("MCP_AUTH_MODE", raising=False)
    monkeypatch.delenv("MCP_AUTH_CONFIG_FILE", raising=False)
    reset_config_cache()
    assert auth_mode_from_env() == "jwt"
    assert auth_mode_from_env({}) == "none"  # explicit environ ignores the file


# ------------------------------------------------------------------------ CLI
def test_cli_init_validate_path_show(isolated, capsys, monkeypatch):
    target = isolated / "cfg" / "uml-mcp.yaml"
    assert (
        commands.main(["config", "init", "--profile", "local", "--path", str(target)])
        == 0
    )
    assert target.is_file()
    assert commands.main(["config", "init", "--path", str(target)]) == 1  # no overwrite
    assert commands.main(["config", "init", "--path", str(target), "--force"]) == 0
    assert commands.main(["config", "validate", "--config", str(target)]) == 0
    assert "OK:" in capsys.readouterr().out
    assert commands.main(["config", "path", "--config", str(target)]) == 0
    assert str(target) in capsys.readouterr().out
    assert commands.main(["config", "path", "--config", "missing.yaml"]) == 1
    monkeypatch.setattr("os.environ", dict(__import__("os").environ))
    assert commands.main(["config", "show", "--config", str(target), "--sources"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["config_file"] == str(target) and shown["auth"] == {"mode": "none"}
    assert shown["env_mapped"]["MCP_OUTPUT_DIR"]["yaml"] == "rendering.output_dir"


def test_cli_init_default_path_uses_xdg(isolated):
    assert commands.main(["config", "init"]) == 0
    assert (isolated / "xdg" / "uml-mcp" / "config.yaml").is_file()


def test_cli_validate_reports_errors(isolated, capsys):
    bad = write(isolated / "bad.yaml", "audit:\n  include_inputs: everything\n")
    assert commands.main(["config", "validate", "--config", str(bad)]) == 1
    assert "INVALID" in capsys.readouterr().err
    bad_auth = write(isolated / "auth.yaml", "auth:\n  mode: jwt\n  client_secret: x\n")
    assert commands.main(["config", "validate", "--config", str(bad_auth)]) == 1


def test_run_dispatches_subcommands(monkeypatch, isolated):
    from mcp_core.core import cli

    monkeypatch.setattr(
        "sys.argv", ["uml-mcp", "config", "path", "--config", "missing"]
    )
    with pytest.raises(SystemExit) as exc:
        cli.run()
    assert exc.value.code == 1
