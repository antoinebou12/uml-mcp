"""Build an offline MCP App replay and report from chat-raw JSON exports.

uv run python scripts/replay_mcp_chat.py path/to/chat-raw.json --out .cache/chat-replay
No recorded prompts, tool calls or network renders are executed. Only recorded
viewer results are displayed. Full-asset loading and host exports stay unverified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_core.apps.diagram_viewer import diagram_viewer_html
from mcp_core.quality.chat_trace import VIEWER_TOOLS, extract_calls, summarize_calls

PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-src 'self' blob:; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MCP chat replay</title>
<style>body{margin:16px;font:14px system-ui;background:#12151c;color:#edf0f7}
header{display:flex;gap:8px;flex-wrap:wrap;align-items:center}h1{font-size:20px;margin:0 14px 0 0}
button,select{padding:7px;background:#252b37;color:inherit;border:1px solid #536078;border-radius:6px}
p{max-width:1000px;line-height:1.5}#pane{max-width:100%;margin:auto}iframe{width:100%;height:900px;border:1px solid #536078;border-radius:10px;background:#181a20}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1c2230;padding:12px;border-radius:8px}
</style><header><h1>MCP chat replay</h1><select id="cases" aria-label="Recorded result"></select>
<button id="previous">Previous</button><button id="next">Next</button>
<select id="width" aria-label="Viewer width"><option value="640">640 px</option><option value="390">390 px</option><option value="1000">1000 px</option></select></header>
<p>Recorded results only. Network rendering is disabled. Compact images remain thumbnails; full-asset loading,
interactive HTML omitted from a result, and real host downloads require a connected MCP host. A visible preview is not a test pass.</p>
<p id="summary"></p><details><summary>Selected call diagnostics</summary><pre id="diagnostics"></pre></details>
<div id="pane"><iframe title="Recorded MCP diagram" sandbox="allow-scripts"></iframe></div>
<script type="application/json" id="data">__DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent), frame=document.querySelector('iframe');
const cases=document.getElementById('cases');let ready=false;
data.cases.forEach((c,i)=>{const option=document.createElement('option');option.value=i;option.textContent=c.label;cases.appendChild(option);});
document.getElementById('summary').textContent=data.summary;
function send(method,params){frame.contentWindow.postMessage({jsonrpc:'2.0',method,params},'*');}
function show(){const c=data.cases[+cases.value];if(!c)return;
 document.getElementById('diagnostics').textContent=JSON.stringify(c.diagnostics,null,2);
 if(ready){send('ui/notifications/tool-input',{arguments:c.arguments});send('ui/notifications/tool-result',c.result);}}
cases.addEventListener('change',show);
['previous','next'].forEach(id=>document.getElementById(id).addEventListener('click',()=>{
 if(!data.cases.length)return;cases.value=(+cases.value+(id==='next'?1:-1)+data.cases.length)%data.cases.length;show();}));
function resize(){document.getElementById('pane').style.width=document.getElementById('width').value+'px';}
document.getElementById('width').addEventListener('change',resize);resize();
window.addEventListener('message',event=>{if(event.source!==frame.contentWindow||!event.data)return;const m=event.data;
 if(m.method==='ui/notifications/initialized'){ready=true;show();return;}
 if(m.id==null||!m.method)return;
 const reply=body=>event.source.postMessage(Object.assign({jsonrpc:'2.0',id:m.id},body),'*');
 if(m.method==='ui/initialize')return reply({result:{hostCapabilities:{},hostContext:{}}});
 if(m.method==='tools/call'||m.method==='ui/download-file')return reply({error:{code:-32601,message:'Offline replay: a connected MCP host is required'}});
 reply({result:{}});
});
show();frame.srcdoc=data.viewer;
</script></html>"""


def write_replay(paths: list[Path], output: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for path in paths:
        calls = extract_calls(json.loads(path.read_text(encoding="utf-8-sig")))
        report = summarize_calls(calls)
        reports.append({"file": path.name, **report})
        for call, diagnostic in zip(calls, report["entries"], strict=True):
            if call["tool"] in VIEWER_TOOLS and call["result"] is not None:
                cases.append(
                    {
                        "label": f"{path.name} · call {diagnostic['call']} · {call['tool']}",
                        "arguments": call["arguments"],
                        "result": call["result"],
                        "diagnostics": diagnostic,
                    }
                )
    total = sum(report["tool_calls"] for report in reports)
    data = {
        "cases": cases,
        "viewer": diagram_viewer_html(),
        "summary": f"{total} recorded tool calls; {len(cases)} viewer results. See report.json for exact call counts and preview limitations.",
    }
    encoded = (
        json.dumps(data, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "replay.html").write_text(
        PAGE.replace("__DATA__", encoded), encoding="utf-8"
    )
    (output / "report.json").write_text(
        json.dumps(reports, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return {
        "tool_calls": total,
        "viewer_results": len(cases),
        "path": str((output / "replay.html").resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=Path(".cache/chat-replay"))
    args = parser.parse_args()
    try:
        result = write_replay(args.traces, args.out)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"Could not read chat trace: {exc}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
