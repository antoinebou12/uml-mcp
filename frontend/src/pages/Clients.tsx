import { Check, Plug } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { CodeBlock, Page } from "@/components/app/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { post } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function Clients() {
  const { mode } = useSession();
  const url = `${window.location.origin}/mcp`;
  const [done, setDone] = React.useState<Record<string, string>>({});
  const http = {
    vscode: JSON.stringify({ servers: { "uml-mcp": { type: "http", url } } }, null, 2),
    cursor: JSON.stringify({ mcpServers: { "uml-mcp": { url } } }, null, 2),
    "claude-code": `claude mcp add --transport http uml-mcp ${url}`,
    "claude-desktop": JSON.stringify({ mcpServers: { "uml-mcp": { command: "npx", args: ["mcp-remote", url] } } }, null, 2),
  };
  const stdio = JSON.stringify({ mcpServers: { "uml-mcp": { command: "uml-mcp", args: ["--transport", "stdio"] } } }, null, 2);
  const register = async (client: string) => {
    try {
      const res = await post<{ path: string | null; config: string }>(`/admin/api/clients/${client}`);
      setDone((d) => ({ ...d, [client]: res.path ?? res.config }));
      toast.success(res.path ? `Updated ${res.path}` : "Run the command shown to finish");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Page title="Clients" description="Connect VS Code / Copilot, Cursor, Claude Desktop and Claude Code.">
      {mode === "local" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Plug className="size-5" />One-click local install</CardTitle>
            <CardDescription>Adds a stdio entry to the client's config on this machine (a backup is kept).</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {["vscode", "cursor", "claude-desktop", "claude-code"].map((c) => (
              <Button key={c} variant={done[c] ? "secondary" : "outline"} onClick={() => register(c)}>
                {done[c] && <Check />}{c}
              </Button>
            ))}
          </CardContent>
        </Card>
      )}
      <Tabs defaultValue="vscode">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
          {Object.keys(http).map((k) => <TabsTrigger key={k} value={k}>{k}</TabsTrigger>)}
          <TabsTrigger value="stdio">stdio</TabsTrigger>
        </TabsList>
        {Object.entries(http).map(([k, code]) => (
          <TabsContent key={k} value={k}><CodeBlock code={code} /></TabsContent>
        ))}
        <TabsContent value="stdio"><CodeBlock code={stdio} /></TabsContent>
      </Tabs>
    </Page>
  );
}
