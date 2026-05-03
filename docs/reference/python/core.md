---
title: mcp_core.core
description: "Service layer: rendering pipeline, validation, configuration, and the DiagramRequest dataclass."
---

# `mcp_core.core`

Internals of the diagram pipeline. `diagram_service.generate_from_request` is the single entry point used by every tool.

## `mcp_core.core.diagram_service`

::: mcp_core.core.diagram_service
    options:
      show_root_heading: true
      show_root_full_path: true
      members_order: source

## `mcp_core.core.diagram_rendering`

::: mcp_core.core.diagram_rendering
    options:
      show_root_heading: true
      show_root_full_path: true
      members_order: source

## `mcp_core.core.diagram_validation`

::: mcp_core.core.diagram_validation
    options:
      show_root_heading: true
      show_root_full_path: true
      members_order: source

## `mcp_core.core.diagram_catalog`

::: mcp_core.core.diagram_catalog
    options:
      show_root_heading: true
      show_root_full_path: true
      members_order: source

## `mcp_core.core.config`

::: mcp_core.core.config
    options:
      show_root_heading: true
      show_root_full_path: true
      members_order: source
      filters:
        - "!^_"
        - "!^DIAGRAM_TYPES$"
