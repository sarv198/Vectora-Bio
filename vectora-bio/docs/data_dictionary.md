# Data dictionary

## Profile files (Parquet)

Written by `app.pipeline.import_profiles` to `data/processed/profiles/`:

| File | `profile_type` |
| --- | --- |
| `compound_profiles.parquet` | `compound` |
| `genetic_profiles.parquet` | `genetic` |
| `control_profiles.parquet` | `control` |

One row per profile (typically one well). Columns:

| Column | Required | Description |
| --- | --- | --- |
| `profile_id` | yes | Unique per row. Build it from source columns with `--profile-id-columns` (joined with `:`). |
| `perturbation_id` | yes | Compound id (e.g. JUMP `Metadata_JCP2022`), genetic reagent id, or control id. Replicates share it. |
| `profile_type` | yes | `compound`, `genetic` or `control`. Filled from `--profile-type` if absent. |
| `cell_line` | yes | e.g. `U2OS`. Usually supplied with `--set cell_line=…`. |
| `timepoint` | yes | Hours after perturbation, > 0. |
| `Metadata_*` | no | Any other metadata. Kept, never used as features. |
| everything else | ≥ 1 | Numeric features, stored as float32. |

### Validation (import fails on errors)

- Required metadata columns present and non-blank; timepoint numeric and positive.
- `profile_type` values valid and matching `--profile-type`.
- `profile_id` unique.
- At least one feature; all features numeric.
- No missing or infinite feature values (choose `--missing drop-features` or `drop-rows` to clean instead).
- No all-zero profiles (cosine undefined).
- Feature set identical to any already-imported profile type (use `--feature-list` to restrict every dataset to a shared list). Warning only: constant features.

### Consensus profiles

At query time, profiles are filtered to the requested `cell_line` / `timepoint` and aggregated per `perturbation_id` (`CONSENSUS_METHOD`, median by default). A perturbation present in more than one context within the filtered set is rejected as ambiguous.

Profiles are expected to be **normalized relative to matched controls** (as JUMP's processed profiles are, per plate). Rescue additionally subtracts the matched control consensus.

## Metadata tables (PostgreSQL)

### `compounds` — unique on (`compound_id`, `cell_line`, `timepoint`)

| Column | Type | Notes |
| --- | --- | --- |
| `compound_id` | varchar(128) | Matches `perturbation_id` in compound profiles. |
| `compound_name` | varchar(512) | `--name-fallback-to-id` uses the id when blank. |
| `moa` | varchar, nullable | Mechanism(s) of action; multiple separated by `|`. |
| `known_target` | varchar, nullable | Target gene symbol(s); multiple separated by `|`. |
| `cell_line`, `timepoint` | | Context. |
| `replicate_count` | int | Counted from imported compound profiles when the column is absent. |

### `genetic_perturbations` — unique on (`perturbation_id`, `cell_line`, `timepoint`)

| Column | Type | Notes |
| --- | --- | --- |
| `perturbation_id` | varchar(128) | Matches `perturbation_id` in genetic profiles. |
| `gene_id` | varchar(64) | e.g. NCBI Gene ID. |
| `gene_symbol` | varchar(64) | |
| `perturbation_type` | varchar(16) | `crispr`, `orf` or `sirna`. |
| `cell_line`, `timepoint` | | Context. |

### Other tables

| Table | Contents |
| --- | --- |
| `profile_datasets` | One row per imported profile type: file and source paths, row/feature counts, feature hash, contexts. |
| `analysis_runs` | Prediction type, query id, parameters (JSON), timestamp. |
| `predictions` | Per-run ranked candidates with score and evidence (JSON). |
| `evaluation_results` | `metric_name`, `metric_value`, `evaluation_method`, `dataset_split`, `sample_count`, parameters. |

## API objects

| Schema | Fields |
| --- | --- |
| `Compound` | `compound_id`, `compound_name`, `moa?`, `known_target?`, `cell_line`, `timepoint`, `replicate_count` |
| `GeneticPerturbation` | `perturbation_id`, `gene_id`, `gene_symbol`, `perturbation_type`, `cell_line`, `timepoint` |
| `Profile` | `profile_id`, `perturbation_id`, `profile_type`, `cell_line`, `timepoint`, `feature_values` |
| `Prediction` | `query_id`, `candidate_id`, `prediction_type`, `score`, `rank`, `supporting_evidence[]` |
| `EvidenceItem` | `evidence_type`, `description`, `value?`, `source_id?` |
| `Evaluation` | `metric_name`, `metric_value`, `evaluation_method`, `dataset_split`, `sample_count` |

## Column maps

`--column-map` takes a JSON object of *source column → canonical column*. Keys starting with `_` are comments. Examples in `backend/config/`. Verify every source column name against the files you actually downloaded.
