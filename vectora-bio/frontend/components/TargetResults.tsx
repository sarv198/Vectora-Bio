"use client";

import { AlertTriangle, ChevronDown, ChevronRight, Info } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { QueryCompoundCard } from "@/components/QueryCompoundCard";
import { ScoreChart } from "@/components/ScoreChart";
import { Badge, Card, EmptyState } from "@/components/ui";
import type { ApiError } from "@/lib/api";
import { formatScore, formatSigned, splitLabels, topPercent } from "@/lib/format";
import type { AnalysisResponse, CompoundRef, MatchAnnotations, TargetAnnotations } from "@/lib/types";

type Tab = "prioritized" | "matches";

function CompoundList({ title, items, empty }: { title: string; items: CompoundRef[]; empty: string }) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-ink-2">{title}</p>
      {items.length === 0 ? (
        <p className="text-xs text-ink-3">{empty}</p>
      ) : (
        <ul className="space-y-0.5 text-xs">
          {items.map((item) => (
            <li key={item.compound_id} className="flex justify-between gap-2">
              <Link
                href={`/compounds/${encodeURIComponent(item.compound_id)}`}
                className="truncate text-accent hover:underline"
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

function PrioritizedTable({ response }: { response: AnalysisResponse }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const weight = Number(response.parameters.neighbor_weight ?? 0);

  return (
    <div className="space-y-4">
      <Card title="Priority score">
        <ScoreChart
          valueLabel="Priority"
          domain={[0, 1]}
          data={response.predictions.map((p) => ({ label: p.candidate_id, value: p.score }))}
        />
      </Card>
      <Card title="Candidate target genes">
        <div className="-mx-4 -my-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-ink-3">
              <tr>
                <th className="w-8 px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Gene</th>
                <th className="px-3 py-2 text-right font-medium">Priority</th>
                <th className="px-3 py-2 font-medium">Evidence</th>
                <th className="w-8 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {response.predictions.map((prediction) => {
                const info = prediction.candidate_annotations as unknown as TargetAnnotations;
                const open = expanded === prediction.candidate_id;
                const best = info.reagents[0];
                return (
                  <Fragment key={prediction.candidate_id}>
                    <tr className="border-b border-line align-top">
                      <td className="tabular px-3 py-2 text-ink-3">{prediction.rank}</td>
                      <td className="px-3 py-2">
                        <Link
                          href={`/genes/${encodeURIComponent(prediction.candidate_id)}`}
                          className="font-medium text-accent hover:underline"
                        >
                          {prediction.candidate_id}
                        </Link>
                        {info.annotated_target_of_query && (
                          <div className="mt-1">
                            <Badge tone="ok">Known target of query</Badge>
                          </div>
                        )}
                      </td>
                      <td className="tabular px-3 py-2 text-right font-medium">{formatScore(prediction.score, 2)}</td>
                      <td className="px-3 py-2 text-xs text-ink-2">
                        <p>
                          <span className="text-ink-3">Phenotype:</span> {topPercent(info.phenotypic_score * 100)} ·{" "}
                          {best?.perturbation_type?.toUpperCase()} {formatSigned(best?.cosine, 2)} ·{" "}
                          {info.n_strong_reagents}/{info.n_reagents} reagents strong
                        </p>
                        <p>
                          <span className="text-ink-3">Similar compounds hitting it:</span>{" "}
                          {info.supporting_compounds.length === 0
                            ? "none"
                            : `${Math.round(info.neighbor_support * 100)}% · ${info.supporting_compounds
                                .slice(0, 2)
                                .map((c) => c.compound_name ?? c.compound_id)
                                .join(", ")}${info.supporting_compounds.length > 2 ? "…" : ""}`}
                        </p>
                      </td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => setExpanded(open ? null : prediction.candidate_id)}
                          aria-expanded={open}
                          aria-label={`Details for ${prediction.candidate_id}`}
                          className="text-ink-3 hover:text-ink"
                        >
                          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                      </td>
                    </tr>
                    {open && (
                      <tr className="border-b border-line bg-surface-2/40">
                        <td />
                        <td colSpan={4} className="px-3 py-3">
                          <div className="grid gap-4 sm:grid-cols-3">
                            <div className="min-w-0">
                              <p className="mb-1 text-xs font-medium text-ink-2">Genetic reagents</p>
                              <ul className="space-y-0.5 text-xs">
                                {info.reagents.map((reagent) => (
                                  <li key={reagent.perturbation_id} className="flex justify-between gap-2">
                                    <span className="truncate font-mono text-ink-2" title={reagent.perturbation_id}>
                                      {reagent.perturbation_type?.toUpperCase()} {reagent.perturbation_id}
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
                          <p className="mt-2 text-[11px] text-ink-3">
                            Priority = (phenotype percentile + {weight} × similar-compound share) / {1 + weight}. Compound
                            similarities are to the query.
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
    </div>
  );
}

function MatchTable({ response }: { response: AnalysisResponse }) {
  return (
    <Card title="Genetic perturbations resembling the compound">
      <div className="-mx-4 -my-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs text-ink-3">
            <tr>
              <th className="w-8 px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">Gene</th>
              <th className="px-3 py-2 font-medium">Reagent</th>
              <th className="px-3 py-2 text-right font-medium">Cosine</th>
              <th className="px-3 py-2 text-right font-medium">vs. all pairs</th>
            </tr>
          </thead>
          <tbody>
            {response.predictions.map((prediction) => {
              const info = prediction.candidate_annotations as unknown as MatchAnnotations;
              return (
                <tr key={prediction.candidate_id} className="border-b border-line last:border-0">
                  <td className="tabular px-3 py-2 text-ink-3">{prediction.rank}</td>
                  <td className="px-3 py-2">
                    {info.gene_symbol ? (
                      <Link
                        href={`/genes/${encodeURIComponent(info.gene_id ?? info.gene_symbol)}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {info.gene_symbol}
                      </Link>
                    ) : (
                      <span className="text-ink-3">unknown</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Badge>{info.perturbation_type?.toUpperCase() ?? "?"}</Badge>{" "}
                    <span className="font-mono text-xs text-ink-3">{prediction.candidate_id}</span>
                  </td>
                  <td className="tabular px-3 py-2 text-right">{formatSigned(info.cosine, 2)}</td>
                  <td className="tabular px-3 py-2 text-right text-ink-2">{topPercent(info.percentile)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Target prioritization and compound-to-gene matching, kept distinct as two views. */
export function TargetResults({
  prioritized,
  matches,
  matchesError,
}: {
  prioritized: AnalysisResponse;
  matches: AnalysisResponse | null;
  matchesError: ApiError | null;
}) {
  const [tab, setTab] = useState<Tab>("prioritized");
  const knownTargets = splitLabels(prioritized.query_annotations.known_target);
  const ranked = (prioritized.details.query_targets_in_ranking ?? []) as { gene: string; rank: number }[];
  const nGenes = Number(prioritized.details.n_genes ?? 0);

  return (
    <div className="space-y-4">
      <QueryCompoundCard response={prioritized}>
        <div>
          <p className="text-xs text-ink-3">Annotated targets (hidden from the score)</p>
          {knownTargets.length === 0 ? (
            <p className="text-ink-3">None</p>
          ) : (
            <p className="text-ink-2">
              {ranked.length > 0
                ? ranked.map((item) => `${item.gene} ranked #${item.rank} of ${nGenes}`).join(" · ")
                : `${knownTargets.slice(0, 4).join(", ")} (no genetic reagents for these)`}
            </p>
          )}
        </div>
      </QueryCompoundCard>

      <p className="flex items-start gap-2 rounded-lg border border-warn-line bg-warn-soft px-3 py-2 text-xs text-ink-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
        These are candidate associations. A gene whose perturbation resembles a compound&apos;s effect may act
        upstream, downstream or in parallel to the compound&apos;s real target.
      </p>
      {prioritized.message && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {prioritized.message}
        </p>
      )}

      <div role="tablist" className="flex gap-1 border-b border-line">
        {(
          [
            ["prioritized", "Prioritized genes", "Combined evidence per gene"],
            ["matches", "Genetic matches", "Raw reagent similarity"],
          ] as const
        ).map(([value, label, hint]) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === value ? "border-accent font-medium text-ink" : "border-transparent text-ink-3 hover:text-ink"
            }`}
            title={hint}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "prioritized" ? (
        prioritized.predictions.length ? (
          <PrioritizedTable response={prioritized} />
        ) : (
          <EmptyState title="No candidate genes" />
        )
      ) : matchesError ? (
        <ApiErrorNotice error={matchesError} />
      ) : matches ? (
        <MatchTable response={matches} />
      ) : (
        <EmptyState title="Matches not loaded" />
      )}
    </div>
  );
}
