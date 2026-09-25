import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useSession } from "@/lib/session";
import { GROUPS, NAV } from "./nav";

export function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
          <path d="M6.5 10v4.5a2 2 0 0 0 2 2H14" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="text-sm font-semibold">UML-MCP</div>
        <div className="text-[11px] text-muted-foreground">Console</div>
      </div>
    </div>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { mode } = useSession();
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      {GROUPS.map((group) => (
        <div key={group}>
          <div className="mb-1.5 px-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            {group}
          </div>
          <ul className="flex flex-col gap-0.5">
            {NAV.filter((n) => n.group === group && (!n.enterpriseOnly || mode === "enterprise")).map(
              ({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all duration-200",
                        isActive
                          ? "bg-sidebar-accent font-medium text-sidebar-foreground shadow-xs"
                          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                      )
                    }
                  >
                    <Icon className="size-4 transition-transform duration-200 group-hover:scale-110" />
                    {label}
                  </NavLink>
                </li>
              ),
            )}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-sidebar-border bg-sidebar px-3 py-4 md:flex">
      <Brand />
      <SidebarNav />
      <div className="mt-auto px-3 text-[11px] text-muted-foreground">
        Read the{" "}
        <a className="underline underline-offset-2" href="https://antoinebou12.github.io/uml-mcp/" target="_blank" rel="noreferrer">
          docs
        </a>
      </div>
    </aside>
  );
}
