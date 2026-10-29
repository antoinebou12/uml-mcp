# ChatGPT app submission (OpenAI Apps directory)

Submit UML-MCP to the OpenAI Apps directory as the remote server
`https://uml-mcp.antoineboucher.info/mcp`, self-hosted (no Manufact build or hosting).

## Done in this pass

- `submission/openai/` bundle (`plugin.json`, `mcp.json`, logo, demo) customised from
  the Manufact draft: real name, descriptions, production URLs, terms page, accurate
  release notes (there is no feedback tool), one more viewer test case.
- `scripts/build_openai_submission.py` checks the bundle against the tool registry and
  production host and writes a reproducible `dist/uml-mcp-openai-<version>.zip`.
- `/.well-known/openai-apps-challenge` served from `OPENAI_APPS_CHALLENGE_TOKEN`
  (`server.openai_apps_challenge_token`); `/.well-known/terms.txt`.
- Viewer: widget domain + `openai/widgetDescription`, modern UI, SVG fit fix.

## Remaining

- [ ] Upload `dist/uml-mcp-openai-1.4.0.zip` in the OpenAI dashboard.
- [ ] Set `OPENAI_APPS_CHALLENGE_TOKEN` on Vercel (Production), redeploy, `curl` the
      challenge URL, then press Verify.
- [ ] Re-record the demo with the new viewer and update `demo_recording_url`.
