# Diagram rendering fallback

UML-MCP tries **Kroki** first for rendering. If Kroki fails or is unreachable, the pipeline may fall back to a **PlantUML server** (for PlantUML-family diagrams) or **Mermaid.ink** (for Mermaid). Responses may include a `source` field (`kroki`, `plantuml_server`, or `mermaid_ink`) naming the backend that produced the image.

All three backends can be self-hosted:

| Backend | Setting | Self-hosted with |
| --- | --- | --- |
| Kroki | `KROKI_SERVER` / `USE_LOCAL_KROKI` | Docker compose (default stack), Helm `kroki.enabled` |
| PlantUML server | `PLANTUML_SERVER` / `USE_LOCAL_PLANTUML` | Docker compose `--profile plantuml`, Helm `plantuml.enabled` |
| mermaid.ink | `MERMAID_INK_SERVER` / `USE_LOCAL_MERMAID_INK` | Docker compose `--profile mermaid-ink`, Helm `mermaidInk.enabled` |

See [Docker](deploy/docker.md) and [Kubernetes (Helm)](enterprise/kubernetes.md#in-cluster-renderers-optional).

For environment variables, local servers, and tuning, see **[Configuration](configuration.md)** and the **Fallback strategy** section in the [README](https://github.com/antoinebou12/uml-mcp/blob/main/README.md).
