"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable, Pagination } from "@/components/DataTable";
import { EmptyState, LoadingState, PageHeader, Select, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";
import type { GeneticPerturbationType } from "@/lib/types";

const LIMIT = 50;
const TYPE_LABEL: Record<string, string> = { crispr: "CRISPR knockout", orf: "ORF overexpression", sirna: "siRNA" };

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
        context="Library"
        title="Genes"
        description="Genetic perturbations in the screen: CRISPR guides and ORF constructs, one row per reagent."
      />
      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-ink-3" strokeWidth={1.75} aria-hidden />
          <TextInput
            className="pl-8"
            placeholder="Search symbol, gene id or reagent"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
            aria-label="Search genes"
          />
        </div>
        <Select
          value={type}
          onChange={(e) => {
            setType(e.target.value as GeneticPerturbationType | "");
            setOffset(0);
          }}
          className="sm:w-48"
          aria-label="Perturbation type"
        >
          <option value="">All reagent types</option>
          <option value="crispr">CRISPR knockout</option>
          <option value="orf">ORF overexpression</option>
          <option value="sirna">siRNA</option>
        </Select>
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
                  <Link
                    href={`/genes/${encodeURIComponent(row.gene_id)}`}
                    className="font-medium text-ink hover:text-accent hover:underline"
                  >
                    {row.gene_symbol}
                  </Link>
                ),
              },
              { header: "Reagent", cell: (row) => <span className="text-ink-2">{TYPE_LABEL[row.perturbation_type] ?? row.perturbation_type}</span> },
              { header: "Reagent id", cell: (row) => <span className="font-mono text-[12px] text-ink-2">{row.perturbation_id}</span> },
              { header: "Gene id", cell: (row) => <span className="font-mono text-[12px] text-ink-3">{row.gene_id}</span> },
              { header: "Cell line", cell: (row) => <span className="text-ink-2">{row.cell_line}</span> },
              { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
            ]}
          />
          <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      ) : null}
    </>
  );
}
