"""Open the MCP App viewer locally with an example picker and real MCP tool calls.

Run ``uv run python scripts/run_local_viewer.py --mcp-url http://127.0.0.1:8766/mcp``
against a running UML-MCP server. This is a browser test host, not a chat client.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/local-viewer"
MCP = "http://127.0.0.1:8766/mcp"
SOURCES = dict(
    re.findall(
        r"^### (\w+)\n\n```json\n(.*?)\n```",
        (ROOT / "tests/prompts/all_interactive_plugins_smoke_test.md").read_text(
            encoding="utf8"
        ),
        re.MULTILINE | re.DOTALL,
    )
)


async def resource():
    async with Client(MCP, timeout=120) as c:
        contents = await c.read_resource("ui://uml-mcp/diagram-viewer")
        picker = r"""<style>#typeBadge{display:none!important}#exampleDiagram{max-width:260px;padding:5px 9px;border:1px solid var(--border,#334154);border-radius:6px;background:var(--panel,#141b24);color:inherit;font:inherit}</style><script>
const exampleNames={d3_force:'Force graph',d3_architecture:'Cloud architecture',d3_topology:'Network topology',stack_diagram:'Stack diagram',archify_architecture:'Architecture',archify_workflow:'Workflow',archify_sequence:'Sequence',llm_2d:'LLM · 2D',llm_3d:'LLM · 3D',db_schema:'Database schema',dependency_graph:'Dependencies',state_machine:'Statechart',agent_trace:'Agent trace',c4_model:'C4 model',timeline:'Timeline'};
const examplePicker=document.createElement('select');examplePicker.id='exampleDiagram';examplePicker.setAttribute('aria-label','Example diagram');
for(const [value,label] of Object.entries(exampleNames)){const option=document.createElement('option');option.value=value;option.textContent=label;examplePicker.append(option)}
examplePicker.value='archify_architecture';document.querySelector('#typeBadge').after(examplePicker);
examplePicker.addEventListener('change',()=>parent.postMessage({jsonrpc:'2.0',method:'local/select-example',params:{type:examplePicker.value}},location.origin));
</script>"""
        (OUT / "viewer.html").write_text(
            contents[0].text.replace("</body>", picker + "</body>"), encoding="utf8"
        )


async def call(name, args):
    if name not in {
        "generate_uml",
        "generate_uml_image",
        "download_diagram",
        "rerender_diagram",
        "validate_uml",
        "list_diagram_types",
    }:
        raise ValueError("Tool is not enabled in this local test host")
    async with Client(MCP, timeout=120) as c:
        result = await c.call_tool(name, args)
        return {
            "content": [
                x.model_dump(mode="json", by_alias=True) for x in result.content
            ],
            "structuredContent": result.structured_content,
            "isError": result.is_error,
        }


PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UML-MCP viewer</title><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#11151b;color:#e8eef6}#viewer{width:100%;height:100dvh;border:0;display:block}
</style><select id="type" hidden aria-hidden="true" tabindex="-1"></select><span id="status" hidden></span>
<iframe id="viewer" title="UML-MCP diagram viewer" src="viewer.html" allow="clipboard-write" sandbox="allow-scripts allow-same-origin allow-downloads"></iframe>
<script>
const frame=document.querySelector('#viewer'),sel=document.querySelector('#type'),status=document.querySelector('#status');let sources={},ready=false;

const post=m=>frame.contentWindow.postMessage(m,location.origin);
async function tool(name,args){const res=await fetch('/api/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,arguments:args})});const data=await res.json();if(!res.ok)throw Error(data.error||res.statusText);return data}
async function render(){if(!ready||!sources[sel.value])return;status.textContent='Rendering…';try{const args={diagram_type:sel.value,code:sources[sel.value],output_format:'html'};post({jsonrpc:'2.0',method:'ui/notifications/tool-input',params:{name:'generate_uml',arguments:args}});const result=await tool('generate_uml',args);post({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:result});status.textContent='Local render ready'}catch(e){status.textContent=e.message}}
window.addEventListener('message',async e=>{
 if(e.source!==frame.contentWindow||e.origin!==location.origin||!e.data||e.data.jsonrpc!=='2.0')return;
 const m=e.data;
 const reply=(result,error)=>{if(m.id!=null)post({jsonrpc:'2.0',id:m.id,...(error?{error:{code:-32000,message:String(error)}}:{result})})};
 try{
  if(m.method==='local/select-example'){sel.value=m.params.type;render()}
  else if(m.method==='ui/initialize'){reply({protocolVersion:'2026-01-26',hostInfo:{name:'uml-mcp-local-test-host',version:'1'},hostCapabilities:{serverTools:true,openLinks:true},hostContext:{theme:'dark',locale:'en',displayMode:'inline'}});ready=true;if(Object.keys(sources).length)render()}
  else if(m.method==='tools/call')reply(await tool(m.params.name,m.params.arguments||{}));
  else if(m.method==='ui/download-file'){
   for(const item of m.params.contents||[]){const r=item.resource;if(!r||!r.blob)throw Error('No file bytes');const bytes=Uint8Array.from(atob(r.blob),c=>c.charCodeAt(0));const blob=new Blob([bytes],{type:r.mimeType});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=decodeURIComponent(r.uri.split('/').pop())||'diagram';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}reply({});
  }else if(m.method==='ui/open-link'){window.open(m.params.url,'_blank','noopener');reply({})}
  else if(m.method==='ui/update-model-context')reply({});
  else if(m.id!=null)reply(null,'Unsupported method: '+m.method);
 }catch(err){reply(null,err.message)}
});
fetch('/api/sources').then(r=>r.json()).then(data=>{sources=data;for(const type of Object.keys(sources)){const o=document.createElement('option');o.value=type;o.textContent=type;sel.append(o)}sel.value='archify_architecture';if(ready)render()});sel.addEventListener('change',render);
</script></html>"""


class Handler(SimpleHTTPRequestHandler):
    server: ThreadingHTTPServer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(OUT), **kwargs)

    def do_GET(self):
        if self.path == "/api/sources":
            raw = json.dumps(SOURCES).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(raw)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/tool":
            self.send_error(404)
            return
        origin = self.headers.get("Origin")
        allowed_origins = {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }
        if origin and origin not in allowed_origins:
            self.send_error(403, "Cross-origin tool calls are not allowed")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "Tool calls require application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length < 1_000_000:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            data = asyncio.run(call(request["name"], request.get("arguments", {})))
            code = 200
        except Exception as e:  # noqa: BLE001 - return MCP failures to the viewer
            data = {"error": str(e)}
            code = 400
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)


def main(argv: list[str] | None = None) -> None:
    global MCP, OUT
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mcp-url", default=MCP, help="Running UML-MCP endpoint")
    parser.add_argument("--port", type=int, default=8767, help="Local viewer port")
    parser.add_argument(
        "--output-dir", type=Path, default=OUT, help="Generated viewer files"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    MCP, OUT = args.mcp_url, args.output_dir.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    asyncio.run(resource())
    (OUT / "index.html").write_text(PAGE, encoding="utf-8")
    print(f"MCP App viewer: http://127.0.0.1:{args.port}/", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
