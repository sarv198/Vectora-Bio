"use client";

import { Check } from "lucide-react";
import Link from "next/link";

import { ComparisonPanel } from "@/components/PerturbationPanels";
import { Em, Findings, QuerySummary } from "@/components/QuerySummary";
import {
  EmptyState,
  InfoTip,
  Notice,
  Score,
  Section,
  TABLE,
  TD,
  TH,
  THEAD,
  TableFrame,
  selectableRow,
} from "@/components/ui";
import { formatCount, formatHours, formatScore, splitLabels, topPercent } from "@/lib/format";
import { resultStamp, useResultChoice } from "@/lib/session";
import type { AnalysisResponse, CompoundQueryAnnotations, SimilarityAnnotations } from "@/lib/types";

const MAX_TARGETS_SHOWN = 3;

function MechanismCell({ moa, shared }: { moa: string | null; shared: string[] }) {
  const labels = splitLabels(moa);
  if (labels.length === 0) return <span className="text-ink-3">Not annotated</span>;
  return (
    <span className="flex flex-wrap gap-x-1.5 gap-y-0.5">
      {labels.map((label, index) =>
        shared.includes(label) ? (
          <span key={label} className="inline-flex items-center gap-1 font-medium text-accent" title="Shared with the query">
            <Check className="h-3.5 w-3.5" aria-hidden />
            {label}
            {index < labels.length - 1 ? "," : ""}
          </span>
        ) : (
          <span key={label} className="text-ink-2">
            {label}
            {index < labels.length - 1 ? "," : ""}
          </span>
        ),
      )}
    </span>
  );
}

function targetsText(value: string | null): string {
  const targets = splitLabels(value);
  if (targets.length === 0) return "None annotated";
  const extra = targets.length - MAX_TARGETS_SHOWN;
  return `${targets.slice(0, MAX_TARGETS_SHOWN).join(", ")}${extra > 0 ? ` +${extra}` : ""}`;
}

/** Query, key findings, ranked neighbours with inline evidence, and a visual comparison of the selected hit. */
export function SimilarityResults({ response }: { response: AnalysisResponse }) {
  const query = response.query_annotations as unknown as CompoundQueryAnnotations;
  const { summary, predictions } = response;
  const [selected, setSelected] = useResultChoice<string | null>(
    "similarity.selected",
    resultStamp(response),
    predictions[0]?.candidate_id ?? null,
  );

  const info = (id: string) =>
    predictions.find((p) => p.candidate_id === id)?.candidate_annotations as unknown as SimilarityAnnotations;
  const top = predictions[0];
  const queryMoa = splitLabels(query.moa);
  const sharing = predictions.filter((p) => (info(p.candidate_id).shared_moa ?? []).length > 0);
  const sharedLabels = [...new Set(sharing.flatMap((p) => info(p.candidate_id).shared_moa ?? []))];
  const nAnnotated = predictions.filter((p) => info(p.candidate_id).moa).length;
  const nTop1 = predictions.filter((p) => (info(p.candidate_id).score_percentile ?? 0) >= 99).length;
  const selectedPrediction = predictions.find((p) => p.candidate_id === selected);

  return (
    <div className="space-y-9">
      <QuerySummary
        label="Query compound"
        name={response.query_name ?? response.query_id}
        id={response.query_id}
        href={`/compounds/${encodeURIComponent(response.query_id)}`}
        facts={[
          { label: "Known mechanism", value: queryMoa.length ? queryMoa.join(", ") : <span className="text-ink-3">Not annotated</span> },
          { label: "Known targets", value: targetsText(query.known_target) },
          { label: "Replicate agreement", value: <span className="tabular">{formatScore(query.replicate_cosine, 2)}</span> },
          {
            label: "Context",
            value: `${summary.cell_line ?? "Several cell lines"} · ${formatHours(summary.timepoint)} · ${formatCount(summary.n_candidates)} candidates`,
          },
        ]}
      />

      {response.message && <Notice>{response.message}</Notice>}

      {predictions.length === 0 || !top ? (
        <EmptyState title="No similar compounds">No candidates remain after the filters. Relax the parameters and run again.</EmptyState>
      ) : (
        <>
          <Findings
            items={[
              <>
                Nearest: <Em>{top.candidate_name ?? top.candidate_id}</Em>, cosine <Em>{formatScore(top.score, 2)}</Em>
                {info(top.candidate_id).score_percentile !== null
                  ? ` (${topPercent(info(top.candidate_id).score_percentile).toLowerCase()} of compound pairs).`
                  : "."}
              </>,
              queryMoa.length ? (
                <>
                  <Em>
                    {sharing.length} of {predictions.length}
                  </Em>{" "}
                  share the query&apos;s mechanism{sharedLabels.length ? ` (${sharedLabels.join(", ")})` : ""}.
                </>
              ) : (
                <>
                  Query mechanism unknown; {nAnnotated} of {predictions.length} neighbours are annotated.
                </>
              ),
              nTop1 > 0 ? (
                <>
                  <Em>{nTop1}</Em> in the top 1% of compound pairs.
                </>
              ) : (
                <>None in the top 1% of compound pairs: matches are weak.</>
              ),
            ]}
          />

          <Section title="Ranked neighbours" description="Select a row to compare cells.">
            <TableFrame>
              <table className={TABLE}>
                <thead className={THEAD}>
                  <tr>
                    <th className={`${TH} w-8`}>#</th>
                    <th className={TH}>Compound</th>
                    <th className={`${TH} text-right`}>Cosine similarity</th>
                    <th className={`${TH} text-right`}>
                      <span className="inline-flex items-center gap-1">
                        Percentile
                        <InfoTip side="bottom">
                          How this score ranks among all compound pairs in the same cell line and timepoint.
                        </InfoTip>
                      </span>
                    </th>
                    <th className={TH}>Known mechanism</th>
                    <th className={`${TH} hidden lg:table-cell`}>Known targets</th>
                    <th className={`${TH} text-right`}>
                      <span className="inline-flex items-center gap-1">
                        Replicates
                        <InfoTip side="bottom">Mean cosine between this compound&apos;s replicate wells: its reproducibility.</InfoTip>
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((prediction) => {
                    const annotations = info(prediction.candidate_id);
                    return (
                      <tr
                        key={prediction.candidate_id}
                        {...selectableRow(selected === prediction.candidate_id, () => setSelected(prediction.candidate_id))}
                      >
                        <td className={`${TD} tabular text-ink-3`}>{prediction.rank}</td>
                        <td className={`${TD} max-w-[15rem]`}>
                          <Link
                            href={`/compounds/${encodeURIComponent(prediction.candidate_id)}`}
                            onClick={(event) => event.stopPropagation()}
                            className="block truncate font-medium text-ink hover:text-accent hover:underline"
                          >
                            {prediction.candidate_name ?? prediction.candidate_id}
                          </Link>
                          {prediction.candidate_name && (
                            <span className="block truncate font-mono text-[11.5px] text-ink-3">{prediction.candidate_id}</span>
                          )}
                        </td>
                        <td className={`${TD} text-right`}>
                          <Score value={prediction.score} text={formatScore(prediction.score, 2)} />
                        </td>
                        <td className={`${TD} tabular text-right whitespace-nowrap text-ink-2`}>
                          {topPercent(annotations.score_percentile)}
                        </td>
                        <td className={`${TD} max-w-[18rem]`}>
                          <MechanismCell moa={annotations.moa} shared={annotations.shared_moa ?? []} />
                        </td>
                        <td className={`${TD} hidden max-w-[12rem] truncate text-ink-2 lg:table-cell`}>
                          {targetsText(annotations.known_target)}
                        </td>
                        <td className={`${TD} tabular text-right text-ink-2`}>{formatScore(annotations.replicate_cosine, 2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableFrame>
            <p className="mt-2 inline-flex items-center gap-1 text-[12px] text-ink-3">
              <Check className="h-3.5 w-3.5 text-accent" aria-hidden /> shared with the query
            </p>
          </Section>

          {selected && (
            <ComparisonPanel
              first={{ type: "compound", id: response.query_id }}
              second={{ type: "compound", id: selected }}
              firstRole="Query"
              secondRole={`Neighbour #${selectedPrediction?.rank ?? ""}`}
            />
          )}
        </>
      )}
    </div>
  );
}
