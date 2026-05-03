# Claude Desktop Integration

Connect UML-MCP to Claude Desktop to generate diagrams in chat.

For **Claude Code** (CLI / IDE extension) and the bundled marketplace plugin, see [Claude Code integration](claude_code.md).

## Overview

Claude Desktop connects to UML-MCP as an MCP server so you can generate and view UML and other supported diagram types in chat.

## Setup

### 1. Install UML-MCP

Install the server on your machine. See [Installation](../installation.md).

### 2. Claude Desktop Configuration

Claude Desktop requires specific configuration to connect to the UML-MCP server:

1. Open Claude Desktop
2. Go to Settings (gear icon) → Advanced → MCP Servers
3. Add a new MCP server with the following details:
   - **Name**: `uml-mcp` (or any label; must match the JSON key under `mcpServers`)
   - **Command**: `python` (or the full path to your Python executable)
   - **Arguments**: `-u` and `server.py` (working directory must be the repo root so `server.py` resolves)
   - **Working Directory**: absolute path to your `uml-mcp` clone
   - Optional environment: `KROKI_SERVER`, `MCP_OUTPUT_DIR`, `MCP_DIAGRAM_FALLBACK` (see [Configuration](../configuration.md))

Example configuration (see also **`config/claude_desktop_config.json`** and **`config/README.md`** in the repo):

```json
{
  "mcpServers": {
    "uml-mcp": {
      "command": "python",
      "args": ["-u", "server.py"],
      "cwd": "/path/to/uml-mcp",
      "env": {
        "KROKI_SERVER": "https://kroki.io",
        "MCP_OUTPUT_DIR": "output",
        "MCP_DIAGRAM_FALLBACK": "true"
      }
    }
  }
}
```

### 3. Test the Integration

1. Restart Claude Desktop after saving the configuration
2. In a new conversation, ask Claude to create a UML diagram
3. Claude should be able to generate the diagram using the UML-MCP server

Example prompt:
```
Create a UML class diagram for a simple e-commerce system with Customer, Product, and Order classes.
```

## Troubleshooting

### Server Connection Issues

If Claude Desktop cannot connect to the UML-MCP server:

1. Verify the server is running by launching it manually first
2. Check paths in your configuration are correct and absolute
3. Ensure you have the required permissions for the directories
4. Check Claude Desktop logs for connection errors

### Diagram Generation Problems

If diagrams aren't being generated correctly:

1. Verify the UML-MCP server is running without errors
2. Check the output directory permissions
3. Try generating different diagram types to isolate the issue
4. Verify that all required dependencies are installed

## Advanced configuration

### Custom Templates

You can customize how diagrams appear in Claude Desktop by modifying the templates in the UML-MCP server. See [Advanced Configuration](../configuration.md#custom-templates) for details.

### Output Formats

Claude Desktop works best with SVG and PNG formats. You can specify the preferred format in your prompts to Claude or configure defaults in the UML-MCP server.

## Related resources

- [Configuration Options](../configuration.md)
- [UML Diagram Examples](../examples.md)
- [Supported Diagram Types](../diagrams/uml.md)
