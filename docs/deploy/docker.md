---
title: Docker
description: "Run UML-MCP in Docker: full stack with bundled Kroki, Mermaid, and BlockDiag, plain HTTP, or stdio MCP."
tags:
  - docker
  - deploy
---

# Docker

The repo includes a `Dockerfile` and a `docker-compose.yml` that gets you a full local stack: UML-MCP (FastAPI + MCP HTTP at `/mcp`), local Kroki, Mermaid, and BlockDiag. Everything stays on your machine, which suits air-gapped networks, CI runners, or shared infra where you do not want to depend on `kroki.io`.

## Full local stack (compose)

```bash
docker compose up -d
```

This brings up:

- `uml-mcp`: FastAPI on port `8000` with MCP HTTP at `http://127.0.0.1:8000/mcp`.
- `kroki`: local Kroki gateway.
- `mermaid` and `blockdiag`: companion services Kroki delegates to.

Stop the stack:

```bash
docker compose down
```

## Optional local PlantUML

The compose file ships a `plantuml-server` service behind an opt-in profile, so it is not
started by a plain `docker compose up`:

```bash
docker compose --profile plantuml up -d
```

That adds one container, `plantuml/plantuml-server:jetty-v1.2026.6`, published on host port
`8002` (`8000` and `8001` are already taken by `uml-mcp` and `kroki`). It has an HTTP health
check, so `docker compose ps` reports `healthy` once Jetty is serving.

### Making UML-MCP actually use it

PlantUML is a **fallback** renderer: UML-MCP tries Kroki first and only reaches for PlantUML
when Kroki fails (see [Fallback strategy](../fallback-mechanism.md)). The compose stack runs
with a local Kroki and therefore disables the fallback chain by default. Starting the profile
on its own changes nothing about how diagrams are rendered — you also need to turn the chain
back on:

```bash
MCP_DIAGRAM_FALLBACK=true USE_LOCAL_PLANTUML=true docker compose --profile plantuml up -d
```

`USE_LOCAL_PLANTUML`, `PLANTUML_SERVER` and `MCP_DIAGRAM_FALLBACK` are passed through from
your shell with the previous defaults (`false`, `http://plantuml-server:8080`, `false`), so
omitting them leaves today's behavior exactly as it was.

A successful PlantUML render reports `"source": "plantuml_server"` in the tool response.

### Fully offline

Local Kroki plus local PlantUML means no outbound calls for any supported diagram type:

```bash
MCP_DIAGRAM_FALLBACK=true USE_LOCAL_PLANTUML=true docker compose --profile plantuml up -d
```

Without the profile, the `PLANTUML_SERVER` default points at a `plantuml-server` host that
does not exist in the default stack — so the fallback simply fails and the Kroki error is
returned, which is the current behavior.

## API + MCP only (public Kroki)

If you don't need a local Kroki and want a single small image:

```bash
docker build -t uml-mcp .
docker run -p 8000:8000 uml-mcp
```

The container reaches out to `https://kroki.io` by default. Override with environment variables (see below).

## stdio MCP subprocess

Some clients prefer to spawn a stdio MCP process. The same image works:

```bash
docker run -i uml-mcp python server.py --transport stdio
```

Add `-v "$(pwd)/output:/app/output"` if you need diagrams written to your host filesystem.

## Environment variables

The Docker image reads the same variables as the local server. The most useful for Docker:

| Variable | Description | Default |
| --- | --- | --- |
| `KROKI_SERVER` | Kroki gateway URL | `https://kroki.io` |
| `PLANTUML_SERVER` | PlantUML server URL (fallback); resolves to the `plantuml` profile service | `http://plantuml-server:8080` |
| `USE_LOCAL_KROKI` | Use a local Kroki instance (`true`/`false`) | `false` |
| `USE_LOCAL_PLANTUML` | Use a local PlantUML instance (`true`/`false`) | `false` |
| `MCP_OUTPUT_DIR` | Where to write rendered diagrams | `./output` |
| `MCP_READ_ONLY` | Reject `output_dir` (read-only mode) | `false` |
| `MCP_DIAGRAM_FALLBACK` | Enable the PlantUML / Mermaid.ink fallback chain | (auto) |

Full table: [Configuration](../configuration.md).

## Compose snippet: bring your own backends

```yaml
services:
  uml-mcp:
    image: uml-mcp:latest
    build: .
    ports:
      - "8000:8000"
    environment:
      KROKI_SERVER: http://kroki:8000
      USE_LOCAL_KROKI: "true"
      MCP_OUTPUT_DIR: /app/output
    volumes:
      - ./output:/app/output
    depends_on:
      - kroki

  kroki:
    image: yuzutech/kroki:latest
    ports:
      - "8001:8000"
```

!!! tip "CI / GitHub Actions"

    The image is small and starts in seconds. Use it inside a job to render diagrams as part of a build pipeline: call `POST /generate_diagram` (REST) or use MCP HTTP at `/mcp`. See [Fallback strategy](../fallback-mechanism.md) if Kroki is unreachable from your CI network.

## Troubleshooting

- **`Connection refused` to `kroki:8000`**: start the `kroki` service (`docker compose up -d kroki`) or set `USE_LOCAL_KROKI=false` to fall back to the public gateway.
- **`output_dir` rejected**: the container has `MCP_READ_ONLY=true` set somewhere; unset it or omit `output_dir` and use the URL/base64 response instead.
- **Slow first render**: Kroki cold-starts the per-diagram engine on first use; subsequent renders are fast.

See [Configuration](../configuration.md) for the full env table and [Vercel & Smithery](../integrations/vercel_smithery.md) for the hosted deployment alternative.
