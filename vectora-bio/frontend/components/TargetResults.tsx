"use client";

import Link from "next/link";
import { Fragment, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { ComparisonPanel } from "@/components/PerturbationPanels";
import { Em, Findings, QuerySummary } from "@/components/QuerySummary";
import {
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
  Tabs,
  selectableRow,
} from "@/components/ui";
import type { ApiError } from "@/lib/api";
import { formatHours, formatScore, formatSigned, splitLabels, topPercent } from "@/lib/format";
import { resultStamp, useResultChoice } from "@/lib/session";
import type { AnalysisResponse, CompoundRef, MatchAnnotations, TargetAnnotations } from "@/lib/types";

type Tab = "prioritized" | "matches";

const TYPE_LABEL: Record<string, string> = { crispr: "CRISPR", orf: "ORF", sirna: "siRNA" };
const typeLabel = (value: string | null | undefined) => (value ? (TYPE_LABEL[value] ?? value.toUpperCase()) : "Reagent");

function CompoundList({ title, items, empty }: { title: string; items: CompoundRef[]; empty: string }) {
  return (
    <div className="min-w-0">
      <p className="mb-1.5 flex justify-between gap-3 text-[12px] font-medium text-ink-2">
        {title}
        {items.length > 0 && <span className="font-normal text-ink-3">cosine</span>}
      </p>
      {items.length === 0 ? (
        <p className="text-[12.5px] text-ink-3">{empty}</p>
      ) : (
        <ul className="space-y-1 text-[12.5px]">
          {items.map((item) => (
            <li key={item.compound_id} className="flex justify-between gap-3">
              <Link
                href={`/compounds/${encodeURIComponent(item.compound_id)}`}
                className="truncate text-ink-2 hover:text-accent hover:underline"
              >
                {item.compound_name ?? item.compound_id}
              </Link>
              <span className="tabular shrink-0 text-ink-3">{formatScore(item.similarity, 2)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PrioritizedTable({
  response,
  selected,
  onSelect,
}: {
  response: AnalysisResponse;
  selected: string | null;
  onSelect: (reagentId: string) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const weight = Number(response.parameters.neighbor_weight ?? 0);

  return (
    <TableFrame>
      <table className={TABLE}>
        <thead className={THEAD}>
          <tr>
            <th className={`${TH} w-8`}>#</th>
            <th className={TH}>Gene</th>
            <th className={`${TH} text-right`}>
              <span className="inline-flex items-center gap-1">
                Priority
                <InfoTip side="bottom">
                  (phenotype percentile + {weight} x similar-compound share) / {1 + weight}. 1 is the strongest
                  possible evidence.
                </InfoTip>
              </span>
            </th>
            <th className={TH}>Phenotype match</th>
            <th className={TH}>Similar compounds acting on it</th>
            <th className={`${TH} w-8`}>
              <span className="sr-only">Details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {response.predictions.map((prediction) => {
            const info = prediction.candidate_annotations as unknown as TargetAnnotations;
            const best = info.reagents[0];
            const open = expanded === prediction.candidate_id;
            const isSelected = best !== undefined && selected === best.perturbation_id;
            return (
              <Fragment key={prediction.candidate_id}>
                <tr {...selectableRow(isSelected, () => best && onSelect(best.perturbation_id))}>
                  <td className={`${TD} tabular text-ink-3`}>{prediction.rank}</td>
                  <td className={TD}>
                    <Link
                      href={`/genes/${encodeURIComponent(prediction.candidate_id)}`}
                      onClick={(event) => event.stopPropagation()}
                      className="font-medium text-ink hover:text-accent hover:underline"
                    >
                      {prediction.candidate_id}
                    </Link>
                    {info.annotated_target_of_query && (
                      <span className="block text-[12px] text-accent">Annotated target of query</span>
                    )}
                  </td>
                  <td className={`${TD} text-right`}>
                    <Score value={prediction.score} text={formatScore(prediction.score, 2)} />
                  </td>
                  <td className={`${TD} text-ink-2`}>
                    <span className="tabular">{topPercent(info.phenotypic_score * 100)}</span>
                    <span className="subline mt-0.5 block">
                      {typeLabel(best?.perturbation_type)} cosine {formatSigned(best?.cosine, 2)} · {info.n_strong_reagents} of{" "}
                      {info.n_reagents} reagents strong
                    </span>
                  </td>
                  <td className={`${TD} text-ink-2`}>
                    {info.supporting_compounds.length === 0 ? (
                      <span className="text-ink-3">None</span>
                    ) : (
                      <>
                        <span className="tabular">{Math.round(info.neighbor_support * 100)}%</span>
                        <span className="subline mt-0.5 block max-w-[16rem] truncate">
                          {info.supporting_compounds.map((c) => c.compound_name ?? c.compound_id).join(", ")}
                        </span>
                      </>
                    )}
                  </td>
                  <td className={TD_EXPANDER}>
                    <RowExpander
                      open={open}
                      onToggle={() => setExpanded(open ? null : prediction.candidate_id)}
                      label={`Evidence for ${prediction.candidate_id}`}
                    />
                  </td>
                </tr>
                {open && (
                  <tr className={`${TR} bg-surface-2`}>
                    <td />
                    <td colSpan={5} className="py-4 pr-3">
                      <div className="grid gap-6 sm:grid-cols-3">
                        <div className="min-w-0">
                          <p className="mb-1.5 text-[12px] font-medium text-ink-2">Genetic reagents</p>
                          <ul className="space-y-1 text-[12.5px]">
                            {info.reagents.map((reagent) => (
                              <li key={reagent.perturbation_id} className="flex justify-between gap-3">
                                <span className="truncate text-ink-2" title={reagent.perturbation_id}>
                                  {typeLabel(reagent.perturbation_type)}{" "}
                                  <span className="font-mono text-[11.5px] text-ink-3">{reagent.perturbation_id}</span>
                                </span>
                                <span className="tabular shrink-0 text-ink-3">
                                  {formatSigned(reagent.cosine, 2)} · {topPercent(reagent.percentile)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <CompoundList
                          title={`Similar compounds annotated to ${prediction.candidate_id}`}
                          items={info.supporting_compounds}
                          empty="None among the nearest compounds."
                        />
                        <CompoundList
                          title={`All compounds annotated to ${prediction.candidate_id} (${info.n_known_compounds})`}
                          items={info.known_compounds}
                          empty="No imported compound lists this gene as a target."
                        />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </TableFrame>
  );
}

function MatchTable({
  response,
  selected,
  onSelect,
}: {
  response: AnalysisResponse;
  selected: string | null;
  onSelect: (reagentId: string) => void;
}) {
  return (
    <TableFrame>
      <table className={TABLE}>
        <thead className={THEAD}>
          <tr>
            <th className={`${TH} w-8`}>#</th>
            <th className={TH}>Gene</th>
            <th className={TH}>Reagent</th>
            <th className={`${TH} text-right`}>Cosine</th>
            <th className={`${TH} text-right`}>Percentile</th>
          </tr>
        </thead>
        <tbody>
          {response.predictions.map((prediction) => {
            const info = prediction.candidate_annotations as unknown as MatchAnnotations;
            return (
              <tr
                key={prediction.candidate_id}
                {...selectableRow(selected === prediction.candidate_id, () => onSelect(prediction.candidate_id))}
              >
                <td className={`${TD} tabular text-ink-3`}>{prediction.rank}</td>
                <td className={TD}>
                  {info.gene_symbol ? (
                    <Link
                      href={`/genes/${encodeURIComponent(info.gene_id ?? info.gene_symbol)}`}
                      onClick={(event) => event.stopPropagation()}
                      className="font-medium text-ink hover:text-accent hover:underline"
                    >
                      {info.gene_symbol}
                    </Link>
                  ) : (
                    <span className="text-ink-3">Unknown</span>
                  )}
                </td>
                <td className={`${TD} text-ink-2`}>
                  {typeLabel(info.perturbation_type)}{" "}
                  <span className="font-mono text-[11.5px] text-ink-3">{prediction.candidate_id}</span>
                </td>
                <td className={`${TD} text-right`}>
                  <Score value={info.cosine} text={formatSigned(info.cosine, 2)} signed />
                </td>
                <td className={`${TD} tabular text-right text-ink-2`}>{topPercent(info.percentile)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </TableFrame>
  );
}

/** Drug-to-gene matching: prioritised genes and raw reagent matches, with compound vs. reagent images. */
export function TargetResults({
  prioritized,
  matches,
  matchesError,
}: {
  prioritized: AnalysisResponse;
  matches: AnalysisResponse | null;
  matchesError: ApiError | null;
}) {
  const stamp = resultStamp(prioritized);
  const [tab, setTab] = useResultChoice<Tab>("targets.tab", stamp, "prioritized");
  const knownTargets = splitLabels(prioritized.query_annotations.known_target);
  const ranked = (prioritized.details.query_targets_in_ranking ?? []) as { gene: string; rank: number }[];
  const nGenes = Number(prioritized.details.n_genes ?? 0);
  const weight = Number(prioritized.parameters.neighbor_weight ?? 0);
  const firstReagent = () =>
    (prioritized.predictions[0]?.candidate_annotations as unknown as TargetAnnotations | undefined)?.reagents[0]
      ?.perturbation_id ?? null;
  const [selected, setSelected] = useResultChoice<string | null>("targets.selected", stamp, firstReagent());

  const top = prioritized.predictions[0];
  const topInfo = top?.candidate_annotations as unknown as TargetAnnotations | undefined;
  const selectedGene = (() => {
    for (const p of prioritized.predictions) {
      const info = p.candidate_annotations as unknown as TargetAnnotations;
      if (info.reagents.some((r) => r.perturbation_id === selected)) return p.candidate_id;
    }
    const match = matches?.predictions.find((p) => p.candidate_id === selected);
    return (match?.candidate_annotations as unknown as MatchAnnotations | undefined)?.gene_symbol ?? selected;
  })();
  const { summary } = prioritized;

  return (
    <div className="space-y-12">
      <QuerySummary
        label="Query compound"
        name={prioritized.query_name ?? prioritized.query_id}
        id={prioritized.query_id}
        href={`/compounds/${encodeURIComponent(prioritized.query_id)}`}
        facts={[
          {
            label: "Annotated targets",
            note: "Never used in scoring; shown only to check where they rank.",
            value: knownTargets.length ? knownTargets.slice(0, 6).join(", ") : <span className="text-ink-3">None</span>,
          },
          { label: "Genes scored", value: <span className="tabular">{nGenes}</span> },
          { label: "Context", value: `${summary.cell_line ?? "Several cell lines"} · ${formatHours(summary.timepoint)}` },
        ]}
      />

      {prioritized.message && <Notice>{prioritized.message}</Notice>}

      {top && topInfo && (
        <Findings
          items={[
            <>
              Top candidate: <Em>{top.candidate_id}</Em>, priority <Em>{formatScore(top.score, 2)}</Em> (
              {typeLabel(topInfo.reagents[0]?.perturbation_type)} cosine {formatSigned(topInfo.reagents[0]?.cosine, 2)},{" "}
              {topPercent(topInfo.phenotypic_score * 100).toLowerCase()}).
            </>,
            knownTargets.length === 0 ? (
              <>No annotated targets to check against.</>
            ) : ranked.length ? (
              <>
                Annotated target{ranked.length > 1 ? "s" : ""}{" "}
                {ranked.map((item, index) => (
                  <span key={item.gene}>
                    <Em>{item.gene}</Em> ranks #{item.rank}
                    {index < ranked.length - 1 ? ", " : ""}
                  </span>
                ))}{" "}
                of {nGenes} genes.
              </>
            ) : (
              <>No annotated target ({knownTargets.slice(0, 3).join(", ")}) has a genetic reagent here.</>
            ),
            weight > 0 ? (
              <>
                Includes similar-compound evidence (weight {weight}). Set 0 in Parameters for novel chemistry.
              </>
            ) : (
              <>Phenotype match only.</>
            ),
          ]}
        />
      )}

      <Section title="Candidate genes" description="Select a row to compare cells.">
        <div className="space-y-4">
          <Tabs
            value={tab}
            onChange={setTab}
            options={[
              { value: "prioritized", label: "Prioritised genes", title: "Combined evidence per gene" },
              { value: "matches", label: "Reagent matches", title: "Raw similarity of every reagent" },
            ]}
          />
          {tab === "prioritized" ? (
            prioritized.predictions.length ? (
              <PrioritizedTable response={prioritized} selected={selected} onSelect={setSelected} />
            ) : (
              <EmptyState title="No candidate genes" />
            )
          ) : matchesError ? (
            <ApiErrorNotice error={matchesError} />
          ) : matches ? (
            <MatchTable response={matches} selected={selected} onSelect={setSelected} />
          ) : (
            <EmptyState title="Reagent matches not loaded" />
          )}
        </div>
      </Section>

      {selected && (
        <ComparisonPanel
          first={{ type: "compound", id: prioritized.query_id }}
          second={{ type: "genetic", id: selected }}
          firstRole="Compound"
          secondRole={`Genetic perturbation of ${selectedGene ?? ""}`}
        />
      )}
    </div>
  );
}
