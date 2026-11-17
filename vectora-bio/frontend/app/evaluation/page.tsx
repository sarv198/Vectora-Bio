"use client";

import { Check, X } from "lucide-react";
import { useMemo } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { BenchmarkChart, type BenchmarkSeries } from "@/components/BenchmarkChart";
import { Em, Findings } from "@/components/QuerySummary";
import {
  Button,
  Checkbox,
  EmptyState,
  Field,
  InfoTip,
  LoadingState,
  Notice,
  PageHeader,
  Panel,
  Section,
  Select,
  TABLE,
  TD,
  TH,
  THEAD,
  TR,
  TableFrame,
  Tabs,
  TextInput,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatCount, optionalNumber } from "@/lib/format";
import { useApiMutation, useApiQuery } from "@/lib/hooks";
import { useSessionState } from "@/lib/session";
import type { EvaluationRecord, FoldAudit, SplitStrategy } from "@/lib/types";

const STRATEGIES: { value: SplitStrategy; label: string; hint: string }[] = [
  { value: "random", label: "Random split", hint: "Compounds assigned to folds at random." },
  {
    value: "target_group",
    label: "Unseen targets",
    hint: "Compounds sharing a designed target are held out together: tests generalisation to new targets.",
  },
];

const TASKS: { key: string; title: string; question: string; headline: string[] }[] = [
  {
    key: "similarity",
    title: "Compound similarity",
    question: "Do a held-out compound's nearest neighbours share its mechanism?",
    headline: ["recall_at_10", "precision_at_10"],
  },
  {
    key: "moa",
    title: "Mechanism of action",
    question: "Is a held-out compound's hidden mechanism recovered?",
    headline: ["top1_accuracy_recoverable", "top1_accuracy"],
  },
  {
    key: "targets",
    title: "Drug-to-gene matching",
    question: "Does a held-out compound's annotated target rank among the top genes?",
    headline: ["hit_at_10", "recall_at_10"],
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
  return value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`;
}

interface Row {
  metric: string;
  values: Record<string, EvaluationRecord>;
}

function taskRows(records: EvaluationRecord[]): Row[] {
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
  return rows;
}

function modelsOf(rows: Row[]): string[] {
  return ["combined", "method", "phenotype_only", "baseline"].filter((m) => rows.some((r) => r.values[m]));
}

function TaskSection({ task, records }: { task: (typeof TASKS)[number]; records: EvaluationRecord[] }) {
  const rows = taskRows(records);
  const models = modelsOf(rows);
  const methodKeys = models.filter((m) => m !== "baseline");
  const chartData = rows.map((row) => ({
    metric: metricLabel(row.metric),
    ...Object.fromEntries(models.map((m) => [m, row.values[m]?.metric_value ?? 0])),
  }));
  const n = rows[0] ? Object.values(rows[0].values)[0]?.sample_count : 0;
  const method = rows[0]?.values[methodKeys[0]]?.evaluation_method;
  const baseline = rows[0]?.values.baseline?.evaluation_method;

  return (
    <Section title={task.title} description={task.question} actions={`${formatCount(n)} held-out queries`}>
      <div className="grid gap-8 xl:grid-cols-2">
        <BenchmarkChart data={chartData} series={models.map((m) => MODELS[m])} />
        <div>
          <TableFrame>
            <table className={TABLE}>
              <thead className={THEAD}>
                <tr>
                  <th className={TH}>Metric</th>
                  {models.map((m) => (
                    <th key={m} className={`${TH.replace("whitespace-nowrap", "")} text-right align-bottom`}>
                      <span className="inline-flex items-start justify-end gap-1.5">
                        <span className="mt-[5px] h-2 w-2 shrink-0 rounded-[1px]" style={{ background: MODELS[m].color }} aria-hidden />
                        {MODELS[m].label}
                      </span>
                    </th>
                  ))}
                  <th className={`${TH} text-right`}>
                    <span className="inline-flex items-center gap-1">
                      Lift
                      <InfoTip side="bottom">Best method divided by the baseline.</InfoTip>
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const best = Math.max(...methodKeys.map((m) => row.values[m]?.metric_value ?? 0));
                  const base = row.values.baseline?.metric_value;
                  const lift = base ? best / base : null;
                  return (
                    <tr key={row.metric} className={TR}>
                      <td className={`${TD} py-2 text-ink-2`}>{metricLabel(row.metric)}</td>
                      {models.map((m) => {
                        const record = row.values[m];
                        const std = record?.parameters?.fold_std as number | null | undefined;
                        return (
                          <td key={m} className={`${TD} tabular py-2 text-right ${m === "baseline" ? "text-ink-3" : "text-ink"}`}>
                            {pct(record?.metric_value)}
                            {typeof std === "number" && (
                              <span className="block text-[11.5px] text-ink-3">±{(std * 100).toFixed(1)}</span>
                            )}
                          </td>
                        );
                      })}
                      <td className={`${TD} tabular py-2 text-right font-medium text-ink`}>
                        {lift === null ? "n/a" : `${lift.toFixed(1)}x`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableFrame>
          <p className="mt-2 flex items-center gap-1 text-[12px] text-ink-3">
            ± = standard deviation across folds
            <InfoTip>
              Method: {method}. Baseline: {baseline}.
            </InfoTip>
          </p>
        </div>
      </div>
    </Section>
  );
}

function headline(task: (typeof TASKS)[number], records: EvaluationRecord[]) {
  const rows = taskRows(records);
  const row = task.headline.map((m) => rows.find((r) => r.metric === m)).find(Boolean) ?? rows[0];
  if (!row) return null;
  const methods = modelsOf(rows).filter((m) => m !== "baseline");
  const bestKey = methods.reduce(
    (best, m) => ((row.values[m]?.metric_value ?? 0) > (row.values[best]?.metric_value ?? 0) ? m : best),
    methods[0],
  );
  const value = row.values[bestKey]?.metric_value;
  const base = row.values.baseline?.metric_value;
  return (
    <>
      {task.title}: <Em>{pct(value)}</Em> {metricLabel(row.metric)}
      {methods.length > 1 ? ` (${MODELS[bestKey].label.toLowerCase()})` : ""} vs {pct(base)} baseline
      {base ? ` (${(value! / base).toFixed(1)}x)` : ""}.
    </>
  );
}

function Audit({ audit, strategy }: { audit: FoldAudit | undefined; strategy: SplitStrategy }) {
  if (!audit) return null;
  const checks: [string, boolean][] = [
    ["Reference and test compounds never overlap", audit.reference_test_disjoint],
    ["Every compound tested exactly once", audit.each_item_tested_once],
    ["Test compounds' annotations hidden from predictions", audit.test_annotations_hidden],
  ];
  if (strategy === "target_group") checks.push(["No designed target on both sides of a split", audit.groups_disjoint]);
  return (
    <Section
      title="Leakage audit"
      description={`${audit.n_folds}-fold cross-validation over ${audit.n_items} compounds, checked on every run.`}
    >
      <ul className="divide-y divide-line border-y border-line text-[13.5px]">
        {checks.map(([label, ok]) => (
          <li key={label} className="flex items-center justify-between gap-4 py-2">
            <span className="text-ink-2">{label}</span>
            {ok ? (
              <span className="inline-flex items-center gap-1 text-ok">
                <Check className="h-4 w-4" aria-hidden /> Passed
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-danger">
                <X className="h-4 w-4" aria-hidden /> Failed
              </span>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}

export default function EvaluationPage() {
  const { data, error, loading, reload } = useApiQuery(() => api.listEvaluations(), []);
  const runner = useApiMutation(api.runEvaluation);
  const [strategies, setStrategies] = useSessionState<SplitStrategy[]>("evaluation.strategies", ["random", "target_group"]);
  const [folds, setFolds] = useSessionState("evaluation.folds", "5");
  const [seed, setSeed] = useSessionState("evaluation.seed", "0");
  const [selectedRun, setSelectedRun] = useSessionState<string | null>("evaluation.run", null);
  const [strategy, setStrategy] = useSessionState<SplitStrategy>("evaluation.strategy", "random");

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
  const runDate = (records: EvaluationRecord[]) =>
    records[0]?.created_at ? new Date(records[0].created_at).toLocaleString() : "";

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
        context="Analysis"
        title="Evaluation"
        description="Each method is tested on held-out compounds and compared with a baseline."
      />

      <Panel>
        <div className="flex flex-wrap items-end gap-x-6 gap-y-4 p-4">
          <fieldset className="flex flex-wrap gap-x-5 gap-y-2">
            <legend className="mb-1.5 text-[12.5px] font-medium text-ink-2">Split strategies</legend>
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
          <Field label="Folds" className="w-20">
            <TextInput type="number" min={2} max={20} value={folds} onChange={(e) => setFolds(e.target.value)} />
          </Field>
          <Field label="Seed" className="w-20">
            <TextInput type="number" value={seed} onChange={(e) => setSeed(e.target.value)} />
          </Field>
          <div className="flex items-center gap-3 sm:ml-auto">
            <span className="text-[12px] text-ink-3">About 15 s</span>
            <Button onClick={run} loading={runner.loading} disabled={strategies.length === 0}>
              Run benchmarks
            </Button>
          </div>
        </div>
      </Panel>

      <div className="mt-9 space-y-9">
        {runner.error && <ApiErrorNotice error={runner.error} />}
        {error ? (
          <ApiErrorNotice error={error} />
        ) : loading && !data ? (
          <LoadingState />
        ) : runRecords.length === 0 ? (
          <EmptyState title="No benchmark results yet">Run the benchmarks to measure every method on held-out compounds.</EmptyState>
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="min-w-[16rem] flex-1">
                <Tabs
                  value={activeStrategy}
                  onChange={setStrategy}
                  options={available.map((s) => ({ value: s.value, label: s.label, title: s.hint }))}
                />
              </div>
              {runs.length > 1 ? (
                <label className="flex items-center gap-2 text-[12.5px] text-ink-3">
                  Run
                  <Select value={runId ?? ""} onChange={(e) => setSelectedRun(e.target.value)} className="h-7 w-auto text-[12.5px]">
                    {runs.map(([id, records]) => (
                      <option key={id} value={id}>
                        {runDate(records)}
                      </option>
                    ))}
                  </Select>
                </label>
              ) : (
                <span className="text-[12.5px] text-ink-3">Run of {runDate(runRecords)}</span>
              )}
            </div>

            {activeStrategy === "target_group" && (
              <Notice>Compounds sharing a target are held out together: the realistic case for a new compound.</Notice>
            )}

            <Findings
              items={TASKS.map((task) => {
                const records = shown.filter((r) => r.parameters?.task === task.key);
                return records.length ? headline(task, records) : null;
              })}
            />

            {TASKS.map((task) => {
              const records = shown.filter((r) => r.parameters?.task === task.key);
              return records.length ? <TaskSection key={task.key} task={task} records={records} /> : null;
            })}
            <Audit audit={audit} strategy={activeStrategy} />
          </>
        )}
      </div>
    </>
  );
}
