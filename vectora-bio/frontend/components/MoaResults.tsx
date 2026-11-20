"use client";

import Link from "next/link";
import { Fragment, useState } from "react";

import { ComparisonPanel } from "@/components/PerturbationPanels";
import { Em, Findings, QuerySummary } from "@/components/QuerySummary";
import {
  DisclosureButton,
  EmptyState,
  InfoTip,
  Notice,
  RowExpander,
  Score,
  Section,
  TABLE,
  TD,
  TD_EXPANDER,
  TH,
  THEAD,
  TR,
  TableFrame,
  selectableRow,
} from "@/components/ui";
import { formatHours, formatScore, splitLabels } from "@/lib/format";
import { resultStamp, useResultChoice } from "@/lib/session";
import type { AnalysisResponse, MoaAnnotations, MoaCalibration, MoaNeighbor } from "@/lib/types";

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "n/a" : `${Math.round(value * 100)}%`;
}

const NEIGHBORS_SHOWN = 5;

const CONFIDENCE_HINT =
  "How often calls with this vote share were correct when known compounds were hidden and re-predicted (isotonic calibration). Low values are expected: many mechanisms in this dataset have a single compound.";

/** Candidate mechanisms with calibrated confidence, their supporting compounds, and the neighbourhood. */
export function MoaResults({ response }: { response: AnalysisResponse }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const queryMoa = splitLabels(response.query_annotations.moa);
  const calibration = (response.details.calibration ?? null) as MoaCalibration | null;
  const neighbors = (response.details.neighbors ?? []) as MoaNeighbor[];
  const nAnnotated = Number(response.details.n_annotated_neighbors ?? 0);
  const [selected, setSelected] = useResultChoice<string | null>(
    "moa.selected",
    resultStamp(response),
    neighbors[0]?.compound_id ?? null,
  );
  const top = response.predictions[0];
  const topInfo = top?.candidate_annotations as unknown as MoaAnnotations | undefined;
  const selectedNeighbor = neighbors.find((n) => n.compound_id === selected);
  const { summary } = response;
  // All neighbours vote on the mechanism; the table lists the closest five unless asked for more.
  const [showAllNeighbors, setShowAllNeighbors] = useState(false);
  const shownNeighbors = showAllNeighbors ? neighbors : neighbors.slice(0, NEIGHBORS_SHOWN);

  return (
    <div className="space-y-12">
      <QuerySummary
        label="Query compound"
        name={response.query_name ?? response.query_id}
        id={response.query_id}
        href={`/compounds/${encodeURIComponent(response.query_id)}`}
        facts={[
          {
            label: "Annotated mechanism",
            note: "Hidden from inference; shown only to check the call.",
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
                Most likely: <Em>{top.candidate_id}</Em>, confidence <Em>{percent(topInfo.confidence)}</Em> (
                {percent(topInfo.vote_share)} of the vote, {topInfo.n_supporting} of {topInfo.n_annotated_neighbors}{" "}
                annotated neighbours).
              </>,
              topInfo.matches_query_annotation === true ? (
                <>Matches the hidden annotation.</>
              ) : topInfo.matches_query_annotation === false ? (
                <>Differs from the annotation ({queryMoa.join(", ")}).</>
              ) : null,
              calibration ? (
                <>
                  Top calls are right for <Em>{percent(calibration.top1_accuracy)}</Em> of {calibration.n_compounds}{" "}
                  annotated compounds: treat them as leads.
                </>
              ) : null,
            ]}
          />

          <Section title="Candidate mechanisms">
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
                            <span className="subline mt-0.5 block">
                              mean cosine {formatScore(info.mean_similarity, 2)}
                            </span>
                          </td>
                          <td className={TD_EXPANDER}>
                            <RowExpander open={open} onToggle={toggle} label={`Compounds voting for ${prediction.candidate_id}`} />
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
                                {info.label_frequency} other compound{info.label_frequency === 1 ? "" : "s"} carry this
                                label.
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
          description={`The ${Math.min(NEIGHBORS_SHOWN, neighbors.length)} closest of the ${neighbors.length} that vote. Select a row to compare cells.`}
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
                {shownNeighbors.map((neighbor) => (
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
          {neighbors.length > NEIGHBORS_SHOWN && (
            <div className="mt-3">
              <DisclosureButton open={showAllNeighbors} onToggle={() => setShowAllNeighbors((v) => !v)}>
                {showAllNeighbors ? `Show the closest ${NEIGHBORS_SHOWN}` : `Show all ${neighbors.length} voting neighbours`}
              </DisclosureButton>
            </div>
          )}
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
