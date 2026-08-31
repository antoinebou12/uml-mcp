"""Contract tests for oi-manifest.json.

The manifest is consumed by an external agent runtime, so the failure mode is
silent: a stale tool name or a duplicate keyword routes a user's request into
nothing. These tests pin it to the live tool registry instead.
"""

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "oi-manifest.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registered_tool_names() -> set[str]:
    from mcp_core.tools import diagram_tools  # noqa: F401  (populates the registry)
    from mcp_core.tools.tool_decorator import get_tool_registry

    return set(get_tool_registry())


def test_manifest_is_valid_json_with_the_expected_shape(manifest: dict) -> None:
    assert set(manifest) == {
        "server_name",
        "version",
        "intents",
        "parameter_extractors",
        "reminder_message",
    }
    assert isinstance(manifest["intents"], list)
    assert manifest["intents"]


def test_manifest_targets_this_server(manifest: dict) -> None:
    from mcp_core.core.config import MCPSettings

    assert manifest["server_name"] == MCPSettings().server_name == "uml_mcp"


def test_manifest_version_matches_project_version(manifest: dict) -> None:
    from mcp_core.core.config import MCPSettings

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert manifest["version"] == pyproject["project"]["version"]
    assert manifest["version"] == MCPSettings().version


def test_every_intent_targets_a_registered_tool(
    manifest: dict, registered_tool_names: set[str]
) -> None:
    targeted = {intent["tool_name"] for intent in manifest["intents"]}

    assert targeted <= registered_tool_names
    # Generation, validation, type discovery and batch generation must all be
    # reachable; an unmapped tool is a tool OI OS can never call.
    assert targeted == registered_tool_names


def test_intent_keywords_are_unique(manifest: dict) -> None:
    keywords = [intent["keyword"].strip().lower() for intent in manifest["intents"]]

    assert all(keywords)
    assert len(keywords) == len(set(keywords)), "duplicate keywords route ambiguously"


def test_intent_priorities_are_sane(manifest: dict) -> None:
    for intent in manifest["intents"]:
        priority = intent["priority"]
        assert isinstance(priority, int) and not isinstance(priority, bool)
        assert 1 <= priority <= 10


def test_parameter_extraction_is_left_to_the_mcp_client(manifest: dict) -> None:
    """Deliberately empty.

    The upstream OI OS fork extracted `code` with a rule that deletes the literal
    words "generate", "create", "uml", "diagram" and "plantuml" from the request
    before the tool sees it, which corrupts valid diagram source. Structured
    argument construction stays the client's job.
    """
    assert manifest["parameter_extractors"] == {}


def test_reminder_message_names_the_real_tools(
    manifest: dict, registered_tool_names: set[str]
) -> None:
    reminder = manifest["reminder_message"]

    assert all(name in reminder for name in registered_tool_names)
    assert "@startuml" in reminder
