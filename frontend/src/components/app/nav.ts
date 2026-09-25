import {
  Activity,
  BadgeCheck,
  ChartLine,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Plug,
  Puzzle,
  Rocket,
  ScrollText,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  group: "Overview" | "Configure" | "Observe" | "Extend";
  enterpriseOnly?: boolean;
}

export const NAV: NavItem[] = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard, group: "Overview" },
  { to: "/setup", label: "Setup", icon: Rocket, group: "Overview" },
  { to: "/settings", label: "Settings", icon: Settings, group: "Configure" },
  { to: "/clients", label: "Clients", icon: Plug, group: "Configure" },
  { to: "/security", label: "Security", icon: ShieldCheck, group: "Configure", enterpriseOnly: true },
  { to: "/activity", label: "Activity", icon: ListChecks, group: "Observe" },
  { to: "/logs", label: "Logs", icon: ScrollText, group: "Observe" },
  { to: "/metrics", label: "Metrics", icon: ChartLine, group: "Observe" },
  { to: "/limits", label: "Rate limits", icon: Gauge, group: "Observe" },
  { to: "/tools", label: "Tools & plugins", icon: Puzzle, group: "Extend" },
  { to: "/lint", label: "Quality", icon: BadgeCheck, group: "Extend" },
];

export const GROUPS: NavItem["group"][] = ["Overview", "Configure", "Observe", "Extend"];
export { Activity };
