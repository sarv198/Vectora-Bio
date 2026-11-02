"use client";

import { BarChart3 } from "lucide-react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable } from "@/components/DataTable";
import { ScoreChart } from "@/components/ScoreChart";
import { Card, EmptyState, LoadingState, Mono, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatCount, formatScore, humanize } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { EvaluationRecord } from "@/lib/types";

/** Most recent value per metric name. */
function latestPerMetric(results: EvaluationRecord[]): EvaluationRecord[] {
  const seen = new Map<string, EvaluationRecord>();
  for (const result of results) {
    if (!seen.has(result.metric_name)) seen.set(result.metric_name, result);
  }
  return [...seen.values()];
}

export default function EvaluationPage() {
  const { data, error, loading } = useApiQuery(() => api.listEvaluations(), []);
  const latest = data ? latestPerMetric(data.results) : [];
  const bounded = latest.filter((r) => r.metric_value >= 0 && r.metric_value <= 1);

  return (
    <>
      <PageHeader
        title="Evaluation"
        description="Metrics recorded by evaluation runs on imported data. Nothing is shown until an evaluation has been run."
        icon={<BarChart3 className="h-5 w-5" />}
      />
      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : data.results.length === 0 ? (
        <EmptyState title="No evaluation results">
          <p>{data.message}</p>
          <p className="mt-2">
            <Mono>python -m app.pipeline.evaluate_moa --cell-line U2OS --timepoint 48</Mono>
          </p>
        </EmptyState>
      ) : (
        <div className="space-y-4">
          {bounded.length > 0 && (
            <Card title="Latest value per metric (0–1 scale)">
              <ScoreChart valueLabel="Value" domain={[0, 1]} data={bounded.map((r) => ({ label: humanize(r.metric_name), value: r.metric_value }))} />
            </Card>
          )}
          <DataTable
            rows={data.results}
            rowKey={(row) => String(row.id)}
            columns={[
              { header: "Metric", cell: (row) => <span className="font-medium">{humanize(row.metric_name)}</span> },
              { header: "Value", cell: (row) => formatScore(row.metric_value), align: "right" },
              { header: "n", cell: (row) => formatCount(row.sample_count), align: "right" },
              { header: "Method", cell: (row) => <span className="text-xs text-ink-2">{row.evaluation_method}</span> },
              { header: "Split", cell: (row) => row.dataset_split },
              {
                header: "Recorded",
                cell: (row) => (row.created_at ? new Date(row.created_at).toLocaleString() : "—"),
              },
            ]}
          />
        </div>
      )}
    </>
  );
}
