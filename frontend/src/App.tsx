import { PowerOff } from "lucide-react";
import * as React from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { CodeBlock, ErrorState, Loading } from "@/components/app/common";
import { Sidebar } from "@/components/app/Sidebar";
import { TopBar } from "@/components/app/TopBar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider, useTheme } from "@/lib/theme";

const Overview = React.lazy(() => import("@/pages/Overview"));
const Setup = React.lazy(() => import("@/pages/Setup"));
const Settings = React.lazy(() => import("@/pages/Settings"));
const Activity = React.lazy(() => import("@/pages/Activity"));
const Logs = React.lazy(() => import("@/pages/Logs"));
const Metrics = React.lazy(() => import("@/pages/Metrics"));
const RateLimits = React.lazy(() => import("@/pages/RateLimits"));
const Tools = React.lazy(() => import("@/pages/Tools"));
const Clients = React.lazy(() => import("@/pages/Clients"));
const Security = React.lazy(() => import("@/pages/Security"));
const Lint = React.lazy(() => import("@/pages/Lint"));

function Stopped() {
  return (
    <div className="grid min-h-[70vh] place-items-center p-6">
      <Card className="w-full max-w-lg text-center animate-in zoom-in-95 fade-in-0 duration-500" data-testid="stopped">
        <CardHeader className="items-center">
          <div className="mb-2 grid size-14 place-items-center rounded-full bg-destructive/10 text-destructive"><PowerOff className="size-7" /></div>
          <CardTitle>Server stopped</CardTitle>
          <CardDescription>MCP clients are disconnected. Start it again with:</CardDescription>
        </CardHeader>
        <CardContent><CodeBlock code="uml-mcp admin" /></CardContent>
      </Card>
    </div>
  );
}

class PageBoundary extends React.Component<{ children: React.ReactNode }, { error?: Error }> {
  state: { error?: Error } = {};
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto w-full max-w-3xl p-6">
        <ErrorState error={new Error(`This page failed to load: ${this.state.error.message}`)} />
        <button className="mt-3 text-sm underline" onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}

function Shell() {
  const { stopped, authError, overview } = useSession();
  const { resolved } = useTheme();
  return (
    <div className="flex min-h-svh">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1">
          {stopped ? <Stopped /> : (
            <>
              {authError && !overview && (
                <div className="mx-auto w-full max-w-7xl p-4 sm:p-6"><ErrorState error={authError} /></div>
              )}
              <PageBoundary>
              <React.Suspense fallback={<div className="p-6"><Loading rows={6} /></div>}>
                <Routes>
                  <Route path="/" element={<Navigate to="/overview" replace />} />
                  <Route path="/overview" element={<Overview />} />
                  <Route path="/setup" element={<Setup />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/activity" element={<Activity />} />
                  <Route path="/logs" element={<Logs />} />
                  <Route path="/metrics" element={<Metrics />} />
                  <Route path="/limits" element={<RateLimits />} />
                  <Route path="/tools" element={<Tools />} />
                  <Route path="/clients" element={<Clients />} />
                  <Route path="/security" element={<Security />} />
                  <Route path="/lint" element={<Lint />} />
                  <Route path="*" element={<Navigate to="/overview" replace />} />
                </Routes>
              </React.Suspense>
              </PageBoundary>
            </>
          )}
        </main>
      </div>
      <Toaster theme={resolved} richColors closeButton position="bottom-right" />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <TooltipProvider>
        <SessionProvider>
          <HashRouter>
            <Shell />
          </HashRouter>
        </SessionProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
