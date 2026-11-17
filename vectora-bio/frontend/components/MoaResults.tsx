"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { Fragment, useEffect, useState } from "react";

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
  TR,
  TableFrame,
  selectableRow,
} from "@/components/ui";
import { formatHours, formatScore, splitLabels } from "@/lib/format";
import type { AnalysisResponse, MoaAnnotations, MoaCalibration, MoaNeighbor } from "@/lib/types";

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "n/a" : `${Math.round(value * 100)}%`;
}

const CONFIDENCE_HINT =
  "How often calls with this vote share were correct when known compounds were hidden and re-predicted (isotonic calibration). Low values are expected: many mechanisms in this dataset have a single compound.";

/** Candidate mechanisms with calibrated confidence, their supporting compounds, and the neighbourhood. */
export function MoaResults({ response }: { response: AnalysisResponse }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const queryMoa = splitLabels(response.query_annotations.moa);
  const calibration = (response.details.calibration ?? null) as MoaCalibration | null;
  const neighbors = (response.details.neighbors ?? []) as MoaNeighbor[];
  const nAnnotated = Number(response.details.n_annotated_neighbors ?? 0);
  const [selected, setSelected] = useState<string | null>(neighbors[0]?.compound_id ?? null);
  useEffect(() => setSelected(neighbors[0]?.compound_id ?? null), [response]);
  const top = response.predictions[0];
  const topInfo = top?.candidate_annotations as unknown as MoaAnnotations | undefined;
  const selectedNeighbor = neighbors.find((n) => n.compound_id === selected);
  const { summary } = response;

  return (
    <div className="space-y-9">
      <QuerySummary
        label="Query compound"
        name={response.query_name ?? response.query_id}
        id={response.query_id}
        href={`/compounds/${encodeURIComponent(response.query_id)}`}
        facts={[
          {
            label: "Annotated mechanism (hidden from inference)",
            value: queryMoa.length ? queryMoa.join(", ") : <span className="text-ink-3">None: this is a true prediction</span>,
          },
          { label: "Annotated neighbours", value: <span className="tabular">{`${nAnnotated} of ${neighbors.length}`}</span> },
          { label: "Context", value: `${summary.cell_line ?? "Several cell lines"} · ${formatHours(summary.timepoint)}` },
        ]}
      />

      {response.message && <Notice>{response.message}</Notice>}

      {response.predictions.length === 0 || !top || !topInfo ? (
        <EmptyState title="No mechanism candidates">None of the nearest compounds carries a mechanism annotation.</EmptyState>
      ) : (
        <>
          <Findings
            items={[
              <>
                Most likely mechanism is <Em>{top.candidate_id}</Em>, with calibrated confidence{" "}
                <Em>{percent(topInfo.confidence)}</Em> ({percent(topInfo.vote_share)} of the vote, from{" "}
                {topInfo.n_supporting} of {topInfo.n_annotated_neighbors} annotated neighbours).
              </>,
              topInfo.matches_query_annotation === true ? (
                <>This matches the compound&apos;s hidden annotation.</>
              ) : topInfo.matches_query_annotation === false ? (
                <>This differs from the compound&apos;s annotation ({queryMoa.join(", ")}).</>
              ) : null,
              calibration ? (
                <>
                  For reference, the top call recovers the hidden mechanism for {percent(calibration.top1_accuracy)} of{" "}
                  {calibration.n_compounds} annotated compounds, so treat calls as leads to test, not conclusions.
                </>
              ) : null,
            ]}
          />

          <Section title="Candidate mechanisms" description="Expand a mechanism to see the compounds that voted for it.">
            <TableFrame>
              <table className={TABLE}>
                <thead className={THEAD}>
                  <tr>
                    <th className={`${TH} w-8`}>#</th>
                    <th className={TH}>Mechanism</th>
                    <th className={`${TH} text-right`}>
                      <span className="inline-flex items-center gap-1">
                        Confidence
                        <InfoTip side="bottom">{CONFIDENCE_HINT}</InfoTip>
                      </span>
                    </th>
                    <th className={`${TH} text-right`}>
                      <span className="inline-flex items-center gap-1">
                        Vote share
                        <InfoTip side="bottom">This label&apos;s share of the similarity-weighted vote of annotated neighbours.</InfoTip>
                      </span>
                    </th>
                    <th className={TH}>Support</th>
                    <th className={`${TH} w-8`}>
                      <span className="sr-only">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {response.predictions.map((prediction) => {
                    const info = prediction.candidate_annotations as unknown as MoaAnnotations;
                    const open = expanded === prediction.candidate_id;
                    const toggle = () => setExpanded(open ? null : prediction.candidate_id);
                    return (
                      <Fragment key={prediction.candidate_id}>
                        <tr {...selectableRow(open, toggle)} aria-expanded={open}>
                          <td className={`${TD} tabular text-ink-3`}>{prediction.rank}</td>
                          <td className={TD}>
                            <span className="font-medium text-ink">{prediction.candidate_id}</span>
                            {info.matches_query_annotation === true && (
                              <span className="block text-[12px] text-ok">Matches the hidden annotation</span>
                            )}
                            {info.matches_query_annotation === false && prediction.rank === 1 && (
                              <span className="block text-[12px] text-ink-3">Differs from the annotation</span>
                            )}
                          </td>
                          <td className={`${TD} text-right`}>
                            <Score value={info.confidence} text={percent(info.confidence)} />
                          </td>
                          <td className={`${TD} text-right`}>
                            <Score value={info.vote_share} text={percent(info.vote_share)} tone="muted" />
                          </td>
                          <td className={`${TD} text-ink-2`}>
                            {info.n_supporting} of {info.n_annotated_neighbors} neighbours
                            <span className="block text-[12px] text-ink-3">
                              mean cosine {formatScore(info.mean_similarity, 2)}
                            </span>
                          </td>
                          <td className={TD}>
                            <ChevronRight
                              className={`h-4 w-4 text-ink-3 transition-transform ${open ? "rotate-90" : ""}`}
                              aria-hidden
                            />
                          </td>
                        </tr>
                        {open && (
                          <tr className={`${TR} bg-surface-2`}>
                            <td />
                            <td colSpan={5} className="py-3 pr-3">
                              <p className="mb-1.5 text-[12px] font-medium text-ink-2">Supporting compounds</p>
                              <ul className="max-w-md space-y-1 text-[12.5px]">
                                {info.supporting_compounds.map((compound) => (
                                  <li key={compound.compound_id} className="flex justify-between gap-3">
                                    <Link
                                      href={`/compounds/${encodeURIComponent(compound.compound_id)}`}
                                      className="truncate text-ink-2 hover:text-accent hover:underline"
                                    >
                                      {compound.compound_name ?? compound.compound_id}
                                    </Link>
                                    <span className="tabular text-ink-3">cosine {formatScore(compound.similarity, 2)}</span>
                                  </li>
                                ))}
                              </ul>
                              <p className="mt-2 text-[12px] text-ink-3">
                                {info.label_frequency} other compound{info.label_frequency === 1 ? "" : "s"} in the
                                reference set carry this label.
                              </p>
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
        </>
      )}

      {neighbors.length > 0 && (
        <Section
          title="Nearest compounds"
          description="The evidence behind the vote. Select a row to compare its cells with the query."
        >
          <TableFrame>
            <table className={TABLE}>
              <thead className={THEAD}>
                <tr>
                  <th className={TH}>Compound</th>
                  <th className={`${TH} text-right`}>Cosine similarity</th>
                  <th className={TH}>Known mechanism</th>
                </tr>
              </thead>
              <tbody>
                {neighbors.map((neighbor) => (
                  <tr
                    key={neighbor.compound_id}
                    {...selectableRow(selected === neighbor.compound_id, () => setSelected(neighbor.compound_id))}
                  >
                    <td className={TD}>
                      <Link
                        href={`/compounds/${encodeURIComponent(neighbor.compound_id)}`}
                        onClick={(event) => event.stopPropagation()}
                        className="font-medium text-ink hover:text-accent hover:underline"
                      >
                        {neighbor.compound_name ?? neighbor.compound_id}
                      </Link>
                    </td>
                    <td className={`${TD} text-right`}>
                      <Score value={neighbor.similarity} text={formatScore(neighbor.similarity, 2)} />
                    </td>
                    <td className={`${TD} text-ink-2`}>
                      {neighbor.moa ? splitLabels(neighbor.moa).join(", ") : <span className="text-ink-3">Not annotated</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableFrame>
        </Section>
      )}

      {selected && (
        <ComparisonPanel
          first={{ type: "compound", id: response.query_id }}
          second={{ type: "compound", id: selected }}
          firstRole="Query"
          secondRole={
            selectedNeighbor?.moa ? `Neighbour annotated ${splitLabels(selectedNeighbor.moa).join(", ")}` : "Unannotated neighbour"
          }
        />
      )}
    </div>
  );
}
