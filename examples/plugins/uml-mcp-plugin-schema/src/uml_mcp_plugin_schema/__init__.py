"""UML-MCP plugin: database schema diagrams from SQL DDL or JSON.

One diagram type, ``db_schema``: table cards with key, link, null and unique markers,
crow's-foot relationships attached at the exact column rows, groups as tinted containers,
laid out left to right by foreign-key direction. ``html`` is an interactive page (focus a
table, trace a column's references, search, export); ``svg`` is the static drawing.
"""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html
from .layout import layout
from .model import MAX_TABLES, THEMES, SchemaError, parse
from .samples import EXAMPLE, TEMPLATE
from .svg import render_svg

__all__ = ["SchemaError", "SchemaRenderer", "parse"]

FEATURES = ("zoom", "pan", "fit", "theme", "inspect", "search", "trace")


class SchemaRenderer:
    name = "schema"
    version = "0.1.0"

    def __init__(self) -> None:
        self.max_tables = MAX_TABLES
        self.diagram_types = {
            "db_schema": DiagramTypeSpec(
                "Database schema (ER) from SQL DDL (CREATE TABLE; Postgres, MySQL, SQLite) "
                "or JSON tables: column cards with PK/FK/null/unique markers, crow's-foot "
                "relationships at the column rows, groups; html or svg",
                ("html", "svg"),
                example=EXAMPLE,
                template=TEMPLATE,
                version=self.version,
                source_schema="urn:uml-mcp:db-schema:1",
                interaction_features=FEATURES,
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
        }

    def configure(self, settings: dict[str, Any]) -> None:
        value = settings.get("max_tables", MAX_TABLES)
        if type(value) is not int or not 1 <= value <= MAX_TABLES:
            raise ValueError(f"max_tables must be an integer from 1 to {MAX_TABLES}")
        self.max_tables = value

    def _parse(self, diagram_type: str, code: str):
        if diagram_type not in self.diagram_types:
            raise SchemaError([f"unknown schema type: {diagram_type}"])
        schema = parse(code)
        if len(schema.tables) > self.max_tables:
            raise SchemaError(
                [
                    (
                        f"{len(schema.tables)} tables is more than this server's limit of "
                        f"{self.max_tables}"
                    )
                ]
            )
        return schema

    def validate(self, diagram_type: str, code: str) -> list[str]:
        try:
            self._parse(diagram_type, code)
        except SchemaError as exc:
            return exc.problems
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format not in {"html", "svg"}:
            raise ValueError("schema renders html or svg")
        try:
            schema = self._parse(diagram_type, code)
        except SchemaError as exc:
            raise ValueError(f"invalid {diagram_type} source: {exc}") from exc
        lay = layout(schema)
        if output_format == "html":
            return RenderOutput(
                html.page(schema, lay).encode("utf-8"), "text/html; charset=utf-8"
            )
        theme = schema.theme if schema.theme in THEMES[1:] else "dark"
        return RenderOutput(
            render_svg(schema, lay, theme).encode("utf-8"), "image/svg+xml"
        )
