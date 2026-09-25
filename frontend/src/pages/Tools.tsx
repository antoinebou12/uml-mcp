import { Puzzle, Wrench } from "lucide-react";
import { toast } from "sonner";
import { Empty, ErrorState, Loading, Page } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { post } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { PluginInfo, SaveResult, ToolInfo } from "@/lib/types";
import { announceSave } from "./Settings";

export default function Tools() {
  const tools = useApi<ToolInfo[]>("/admin/api/tools");
  const plugins = useApi<{ plugins: PluginInfo[] }>("/admin/api/plugins");
  return (
    <Page title="Tools & plugins" description="What this server exposes to MCP clients, and extensions installed next to it.">
      <Tabs defaultValue="tools">
        <TabsList>
          <TabsTrigger value="tools"><Wrench />Tools</TabsTrigger>
          <TabsTrigger value="plugins"><Puzzle />Plugins</TabsTrigger>
        </TabsList>
        <TabsContent value="tools">
          {tools.error && <ErrorState error={tools.error} />}
          {!tools.data && !tools.error && <Loading rows={5} />}
          <div className="grid gap-4 md:grid-cols-2">
            {tools.data?.map((t) => (
              <Card key={t.name} className={t.enabled ? "" : "opacity-60"}>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2 font-mono text-base">
                    {t.name}
                    <Badge variant={t.permission === "read" ? "secondary" : "warning"}>{t.permission}</Badge>
                    {!t.enabled && <Badge variant="outline">disabled</Badge>}
                    {t.rate_limit_per_minute && <Badge variant="outline">{t.rate_limit_per_minute}/min</Badge>}
                  </CardTitle>
                  <CardDescription>{t.description}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-1.5">
                  {Object.entries(t.annotations).map(([k, v]) => (
                    <Badge key={k} variant="outline" className="font-mono">{k}: {String(v)}</Badge>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="plugins">
          {plugins.error && <ErrorState error={plugins.error} />}
          {plugins.data && plugins.data.plugins.length === 0 && (
            <Empty title="No plugins installed">
              Plugins add renderers and tools. Install one (e.g. <code>pip install uml-mcp-plugin-hello</code>), then enable it here. See the plugin guide in the docs.
            </Empty>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {plugins.data?.plugins.map((p) => (
              <Card key={`${p.group}:${p.name}`}>
                <CardHeader className="flex-row items-start justify-between gap-4">
                  <div>
                    <CardTitle className="flex flex-wrap items-center gap-2">
                      {p.name}
                      <Badge variant="secondary">{p.group}</Badge>
                      {p.loaded && <Badge variant="success">loaded</Badge>}
                      {p.error && <Badge variant="destructive">error</Badge>}
                    </CardTitle>
                    <CardDescription className="mt-1.5">
                      {p.distribution ? `${p.distribution} ${p.version ?? ""}` : p.target || "not installed"}
                    </CardDescription>
                  </div>
                  <Switch
                    aria-label={`enable ${p.name}`}
                    checked={p.enabled}
                    disabled={p.error === "not installed" && !p.enabled}
                    onCheckedChange={async (on) => {
                      try {
                        announceSave(await post<SaveResult>(`/admin/api/plugins/${encodeURIComponent(p.name)}`, { enabled: on }));
                        plugins.reload();
                      } catch (e) {
                        toast.error((e as Error).message);
                      }
                    }}
                  />
                </CardHeader>
                <CardContent className="text-sm">
                  {p.error && <div className="text-destructive">{p.error}</div>}
                  {p.tools.length > 0 && <div>Tools: {p.tools.join(", ")}</div>}
                  {p.diagram_types.length > 0 && <div>Diagram types: {p.diagram_types.join(", ")}</div>}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </Page>
  );
}
