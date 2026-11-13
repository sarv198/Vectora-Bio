import type {
  AnalysisResponse,
  Compound,
  CompoundDetail,
  EvaluationListResponse,
  GeneDetail,
  GeneticPerturbation,
  HealthResponse,
  MoaInferenceRequest,
  Page,
  RescueSearchRequest,
  SimilarityRequest,
  TargetMatchRequest,
  TargetPrioritizationRequest,
} from "@/lib/types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** An error from the API, normalized from `{error, message, details}` or FastAPI's 422 body. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  get missingDatasets(): string[] {
    const value = this.details.missing_datasets;
    return Array.isArray(value) ? value.map(String) : [];
  }

  get hint(): string | null {
    return typeof this.details.hint === "string" ? this.details.hint : null;
  }
}

interface ValidationIssue {
  loc?: unknown[];
  msg?: string;
}

export function parseApiError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.error === "string" && typeof record.message === "string") {
      const details = record.details && typeof record.details === "object" ? record.details : {};
      return new ApiError(status, record.error, record.message, details as Record<string, unknown>);
    }
    if (Array.isArray(record.detail)) {
      const issues = (record.detail as ValidationIssue[]).map((issue) => {
        const field = (issue.loc ?? []).filter((part) => part !== "body").join(".");
        return field ? `${field}: ${issue.msg ?? "invalid"}` : (issue.msg ?? "invalid");
      });
      return new ApiError(status, "validation_error", issues.join("; ") || "Invalid request.", { issues });
    }
    if (typeof record.detail === "string") {
      return new ApiError(status, "http_error", record.detail);
    }
  }
  return new ApiError(status, "http_error", `Request failed with status ${status}.`);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw parseApiError(response.status, body);
  }
  return body as T;
}

type QueryValue = string | number | boolean | null | undefined;

export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

const post = <T>(path: string, body: unknown) => apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => apiFetch<HealthResponse>("/api/health"),
  listCompounds: (params: Record<string, QueryValue>) => apiFetch<Page<Compound>>(`/api/compounds${buildQuery(params)}`),
  getCompound: (id: string) => apiFetch<CompoundDetail>(`/api/compounds/${encodeURIComponent(id)}`),
  listGenes: (params: Record<string, QueryValue>) =>
    apiFetch<Page<GeneticPerturbation>>(`/api/genes${buildQuery(params)}`),
  getGene: (id: string) => apiFetch<GeneDetail>(`/api/genes/${encodeURIComponent(id)}`),
  similarCompounds: (body: SimilarityRequest) => post<AnalysisResponse>("/api/similarity/compounds", body),
  matchGenes: (body: TargetMatchRequest) => post<AnalysisResponse>("/api/targets/match", body),
  prioritizeTargets: (body: TargetPrioritizationRequest) => post<AnalysisResponse>("/api/targets/prioritize", body),
  inferMoa: (body: MoaInferenceRequest) => post<AnalysisResponse>("/api/moa/infer", body),
  searchRescue: (body: RescueSearchRequest) => post<AnalysisResponse>("/api/rescue/search", body),
  listEvaluations: () => apiFetch<EvaluationListResponse>("/api/evaluation"),
};
