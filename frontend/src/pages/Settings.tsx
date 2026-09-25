import { Activity, Download, Gauge, Image, ListChecks, Puzzle, RotateCcw, Save, ScrollText, Server, Shield, Wrench, ChartLine, type LucideIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { ErrorState, Loading, Page } from "@/components/app/common";
import { Field } from "@/components/app/SchemaForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/select";
import { ApiError, download, get, post, postRead, put } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { SaveResult, SettingsSchema, SettingsState } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  image: Image, server: Server, wrench: Wrench, gauge: Gauge, "list-checks": ListChecks,
  "scroll-text": ScrollText, "chart-line": ChartLine, activity: Activity, puzzle: Puzzle, shield: Shield,
};

type Draft = Record<string, Record<string, unknown> | undefined>;

export function announceSave(result: SaveResult) {
  const restart = result.restart_required.length;
  toast.success(result.changed.length ? `Saved ${result.changed.length} change(s)` : "Nothing changed", {
    description: restart
      ? `Restart needed for: ${result.restart_required.join(", ")}`
      : result.changed.length ? "Applied live, no restart needed." : undefined,
  });
}

export default function Settings() {
  const schema = useApi<SettingsSchema>("/admin/api/settings/schema");
  const state = useApi<SettingsState>("/admin/api/settings");
  const [draft, setDraft] = React.useState<Draft>();
  const [active, setActive] = React.useState("rendering");
  const [busy, setBusy] = React.useState(false);
  const [resetOpen, setResetOpen] = React.useState(false);
  const [profile, setProfile] = React.useState("local");

  React.useEffect(() => {
    if (state.data) setDraft(structuredClone(state.data.data) as Draft);
  }, [state.data]);

  const dirty = React.useMemo(
    () => Boolean(state.data && draft && JSON.stringify(draft) !== JSON.stringify(state.data.data)),
    [draft, state.data],
  );
  React.useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (schema.error || state.error) return <Page title="Settings"><ErrorState error={(schema.error ?? state.error)!} /></Page>;
  if (!schema.data || !state.data || !draft) return <Page title="Settings"><Loading rows={8} /></Page>;

  const section = schema.data.sections.find((s) => s.key === active) ?? schema.data.sections[0];
  const readOnly = !state.data.writable;

  const save = async () => {
    setBusy(true);
    try {
      await postRead("/admin/api/settings/validate", { data: draft });
      const result = await put<SaveResult>("/admin/api/settings", { data: draft });
      announceSave(result);
      state.reload();
    } catch (e) {
      const err = e as ApiError;
      toast.error(err.status === 401 ? "Enter the setup token (top bar) to save." : err.message);
    } finally {
      setBusy(false);
    }
  };

  const reset = async (body: Record<string, string>) => {
    setBusy(true);
    try {
      announceSave(await post<SaveResult>("/admin/api/settings/reset", body));
      state.reload();
      setResetOpen(false);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page
      title="Settings"
      description={`Editing ${state.data.path}. Environment variables always win over the file.`}
      actions={
        <>
          <Button variant="outline" size="sm" onClick={async () => download("uml-mcp.yaml", await get<string>("/admin/api/config/download"), "application/yaml")}>
            <Download />YAML
          </Button>
          <Button variant="outline" size="sm" onClick={() => setResetOpen(true)} disabled={readOnly}>
            <RotateCcw />Reset all
          </Button>
          <Button size="sm" onClick={save} disabled={!dirty || busy || readOnly} data-testid="save-settings">
            <Save />{busy ? "Saving…" : "Save"}
          </Button>
        </>
      }
    >
      {readOnly && (
        <div className="rounded-lg border border-warning/50 bg-warning/10 p-3 text-sm">
          This file is read-only here (for example a Kubernetes ConfigMap). Download the YAML and apply it through your deployment.
        </div>
      )}
      {dirty && <div className="text-xs text-warning animate-in fade-in-0">You have unsaved changes.</div>}
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto lg:flex-col">
          {schema.data.sections.map((s) => {
            const Icon = ICONS[s.icon] ?? Wrench;
            return (
              <button
                key={s.key}
                onClick={() => setActive(s.key)}
                data-section={s.key}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
                  s.key === section.key ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted/60",
                )}
              >
                <Icon className="size-4" />{s.title}
              </button>
            );
          })}
        </nav>
        <Card key={section.key} className="animate-in fade-in-0 slide-in-from-right-2 duration-300">
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                {section.title}
                <Badge variant={section.apply === "live" ? "success" : "outline"}>
                  {section.apply === "live" ? "applies live" : "restart to apply"}
                </Badge>
              </CardTitle>
              <CardDescription className="mt-1.5">{section.description}</CardDescription>
            </div>
            <Button variant="ghost" size="sm" disabled={readOnly || busy} onClick={() => reset({ section: section.key })}>
              <RotateCcw />Reset
            </Button>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {Object.entries(section.schema.properties ?? {}).map(([key, sub]) => {
              const path = `${section.key}.${key}`;
              return (
                <Field
                  key={path}
                  path={path}
                  name={key}
                  schema={sub}
                  root={section.schema}
                  value={draft[section.key]?.[key]}
                  effective={state.data!.effective[section.key]?.[key]}
                  locked={state.data!.env_locked[path]}
                  restart={section.apply === "restart" || schema.data!.restart_fields.includes(path)}
                  disabled={readOnly}
                  onChange={(v) =>
                    setDraft((d) => {
                      const next = { ...(d ?? {}) };
                      const sec = { ...(next[section.key] ?? {}) };
                      if (v === undefined) delete sec[key]; else sec[key] = v;
                      next[section.key] = Object.keys(sec).length ? sec : undefined;
                      if (!next[section.key]) delete next[section.key];
                      return next;
                    })
                  }
                />
              );
            })}
          </CardContent>
        </Card>
      </div>
      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset all settings?</DialogTitle>
            <DialogDescription>Every section is replaced with the chosen profile's defaults. A backup of the current file is kept.</DialogDescription>
          </DialogHeader>
          <NativeSelect aria-label="profile" value={profile} onChange={(e) => setProfile(e.target.value)}>
            {schema.data.profiles.map((p) => <option key={p} value={p}>{p}</option>)}
          </NativeSelect>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetOpen(false)}>Cancel</Button>
            <Button variant="destructive" disabled={busy} onClick={() => reset({ profile })} data-testid="confirm-reset">Reset to {profile}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  );
}
