"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface BenchmarkSeries {
  key: string;
  label: string;
  color: string;
}

interface TooltipEntry {
  name: string;
  value: number;
  color: string;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipEntry[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="mb-1 font-medium text-ink">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className="tabular flex items-center gap-2 text-ink-2">
          <span className="h-2 w-2 rounded-sm" style={{ background: entry.color }} />
          {entry.name}: {(entry.value * 100).toFixed(1)}%
        </p>
      ))}
    </div>
  );
}

/** Grouped bars: one group per metric, one bar per model (method(s) vs. baseline). */
export function BenchmarkChart({ data, series }: { data: Record<string, number | string>[]; series: BenchmarkSeries[] }) {
  return (
    <div style={{ height: 240 }} role="img" aria-label="Method versus baseline for each metric">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barGap={2} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="metric"
            tick={{ fill: "var(--ink-2)", fontSize: 11 }}
            axisLine={{ stroke: "var(--line)" }}
            tickLine={false}
            interval={0}
          />
          <YAxis
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: "var(--ink-3)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip />} isAnimationActive={false} />
          <Legend
            itemSorter={(item) => series.findIndex((s) => s.key === item.dataKey)}
            iconType="square"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }}
            formatter={(value: string) => <span style={{ color: "var(--ink-2)" }}>{value}</span>}
          />
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color}
              radius={[4, 4, 0, 0]}
              maxBarSize={22}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
