import { ArrowLeft, ArrowRight, Boxes, Building2, Check, Container, Laptop, PartyPopper, Rocket } from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { CodeBlock, ErrorState, Loading, Page } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ApiError, post, postRead, put } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import type { SaveResult, SettingsSchema, SettingsState } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS = ["Profile", "Features", "Clients", "Review"] as const;
const PROFILES = [
  { key: "local", title: "Local", icon: Laptop, text: "One user on this machine. Stdio clients (VS Code, Cursor, Claude), files in ~/uml-mcp." },
  { key: "docker", title: "Docker / server", icon: Container, text: "One host over HTTP. Local Kroki, in-memory rendering, JSON logs, rate limits." },
  { key: "enterprise", title: "Enterprise", icon: Building2, text: "Kubernetes + Microsoft Entra ID. Audit to your SIEM, metrics, per-user limits." },
];
const CLIENTS = [
  { key: "vscode", title: "VS Code / GitHub Copilot" },
  { key: "cursor", title: "Cursor" },
  { key: "claude-desktop", title: "Claude Desktop" },
  { key: "claude-code", title: "Claude Code" },
];

function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex items-center gap-2 overflow-x-auto" aria-label="Setup progress">
      {STEPS.map((label, i) => (
        <li key={label} className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "grid size-7 place-items-center rounded-full border text-xs font-medium transition-all duration-300",
              i < step && "border-primary bg-primary text-primary-foreground",
              i === step && "border-primary ring-4 ring-primary/15",
            )}
          >
            {i < step ? <Check className="size-3.5" /> : i + 1}
          </span>
          <span className={cn("text-sm", i === step ? "font-medium" : "text-muted-foreground")}>{label}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-border sm:w-10" />}
        </li>
      ))}
    </ol>
  );
}

export default function Setup() {
  const { mode } = useSession();
  const schema = useApi<SettingsSchema>("/admin/api/settings/schema");
  const current = useApi<SettingsState>("/admin/api/settings");
  const [step, setStep] = React.useState(0);
  const [profile, setProfile] = React.useState("local");
  const [features, setFeatures] = React.useState<Set<string>>(new Set());
  const [kroki, setKroki] = React.useState("");
  const [clients, setClients] = React.useState<Set<string>>(new Set());
  const [preview, setPreview] = React.useState<{ yaml: string; data: Record<string, unknown> }>();
  const [result, setResult] = React.useState<SaveResult>();
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (schema.data) setFeatures(new Set(schema.data.features.filter((f) => f.defaults.includes(profile)).map((f) => f.key)));
  }, [profile, schema.data]);

  React.useEffect(() => {
    if (step !== 3) return;
    const overrides: Record<string, unknown> = {
      setup: { completed_at: new Date().toISOString().slice(0, 19) + "Z", profile, features: [...features].sort() },
    };
    if (kroki.trim()) overrides.rendering = { kroki_server: kroki.trim() };
    postRead<{ yaml: string; data: Record<string, unknown> }>("/admin/api/setup/preview", {
      profile, features: [...features], overrides,
    }).then(setPreview).catch((e) => toast.error((e as Error).message));
  }, [step, profile, features, kroki]);

  if (schema.error) return <Page title="Setup"><ErrorState error={schema.error} /></Page>;
  if (!schema.data) return <Page title="Setup"><Loading rows={6} /></Page>;

  const finish = async () => {
    if (!preview) return;
    setBusy(true);
    try {
      const { version: _v, ...sections } = preview.data;
      void _v;
      const saved = await put<SaveResult>("/admin/api/settings", { data: sections });
      if (mode === "local") {
        for (const c of clients) {
          try {
            await post(`/admin/api/clients/${c}`);
          } catch (e) {
            toast.error(`${c}: ${(e as Error).message}`);
          }
        }
      }
      setResult(saved);
      current.reload();
    } catch (e) {
      const err = e as ApiError;
      toast.error(err.status === 401 ? "Enter the setup token from the terminal (top bar → Token)." : err.message);
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <Page title="Setup complete">
        <Card className="mx-auto w-full max-w-2xl text-center animate-in zoom-in-95 fade-in-0 duration-500" data-testid="setup-done">
          <CardHeader className="items-center">
            <div className="mb-2 grid size-14 place-items-center rounded-full bg-success/15 text-success">
              <PartyPopper className="size-7" />
            </div>
            <CardTitle className="text-xl">UML-MCP is configured</CardTitle>
            <CardDescription>Saved to {result.saved}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-left">
            {result.restart_required.length > 0 && (
              <div className="rounded-lg border border-warning/50 bg-warning/10 p-3 text-sm">
                Restart the server to apply: {result.restart_required.slice(0, 6).join(", ")}
                {result.restart_required.length > 6 && "…"}
              </div>
            )}
            <ul className="flex flex-col gap-2 text-sm">
              <li>1. Restart your MCP client and ask: <em>“Draw a sequence diagram of a login”</em>.</li>
              <li>2. Watch calls arrive in <Link className="underline" to="/activity">Activity</Link>.</li>
              <li>3. Fine-tune anything in <Link className="underline" to="/settings">Settings</Link>.</li>
            </ul>
            <div className="flex justify-center gap-2">
              <Button asChild><Link to="/overview">Go to overview</Link></Button>
              <Button variant="outline" onClick={() => { setResult(undefined); setStep(0); }}>Run again</Button>
            </div>
          </CardContent>
        </Card>
      </Page>
    );
  }

  return (
    <Page title="Setup" description="Configure UML-MCP in four steps. Everything can be changed later in Settings.">
      {current.data?.setup_complete && (
        <div className="rounded-lg border bg-muted/40 p-3 text-sm">
          Setup already completed ({String(current.data.setup?.profile ?? "")}). Running it again replaces the configuration; a backup is kept.
        </div>
      )}
      <Stepper step={step} />
      <div key={step} className="animate-in fade-in-0 slide-in-from-right-4 duration-300">
        {step === 0 && (
          <div className="grid gap-4 md:grid-cols-3">
            {PROFILES.map(({ key, title, icon: Icon, text }) => (
              <button
                key={key}
                onClick={() => setProfile(key)}
                data-profile={key}
                className={cn(
                  "rounded-xl border bg-card p-5 text-left shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md",
                  profile === key && "border-primary ring-2 ring-primary/20",
                )}
              >
                <div className="flex items-center justify-between">
                  <Icon className="size-6" />
                  {profile === key && <Badge><Check />Selected</Badge>}
                </div>
                <div className="mt-4 font-semibold">{title}</div>
                <p className="mt-1 text-sm text-muted-foreground">{text}</p>
              </button>
            ))}
          </div>
        )}
        {step === 1 && (
          <div className="flex flex-col gap-4">
            <div className="grid gap-3 md:grid-cols-2">
              {schema.data.features.map((f) => (
                <label
                  key={f.key}
                  htmlFor={`feat-${f.key}`}
                  className={cn(
                    "flex cursor-pointer items-start gap-4 rounded-xl border bg-card p-4 transition-colors hover:bg-muted/40",
                    features.has(f.key) && "border-primary/50",
                  )}
                >
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{f.title}</span>
                      <Badge variant="secondary">{f.category}</Badge>
                      <Badge variant={f.apply === "live" ? "success" : "outline"}>{f.apply === "live" ? "live" : "restart"}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{f.description}</p>
                  </div>
                  <Switch
                    id={`feat-${f.key}`}
                    checked={features.has(f.key)}
                    onCheckedChange={(on) =>
                      setFeatures((s) => {
                        const next = new Set(s);
                        if (on) next.add(f.key); else next.delete(f.key);
                        return next;
                      })
                    }
                  />
                </label>
              ))}
            </div>
            <div className="grid max-w-xl gap-1.5">
              <Label htmlFor="kroki">Kroki server (optional)</Label>
              <Input id="kroki" placeholder="https://kroki.io" value={kroki} onChange={(e) => setKroki(e.target.value)} />
              <p className="text-xs text-muted-foreground">Self-host Kroki to keep diagram source inside your network.</p>
            </div>
          </div>
        )}
        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Boxes className="size-5" />MCP clients</CardTitle>
              <CardDescription>
                {mode === "local"
                  ? "Register the local stdio server in these clients when you finish (a backup of each config is kept)."
                  : "Client configs for a deployed server are on the Clients page."}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {CLIENTS.map((c) => (
                <label key={c.key} className="flex items-center justify-between rounded-lg border p-3">
                  <span className="text-sm font-medium">{c.title}</span>
                  <Switch
                    disabled={mode !== "local"}
                    checked={clients.has(c.key)}
                    onCheckedChange={(on) => setClients((s) => { const n = new Set(s); if (on) n.add(c.key); else n.delete(c.key); return n; })}
                  />
                </label>
              ))}
            </CardContent>
          </Card>
        )}
        {step === 3 && (
          <Card>
            <CardHeader>
              <CardTitle>Review</CardTitle>
              <CardDescription>This is the uml-mcp.yaml that will be written to {current.data?.path}.</CardDescription>
            </CardHeader>
            <CardContent>{preview ? <CodeBlock code={preview.yaml} /> : <Loading rows={6} />}</CardContent>
          </Card>
        )}
      </div>
      <div className="flex justify-between">
        <Button variant="outline" onClick={() => setStep((s) => s - 1)} disabled={step === 0}>
          <ArrowLeft />Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep((s) => s + 1)} data-testid="setup-next">Next<ArrowRight /></Button>
        ) : (
          <Button onClick={finish} disabled={busy || !preview} data-testid="setup-finish">
            <Rocket />{busy ? "Saving…" : "Save & finish"}
          </Button>
        )}
      </div>
    </Page>
  );
}
