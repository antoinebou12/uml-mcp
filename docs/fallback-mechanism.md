# Diagram rendering fallback

UML-MCP tries **Kroki** first for rendering. If Kroki fails or is unreachable, the pipeline may fall back to a **PlantUML server** (for PlantUML-family diagrams) or **Mermaid.ink** (for Mermaid). Responses may include a `source` field (`kroki`, `plantuml_server`, or `mermaid_ink`) naming the backend that produced the image.

## URL-only mode (hosted deployments)

On Vercel the server runs in URL-only mode: it returns a link to the rendered diagram instead of downloading the image, so by default it never contacts Kroki. That made a Mermaid link look successful even when Kroki's Mermaid renderer was down (HTTP 500 or a hang), and the fallback above could never run.

For **Mermaid**, the link is now checked before it is returned. A failed or timed-out check (deadline: `MCP_KROKI_MERMAID_TIMEOUT_SECONDS`, default 8 s) switches the result to a **Mermaid.ink** link, and the response says so:

```json
{
  "source": "mermaid_ink",
  "fallback_used": true,
  "attempts": [
    { "backend": "kroki", "ok": false, "error_summary": "Diagram service timed out (retryable)..." },
    { "backend": "mermaid_ink", "ok": true }
  ]
}
```

Notes:

- The check costs one extra request to Kroki per new Mermaid diagram (results are cached in memory for 300 s). When Kroki's Mermaid renderer hangs, the first diagrams pay up to the deadline in extra latency, then [the circuit breaker](#when-kroki-is-down) skips the check for a while.
- It runs only when `MCP_DIAGRAM_FALLBACK` is on. The repo's `vercel.json` sets it; with it off there is nothing to fall back to, so the Kroki link is returned unchecked as before.
- Other diagram types are not checked; their links come straight from Kroki.

## When Kroki is down

Public `kroki.io` has had outages where its Mermaid renderer accepts a request and never answers (the other renderers keep working). Falling back works, but without more every new Mermaid diagram still waits out `MCP_KROKI_MERMAID_TIMEOUT_SECONDS` (a render, or the link check in URL-only mode) before it does.

UML-MCP therefore remembers the health of the Kroki Mermaid renderer, in memory and per process:

- **Two failures in a row** (timeout, connection error, HTTP 5xx or 429, from a render or from the URL-only link check) open a breaker. While it is open, Mermaid goes straight to mermaid.ink without contacting Kroki, and the response reports `fallback_used: true`; the first attempt entry says Kroki was skipped.
- **A syntax error (HTTP 400, 413, 422) never counts**: the renderer answered, so a bad diagram cannot take Mermaid offline. A 404 does not count either: that is a wrong `KROKI_SERVER`, not an outage.
- **After the cooldown** (`MCP_KROKI_CIRCUIT_COOLDOWN_SECONDS`, default 60 s) Kroki is tried again. One more failure re-opens the breaker; a success closes it.
- It only applies to Mermaid, and only when a fallback exists (`MCP_DIAGRAM_FALLBACK`): without one, skipping Kroki would just replace a slow error with a fast one. Set the cooldown to `0` to turn it off.

For environment variables, local servers, and tuning, see **[Configuration](configuration.md)** and the **Fallback strategy** section in the [README](https://github.com/antoinebou12/uml-mcp/blob/main/README.md).
