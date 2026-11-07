import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimePoint } from "@/lib/types";

const axis = { stroke: "var(--muted-foreground)", fontSize: 11, tickLine: false, axisLine: false };
const tooltipStyle = {
  contentStyle: {
    background: "var(--popover)",
    border: "1px solid var(--border)",
    borderRadius: "8px",
    color: "var(--popover-foreground)",
    fontSize: 12,
  },
};
export const CHART_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

function minuteLabel(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function TrafficChart({ points, height = 240 }: { points: TimePoint[]; height?: number }) {
  const data = points.map((p) => ({ ...p, label: minuteLabel(p.minute) }));
  return (
    <div style={{ height }} data-testid="traffic-chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" {...axis} minTickGap={24} />
          <YAxis {...axis} allowDecimals={false} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area type="monotone" dataKey="calls" name="Calls" stroke="var(--chart-1)" fill="var(--chart-1)" fillOpacity={0.1} strokeWidth={2} />
          <Area type="monotone" dataKey="errors" name="Errors" stroke="var(--destructive)" fill="var(--destructive)" fillOpacity={0.1} strokeWidth={2} />
          <Area type="monotone" dataKey="denied" name="Denied" stroke="var(--warning)" fillOpacity={0} strokeWidth={1.5} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function LatencyBars({ data, height = 240 }: { data: Array<{ name: string; p50: number | null; p95: number | null }>; height?: number }) {
  return (
    <div style={{ height }} data-testid="latency-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="name" {...axis} interval={0} tick={{ fontSize: 10 }} />
          <YAxis {...axis} unit="ms" />
          <Tooltip {...tooltipStyle} cursor={{ fill: "var(--muted)" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="p50" name="p50" fill="var(--chart-1)" fillOpacity={0.45} radius={[3, 3, 0, 0]} />
          <Bar dataKey="p95" name="p95" fill="var(--chart-1)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Donut({ data, height = 220 }: { data: Array<{ name: string; value: number }>; height?: number }) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="80%" paddingAngle={2}>
            {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
          </Pie>
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
