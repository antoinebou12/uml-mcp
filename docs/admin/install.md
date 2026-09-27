---
title: Install the admin console
description: "Install UML-MCP and open its admin console locally or on a server, run Kroki with every companion in Docker, and troubleshoot access."
---

# Install the admin console

The console ships inside the `uml-mcp` package. Its web assets are prebuilt, so you don't
need Node. This page gets you from nothing to a working console with a local Kroki. The
[user guide](user-guide.md) then walks through each task.

## 1. Requirements

| Need | For | Check |
| --- | --- | --- |
| Python 3.12+ and [uv](https://docs.astral.sh/uv/) (or pip) | UML-MCP and the console | `uv --version` |
| A browser | The console | Any recent Chromium, Firefox or Safari |
| Docker with Compose v2 (optional) | A local Kroki that renders **every** diagram type offline | `docker compose version` |

Without Docker the console still works. Rendering then uses the Kroki in
`rendering.kroki_server` (the public `https://kroki.io` by default).

## 2. Install UML-MCP

=== "uv (recommended)"

    ```bash
    uv tool install uml-mcp
    ```

=== "pip"

    ```bash
    pip install uml-mcp
    ```

=== "From a checkout"

    ```bash
    git clone https://github.com/antoinebou12/uml-mcp && cd uml-mcp
    uv sync
    ```

## 3. Open the console

### On your machine (local mode)

```bash
uml-mcp admin
```

- **Where it runs:** `http://127.0.0.1:8765/admin/#/overview`, which opens in your browser.
- **Setup token:** printed in the terminal, and carried in the link as `?token=`. The token is
  what lets you save; without it the console is read-only.
- **Fixed token:** set `UML_MCP_ADMIN_TOKEN` before starting to choose your own.
- **Loopback only:** the console binds to `127.0.0.1`. Requests from other machines, or with
  a non-local `Host` header, are refused.
- **Other options:** `uml-mcp admin --port 9000` and `--no-open` (don't open a browser).
  `uml-mcp setup --web` starts on the Setup page.

### On a server

A server started with `uvicorn app:app` (Docker image, Helm chart) serves the same console
at `/admin`:

| Server | Console access |
| --- | --- |
| Auth off (`MCP_AUTH_MODE` unset) | Only when `admin.allow_local_without_auth: true`, and then from loopback only, for example through `ssh -L 8000:127.0.0.1:8000 server` |
| Enterprise SSO (`MCP_AUTH_MODE=jwt` / `entra-proxy`) | Users with the `MCP.Admin` app role. Changes also need `admin.allow_write: true`, and Stop needs `admin.allow_stop: true` |

Enterprise setup is covered in [Enterprise](../enterprise/README.md) and the
[admin UI reference](../enterprise/admin-ui.md).

## 4. Run Kroki with every companion (Docker)

Kroki is the renderer behind every tool. The core image handles most types. Mermaid,
blockdiag (plus seqdiag, actdiag, nwdiag…), BPMN and Excalidraw need **companion**
containers. One command starts all five on the loopback interface and points UML-MCP at
them:

```bash
uml-mcp kroki up --use        # first run pulls ~10 GB of images; later starts take seconds
uml-mcp kroki status          # Docker, containers and one real render per companion
```

```text
Docker: Docker 29.3.1
  blockdiag   running   Up 2 minutes
  bpmn        running   Up 2 minutes
  excalidraw  running   Up 2 minutes
  kroki       running   Up 2 minutes
  mermaid     running   Up 2 minutes
Kroki 0.32.1 at http://127.0.0.1:8001: reachable
  ok  mermaid     ok
  ok  blockdiag   ok
  ok  bpmn        ok
  ok  excalidraw  ok
```

| Command | Does |
| --- | --- |
| `uml-mcp kroki up [--port 8001] [--use]` | Writes `~/.config/uml-mcp/kroki/compose.yml` and starts Kroki with every companion (Compose project `uml-mcp-kroki`). `--use` saves `rendering.kroki_server` |
| `uml-mcp kroki status [--url URL]` | Checks the configured (or given) Kroki: `/health` plus a real render per companion. Exits 1 if anything fails |
| `uml-mcp kroki logs [--tail N]` | Container logs |
| `uml-mcp kroki down` | Stops and removes the containers |

- **Same from the console:** the **Kroki** page has **Start all & use** and **Stop**
  buttons (local mode, with the setup token).
- **Why not `/health`?** Kroki's `/health` only covers the core server. The companion
  checks render a real diagram, because companions can be missing or still starting.
- **From a checkout:** `docker compose --profile kroki-extra up -d` starts the same stack,
  with the MCP server in a container.

Kroki is published on `127.0.0.1` only. Enterprise deployments run Kroki next to the server
(Helm or `docker-compose.yml`), and there the console only reports its health.

## 5. Check the install

1. Open the console. **Overview** shows the server as running.
2. Open **Kroki**. The server is **reachable**, and all four companions are **ok**.
3. In **Playground**, pick `mermaid` and press **Render**. A diagram appears.

![Kroki page with every companion ok and a rendered diagram](../assets/admin/desktop-kroki-playground.png)

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `403 Host must be localhost` | You opened the console through a hostname. Use `http://127.0.0.1:8765` or `http://localhost:8765` |
| `404` on `/admin` of a server | Auth is off and `admin.allow_local_without_auth` is not `true`, or the request didn't come from loopback |
| Buttons are disabled, "Enter the setup token" | Use the link printed by `uml-mcp admin`, or paste the token into the key icon in the top bar |
| `docker is not installed` / `the Docker daemon is not running` | Install Docker Desktop or Engine, start it, then run `uml-mcp kroki up` again |
| `port is already allocated` | Another service uses 8001: `uml-mcp kroki up --port 8002 --use` |
| A companion shows `HTTP 500` right after start | It is still starting. Run `uml-mcp kroki status` again after a few seconds; `up` already waits up to 5 minutes |
| `KROKI_SERVER is set by the environment` (409) | An environment variable wins over `uml-mcp.yaml`. Change or unset it where the server is started |
| Rendering works in the playground but not in a client | The client talks to another server process; check that process's **Kroki** page |
