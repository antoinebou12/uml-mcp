"""Serve the bundled diagram workflow through the MCP Skills extension.

Keep a byte snapshot for both the manifest and reads so newline conversion or
on-disk edits cannot make the advertised digest disagree with served content.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
from typing import Any

import yaml
from fastmcp.server.extensions import MethodBinding, ServerExtension
from mcp.shared.exceptions import MCPError
from mcp.types import RequestParams
from pydantic import StrictStr

SKILL_URI = "skill://uml-mcp-diagrams/SKILL.md"


class ListSkillsParams(RequestParams):
    cursor: StrictStr | None = None


class GetSkillParams(RequestParams):
    uri: StrictStr


class DiagramSkillsExtension(ServerExtension):
    """Metadata discovery for the single bundled, immutable diagram skill."""

    identifier = "io.modelcontextprotocol/skills"

    def __init__(self, cache_scope: str) -> None:
        self.cache_scope = cache_scope
        self.content = (
            files("mcp_core")
            .joinpath("skills", "uml-mcp-diagrams", "SKILL.md")
            .read_bytes()
        )
        self.text = self.content.decode("utf-8")
        lines = self.text.splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            raise ValueError("Bundled diagram skill must begin with YAML frontmatter")
        end = lines.index("---", 1)
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
        if (
            not isinstance(frontmatter, dict)
            or frontmatter.get("name") != "uml-mcp-diagrams"
            or not isinstance(frontmatter.get("description"), str)
            or not frontmatter["description"].strip()
        ):
            raise ValueError("Invalid bundled diagram skill frontmatter")
        self.entry = {
            "uri": SKILL_URI,
            "frontmatter": frontmatter,
            "resources": [
                {
                    "uri": SKILL_URI,
                    "digest": f"sha256:{sha256(self.content).hexdigest()}",
                    "size": len(self.content),
                }
            ],
        }

    def methods(self) -> list[MethodBinding]:
        return [
            MethodBinding("skills/list", ListSkillsParams, self.list_skills),
            MethodBinding("skills/get", GetSkillParams, self.get_skill),
        ]

    def _result(self, **payload: Any) -> dict[str, Any]:
        return {
            "resultType": "complete",
            **payload,
            "ttlMs": 300_000,
            "cacheScope": self.cache_scope,
        }

    async def list_skills(self, ctx: Any, params: ListSkillsParams) -> dict[str, Any]:
        # One atomic entry fits on one page; no cursors are issued.
        if params.cursor is not None:
            raise MCPError(code=-32602, message="Invalid skills cursor")
        return self._result(skills=[deepcopy(self.entry)])

    async def get_skill(self, ctx: Any, params: GetSkillParams) -> dict[str, Any]:
        if params.uri != SKILL_URI:
            raise MCPError(code=-32602, message="Unknown skill URI")
        return self._result(skill=deepcopy(self.entry))


def register_diagram_skills(server: Any, *, cache_scope: str) -> list[str]:
    """Register resources for all clients and extension methods for real FastMCP."""
    extension = DiagramSkillsExtension(cache_scope)

    def read_skill() -> str:
        return extension.text

    server.resource(
        SKILL_URI,
        description="Diagram workflow instructions for UML-MCP.",
        mime_type="text/markdown",
    )(read_skill)
    if callable(getattr(server, "add_extension", None)):
        server.add_extension(extension)
    return [SKILL_URI]
