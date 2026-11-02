"use client";

import { ChevronDown, ChevronRight, Info } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { ScoreChart } from "@/components/ScoreChart";
import { Card, EmptyState } from "@/components/ui";
import { formatCount, formatHours, formatScore, formatSigned, humanize } from "@/lib/format";
import type { AnalysisResponse, Prediction } from "@/lib/types";

const CANDIDATE_LINKS: Partial<Record<Prediction["prediction_type"], (id: string) => string>> = {
  compound_similarity: (id) => `/compounds/${encodeURIComponent(id)}`,
  phenotypic_rescue: (id) => `/compounds/${encodeURIComponent(id)}`,
  target_prioritization: (id) => `/genes/${encodeURIComponent(id)}`,
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-ink-3">{label}</p>
      <p className="tabular text-sm font-medium">{value}</p>
    </div>
  );
}

export function PredictionResults({
  response,
  scoreLabel,
  candidateLabel = "Candidate",
}: {
  response: AnalysisResponse;
  scoreLabel: string;
  candidateLabel?: string;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const { summary, predictions } = response;
  const link = CANDIDATE_LINKS[response.prediction_type];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 rounded-xl border border-line bg-surface px-4 py-3 sm:grid-cols-5">
        <Stat label="Query" value={response.query_id} />
        <Stat label="Candidates scored" value={formatCount(summary.n_candidates)} />
        <Stat label="Features" value={formatCount(summary.n_features)} />
        <Stat label="Cell line" value={summary.cell_line ?? "multiple"} />
        <Stat label="Timepoint" value={summary.timepoint === null ? "multiple" : formatHours(summary.timepoint)} />
      </div>

      {response.message && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {response.message}
        </p>
      )}

      {predictions.length === 0 ? (
        <EmptyState title="No predictions">The analysis ran but produced no ranked candidates.</EmptyState>
      ) : (
        <>
          <Card title={scoreLabel}>
            <ScoreChart
              valueLabel={scoreLabel}
              data={predictions.map((p) => ({ label: p.candidate_id, value: p.score }))}
            />
          </Card>

          <Card title="Ranked predictions" actions={response.run_id ? <span className="text-xs text-ink-3">Run #{response.run_id}</span> : null}>
            <div className="-mx-4 -my-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-xs text-ink-3">
                  <tr>
                    <th className="w-10 px-4 py-2 font-medium">#</th>
                    <th className="px-4 py-2 font-medium">{candidateLabel}</th>
                    <th className="px-4 py-2 text-right font-medium">{scoreLabel}</th>
                    <th className="px-4 py-2 font-medium">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((prediction, index) => {
                    const open = expanded === index;
                    return (
                      <Fragment key={`${prediction.candidate_id}-${prediction.rank}`}>
                        <tr className="border-b border-line last:border-0 hover:bg-surface-2/60">
                          <td className="tabular px-4 py-2 text-ink-3">{prediction.rank}</td>
                          <td className="px-4 py-2 font-medium">
                            {link ? (
                              <Link href={link(prediction.candidate_id)} className="text-accent hover:underline">
                                {prediction.candidate_id}
                              </Link>
                            ) : (
                              prediction.candidate_id
                            )}
                          </td>
                          <td className="tabular px-4 py-2 text-right">{formatScore(prediction.score)}</td>
                          <td className="px-4 py-2">
                            <button
                              type="button"
                              onClick={() => setExpanded(open ? null : index)}
                              className="inline-flex items-center gap-1 text-xs text-ink-2 hover:text-ink"
                              aria-expanded={open}
                            >
                              {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                              {prediction.supporting_evidence.length} item
                              {prediction.supporting_evidence.length === 1 ? "" : "s"}
                            </button>
                          </td>
                        </tr>
                        {open && (
                          <tr className="border-b border-line bg-surface-2/40">
                            <td />
                            <td colSpan={3} className="px-4 py-3">
                              <ul className="space-y-1.5">
                                {prediction.supporting_evidence.map((evidence, i) => (
                                  <li key={i} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                                    <span className="rounded bg-surface px-1.5 py-0.5 font-medium text-ink-2">
                                      {humanize(evidence.evidence_type)}
                                    </span>
                                    <span className="text-ink-2">{evidence.description}</span>
                                    {evidence.value !== null && (
                                      <span className="tabular font-mono text-ink-3">{formatSigned(evidence.value)}</span>
                                    )}
                                  </li>
                                ))}
                              </ul>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
