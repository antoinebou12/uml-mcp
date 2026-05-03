---
title: About
description: Project background, citation, license, and acknowledgements.
---

# About

UML-MCP connects AI assistants to textual diagram languages over the [Model Context Protocol](https://modelcontextprotocol.io/). The repo is one Python codebase: MCP server, light validation, batching, and a Kroki / PlantUML / Mermaid fallback chain, runnable locally, in Docker, or on Vercel.

## Citation

If UML-MCP helps your research, tooling, or product, please cite it:

```bibtex
@software{uml_mcp,
  author = {Antoine Boucher and contributors},
  title  = {{UML-MCP: Diagram Generation via the Model Context Protocol}},
  url    = {https://github.com/antoinebou12/uml-mcp},
  year   = {2025}
}
```

A GitHub star also helps others discover the project.

[![Star History Chart](https://api.star-history.com/svg?repos=antoinebou12/uml-mcp&type=Date)](https://star-history.com/#antoinebou12/uml-mcp&Date)

## License

UML-MCP is released under the [MIT License](https://github.com/antoinebou12/uml-mcp/blob/main/LICENSE).

You are free to use, modify, and distribute this code in your projects, including commercial ones, as long as you keep the original copyright and license notice. If you embed UML-MCP in a product you ship, include a copy of the original copyright and license notice, for example in your product documentation, an "About" or "Third-Party Licenses" section, or another clear third-party notice.

## Acknowledgements

UML-MCP would not exist without the work of the upstream rendering projects:

- [PlantUML](https://plantuml.com/): text-to-UML engine.
- [Kroki](https://kroki.io/): unified API for 30+ diagram languages.
- [Mermaid](https://mermaid.js.org/): JavaScript-native flowcharts, sequence, class, state, Gantt, and ER diagrams.
- [D2](https://d2lang.com/): declarative diagram language.
- [TikZ/PGF](https://tikz.dev/): TeX-quality vector graphics.

And the MCP ecosystem:

- [Model Context Protocol](https://modelcontextprotocol.io/): open standard this server speaks.
- [FastMCP](https://gofastmcp.com/): Python MCP server framework.
- [Smithery](https://smithery.ai/): MCP server registry.
- [Vercel](https://vercel.com/): hosts the public deployment.

## Maintainers

- [Antoine Boucher](https://github.com/antoinebou12) and the [list of contributors](https://github.com/antoinebou12/uml-mcp/graphs/contributors).

## Get in touch

- Issues / feature requests: [GitHub Issues](https://github.com/antoinebou12/uml-mcp/issues).
- Security: [`SECURITY.md`](https://github.com/antoinebou12/uml-mcp/blob/main/SECURITY.md).
- Live deployment: [https://uml-mcp.vercel.app/mcp](https://uml-mcp.vercel.app/mcp).
- Smithery listing: [smithery.ai/server/@antoinebou12/uml](https://smithery.ai/server/@antoinebou12/uml).
