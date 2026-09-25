import { Link } from "react-router-dom";
import { CodeBlock, Empty, ErrorState, Loading, Page } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/lib/hooks";

interface Limits {
  policy: { enabled: boolean; key: string; default: { requests_per_minute: number; burst: number } } & Record<string, unknown>;
  hot_keys: Array<{ scope: string; key: string; tokens_left: number }>;
  rejected: Record<string, number>;
}

export default function RateLimits() {
  const limits = useApi<Limits>("/admin/api/rate-limits", 5000);
  if (limits.error) return <Page title="Rate limits"><ErrorState error={limits.error} /></Page>;
  if (!limits.data) return <Page title="Rate limits"><Loading /></Page>;
  const { policy, hot_keys, rejected } = limits.data;
  return (
    <Page
      title="Rate limits"
      description="Token buckets per client or user. Limits are per process; use your gateway for global quotas."
      actions={<Button asChild variant="outline" size="sm"><Link to="/settings">Edit policy</Link></Button>}
    >
      <div className="flex flex-wrap gap-2">
        <Badge variant={policy.enabled ? "success" : "secondary"}>{policy.enabled ? "enabled" : "disabled"}</Badge>
        <Badge variant="outline">key: {policy.key}</Badge>
        <Badge variant="outline">{policy.default.requests_per_minute}/min, burst {policy.default.burst || policy.default.requests_per_minute}</Badge>
        {Object.entries(rejected).map(([scope, n]) => <Badge key={scope} variant="destructive">{scope}: {n} rejected</Badge>)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Busiest buckets</CardTitle></CardHeader>
          {hot_keys.length ? (
            <Table>
              <TableHeader><TableRow><TableHead>Scope</TableHead><TableHead>Key (hashed)</TableHead><TableHead className="text-right">Tokens left</TableHead></TableRow></TableHeader>
              <TableBody>
                {hot_keys.map((k) => (
                  <TableRow key={`${k.scope}${k.key}`}>
                    <TableCell>{k.scope}</TableCell><TableCell className="font-mono text-xs">{k.key}</TableCell>
                    <TableCell className="text-right tabular-nums">{k.tokens_left}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : <CardContent><Empty title="No active buckets" /></CardContent>}
        </Card>
        <Card>
          <CardHeader><CardTitle>Effective policy</CardTitle></CardHeader>
          <CardContent><CodeBlock code={JSON.stringify(policy, null, 2)} /></CardContent>
        </Card>
      </div>
    </Page>
  );
}
