import type { ReactNode } from "react";

import { Button } from "@/components/ui";
import { formatCount } from "@/lib/format";

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
}

export function DataTable<T>({ columns, rows, rowKey }: { columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface">
      <table className="w-full text-sm">
        <thead className="border-b border-line text-left text-xs text-ink-3">
          <tr>
            {columns.map((column) => (
              <th key={column.header} className={`px-4 py-2 font-medium ${column.align === "right" ? "text-right" : ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-line last:border-0 hover:bg-surface-2/60">
              {columns.map((column) => (
                <td key={column.header} className={`px-4 py-2 ${column.align === "right" ? "tabular text-right" : ""}`}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  const end = Math.min(offset + limit, total);
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-ink-3">
      <span className="tabular">
        {total === 0 ? "0 results" : `${formatCount(offset + 1)}–${formatCount(end)} of ${formatCount(total)}`}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button variant="secondary" disabled={end >= total} onClick={() => onChange(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  );
}
