"use client";

import { ArrowLeft, FlaskConical } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable } from "@/components/DataTable";
import { SimilarCompoundsPanel } from "@/components/SimilarCompoundsPanel";
import { Card, LoadingState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

export default function CompoundDetailPage() {
  const { compoundId } = useParams<{ compoundId: string }>();
  const id = decodeURIComponent(compoundId);
  const { data, error, loading } = useApiQuery(() => api.getCompound(id), [id]);

  return (
    <>
      <Link href="/compounds" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> Compounds
      </Link>
      <PageHeader title={data?.compound_name ?? id} description={<span className="font-mono">{id}</span>} icon={<FlaskConical className="h-5 w-5" />} />
      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : (
        <div className="space-y-4">
          <Card title="Annotations">
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-3">Mechanism of action</dt>
                <dd>{data.moa ?? "Not annotated"}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-3">Known target</dt>
                <dd>{data.known_target ?? "Not annotated"}</dd>
              </div>
            </dl>
          </Card>
          {data.contexts.length > 0 && (
            <SimilarCompoundsPanel
              compoundId={data.compound_id}
              cellLine={data.contexts[0].cell_line}
              timepoint={data.contexts[0].timepoint}
            />
          )}
          <div className="flex flex-wrap gap-2 text-sm">
            {[
              [`/similarity?compound=${encodeURIComponent(data.compound_id)}`, "Find similar compounds"],
              [`/targets?compound=${encodeURIComponent(data.compound_id)}`, "Prioritize targets"],
              [`/moa?compound=${encodeURIComponent(data.compound_id)}`, "Infer MoA"],
            ].map(([href, label]) => (
              <Link key={href} href={href} className="rounded-md border border-line bg-surface px-3 py-1.5 hover:bg-surface-2">
                {label}
              </Link>
            ))}
          </div>
          <h2 className="pt-2 text-sm font-semibold">Imported contexts</h2>
          <DataTable
            rows={data.contexts}
            rowKey={(row) => `${row.cell_line}-${row.timepoint}`}
            columns={[
              { header: "Cell line", cell: (row) => row.cell_line },
              { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
              { header: "Replicates", cell: (row) => row.replicate_count, align: "right" },
            ]}
          />
        </div>
      )}
    </>
  );
}
