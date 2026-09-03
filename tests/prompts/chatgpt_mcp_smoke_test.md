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

## What this catches

This manual fixture is intentionally stricter than a health check. It catches cases where `/health` works but the MCP client cannot discover tools, cannot validate inputs, cannot invoke Kroki-backed rendering, cannot show an inline image, omits playground/URL links, uses local file paths in markdown, or silently answers without using the MCP server.

Canonical agent workflow for presenting results: [`.skill/skills/uml-mcp-diagrams/SKILL.md`](../../.skill/skills/uml-mcp-diagrams/SKILL.md).
