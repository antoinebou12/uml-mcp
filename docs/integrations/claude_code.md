# Claude Code integration

Install UML-MCP as a **Claude Code plugin** to get the hosted HTTP MCP server plus a diagram skill, without editing `settings.json` by hand.

## What you get

| Piece | Purpose |
| --- | --- |
| **MCP server `uml-mcp`** | Streamable HTTP to `https://uml-mcp.vercel.app/mcp` — tools such as `generate_uml`, `validate_uml`, `list_diagram_types`, `generate_uml_batch` |
| **Skill `uml-diagrams`** | Invoked as **`/uml-mcp:uml-diagrams`** (plugin name + skill name) for URL-first diagram workflows |

Plugin sources live under [`plugins/uml-mcp/`](https://github.com/antoinebou12/uml-mcp/tree/main/plugins/uml-mcp) in this repository. The catalog file is [`.claude-plugin/marketplace.json`](https://github.com/antoinebou12/uml-mcp/tree/main/.claude-plugin/marketplace.json).

## Prerequisites

- [Claude Code](https://code.claude.com/docs) installed, with the `claude` CLI available in your shell.

## Add the marketplace

Pick **one** source (path or Git URL).

=== "Local clone"

    From the directory that contains **`.claude-plugin/marketplace.json`** (the repo root):

    ```bash
    /plugin marketplace add /absolute/path/to/uml-mcp
    ```

    On Windows, use a path such as `C:\Users\you\uml-mcp`.

=== "GitHub"

    ```bash
    /plugin marketplace add https://github.com/antoinebou12/uml-mcp
    ```

    For a large monorepo you can limit checkout size:

    ```bash
    /plugin marketplace add https://github.com/antoinebou12/uml-mcp --sparse .claude-plugin plugins
    ```

## Install the plugin

```bash
/plugin install uml-mcp@uml-mcp-plugins
```

Enable the plugin if Claude Code prompts you to, then restart the session if required so MCP tools appear.

## Optional checks

Validate the plugin or marketplace manifests from a shell (not inside the Claude Code slash UI):

```bash
claude plugin validate /path/to/uml-mcp/plugins/uml-mcp
claude plugin validate /path/to/uml-mcp
```

## Custom MCP URL

The default plugin ships HTTP MCP pointing at the public deployment. To use another endpoint, either:

1. Edit **`plugins/uml-mcp/.mcp.json`** in your clone and reinstall or update the plugin from that clone, or  
2. Keep using [manual MCP configuration](../configuration.md) in Claude Code settings instead of the plugin.

The plugin directory is copied into Claude Code’s plugin cache when installed, so changes apply after you bump the plugin **`version`** in **`plugins/uml-mcp/.claude-plugin/plugin.json`** (and reinstall/update) or reinstall from a branch that contains your edits.

## Related resources

- [Claude Desktop](claude_desktop.md) — MCP via app settings (not the plugin system)
- [Configuration](../configuration.md)
- [Getting started](../tutorials/getting-started.md)
