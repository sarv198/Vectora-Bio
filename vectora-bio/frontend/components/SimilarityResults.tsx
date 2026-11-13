"use client";

import { Check, Info } from "lucide-react";
import Link from "next/link";

import { ScoreChart } from "@/components/ScoreChart";
import { Badge, Card, EmptyState } from "@/components/ui";
import { formatCount, formatHours, formatScore, splitLabels, topPercent } from "@/lib/format";
import type { AnalysisResponse, CompoundQueryAnnotations, SimilarityAnnotations } from "@/lib/types";

const MAX_TARGETS_SHOWN = 2;

function MoaLabels({ moa, shared }: { moa: string | null; shared: string[] }) {
  const labels = splitLabels(moa);
  if (labels.length === 0) return <span className="text-ink-3">Unknown</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {labels.map((label) =>
        shared.includes(label) ? (
          <Badge key={label} tone="accent">
            <Check className="h-3 w-3" aria-hidden />
            {label}
          </Badge>
        ) : (
          <Badge key={label}>{label}</Badge>
        ),
      )}
    </div>
  );
}

function Targets({ value }: { value: string | null }) {
  const targets = splitLabels(value);
  if (targets.length === 0) return <span className="text-ink-3">—</span>;
  const shown = targets.slice(0, MAX_TARGETS_SHOWN).join(", ");
  const extra = targets.length - MAX_TARGETS_SHOWN;
  return (
    <span title={targets.join(", ")}>
      {shown}
      {extra > 0 && <span className="text-ink-3"> +{extra}</span>}
    </span>
  );
}

/** Compound | Similarity | Known MoA table with the query's own annotations for comparison. */
export function SimilarityResults({ response }: { response: AnalysisResponse }) {
  const query = response.query_annotations as unknown as CompoundQueryAnnotations;
  const { summary, predictions } = response;
  const nShared = predictions.filter(
    (p) => ((p.candidate_annotations as unknown as SimilarityAnnotations).shared_moa ?? []).length > 0,
  ).length;
  const nAnnotated = predictions.filter((p) => (p.candidate_annotations as unknown as SimilarityAnnotations).moa).length;

  return (
    <div className="space-y-4">
      <Card title="Query compound">
        <div className="grid gap-4 text-sm sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <div className="min-w-0">
            <p className="truncate text-base font-semibold">{response.query_name ?? response.query_id}</p>
            <Link
              href={`/compounds/${encodeURIComponent(response.query_id)}`}
              className="font-mono text-xs text-accent hover:underline"
            >
              {response.query_id}
            </Link>
          </div>
          <div className="min-w-0">
            <p className="text-xs text-ink-3">Known MoA</p>
            <MoaLabels moa={query.moa} shared={[]} />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-ink-3">Known targets</p>
            <Targets value={query.known_target} />
          </div>
        </div>
        <p className="tabular mt-3 text-xs text-ink-3">
          {formatCount(summary.n_candidates)} candidates · {formatCount(summary.n_features)} features ·{" "}
          {summary.cell_line ?? "multiple cell lines"} · {formatHours(summary.timepoint)}
          {query.replicate_cosine !== null && ` · replicate agreement ${formatScore(query.replicate_cosine, 2)}`}
          {response.run_id ? ` · run #${response.run_id}` : ""}
        </p>
      </Card>

      {response.message && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {response.message}
        </p>
      )}

      {predictions.length === 0 ? (
        <EmptyState title="No similar compounds">No candidates remain after the filters.</EmptyState>
      ) : (
        <>
          <Card title="Cosine similarity">
            <ScoreChart
              valueLabel="Cosine similarity"
              data={predictions.map((p) => ({ label: p.candidate_name ?? p.candidate_id, value: p.score }))}
            />
          </Card>

          <Card
            title="Nearest compounds"
            actions={
              <span className="text-xs text-ink-3">
                {nAnnotated} of {predictions.length} annotated
                {query.moa ? ` · ${nShared} share the query's MoA` : ""}
              </span>
            }
          >
            <div className="-mx-4 -my-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-xs text-ink-3">
                  <tr>
                    <th className="w-8 px-3 py-2 font-medium">#</th>
                    <th className="px-3 py-2 font-medium">Compound</th>
                    <th className="px-3 py-2 text-right font-medium">Similarity</th>
                    <th
                      className="px-3 py-2 text-right font-medium"
                      title="How this score ranks among all compound pairs in the same cell line and timepoint"
                    >
                      vs. all pairs
                    </th>
                    <th className="px-3 py-2 font-medium">Known MoA · targets</th>
                    <th
                      className="px-3 py-2 text-right font-medium"
                      title="Mean cosine between this compound's replicate wells"
                    >
                      Replicate agr.
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((prediction) => {
                    const info = prediction.candidate_annotations as unknown as SimilarityAnnotations;
                    return (
                      <tr key={prediction.candidate_id} className="border-b border-line align-top last:border-0">
                        <td className="tabular px-3 py-2 text-ink-3">{prediction.rank}</td>
                        <td className="max-w-48 px-3 py-2">
                          <Link
                            href={`/compounds/${encodeURIComponent(prediction.candidate_id)}`}
                            className="block truncate font-medium text-accent hover:underline"
                          >
                            {prediction.candidate_name ?? prediction.candidate_id}
                          </Link>
                          {prediction.candidate_name && (
                            <span className="block truncate font-mono text-[11px] text-ink-3">
                              {prediction.candidate_id}
                            </span>
                          )}
                        </td>
                        <td className="tabular px-3 py-2 text-right font-medium">
                          {formatScore(prediction.score, 2)}
                        </td>
                        <td className="tabular px-3 py-2 text-right whitespace-nowrap text-ink-2">
                          {topPercent(info.score_percentile)}
                        </td>
                        <td className="px-3 py-2">
                          <MoaLabels moa={info.moa} shared={info.shared_moa ?? []} />
                          <p className="mt-1 text-xs text-ink-3">
                            <Targets value={info.known_target} />
                          </p>
                        </td>
                        <td className="tabular px-3 py-2 text-right text-ink-2">
                          {info.replicate_cosine === null ? "—" : formatScore(info.replicate_cosine, 2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
          <p className="text-xs text-ink-3">
            Phenotypic similarity suggests, but does not establish, a shared mechanism. Highlighted MoA labels are
            shared with the query.
          </p>
        </>
      )}
    </div>
  );
}
