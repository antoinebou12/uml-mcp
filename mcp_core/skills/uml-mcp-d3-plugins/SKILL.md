---
name: uml-mcp-d3-plugins
description: Discover installed D3 plugins and render architecture diagrams with cloud and AI logos in the MCP App.
---

# D3 and plugin diagrams

Follow `skill://uml-mcp-diagrams/SKILL.md`. Discover live types first. If a D3
renderer is listed, use its exact catalog key, such as `d3_architecture`, with
`generate_uml_image`. Do not substitute a standalone HTML code block for the
requested App diagram. If D3 is absent, report that this deployment has not
enabled it; code availability in a repository does not prove runtime availability.

Read `uml://templates`, the plugin's registered resources and `d3_catalog` when
that tool is exposed. Check its supported services before assigning logos.
Cloud services use keys such as `aws:s3` and `gcp:run`; AI services include
`tech:chatgpt`, `tech:openai`, `tech:claude` and `tech:anthropic`. AWS/GCP marks
identify the provider; do not describe a provider mark as a specific service icon.

Start with this JSON and extend it from the user's component/edge inventory:

```json
{"direction":"LR","title":"Web application","nodes":[{"id":"web","label":"Frontend","service":"tech:react"},{"id":"api","label":"Backend API","category":"backend"},{"id":"ai","label":"Claude","service":"tech:claude"}],"links":[{"source":"web","target":"api","label":"HTTPS / JSON"},{"source":"api","target":"ai","label":"Inference"}]}
```

Use stable unique IDs and explicit labels. Validate the JSON through
`validate_uml` with the same catalog type; request SVG for App previews.
Inspect text, logo contrast and edge endpoints, including after theme changes.
A clean parse is not proof of a readable graph. Keep cloud storage, cache,
authentication, queues and payment services distinct when the user supplied them.

For architecture containers, declare `groups` with `id`, `label`, `type` and
optional `parent`, then set each node's `group`. Preserve the user's boundaries
and labelled relationships when converting formats. For category-only grouping,
`group_by: "category"` wraps ungrouped nodes; it does not infer network or cloud
account boundaries. Use named ports for distinct flows when needed. Check routes
and label placement after dragging, then reopen an HTML export to verify the
containers and connections survived.

The App exports SVG, PNG, PDF and interactive standalone HTML with its D3
runtime and logos bundled. PDF embeds a high-resolution raster; use SVG for
vector editing. Select HTML in the viewer to use the interactive plugin. Large
HTML pages load on demand rather than in the initial tool result. Request downloads through the viewer; do not claim an HTML
file exists merely because source was printed. If the plugin failed, report the
actual error and preserve the graph inventory for a supported fallback.

In the embedded HTML view, SVG, PNG and HTML downloads preserve the live layout
and theme. PDF export renders the source specification. File downloads go through
the MCP host; an unsupported or rejected host download must be reported rather
than claimed successful. Standalone HTML opened in a browser downloads directly.
