"use client";

import { ArrowLeft, Dna } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable } from "@/components/DataTable";
import { Badge, LoadingState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

export default function GeneDetailPage() {
  const { geneId } = useParams<{ geneId: string }>();
  const id = decodeURIComponent(geneId);
  const { data, error, loading } = useApiQuery(() => api.getGene(id), [id]);

  return (
    <>
      <Link href="/genes" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> Genes
      </Link>
      <PageHeader
        title={data?.gene_symbol ?? id}
        description={data ? <span className="font-mono">Gene id {data.gene_id}</span> : undefined}
        icon={<Dna className="h-5 w-5" />}
      />
      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : (
        <>
          <h2 className="mb-2 text-sm font-semibold">Perturbations ({data.perturbations.length})</h2>
          <DataTable
            rows={data.perturbations}
            rowKey={(row) => `${row.perturbation_id}-${row.cell_line}-${row.timepoint}`}
            columns={[
              { header: "Perturbation", cell: (row) => <span className="font-mono text-xs">{row.perturbation_id}</span> },
              { header: "Type", cell: (row) => <Badge>{row.perturbation_type.toUpperCase()}</Badge> },
              { header: "Cell line", cell: (row) => row.cell_line },
              { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
            ]}
          />
        </>
      )}
    </>
  );
}
