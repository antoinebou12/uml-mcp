"""
Pure builders for agent discovery: robots.txt, sitemap, API catalog (RFC 9727),
OAuth protected resource metadata (RFC 9728), homepage HTML/Markdown, Link headers.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape

# Default GitHub raw URLs for skills (plan: raw.githubusercontent.com/.../main/.skill/skills/...)
DEFAULT_GITHUB_REPO = "antoinebou12/uml-mcp"
DEFAULT_GITHUB_BRANCH = "main"
# Keep in sync with mkdocs.yml site_url / repo_url
DOCUMENTATION_SITE_URL = "https://antoinebou12.github.io/uml-mcp/"
PUBLIC_DEPLOYMENT_URL = "https://uml-mcp.vercel.app"
GITHUB_REPO_URL = f"https://github.com/{DEFAULT_GITHUB_REPO}"
SMITHERY_LISTING_URL = "https://smithery.ai/server/antoinebou12/uml"
AGENT_SKILLS_SCHEMA = "https://agentskills.io/schemas/agent-skills-index-v0.2.0.json"

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
        "/status",
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
        urls_xml.append(f"    <url>\n        <loc>{escape(loc)}</loc>\n    </url>")
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
    return f"""# UML Diagram Generator (UML-MCP)

REST API and **Model Context Protocol (MCP)** service for generating UML and other diagrams (PlantUML, Mermaid, D2, Kroki).

## About

UML-MCP helps you produce diagrams from natural-language prompts or from diagram source you write yourself (PlantUML, Mermaid, D2, and other [Kroki](https://kroki.io/) backends). Use the hosted [interactive API (Swagger)]({PUBLIC_DEPLOYMENT_URL}/docs), read the [full documentation]({DOCUMENTATION_SITE_URL}), or clone the [GitHub repository]({GITHUB_REPO_URL}).

## Documentation

Full guides and deployment notes: [{DOCUMENTATION_SITE_URL}]({DOCUMENTATION_SITE_URL})

## Quick links

| Resource | Path |
|----------|------|
| OpenAPI (JSON) | `/openapi.json` |
| OpenAPI (YAML) | `/openapi.yaml` |
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |
| Health (JSON) | `/health` |
| Status (HTML) | `/status` |
| MCP (Streamable HTTP) | `/mcp` |
| Kroki URL encode (no disk) | `POST /kroki_encode` |
| Generate diagram | `POST /generate_diagram` |
| Supported formats | `/supported_formats` |
| MCP server card | `/.well-known/mcp/server-card.json` |
| API catalog (RFC 9727) | `/.well-known/api-catalog` |
| Agent skills index | `/.well-known/agent-skills/index.json` |

## Version

1.3.0 — status: operational.

Use an MCP client to connect to `/mcp` or call the REST endpoints above.
"""


def _landing_page_css() -> str:
    """Shared inline styles for HTML landing and status pages."""
    return """
:root {
  color-scheme: light dark;
  --bg: #f0f2f7;
  --fg: #141824;
  --muted: #5a6270;
  --card: #ffffff;
  --border: #d8dce6;
  --accent: #4338ca;
  --accent-hover: #3730a3;
  --link: #2563eb;
  --radius: 12px;
  --shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1117;
    --fg: #e8eaef;
    --muted: #9aa1b0;
    --card: #181b24;
    --border: #2c3140;
    --accent: #a5b4fc;
    --accent-hover: #c7d2fe;
    --link: #93c5fd;
    --shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.55;
  min-height: 100vh;
}
a { color: var(--link); }
a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.wrap {
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem 1.25rem 2.5rem;
}
header {
  margin-bottom: 1.75rem;
}
header h1 {
  font-size: 1.65rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 0.5rem;
}
header p {
  margin: 0;
  color: var(--muted);
  max-width: 42rem;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.9rem;
  text-decoration: none;
  background: var(--accent);
  color: #fff;
  border: none;
}
@media (prefers-color-scheme: dark) {
  .btn { color: var(--fg); }
}
.btn:hover { background: var(--accent-hover); }
.btn-secondary {
  background: var(--card);
  color: var(--fg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}
.btn-secondary:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.1rem 1.2rem;
  box-shadow: var(--shadow);
}
.card h2 {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin: 0 0 0.75rem;
  font-weight: 600;
}
.card ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.card li {
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--border);
}
.card li:last-child { border-bottom: none; }
.card a { font-weight: 500; }
footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
}
.about-card {
  grid-column: 1 / -1;
}
.about-card p {
  margin: 0 0 0.75rem;
  color: var(--muted);
  max-width: 52rem;
}
.about-card p:last-child {
  margin-bottom: 0;
}
"""


def status_html(health: dict[str, Any]) -> str:
    """Human-readable status page HTML (same facts as ``/health``)."""
    payload = html.escape(json.dumps(health, indent=2, sort_keys=True))
    status_val = str(health.get("status", "unknown"))
    modules = health.get("modules_available")
    mod_ok = bool(modules)
    status_label = html.escape(status_val)
    mod_text = "Available" if mod_ok else "Unavailable"
    css = _landing_page_css()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="description" content="UML-MCP service status and health."/>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml"/>
  <title>Service status — UML Diagram Generator</title>
  <style>{css}
.status-pill {{
  display: inline-block;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  background: var(--card);
  border: 1px solid var(--border);
}}
.status-pill.ok {{ color: #15803d; border-color: #86efac; }}
@media (prefers-color-scheme: dark) {{
  .status-pill.ok {{ color: #86efac; border-color: #166534; }}
}}
.status-pill.warn {{ color: #b45309; border-color: #fcd34d; }}
pre.raw {{
  margin: 1rem 0 0;
  padding: 1rem;
  overflow: auto;
  font-size: 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
}}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Service status</h1>
      <p>Live view of the same payload as <a href="/health"><code>/health</code></a> (JSON).</p>
    </header>
    <div class="card">
      <p style="margin:0 0 0.75rem">
        <span class="status-pill ok" aria-label="Overall status">{status_label}</span>
        <span style="margin-left:0.75rem;color:var(--muted)">Diagram modules: <strong>{html.escape(mod_text)}</strong></span>
      </p>
      <pre class="raw" tabindex="0"><code>{payload}</code></pre>
    </div>
    <p style="margin-top:1.25rem"><a href="/">← Back to home</a></p>
  </div>
</body>
</html>
"""


def homepage_html() -> str:
    """HTML landing page with discovery links and WebMCP tool registration."""
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
    css = _landing_page_css()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="description" content="UML-MCP: REST API and MCP for diagram generation via Kroki, PlantUML, Mermaid, and more."/>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml"/>
  <title>UML Diagram Generator</title>
  <style>{css}</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>UML Diagram Generator</h1>
      <p>REST API and <strong>Model Context Protocol (MCP)</strong> for UML and diagram generation — PlantUML, Mermaid, D2, Kroki, and more.</p>
      <div class="actions">
        <a class="btn" href="{DOCUMENTATION_SITE_URL}">Documentation (MkDocs)</a>
        <a class="btn btn-secondary" href="/docs">Swagger UI</a>
        <a class="btn btn-secondary" href="/redoc">ReDoc</a>
        <a class="btn btn-secondary" href="{GITHUB_REPO_URL}">GitHub</a>
        <a class="btn btn-secondary" href="/status">Status</a>
      </div>
    </header>
    <div class="grid">
      <section class="card about-card" aria-labelledby="h-about">
        <h2 id="h-about">About</h2>
        <p>
          <strong>UML-MCP</strong> is a diagram generation service built on the
          <strong>Model Context Protocol (MCP)</strong>. Describe what you need in natural language,
          or send PlantUML, Mermaid, D2, and other sources supported by
          <a href="https://kroki.io/">Kroki</a>.
        </p>
        <p>
          <a href="/docs">Swagger UI</a> (same as
          <a href="{PUBLIC_DEPLOYMENT_URL}/docs">uml-mcp.vercel.app/docs</a>),
          <a href="{DOCUMENTATION_SITE_URL}">full documentation on GitHub Pages</a>,
          and <a href="{GITHUB_REPO_URL}">source &amp; issues on GitHub</a>.
          MCP clients connect to <a href="/mcp"><code>/mcp</code></a> (Streamable HTTP).
        </p>
      </section>
      <section class="card" aria-labelledby="h-api">
        <h2 id="h-api">API reference</h2>
        <ul>
          <li><a href="/docs">Swagger UI</a> — interactive REST</li>
          <li><a href="/redoc">ReDoc</a> — readable spec</li>
          <li><a href="/openapi.json">OpenAPI JSON</a></li>
          <li><a href="/openapi.yaml">OpenAPI YAML</a></li>
        </ul>
      </section>
      <section class="card" aria-labelledby="h-svc">
        <h2 id="h-svc">Service</h2>
        <ul>
          <li><a href="/health"><code>/health</code></a> — JSON health</li>
          <li><a href="/status">Status page</a> — human-readable</li>
          <li><a href="/supported_formats">Supported formats</a></li>
        </ul>
      </section>
      <section class="card" aria-labelledby="h-mcp">
        <h2 id="h-mcp">MCP</h2>
        <ul>
          <li><a href="/mcp"><code>/mcp</code></a> — Streamable HTTP</li>
          <li><a href="/.well-known/mcp/server-card.json">MCP server card</a></li>
          <li><a href="{SMITHERY_LISTING_URL}">Smithery catalog</a> (external)</li>
        </ul>
      </section>
      <section class="card" aria-labelledby="h-docs">
        <h2 id="h-docs">Repository</h2>
        <ul>
          <li><a href="{DOCUMENTATION_SITE_URL}">MkDocs site</a></li>
          <li><a href="{GITHUB_REPO_URL}">GitHub</a> — source &amp; issues</li>
        </ul>
      </section>
    </div>
    <footer>
      Version 1.3.0 · Browsers get HTML for <code>GET /</code>; send <code>Accept: application/json</code> for JSON.
      Public deployment: <a href="{PUBLIC_DEPLOYMENT_URL}">{PUBLIC_DEPLOYMENT_URL}</a>.
    </footer>
  </div>
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
            m = re.search(r"q\s*=\s*([0-9.]+)", rest, re.IGNORECASE)
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


def negotiate_root_format(
    accept_header: str | None,
) -> Literal["json", "html", "markdown"]:
    """
    Choose response type for GET /.

    Picks the highest ``q`` within each family (markdown, HTML, JSON). Markdown
    wins if its ``q`` is greatest. Otherwise HTML wins over JSON when
    ``q_html >= q_json`` so typical browser ``Accept`` lists still return HTML
    even if ``application/json`` appears with equal weight. ``*/*`` alone
    yields JSON for API-style clients.
    """
    if not accept_header or not accept_header.strip():
        return "json"
    parsed = _parse_accept(accept_header)
    if not parsed:
        return "json"

    q_markdown = 0.0
    q_html = 0.0
    q_json = 0.0

    for media, q, _ in parsed:
        if q <= 0:
            continue
        m = media.split(";")[0].strip().lower()
        if m == "text/markdown":
            q_markdown = max(q_markdown, q)
        elif m in ("text/html", "application/xhtml+xml"):
            q_html = max(q_html, q)
        elif m == "application/json":
            q_json = max(q_json, q)

    if q_markdown > 0 and q_markdown >= q_html and q_markdown >= q_json:
        return "markdown"
    if q_html > 0 and q_html >= q_json:
        return "html"
    if q_json > 0:
        return "json"
    return "json"


def approximate_markdown_token_count(text: str) -> int:
    """Rough token count for x-markdown-tokens header (whitespace-split)."""
    return len(text.split())
