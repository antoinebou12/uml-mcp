"""
Build MCP server card (tools, resources, prompts) for Smithery and static JSON.
Used by scripts/generate_server_card.py and app.py.
"""


def _param_descriptions_for_tool(tool_name: str):
    """Return a dict of param name -> description for the given tool."""
    from mcp_core.tools.schemas import GenerateUMLInput

    if tool_name == "generate_uml":
        schema = GenerateUMLInput.model_json_schema()
    else:
        return {}
    props = schema.get("properties", {})
    return {
        k: v.get("description", k.replace("_", " ").title()) for k, v in props.items()
    }


def _param_types_for_tool(tool_name: str):
    """Return a dict of param name -> JSON schema type for the given tool (for server card)."""
    return {}


def build_server_card(*, strict: bool = False):
    """Build server card dict from tool and resource registries.

    When strict is True (e.g. Vercel static generator), failures propagate so logs
    show the real error. When False (runtime HTTP), failures return an empty stub.
    """
    try:
        from mcp_core.core.config import MCP_SETTINGS
        from mcp_core.prompts.diagram_prompts import get_prompt_registry
        from mcp_core.resources.diagram_resources import get_resource_registry
        from mcp_core.tools import diagram_tools  # noqa: F401 - load tools so registry is populated
        from mcp_core.tools.tool_decorator import get_tool_registry

        tool_registry = get_tool_registry()
        resource_registry = get_resource_registry()
        param_descriptions = {
            name: _param_descriptions_for_tool(name) for name in tool_registry
        }
        param_types_override = {
            name: _param_types_for_tool(name) for name in tool_registry
        }

        tools = []
        for name, info in tool_registry.items():
            params = info.get("parameters", {})
            descriptions = param_descriptions.get(name, {})
            type_overrides = param_types_override.get(name, {})
            properties = {}
            required = []
            for pname, pinfo in params.items():
                if pname in type_overrides:
                    js_type = type_overrides[pname]
                else:
                    py_type = pinfo.get("type", "str")
                    js_type = (
                        "string"
                        if py_type in ("str", "Optional[str]")
                        else "boolean"
                        if py_type == "bool"
                        else "integer"
                        if py_type == "int"
                        else "string"
                    )
                properties[pname] = {
                    "type": js_type,
                    "description": descriptions.get(
                        pname, pname.replace("_", " ").title()
                    ),
                }
                if pinfo.get("required", True):
                    required.append(pname)
            tool_entry = {
                "name": name,
                "description": info.get("description", ""),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
            annotations = info.get("annotations") or {}
            if annotations:
                tool_entry["annotations"] = annotations
            tools.append(tool_entry)

        resources = []
        for uri, info in resource_registry.items():
            resources.append(
                {
                    "uri": uri,
                    "name": uri,
                    "description": info.get("description", ""),
                }
            )

        prompt_registry = get_prompt_registry()
        prompts = [
            {"name": pname, "description": pinfo.get("description", "")}
            for pname, pinfo in prompt_registry.items()
        ]

        card = {
            "serverInfo": {
                "name": MCP_SETTINGS.display_name,
                "version": MCP_SETTINGS.version,
            },
            "tools": tools,
            "resources": resources,
            "prompts": prompts,
        }
        schema_url = getattr(MCP_SETTINGS, "config_schema_url", None) or ""
        if schema_url:
            card["configSchemaUrl"] = schema_url
        else:
            # Relative URL: when card is at /.well-known/mcp/server-card.json, schema at config-schema.json
            card["configSchemaUrl"] = "config-schema.json"
        return card
    except Exception as e:
        import logging

        log = logging.getLogger(__name__)
        if strict:
            log.exception("build_server_card(strict=True) failed")
            raise
        log.warning("Could not build server card: %s", e)
        return {
            "serverInfo": {"name": "UML Diagram Generator", "version": "1.2.0"},
            "tools": [],
            "resources": [],
            "prompts": [],
        }
