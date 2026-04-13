# Cursor Integration

This guide explains how to integrate UML-MCP with Cursor for generating diagrams directly in your editor.

## Overview

Cursor can connect to the UML-MCP server through the Model Context Protocol (MCP), allowing you to generate and visualize UML diagrams and other supported diagram types while you code.

## Setup Instructions

### 1. Install and Configure UML-MCP

Make sure you have the UML-MCP server properly installed and configured on your system. See the [Installation](../installation.md) guide for details.

### 2. Cursor Configuration

1. Open the MCP config for Cursor (or use **Cursor Settings → MCP**):
   - **Windows:** `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json`
   - **macOS:** `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/mcp.json`
   - **Linux:** `~/.config/Cursor/User/globalStorage/cursor.mcp/mcp.json`

2. Merge the `mcpServers` block from **[`config/cursor_config.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/cursor_config.json)** in this repo, or copy the same structure from **[`config/README.md`](https://github.com/antoinebou12/uml-mcp/blob/main/config/README.md)**. The example uses server key **`uml-mcp`**, **`args`**: `["-u", "server.py"]` (relative to **`cwd`**), and **`env`** for `KROKI_SERVER`, `MCP_OUTPUT_DIR`, and `MCP_DIAGRAM_FALLBACK`. Set **`cwd`** to your repo root (the sample uses `${workspaceFolder}` if your Cursor build expands it; otherwise use an absolute path). See [Configuration](../configuration.md) for environment variables.

### 3. Test the Integration

1. Restart Cursor after saving the configuration
2. In a conversation with Cursor, ask it to create a UML diagram
3. Cursor should be able to generate the diagram using the UML-MCP server

Example prompt:
```
Create a UML class diagram for the current project structure.
```

## Troubleshooting

### Server Connection Issues

If Cursor cannot connect to the UML-MCP server:

1. Verify the server is running by launching it manually first
2. Check paths in your configuration are correct and absolute
3. Ensure you have the required permissions for the directories
4. Check Cursor logs for connection errors

### Diagram Generation Problems

If diagrams aren't being generated correctly:

1. Verify the UML-MCP server is running without errors
2. Check the output directory permissions
3. Try generating different diagram types to isolate the issue
4. Verify that all required dependencies are installed

## Advanced Configuration

### Custom Templates

You can customize how diagrams appear in Cursor by modifying the templates in the UML-MCP server. See [Advanced Configuration](../configuration.md#custom-templates) for details.

### Output Formats

Cursor works well with SVG and PNG formats. You can specify the preferred format in your prompts or configure defaults in the UML-MCP server.

## Related Resources

- [Configuration Options](../configuration.md)
- [UML Diagram Examples](../examples.md)
- [Supported Diagram Types](../diagrams/uml.md)
