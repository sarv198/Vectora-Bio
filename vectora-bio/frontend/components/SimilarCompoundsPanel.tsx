"use client";

import Link from "next/link";

import { Card, LoadingState } from "@/components/ui";
import { api } from "@/lib/api";
import { formatScore, splitLabels, topPercent } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { SimilarityAnnotations } from "@/lib/types";

const TOP_K = 5;

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
    <Card
      title="Most similar compounds"
      actions={
        <Link href={fullSearch} className="text-xs text-accent hover:underline">
          Full similarity search
        </Link>
      }
    >
      {loading ? (
        <LoadingState />
      ) : error ? (
        <p className="text-sm text-ink-3">{error.message}</p>
      ) : data && data.predictions.length > 0 ? (
        <ul className="divide-y divide-line text-sm">
          {data.predictions.map((prediction) => {
            const info = prediction.candidate_annotations as unknown as SimilarityAnnotations;
            const moa = splitLabels(info.moa);
            return (
              <li key={prediction.candidate_id} className="flex items-center justify-between gap-4 py-2">
                <div className="min-w-0">
                  <Link
                    href={`/compounds/${encodeURIComponent(prediction.candidate_id)}`}
                    className="block truncate font-medium text-accent hover:underline"
                  >
                    {prediction.candidate_name ?? prediction.candidate_id}
                  </Link>
                  <p className="truncate text-xs text-ink-3">{moa.length ? moa.join(", ") : "MoA unknown"}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="tabular font-medium">{formatScore(prediction.score, 2)}</p>
                  <p className="tabular text-xs text-ink-3">{topPercent(info.score_percentile)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-ink-3">No other compounds in this context.</p>
      )}
    </Card>
  );
}
