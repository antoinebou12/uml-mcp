"""
CLI and Rich UI for the MCP server entry point.
"""

import argparse
import datetime
import logging
import os
import sys

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

# Default to stderr so import-time output never pollutes MCP stdio.
# Switched to stdout in run() for non-stdio transports.
console = Console(stderr=True)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="UML-MCP Diagram Generation Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Server port (default: 8000)"
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--list-tools", action="store_true", help="List available tools and exit"
    )
    return parser.parse_args()


def setup_logging(debug=False):
    """Configure logging based on arguments."""
    level = logging.DEBUG if debug else logging.INFO

    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    date_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"uml_mcp_server_{date_str}.log")

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Always log to stderr, even when the display console targets stdout.
    console_handler = RichHandler(rich_tracebacks=True, console=Console(stderr=True))
    console_handler.setLevel(level)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[console_handler],
        force=True,
    )

    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(file_handler)

    return logging.getLogger(__name__)


def safe_import(module_name, display_name=None):
    """Try to import a module; return None and log error on failure."""
    try:
        return __import__(module_name)
    except ImportError as e:
        display_name = display_name or module_name
        logging.getLogger(__name__).error("Error importing %s: %s", display_name, e)
        return None


def _stdio_ui_enabled() -> bool:
    """Check if human-readable UI is explicitly enabled for stdio transport."""
    return os.environ.get("UML_MCP_STDIO_UI", "").lower() in ("true", "1", "yes")


def _should_render_human_output(transport: str) -> bool:
    """Return True if Rich UI output should be rendered for the given transport."""
    if transport != "stdio":
        return True
    return _stdio_ui_enabled()


def _display_tools_fallback(mcp_settings, tools_table):
    """Fallback method to display tools if decorator system is not available."""
    tool_names = getattr(mcp_settings, "tools", [])

    if tool_names:
        tool_descriptions = {
            "generate_uml": "Generate any UML or diagram by type (class, sequence, mermaid, d2, etc.)",
        }
        tool_parameters = {
            "generate_uml": "diagram_type: str, code: str, output_dir: str, output_format: str, theme: str",
        }
        for tool_name in tool_names:
            if tool_name == "tool_function":
                continue
            description = tool_descriptions.get(
                tool_name, "Generate diagrams based on text descriptions"
            )
            parameters = tool_parameters.get(tool_name, "No parameters info")
            tools_table.add_row(tool_name, description, parameters)
    else:
        tools_table.add_row("No tools found", "Check server configuration", "")


def display_tools(mcp_settings):
    """Display information about available tools in the MCP server."""
    tools_table = Table(title="[bold blue]Available UML-MCP Tools[/bold blue]")
    tools_table.add_column("Tool Name", style="cyan")
    tools_table.add_column("Description", style="green")
    tools_table.add_column("Parameters", style="yellow")

    try:
        from mcp_core.tools.tool_decorator import get_tool_registry

        tool_registry = get_tool_registry()
        if tool_registry:
            for tool_name, tool_info in tool_registry.items():
                if tool_name == "tool_function":
                    continue
                description = tool_info.get("description", "No description available")
                params = tool_info.get("parameters", {})
                param_str = ", ".join(
                    [f"{name}: {info['type']}" for name, info in params.items()]
                )
                tools_table.add_row(tool_name, description, param_str)
        else:
            _display_tools_fallback(mcp_settings, tools_table)
    except ImportError:
        _display_tools_fallback(mcp_settings, tools_table)

    console.print(tools_table)


def _display_prompts_fallback(mcp_settings, prompts_table):
    """Fallback method to display prompts if registry not available."""
    prompt_names = getattr(mcp_settings, "prompts", [])
    if prompt_names:
        prompt_descriptions = {
            "class_diagram": "Create a UML class diagram showing classes, attributes, methods, and relationships",
            "sequence_diagram": "Create a UML sequence diagram showing interactions between objects over time",
            "activity_diagram": "Create a UML activity diagram showing workflows and business processes",
        }
        for prompt_name in prompt_names:
            description = prompt_descriptions.get(prompt_name, "Generate UML diagrams")
            prompts_table.add_row(prompt_name, description)
    else:
        prompts_table.add_row("No prompts found", "Check server configuration")


def display_prompts(mcp_settings):
    """Display information about available prompts in the MCP server."""
    prompts_table = Table(title="[bold blue]Available Prompts[/bold blue]")
    prompts_table.add_column("Prompt Name", style="cyan")
    prompts_table.add_column("Description", style="green")

    try:
        from mcp_core.prompts.diagram_prompts import get_prompt_registry

        prompt_registry = get_prompt_registry()
        if prompt_registry:
            for prompt_name, prompt_info in prompt_registry.items():
                description = prompt_info.get("description", "No description available")
                prompts_table.add_row(prompt_name, description)
        else:
            _display_prompts_fallback(mcp_settings, prompts_table)
    except ImportError:
        _display_prompts_fallback(mcp_settings, prompts_table)

    console.print(prompts_table)


def _display_resources_fallback(mcp_settings, resources_table):
    """Fallback method to display resources if registry not available."""
    resource_names = getattr(mcp_settings, "resources", [])
    if resource_names:
        resource_descriptions = {
            "uml://types": "List of available UML diagram types",
            "uml://templates": "Templates for creating UML diagrams",
            "uml://examples": "Example UML diagrams for reference",
            "uml://formats": "Supported output formats for diagrams",
            "uml://server-info": "Information about the UML-MCP server",
        }
        for resource_name in resource_names:
            description = resource_descriptions.get(
                resource_name, "Resource information"
            )
            resources_table.add_row(resource_name, description)
    else:
        resources_table.add_row("No resources found", "Check server configuration")


def display_resources(mcp_settings):
    """Display information about available resources in the MCP server."""
    resources_table = Table(title="[bold blue]Available Resources[/bold blue]")
    resources_table.add_column("Resource URI", style="cyan")
    resources_table.add_column("Description", style="green")

    try:
        from mcp_core.resources.diagram_resources import get_resource_registry

        resource_registry = get_resource_registry()
        if resource_registry:
            for resource_uri, resource_info in resource_registry.items():
                description = resource_info.get(
                    "description", "No description available"
                )
                resources_table.add_row(resource_uri, description)
        else:
            _display_resources_fallback(mcp_settings, resources_table)
    except ImportError:
        _display_resources_fallback(mcp_settings, resources_table)

    console.print(resources_table)


def display_tools_and_resources(mcp_settings):
    """Display tools, prompts, and resources."""
    display_tools(mcp_settings)
    display_prompts(mcp_settings)
    display_resources(mcp_settings)


def run():
    """Run the CLI: parse args, setup logging, optionally list tools, then start server."""
    global console
    args = parse_args()

    # Use stdout for human-facing output when not using stdio transport
    # or when just listing tools, so output remains pipeable.
    # Always set explicitly so a prior run() in the same process doesn't leak.
    if args.transport != "stdio" or args.list_tools:
        console = Console()
    else:
        console = Console(stderr=True)

    logger = setup_logging(args.debug)

    logger.info("Starting UML-MCP Server with transport: %s", args.transport)

    required_modules = {
        "mcp.server": "MCP Server",
        "tools.kroki.kroki": "Kroki",
        "tools.kroki.plantuml": "PlantUML",
        "tools.kroki.mermaid": "Mermaid",
        "tools.kroki.d2": "D2",
    }
    missing_modules = []
    for module_name, display_name in required_modules.items():
        if not safe_import(module_name, display_name):
            missing_modules.append(display_name)

    if missing_modules:
        console.print(
            f"[bold red]Error:[/bold red] Missing required modules: {', '.join(missing_modules)}"
        )
        console.print("Please ensure all project components are correctly installed.")
        sys.exit(1)

    ran_server = False
    try:
        from mcp_core.core.config import MCP_SETTINGS
        from mcp_core.core.server import get_mcp_server, start_server

        if hasattr(MCP_SETTINGS, "update_from_args"):
            updater = MCP_SETTINGS.update_from_args
            if callable(updater):
                updater(args)

        get_mcp_server()

        if _should_render_human_output(args.transport):
            console.print(
                Panel(
                    f"[bold green]UML-MCP Server v{MCP_SETTINGS.version}[/bold green]"
                )
            )
            table = Table(title="Server Configuration")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Server Name", MCP_SETTINGS.server_name)
            table.add_row("Transport", args.transport)
            table.add_row("Available Tools", str(len(MCP_SETTINGS.tools)))
            table.add_row("Available Prompts", str(len(MCP_SETTINGS.prompts)))
            table.add_row("Available Resources", str(len(MCP_SETTINGS.resources)))
            if args.transport == "http":
                table.add_row("Host", args.host)
                table.add_row("Port", str(args.port))
            console.print(table)

        list_tools = (
            args.list_tools or os.environ.get("LIST_TOOLS", "").lower() == "true"
        )
        if list_tools:
            # Always print and exit (--list-tools forces stdout console above).
            display_tools_and_resources(MCP_SETTINGS)
            return

        ran_server = True
        start_server(transport=args.transport, host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical("Server error: %s", str(e), exc_info=True)
    finally:
        if ran_server:
            logger.info("Server shut down")
