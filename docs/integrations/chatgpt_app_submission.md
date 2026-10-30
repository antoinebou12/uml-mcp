# ChatGPT app submission

UML-MCP is submitted to the OpenAI Apps directory as a remote MCP server at
`https://uml-mcp.antoineboucher.info/mcp`. The bundle and the domain challenge are
self-hosted: nothing is built or hosted by a third-party submission service.

## Bundle

The checked-in bundle lives in [`submission/openai/`](https://github.com/antoinebou12/uml-mcp/tree/main/submission/openai):

| File | Purpose |
| --- | --- |
| `plugin.json` | Listing (name, descriptions, prompts, URLs), review test cases, release notes |
| `mcp.json` | The one Streamable HTTP server: `https://uml-mcp.antoineboucher.info/mcp` |
| `assets/logo.png` | 48×48 logo and composer icon |
| `demo.mp4` | Demo recording (kept for reference; uploaded separately, not zipped) |

Check and zip it:

```bash
uv run python scripts/build_openai_submission.py
```

The script stamps nothing silently: it fails when the `plugin.json` version differs
from `pyproject.toml`, when a positive test case names a tool the server does not
register, when a negative test case triggers a tool, or when a listing URL is not
HTTPS on the production host. The zip (`dist/uml-mcp-openai-<version>.zip`) holds
only `plugin.json`, `mcp.json` and `assets/logo.png`, with fixed timestamps so the
same sources give the same bytes. `--check` validates without writing the zip.

## Domain verification

After the ZIP is uploaded, OpenAI shows a verification token and checks it at:

```text
https://uml-mcp.antoineboucher.info/.well-known/openai-apps-challenge
```

The FastAPI app serves that path from configuration:

| Setting | Value |
| --- | --- |
| Env var | `OPENAI_APPS_CHALLENGE_TOKEN` |
| `uml-mcp.yaml` | `server.openai_apps_challenge_token` |
| Response | The token as `text/plain`, `Cache-Control: no-store` |
| Unset | `404` (nothing is claimed by default) |

On Vercel, add the token under **Project → Settings → Environment Variables**
(Production), redeploy, then confirm before pressing **Verify** in OpenAI:

```bash
curl -i https://uml-mcp.antoineboucher.info/.well-known/openai-apps-challenge
```

The token is not a secret credential, but it is per-submission, so keep it in the
environment rather than in git.

## Listing URLs

| Field | URL |
| --- | --- |
| Website | `https://uml-mcp.antoineboucher.info` |
| Privacy policy | `https://uml-mcp.antoineboucher.info/.well-known/privacy.txt` |
| Terms of service | `https://uml-mcp.antoineboucher.info/.well-known/terms.txt` |
| Support | `https://github.com/antoinebou12/uml-mcp/issues` |

## Diagram viewer

`generate_uml`, `generate_uml_image`, and `generate_uml_batch` link the sandboxed MCP Apps viewer
(`ui://uml-mcp/diagram-viewer`). Its resource declares the widget domain
(`https://uml-mcp.antoineboucher.info` by default, `MCP_APP_DOMAIN` to override),
an empty `connectDomains` CSP and a standard resource `description` (MCP Apps v2;
see [Manufact compatibility](manufact-compatibility.md)). The
viewer offers zoom, pan, fit, per-type theme and format pickers that re-render
through the app-only `rerender_diagram` tool, copyable links and source, and
fullscreen when the host allows it.

Batch results appear in a gallery, including failed items and links whose previews
load when selected. The server shares a bounded inline-image budget across the
batch. PDF results remain links; text diagrams display as text.

The Source tab lets you edit, check syntax, and render again with Ctrl+Enter.
Validation messages link to the affected line. Failed renders offer edit and retry
actions, plus an assistant repair request when the host supports messages.
Hosts without tool-call support keep source read-only and expose available links.
Arrow keys, Home, and End navigate the view tabs and batch gallery.
