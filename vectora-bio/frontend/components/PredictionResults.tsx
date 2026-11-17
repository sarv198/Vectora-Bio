"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { EmptyState, Metrics, Notice, Score, Section, TABLE, TD, TH, THEAD, TR, TableFrame } from "@/components/ui";
import { formatCount, formatHours, formatScore, formatSigned, humanize } from "@/lib/format";
import type { AnalysisResponse, Prediction } from "@/lib/types";

const CANDIDATE_LINKS: Partial<Record<Prediction["prediction_type"], (id: string) => string>> = {
  compound_similarity: (id) => `/compounds/${encodeURIComponent(id)}`,
  phenotypic_rescue: (id) => `/compounds/${encodeURIComponent(id)}`,
  target_prioritization: (id) => `/genes/${encodeURIComponent(id)}`,
};

/** Generic ranked view for analyses without a dedicated results layout. */
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
    <div className="space-y-8">
      <Metrics
        items={[
          { label: "Query", value: <span className="font-mono text-[14px]">{response.query_id}</span> },
          { label: "Candidates scored", value: formatCount(summary.n_candidates) },
          { label: "Features", value: formatCount(summary.n_features) },
          { label: "Context", value: `${summary.cell_line ?? "Several"} · ${formatHours(summary.timepoint)}` },
        ]}
      />
      {response.message && <Notice>{response.message}</Notice>}
      {predictions.length === 0 ? (
        <EmptyState title="No predictions">The analysis ran but produced no ranked candidates.</EmptyState>
      ) : (
        <Section title="Ranked predictions" actions={response.run_id ? `Run ${response.run_id}` : null}>
          <TableFrame>
            <table className={TABLE}>
              <thead className={THEAD}>
                <tr>
                  <th className={`${TH} w-8`}>#</th>
                  <th className={TH}>{candidateLabel}</th>
                  <th className={`${TH} text-right`}>{scoreLabel}</th>
                  <th className={TH}>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((prediction, index) => {
                  const open = expanded === index;
                  return (
                    <Fragment key={`${prediction.candidate_id}-${prediction.rank}`}>
                      <tr className={`${TR} hover:bg-surface-2`}>
                        <td className={`${TD} tabular text-ink-3`}>{prediction.rank}</td>
                        <td className={`${TD} font-medium`}>
                          {link ? (
                            <Link href={link(prediction.candidate_id)} className="text-ink hover:text-accent hover:underline">
                              {prediction.candidate_id}
                            </Link>
                          ) : (
                            prediction.candidate_id
                          )}
                        </td>
                        <td className={`${TD} text-right`}>
                          <Score value={prediction.score} text={formatScore(prediction.score, 2)} />
                        </td>
                        <td className={TD}>
                          <button
                            type="button"
                            onClick={() => setExpanded(open ? null : index)}
                            className="inline-flex items-center gap-1 text-[12.5px] text-ink-2 hover:text-ink"
                            aria-expanded={open}
                          >
                            <ChevronRight className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`} aria-hidden />
                            {prediction.supporting_evidence.length} item{prediction.supporting_evidence.length === 1 ? "" : "s"}
                          </button>
                        </td>
                      </tr>
                      {open && (
                        <tr className={`${TR} bg-surface-2`}>
                          <td />
                          <td colSpan={3} className="py-3 pr-3">
                            <ul className="space-y-1 text-[12.5px]">
                              {prediction.supporting_evidence.map((evidence, i) => (
                                <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                                  <span className="font-medium text-ink-2">{humanize(evidence.evidence_type)}</span>
                                  <span className="text-ink-2">{evidence.description}</span>
                                  {evidence.value !== null && <span className="tabular text-ink-3">{formatSigned(evidence.value)}</span>}
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
          </TableFrame>
        </Section>
      )}
    </div>
  );
}
