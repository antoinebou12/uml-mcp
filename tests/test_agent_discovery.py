"""Unit tests for mcp_core.core.agent_discovery builders."""

import hashlib

from mcp_core.core.agent_discovery import (
    AGENT_SKILLS_SCHEMA,
    DOCUMENTATION_SITE_URL,
    PUBLIC_DEPLOYMENT_URL,
    build_agent_skills_index,
    build_api_catalog,
    build_oauth_protected_resource,
    build_robots_txt,
    build_sitemap_xml,
    homepage_markdown,
    link_header_values,
    negotiate_root_format,
    normalize_base_url,
)


def test_normalize_base_url():
    assert normalize_base_url("https://x.com/") == "https://x.com"


def test_build_robots_txt_open_policy():
    txt = build_robots_txt("https://uml-mcp.vercel.app/")
    assert "User-agent: *" in txt
    assert "User-agent: GPTBot" in txt
    assert "Content-Signal: ai-train=yes, search=yes, ai-input=yes" in txt
    assert "Sitemap: https://uml-mcp.vercel.app/sitemap.xml" in txt
    assert "Allow: /" in txt


def test_build_sitemap_xml():
    xml = build_sitemap_xml("https://example.com")
    assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in xml
    assert "<urlset" in xml
    assert "https://example.com/openapi.json" in xml
    assert "https://example.com/status" in xml
    assert "https://example.com/.well-known/api-catalog" in xml


def test_build_api_catalog():
    data = build_api_catalog("https://api.example/")
    assert "linkset" in data
    assert len(data["linkset"]) == 1
    entry = data["linkset"][0]
    assert entry["anchor"] == "https://api.example/"
    assert entry["service-desc"][0]["href"].endswith("/openapi.json")


def test_build_oauth_protected_resource():
    data = build_oauth_protected_resource("https://x/")
    assert data["resource"] == "https://x/"
    assert data["authorization_servers"] == []
    assert data["scopes_supported"] == []


def test_link_header_values_contains_relations():
    h = link_header_values("https://ignored/")
    assert 'rel="api-catalog"' in h
    assert 'rel="service-desc"' in h
    assert 'rel="sitemap"' in h
    assert 'rel="describedby"' in h
    assert 'rel="agent-skills"' in h


def test_negotiate_root_format():
    assert negotiate_root_format(None) == "json"
    assert negotiate_root_format("") == "json"
    assert negotiate_root_format("text/markdown") == "markdown"
    assert negotiate_root_format("text/html, application/json;q=0.9") == "html"
    assert negotiate_root_format("application/json") == "json"
    assert negotiate_root_format("*/*") == "json"
    # JSON listed first but same q as HTML — browsers / proxies; prefer HTML
    assert negotiate_root_format("application/json, text/html") == "html"
    assert negotiate_root_format("application/json;q=1, text/html;q=0.9") == "json"


def test_homepage_markdown_non_empty():
    md = homepage_markdown()
    assert "# UML" in md or "UML" in md
    assert "/openapi.json" in md
    assert "/status" in md
    assert DOCUMENTATION_SITE_URL in md
    assert PUBLIC_DEPLOYMENT_URL in md


def test_build_agent_skills_index_tmp(tmp_path):
    skill_dir = tmp_path / ".skill" / "skills" / "demo_skill"
    skill_dir.mkdir(parents=True)
    body = b"# Title\n\nFirst line desc.\n"
    (skill_dir / "SKILL.md").write_bytes(body)
    idx = build_agent_skills_index(tmp_path, github_repo="owner/repo", branch="main")
    assert idx["$schema"] == AGENT_SKILLS_SCHEMA
    assert len(idx["skills"]) == 1
    sk = idx["skills"][0]
    assert sk["name"] == "demo_skill"
    assert sk["type"] == "context"
    assert sk["description"] == "First line desc."
    assert sk["sha256"] == hashlib.sha256(body).hexdigest()
    assert sk["url"].endswith("/.skill/skills/demo_skill/SKILL.md")
    assert "raw.githubusercontent.com/owner/repo/main/" in sk["url"]
