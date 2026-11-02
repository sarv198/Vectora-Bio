// Mirrors the Pydantic schemas in backend/app/schemas.

export type ProfileType = "compound" | "genetic" | "control";
export type GeneticPerturbationType = "crispr" | "orf" | "sirna";
export type PredictionType =
  | "compound_similarity"
  | "target_prioritization"
  | "moa_inference"
  | "phenotypic_rescue";
export type DatasetSplit = "train" | "validation" | "test" | "all";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Compound {
  compound_id: string;
  compound_name: string;
  moa: string | null;
  known_target: string | null;
  cell_line: string;
  timepoint: number;
  replicate_count: number;
}

export interface CompoundDetail {
  compound_id: string;
  compound_name: string;
  moa: string | null;
  known_target: string | null;
  contexts: Compound[];
}

export interface GeneticPerturbation {
  perturbation_id: string;
  gene_id: string;
  gene_symbol: string;
  perturbation_type: GeneticPerturbationType;
  cell_line: string;
  timepoint: number;
}

export interface GeneDetail {
  gene_id: string;
  gene_symbol: string;
  perturbations: GeneticPerturbation[];
}

export interface EvidenceItem {
  evidence_type: string;
  description: string;
  value: number | null;
  source_id: string | null;
}

export interface Prediction {
  query_id: string;
  candidate_id: string;
  prediction_type: PredictionType;
  score: number;
  rank: number;
  supporting_evidence: EvidenceItem[];
}

export interface AnalysisSummary {
  n_candidates: number;
  n_features: number;
  cell_line: string | null;
  timepoint: number | null;
}

export interface AnalysisResponse {
  query_id: string;
  prediction_type: PredictionType;
  predictions: Prediction[];
  parameters: Record<string, unknown>;
  summary: AnalysisSummary;
  message: string | null;
  run_id: number | null;
}

export interface ContextFilter {
  cell_line?: string | null;
  timepoint?: number | null;
}

export interface SimilarityRequest extends ContextFilter {
  compound_id: string;
  top_k?: number;
}

export interface TargetPrioritizationRequest extends ContextFilter {
  compound_id: string;
  genetic_timepoint?: number | null;
  perturbation_types?: GeneticPerturbationType[] | null;
  use_absolute_similarity?: boolean;
  top_k?: number;
}

export interface MoaInferenceRequest extends ContextFilter {
  compound_id: string;
  n_neighbors?: number;
  top_k?: number;
}

export interface RescueSearchRequest extends ContextFilter {
  perturbation_id?: string | null;
  signature?: Record<string, number> | null;
  perturbation_timepoint?: number | null;
  subtract_matched_controls?: boolean;
  top_k?: number;
}

export interface EvaluationRecord {
  id: number;
  metric_name: string;
  metric_value: number;
  evaluation_method: string;
  dataset_split: DatasetSplit;
  sample_count: number;
  parameters: Record<string, unknown> | null;
  created_at: string | null;
}

export interface EvaluationListResponse {
  results: EvaluationRecord[];
  message: string | null;
}

export interface DatasetStatus {
  name: string;
  profile_type: ProfileType;
  path: string;
  available: boolean;
  n_rows: number | null;
  n_features: number | null;
  message: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app_name: string;
  version: string;
  environment: string;
  database: {
    status: "ok" | "unavailable";
    dialect: string;
    message: string | null;
    compound_count: number | null;
    genetic_perturbation_count: number | null;
  };
  datasets: DatasetStatus[];
}

export interface ApiErrorBody {
  error: string;
  message: string;
  details: Record<string, unknown>;
}
