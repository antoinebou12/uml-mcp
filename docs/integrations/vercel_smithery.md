# Deploy to Vercel and Publish on Smithery

This guide walks you through deploying the UML-MCP server to Vercel and publishing it on Smithery so users can connect via **Streamable HTTP** without installing anything. For the full Smithery docs index, see [smithery.ai/docs/llms.txt](https://smithery.ai/docs/llms.txt).

## 1. Deploy to Vercel

### Prerequisites

- A [Vercel](https://vercel.com) account
- This repo connected to Vercel (GitHub/GitLab/Bitbucket)

### Deploy

1. **Connect the repo** in the [Vercel dashboard](https://vercel.com/new): Import your `uml-mcp` repository.
2. **Build settings** (match [vercel.json](https://github.com/antoinebou12/uml-mcp/blob/main/vercel.json) in the repo root; clear dashboard overrides if they disagree):
   - Framework Preset: **FastAPI** (`"framework": "fastapi"`—needed so Vercel runs the custom install inside the Python build virtualenv)
   - Install Command: `bash scripts/vercel-install.sh` (runs `uv pip install -r requirements.txt` only, then a quick `pydantic` / `pydantic_core` import smoke test)
   - Build Command: `python -m mcp_core.build_static_server_card` (writes `public/.well-known/mcp/server-card.json` and related files)
   - Serverless entrypoint: `app.py` at the repo root (see `functions` in `vercel.json`); routing and output are handled by `vercel.json`
3. **Deploy** and wait for the build to finish.

**Install step fails (e.g. exit code 2):** Keep `"framework": "fastapi"` in `vercel.json` (not `null` / dashboard **Framework Preset** forced to Other without the FastAPI preset), so Vercel runs `installCommand` inside the Python build virtualenv. Do not override **Install Command** in the dashboard with a bare `pip install` that targets the system interpreter (PEP 668).

Your app will be available at:

- **Production**: `https://<your-project>.vercel.app`
- **REST API**: `https://<your-project>.vercel.app/` (root, `/health`, `/generate_diagram`, etc.)
- **MCP endpoint**: `https://<your-project>.vercel.app/mcp`

Use the **MCP URL** when publishing to Smithery.

## 2. Publish on Smithery

Smithery can list your server so users can add it with one click. You can either **host the server on Smithery** (Docker/stdio) or **point Smithery to your Vercel URL** (self-hosted HTTP).

### Option A: URL (bring your own hosting)

Publishing a URL-based server is done **only via the Smithery website**; the `@smithery/cli` npm package has no `deploy` or `publish` command for this.

1. Go to [smithery.ai/new](https://smithery.ai/new).
2. Sign in if needed (Google or GitHub).
3. Choose **URL** (bring your own hosting).
4. Fill in:
   - **Namespace**: your Smithery username (e.g. `antoinebou12`)
   - **Server ID**: short slug (e.g. `uml`)
   - **MCP Server URL**: `https://<your-project>.vercel.app/mcp`  
     Replace `<your-project>` with your actual Vercel project URL. Use the **root** deployment URL (e.g. `https://uml-xxx.vercel.app`), not a path; the MCP endpoint is at `/mcp`.
5. Submit. Smithery will use your server’s Streamable HTTP transport and will fetch metadata from `https://<your-project>.vercel.app/.well-known/mcp/server-card.json` when automatic scanning is not possible.

**Config schema (recommended):** To remove the “No config schema provided” warning and let users set options (output dir, Kroki URL, etc.) in Smithery’s UI, add a session config schema after creating the server (see below). The npm package `@smithery/cli` (v2.x) does not provide `publish` or `deploy` for URL-based servers; use the web flow only.

After creating the server, open it on Smithery → **Settings** → **Session configuration** (or equivalent) and paste or upload the contents of `smithery-config-schema.json`. See [Smithery Session Configuration](https://smithery.ai/docs/build/session-config) for the JSON Schema format with `x-from` extension.

After publishing, your server will appear at:

`https://smithery.ai/server/@<namespace>/<server-id>`

Example: `https://smithery.ai/server/@antoinebou12/uml`

**Improve your Smithery listing:** Open **Settings → General** on your server’s Smithery page. Set **Display name**, **Description**, **Homepage** (e.g. your repo URL or `https://umlmcp.vercel.app`), and **Server icon** to improve discoverability and the Server Metadata score. Adding the session config schema (see above) improves the Configuration UX score.

**AI and plugin compatibility:** The app serves `/.well-known/ai-plugin.json` with a dynamic base URL (so OpenAI-style plugins work on any deployment), `/openapi.json` and `/openapi.yaml` for API docs and AI consumers, and `/logo.png` (ICO) for manifests. The server card at `/.well-known/mcp/server-card.json` uses correct JSON schema types for all tools so AI models and Smithery get accurate tool schemas.

### Option B: Hosted (Smithery hosts it)

**Note:** Hosted deployment is in private early access — [contact Smithery](mailto:support@smithery.ai) if interested.

If you use Smithery-hosted deployment, the existing `smithery.yaml` defines the server. Connect your GitHub repo and deploy via the **Deployments** tab on your server's Smithery page. The `smithery.yaml` includes a [Session Configuration](https://smithery.ai/docs/build/session-config) schema for output directory, Kroki URL, log level, and other settings.

## 3. Connect from a client

Once the server is on Smithery (or you have the Vercel URL), configure your MCP client with the **Streamable HTTP** URL:

- **From Smithery**: Use the “Add to Cursor” (or similar) button on the server page, or copy the URL Smithery shows.
- **Direct**: In Cursor (or another client), set the MCP server URL to:
  `https://<your-project>.vercel.app/mcp`

Example Cursor config (`.cursor/mcp.json` or project MCP settings):

```json
{
  "mcpServers": {
    "uml": {
      "url": "https://<your-project>.vercel.app/mcp"
    }
  }
}
```

Replace `<your-project>` with your real Vercel URL.

## Troubleshooting

### HTTP 401 / "Invalid OAuth error response" when connecting via Smithery

If Smithery shows a connection error like `HTTP 401: Invalid OAuth error response: SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON`, the gateway is hitting **Vercel Deployment Protection**: Vercel returns an HTML login page instead of JSON, so the MCP handshake fails.

**Fix (choose one):**

1. **Disable Deployment Protection (recommended for public MCP)**  
   In the [Vercel project](https://vercel.com/dashboard) → **Settings** → **Deployment Protection**, turn off protection for Production and/or Preview so your app URL is publicly reachable. Then use the normal MCP URL in Smithery: `https://<your-project>.vercel.app/mcp`.

2. **Keep protection and use a bypass token**  
   If you want to keep protection, use Vercel’s [Protection Bypass for automation](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation). Get the bypass token from the project’s Deployment Protection settings, then in Smithery set **MCP Server URL** to:
   ```
   https://<your-project>.vercel.app/mcp?x-vercel-set-bypass-cookie=true&x-vercel-protection-bypass=YOUR_BYPASS_TOKEN
   ```
   Replace `YOUR_BYPASS_TOKEN` with the token from Vercel.

### Connection error: Initialization failed with status 404 or 405 / “advertise server-card”

Smithery discovers your server by requesting `/.well-known/mcp/server-card.json` on the **root** of your deployment. Vercel reserves the `/.well-known` path and does not allow rewrites to serverless functions, so the FastAPI app may never receive that URL (404). If the path is served but only for certain HTTP methods, you can get **405 Method Not Allowed**; serving the server card as a static asset fixes both (GET/HEAD return 200).

**Fix:** This repo serves the server card as a **static file** at `public/.well-known/mcp/server-card.json` (Vercel exposes it at `/.well-known/mcp/server-card.json`). The catch-all rewrite to `/` (the serverless handler) must **not** apply to `/.well-known/*`, or those URLs never hit the static asset. In `vercel.json`, the final rewrite uses a path pattern that excludes `.well-known`, and `buildCommand` runs `python -m mcp_core.build_static_server_card` so the JSON exists in `public/` on each deploy. Before publishing to Smithery, verify: open `https://<your-project>.vercel.app/.well-known/mcp/server-card.json` in a browser; you should see valid JSON with `serverInfo`, `tools`, and `resources`. If you see 404/405, redeploy and ensure the latest `vercel.json` is deployed (and that `public/.well-known/mcp/server-card.json` exists after the build). To regenerate the file when tools change, run `python -m mcp_core.build_static_server_card` from the repo root, then commit the updated `public/.well-known/mcp/` files if you want them versioned. Then ensure `public/.well-known/mcp/server-card.json` is committed and deployed.

### "Not Acceptable: Client must accept text/event-stream" (JSON-RPC error)

The [MCP Streamable HTTP](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports/) protocol requires clients to send an **Accept** header that includes `text/event-stream` (e.g. `Accept: application/json, text/event-stream`). If the client or proxy (e.g. Smithery) does not send this header, the MCP layer may respond with a JSON-RPC error: `"Not Acceptable: Client must accept text/event-stream"` (code -32600).

**Server-side workaround:** This app includes middleware that, for all requests to `/mcp` and `/mcp/...`, sets or normalizes the `Accept` header to `application/json, text/event-stream` when it is missing or does not include `text/event-stream`. So connections via Smithery or Cursor should work even if the client or proxy omits the header. No client or Smithery configuration change is required.

If you still see this error after deploying the latest version, ensure the middleware is present in `app.py` (`_MCPAcceptHeaderMiddleware`) and that requests to `/mcp` go through the FastAPI app (not a static rewrite).

### "Bad Request: Missing session ID" (JSON-RPC -32600)

If you see `{"error":{"code":-32600,"message":"Bad Request: Missing session ID"}}` when connecting to `/mcp`, the MCP Streamable HTTP transport is rejecting requests because session validation fails (e.g. on serverless, where sessions cannot persist across invocations).

**Fix:** Ensure `FASTMCP_STATELESS_HTTP=true` is set in your Vercel project. In stateless mode, each request gets a fresh context and does not require session IDs. This is already configured in `vercel.json` for this repo; if you use the Vercel Dashboard for env vars, add it there for Production (and Preview if needed).

### Read-only filesystem (diagram save fails on Vercel)

On Vercel, the runtime filesystem may be read-only. If the MCP cannot write the generated diagram to disk, it still returns the **Kroki URL** and **playground** link in the tool result (only `local_path` is omitted). So diagram generation continues to work; clients can open the URL to view the image. Alternatively, use **`POST /kroki_encode`** with `type`, `code`, and `output_format` in the body to get a diagram URL without any file write (useful for serverless or when you only need a shareable link).

### URL-only mode on Vercel (no image fetch in the function)

Production deployments set **`MCP_URL_ONLY=true`** (and **`MCP_MEMORY_ONLY=true`**, **`MCP_DIAGRAM_CACHE_SIZE=0`**) in `vercel.json`. In that mode the server builds Kroki and playground links locally and does **not** download rendered diagram bytes into the serverless function, does **not** return `content_base64`, and does not use the in-process render cache. PlantUML/Mermaid fallbacks return URLs only (no HTTP GET of the image inside the function). To restore fetching and base64 when not saving to disk, set `MCP_URL_ONLY=false` in the Vercel project environment. SVG `scale` is ignored in URL-only mode because scaling requires decoded SVG bytes.

### 405 on POST /mcp (Reconnect failed)

If you see **405 Method Not Allowed** on **POST /mcp** (e.g. “Reconnect failed” in Cursor via Smithery, or “Streamable HTTP error: Error POSTing to endpoint: {detail:Method Not Allowed}”), the client or a proxy is POSTing to an endpoint that does not allow POST.

**What to check:**

1. **Correct MCP URL**  
   The client must POST to the **MCP endpoint** (e.g. `https://<your-project>.vercel.app/mcp`), not to the server card or root. POSTing to `/.well-known/mcp/server-card.json` or to the root URL can return 405 because those are served as GET-only (static card) or other handlers. In Cursor/Smithery, ensure the configured URL is exactly `https://<your-project>.vercel.app/mcp` (with `/mcp`).

2. **Vercel build and runtime logs**  
   In the app startup logs, look for either “MCP HTTP app mounted at /mcp” (success) or “MCP HTTP fallback: GET/POST /mcp return 503 (MCP HTTP transport not available).” If you see the fallback message, the MCP app failed to load. Check for any exception logged in the same block (the app logs with `exc_info=True`).

3. **Dependencies**  
   Confirm that `fastmcp` and all modules used by `get_mcp_server()` (e.g. diagram tools, resources, prompts, Kroki, PlantUML) are installed and import without error. Production installs use `requirements.txt` via `installCommand` and Vercel’s Python/`uv` pipeline (`requirements-dev.txt` is for local development and CI only). Ensure the build completes and that `fastmcp>=2.3.1` is present in `requirements.txt`.

**405 vs 503 fallback:** When the MCP app is not mounted, this server registers both GET and POST for `/mcp` and returns **503** with `{"detail": "MCP HTTP transport is not available."}` (and OPTIONS for CORS). So if the request reaches the FastAPI app at `/mcp`, you would see 503, not 405. A 405 usually means the request is hitting a different handler (e.g. wrong URL or a proxy that only allows GET for that path).

### "Vercel Runtime Timeout Error: Task timed out after 300 seconds" (GET /mcp)

MCP Streamable HTTP keeps a **long-lived GET** connection open (Server-Sent Events) for the session. Vercel terminates serverless invocations after a maximum duration, so the function that handles GET `/mcp` is killed when that limit is reached (default **300 seconds** on Hobby and Pro).

**What you see:** Logs show `GET 200 /mcp/` followed by `Vercel Runtime Timeout Error: Task timed out after 300 seconds` or `Terminating session: None`. The client (Cursor, Smithery, etc.) then loses the connection and may show a reconnect or timeout error.

**Mitigations:**

1. **Increase max duration (Pro/Enterprise)**  
   This repo sets `maxDuration: 200` in `vercel.json` under `functions["app.py"]`. On **Pro** or **Enterprise** (with Fluid Compute), you may raise that value (for example toward **800** seconds) so the GET `/mcp` connection can stay open longer than the default **300s** platform cap on Hobby. On **Hobby**, the cap remains 300s regardless.

2. **Reconnect on timeout**  
   Clients should reconnect when the stream ends. Cursor and Smithery typically retry or allow re-adding the server; after a timeout, reconnect to `/mcp` to start a new session.

3. **Long-lived or heavy use**  
   For sessions that must stay open indefinitely (or to avoid timeouts entirely), use **Smithery-hosted** deployment (Docker) or self-host the server (e.g. Docker, a long-running process) instead of Vercel serverless.

### CI or local: `pip install smithery-cli` / "No matching distribution"

**Smithery does not publish a Python package on PyPI** under the name `smithery-cli`. The official CLI is **Node/npm**: [`@smithery/cli`](https://www.npmjs.com/package/@smithery/cli).

**Use instead:**

- One-off: `npx -y @smithery/cli <command>` (see [Smithery docs](https://smithery.ai/docs)).
- Global: `npm install -g @smithery/cli` then run `smithery ...`.

This repository’s workflow `.github/workflows/deploy.yml` uses `npx -y @smithery/cli publish ...` with **Node 20+**. If your workflow still runs `pip install smithery-cli`, remove that step, add **Node 20+** (for example `actions/setup-node`), then call the CLI via `npx` or `npm`.

### Smithery CLI: "ReferenceError: File is not defined"

If `npx -y @smithery/cli` (e.g. `publish` or `deploy`) fails with `ReferenceError: File is not defined` (in `undici`), the CLI is running on **Node.js 18**. The `File` global is only available in **Node.js 20+**.

**Fix (pick one):**

1. **Use Node 20+** when running the CLI (e.g. install Node 20 or use [nvm](https://github.com/nvm-sh/nvm): `nvm use 20` then run the `deploy` command again).
2. **Use the Smithery website instead:** Create the URL-based server at [smithery.ai/new](https://smithery.ai/new) (choose URL, set MCP Server URL to `https://<your-project>.vercel.app/mcp`). Then in **Settings → Session configuration**, paste the contents of `smithery-config-schema.json`. No CLI required.

### Other issues

- **405 Method Not Allowed** on the server card URL: usually fixed by ensuring the server card is served as a static asset at `/.well-known/mcp/server-card.json` so GET/HEAD return 200 (see the 404/405 section above).
- **502 / timeout**: Vercel serverless functions have a max duration (300s default on Hobby; Pro/Enterprise can set a higher `maxDuration` on `app.py` in `vercel.json`). The MCP GET connection is long-lived and will hit this limit; see the [timeout section](#vercel-runtime-timeout-error-task-timed-out-after-300-seconds-get-mcp) above. For very long sessions or heavy use, consider Smithery-hosted Docker.
- **MCP at /mcp**: Ensure you use the path `/mcp` (e.g. `https://...vercel.app/mcp`), not the root URL.
- **CORS**: The app allows all origins for API and MCP; restrict in production if needed.
- **Logo or OpenAPI YAML**: `/logo.png` is served by the app (image/x-icon). `/openapi.yaml` returns the spec in YAML when PyYAML is installed (required in `requirements.txt`); if not, it returns 501 and clients should use `/openapi.json`.
