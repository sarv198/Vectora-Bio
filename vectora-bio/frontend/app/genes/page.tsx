"use client";

import { Dna, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable, Pagination } from "@/components/DataTable";
import { Badge, EmptyState, LoadingState, PageHeader, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { GeneticPerturbationType } from "@/lib/types";

const LIMIT = 50;

export default function GenesPage() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState<GeneticPerturbationType | "">("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useApiQuery(
    () => api.listGenes({ search, perturbation_type: type, limit: LIMIT, offset }),
    [search, type, offset],
  );

  return (
    <>
      <PageHeader
        title="Genes"
        description="Genetic perturbations (CRISPR, ORF, siRNA reagents) imported into the database."
        icon={<Dna className="h-5 w-5" />}
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-ink-3" aria-hidden />
          <TextInput
            className="pl-8"
            placeholder="Search symbol, gene id, or reagent"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
            aria-label="Search genes"
          />
        </div>
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value as GeneticPerturbationType | "");
            setOffset(0);
          }}
          className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm"
          aria-label="Perturbation type"
        >
          <option value="">All types</option>
          <option value="crispr">CRISPR</option>
          <option value="orf">ORF</option>
          <option value="sirna">siRNA</option>
        </select>
      </div>

      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading && !data ? (
        <LoadingState />
      ) : data && data.items.length === 0 ? (
        <EmptyState title="No perturbations match these filters" />
      ) : data ? (
        <>
          <DataTable
            rows={data.items}
            rowKey={(row) => `${row.perturbation_id}-${row.cell_line}-${row.timepoint}`}
            columns={[
              {
                header: "Gene",
                cell: (row) => (
                  <Link href={`/genes/${encodeURIComponent(row.gene_id)}`} className="font-medium text-accent hover:underline">
                    {row.gene_symbol}
                  </Link>
                ),
              },
              { header: "Gene id", cell: (row) => <span className="font-mono text-xs">{row.gene_id}</span> },
              { header: "Perturbation", cell: (row) => <span className="font-mono text-xs">{row.perturbation_id}</span> },
              { header: "Type", cell: (row) => <Badge>{row.perturbation_type.toUpperCase()}</Badge> },
              { header: "Cell line", cell: (row) => row.cell_line },
              { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
            ]}
          />
          <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      ) : null}
    </>
  );
}
