import type { ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";

interface Context {
  cell_line: string;
  timepoint: number;
  n_profiles: number;
}

const TITLES: Record<string, string> = {
  data_not_loaded: "Data not loaded",
  network_error: "API not reachable",
  database_unavailable: "Database unavailable",
  images_unavailable: "Images unavailable",
  not_found: "Not found",
  invalid_query: "This query cannot be answered as posed",
  validation_error: "Check the inputs",
};

/** Renders an API error as an informative state. Data-not-loaded is expected, not a failure. */
export function ApiErrorNotice({ error }: { error: ApiError }) {
  const contexts = Array.isArray(error.details.available_contexts)
    ? (error.details.available_contexts as Context[])
    : [];
  const expected = error.code === "data_not_loaded" || error.code === "invalid_query" || error.code === "not_found";

  return (
    <div
      role={expected ? "status" : "alert"}
      className={`rounded-lg border-l-2 bg-surface-2 py-3 pr-4 pl-4 text-[13.5px] ${expected ? "border-warn" : "border-danger"}`}
    >
      <p className="font-medium text-ink">
        {TITLES[error.code] ?? humanize(error.code)}
        {error.status > 0 && <span className="ml-2 text-[12px] font-normal text-ink-3">HTTP {error.status}</span>}
      </p>
      <p className="mt-0.5 break-words text-ink-2">{error.message}</p>
      {error.missingDatasets.length > 0 && (
        <p className="mt-2 text-[12.5px] text-ink-3">
          Missing:{" "}
          {error.missingDatasets.map((name, index) => (
            <span key={name}>
              <code className="font-mono text-ink-2">{name}</code>
              {index < error.missingDatasets.length - 1 ? ", " : ""}
            </span>
          ))}
        </p>
      )}
      {error.hint && <p className="mt-1 text-[12.5px] text-ink-3">{error.hint}</p>}
      {contexts.length > 0 && (
        <div className="mt-2 text-[12.5px] text-ink-3">
          Available contexts:{" "}
          {contexts.map((context, index) => (
            <span key={`${context.cell_line}-${context.timepoint}`} className="text-ink-2">
              {context.cell_line}, {context.timepoint} h ({context.n_profiles} profiles)
              {index < contexts.length - 1 ? "; " : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
