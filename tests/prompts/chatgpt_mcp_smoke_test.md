# ChatGPT MCP smoke-test prompt

Use this prompt after connecting the UML MCP server at:

`https://uml-mcp.vercel.app/mcp`

The purpose is to verify that an MCP client can discover the UML tools, validate diagram source, and render a real diagram through the server.

## End-to-end smoke-test prompt

Copy and paste the following prompt into an MCP-enabled ChatGPT conversation:

```text
Use the connected UML MCP server for this entire test. Do not generate or render the diagram yourself, and do not substitute built-in diagram knowledge for MCP tool calls.

Perform these steps in order:

1. Call `list_diagram_types` and confirm that `mermaid` is supported.
2. Call `validate_uml` with:
   - diagram_type: `mermaid`
   - output_format: `svg`
   - strict: `true`
   - code:

     sequenceDiagram
       participant User
       participant ChatGPT
       participant UMLMCP as UML MCP
       participant Kroki
       User->>ChatGPT: Create OAuth login diagram
       ChatGPT->>UMLMCP: generate_uml(...)
       UMLMCP->>Kroki: Render Mermaid
       Kroki-->>UMLMCP: SVG
       UMLMCP-->>ChatGPT: Diagram result
       ChatGPT-->>User: Show result

3. Only if validation succeeds, call `generate_uml` using the same Mermaid code with:
   - diagram_type: `mermaid`
   - output_format: `svg`
   - scale: `1.0`
4. Report the exact MCP tools you called.
5. Confirm whether the generated result contains a usable URL, SVG/result payload, or another successful diagram artifact returned by the MCP server.
6. End with exactly one of these lines:

MCP_SMOKE_TEST: PASS
MCP_SMOKE_TEST: FAIL - <short reason>
```

## Expected result

The test passes only when all of the following are true:

- the MCP connection exposes `list_diagram_types`;
- Mermaid appears in the supported diagram catalog;
- `validate_uml` accepts the Mermaid sequence diagram;
- `generate_uml` is actually invoked;
- the server returns a successful diagram result rather than the client inventing one locally;
- the final response contains `MCP_SMOKE_TEST: PASS`.

## Batch smoke-test prompt

Use this after the end-to-end test passes:

```text
Use only the connected UML MCP server for diagram rendering.

Call `generate_uml_batch` once with two Mermaid diagrams and SVG output:

1. `graph TD; Client-->MCP; MCP-->Kroki; Kroki-->MCP; MCP-->Client;`
2. `sequenceDiagram; participant A; participant B; A->>B: MCP 2026 request; B-->>A: Stateless response;`

Do not render them yourself. Report the number of successful batch results and finish with exactly:

MCP_BATCH_TEST: PASS

If either result fails, finish with:

MCP_BATCH_TEST: FAIL - <short reason>
```

## What this catches

This manual fixture is intentionally stricter than a health check. It catches cases where `/health` works but the MCP client cannot discover tools, cannot validate inputs, cannot invoke Kroki-backed rendering, or silently answers without using the MCP server.
