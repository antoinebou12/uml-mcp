---
title: Changelog
description: How to find release notes and tagged versions of UML-MCP.
---

# Changelog

Release notes and tagged versions live on GitHub:

- [GitHub Releases](https://github.com/antoinebou12/uml-mcp/releases): full notes per tag.
- [Compare across tags](https://github.com/antoinebou12/uml-mcp/compare): diff between any two versions.
- [Commit history](https://github.com/antoinebou12/uml-mcp/commits/main): full commit history on `main`.

!!! tip "Subscribe"

    Use GitHub's "Watch → Custom → Releases" to get an email or notification on every release.

## Versioning

UML-MCP follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: breaking change to the MCP tool surface or HTTP API.
- **MINOR**: new tools, resources, prompts, diagram types, or backwards-compatible behavior.
- **PATCH**: bug fixes, docs, performance.

The current package version is set in [`pyproject.toml`](https://github.com/antoinebou12/uml-mcp/blob/main/pyproject.toml). The `uml://server-info` resource exposes the running server's version at runtime.
