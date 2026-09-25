import { Donut, TrafficChart } from "@/components/app/charts";
import { Empty, ErrorState, Loading, Page } from "@/components/app/common";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/lib/hooks";
import type { MetricsSnapshot, TimePoint } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

export default function Metrics() {
  const metrics = useApi<MetricsSnapshot>("/admin/api/metrics", 5000);
  const series = useApi<{ points: TimePoint[] }>("/admin/api/metrics/timeseries?minutes=180", 15000);
  const denials = Object.entries(metrics.data?.denial_reasons ?? {}).map(([name, value]) => ({ name, value }));
  const limited = Object.entries(metrics.data?.rate_limited ?? {}).map(([name, value]) => ({ name, value }));
  return (
    <Page title="Metrics" description="In-process counters since start. Scrape /metrics (Prometheus) for fleet-wide views.">
      {metrics.error && <ErrorState error={metrics.error} />}
      <Card>
        <CardHeader><CardTitle>Traffic (3 hours)</CardTitle></CardHeader>
        <CardContent>{series.data ? <TrafficChart points={series.data.points} height={280} /> : <Loading rows={6} />}</CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Denial reasons</CardTitle><CardDescription>Why calls were refused</CardDescription></CardHeader>
          <CardContent>{denials.length ? <Donut data={denials} /> : <Empty title="No denials" />}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Rate-limit rejections</CardTitle><CardDescription>429s per scope</CardDescription></CardHeader>
          <CardContent>{limited.length ? <Donut data={limited} /> : <Empty title="No 429s" />}</CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Per operation</CardTitle></CardHeader>
        {metrics.data?.operations.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Operation</TableHead><TableHead className="text-right">Calls</TableHead>
                <TableHead className="text-right">Errors</TableHead><TableHead className="text-right">Denied</TableHead>
                <TableHead className="text-right">p50</TableHead><TableHead className="text-right">p95</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {metrics.data.operations.map((o) => (
                <TableRow key={`${o.operation_type}:${o.operation_name}`}>
                  <TableCell><div className="font-medium">{o.operation_name}</div><div className="text-xs text-muted-foreground">{o.operation_type}</div></TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(o.total)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(o.error)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(o.denied)}</TableCell>
                  <TableCell className="text-right tabular-nums">{o.p50_ms ?? "–"}</TableCell>
                  <TableCell className="text-right tabular-nums">{o.p95_ms ?? "–"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <CardContent><Empty title="No operations recorded yet" /></CardContent>
        )}
      </Card>
    </Page>
  );
}
