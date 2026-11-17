"use client";

import Link from "next/link";

import { LoadingState, ScoreBar, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { formatScore, splitLabels, topPercent } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { SimilarityAnnotations } from "@/lib/types";

const TOP_K = 6;

/** The few nearest compounds for one compound context, with a link to the full search. */
export function SimilarCompoundsPanel({
  compoundId,
  cellLine,
  timepoint,
}: {
  compoundId: string;
  cellLine: string;
  timepoint: number;
}) {
  const { data, error, loading } = useApiQuery(
    () => api.similarCompounds({ compound_id: compoundId, cell_line: cellLine, timepoint, top_k: TOP_K }),
    [compoundId, cellLine, timepoint],
  );
  const fullSearch = `/similarity?compound=${encodeURIComponent(compoundId)}`;

  return (
    <Section
      title="Most similar compounds"
      actions={
        <Link href={fullSearch} className="text-accent hover:underline">
          Full search
        </Link>
      }
    >
      {loading ? (
        <LoadingState />
      ) : error ? (
        <p className="text-[13px] text-ink-3">{error.message}</p>
      ) : data && data.predictions.length > 0 ? (
        <ul className="divide-y divide-line border-y border-line">
          {data.predictions.map((prediction) => {
            const info = prediction.candidate_annotations as unknown as SimilarityAnnotations;
            const moa = splitLabels(info.moa);
            return (
              <li key={prediction.candidate_id} className="py-2">
                <div className="flex items-baseline justify-between gap-3">
                  <Link
                    href={`/compounds/${encodeURIComponent(prediction.candidate_id)}`}
                    className="truncate text-[13.5px] font-medium text-ink hover:text-accent hover:underline"
                  >
                    {prediction.candidate_name ?? prediction.candidate_id}
                  </Link>
                  <span className="tabular shrink-0 text-[13px] text-ink">{formatScore(prediction.score, 2)}</span>
                </div>
                <div className="mt-1 flex items-center justify-between gap-3">
                  <p className="truncate text-[12px] text-ink-3">{moa.length ? moa.join(", ") : "Mechanism not annotated"}</p>
                  <span className="flex shrink-0 items-center gap-2 text-[11.5px] text-ink-3">
                    {topPercent(info.score_percentile)}
                    <ScoreBar value={prediction.score} width={48} />
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-[13px] text-ink-3">No other compounds in this context.</p>
      )}
    </Section>
  );
}
