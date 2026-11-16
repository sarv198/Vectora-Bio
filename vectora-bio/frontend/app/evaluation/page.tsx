"use client";

import { BarChart3, CheckCircle2, Info, Play, XCircle } from "lucide-react";
import { useMemo, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { BenchmarkChart, type BenchmarkSeries } from "@/components/BenchmarkChart";
import { Button, Card, Checkbox, EmptyState, Field, LoadingState, PageHeader, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { formatCount, optionalNumber } from "@/lib/format";
import { useApiMutation, useApiQuery } from "@/lib/hooks";
import type { EvaluationRecord, FoldAudit, SplitStrategy } from "@/lib/types";

const STRATEGIES: { value: SplitStrategy; label: string; hint: string }[] = [
  { value: "random", label: "Random split", hint: "Compounds assigned to folds at random." },
  {
    value: "target_group",
    label: "Unseen targets",
    hint: "Compounds sharing a designed target are held out together: tests generalization to new targets.",
  },
];

const TASKS: { key: string; title: string; question: string }[] = [
  {
    key: "similarity",
    title: "Compound similarity",
    question: "Do a held-out compound's nearest neighbours share its MoA?",
  },
  { key: "moa", title: "MoA inference", question: "Is a held-out compound's hidden MoA recovered?" },
  {
    key: "targets",
    title: "Target prioritization",
    question: "Does a held-out compound's annotated target rank in the top of 160 genes?",
  },
];

const MODELS: Record<string, BenchmarkSeries> = {
  method: { key: "method", label: "Method", color: "var(--series-1)" },
  combined: { key: "combined", label: "Phenotype + similar compounds", color: "var(--series-1)" },
  phenotype_only: { key: "phenotype_only", label: "Phenotype only", color: "var(--series-2)" },
  baseline: { key: "baseline", label: "Baseline", color: "var(--series-baseline)" },
};

const METRIC_LABELS: Record<string, string> = {
  top1_accuracy: "Top-1 accuracy",
  top5_accuracy: "Top-5 accuracy",
  top1_accuracy_recoverable: "Top-1 (recoverable)",
  macro_f1: "Macro-F1",
  mrr: "MRR",
};

function metricLabel(metric: string): string {
  if (METRIC_LABELS[metric]) return METRIC_LABELS[metric];
  const match = metric.match(/^(\w+?)_at_(\d+)$/);
  if (match) {
    const names: Record<string, string> = { precision: "Precision", recall: "Recall", ndcg: "nDCG", hit: "Hit" };
    return `${names[match[1]] ?? match[1]}@${match[2]}`;
  }
  return metric;
}

function pct(value: number | undefined): string {
  return value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

interface Row {
  metric: string;
  values: Record<string, EvaluationRecord>;
}

function TaskCard({ task, records }: { task: (typeof TASKS)[number]; records: EvaluationRecord[] }) {
  const rows: Row[] = [];
  for (const record of records) {
    const metric = String(record.parameters?.metric ?? record.metric_name.split(".")[1]);
    let row = rows.find((r) => r.metric === metric);
    if (!row) {
      row = { metric, values: {} };
      rows.push(row);
    }
    row.values[String(record.parameters?.model)] = record;
  }
  const models = ["combined", "method", "phenotype_only", "baseline"].filter((m) => rows.some((r) => r.values[m]));
  const methodKeys = models.filter((m) => m !== "baseline");
  const series = models.map((m) => MODELS[m]);
  const chartData = rows.map((row) => ({
    metric: metricLabel(row.metric),
    ...Object.fromEntries(models.map((m) => [m, row.values[m]?.metric_value ?? 0])),
  }));
  const n = rows[0] ? Object.values(rows[0].values)[0]?.sample_count : 0;
  const method = rows[0]?.values[methodKeys[0]]?.evaluation_method;
  const baseline = rows[0]?.values.baseline?.evaluation_method;

  return (
    <Card title={task.title} actions={<span className="text-xs text-ink-3">{formatCount(n)} held-out queries</span>}>
      <p className="mb-3 text-sm text-ink-2">{task.question}</p>
      <BenchmarkChart data={chartData} series={series} />
      <div className="-mx-4 mt-3 overflow-x-auto border-t border-line">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs text-ink-3">
            <tr>
              <th className="px-4 py-2 font-medium">Metric</th>
              {models.map((m) => (
                <th key={m} className="px-3 py-2 text-right font-medium">
                  {MODELS[m].label}
                </th>
              ))}
              <th className="px-4 py-2 text-right font-medium" title="Best method ÷ baseline">
                vs. baseline
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const best = Math.max(...methodKeys.map((m) => row.values[m]?.metric_value ?? 0));
              const base = row.values.baseline?.metric_value;
              const lift = base ? best / base : null;
              return (
                <tr key={row.metric} className="border-b border-line last:border-0">
                  <td className="px-4 py-1.5">{metricLabel(row.metric)}</td>
                  {models.map((m) => {
                    const record = row.values[m];
                    const std = record?.parameters?.fold_std as number | null | undefined;
                    return (
                      <td key={m} className="tabular px-3 py-1.5 text-right">
                        {pct(record?.metric_value)}
                        {typeof std === "number" && (
                          <span className="text-[11px] text-ink-3"> ±{(std * 100).toFixed(1)}</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="tabular px-4 py-1.5 text-right font-medium">
                    {lift === null ? "—" : `${lift.toFixed(1)}×`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-ink-3">
        Method: {method}. Baseline: {baseline}. ± is the standard deviation across folds.
      </p>
    </Card>
  );
}

function AuditCard({ audit, strategy }: { audit: FoldAudit | undefined; strategy: SplitStrategy }) {
  if (!audit) return null;
  const checks: [string, boolean][] = [
    ["Reference and test compounds never overlap", audit.reference_test_disjoint],
    ["Every compound tested exactly once", audit.each_item_tested_once],
    ["Test compounds' annotations hidden from predictions", audit.test_annotations_hidden],
  ];
  if (strategy === "target_group") checks.push(["No designed target on both sides of a split", audit.groups_disjoint]);
  return (
    <Card title="Leakage audit">
      <ul className="space-y-1 text-sm">
        {checks.map(([label, ok]) => (
          <li key={label} className="flex items-center gap-2">
            {ok ? (
              <CheckCircle2 className="h-4 w-4 text-ok" aria-label="passed" />
            ) : (
              <XCircle className="h-4 w-4 text-danger" aria-label="failed" />
            )}
            {label}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-ink-3">
        {audit.n_folds}-fold cross-validation over {audit.n_items} compounds.
      </p>
    </Card>
  );
}

export default function EvaluationPage() {
  const { data, error, loading, reload } = useApiQuery(() => api.listEvaluations(), []);
  const runner = useApiMutation(api.runEvaluation);
  const [strategies, setStrategies] = useState<SplitStrategy[]>(["random", "target_group"]);
  const [folds, setFolds] = useState("5");
  const [seed, setSeed] = useState("0");
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<SplitStrategy>("random");

  const runs = useMemo(() => {
    const byRun = new Map<string, EvaluationRecord[]>();
    for (const record of data?.results ?? []) {
      const runId = String(record.parameters?.run_id ?? "legacy");
      byRun.set(runId, [...(byRun.get(runId) ?? []), record]);
    }
    return [...byRun.entries()].filter(([runId]) => runId !== "legacy");
  }, [data]);
  const runId = selectedRun ?? runs[0]?.[0] ?? null;
  const runRecords = runs.find(([id]) => id === runId)?.[1] ?? [];
  const available = STRATEGIES.filter((s) => runRecords.some((r) => r.parameters?.split_strategy === s.value));
  const activeStrategy = available.some((s) => s.value === strategy) ? strategy : (available[0]?.value ?? "random");
  const shown = runRecords.filter((r) => r.parameters?.split_strategy === activeStrategy);
  const audit = shown[0]?.parameters?.audit as FoldAudit | undefined;
  const runDate = runRecords[0]?.created_at ? new Date(runRecords[0].created_at).toLocaleString() : null;

  const run = async () => {
    await runner.run({
      split_strategies: strategies,
      n_folds: optionalNumber(folds) ?? 5,
      seed: optionalNumber(seed) ?? 0,
    });
    setSelectedRun(null);
    reload();
  };

  return (
    <>
      <PageHeader
        title="Evaluation"
        description="Held-out benchmarks: every prediction is made for compounds removed from the reference set, then scored against their hidden annotations and compared with a baseline."
        icon={<BarChart3 className="h-5 w-5" />}
      />
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Run benchmarks">
            <div className="space-y-3">
              <fieldset className="space-y-1.5">
                <legend className="mb-1 text-sm font-medium text-ink-2">Split strategies</legend>
                {STRATEGIES.map((s) => (
                  <Checkbox
                    key={s.value}
                    label={s.label}
                    title={s.hint}
                    checked={strategies.includes(s.value)}
                    onChange={() =>
                      setStrategies((current) =>
                        current.includes(s.value) ? current.filter((v) => v !== s.value) : [...current, s.value],
                      )
                    }
                  />
                ))}
              </fieldset>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Folds">
                  <TextInput type="number" min={2} max={20} value={folds} onChange={(e) => setFolds(e.target.value)} />
                </Field>
                <Field label="Seed">
                  <TextInput type="number" value={seed} onChange={(e) => setSeed(e.target.value)} />
                </Field>
              </div>
              <Button onClick={run} loading={runner.loading} disabled={strategies.length === 0} className="w-full">
                <Play className="h-4 w-4" aria-hidden /> Run benchmarks
              </Button>
              <p className="text-xs text-ink-3">Takes about 15 seconds on the JUMP pilot. Results are saved.</p>
            </div>
          </Card>
          {runs.length > 1 && (
            <Card title="Previous runs">
              <ul className="space-y-1 text-sm">
                {runs.map(([id, records]) => (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() => setSelectedRun(id)}
                      className={`w-full rounded px-2 py-1 text-left hover:bg-surface-2 ${id === runId ? "bg-accent-soft text-accent" : "text-ink-2"}`}
                    >
                      <span className="font-mono text-xs">{id}</span>
                      <span className="block text-xs text-ink-3">
                        {records[0]?.created_at ? new Date(records[0].created_at).toLocaleString() : ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="min-w-0 space-y-4">
          {runner.error && <ApiErrorNotice error={runner.error} />}
          {error ? (
            <ApiErrorNotice error={error} />
          ) : loading && !data ? (
            <LoadingState />
          ) : runRecords.length === 0 ? (
            <EmptyState title="No benchmark results yet">Run the benchmarks to measure every module on held-out compounds.</EmptyState>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div role="tablist" className="flex gap-1 border-b border-line">
                  {available.map((s) => (
                    <button
                      key={s.value}
                      role="tab"
                      type="button"
                      aria-selected={activeStrategy === s.value}
                      title={s.hint}
                      onClick={() => setStrategy(s.value)}
                      className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                        activeStrategy === s.value
                          ? "border-accent font-medium text-ink"
                          : "border-transparent text-ink-3 hover:text-ink"
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
                <span className="text-xs text-ink-3">
                  Run <span className="font-mono">{runId}</span>
                  {runDate ? ` · ${runDate}` : ""}
                </span>
              </div>
              {activeStrategy === "target_group" && (
                <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs text-ink-2">
                  <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  JUMP-Target pairs two compounds per target. Holding both out shows how the methods do on targets the
                  reference set has never seen, the harder and more realistic case for a new compound.
                </p>
              )}
              {TASKS.map((task) => {
                const records = shown.filter((r) => r.parameters?.task === task.key);
                return records.length ? <TaskCard key={task.key} task={task} records={records} /> : null;
              })}
              <AuditCard audit={audit} strategy={activeStrategy} />
            </>
          )}
        </div>
      </div>
    </>
  );
}
