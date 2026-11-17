import type { ReactNode } from "react";

import { Button, TABLE, TD, TH, THEAD, TR, TableFrame } from "@/components/ui";
import { formatCount } from "@/lib/format";

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  rowProps,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Optional per-row props (e.g. from `selectableRow`). */
  rowProps?: (row: T) => Record<string, unknown>;
}) {
  return (
    <TableFrame>
      <table className={TABLE}>
        <thead className={THEAD}>
          <tr>
            {columns.map((column, index) => (
              <th key={index} className={`${TH} ${column.align === "right" ? "text-right" : ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className={`${TR} hover:bg-surface-2`} {...(rowProps?.(row) ?? {})}>
              {columns.map((column, index) => (
                <td
                  key={index}
                  className={`${TD} ${column.align === "right" ? "tabular text-right" : ""} ${column.className ?? ""}`}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </TableFrame>
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
    <div className="mt-3 flex items-center justify-between text-[12.5px] text-ink-3">
      <span className="tabular">
        {total === 0 ? "No results" : `${formatCount(offset + 1)} to ${formatCount(end)} of ${formatCount(total)}`}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={end >= total} onClick={() => onChange(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  );
}
