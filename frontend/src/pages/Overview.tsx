import { Activity, AlertTriangle, CheckCircle2, Circle, Clock, ShieldAlert, Timer } from "lucide-react";
import { Link } from "react-router-dom";
import { LatencyBars, TrafficChart } from "@/components/app/charts";
import { Empty, ErrorState, Loading, Page, StatCard } from "@/components/app/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getToken } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useSession } from "@/lib/session";
import type { MetricsSnapshot, SettingsState, TimePoint } from "@/lib/types";
import { formatDuration, formatNumber } from "@/lib/utils";

function GettingStarted({ settings }: { settings?: SettingsState }) {
  const { mode } = useSession();
  const steps = [
    { done: Boolean(settings?.setup_complete), label: "Run the setup", hint: "Pick a profile and features", to: "/setup" },
    { done: Boolean(settings?.effective?.audit?.enabled), label: "Turn on the audit trail", hint: "See every tool call in Activity", to: "/settings" },
    { done: mode !== "local" || Boolean(getToken()), label: "Unlock saving", hint: "Enter the setup token from the terminal", to: "/settings" },
    { done: false, label: "Connect an MCP client", hint: "VS Code, Cursor, Claude", to: "/clients" },
  ];
  const done = steps.filter((s) => s.done).length;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Getting started</CardTitle>
        <CardDescription>{done} of {steps.length} done</CardDescription>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${(done / steps.length) * 100}%` }} />
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        {steps.map((s) => (
          <Link key={s.label} to={s.to} className="flex items-center gap-3 rounded-md p-2 transition-colors hover:bg-muted">
            {s.done ? <CheckCircle2 className="size-5 text-success" /> : <Circle className="size-5 text-muted-foreground" />}
            <div>
              <div className={s.done ? "text-sm text-muted-foreground line-through" : "text-sm font-medium"}>{s.label}</div>
              <div className="text-xs text-muted-foreground">{s.hint}</div>
            </div>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}

export default function Overview() {
  const metrics = useApi<MetricsSnapshot>("/admin/api/metrics", 5000);
  const series = useApi<{ points: TimePoint[] }>("/admin/api/metrics/timeseries?minutes=60", 10000);
  const settings = useApi<SettingsState>("/admin/api/settings");
  const ops = metrics.data?.operations ?? [];
  const total = ops.reduce((n, o) => n + o.total, 0);
  const errors = ops.reduce((n, o) => n + o.error, 0);
  const denied = ops.reduce((n, o) => n + o.denied, 0);
  const p95 = Math.max(0, ...ops.map((o) => o.p95_ms ?? 0));
  const tools = ops.filter((o) => o.operation_type === "tool");

  return (
    <Page
      title="Overview"
      description="Health, traffic and latency of this UML-MCP server."
      actions={<Button asChild variant="outline" size="sm"><Link to="/metrics"><Activity />All metrics</Link></Button>}
    >
      {metrics.error && <ErrorState error={metrics.error} />}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Calls" value={formatNumber(total)} icon={Activity} hint="since start" />
        <StatCard label="Error rate" value={total ? `${formatNumber((errors / total) * 100, 1)}%` : "–"} icon={AlertTriangle} tone={errors ? "warning" : "success"} />
        <StatCard label="p95 latency" value={p95 ? `${formatNumber(p95)} ms` : "–"} icon={Timer} />
        <StatCard label="Denied" value={formatNumber(denied)} icon={ShieldAlert} tone={denied ? "destructive" : "default"} hint="auth & rate limits" />
        <StatCard label="Uptime" value={metrics.data ? formatDuration(metrics.data.uptime_seconds) : "–"} icon={Clock} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Traffic</CardTitle>
            <CardDescription>Calls, errors and denials per minute (last hour)</CardDescription>
          </CardHeader>
          <CardContent>
            {series.data ? <TrafficChart points={series.data.points} /> : <Loading rows={5} />}
          </CardContent>
        </Card>
        <GettingStarted settings={settings.data} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Tool latency</CardTitle>
          <CardDescription>p50 and p95 per MCP tool</CardDescription>
        </CardHeader>
        <CardContent>
          {tools.length ? (
            <LatencyBars data={tools.map((t) => ({ name: t.operation_name, p50: t.p50_ms, p95: t.p95_ms }))} />
          ) : (
            <Empty title="No tool calls yet">Ask your MCP client to draw a diagram, then come back.</Empty>
          )}
        </CardContent>
      </Card>
    </Page>
  );
}
