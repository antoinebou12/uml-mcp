# ChatGPT / Cursor MCP smoke-test prompt

Use this prompt after connecting the UML MCP server at:

`https://uml-mcp.vercel.app/mcp`

The purpose is to verify that an MCP client can discover the UML tools, validate diagram source, render a real diagram through the server, show an inline image in chat, and surface both the diagram **URL** and **Playground** links.

## End-to-end smoke-test prompt

Copy and paste the following prompt into an MCP-enabled ChatGPT, Cursor, Copilot, or Claude conversation:

```text
Use the connected UML MCP server for this entire test. Do not generate or render the diagram yourself, and do not substitute built-in diagram knowledge for MCP tool calls. Do not link local filesystem paths such as output/*.png.

Perform these steps in order:

1. Call `list_diagram_types` and confirm that `mermaid` is supported. Note whether `goat` and `umlet` appear (informational; do not fail only for catalog drift).
2. Call `validate_uml` with:
   - diagram_type: `mermaid`
   - output_format: `svg`
   - strict: `true`
   - code (newline-separated sequenceDiagram; do NOT pack with `;` on one line):

     sequenceDiagram
       participant Client
       participant Server
       Client->>Server: request
       Server-->>Client: response

3. Only if validation succeeds, call `generate_uml` using the same Mermaid code with:
   - diagram_type: `mermaid`
   - output_format: `svg`
   - scale: `1.0`
4. Prefer `generate_uml_image` with the same Mermaid code and `output_format: png`. If that tool is missing from the client tool list, call `generate_uml` again with `output_format: png` instead (raster force-fetch path).
5. In your reply to the user, present exactly this shape (fill from the MCP tool result; do not invent URLs):
   - show the diagram image (MCP image content, or markdown ![diagram](<url>) from the tool text)
   - **URL:** <https url from the tool>
   - **Playground:** <https playground from the tool, required when present>
   - a fenced ```mermaid copy of the source
6. Report the exact MCP tools you called.
7. End with exactly one of these lines:

MCP_SMOKE_TEST: PASS
MCP_SMOKE_TEST: FAIL - <short reason>
```

## Expected result

The test passes only when all of the following are true:

- the MCP connection exposes `list_diagram_types` and at least one of `generate_uml_image` or `generate_uml`;
- Mermaid appears in the supported diagram catalog;
- `validate_uml` accepts the multiline Mermaid Client/Server sequence;
- `generate_uml` (svg) succeeds and returns a usable HTTPS `url`;
- an inline image is shown (via `generate_uml_image` / `content_base64` / ImageContent, or `generate_uml` png, or markdown `![diagram](url)` from the tool);
- when the tool returns `playground`, the assistant reply includes a **Playground** markdown link (typically mermaid.live);
- no local `output/*.png` paths are used;
- the server produced the artifact (the client did not invent the diagram);
- the final response contains `MCP_SMOKE_TEST: PASS`.

## Batch smoke-test prompt

Use this after the end-to-end test passes:

```text
Use only the connected UML MCP server for diagram rendering.

Call `generate_uml_batch` once with two Mermaid diagrams and SVG output:

1. `graph TD; Client-->MCP; MCP-->Kroki; Kroki-->MCP; MCP-->Client;`
2. Multiline sequence diagram (do not pack statements with `;` on one line):

sequenceDiagram
  participant A
  participant B
  A->>B: MCP 2026 request
  B-->>A: Stateless response

Do not render them yourself. For each successful item, note whether `url` and `playground` are present. Report the number of successful batch results and finish with exactly:

MCP_BATCH_TEST: PASS

If either result fails, finish with:

MCP_BATCH_TEST: FAIL - <short reason>
```

## Interactive plugins smoke-test prompt

Checks the four bundled plugins (on by default): real logos, step numbers, presets,
sequence autonumbering, grouped `N×` blocks and flow direction, through both the chat image
path (clients without MCP Apps) and the interactive HTML page (MCP App viewer).

```text
Use the connected UML MCP server for this entire test. Do not draw any diagram yourself.

1. Call `list_diagram_types`. Confirm these types are listed: stack_diagram, archify_architecture,
   archify_sequence, d3_architecture, llm_2d, llm_3d. If any is missing, report it and continue
   with the rest; do not invent a renderer.
2. For each source below, call `validate_uml` (output_format `svg`), then `generate_uml_image`
   with the same diagram_type and code. Keep each source exactly as written:
   - stack_diagram: {"title":"SaaS stack","groups":[{"id":"vercel","name":"Vercel","icon":"vercel"}],"nodes":[{"id":"user","name":"User","role":"browser","icon":"user"},{"id":"web","name":"Next.js","role":"frontend","icon":"browser","group":"vercel"},{"id":"db","name":"Neon","role":"postgres","icon":"database"},{"id":"ci","name":"GitHub Actions","role":"ci"}],"edges":[{"from":"user","to":"web","label":"HTTPS","step":1},{"from":"web","to":"db","label":"SQL","step":2},{"from":"ci","to":"web","label":"deploy","style":"dashed"}]}
   - archify_architecture: {"title":"Platform","preset":"blueprint","groups":[{"id":"sec","name":"Security","style":"security","icon":"shield"},{"id":"be","name":"Backend","style":"backend","icon":"server"}],"nodes":[{"id":"auth","name":"Auth","role":"OIDC","group":"sec","tag":"platform"},{"id":"api","name":"API","role":"REST","group":"be","tag":"app team"},{"id":"llm","name":"Claude","role":"reasoning"}],"edges":[{"from":"auth","to":"api","label":"token","style":"dashed"},{"from":"api","to":"llm","label":"prompt"}]}
   - archify_sequence: {"title":"Cache miss","autonumber":true,"participants":[{"id":"web","name":"Web","icon":"browser"},{"id":"api","name":"API","icon":"api"},{"id":"db","name":"Postgres","icon":"database"}],"messages":[{"from":"web","to":"api","label":"GET /dashboard"},{"from":"api","to":"db","label":"SELECT"},{"from":"db","to":"api","label":"rows","style":"dashed"},{"from":"api","to":"web","label":"200 OK","style":"dashed"}]}
   - d3_architecture: {"title":"AI app","nodes":[{"id":"edge","label":"Edge","service":"tech:cloudflare"},{"id":"app","label":"App","service":"tech:vercel"},{"id":"agent","label":"Agent","service":"tech:langgraph"},{"id":"claude","label":"Claude","service":"tech:claude"},{"id":"gpt","label":"GPT","service":"tech:openai"}],"links":[{"from":"edge","to":"app","label":"HTTPS"},{"from":"app","to":"agent"},{"from":"agent","to":"claude"},{"from":"agent","to":"gpt"}]}
   - llm_2d: {"title":"Autoencoder","layout":"flow","direction":"TB","layers":[{"id":"x","label":"x","kind":"vector","shape":[784]},{"id":"enc","label":"Encoder","kind":"encoder"},{"id":"z","label":"z","kind":"bottleneck","shape":[32]},{"id":"dec","label":"Decoder","kind":"decoder"},{"id":"xr","label":"x'","kind":"vector","shape":[784]}]}
   - llm_3d: {"title":"Transformer","groups":[{"id":"blk","label":"Block","repeat":12,"color":"#818cf8"}],"layers":[{"id":"emb","label":"Embedding","kind":"embedding"},{"id":"att","label":"Attention","kind":"attention","group":"blk"},{"id":"ffn","label":"Feed forward","kind":"feedforward","group":"blk"},{"id":"out","label":"Logits","kind":"output"}]}
3. Show each returned image. For stack_diagram, d3_architecture and archify_architecture, state
   which brand logos are visible (expected: GitHub and Vercel; Cloudflare, Vercel, LangGraph, Claude
   and OpenAI; Claude). For stack_diagram, confirm the numbered step badges 1 and 2. For
   archify_sequence, confirm the labels start with 1. to 4.
4. Call `generate_uml` for archify_architecture with `output_format: html`. If this client shows
   MCP Apps, open it: click the API node (the detail panel opens), shift-click Claude (a path
   appears), switch the preset to flow and the theme to light. Otherwise say MCP App: UNAVAILABLE.
5. Call `generate_uml_image` for stack_diagram again with `theme: light` and confirm the
   background is light.
6. Report a table: diagram_type | validate | image | logos/badges seen | notes.
7. End with exactly one of these lines:

PLUGIN_SMOKE_TEST: PASS
PLUGIN_SMOKE_TEST: FAIL - <short reason>
```

`tests/test_chatgpt_mcp_smoke_prompt.py` validates and renders every source in this prompt, so
a passing test suite means a failure here is the client or the deployment, not the prompt.

## What this catches

This manual fixture is intentionally stricter than a health check. It catches cases where `/health` works but the MCP client cannot discover tools, cannot validate inputs, cannot invoke Kroki-backed rendering, cannot show an inline image, omits playground/URL links, uses local file paths in markdown, or silently answers without using the MCP server.

Canonical agent workflow for presenting results: [`.skill/skills/uml-mcp-diagrams/SKILL.md`](../../.skill/skills/uml-mcp-diagrams/SKILL.md).

## Automated run (no chat model)

`scripts/run_mcp_smoke.py` runs the same steps, and the batch prompt, with a real MCP
client. It prints `MCP_SMOKE_TEST: PASS|FAIL` and `MCP_BATCH_TEST: PASS|FAIL`, and
exits with 0 only when both pass.

It checks the rendered output, not just the links:

- The SVG must parse and show `Client`, `Server`, `request` and `response`.
- The inline image must be a decodable PNG with a real size.
- Each batch SVG must show its labels.

```bash
# in-process server; --offline skips the steps that need Kroki
USE_REAL_FASTMCP=1 MCP_URL_ONLY=true uv run python scripts/run_mcp_smoke.py --offline
# a server backed by a local Kroki (docker compose up -d); diagram URLs are http://
uv run python scripts/run_mcp_smoke.py --url http://127.0.0.1:8000/mcp --allow-http --json smoke.json
# hosted or enterprise (Entra ID) server
uv run python scripts/run_mcp_smoke.py --url https://mcp.contoso.com/mcp --token "$TOKEN"
```

It also checks that strict validation rejects `;`-packed Mermaid, and that the
`architecture_report` prompt is advertised. `tests/test_chatgpt_mcp_smoke_prompt.py`
runs it against the fake, local and public Kroki tiers (see `docs/testing.md`).

## Enterprise (SSO) smoke-test prompt

Use this prompt when the server runs with `MCP_AUTH_MODE=jwt` or `entra-proxy`
(see `docs/enterprise/README.md`):

```text
Use the connected UML MCP server, which requires sign-in (Microsoft Entra ID / OAuth 2.1).

1. If the first call fails with an authentication prompt, complete the sign-in and retry. Report
   whether the client showed a sign-in (HTTP 401 → protected resource metadata → Entra login).
2. Call `list_diagram_types` and `validate_uml` (mermaid, strict, the Client/Server sequence above).
3. Call `generate_uml` with the same code. If the server answers with insufficient scope (HTTP 403),
   accept the additional-permission (mcp.write) prompt and retry once.
4. Never print, paste or summarize the access token or any Authorization header.
5. End with exactly one line:

MCP_AUTH_SMOKE_TEST: PASS
MCP_AUTH_SMOKE_TEST: FAIL - <short reason>
```

Pass criteria: sign-in happened only once, `validate_uml` works with the read scope,
generation works after (at most one) step-up, and no token appears in the transcript.

## App and plugin acceptance

Run [MCP App and plugin acceptance](mcp_apps_plugin_acceptance_test.md) separately
from the baseline tool-count phases. Tool success and valid SVG XML do not prove
visible labels or working downloads. Uninspected cases remain UNVERIFIED.
