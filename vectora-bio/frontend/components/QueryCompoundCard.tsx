import Link from "next/link";
import type { ReactNode } from "react";

import { Card } from "@/components/ui";
import { formatCount, formatHours } from "@/lib/format";
import type { AnalysisResponse } from "@/lib/types";

/** Header card naming the query compound, with analysis-specific annotation fields beside it. */
export function QueryCompoundCard({ response, children }: { response: AnalysisResponse; children?: ReactNode }) {
  const { summary } = response;
  return (
    <Card title="Query compound">
      <div className="grid gap-4 text-sm sm:grid-cols-[minmax(0,1.2fr)_minmax(0,2fr)]">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold">{response.query_name ?? response.query_id}</p>
          <Link
            href={`/compounds/${encodeURIComponent(response.query_id)}`}
            className="font-mono text-xs text-accent hover:underline"
          >
            {response.query_id}
          </Link>
        </div>
        <div className="min-w-0 space-y-2">{children}</div>
      </div>
      <p className="tabular mt-3 text-xs text-ink-3">
        {formatCount(summary.n_candidates)} candidates · {formatCount(summary.n_features)} features ·{" "}
        {summary.cell_line ?? "multiple cell lines"} · {formatHours(summary.timepoint)}
        {response.run_id ? ` · run #${response.run_id}` : ""}
      </p>
    </Card>
  );
}
