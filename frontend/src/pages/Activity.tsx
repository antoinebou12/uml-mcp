import { Download, Filter } from "lucide-react";
import * as React from "react";
import { CodeBlock, Empty, ErrorState, Loading, Page } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { download, get } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { AuditRecord } from "@/lib/types";

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={status === "success" ? "success" : "destructive"}>{status}</Badge>;
}
export function DecisionBadge({ decision }: { decision: string }) {
  const variant = decision === "allow" ? "success" : decision === "deny" ? "destructive" : "secondary";
  return <Badge variant={variant}>{decision}</Badge>;
}

export default function Activity() {
  const [filters, setFilters] = React.useState({ status: "", decision: "", operation: "", user: "" });
  const [applied, setApplied] = React.useState(filters);
  const [offset, setOffset] = React.useState(0);
  const [selected, setSelected] = React.useState<AuditRecord>();
  const qs = new URLSearchParams({ limit: "50", offset: String(offset) });
  Object.entries(applied).forEach(([k, v]) => v && qs.set(k, v));
  const audit = useApi<{ enabled: boolean; records: AuditRecord[]; hint?: string }>(`/admin/api/audit?${qs}`, 5000);

  return (
    <Page
      title="Activity"
      description="Audit trail of tool, resource, prompt and REST calls (MXCP fields, inputs redacted)."
      actions={
        <Button variant="outline" size="sm" onClick={async () => download("uml-mcp-audit.jsonl", await get<string>("/admin/api/audit/export"), "application/x-ndjson")}>
          <Download />Export JSONL
        </Button>
      }
    >
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:flex-wrap sm:items-end">
          <NativeSelect aria-label="status" className="sm:w-36" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
            <option value="">Any status</option><option value="success">success</option><option value="error">error</option>
          </NativeSelect>
          <NativeSelect aria-label="decision" className="sm:w-36" value={filters.decision} onChange={(e) => setFilters({ ...filters, decision: e.target.value })}>
            <option value="">Any decision</option><option value="allow">allow</option><option value="deny">deny</option><option value="n/a">n/a</option>
          </NativeSelect>
          <Input aria-label="operation" className="sm:w-48" placeholder="Operation" value={filters.operation} onChange={(e) => setFilters({ ...filters, operation: e.target.value })} />
          <Input aria-label="user" className="sm:w-48" placeholder="User" value={filters.user} onChange={(e) => setFilters({ ...filters, user: e.target.value })} />
          <Button size="sm" onClick={() => { setOffset(0); setApplied(filters); }}><Filter />Apply</Button>
        </CardContent>
      </Card>
      {audit.error && <ErrorState error={audit.error} />}
      {audit.loading && !audit.data && <Loading rows={6} />}
      {audit.data && !audit.data.enabled && (
        <Empty title="Audit trail is off">Turn on <strong>Audit trail</strong> with the <code>memory</code> sink in Settings or Setup; it applies live.</Empty>
      )}
      {audit.data?.enabled && (audit.data.records.length === 0 ? (
        <Empty title="No matching records">Calls appear here within seconds.</Empty>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead><TableHead>Operation</TableHead><TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Decision</TableHead><TableHead className="hidden lg:table-cell">User</TableHead>
                <TableHead className="text-right">ms</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audit.data.records.map((r, i) => (
                <TableRow key={`${r.timestamp}-${i}`} className="cursor-pointer" onClick={() => setSelected(r)}>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{new Date(r.timestamp).toLocaleTimeString()}</TableCell>
                  <TableCell>
                    <div className="font-medium">{r.operation_name}</div>
                    <div className="text-xs text-muted-foreground">{r.operation_type} · {r.caller_type}</div>
                  </TableCell>
                  <TableCell><StatusBadge status={r.operation_status} /></TableCell>
                  <TableCell className="hidden md:table-cell"><DecisionBadge decision={r.policy_decision} /></TableCell>
                  <TableCell className="hidden text-xs lg:table-cell">{r.user_id ?? "–"}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.duration_ms ?? "–"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex justify-between border-t p-3">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - 50))}>Newer</Button>
            <Button variant="outline" size="sm" disabled={audit.data.records.length < 50} onClick={() => setOffset((o) => o + 50)}>Older</Button>
          </div>
        </Card>
      ))}
      <Dialog open={Boolean(selected)} onOpenChange={(v) => !v && setSelected(undefined)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>{selected?.operation_name}</DialogTitle></DialogHeader>
          {selected && <CodeBlock code={JSON.stringify(selected, null, 2)} />}
        </DialogContent>
      </Dialog>
    </Page>
  );
}
