# PlantUML JAR (optional)

UML-MCP can fall back to a **local** `plantuml.jar` when Kroki fails for
PlantUML-family diagrams. Diagram source stays on your machine (no PlantUML HTTP
server required).

```bash
uv run python scripts/download_plantuml_jar.py
```

That writes `plantuml.jar` here. Leave `PLANTUML_JAR_PATH` unset to auto-detect
this path, or point it at another JAR. Java 11+ must be on `PATH` (or set
`JAVA_PATH` / `JAVA_HOME`).
