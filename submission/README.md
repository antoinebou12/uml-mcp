# Store submissions

| Folder | Store | Build |
| --- | --- | --- |
| [`openai/`](openai/) | OpenAI Apps directory (ChatGPT) | `uv run python scripts/build_openai_submission.py` |

The OpenAI bundle follows the agent-plugins.org 1.0.0 layout (`plugin.json`,
`mcp.json`, `assets/`). Domain verification is served by the app itself at
`/.well-known/openai-apps-challenge` from `OPENAI_APPS_CHALLENGE_TOKEN`.

Full walkthrough: [ChatGPT app submission](../docs/integrations/chatgpt_app_submission.md).
