import { KeyRound, LogOut, Menu, Monitor, Moon, Power, Sun } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import { getToken, post, setToken } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { Brand, SidebarNav } from "./Sidebar";

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <Tooltip content={`Theme: ${theme} (click for ${next})`}>
      <Button variant="ghost" size="icon" aria-label={`Theme ${theme}`} data-testid="theme-toggle" onClick={() => setTheme(next)}>
        <Icon className="transition-transform duration-300 hover:rotate-12" />
      </Button>
    </Tooltip>
  );
}

function SignInDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { mode, refresh } = useSession();
  const [value, setValue] = React.useState("");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "local" ? "Enter setup token" : "Sign in"}</DialogTitle>
          <DialogDescription>
            {mode === "local"
              ? "Saving settings needs the one-time setup token printed by `uml-mcp admin` (or UML_MCP_ADMIN_TOKEN)."
              : "Paste an access token with the MCP.Admin app role, e.g. az account get-access-token --scope api://<client-id>/mcp.read --query accessToken -o tsv"}
          </DialogDescription>
        </DialogHeader>
        <Input
          type="password"
          autoComplete="off"
          placeholder="token"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label="token"
        />
        <DialogFooter>
          <Button
            onClick={() => {
              setToken(value.trim());
              setValue("");
              onOpenChange(false);
              refresh();
              toast.success("Token saved for this tab");
            }}
            disabled={!value.trim()}
          >
            Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StopDialog() {
  const { setStopped, mode } = useSession();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  return (
    <>
      <Tooltip content="Stop the UML-MCP server">
        <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setOpen(true)} data-testid="stop-button">
          <Power />
          <span className="hidden sm:inline">Stop</span>
        </Button>
      </Tooltip>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Stop the server?</DialogTitle>
            <DialogDescription>
              Connected MCP clients lose the connection.{" "}
              {mode === "enterprise"
                ? "On Kubernetes the pod is restarted automatically."
                : "Start it again with `uml-mcp admin` or your usual command."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={busy}
              data-testid="confirm-stop"
              onClick={async () => {
                setBusy(true);
                try {
                  await post("/admin/api/server/stop");
                  setStopped(true);
                  setOpen(false);
                } catch (e) {
                  toast.error(`Stop failed: ${(e as Error).message}`);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Stop server
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function TopBar() {
  const { overview, mode, stopped } = useSession();
  const [menu, setMenu] = React.useState(false);
  const [signIn, setSignIn] = React.useState(false);
  const hasToken = Boolean(getToken());
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-5">
      <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" data-testid="menu-button" onClick={() => setMenu(true)}>
        <Menu />
      </Button>
      <Dialog open={menu} onOpenChange={setMenu}>
        <DialogContent side="left" aria-describedby={undefined}>
          <DialogTitle className="sr-only">Navigation</DialogTitle>
          <div className="flex h-full flex-col gap-6 overflow-y-auto bg-sidebar px-3 py-4">
            <Brand />
            <SidebarNav onNavigate={() => setMenu(false)} />
          </div>
        </DialogContent>
      </Dialog>
      <div className="flex min-w-0 items-center gap-2">
        <span className={`relative flex size-2.5 ${stopped ? "" : ""}`}>
          {!stopped && <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-60" />}
          <span className={`relative inline-flex size-2.5 rounded-full ${stopped ? "bg-destructive" : "bg-success"}`} />
        </span>
        <span className="truncate text-sm font-medium" data-testid="server-status">
          {stopped ? "Stopped" : overview ? "Running" : "Connecting…"}
        </span>
        {overview && (
          <Badge variant="secondary" className="hidden sm:inline-flex">
            v{overview.version}
          </Badge>
        )}
        {mode !== "unknown" && (
          <Badge variant="outline" className="hidden sm:inline-flex">
            {mode === "local" ? "local" : `auth: ${overview?.mode}`}
          </Badge>
        )}
      </div>
      <div className="ml-auto flex items-center gap-1">
        {hasToken ? (
          <Tooltip content="Forget the token for this tab">
            <Button variant="ghost" size="icon" aria-label="Sign out" onClick={() => { setToken(null); location.reload(); }}>
              <LogOut />
            </Button>
          </Tooltip>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setSignIn(true)} data-testid="signin-button">
            <KeyRound />
            <span className="hidden sm:inline">{mode === "local" ? "Token" : "Sign in"}</span>
          </Button>
        )}
        <ThemeToggle />
        {!stopped && <StopDialog />}
      </div>
      <SignInDialog open={signIn} onOpenChange={setSignIn} />
    </header>
  );
}
