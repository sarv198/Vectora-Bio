"use client";

import { AlertTriangle, ArrowDown, ArrowUp, ChevronDown, ChevronRight, Info } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { ScoreChart } from "@/components/ScoreChart";
import { Badge, Card, EmptyState } from "@/components/ui";
import { formatCount, formatHours, formatScore, splitLabels } from "@/lib/format";
import type { AnalysisResponse, FeatureContribution, RescueAnnotations } from "@/lib/types";

const FLAG_LABELS: Record<string, { label: string; hint: string }> = {
  cell_loss: {
    label: "Cell loss",
    hint: "Cell-density features drop more than in 99% of control pseudo-replicates: possible toxicity or arrested growth.",
  },
  generic_response: {
    label: "Generic response",
    hint: "Among the 10% of compounds most aligned with the response many compounds share, often stress.",
  },
};

function Direction({ value }: { value: number }) {
  return value >= 0 ? (
    <ArrowUp className="inline h-3 w-3 text-ink-2" aria-label="increased" />
  ) : (
    <ArrowDown className="inline h-3 w-3 text-ink-2" aria-label="decreased" />
  );
}

function FeatureList({ items, title }: { items: FeatureContribution[]; title: string }) {
  if (items.length === 0) return null;
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-ink-2">{title}</p>
      <ul className="space-y-1 text-xs">
        {items.map((item) => (
          <li key={item.feature} className="flex items-baseline justify-between gap-3" title={item.feature}>
            <span className="min-w-0 truncate text-ink-2">{item.label}</span>
            <span className="tabular shrink-0 text-ink-3">
              KO/OE <Direction value={item.signature} /> · cpd <Direction value={item.compound ?? 0} /> ·{" "}
              {item.value >= 0 ? "+" : ""}
              {(item.value * 100).toFixed(1)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GroupBars({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values).filter(([, v]) => v !== 0).slice(0, 6);
  const max = Math.max(...entries.map(([, v]) => Math.abs(v)), 1e-9);
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-ink-2">{title}</p>
      <ul className="space-y-1 text-xs">
        {entries.map(([name, value]) => (
          <li key={name} className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-2">
            <span className="truncate text-ink-2">{name}</span>
            <span className="h-1.5 rounded-full bg-surface-2">
              <span
                className={`block h-full rounded-full ${value >= 0 ? "bg-[var(--series-1)]" : "bg-[var(--ink-3)]"}`}
                style={{ width: `${(Math.abs(value) / max) * 100}%` }}
              />
            </span>
            <span className="tabular text-right text-ink-3">{(value * 100).toFixed(0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Rescue candidates with quality flags and per-feature explanations of each reversal score. */
export function RescueResults({ response }: { response: AnalysisResponse }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const query = response.query_annotations as Record<string, string | number | null>;
  const signatureTop = (response.details.signature_top_features ?? []) as FeatureContribution[];
  const excluded = (response.details.excluded ?? {}) as Record<string, number>;

  return (
    <div className="space-y-4">
      <Card title="Perturbation signature">
        <div className="grid gap-4 text-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div className="min-w-0">
            <p className="text-base font-semibold">{response.query_name ?? response.query_id}</p>
            <p className="text-xs text-ink-3">
              {String(query.perturbation_type ?? "custom").toUpperCase()} ·{" "}
              <span className="font-mono">{response.query_id}</span>
            </p>
            <p className="mt-1 text-xs text-ink-3">
              {String(query.cell_line ?? "")} · {formatHours(Number(query.timepoint ?? NaN))} · minus matched controls
            </p>
          </div>
          <div className="min-w-0">
            <p className="mb-1 text-xs text-ink-3">Largest changes vs. controls</p>
            <ul className="space-y-0.5 text-xs">
              {signatureTop.slice(0, 5).map((feature) => (
                <li key={feature.feature} className="flex justify-between gap-2" title={feature.feature}>
                  <span className="truncate text-ink-2">{feature.label}</span>
                  <span className="tabular shrink-0 text-ink-3">
                    <Direction value={feature.value} /> {formatScore(Math.abs(feature.value), 1)} MAD
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="tabular mt-3 text-xs text-ink-3">
          {formatCount(response.summary.n_candidates)} compounds ranked · {formatCount(response.summary.n_features)}{" "}
          features
          {excluded.weak_response ? ` · ${excluded.weak_response} weak responses excluded` : ""}
          {excluded.stress_like ? ` · ${excluded.stress_like} stress-like excluded` : ""}
        </p>
      </Card>

      <p className="flex items-start gap-2 rounded-lg border border-warn-line bg-warn-soft px-3 py-2 text-xs text-ink-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
        Computational reversal candidates, not proven rescue: an opposing profile can come from a different mechanism,
        and must be tested experimentally.
      </p>
      {response.message && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {response.message}
        </p>
      )}

      {response.predictions.length === 0 ? (
        <EmptyState title="No candidates">No compound passes the filters.</EmptyState>
      ) : (
        <>
          <Card title="Reversal score">
            <ScoreChart
              valueLabel="Reversal score"
              domain={[0, 1]}
              data={response.predictions.map((p) => ({ label: p.candidate_name ?? p.candidate_id, value: p.score }))}
            />
          </Card>
          <Card title="Rescue candidates">
            <div className="-mx-4 -my-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-xs text-ink-3">
                  <tr>
                    <th className="w-8 px-3 py-2 font-medium">#</th>
                    <th className="px-3 py-2 font-medium">Compound</th>
                    <th className="px-3 py-2 text-right font-medium">Reversal</th>
                    <th
                      className="px-3 py-2 text-right font-medium"
                      title="Response strength vs. control pseudo-replicates, and agreement between replicate wells"
                    >
                      Strength · replicates
                    </th>
                    <th className="px-3 py-2 font-medium">Flags</th>
                    <th className="w-8 px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {response.predictions.map((prediction) => {
                    const info = prediction.candidate_annotations as unknown as RescueAnnotations;
                    const open = expanded === prediction.candidate_id;
                    const moa = splitLabels(info.moa);
                    return (
                      <Fragment key={prediction.candidate_id}>
                        <tr className="border-b border-line align-top">
                          <td className="tabular px-3 py-2 text-ink-3">{prediction.rank}</td>
                          <td className="max-w-52 px-3 py-2">
                            <Link
                              href={`/compounds/${encodeURIComponent(prediction.candidate_id)}`}
                              className="block truncate font-medium text-accent hover:underline"
                            >
                              {prediction.candidate_name ?? prediction.candidate_id}
                            </Link>
                            <span className="block truncate text-xs text-ink-3">
                              {moa.length ? moa.join(", ") : "MoA unknown"}
                            </span>
                          </td>
                          <td className="tabular px-3 py-2 text-right font-medium">{formatScore(prediction.score, 2)}</td>
                          <td className="tabular px-3 py-2 text-right text-xs text-ink-2">
                            {info.response_percentile === null ? "—" : `>${Math.floor(info.response_percentile * 100)}%`}
                            <span className="text-ink-3"> · {formatScore(info.replicate_cosine, 2)}</span>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap gap-1">
                              {info.stress_flags.map((flag) => (
                                <span key={flag} title={FLAG_LABELS[flag]?.hint}>
                                  <Badge tone="warn">
                                    <AlertTriangle className="h-3 w-3" aria-hidden />
                                    {FLAG_LABELS[flag]?.label ?? flag}
                                  </Badge>
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <button
                              type="button"
                              onClick={() => setExpanded(open ? null : prediction.candidate_id)}
                              aria-expanded={open}
                              aria-label={`Explain score for ${prediction.candidate_name ?? prediction.candidate_id}`}
                              className="text-ink-3 hover:text-ink"
                            >
                              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            </button>
                          </td>
                        </tr>
                        {open && (
                          <tr className="border-b border-line bg-surface-2/40">
                            <td />
                            <td colSpan={5} className="space-y-3 px-3 py-3">
                              <FeatureList
                                title="Features driving the reversal (perturbation vs. compound direction, share of score ×100)"
                                items={info.reversing_features}
                              />
                              <FeatureList title="Features working against it" items={info.opposing_features} />
                              <div className="grid gap-4 sm:grid-cols-2">
                                <GroupBars title="Contribution by measurement" values={info.by_measurement} />
                                <GroupBars title="Contribution by stain channel" values={info.by_channel} />
                              </div>
                              <p className="text-[11px] text-ink-3">
                                Feature contributions sum exactly to the reversal score.
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
        </>
      )}
    </div>
  );
}
