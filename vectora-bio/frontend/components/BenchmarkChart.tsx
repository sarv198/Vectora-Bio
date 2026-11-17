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
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-[12px] shadow-[0_4px_14px_rgba(0,0,0,0.08)]">
      <p className="mb-1 font-medium text-ink">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className="tabular flex items-center gap-2 text-ink-2">
          <span className="h-2 w-2 rounded-[1px]" style={{ background: entry.color }} />
          {entry.name}
          <span className="ml-auto pl-4 text-ink">{(entry.value * 100).toFixed(1)}%</span>
        </p>
      ))}
    </div>
  );
}

/** Grouped bars: one group per metric, one bar per model (method(s) vs. baseline). */
export function BenchmarkChart({ data, series }: { data: Record<string, number | string>[]; series: BenchmarkSeries[] }) {
  return (
    <div style={{ height: 220 }} role="img" aria-label="Method versus baseline for each metric">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: -8 }} barGap={2} barCategoryGap="26%">
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="metric"
            tick={{ fill: "var(--ink-2)", fontSize: 11.5 }}
            axisLine={{ stroke: "var(--line-strong)" }}
            tickLine={false}
            interval={0}
          />
          <YAxis
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fill: "var(--ink-3)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip />} isAnimationActive={false} />
          <Legend
            itemSorter={(item) => series.findIndex((s) => s.key === item.dataKey)}
            iconType="square"
            iconSize={8}
            align="left"
            wrapperStyle={{ fontSize: 12, paddingLeft: 44 }}
            formatter={(value: string) => <span style={{ color: "var(--ink-2)" }}>{value}</span>}
          />
          {series.map((s) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color}
              radius={[3, 3, 0, 0]}
              maxBarSize={20}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
