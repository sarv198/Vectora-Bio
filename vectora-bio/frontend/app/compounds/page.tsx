"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable, Pagination } from "@/components/DataTable";
import { EmptyState, LoadingState, PageHeader, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours, splitLabels } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

const LIMIT = 50;

export default function CompoundsPage() {
  const [search, setSearch] = useState("");
  const [moa, setMoa] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useApiQuery(
    () => api.listCompounds({ search, moa, limit: LIMIT, offset }),
    [search, moa, offset],
  );

  return (
    <>
      <PageHeader
        context="Library"
        title="Compounds"
        description="Compounds in the screen with their annotated mechanisms and targets."
      />
      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-ink-3" strokeWidth={1.75} aria-hidden />
          <TextInput
            className="pl-8"
            placeholder="Search by name or id"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
            aria-label="Search compounds"
          />
        </div>
        <TextInput
          className="sm:w-60"
          placeholder="Filter by mechanism"
          value={moa}
          onChange={(e) => {
            setMoa(e.target.value);
            setOffset(0);
          }}
          aria-label="Filter by mechanism of action"
        />
      </div>

      {error ? (
        <ApiErrorNotice error={error} />
      ) : loading && !data ? (
        <LoadingState />
      ) : data && data.items.length === 0 ? (
        <EmptyState title="No compounds match these filters" />
      ) : data ? (
        <>
          <DataTable
            rows={data.items}
            rowKey={(row) => `${row.compound_id}-${row.cell_line}-${row.timepoint}`}
            columns={[
              {
                header: "Compound",
                cell: (row) => (
                  <>
                    <Link
                      href={`/compounds/${encodeURIComponent(row.compound_id)}`}
                      className="font-medium text-ink hover:text-accent hover:underline"
                    >
                      {row.compound_name}
                    </Link>
                    <span className="block font-mono text-[11.5px] text-ink-3">{row.compound_id}</span>
                  </>
                ),
              },
              {
                header: "Mechanism",
                cell: (row) =>
                  row.moa ? <span className="text-ink-2">{splitLabels(row.moa).join(", ")}</span> : <span className="text-ink-3">Not annotated</span>,
                className: "max-w-[18rem]",
              },
              {
                header: "Known targets",
                cell: (row) =>
                  row.known_target ? (
                    <span className="text-ink-2">{splitLabels(row.known_target).join(", ")}</span>
                  ) : (
                    <span className="text-ink-3">None</span>
                  ),
                className: "max-w-[16rem]",
              },
              { header: "Cell line", cell: (row) => <span className="text-ink-2">{row.cell_line}</span> },
              { header: "Timepoint", cell: (row) => formatHours(row.timepoint), align: "right" },
              { header: "Replicates", cell: (row) => row.replicate_count, align: "right" },
            ]}
          />
          <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      ) : null}
    </>
  );
}
