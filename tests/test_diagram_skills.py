"""Skills extension discovery, byte integrity, errors and installed assets."""

from hashlib import sha256
from pathlib import Path

import pytest
import yaml
from fastmcp import Client, FastMCP
from mcp.shared.exceptions import MCPError
from mcp.types import Request, RequestParams
from pydantic import ConfigDict, TypeAdapter

from mcp_core.auth.policy import READ_METHODS
from mcp_core.resources import diagram_skills
from mcp_core.resources.diagram_skills import (
    SKILL_ROOT_URI,
    SKILL_URI,
    DiagramSkillsExtension,
    GetSkillParams,
    ListSkillsParams,
    ReadResourceDirectoryParams,
    register_diagram_skills,
)


class WireParams(RequestParams):
    model_config = ConfigDict(extra="allow")


def test_packaged_skill_matches_canonical_bytes():
    root = Path(__file__).resolve().parents[1]
    canonical = root / ".skill/skills/uml-mcp-diagrams/SKILL.md"
    extension = DiagramSkillsExtension("public")
    assert extension.content == canonical.read_bytes()
    assert {"skills/list", "skills/get"} <= READ_METHODS


@pytest.mark.parametrize("scope", ["public", "private"])
async def test_discovery_and_read_over_real_mcp(scope):
    server = FastMCP("diagram-skills-test", cache_ttl=300, cache_scope=scope)
    register_diagram_skills(server, cache_scope=scope)
    async with Client(server, timeout=10) as client:
        discovery = await client.session.send_discover("2026-07-28")
        assert discovery["capabilities"]["extensions"][
            "io.modelcontextprotocol/skills"
        ] == {"directoryRead": True}
        assert "resources" in discovery["capabilities"]

        async def request(method, params):
            return await client.session.send_request(
                Request[WireParams, str](method=method, params=WireParams(**params)),
                TypeAdapter(dict),
            )

        direct = await request("skills/get", {"uri": SKILL_URI})
        listing = await request("skills/list", {})
        assert listing["skills"] == [direct["skill"]]
        assert listing["resultType"] == direct["resultType"] == "complete"
        assert listing["ttlMs"] == direct["ttlMs"] == 300_000
        assert listing["cacheScope"] == direct["cacheScope"] == scope
        assert "nextCursor" not in listing

        resources = await client.list_resources()
        assert SKILL_URI in {str(resource.uri) for resource in resources}
        read_result = await request("resources/read", {"uri": SKILL_URI})
        assert read_result["resultType"] == "complete"
        assert read_result["ttlMs"] == 300_000
        assert read_result["cacheScope"] == scope
        content = (await client.read_resource(SKILL_URI))[0]
        assert content.mime_type == "text/markdown"
        raw = content.text.encode("utf-8")
        manifest = direct["skill"]["resources"]
        assert manifest == [
            {
                "uri": SKILL_URI,
                "size": len(raw),
                "digest": f"sha256:{sha256(raw).hexdigest()}",
            }
        ]
        assert direct["skill"]["frontmatter"] == yaml.safe_load(
            content.text.split("---", 2)[1]
        )

        for method, params in [
            ("skills/get", {"uri": "skill://unknown/SKILL.md"}),
            ("skills/get", {"uri": "skill://uml-mcp-diagrams/../SOUL.md"}),
            ("skills/get", {}),
            ("skills/list", {"cursor": "invalid"}),
            ("resources/read", {"uri": "skill://uml-mcp-diagrams/../SOUL.md"}),
            ("resources/read", {"uri": "skill://uml-mcp-diagrams/missing.md"}),
        ]:
            with pytest.raises(MCPError) as error:
                await request(method, params)
            assert error.value.code == -32602


async def test_get_does_not_depend_on_listing_and_metadata_is_not_mutable():
    extension = DiagramSkillsExtension("private")
    first = await extension.get_skill(None, GetSkillParams(uri=SKILL_URI))
    first["skill"]["frontmatter"]["description"] = "changed by caller"
    listing = await extension.list_skills(None, ListSkillsParams())
    assert listing["skills"][0]["frontmatter"]["description"] != "changed by caller"


async def test_directory_read_lists_skill_md():
    extension = DiagramSkillsExtension("public")
    listing = await extension.read_directory(
        None, ReadResourceDirectoryParams(uri=SKILL_ROOT_URI)
    )
    assert listing["resultType"] == "complete"
    assert listing["resources"] == [
        {
            "uri": SKILL_URI,
            "name": "SKILL.md",
            "mimeType": "text/markdown",
            "description": "Diagram workflow instructions for UML-MCP.",
        }
    ]
    with pytest.raises(MCPError) as error:
        await extension.read_directory(None, ReadResourceDirectoryParams(uri=SKILL_URI))
    assert error.value.code == -32602


async def test_smoke_contract_skill_names_batch_workflow():
    """Offline smoke expects skills/list + skill body to mention generate_uml_batch."""
    server = FastMCP("diagram-skills-smoke", cache_ttl=300, cache_scope="public")
    register_diagram_skills(server, cache_scope="public")
    async with Client(server, timeout=10) as client:
        listing = await client.session.send_request(
            Request[WireParams, str](method="skills/list", params=WireParams()),
            TypeAdapter(dict),
        )
        frontmatter = listing["skills"][0]["frontmatter"]
        assert frontmatter["name"] == "uml-mcp-diagrams"
        text = (await client.read_resource(SKILL_URI))[0].text
        assert "generate_uml_batch" in text
        assert "uml-mcp-diagrams" in text


@pytest.mark.parametrize(
    "content",
    [
        "# Missing frontmatter\n",
        "---\nname: uml-mcp-diagrams\n",
        "---\nname: other\ndescription: test\n---\n",
        "---\nname: uml-mcp-diagrams\ndescription: ''\n---\n",
        "---\n- not-a-mapping\n---\n",
    ],
)
def test_invalid_bundled_skill_fails_at_startup(tmp_path, monkeypatch, content):
    asset = tmp_path / "skills/uml-mcp-diagrams/SKILL.md"
    asset.parent.mkdir(parents=True)
    asset.write_text(content, encoding="utf-8")
    monkeypatch.setattr(diagram_skills, "files", lambda package: tmp_path)
    with pytest.raises(ValueError, match="[Bb]undled diagram skill"):
        DiagramSkillsExtension("public")


@pytest.mark.parametrize("topic", diagram_skills.GUIDE_TOPICS)
async def test_focused_guides_are_readable_and_mirrored(topic):
    server = FastMCP("diagram-guides")
    register_diagram_skills(server, cache_scope="public")
    async with Client(server) as client:
        text = (await client.read_resource(f"skill://uml-mcp-guides/{topic}/SKILL.md"))[
            0
        ].text
        root = Path(__file__).resolve().parents[1]
        name = f"uml-mcp-{topic}"
        for base in (
            ".skill/skills",
            ".github/skills",
            "mcp_core/skills",
            "plugins/uml-mcp/skills",
        ):
            assert (root / base / name / "SKILL.md").read_text(encoding="utf-8") == text
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        assert frontmatter["name"] == name
        assert frontmatter["description"]
        assert "skill://uml-mcp-diagrams/SKILL.md" in text
        with pytest.raises(MCPError):
            await client.read_resource("skill://uml-mcp-guides/unknown/SKILL.md")
