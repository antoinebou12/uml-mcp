# Deploy to Vercel

Connect a Vercel project to this repository and deploy using `vercel.json`.
The MCP endpoint is `https://<your-project>.vercel.app/mcp`.
Keep enterprise authentication disabled on Vercel.

## Connect a client

Configure a Streamable HTTP connection with the `/mcp` URL. The public endpoint is
`https://uml-mcp.vercel.app/mcp`. See [Cursor](cursor.md) for a client example.

## Discovery

The build runs `python -m mcp_core.build_static_server_card` to generate static
server discovery files in `public/.well-known/mcp/`. The server card and
`config-schema.json` must be reachable under `/.well-known/mcp/`.
The canonical session schema is `mcp-config-schema.json` in the repository root.

## Troubleshooting

- If the MCP handshake returns an HTML login page, check Vercel Deployment Protection
  and allow public access to the intended deployment.
- A 404 or 405 on discovery URLs can indicate missing static build output. Check
  that the deployment includes `public/.well-known/mcp/server-card.json`.
- Configure clients to POST to `/mcp`, not the domain root or server card URL.
- Serverless execution limits can end long sessions. Reconnect, or use a
  [Docker deployment](../deploy/docker.md) for a long-running server.

The deployment workflow waits for Vercel and runs MCP conformance checks.
