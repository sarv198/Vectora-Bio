"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { ComparisonPanel, strengthText } from "@/components/PerturbationPanels";
import { FeatureChangeList } from "@/components/PhenotypeMaps";
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
  selectableRow,
} from "@/components/ui";
import { formatCount, formatHours, formatScore, splitLabels } from "@/lib/format";
import { resultStamp, useResultChoice } from "@/lib/session";
import type { AnalysisResponse, FeatureContribution, RescueAnnotations } from "@/lib/types";

const FLAG_LABELS: Record<string, { label: string; hint: string }> = {
  cell_loss: {
    label: "Cell loss",
    hint: "Cell-density features drop more than in 99% of control pseudo-replicates: possible toxicity or arrested growth.",
  },
  generic_response: {
    label: "Generic response",
    hint: "Among the 10% of compounds most aligned with a response many compounds share, often stress.",
  },
};

const TYPE_LABEL: Record<string, string> = { crispr: "CRISPR knockout", orf: "ORF overexpression", sirna: "siRNA knockdown" };

function Direction({ value }: { value: number }) {
  return value >= 0 ? (
    <ArrowUp className="inline h-3 w-3" aria-label="increased" />
  ) : (
    <ArrowDown className="inline h-3 w-3" aria-label="decreased" />
  );
}

function ContributionList({ items, title }: { items: FeatureContribution[]; title: string }) {
  if (items.length === 0) return null;
  return (
    <div className="min-w-0">
      <p className="mb-1.5 text-[12px] font-medium text-ink-2">{title}</p>
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="text-left text-[11.5px] text-ink-3">
            <th className="pb-1 font-normal">Feature</th>
            <th className="pb-1 text-center font-normal" title="Direction in the gene perturbation">
              Gene
            </th>
            <th className="pb-1 text-center font-normal" title="Direction in the compound">
              Cpd
            </th>
            <th className="pb-1 text-right font-normal" title="Contribution to the reversal score, x100">
              Share
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.feature} title={item.feature}>
              <td className="max-w-0 truncate py-0.5 pr-3 text-ink-2">{item.label}</td>
              <td className="w-10 py-0.5 text-center text-ink-3">
                <Direction value={item.signature} />
              </td>
              <td className="w-10 py-0.5 text-center text-ink-3">
                <Direction value={item.compound ?? 0} />
              </td>
              <td className="tabular w-14 py-0.5 text-right text-ink">
                {item.value >= 0 ? "+" : ""}
                {(item.value * 100).toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GroupBars({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values)
    .filter(([, v]) => v !== 0)
    .slice(0, 6);
  const max = Math.max(...entries.map(([, v]) => Math.abs(v)), 1e-9);
  return (
    <div className="min-w-0">
      <p className="mb-1.5 text-[12px] font-medium text-ink-2">{title}</p>
      <ul className="space-y-1.5 text-[12.5px]">
        {entries.map(([name, value]) => (
          <li key={name} className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-3">
            <span className="truncate text-ink-2">{name}</span>
            <span className="h-1 bg-surface-3">
              <span
                className="block h-full"
                style={{
                  width: `${(Math.abs(value) / max) * 100}%`,
                  background: value >= 0 ? "var(--sage)" : "var(--div-neg-2)",
                }}
              />
            </span>
            <span className="tabular text-right text-ink-3">{(value * 100).toFixed(0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Flags({ flags }: { flags: string[] }) {
  if (flags.length === 0) return <span className="text-ink-3">None</span>;
  return (
    <span className="flex flex-col gap-0.5">
      {flags.map((flag) => (
        <span key={flag} className="inline-flex items-center gap-1 text-warn">
          {FLAG_LABELS[flag]?.label ?? flag}
          {FLAG_LABELS[flag] && <InfoTip>{FLAG_LABELS[flag].hint}</InfoTip>}
        </span>
      ))}
    </span>
  );
}

/** Rescue candidates with quality flags, per-feature explanations, and perturbation vs. compound images. */
export function RescueResults({ response }: { response: AnalysisResponse }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const query = response.query_annotations as Record<string, string | number | null>;
  const signatureTop = (response.details.signature_top_features ?? []) as FeatureContribution[];
  const excluded = (response.details.excluded ?? {}) as Record<string, number>;
  const [selected, setSelected] = useResultChoice<string | null>(
    "rescue.selected",
    resultStamp(response),
    response.predictions[0]?.candidate_id ?? null,
  );

  const top = response.predictions[0];
  const topInfo = top?.candidate_annotations as unknown as RescueAnnotations | undefined;
  const flagged = response.predictions.filter(
    (p) => (p.candidate_annotations as unknown as RescueAnnotations).stress_flags.length > 0,
  );
  const perturbationType = String(query.perturbation_type ?? "");
  const isGenetic = ["crispr", "orf", "sirna"].includes(perturbationType);
  const selectedPrediction = response.predictions.find((p) => p.candidate_id === selected);

  return (
    <div className="space-y-12">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <QuerySummary
          label="Genetic perturbation"
          name={response.query_name ?? response.query_id}
          id={response.query_id}
          facts={[
            { label: "Reagent", value: TYPE_LABEL[perturbationType] ?? (perturbationType || "Custom signature") },
            {
              label: "Context",
              value: `${String(query.cell_line ?? "")} · ${formatHours(Number(query.timepoint ?? NaN))}`,
            },
            {
              label: "Compounds ranked",
              value: (
                <span className="tabular">
                  {formatCount(response.summary.n_candidates)}
                  {excluded.weak_response ? ` (${excluded.weak_response} weak excluded)` : ""}
                </span>
              ),
            },
          ]}
        />
        {signatureTop.length > 0 && (
          <div>
            <p className="eyebrow mb-1">Largest changes vs. controls</p>
            <FeatureChangeList
              unit="MAD"
              features={signatureTop.slice(0, 5).map((f) => ({ feature: f.feature, label: f.label, value: f.value }))}
            />
          </div>
        )}
      </div>

      {response.message && <Notice>{response.message}</Notice>}

      {response.predictions.length === 0 || !top || !topInfo ? (
        <EmptyState title="No rescue candidates">No compound passes the filters. Relax them in Parameters and run again.</EmptyState>
      ) : (
        <>
          <Findings
            items={[
              <>
                Strongest reversal: <Em>{top.candidate_name ?? top.candidate_id}</Em>, score{" "}
                <Em>{formatScore(top.score, 2)}</Em>
                {topInfo.stress_flags.length ? ", with a stress flag." : ", no stress flags."}
              </>,
              <>
                <Em>
                  {flagged.length} of {response.predictions.length}
                </Em>{" "}
                flagged for cell loss or a generic response
                {excluded.stress_like ? `; ${excluded.stress_like} stress-like excluded.` : "."}
              </>,
            ]}
          />

          <Section title="Rescue candidates" description="Select a row to compare cells.">
            <TableFrame>
              <table className={TABLE}>
                <thead className={THEAD}>
                  <tr>
                    <th className={`${TH} w-8`}>#</th>
                    <th className={TH}>Compound</th>
                    <th className={`${TH} text-right`}>
                      <span className="inline-flex items-center gap-1">
                        Reversal
                        <InfoTip side="bottom">Minus the cosine between the compound and the gene signature: 1 is exact opposition.</InfoTip>
                      </span>
                    </th>
                    <th className={`${TH} text-right`}>
                      <span className="inline-flex items-center gap-1">
                        Strength
                        <InfoTip side="bottom">Share of DMSO pseudo-replicates weaker than this compound&apos;s profile.</InfoTip>
                      </span>
                    </th>
                    <th className={`${TH} text-right`}>Replicates</th>
                    <th className={TH}>Flags</th>
                    <th className={`${TH} w-8`}>
                      <span className="sr-only">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {response.predictions.map((prediction) => {
                    const info = prediction.candidate_annotations as unknown as RescueAnnotations;
                    const open = expanded === prediction.candidate_id;
                    const moa = splitLabels(info.moa);
                    return (
                      <Fragment key={prediction.candidate_id}>
                        <tr {...selectableRow(selected === prediction.candidate_id, () => setSelected(prediction.candidate_id))}>
                          <td className={`${TD} tabular text-ink-3`}>{prediction.rank}</td>
                          <td className={`${TD} max-w-[16rem]`}>
                            <Link
                              href={`/compounds/${encodeURIComponent(prediction.candidate_id)}`}
                              onClick={(event) => event.stopPropagation()}
                              className="block truncate font-medium text-ink hover:text-accent hover:underline"
                            >
                              {prediction.candidate_name ?? prediction.candidate_id}
                            </Link>
                            <span className="subline mt-0.5 block truncate">
                              {moa.length ? moa.join(", ") : "Mechanism not annotated"}
                            </span>
                          </td>
                          <td className={`${TD} text-right`}>
                            <Score value={prediction.score} text={formatScore(prediction.score, 2)} />
                          </td>
                          <td className={`${TD} tabular text-right text-ink-2`}>
                            {strengthText(info.response_percentile)}
                          </td>
                          <td className={`${TD} tabular text-right text-ink-2`}>{formatScore(info.replicate_cosine, 2)}</td>
                          <td className={`${TD} text-[12.5px]`}>
                            <Flags flags={info.stress_flags} />
                          </td>
                          <td className={TD_EXPANDER}>
                            <RowExpander
                              open={open}
                              onToggle={() => setExpanded(open ? null : prediction.candidate_id)}
                              label={`Explain the score for ${prediction.candidate_name ?? prediction.candidate_id}`}
                            />
                          </td>
                        </tr>
                        {open && (
                          <tr className={`${TR} bg-surface-2`}>
                            <td />
                            <td colSpan={6} className="space-y-5 py-4 pr-3">
                              <div className="grid gap-6 lg:grid-cols-2">
                                <ContributionList title="Features driving the reversal" items={info.reversing_features} />
                                <ContributionList title="Features working against it" items={info.opposing_features} />
                              </div>
                              <div className="grid gap-6 sm:grid-cols-2">
                                <GroupBars title="Contribution by measurement" values={info.by_measurement} />
                                <GroupBars title="Contribution by stain" values={info.by_channel} />
                              </div>
                              <p className="text-[12px] text-ink-3">Contributions sum to the reversal score.</p>
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

          {selected && isGenetic && (
            <ComparisonPanel
              first={{ type: "genetic", id: response.query_id }}
              second={{ type: "compound", id: selected }}
              firstRole="Genetic perturbation"
              secondRole={`Candidate #${selectedPrediction?.rank ?? ""}`}
              mode="reversal"
            />
          )}
        </>
      )}
    </div>
  );
}
