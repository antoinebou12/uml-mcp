import * as React from "react";
import { CodeBlock, ErrorState, Page } from "@/components/app/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/select";
import { api, get } from "@/lib/api";
import { useSession } from "@/lib/session";

const KINDS = ["entra-manifest", "az-script", "helm-values", "vscode", "visual-studio", "cursor", "claude-code"];

export default function Security() {
  const { overview, authError } = useSession();
  const [token, setToken] = React.useState("");
  const [check, setCheck] = React.useState<string>();
  const [kind, setKind] = React.useState(KINDS[0]);
  const [generated, setGenerated] = React.useState<string>();
  if (authError) return <Page title="Security"><ErrorState error={authError} /></Page>;
  return (
    <Page title="Security" description="Enterprise authentication status, token tester and deployment generators.">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Preflight</CardTitle><CardDescription>Identity provider metadata and signing keys</CardDescription></CardHeader>
          <CardContent><CodeBlock code={JSON.stringify({ preflight: overview?.preflight, signing_keys: overview?.signing_keys }, null, 2)} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Token tester</CardTitle><CardDescription>Shows which validation check fails. Never stored.</CardDescription></CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Textarea aria-label="token to check" value={token} onChange={(e) => setToken(e.target.value)} placeholder="eyJ…" className="font-mono text-xs" />
            <Button className="self-start" disabled={!token.trim()} onClick={async () => {
              try {
                setCheck(JSON.stringify(await api("/admin/api/token-check", { method: "POST", json: { token: token.trim() } }), null, 2));
              } catch (e) { setCheck((e as Error).message); }
            }}>Check token</Button>
            {check && <CodeBlock code={check} />}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Generators</CardTitle><CardDescription>Entra app registration, az script, Helm values and client configs</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex gap-2">
            <NativeSelect aria-label="generator" className="sm:w-60" value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map((k) => <option key={k}>{k}</option>)}
            </NativeSelect>
            <Button onClick={async () => {
              const out = await get<unknown>(`/admin/api/generate/${kind}`).catch((e: Error) => e.message);
              setGenerated(typeof out === "string" ? out : JSON.stringify(out, null, 2));
            }}>Generate</Button>
          </div>
          {generated && <CodeBlock code={generated} />}
        </CardContent>
      </Card>
    </Page>
  );
}
