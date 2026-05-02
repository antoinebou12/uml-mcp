"""
Pure builders for agent discovery: robots.txt, sitemap, API catalog (RFC 9727),
OAuth protected resource metadata (RFC 9728), homepage HTML/Markdown, Link headers.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape

# Default GitHub raw URLs for skills (plan: raw.githubusercontent.com/.../main/.skill/skills/...)
DEFAULT_GITHUB_REPO = "antoinebou12/uml-mcp"
DEFAULT_GITHUB_BRANCH = "main"
AGENT_SKILLS_SCHEMA = (
    "https://agentskills.io/schemas/agent-skills-index-v0.2.0.json"
)

_AI_USER_AGENTS = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-Web",
    "ClaudeBot",
    "anthropic-ai",
    "Google-Extended",
    "PerplexityBot",
    "Applebot-Extended",
    "cohere-ai",
    "CCBot",
)


def normalize_base_url(base: str) -> str:
    """Strip trailing slashes for canonical URL construction."""
    return base.rstrip("/")


def build_robots_txt(base_url: str) -> str:
    """RFC 9309 robots.txt with AI bots, Content-Signal, and Sitemap (open policy)."""
    base = normalize_base_url(base_url)
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
    ]
    for ua in _AI_USER_AGENTS:
        lines.append(f"User-agent: {ua}")
    lines.append("Allow: /")
    lines.append("")
    lines.append("Content-Signal: ai-train=yes, search=yes, ai-input=yes")
    lines.append("")
    lines.append(f"Sitemap: {base}/sitemap.xml")
    lines.append("")
    return "\n".join(lines)


def build_sitemap_xml(base_url: str) -> str:
    """Sitemap listing canonical API and discovery URLs."""
    base = normalize_base_url(base_url)
    paths = (
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/openapi.yaml",
        "/health",
        "/supported_formats",
        "/.well-known/mcp/server-card.json",
        "/.well-known/ai-plugin.json",
        "/.well-known/api-catalog",
        "/.well-known/oauth-protected-resource",
        "/.well-known/agent-skills/index.json",
        "/.well-known/privacy.txt",
    )
    urls_xml = []
    for p in paths:
        loc = base + (p if p.startswith("/") else "/" + p)
        urls_xml.append(
            f"    <url>\n        <loc>{escape(loc)}</loc>\n    </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls_xml)
        + "\n</urlset>\n"
    )


def build_api_catalog(base_url: str) -> dict[str, Any]:
    """RFC 9727 linkset JSON for /.well-known/api-catalog."""
    base = normalize_base_url(base_url)
    return {
        "linkset": [
            {
                "anchor": f"{base}/",
                "service-desc": [
                    {
                        "href": f"{base}/openapi.json",
                        "type": "application/json",
                    }
                ],
                "service-doc": [
                    {"href": f"{base}/docs", "type": "text/html"},
                ],
                "status": [
                    {
                        "href": f"{base}/health",
                        "type": "application/json",
                    }
                ],
                "describedby": [
                    {
                        "href": f"{base}/.well-known/mcp/server-card.json",
                        "type": "application/json",
                    }
                ],
            }
        ]
    }


def build_oauth_protected_resource(base_url: str) -> dict[str, Any]:
    """RFC 9728: public API — no authorization servers."""
    base = normalize_base_url(base_url)
    return {
        "resource": f"{base}/",
        "authorization_servers": [],
        "scopes_supported": [],
        "bearer_methods_supported": [],
        "resource_documentation": f"{base}/docs",
    }


def _first_skill_description(skill_md: str) -> str:
    lines = skill_md.splitlines()
    i = 0
    # Skip YAML frontmatter delimited by --- ... ---
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        if i < len(lines) and lines[i].strip() == "---":
            i += 1
    while i < len(lines):
        stripped = lines[i].strip()
        i += 1
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        return stripped[:500]
    return "Agent skill"


def build_agent_skills_index(
    repo_root: str | Path,
    *,
    github_repo: str = DEFAULT_GITHUB_REPO,
    branch: str = DEFAULT_GITHUB_BRANCH,
) -> dict[str, Any]:
    """
    Agent Skills Discovery v0.2.0 index; URLs point at GitHub raw SKILL.md files.
    """
    root = Path(repo_root)
    skills_dir = root / ".skill" / "skills"
    skills: list[dict[str, Any]] = []
    if skills_dir.is_dir():
        for sub in sorted(skills_dir.iterdir()):
            if not sub.is_dir():
                continue
            skill_file = sub / "SKILL.md"
            if not skill_file.is_file():
                continue
            raw = skill_file.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8", errors="replace")
            name = sub.name
            desc = _first_skill_description(text)
            # Path in repo for raw URL
            path_in_repo = f".skill/skills/{name}/SKILL.md"
            url = (
                f"https://raw.githubusercontent.com/{github_repo}/"
                f"{branch}/{path_in_repo}"
            )
            skills.append(
                {
                    "name": name,
                    "type": "context",
                    "description": desc,
                    "url": url,
                    "sha256": digest,
                }
            )
    return {
        "$schema": AGENT_SKILLS_SCHEMA,
        "skills": skills,
    }


def link_header_values(_base_url: str) -> str:
    """Single RFC 8288 Link header value (comma-separated relations).

    Paths are origin-relative (``</path>``); ``_base_url`` is kept for callers
    that pass the request origin for API symmetry.
    """
    parts = [
        '</.well-known/api-catalog>; rel="api-catalog"',
        '</openapi.json>; rel="service-desc"; type="application/json"',
        '</docs>; rel="service-doc"; type="text/html"',
        '</sitemap.xml>; rel="sitemap"; type="application/xml"',
        (
            '</.well-known/mcp/server-card.json>; rel="describedby"; '
            'type="application/json"'
        ),
        (
            '</.well-known/agent-skills/index.json>; rel="agent-skills"; '
            'type="application/json"'
        ),
    ]
    return ", ".join(parts)


def homepage_markdown() -> str:
    """Markdown summary for Accept: text/markdown."""
    return """# UML Diagram Generator (UML-MCP)

REST API and **Model Context Protocol (MCP)** service for generating UML and other diagrams (PlantUML, Mermaid, D2, Kroki).

## Quick links

| Resource | Path |
|----------|------|
| OpenAPI (JSON) | `/openapi.json` |
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |
| Health | `/health` |
| MCP (Streamable HTTP) | `/mcp` |
| Kroki URL encode (no disk) | `POST /kroki_encode` |
| Generate diagram | `POST /generate_diagram` |
| MCP server card | `/.well-known/mcp/server-card.json` |
| API catalog (RFC 9727) | `/.well-known/api-catalog` |
| Agent skills index | `/.well-known/agent-skills/index.json` |

## Version

1.3.0 — status: operational.

Use an MCP client to connect to `/mcp` or call the REST endpoints above.
"""


def homepage_html() -> str:
    """Minimal HTML landing page with WebMCP tool registration."""
    # Inline script: WebMCP / model context — register site tools for capable browsers.
    script = """
(function () {
  if (typeof navigator === "undefined" || !navigator.modelContext) return;
  var provide = navigator.modelContext.provideContext;
  if (typeof provide !== "function") return;
  provide({
    tools: [
      {
        name: "generate_uml_url",
        description: "Return a Kroki render URL for a diagram (POST /kroki_encode).",
        inputSchema: {
          type: "object",
          properties: {
            type: { type: "string", description: "Diagram type (e.g. class, mermaid, d2)" },
            code: { type: "string", description: "Diagram source" },
            output_format: { type: "string", default: "svg" }
          },
          required: ["type", "code"]
        },
        execute: async function (args) {
          var r = await fetch("/kroki_encode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              type: args.type,
              code: args.code,
              output_format: args.output_format || "svg"
            })
          });
          var data = await r.json();
          if (!r.ok) throw new Error(data.detail || r.statusText);
          return data;
        }
      },
      {
        name: "list_diagram_types",
        description: "List supported diagram types and output formats (GET /supported_formats).",
        inputSchema: { type: "object", properties: {} },
        execute: async function () {
          var r = await fetch("/supported_formats");
          if (!r.ok) throw new Error(r.statusText);
          return r.json();
        }
      }
    ]
  });
})();
"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>UML Diagram Generator</title>
</head>
<body>
  <main>
    <h1>UML Diagram Generator</h1>
    <p>REST API and MCP for UML and diagram generation. Open <a href="/docs">Swagger UI</a> or <a href="/redoc">ReDoc</a>.</p>
    <ul>
      <li><a href="/openapi.json">OpenAPI JSON</a></li>
      <li><a href="/health">Health</a></li>
      <li><a href="/.well-known/mcp/server-card.json">MCP server card</a></li>
    </ul>
  </main>
  <script>
{script}
  </script>
</body>
</html>
"""


def _parse_accept(accept: str) -> list[tuple[str, float, int]]:
    """Return (media_type, q, position) sorted by q desc, then position asc."""
    if not accept or not accept.strip():
        return []
    entries: list[tuple[str, float, int]] = []
    for pos, part in enumerate(accept.split(",")):
        part = part.strip()
        if not part:
            continue
        if ";" in part:
            media, rest = part.split(";", 1)
            media = media.strip()
            q = 1.0
            m = re.search(r"q\s*=\s*([0-9.]+)", rest, re.I)
            if m:
                try:
                    q = float(m.group(1))
                except ValueError:
                    q = 1.0
        else:
            media = part.strip()
            q = 1.0
        entries.append((media.lower(), q, pos))
    entries.sort(key=lambda x: (-x[1], x[2]))
    return entries


def negotiate_root_format(accept_header: str | None) -> Literal["json", "html", "markdown"]:
    """
    Choose response type for GET /.
    Default JSON; text/markdown and text/html when explicitly negotiated with q > 0.
    */* does not force HTML — defaults to json for API clients sending */* only.
    """
    if not accept_header:
        return "json"
    parsed = _parse_accept(accept_header)
    if not parsed:
        return "json"
    # Walk in quality order; first concrete match wins
    for media, q, _ in parsed:
        if q <= 0:
            continue
        if media == "text/markdown":
            return "markdown"
        if media == "text/html":
            return "html"
        if media == "application/json":
            return "json"
    # */* or unknown — default json
    return "json"


def approximate_markdown_token_count(text: str) -> int:
    """Rough token count for x-markdown-tokens header (whitespace-split)."""
    return len(text.split())
