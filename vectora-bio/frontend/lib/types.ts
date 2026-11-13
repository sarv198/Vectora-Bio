// Mirrors the Pydantic schemas in backend/app/schemas.

export type ProfileType = "compound" | "genetic" | "control";
export type GeneticPerturbationType = "crispr" | "orf" | "sirna";
export type PredictionType =
  | "compound_similarity"
  | "compound_gene_matching"
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
  candidate_name: string | null;
  candidate_annotations: Record<string, unknown>;
}

/** `candidate_annotations` returned by compound similarity. */
export interface SimilarityAnnotations {
  moa: string | null;
  known_target: string | null;
  shared_moa: string[];
  score_percentile: number;
  replicate_cosine: number | null;
}

/** `query_annotations` returned for a compound query. */
export interface CompoundQueryAnnotations {
  moa: string | null;
  known_target: string | null;
  replicate_cosine: number | null;
}

export interface AnalysisSummary {
  n_candidates: number;
  n_features: number;
  cell_line: string | null;
  timepoint: number | null;
}

export interface AnalysisResponse {
  query_id: string;
  query_name: string | null;
  query_annotations: Record<string, unknown>;
  prediction_type: PredictionType;
  predictions: Prediction[];
  parameters: Record<string, unknown>;
  summary: AnalysisSummary;
  message: string | null;
  details: Record<string, unknown>;
  run_id: number | null;
}

export interface ContextFilter {
  cell_line?: string | null;
  timepoint?: number | null;
}

export interface SimilarityRequest extends ContextFilter {
  compound_id: string;
  top_k?: number;
  annotated_only?: boolean;
  min_replicate_cosine?: number | null;
}

export interface TargetMatchRequest extends ContextFilter {
  compound_id: string;
  genetic_timepoint?: number | null;
  perturbation_types?: GeneticPerturbationType[] | null;
  use_absolute_similarity?: boolean;
  top_k?: number;
}

export interface TargetPrioritizationRequest extends TargetMatchRequest {
  n_neighbors?: number;
  neighbor_weight?: number;
}

/** A compound referenced as evidence. */
export interface CompoundRef {
  compound_id: string;
  compound_name: string | null;
  similarity: number | null;
}

/** `candidate_annotations` returned by compound-to-gene matching. */
export interface MatchAnnotations {
  gene_id: string | null;
  gene_symbol: string | null;
  perturbation_type: string | null;
  cosine: number;
  percentile: number;
}

export interface ReagentEvidence {
  perturbation_id: string;
  perturbation_type: string | null;
  cosine: number;
  percentile: number;
}

/** `candidate_annotations` returned by target prioritization. */
export interface TargetAnnotations {
  gene_id: string;
  phenotypic_score: number;
  neighbor_support: number;
  n_reagents: number;
  n_strong_reagents: number;
  reagents: ReagentEvidence[];
  supporting_compounds: CompoundRef[];
  known_compounds: CompoundRef[];
  n_known_compounds: number;
  annotated_target_of_query: boolean;
}

/** `candidate_annotations` returned by MoA inference. */
export interface MoaAnnotations {
  vote_share: number;
  confidence: number | null;
  n_supporting: number;
  n_annotated_neighbors: number;
  agreement: number | null;
  mean_similarity: number | null;
  label_frequency: number;
  supporting_compounds: CompoundRef[];
  matches_query_annotation: boolean | null;
}

export interface MoaNeighbor {
  compound_id: string;
  compound_name: string | null;
  similarity: number;
  moa: string | null;
}

export interface MoaCalibration {
  method: string;
  n_compounds: number;
  n_calls: number;
  top1_accuracy: number;
  call_precision: number;
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
