"use client";

import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatScore } from "@/lib/format";

export interface ScoreDatum {
  label: string;
  value: number;
}

interface TooltipPayload {
  payload: ScoreDatum;
}

function ChartTooltip({ active, payload, valueLabel }: { active?: boolean; payload?: TooltipPayload[]; valueLabel: string }) {
  if (!active || !payload?.length) return null;
  const datum = payload[0].payload;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-ink">{datum.label}</p>
      <p className="tabular text-ink-2">
        {valueLabel}: {formatScore(datum.value)}
      </p>
    </div>
  );
}

/** Horizontal bars, one per candidate, in rank order. Single series, so no legend; the card title names it. */
export function ScoreChart({
  data,
  valueLabel = "Score",
  domain,
}: {
  data: ScoreDatum[];
  valueLabel?: string;
  domain?: [number, number];
}) {
  const height = Math.max(160, data.length * 30 + 40);
  const hasNegative = data.some((d) => d.value < 0);
  const xDomain = domain ?? [hasNegative ? -1 : 0, 1];

  return (
    <div style={{ height }} role="img" aria-label={`${valueLabel} by candidate`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke="var(--grid)" />
          <XAxis
            type="number"
            domain={xDomain}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: "var(--ink-3)", fontSize: 11 }}
            axisLine={{ stroke: "var(--line)" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={140}
            tick={{ fill: "var(--ink-2)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          {hasNegative && <ReferenceLine x={0} stroke="var(--ink-3)" />}
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            content={<ChartTooltip valueLabel={valueLabel} />}
            isAnimationActive={false}
          />
          <Bar dataKey="value" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
