import { AlertTriangle, DatabaseZap, PackageOpen, WifiOff } from "lucide-react";

import type { ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";

interface Context {
  cell_line: string;
  timepoint: number;
  n_profiles: number;
}

/** Renders an API error as an informative state. Data-not-loaded is an expected state, not a failure. */
export function ApiErrorNotice({ error }: { error: ApiError }) {
  const contexts = Array.isArray(error.details.available_contexts)
    ? (error.details.available_contexts as Context[])
    : [];

  if (error.code === "data_not_loaded") {
    return (
      <div role="status" className="rounded-xl border border-warn-line bg-warn-soft p-4 text-sm">
        <div className="flex items-start gap-3">
          <PackageOpen className="mt-0.5 h-5 w-5 shrink-0 text-warn" aria-hidden />
          <div className="space-y-2">
            <p className="font-semibold text-ink">Data not loaded</p>
            <p className="text-ink-2">{error.message}</p>
            {error.missingDatasets.length > 0 && (
              <ul className="flex flex-wrap gap-1.5">
                {error.missingDatasets.map((name) => (
                  <li key={name} className="rounded bg-surface px-2 py-0.5 font-mono text-xs text-ink-2">
                    {name}
                  </li>
                ))}
              </ul>
            )}
            {error.hint && <p className="text-xs text-ink-2">{error.hint}</p>}
          </div>
        </div>
      </div>
    );
  }

  const Icon = error.code === "network_error" ? WifiOff : error.code === "database_unavailable" ? DatabaseZap : AlertTriangle;
  return (
    <div role="alert" className="rounded-xl border border-danger-line bg-danger-soft p-4 text-sm">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 space-y-2">
          <p className="font-semibold text-ink">
            {humanize(error.code)}
            {error.status > 0 && <span className="ml-2 font-normal text-ink-3">HTTP {error.status}</span>}
          </p>
          <p className="break-words text-ink-2">{error.message}</p>
          {contexts.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-ink-3">Available contexts:</p>
              <ul className="flex flex-wrap gap-1.5">
                {contexts.map((context) => (
                  <li
                    key={`${context.cell_line}-${context.timepoint}`}
                    className="rounded bg-surface px-2 py-0.5 font-mono text-xs text-ink-2"
                  >
                    {context.cell_line} · {context.timepoint} h · {context.n_profiles} profiles
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
