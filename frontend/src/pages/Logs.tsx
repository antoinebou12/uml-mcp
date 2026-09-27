import { Download, Pause, Play, Trash2 } from "lucide-react";
import * as React from "react";
import { ErrorState, Page } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/select";
import { download, get } from "@/lib/api";
import type { LogRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

const LEVEL_COLOR: Record<string, string> = {
  // The log view is always dark: fixed high-contrast colours (>= 4.5:1 on zinc-950).
  DEBUG: "text-zinc-400", INFO: "text-sky-400", WARNING: "text-amber-300", ERROR: "text-red-400", CRITICAL: "text-red-400",
};

export default function Logs() {
  const [records, setRecords] = React.useState<LogRecord[]>([]);
  const [level, setLevel] = React.useState("");
  const [q, setQ] = React.useState("");
  const [paused, setPaused] = React.useState(false);
  const [error, setError] = React.useState<Error>();
  const last = React.useRef(0);
  const box = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => { last.current = 0; setRecords([]); }, [level, q]);

  React.useEffect(() => {
    if (paused) return;
    let alive = true;
    const tick = async () => {
      const qs = new URLSearchParams({ after: String(last.current), limit: "500" });
      if (level) qs.set("level", level);
      if (q) qs.set("q", q);
      try {
        const data = await get<{ records: LogRecord[]; last_seq: number }>(`/admin/api/logs?${qs}`);
        if (!alive) return;
        setError(undefined);
        if (data.records.length) {
          last.current = data.records[data.records.length - 1].seq;
          setRecords((r) => [...r, ...data.records].slice(-2000));
        }
      } catch (e) {
        if (alive) setError(e as Error);
      }
    };
    tick();
    const id = window.setInterval(tick, 2000);
    return () => { alive = false; window.clearInterval(id); };
  }, [paused, level, q]);

  React.useEffect(() => {
    const el = box.current;
    if (el && !paused) el.scrollTop = el.scrollHeight;
  }, [records, paused]);

  return (
    <Page
      title="Logs"
      description="Live server log (tokens and secrets are redacted before they reach this view)."
      actions={
        <>
          <Button variant="outline" size="sm" onClick={() => setPaused((p) => !p)} data-testid="logs-pause">
            {paused ? <Play /> : <Pause />}{paused ? "Resume" : "Pause"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setRecords([])}><Trash2 />Clear</Button>
          <Button variant="outline" size="sm" onClick={() => download("uml-mcp.log", records.map((r) => `${r.timestamp} ${r.level} ${r.logger} ${r.message}`).join("\n"))}>
            <Download />Download
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <NativeSelect aria-label="level" className="sm:w-40" value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {["DEBUG", "INFO", "WARNING", "ERROR"].map((l) => <option key={l} value={l}>{l}+</option>)}
        </NativeSelect>
        <Input aria-label="search logs" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} className="sm:max-w-sm" />
        <Badge variant={paused ? "secondary" : "success"} className="self-start sm:self-center">{paused ? "paused" : "live"}</Badge>
      </div>
      {error && <ErrorState error={error} />}
      <Card className="overflow-hidden">
        <div
          ref={box}
          role="log"
          aria-live="polite"
          aria-label="Server log"
          tabIndex={0}
          className="h-[60vh] overflow-auto bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          data-testid="log-view"
        >
          {records.length === 0 && <div className="text-zinc-400">Waiting for log lines…</div>}
          {records.map((r) => (
            <div key={r.seq} className="whitespace-pre-wrap break-all animate-in fade-in-0 duration-300">
              <span className="text-zinc-400">{r.timestamp.slice(11, 23)} </span>
              <span className={cn("font-semibold", LEVEL_COLOR[r.level])}>{r.level.padEnd(7)}</span>
              <span className="text-zinc-300"> {r.logger} </span>
              {r.message}
            </div>
          ))}
        </div>
      </Card>
    </Page>
  );
}
