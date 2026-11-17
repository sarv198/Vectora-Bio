"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable } from "@/components/DataTable";
import { PerturbationInspector } from "@/components/PerturbationPanels";
import { LoadingState, PageHeader, Section, selectableRow } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

const TYPE_LABEL: Record<string, string> = { crispr: "CRISPR knockout", orf: "ORF overexpression", sirna: "siRNA" };

export default function GeneDetailPage() {
  const { geneId } = useParams<{ geneId: string }>();
  const id = decodeURIComponent(geneId);
  const { data, error, loading } = useApiQuery(() => api.getGene(id), [id]);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => setSelected(data?.perturbations[0]?.perturbation_id ?? null), [data]);

  return (
    <>
      <Link href="/genes" className="mb-4 inline-flex items-center gap-1 text-[12.5px] text-ink-3 hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Genes
      </Link>
      <PageHeader
        title={data?.gene_symbol ?? id}
        description={data ? <span className="text-[12.5px] text-ink-3">Gene id <span className="font-mono">{data.gene_id}</span></span> : undefined}
      />
      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading || !data ? (
        <LoadingState />
      ) : (
        <div className="space-y-10">
          <Section
            title={`Genetic reagents (${data.perturbations.length})`}
            description="Select a reagent to view its cells."
          >
            <DataTable
              rows={data.perturbations}
              rowKey={(row) => `${row.perturbation_id}-${row.cell_line}-${row.timepoint}`}
              rowProps={(row) => selectableRow(selected === row.perturbation_id, () => setSelected(row.perturbation_id))}
              columns={[
                { header: "Reagent", cell: (row) => <span className="text-ink">{TYPE_LABEL[row.perturbation_type] ?? row.perturbation_type}</span> },
                { header: "Reagent id", cell: (row) => <span className="font-mono text-[12px] text-ink-2">{row.perturbation_id}</span> },
                { header: "Cell line", cell: (row) => <span className="text-ink-2">{row.cell_line}</span> },
                { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
                {
                  header: "",
                  cell: (row) => (
                    <Link
                      href={`/rescue?perturbation=${encodeURIComponent(row.perturbation_id)}`}
                      onClick={(event) => event.stopPropagation()}
                      className="text-[12.5px] text-accent hover:underline"
                    >
                      Find rescue compounds
                    </Link>
                  ),
                  align: "right",
                },
              ]}
            />
          </Section>
          {selected && <PerturbationInspector key={selected} target={{ type: "genetic", id: selected }} />}
        </div>
      )}
    </>
  );
}
