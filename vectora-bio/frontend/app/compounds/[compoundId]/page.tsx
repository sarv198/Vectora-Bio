"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable } from "@/components/DataTable";
import { PerturbationInspector } from "@/components/PerturbationPanels";
import { SimilarCompoundsPanel } from "@/components/SimilarCompoundsPanel";
import { LoadingState, PageHeader, Section } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours, splitLabels } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

export default function CompoundDetailPage() {
  const { compoundId } = useParams<{ compoundId: string }>();
  const id = decodeURIComponent(compoundId);
  const { data, error, loading } = useApiQuery(() => api.getCompound(id), [id]);
  const moa = splitLabels(data?.moa);
  const targets = splitLabels(data?.known_target);

  return (
    <>
      <Link href="/compounds" className="mb-4 inline-flex items-center gap-1 text-[12.5px] text-ink-3 hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Compounds
      </Link>
      <PageHeader
        title={data?.compound_name ?? id}
        description={<span className="font-mono text-[12.5px] text-ink-3">{id}</span>}
        actions={
          data && (
            <div className="flex flex-wrap gap-2">
              {[
                [`/similarity?compound=${encodeURIComponent(data.compound_id)}`, "Find similar"],
                [`/targets?compound=${encodeURIComponent(data.compound_id)}`, "Match genes"],
                [`/moa?compound=${encodeURIComponent(data.compound_id)}`, "Infer mechanism"],
              ].map(([href, label]) => (
                <Link
                  key={href}
                  href={href}
                  className="inline-flex h-8 items-center rounded-md border border-line-strong bg-surface px-3 text-[13px] font-medium text-ink hover:border-ink-3"
                >
                  {label}
                </Link>
              ))}
            </div>
          )
        }
      />
      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : (
        <div className="space-y-10">
          <dl className="grid gap-x-10 gap-y-3 border-y border-line py-3.5 text-[13.5px] sm:grid-cols-3">
            <div>
              <dt className="text-[12px] text-ink-3">Mechanism of action</dt>
              <dd className="text-ink">{moa.length ? moa.join(", ") : <span className="text-ink-3">Not annotated</span>}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-ink-3">Known targets</dt>
              <dd className="text-ink">{targets.length ? targets.join(", ") : <span className="text-ink-3">None annotated</span>}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-ink-3">Profiled in</dt>
              <dd className="text-ink">
                {data.contexts.length
                  ? data.contexts
                      .map((c) => `${c.cell_line}, ${formatHours(c.timepoint)}, ${c.replicate_count} replicates`)
                      .join("; ")
                  : "No profiles imported"}
              </dd>
            </div>
          </dl>

          {data.contexts.length > 0 && (
            <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_20rem]">
              <PerturbationInspector target={{ type: "compound", id: data.compound_id }} />
              <SimilarCompoundsPanel
                compoundId={data.compound_id}
                cellLine={data.contexts[0].cell_line}
                timepoint={data.contexts[0].timepoint}
              />
            </div>
          )}

          {data.contexts.length > 1 && (
            <Section title="Imported contexts">
              <DataTable
                rows={data.contexts}
                rowKey={(row) => `${row.cell_line}-${row.timepoint}`}
                columns={[
                  { header: "Cell line", cell: (row) => row.cell_line },
                  { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
                  { header: "Replicates", cell: (row) => row.replicate_count, align: "right" },
                ]}
              />
            </Section>
          )}
        </div>
      )}
    </>
  );
}
