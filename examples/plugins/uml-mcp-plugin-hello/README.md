# uml-mcp-plugin-hello

Example plugin for [UML-MCP](https://github.com/antoinebou12/uml-mcp): one MCP
tool (`hello_echo`) and one renderer (`ascii` diagram type).

```bash
uv pip install -e examples/plugins/uml-mcp-plugin-hello   # next to uml-mcp
uml-mcp plugins list
uml-mcp plugins enable hello
uml-mcp plugins enable ascii
```

Then restart the server. `hello_echo` shows up in `tools/list`, and
`generate_uml(diagram_type="ascii", code="+--+\n|hi|\n+--+", output_format="svg")`
renders locally. See the [plugin author guide](../../../docs/plugins/authoring.md).
