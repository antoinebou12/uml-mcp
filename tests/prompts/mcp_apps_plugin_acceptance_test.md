# MCP App rendering and plugin acceptance test

Use the connected server's current catalog. Run this alongside the catalog stress
test; count these calls separately from its 28-call baseline. Record server URL,
client, revision when available, each tool call and each returned error. Do not
claim access to Manufact unless a connected tool actually returned live data.

## Required cases

1. Inspect initialize metadata: title, description, website and icon. Inspect UI
   resource MIME, standard description and one exact HTTPS domain. Inspect the
   linked tools' invoking/invoked object. Report the legacy description checker
   gap separately; do not add invented v1 fields. A static lint score is not a
   policy approval, startup check or visual result.
2. Render Mermaid flowchart, sequence, class, state, ER, Gantt and mindmap in one
   SVG batch. Use at least three distinct labels in every case. Select every
   gallery entry and verify the actual visible text, not just shapes or XML
   validity. State and mindmap labels are required. Repeat state/mindmap as PNG.
3. Render all four C4 levels as SVG with named @startuml directives and a valid
   theme. Use context/container/component libraries and ordinary UML for level 4.
   Include a Person icon. Check all thumbnails and full previews, including 2/3.
4. Search for "C4 PlantUML" and verify discovery. Retry failed items individually;
   preserve successful items. Test an invalid type and an empty batch as controlled
   failures. Count them. Never call partial results complete.
5. Discover D3/plugin types. If absent, mark plugin cases unavailable, not passed.
   If present, build one frontend/backend inventory with labelled edges, React,
   API, authentication, cache, database, queue, storage and a payment provider.
   Include AWS, GCP, ChatGPT and Claude marks supported by the plugin catalog.
6. Render D3 SVG, then HTML. Select HTML in the App and verify interactive zoom,
   pan, node dragging, theme and fit. Large HTML must load on demand. A message
   saying HTML rendered without bytes, a URL or a working App is not a pass.
7. In HTML mode, move a node and change theme. Export SVG, PNG and HTML through
   the App; open each downloaded file and verify labels, node positions, theme
   and category colors. HTML must work offline. PDF export must open and include
   readable labels; report that its image is rendered from source, not the moved
   browser layout. SVG retains vectors; PDF embeds a high-resolution image.
8. Start with PNG, re-render as SVG, then HTML and back to SVG. Check labels,
   fresh links, format selectors and other gallery items after each transition.
   Check narrow and wide App panels. The diagram must fit without clipped text.
9. Deny a host download. Verify an error rather than "download ready". Probe a
   host whose download handler exists without an advertised capability. Hosts
   lacking the download API are an explicit platform limitation. Standalone HTML
   downloads directly; App downloads require the host bridge.
10. Compare the same inventory across D3, D2, Mermaid and C4 container views.
    Verify components and directed labelled relationships. In an App, avoid
    repeating the image, links and full source in chat. In a plain client, provide
    one compatible image and working returned render/playground links.
11. Render the D3 commerce inventory with explicit nested application and data
    containers and a separate integrations group. Preserve all 11 components
    and 10 labelled relationships. Drag a data node, check routes against cards
    and group titles, export HTML and reopen it offline. Verify the containers,
    labels and moved positions survive. Repeat with `group_by: "category"` and
    no explicit groups; describe these as logical category containers.

## Report

Use PASS / FAIL / UNVERIFIED / UNAVAILABLE per case. Separate syntax validation,
backend rendering, visible labels, interactivity, downloaded-file verification,
startup health and publishing policy review. A successful tools/call proves none
of the later stages by itself. Record the first failing stage and exact error.
If a host cannot be inspected, mark visual checks UNVERIFIED. Do not infer a
startup crash from historical logs; obtain the deployment's actual traceback.
Do not redeploy or start billed publishing/evaluation checks for this test.

MCP_APP_ACCEPTANCE: PASS only when every applicable required case is verified.
Otherwise emit MCP_APP_ACCEPTANCE: FAIL or UNVERIFIED with affected case numbers.
