import { BadgeCheck } from "lucide-react";
import { Empty, ErrorState, Loading, Page, StatCard } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/lib/hooks";
import type { LintIssue } from "@/lib/types";

interface Report {
  grade: string | null;
  score: number | null;
  token_estimate: number | null;
  counts: Record<string, number>;
  issues: LintIssue[];
  suppressed?: Array<LintIssue & { reason: string }>;
  wire_error?: string;
}

const SEVERITY = { error: "destructive", warning: "warning", info: "secondary" } as const;

export default function Lint() {
  const report = useApi<Report>("/admin/api/lint/report");
  if (report.error) return <Page title="Quality"><ErrorState error={report.error} /></Page>;
  if (!report.data) return <Page title="Quality"><Loading rows={5} /></Page>;
  const r = report.data;
  return (
    <Page title="Quality" description="`uml-mcp lint`: how well LLMs can use this server (mcpx grading) plus MXCP-style config checks.">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Grade" value={r.grade ?? "–"} icon={BadgeCheck} tone={r.grade === "A" ? "success" : "warning"} />
        <StatCard label="Score" value={r.score !== null ? `${r.score}/100` : "–"} icon={BadgeCheck} />
        <StatCard label="Connect-time tokens" value={r.token_estimate !== null ? `~${r.token_estimate}` : "–"} icon={BadgeCheck} hint="tools/list + resources + prompts" />
      </div>
      {r.wire_error && <div className="text-sm text-muted-foreground">Protocol checks unavailable: {r.wire_error}</div>}
      {(r.suppressed?.length ?? 0) > 0 && (
        <Card className="p-4 text-sm">
          <div className="mb-2 font-medium">Documented exceptions ({r.suppressed!.length})</div>
          <ul className="flex flex-col gap-1.5 text-muted-foreground">
            {r.suppressed!.map((s, n) => (
              <li key={n}><span className="font-mono text-xs text-foreground">{s.code}</span> on <span className="font-mono text-xs">{s.target}</span>: {s.reason}</li>
            ))}
          </ul>
        </Card>
      )}
      {r.issues.length === 0 ? <Empty title="No issues. Nice." /> : (
        <Card>
          <Table>
            <TableHeader><TableRow><TableHead>Severity</TableHead><TableHead>Rule</TableHead><TableHead>Target</TableHead><TableHead>Message</TableHead></TableRow></TableHeader>
            <TableBody>
              {r.issues.map((i, n) => (
                <TableRow key={n}>
                  <TableCell><Badge variant={SEVERITY[i.severity]}>{i.severity}</Badge></TableCell>
                  <TableCell className="font-mono text-xs">{i.code}</TableCell>
                  <TableCell className="font-mono text-xs">{i.target}</TableCell>
                  <TableCell>{i.message}{i.fix && <div className="text-xs text-muted-foreground">→ {i.fix}</div>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </Page>
  );
}
