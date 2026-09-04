# Ollama / Open WebUI Integration

Use **Ollama** as the local model host and attach UML-MCP as MCP tools—most commonly through **Open WebUI**, or via **Continue** in the editor.

UML-MCP does not replace Ollama. Ollama runs the LLM; Open WebUI / Continue call `https://uml-mcp.vercel.app/mcp` (or a local stdio server) so the model can render diagrams.

## Open WebUI + Ollama (recommended)

Open WebUI (v0.6.31+) supports **MCP Streamable HTTP** natively.

### 1. Add the MCP connection

1. Open **Admin Panel → Settings → Integrations** (External Tool Servers).
2. **+ Add Connection**.
3. Set **Type** to **MCP (Streamable HTTP)** — not OpenAPI.
4. **URL:** `https://uml-mcp.vercel.app/mcp`
5. **Auth:** None (public hosted endpoint).
6. Save.

Or **Import** the JSON from [`config/openwebui_mcp.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/openwebui_mcp.json):

```json
[
  {
    "type": "mcp",
    "url": "https://uml-mcp.vercel.app/mcp",
    "auth_type": "none",
    "info": {
      "id": "uml-mcp",
      "name": "UML-MCP Diagrams",
      "description": "Generate UML, Mermaid, and 30+ diagram types via MCP."
    }
  }
]
```

### 2. Enable tools on the Ollama model

1. Open the model settings for your Ollama model (for example `llama3.2`).
2. **Advanced Params → Function Calling → Native** (required; Default often ignores tools).
3. Under **Tools**, enable **UML-MCP Diagrams**.

### 3. Chat

Ask for a diagram. Prefer prompts that request PNG / “show in chat” so the agent uses `generate_uml_image`. Expect markdown image + **URL** + **Playground** in the tool result.

Official Open WebUI MCP docs: [docs.openwebui.com/features/extensibility/mcp](https://docs.openwebui.com/features/extensibility/mcp/).

## Continue + Ollama

Merge [`config/continue_config.yaml`](https://github.com/antoinebou12/uml-mcp/blob/main/config/continue_config.yaml) into `~/.continue/config.yaml` (or your workspace Continue config):

```yaml
models:
  - name: Local Ollama
    provider: ollama
    model: llama3.2

mcpServers:
  - name: uml-mcp
    type: streamable-http
    url: https://uml-mcp.vercel.app/mcp
```

Adjust the Ollama model name to one you have pulled (`ollama list`).

## Local stdio via mcpo

Open WebUI’s native MCP connector is **Streamable HTTP only**. To expose a **local** `server.py` stdio process, run [mcpo](https://github.com/open-webui/mcpo) (MCP → OpenAPI proxy), then add an **OpenAPI** tool server in Open WebUI pointing at mcpo.

Example mcpo config pointing at this repo:

```json
{
  "mcpServers": {
    "uml-mcp": {
      "command": "uv",
      "args": ["run", "python", "-u", "server.py"],
      "cwd": "/absolute/path/to/uml-mcp",
      "env": {
        "KROKI_SERVER": "https://kroki.io",
        "MCP_OUTPUT_DIR": "output",
        "MCP_DIAGRAM_FALLBACK": "true"
      }
    }
  }
}
```

Prefer the **hosted HTTP** path unless you need local `output_dir` writes.

## Showing diagrams in chat

Same rules as other clients: use `generate_uml_image` / PNG when you want an inline image; do not paste local `output/*.png` paths into markdown. See [Cursor chat rendering](cursor.md#showing-diagrams-in-chat-cursor--copilot--claude).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Tools never called | Set Function Calling to **Native** on the model; enable the UML-MCP tool. |
| UI crash / infinite load on import | Connection type must be **MCP**, not OpenAPI, for the hosted `/mcp` URL. |
| Timeouts | Increase Open WebUI MCP / tool timeouts; Mermaid may fall back to mermaid.ink. |
| Ollama alone has no tools | Point Open WebUI or Continue at UML-MCP; bare `ollama run` has no MCP client. |

Config hub: [`config/README.md`](https://github.com/antoinebou12/uml-mcp/blob/main/config/README.md).
