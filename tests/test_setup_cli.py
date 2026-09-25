"""`uml-mcp setup` wizard (Typer + tqdm), the feature catalog and scripts/install.py."""

from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from mcp_core.cli.app import app, main, write_config_file
from mcp_core.core import features
from mcp_core.core.settings_file import parse_app_config, read_config_file

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_catalog_is_documented_and_profiles_have_defaults():
    keys = {f.key for f in features.FEATURES}
    assert len(keys) == len(features.FEATURES)
    for f in features.FEATURES:
        assert len(f.description) > 40 and f.apply in ("live", "restart")
        assert f.as_dict()["key"] == f.key
    assert "local_dashboard" in features.default_features("local")
    assert {"audit", "rate_limit"} <= features.default_features("enterprise")
    with pytest.raises(ValueError):
        features.default_features("cloud")
    with pytest.raises(KeyError):
        features.get_feature("nope")


@pytest.mark.parametrize("profile", features.PROFILES)
def test_build_config_is_valid_and_round_trips(profile):
    data = features.build_config(profile)
    parse_app_config(data)
    assert features.enabled_features(data) == features.default_features(profile)
    toggled = features.build_config(profile, {"otel"})
    assert features.enabled_features(toggled) == {"otel"}
    with pytest.raises(KeyError):
        features.build_config(profile, {"bogus"})


def test_setup_non_interactive_writes_valid_yaml(tmp_path):
    target = tmp_path / "cfg" / "uml-mcp.yaml"
    res = runner.invoke(
        app,
        [
            "setup",
            "--profile",
            "docker",
            "--enable",
            "otel",
            "--disable",
            "rate_limit",
            "--kroki-server",
            "http://kroki:8000",
            "--path",
            str(target),
            "--yes",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "UML-MCP is configured" in res.output and "Health check" in res.output
    data = read_config_file(target)
    app_config = parse_app_config(data)
    assert app_config.otel.enabled and not app_config.rate_limit.enabled
    assert data["rendering"]["kroki_server"] == "http://kroki:8000"
    assert data["setup"]["profile"] == "docker" and "otel" in data["setup"]["features"]
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    # second run needs --force; with it a backup is kept
    assert runner.invoke(app, ["setup", "--path", str(target), "--yes"]).exit_code == 1
    assert (
        runner.invoke(
            app, ["setup", "--path", str(target), "--yes", "--force"]
        ).exit_code
        == 0
    )
    assert list(target.parent.glob("uml-mcp.yaml.bak-*"))


def test_setup_dry_run_and_bad_input(tmp_path):
    res = runner.invoke(app, ["setup", "--profile", "enterprise", "--dry-run", "--yes"])
    assert res.exit_code == 0 and "rate_limit:" in res.output
    assert runner.invoke(app, ["setup", "--profile", "cloud", "--yes"]).exit_code != 0
    assert (
        runner.invoke(
            app, ["setup", "--enable", "warp", "--yes", "--dry-run"]
        ).exit_code
        != 0
    )
    bad_client = [
        "setup",
        "--client",
        "emacs",
        "--yes",
        "--path",
        str(tmp_path / "x.yaml"),
    ]
    assert runner.invoke(app, bad_client).exit_code != 0


def test_setup_registers_clients(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "mcp_core.core.client_install.install",
        lambda name: (calls.append(name) or "{}", tmp_path / f"{name}.json"),
    )
    res = runner.invoke(
        app,
        ["setup", "--client", "cursor", "--path", str(tmp_path / "u.yaml"), "--yes"],
    )
    assert res.exit_code == 0, res.output
    assert calls == ["cursor"] and "cursor:" in res.output


def test_interactive_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr("mcp_core.cli.app.is_interactive", lambda: True)
    answers = (
        "local\n"
        + "\n" * len(features.FEATURES)
        + "https://kroki.example\n"
        + "n\n" * 4
    )
    res = runner.invoke(
        app, ["setup", "--path", str(tmp_path / "i.yaml")], input=answers
    )
    assert res.exit_code == 0, res.output
    assert "Features (Enter keeps" in res.output
    assert read_config_file(tmp_path / "i.yaml")["rendering"]["kroki_server"] == (
        "https://kroki.example"
    )


def test_invalid_config_step_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "mcp_core.cli.app.health_check",
        lambda: (_ for _ in ()).throw(RuntimeError("renderer down")),
    )
    res = runner.invoke(app, ["setup", "--path", str(tmp_path / "h.yaml"), "--yes"])
    assert res.exit_code == 1 and "renderer down" in res.output


def test_main_dispatch_and_write_helper(tmp_path, capsys):
    assert main(["setup", "--dry-run", "--yes"]) == 0
    assert main(["setup", "--profile", "nope", "--yes"]) == 2
    with pytest.raises(FileExistsError):
        path = tmp_path / "w.yaml"
        path.write_text("version: 1\n")
        write_config_file(path, {"version": 1}, force=False)
    assert yaml.safe_load((tmp_path / "w.yaml").read_text()) == {
        "version": 1
    }  # untouched


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "installer", ROOT / "scripts/install.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installer_plans_the_right_commands():
    inst = _load_installer()
    assert inst.detect_method(lambda n: "/bin/uv" if n == "uv" else None) == "uv"
    assert inst.detect_method(lambda n: "/bin/pipx" if n == "pipx" else None) == "pipx"
    assert inst.detect_method(lambda n: None) == "pip"
    assert inst.install_command("uv", "1.4.0", "otel") == [
        "uv",
        "tool",
        "install",
        "--force",
        "uml-mcp[otel]==1.4.0",
    ]
    assert inst.plan("pipx", None, None, True, True)[-1] == [
        "uml-mcp",
        "setup",
        "--web",
    ]
    res = CliRunner().invoke(inst.cli, ["--method", "pip", "--dry-run"])
    assert res.exit_code == 0 and "pip install --user" in res.output
    assert "uml-mcp setup" in res.output
