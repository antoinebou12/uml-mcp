# Frontend Integration (AG-UI)

Bring diagram generation into a user-facing web app. UML-MCP exposes two complementary
surfaces, so you can pick the one that matches your stack:

| Surface | What it is | Best for |
| --- | --- | --- |
| **MCP at `/mcp`** | Gives an LLM/agent the `generate_uml` tools | Giving an **in-app agent** diagram tools (e.g. [CopilotKit](https://github.com/copilotkit/copilotkit)) |
| **AG-UI events at `/ag-ui/*`** | Streams `RUN_STARTED…RUN_FINISHED` events over SSE, ending with the diagram as inline base64/URL | Rendering a diagram **directly** in a frontend with no agent orchestrator |

Both run from the same FastAPI app (`app.py`) and share the same render pipeline, so no
extra backend is required.

## Before you start

- The AG-UI routes live on the same host as the MCP endpoint:
  - **Hosted:** `https://uml-mcp.vercel.app` (your project domain)
  - **Local:** `http://127.0.0.1:8000` (via `python server.py --transport http --port 8000`)
- **Browser CORS:** if your frontend is a different origin than the server, allowlist it
  with the `MCP_ALLOWED_ORIGINS` env var (comma-separated) so browser fetches are accepted:
  `MCP_ALLOWED_ORIGINS=https://example.com,http://localhost:3000`.

---

## Inline images in MCP chat clients (Cursor, Copilot)

If your user has the agent call the MCP tool **in a chat** (Cursor agent, Copilot, etc.)
and you want the diagram **visible in the message**, use the **`generate_uml_image`** tool:

```jsonc
// Cursor / Copilot MCP tool call
{
  "diagram_type": "mermaid",
  "code": "graph TD; A-->B;",
  "output_format": "png"        // png (default) | svg | jpeg
}
```

That tool (and `generate_uml`) returns an MCP **`image` content block** (base64 + MIME type)
instead of just a URL, so image-capable clients render it **inline in the chat**.
On hosted Vercel with `MCP_URL_ONLY=true`, **`generate_uml_image` still fetches bytes** so the
image block is present; plain `generate_uml` may return URL-only.

Manual ChatGPT / client smoke prompts live under [`tests/prompts/`](https://github.com/antoinebou12/uml-mcp/tree/main/tests/prompts) (for example `chatgpt_mcp_smoke_test.md`).

- **PNG/JPEG** render in essentially all image-capable clients — use `output_format: "png"`
  for the widest support.
- **SVG** is also returned as an image block; support varies by client.
- If a client does not render image blocks, it still sees the same result as text/JSON with
  the `url` and `content_base64` fields, so nothing is lost.

---

## Option A — CopilotKit (add diagram tools to an in-app agent)

Use the standard MCP path so the agent can call `generate_uml`. CopilotKit's runtime
([`@copilotkit/runtime/v2`](https://github.com/copilotkit/copilotkit)) attaches MCP servers
with `MCPAppsMiddleware`:

```ts
// app/agent.ts
import { BuiltInAgent } from "@copilotkit/runtime/v2";
import { MCPAppsMiddleware } from "@ag-ui/mcp-apps-middleware";

export function createDefaultAgent(): BuiltInAgent {
  const agent = new BuiltInAgent({
    model: "openai/gpt-4o",
    prompt: `You generate UML / Mermaid / D2 diagrams. Call generate_uml and
             show the diagram to the user.`,
  });

  agent.use(new MCPAppsMiddleware({
    mcpServers: [
      {
        type: "http",
        url: "https://uml-mcp.vercel.app/mcp", // or http://127.0.0.1:8000/mcp locally
        serverId: "uml-mcp",
      },
    ],
  }));

  return agent;
}
```

The runtime is mounted with `createCopilotEndpoint` (see the official
[CopilotKit MCP Apps starter](https://github.com/CopilotKit/CopilotKit/tree/main/examples/integrations/mcp-apps),
which uses the `@ag-ui/mcp-apps-middleware` package):

```ts
// app/api/copilotkit/[[...slug]]/route.ts
import { CopilotRuntime, createCopilotEndpoint } from "@copilotkit/runtime/v2";
import { handle } from "hono/vercel"; // matches your Next.js adapter
import { createDefaultAgent } from "../../../agent";

const runtime = new CopilotRuntime({ agents: { default: createDefaultAgent() } });
const app = createCopilotEndpoint({ runtime, basePath: "/api/copilotkit" });

export const GET = handle(app);
export const POST = handle(app);
export const PATCH = handle(app);
export const DELETE = handle(app);
```

`generate_uml` returns `content_base64` (plus a `url`) when you omit `output_dir`, so your
UI can render it inline as a data URL:

```tsx
const svg = `data:image/svg+xml;base64,${toolResult.content_base64}`;
// <img src={svg} /> — or set svg dangerouslySetInnerHTML
```

> **Tip:** From `generate_uml` prefer `output_format: "svg"` for the best inline rendering.

---

## Option B — consume the AG-UI event stream directly

No agent, no LLM orchestrator — your frontend `POST`s a render request and reads SSE
events, then renders the final diagram inline. This is exactly what the `/ag-ui/generate`
streaming endpoint was built for.

### AG-UI endpoints

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/ag-ui/generate` | **Stateless** single-request stream. `POST` the request, read events over SSE until `RUN_FINISHED`/`RUN_ERROR`. Recommended on serverless. |
| `POST` | `/ag-ui/start` | Start-then-subscribe. Returns `{ run_id, events_url }`. |
| `GET` | `/ag-ui/events/{run_id}` | Stream the events for a started run. |

Request body (same fields as the `generate_uml` tool):

```json
{
  "diagram_type": "mermaid",
  "code": "graph TD; A-->B;",
  "output_format": "svg",
  "theme": null,
  "scale": 1.0,
  "run_id": null
}
```

### Event flow

Each streamed frame is `data: {json}`. Events arrive in this order throughout a run:

| `type` | Meaning |
| --- | --- |
| `RUN_STARTED` | A run began. |
| `STEP_STARTED` / `STEP_FINISHED` | The render step started / finished. |
| `TOOL_CALL_START` / `TOOL_CALL_RESULT` | Mirrors the `generate_uml` call (id, args, output). |
| `STATE_SNAPSHOT` | Editable diagram source (for in-place editors). |
| `CUSTOM` | **Rendering payload**: `payload.content_base64`, `payload.url`, `payload.playground`, `payload.code`, `payload.diagram_type`. |
| `RUN_FINISHED` | Success; `outcome.type === "success"`, also carries `output`. |
| `RUN_ERROR` | Failure; `error.message`, `error.code`, `error.retryable`. |

Every event carries a shared `run_id` and `timestamp`.

### Minimal React consumer

```tsx
"use client";
import { useEffect, useRef, useState } from "react";

type AguiEvent = { type: string; [k: string]: unknown };

const API = "https://uml-mcp.vercel.app"; // or "http://127.0.0.1:8000"

export function AguiDiagram({ code, diagramType = "mermaid" }: {
  code: string; diagramType?: string;
}) {
  const [status, setStatus] = useState("starting");
  const [img, setImg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    if (busy.current) return;
    busy.current = true;
    let cancelled = false;

    (async () => {
      const res = await fetch(`${API}/ag-ui/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diagram_type: diagramType, code, output_format: "svg" }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const handleEvent = (ev: AguiEvent) => {
        if (cancelled) return;
        switch (ev.type) {
          case "RUN_STARTED":
          case "STEP_STARTED":
          case "TOOL_CALL_START":
            setStatus("rendering"); break;
          case "CUSTOM": {
            const payload = ev.payload as {
              content_base64?: string | null; url?: string | null;
            };
            if (payload.content_base64) {
              setImg(`data:image/svg+xml;base64,${payload.content_base64}`);
            } else if (payload.url) setImg(payload.url);
            break;
          }
          case "RUN_FINISHED": setStatus("done"); break;
          case "RUN_ERROR":
            setError((ev.error as { message?: string })?.message ?? "Render failed");
            setStatus("error"); break;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // Frames are separated by a blank line after each `data: {json}`.
        for (const frame of buffer.split("\n\n")) buffer = frame;
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines)
          if (line.startsWith("data: ")) handleEvent(JSON.parse(line.slice(6)));
      }
      busy.current = false;
    })().catch((e) => { setError(String(e)); setStatus("error"); });

    return () => { cancelled = true; };
  }, [code, diagramType]);

  if (error) return <pre className="text-red-500">{error}</pre>;
  if (img) return <img src={img} alt="diagram" style={{ maxWidth: "100%" }} />;
  return <div>… {status} …</div>;
}
```

### Plain JavaScript (framework-free)

```js
async function renderDiagram(diagramType, code) {
  const res = await fetch("https://uml-mcp.vercel.app/ag-ui/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ diagram_type: diagramType, code, output_format: "svg" }),
  });
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let dataUrl = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    for (const frame of text.split("\n\n")) {
      const line = frame.trim();
      if (!line.startsWith("data: ")) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.type === "CUSTOM" && ev.payload?.content_base64) {
        dataUrl = `data:image/svg+xml;base64,${ev.payload.content_base64}`;
      } else if (ev.type === "RUN_ERROR") {
        throw new Error(ev.error?.message ?? "Render failed");
      }
    }
  }
  return dataUrl; // e.g. document.getElementById("diagram").src = dataUrl
}
```

### Start-then-subscribe pattern

```bash
# 1. Start a run
RUN=$(curl -s -X POST https://uml-mcp.vercel.app/ag-ui/start \
  -H "Content-Type: application/json" \
  -d '{"diagram_type":"mermaid","code":"graph TD; A-->B;"}')
RUN_ID=$(printf '%s' "$RUN" | jq -r .run_id)
echo "$RUN" | jq -r .events_url

# 2. Stream the events
curl -N "https://uml-mcp.vercel.app/ag-ui/events/$RUN_ID"
```

---

## Notes

- **Serverless / Vercel:** prefer **`/ag-ui/generate`** — it is stateless (no in-process run
  store), whereas `start` + `events/{id}` keep a per-process store and are best on a single
  always-on instance (Docker/local). Both emit the inline `content_base64`, so no filesystem
  writes are required.
- **Spec version:** AG-UI is actively evolving. The event names documented here match the
  current AG-UI core event model. Pin the spec/consumer version you target and validate
  events on the client before rendering.
- **Security:** `/ag-ui/*` routes follow the same CORS/origin and rate-limit middleware as
  the rest of the app. For a hosted deployment, restrict `MCP_ALLOWED_ORIGINS` to your
  frontend origin rather than opening it up.

## Related resources

- [Claude Code plugin](claude_code.md) · [Cursor](cursor.md) · [Vercel & Smithery](vercel_smithery.md)
- [MCP tools](../api/tools.md)
- [AG-UI (the protocol)](https://ag-ui.com) · [CopilotKit](https://github.com/copilotkit/copilotkit)