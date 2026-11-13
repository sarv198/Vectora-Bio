"use client";

import { Check, ChevronDown, ChevronRight, Info, X } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { QueryCompoundCard } from "@/components/QueryCompoundCard";
import { Badge, Card, EmptyState } from "@/components/ui";
import { formatScore, splitLabels } from "@/lib/format";
import type { AnalysisResponse, MoaAnnotations, MoaCalibration, MoaNeighbor } from "@/lib/types";

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

/** MoA candidates with calibrated confidence, the compounds behind each, and the full neighbourhood. */
export function MoaResults({ response }: { response: AnalysisResponse }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const queryMoa = splitLabels(response.query_annotations.moa);
  const calibration = (response.details.calibration ?? null) as MoaCalibration | null;
  const neighbors = (response.details.neighbors ?? []) as MoaNeighbor[];
  const nAnnotated = Number(response.details.n_annotated_neighbors ?? 0);

  return (
    <div className="space-y-4">
      <QueryCompoundCard response={response}>
        <div>
          <p className="text-xs text-ink-3">Annotated MoA</p>
          {queryMoa.length === 0 ? (
            <Badge tone="accent">Unannotated: this is a true prediction</Badge>
          ) : (
            <div className="flex flex-wrap items-center gap-1">
              {queryMoa.map((label) => (
                <Badge key={label}>{label}</Badge>
              ))}
              <span className="text-xs text-ink-3">hidden from inference, shown for comparison</span>
            </div>
          )}
        </div>
      </QueryCompoundCard>

      {response.message && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {response.message}
        </p>
      )}

      {response.predictions.length === 0 ? (
        <EmptyState title="No mechanism candidates">None of the nearest compounds carries a MoA annotation.</EmptyState>
      ) : (
        <Card
          title="Candidate mechanisms"
          actions={
            <span className="text-xs text-ink-3">
              {nAnnotated} of {neighbors.length} neighbours annotated
            </span>
          }
        >
          <div className="-mx-4 -my-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs text-ink-3">
                <tr>
                  <th className="w-8 px-3 py-2 font-medium">#</th>
                  <th className="px-3 py-2 font-medium">Mechanism</th>
                  <th className="px-3 py-2 text-right font-medium" title="Share of annotated neighbours' similarity">
                    Vote share
                  </th>
                  <th
                    className="px-3 py-2 text-right font-medium"
                    title="How often calls with this vote share were correct when known compounds were hidden"
                  >
                    Confidence
                  </th>
                  <th className="px-3 py-2 font-medium">Support</th>
                  <th className="w-8 px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {response.predictions.map((prediction) => {
                  const info = prediction.candidate_annotations as unknown as MoaAnnotations;
                  const open = expanded === prediction.candidate_id;
                  return (
                    <Fragment key={prediction.candidate_id}>
                      <tr className="border-b border-line align-top">
                        <td className="tabular px-3 py-2 text-ink-3">{prediction.rank}</td>
                        <td className="px-3 py-2">
                          <span className="font-medium">{prediction.candidate_id}</span>
                          {info.matches_query_annotation === true && (
                            <span className="ml-2 inline-flex">
                              <Badge tone="ok">
                                <Check className="h-3 w-3" aria-hidden />
                                matches annotation
                              </Badge>
                            </span>
                          )}
                          {info.matches_query_annotation === false && prediction.rank === 1 && (
                            <span className="ml-2 inline-flex">
                              <Badge>
                                <X className="h-3 w-3" aria-hidden />
                                differs from annotation
                              </Badge>
                            </span>
                          )}
                        </td>
                        <td className="tabular px-3 py-2 text-right">{percent(info.vote_share)}</td>
                        <td className="tabular px-3 py-2 text-right font-medium">{percent(info.confidence)}</td>
                        <td className="px-3 py-2 text-xs text-ink-2">
                          {info.n_supporting} of {info.n_annotated_neighbors} annotated neighbours
                          <span className="text-ink-3"> · mean sim. {formatScore(info.mean_similarity, 2)}</span>
                        </td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => setExpanded(open ? null : prediction.candidate_id)}
                            aria-expanded={open}
                            aria-label={`Supporting compounds for ${prediction.candidate_id}`}
                            className="text-ink-3 hover:text-ink"
                          >
                            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                          </button>
                        </td>
                      </tr>
                      {open && (
                        <tr className="border-b border-line bg-surface-2/40">
                          <td />
                          <td colSpan={5} className="px-3 py-3">
                            <p className="mb-1 text-xs font-medium text-ink-2">Supporting compounds</p>
                            <ul className="space-y-0.5 text-xs">
                              {info.supporting_compounds.map((compound) => (
                                <li key={compound.compound_id} className="flex justify-between gap-2">
                                  <Link
                                    href={`/compounds/${encodeURIComponent(compound.compound_id)}`}
                                    className="truncate text-accent hover:underline"
                                  >
                                    {compound.compound_name ?? compound.compound_id}
                                  </Link>
                                  <span className="tabular text-ink-3">cosine {formatScore(compound.similarity, 2)}</span>
                                </li>
                              ))}
                            </ul>
                            <p className="mt-2 text-[11px] text-ink-3">
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
          </div>
        </Card>
      )}

      {calibration && (
        <p className="text-xs text-ink-3">
          Confidence is calibrated by hiding each of {calibration.n_compounds} annotated compounds and checking the
          calls made for it (isotonic regression). Overall, the top call recovered the hidden MoA{" "}
          {percent(calibration.top1_accuracy)} of the time; many labels in this dataset belong to a single compound,
          so low confidence is expected.
        </p>
      )}

      {neighbors.length > 0 && (
        <Card title="Nearest compounds">
          <div className="-mx-4 -my-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs text-ink-3">
                <tr>
                  <th className="px-3 py-2 font-medium">Compound</th>
                  <th className="px-3 py-2 text-right font-medium">Similarity</th>
                  <th className="px-3 py-2 font-medium">Known MoA</th>
                </tr>
              </thead>
              <tbody>
                {neighbors.map((neighbor) => (
                  <tr key={neighbor.compound_id} className="border-b border-line last:border-0">
                    <td className="px-3 py-1.5">
                      <Link
                        href={`/compounds/${encodeURIComponent(neighbor.compound_id)}`}
                        className="text-accent hover:underline"
                      >
                        {neighbor.compound_name ?? neighbor.compound_id}
                      </Link>
                    </td>
                    <td className="tabular px-3 py-1.5 text-right">{formatScore(neighbor.similarity, 2)}</td>
                    <td className="px-3 py-1.5 text-xs text-ink-2">
                      {neighbor.moa ? splitLabels(neighbor.moa).join(", ") : <span className="text-ink-3">Unknown</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
