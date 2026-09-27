import { Container, Download, ExternalLink, Play, Power, PowerOff, RefreshCw, Server, Shapes } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { CodeBlock, ErrorState, Loading, Page } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { api, post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import type { KrokiStatus, KrokiType, RenderResult } from "@/lib/types";

const PREVIEW_FORMATS = ["svg", "png", "jpeg"];

function StatusCard({ status }: { status: KrokiStatus }) {
  const k = status.kroki;
  return (
    <Card data-testid="kroki-status">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <Server className="size-4" /> Kroki server
          <Badge variant={k.reachable ? "success" : "destructive"}>{k.reachable ? "reachable" : "unreachable"}</Badge>
          {k.version && <Badge variant="outline">v{k.version}</Badge>}
        </CardTitle>
        <CardDescription className="break-all font-mono">{k.url}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {k.error && <div className="text-destructive-text">{k.error}</div>}
        <div className="text-muted-foreground">Companion renderers (each checked with a real render):</div>
        <ul className="grid gap-2 sm:grid-cols-2">
          {Object.entries(k.companions).map(([name, check]) => (
            <li key={name} data-testid={`kroki-companion-${name}`} className="flex min-w-0 items-center gap-2">
              <Badge variant={check.ok ? "success" : "destructive"}>{check.ok ? "ok" : "error"}</Badge>
              <span className="font-mono">{name}</span>
              {!check.ok && <span className="truncate text-xs text-muted-foreground" title={check.detail}>{check.detail}</span>}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function DockerCard({ status, reload }: { status: KrokiStatus; reload: () => void }) {
  const { signedIn } = useSession();
  const [busy, setBusy] = React.useState<"up" | "down" | "use" | null>(null);
  const docker = status.docker;
  if (!docker) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Container className="size-4" /> Kroki deployment</CardTitle>
          <CardDescription>
            In enterprise mode Kroki runs next to the server (Helm values or <code>docker-compose.yml</code>); this console only reports its health.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }
  const running = docker.containers.filter((c) => c.state === "running").length;
  const inUse = docker.url !== null && docker.url === status.kroki.url;
  const run = async (action: "up" | "down" | "use") => {
    setBusy(action);
    try {
      if (action === "up") {
        await post("/admin/api/kroki/docker/up", { use: true });
        toast.success("Kroki started with every companion", { description: "Rendering now uses the local Kroki." });
      } else if (action === "down") {
        await post("/admin/api/kroki/docker/down");
        toast.success("Local Kroki stopped");
      } else if (docker.url) {
        await post("/admin/api/kroki/use", { url: docker.url });
        toast.success("Rendering now uses the local Kroki");
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
      reload();
    }
  };
  return (
    <Card data-testid="kroki-docker">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <Container className="size-4" /> Local Kroki (Docker)
          <Badge variant={docker.docker ? "secondary" : "warning"}>{docker.detail}</Badge>
          {docker.containers.length > 0 && <Badge variant={running === 5 ? "success" : "warning"}>{running}/5 running</Badge>}
          {inUse && <Badge variant="success">in use</Badge>}
        </CardTitle>
        <CardDescription>
          Kroki plus the mermaid, blockdiag, bpmn and excalidraw companions on <code>127.0.0.1</code>, so every diagram type renders without the internet.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm">
        {docker.containers.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {docker.containers.map((c) => (
              <li key={c.service}>
                <Badge variant={c.state === "running" ? "outline" : "destructive"} className="font-mono">{c.service}: {c.state}</Badge>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap gap-2">
          <Button data-testid="kroki-docker-up" disabled={!docker.docker || !signedIn || busy !== null} onClick={() => run("up")}>
            <Power /> {busy === "up" ? "Starting (first run pulls images)…" : running ? "Restart & use" : "Start all & use"}
          </Button>
          {docker.url && !inUse && running > 0 && (
            <Button variant="outline" disabled={!signedIn || busy !== null} onClick={() => run("use")}>Use for rendering</Button>
          )}
          <Button variant="outline" disabled={!docker.docker || !signedIn || busy !== null || !docker.containers.length} onClick={() => run("down")}>
            <PowerOff /> {busy === "down" ? "Stopping…" : "Stop"}
          </Button>
        </div>
        {!signedIn && <div className="text-warning-text">Enter the setup token (top bar) to start or stop containers.</div>}
        <div>
          <div className="mb-1.5 text-muted-foreground">Same thing from a terminal:</div>
          <CodeBlock code={docker.command} />
        </div>
      </CardContent>
    </Card>
  );
}

function download(result: RenderResult, name: string) {
  if (!result.content_base64 || !result.mime_type) return;
  const bytes = Uint8Array.from(atob(result.content_base64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: result.mime_type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

function Playground({ types }: { types: KrokiType[] }) {
  const [typeName, setTypeName] = React.useState(() => (types.some((t) => t.name === "mermaid") ? "mermaid" : types[0]?.name ?? ""));
  const current = types.find((t) => t.name === typeName);
  const formats = (current?.formats ?? ["svg"]).filter((f) => PREVIEW_FORMATS.includes(f));
  const [format, setFormat] = React.useState("svg");
  const [code, setCode] = React.useState(current?.example ?? "");
  const [result, setResult] = React.useState<RenderResult>();
  const [busy, setBusy] = React.useState(false);

  const choose = (name: string) => {
    const next = types.find((t) => t.name === name);
    setTypeName(name);
    setCode(next?.example ?? "");
    const nextFormats = (next?.formats ?? []).filter((f) => PREVIEW_FORMATS.includes(f));
    if (!nextFormats.includes(format)) setFormat(nextFormats[0] ?? "svg");
    setResult(undefined);
  };

  const render = async () => {
    setBusy(true);
    try {
      setResult(await api<RenderResult>("/admin/api/kroki/render", {
        method: "POST",
        json: { diagram_type: typeName, code, output_format: format },
        write: true,
      }));
    } catch (e) {
      setResult({ error: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const src = result?.content_base64 && result.mime_type?.startsWith("image/")
    ? `data:${result.mime_type};base64,${result.content_base64}`
    : undefined;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Shapes className="size-4" /> Playground</CardTitle>
        <CardDescription>
          Renders through this server exactly like the <code>generate_uml</code> tool (same validation, Kroki and fallbacks). Ctrl/⌘+Enter renders.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
            <div className="grid gap-1.5">
              <Label htmlFor="kroki-type">Diagram type</Label>
              <NativeSelect id="kroki-type" data-testid="kroki-type" value={typeName} onChange={(e) => choose(e.target.value)}>
                {types.map((t) => (
                  <option key={t.name} value={t.name}>{t.name} ({t.backend})</option>
                ))}
              </NativeSelect>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="kroki-format">Format</Label>
              <NativeSelect id="kroki-format" data-testid="kroki-format" value={format} onChange={(e) => setFormat(e.target.value)}>
                {formats.map((f) => <option key={f} value={f}>{f}</option>)}
              </NativeSelect>
            </div>
          </div>
          {current && <p className="text-xs text-muted-foreground">{current.description}</p>}
          <div className="grid gap-1.5">
            <Label htmlFor="kroki-code">Source</Label>
            <Textarea
              id="kroki-code"
              data-testid="kroki-code"
              spellCheck={false}
              className="h-72 font-mono text-xs leading-relaxed"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                  e.preventDefault();
                  void render();
                }
              }}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button data-testid="kroki-render" disabled={busy || !code.trim()} onClick={render}>
              <Play /> {busy ? "Rendering…" : "Render"}
            </Button>
            <Button variant="outline" onClick={() => choose(typeName)}>Reset example</Button>
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex min-h-72 items-center justify-center overflow-auto rounded-lg border bg-white p-4" aria-live="polite">
            {src ? (
              <img data-testid="kroki-preview" src={src} alt={`${typeName} diagram preview`} className="max-h-[32rem] max-w-full" />
            ) : (
              <span className="text-sm text-zinc-600">{busy ? "Rendering…" : result?.error ? "No preview" : "Press Render to preview the diagram"}</span>
            )}
          </div>
          {result?.error && (
            <div role="alert" data-testid="kroki-error" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive-text">
              {result.error}
            </div>
          )}
          {result && !result.error && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {result.source && <Badge variant="secondary">{result.source}</Badge>}
              {result.render_ms !== undefined && <Badge variant="outline">{Math.round(result.render_ms)} ms</Badge>}
              {result.url && (
                <Button asChild variant="outline" size="sm">
                  <a href={result.url} target="_blank" rel="noreferrer" data-testid="kroki-url"><ExternalLink /> Kroki URL</a>
                </Button>
              )}
              {result.playground && (
                <Button asChild variant="outline" size="sm">
                  <a href={result.playground} target="_blank" rel="noreferrer" data-testid="kroki-playground"><ExternalLink /> Open in playground</a>
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => download(result, `${typeName}.${format}`)}>
                <Download /> Download
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function Kroki() {
  const status = useApi<KrokiStatus>("/admin/api/kroki");
  const catalog = useApi<{ types: KrokiType[] }>("/admin/api/kroki/catalog");
  return (
    <Page
      title="Kroki"
      description="The diagram renderer behind every tool: health, a local Docker stack and a playground."
      actions={<Button variant="outline" size="sm" onClick={status.reload}><RefreshCw /> Re-check</Button>}
    >
      {status.error && <ErrorState error={status.error} />}
      {!status.data && !status.error && <Loading rows={3} />}
      {status.data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <StatusCard status={status.data} />
          <DockerCard status={status.data} reload={status.reload} />
        </div>
      )}
      {catalog.error && <ErrorState error={catalog.error} />}
      {catalog.data && <Playground types={catalog.data.types} />}
    </Page>
  );
}
