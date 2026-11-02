"use client";

import { FlaskConical, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ApiErrorNotice } from "@/components/ApiErrorNotice";
import { DataTable, Pagination } from "@/components/DataTable";
import { EmptyState, LoadingState, PageHeader, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { formatHours } from "@/lib/format";
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
        title="Compounds"
        description="Compound metadata imported into the database, one row per cell line and timepoint."
        icon={<FlaskConical className="h-5 w-5" />}
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-ink-3" aria-hidden />
          <TextInput
            className="pl-8"
            placeholder="Search id or name"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
            aria-label="Search compounds"
          />
        </div>
        <TextInput
          className="sm:w-56"
          placeholder="Filter by MoA"
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
                  <Link href={`/compounds/${encodeURIComponent(row.compound_id)}`} className="font-medium text-accent hover:underline">
                    {row.compound_id}
                  </Link>
                ),
              },
              { header: "Name", cell: (row) => row.compound_name },
              { header: "MoA", cell: (row) => row.moa ?? <span className="text-ink-3">—</span> },
              { header: "Known target", cell: (row) => row.known_target ?? <span className="text-ink-3">—</span> },
              { header: "Cell line", cell: (row) => row.cell_line },
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
