# Diagram rendering fallback

UML-MCP tries **Kroki** first for rendering. If Kroki fails or is unreachable, the pipeline may fall back to a **PlantUML server** (for PlantUML-family diagrams) or **Mermaid.ink** (for Mermaid). Successful responses can include a `source` field (`kroki`, `plantuml_server`, or `mermaid_ink`) indicating which backend produced the image.

For environment variables, local servers, and tuning, see **[Configuration](configuration.md)** and the **Fallback strategy** section in the [README](https://github.com/antoinebou12/uml-mcp/blob/main/README.md).
