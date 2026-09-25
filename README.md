# UML-MCP

[![Run Tests](https://github.com/antoinebou12/uml-mcp/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/test.yml)
[![Build Package](https://github.com/antoinebou12/uml-mcp/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/build.yml)
[![Deploy docs](https://github.com/antoinebou12/uml-mcp/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/docs.yml)
[![Deploy](https://github.com/antoinebou12/uml-mcp/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/deploy.yml)
[![GitHub release](https://img.shields.io/github/v/release/antoinebou12/uml-mcp?include_prereleases)](https://github.com/antoinebou12/uml-mcp/releases)
[![GitHub stars](https://img.shields.io/github/stars/antoinebou12/uml-mcp)](https://github.com/antoinebou12/uml-mcp/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/antoinebou12/uml-mcp)](https://github.com/antoinebou12/uml-mcp/network/members)
[![GitHub issues](https://img.shields.io/github/issues/antoinebou12/uml-mcp)](https://github.com/antoinebou12/uml-mcp/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python >=3.12,<3.15](https://img.shields.io/badge/python-%3E%3D3.12%2C%3C3.15-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Hosted](https://img.shields.io/badge/hosted-Vercel-black)](https://uml-mcp.vercel.app/mcp)
[![MCP status](https://mcpvitals.com/badge/6cfb821be2.svg)](https://mcpvitals.com/status/6cfb821be2)
[![MseeP.ai Security Assessment](https://img.shields.io/badge/MseeP.ai-Security%20Assessment-green)](https://mseep.ai/app/antoinebou12-uml-mcp)
[![Lulu MCPs](https://getlulu.dev/api/mcps/badge/uml-mcp)](https://getlulu.dev/mcps/uml-mcp)
[![smithery badge](https://smithery.ai/badge/antoinebou12/uml)](https://smithery.ai/servers/antoinebou12/uml)

**UML-MCP gives an AI assistant a real diagram tool instead of asking it to fake diagrams in Markdown.** Connect it once over [MCP](https://modelcontextprotocol.io/), then ask for a class diagram, sequence diagram, architecture view, Mermaid flowchart, D2 graph, BPMN process, or another Kroki-backed format. The server validates the source, renders it, and returns a URL, playground link, or inline image.

It also works as a building block for agent-facing products. Use **MCP** when an agent needs diagram tools, **AG-UI** when a frontend needs a standard event stream, and **OpenUI** when the product should turn model output into interactive, application-owned UI components. These layers complement each other; UML-MCP stays focused on diagram generation.

| | |
| --- | --- |
| **Live MCP** | [https://uml-mcp.vercel.app/mcp](https://uml-mcp.vercel.app/mcp) |
| **Docs** | [antoinebou12.github.io/uml-mcp](https://antoinebou12.github.io/uml-mcp/) |
| **Catalog** | ~37 Kroki-backed types · 5 MCP tools · URL + playground + chat PNG |
| **Agent UI** | MCP `/mcp` · canonical AG-UI `/ag-ui` · [OpenUI integration guide](docs/integrations/openui.md) |

<p align="center">
  <img src="docs/assets/diagrams/client-server-chat.png" width="720" alt="UML-MCP in chat: Client/Server Mermaid sequence with URL and Playground links" />
</p>

<p align="center"><sub>Chat reply shape: diagram preview · <b>URL</b> · <b>Playground</b> (mermaid.live)</sub></p>

## Quick start

**Remote (recommended)** — add to your MCP client:

```json
"uml-mcp": {
  "transport": "http",
  "url": "https://uml-mcp.vercel.app/mcp"
}
```

Use **`/mcp`**, not the site root. Then ask: *“Draw a sequence diagram of a user logging in through an API gateway.”* or paste PlantUML / Mermaid / Kroki source.

Repo defaults: [`.cursor/mcp.json`](.cursor/mcp.json) · [`.vscode/mcp.json`](.vscode/mcp.json) · [`.codex/config.toml`](.codex/config.toml).

| Client | Config | Guide |
| --- | --- | --- |
| Cursor | [`.cursor/mcp.json`](.cursor/mcp.json) | [docs/integrations/cursor.md](docs/integrations/cursor.md) |
| VS Code / Copilot | [`.vscode/mcp.json`](.vscode/mcp.json) | [docs/integrations/vscode_copilot.md](docs/integrations/vscode_copilot.md) |
| OpenAI Codex | [`.codex/config.toml`](.codex/config.toml) | [docs/integrations/openai_codex.md](docs/integrations/openai_codex.md) |
| Ollama / Open WebUI | [`config/openwebui_mcp.json`](config/openwebui_mcp.json) | [docs/integrations/ollama.md](docs/integrations/ollama.md) |
| Claude Desktop | [`config/claude_desktop_*.json`](config/) | [docs/integrations/claude_desktop.md](docs/integrations/claude_desktop.md) |

All snippets: [`config/README.md`](config/README.md)

<details>
<summary><strong>Clone from origin (local stdio)</strong></summary>

```bash
git clone https://github.com/antoinebou12/uml-mcp.git
cd uml-mcp
uv sync
uv run python server.py
```

If you already have the repo and need to set origin:

```bash
git remote add origin https://github.com/antoinebou12/uml-mcp.git
```

Configs: [`config/README.md`](config/README.md) (Cursor, VS Code, Codex, Claude, Open WebUI, Continue)

</details>

<details>
<summary><strong>Claude Code plugin</strong></summary>

```text
/plugin marketplace add https://github.com/antoinebou12/uml-mcp
/plugin install uml-mcp@uml-mcp-plugins
```

[docs/integrations/claude_code.md](docs/integrations/claude_code.md) · Cursor skill: [`.skill/skills/uml-mcp-diagrams/SKILL.md`](.skill/skills/uml-mcp-diagrams/SKILL.md)

</details>

## At a glance

| Topic | What you get |
| --- | --- |
| **Diagrams** | ~37 types via [Kroki](https://kroki.io/) (UML, Mermaid, D2, TikZ, BPMN, C4, GoAT, UMLet, …) |
| **Tools** | `generate_uml` · `generate_uml_image` · `validate_uml` · `list_diagram_types` · `generate_uml_batch` |
| **Chat** | Inline PNG + markdown `![diagram](url)` + **Playground** link |
| **Deploy** | Local · Docker · Kubernetes ([Helm](deploy/helm/uml-mcp)) · [Vercel](https://vercel.com/) · [Smithery](https://smithery.ai/) |
| **Enterprise** | Optional SSO: Microsoft Entra ID / OAuth 2.1 bearer tokens, RFC 9728 metadata, clear 401/403 ([docs/enterprise](docs/enterprise/README.md)) |
| **Frontend** | Canonical AG-UI SSE for agent UIs; OpenUI can consume AG-UI and render generated components in your app |

<details>
<summary><strong>MCP tools</strong></summary>

| Tool | Purpose |
| --- | --- |
| `generate_uml` | Render one diagram; tool text includes image markdown, **URL**, **Playground**. Use `png` for ImageContent. |
| `generate_uml_image` | Inline chat image (default PNG); fetches bytes even under hosted `MCP_URL_ONLY` |
| `validate_uml` | Local checks; `strict` for Mermaid/D2 (rejects semicolon-packed `sequenceDiagram`) |
| `list_diagram_types` | Catalog (like `uml://types`) |
| `generate_uml_batch` | Many diagrams (`MCP_BATCH_MAX_ITEMS`, `MCP_BATCH_CONCURRENCY`) |

Smoke prompts: [`tests/prompts/chatgpt_mcp_smoke_test.md`](tests/prompts/chatgpt_mcp_smoke_test.md)

</details>

<details>
<summary><strong>Resources (<code>uml://</code>)</strong></summary>

| Resource | Description |
| --- | --- |
| `uml://types` | Types, backends, formats |
| `uml://templates` / `uml://examples` | Starters and samples |
| `uml://formats` / `uml://capabilities` | Formats and validation matrix |
| `uml://server-info` / `uml://workflow` | Version/tools and plan-then-generate |

</details>

<details>
<summary><strong>Diagram types</strong></summary>

| Category | Examples |
| --- | --- |
| UML | Class, Sequence, Activity, Use Case, State, Component, Deployment, Object |
| General | Mermaid, D2, Graphviz, ERD, BlockDiag, BPMN, C4 |
| Specialized | TikZ, Excalidraw, GoAT, UMLet, Nomnoml, Pikchr, Structurizr, SVGBob, WaveDrom, WireViz, … |

[docs/diagrams/index.md](docs/diagrams/index.md)

</details>

<details>
<summary><strong>Remote vs local</strong></summary>

| | Remote (Vercel) | Local |
| --- | --- | --- |
| Transport | HTTP MCP | stdio or HTTP |
| File writes | No | Optional |
| Chat images | PNG tools fetch bytes under URL-only | Same + optional disk |
| Env | Server-side | Your `.env` |

</details>

<details>
<summary><strong>Deployment</strong></summary>

**Vercel** — connect the repo; clients use `https://<project>.vercel.app/mcp`.

**Smithery** — paste that `/mcp` URL at [smithery.ai/new](https://smithery.ai/new). Guide: [docs/integrations/vercel_smithery.md](docs/integrations/vercel_smithery.md).

**Docker**

```bash
docker compose up -d
docker build -t uml-mcp . && docker run -p 8000:8000 uml-mcp
docker run -i uml-mcp python server.py --transport stdio
```

[docs/deploy/docker.md](docs/deploy/docker.md)

**Kubernetes + SSO**: `helm upgrade --install uml-mcp deploy/helm/uml-mcp --set auth.mode=jwt …` (Entra ID or any OIDC provider). Guide: [docs/enterprise](docs/enterprise/README.md).

</details>

<details>
<summary><strong>Configuration (local)</strong></summary>

| Variable | Default |
| --- | --- |
| `KROKI_SERVER` | `https://kroki.io` |
| `PLANTUML_SERVER` | `http://plantuml-server:8080` |
| `MCP_OUTPUT_DIR` | `./output` |
| `MCP_READ_ONLY` | `false` |
| `MCP_URL_ONLY` | see [docs/configuration.md](docs/configuration.md) |
| `MCP_BATCH_MAX_ITEMS` | `20` |
| `MCP_BATCH_CONCURRENCY` | `4` |
| `MCP_RATE_LIMIT_PER_MINUTE` | `0` |

Full list: [docs/configuration.md](docs/configuration.md)

</details>

<details>
<summary><strong>Architecture & layout</strong></summary>

Assistant → `generate_uml` / `generate_uml_image` → Kroki (+ fallbacks) → `url`, `playground`, optional image bytes.

<p align="center">
  <img src="docs/assets/diagrams/mcp-request-flow.svg" width="100%" style="max-width: 900px;" alt="MCP request flow" />
</p>

```text
server.py / app.py     -- MCP + FastAPI (/mcp)
mcp_core/tools/        -- generate_uml, generate_uml_image, validate, batch
tools/kroki/           -- Kroki, PlantUML, Mermaid, D2
```

**Agent UI:** canonical `POST /ag-ui` for AG-UI clients; legacy direct render at `POST /ag-ui/generate`. See [frontend integration](docs/integrations/frontend.md) and [OpenUI + UML-MCP](docs/integrations/openui.md).

</details>

<details>
<summary><strong>Development</strong></summary>

```bash
uv sync --all-groups
uv run pytest tests/ -v
uv run ruff check . && uv run ruff format --check .
make ci
```

Docs locally: `uv run mkdocs serve` → http://127.0.0.1:8000

</details>

<details>
<summary><strong>Enterprise SSO: OAuth 2.1 · OpenID Connect · Microsoft Entra ID</strong></summary>

Optional and off by default (`MCP_AUTH_MODE=none`; the public Vercel endpoint stays open).

| Topic | Summary |
| --- | --- |
| Modes | `jwt`: validate Entra / OIDC access tokens (resource server) · `entra-proxy`: adds RFC 8414 + RFC 7591 facade with S256-only PKCE for DCR clients |
| OAuth 2.1 | Authorization Code + PKCE S256; header-only bearer tokens; 401 → `WWW-Authenticate: Bearer resource_metadata, scope`; 403 `insufficient_scope` step-up |
| OpenID Connect | Discovery + JWKS for signing keys; ID tokens are rejected, access tokens only |
| Entra ID | v2 tokens (`requestedAccessTokenVersion: 2`), `mcp.read` / `mcp.write` / `.default`, app roles, VS Code + Visual Studio pre-authorized ([setup](docs/enterprise/entra-id.md)) |
| MSAL | Client side only (VS Code, Visual Studio, Azure CLI, daemons); examples in [OAuth/OIDC/MSAL](docs/enterprise/oauth-oidc.md) |
| Try it | [`tests/http/entra-auth.http`](tests/http/entra-auth.http) · `python -m mcp_core.auth generate az-script` · [checklist](docs/enterprise/checklist.md) |

</details>

## Community

> If this survives a real production repo, it beats a lot of polished launch demos.

— [@AIDailyGems](https://x.com/AIDailyGems/status/2060894196777509037) on [antoinebou12/uml-mcp](https://github.com/antoinebou12/uml-mcp)

Daily and monthly activity (stars, forks, merged PRs, issues): [trendshift.io/repositories/42725](https://trendshift.io/repositories/42725)

## Links

| | |
| --- | --- |
| Docs | [Site](https://antoinebou12.github.io/uml-mcp/) · [Cursor](docs/integrations/cursor.md) · [Claude Code](docs/integrations/claude_code.md) · [Frontend](docs/integrations/frontend.md) · [Enterprise SSO](docs/enterprise/README.md) · [OpenUI](docs/integrations/openui.md) |
| Contribute | [CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [SECURITY.md](SECURITY.md) |
| License | [MIT](LICENSE) |

Maintained by [Antoine Boucher](https://github.com/antoinebou12). Built on [PlantUML](https://plantuml.com/), [Kroki](https://kroki.io/), [Mermaid](https://mermaid.js.org/), and [D2](https://d2lang.com/).
