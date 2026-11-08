# Methodology

All methods operate on **consensus profiles**: replicate profiles of one perturbation in one (cell line, timepoint) context, aggregated by median. They are deliberately simple, transparent baselines. None of them encodes biological priors, and annotations are only ever taken from imported data.

Input validation shared by every function (`app/core/vectors.py`): vectors must be 1-D/2-D with matching feature counts (labelled pandas inputs are aligned by feature name and rejected if the sets differ), finite, and non-zero-norm.

## Phase 1 — Preprocessing

`app/preprocessing/`, run by `python -m app.pipeline.build_profiles`. Input: the JUMP pilot's per-plate `*_augmented.csv.gz` files. These hold well-level means of CellProfiler single-cell features with metadata attached, and are not normalized.

1. **Select plates** (`sources.select_plates`). Uses `experiment-metadata.tsv` filtered on batch, `Cell_type`, `Density`, `Antibiotics`, optional `Anomaly` exclusions, and one `Time` per modality. The pilot has no timepoint shared by compound, ORF and CRISPR plates, so each modality has its own.
2. **Separate** (`sources.read_plates`, `build`). Empty wells are dropped. `control_type == "negcon"` wells are matched controls: DMSO, non-targeting/intergenic guides, negative-control ORFs. Every other well is a perturbation, including positive controls, which are real compounds and reagents with known targets. Wells are identified by `broad_sample` (DMSO: by name).
3. **Normalize** (`normalize.normalize_by_plate`). Each plate is scaled to its own negative-control wells: `(x − median_negcon) / MAD_negcon`, with the MAD scaled to match a normal SD. This removes plate and batch offsets and expresses every profile relative to matched controls. A feature with zero MAD on a plate cannot be scaled; it becomes missing on that plate and is dropped in the next step.
4. **Select features** (`feature_selection.select_features`). The selection is fit once on all wells of all modalities, so compound, genetic and control profiles share exactly one feature set. The steps run in order:
   - drop positional/bookkeeping features (location, centre, bounding box, object number, parent);
   - drop features with any missing or non-finite value;
   - drop constant or near-constant features (caret-style frequency and uniqueness cut-offs);
   - drop redundant features greedily: visit from least to most correlated and drop a feature whose |r| with a kept feature exceeds 0.9.
5. **Aggregate** (`aggregate.aggregate_replicates`). Each perturbation becomes the median of its wells across plates, per (modality, cell line, timepoint). The mean pairwise cosine of the replicate wells is recorded as a reproducibility indicator; downstream phases can use it to filter weak or irreproducible responses.
6. **Write**. Parquet profiles, metadata and well-level files, plus a manifest with input checksums; the metadata is optionally upserted into Postgres.

Annotations are used only as provided. Known targets come from `JUMP-Target-1_compound_metadata_targets.tsv` (`target_list`). MoA comes only from an external file you configure, joined on `pert_iname` or InChIKey. Gene ids come from an optional symbol→id table; otherwise the symbol is used as the id.

On a real 4-plate U2OS sample, the build reduced 5,792 features to 893. Positive controls replicated more strongly than ordinary treatments (median replicate cosine 0.68–0.86 vs 0.53).

## 1. Compound similarity — `core/similarity.py`

- `calculate_cosine_similarity(query_profile, candidate_profiles)` → cosine per candidate, in [−1, 1].
- `rank_similar_compounds(compound_id, profiles, metadata, top_k)` → other compounds by descending cosine; ties broken by id; optional metadata attached.

## 2. Target prioritization — `core/target_prioritization.py`

- `match_compound_to_genes(compound_profile, genetic_profiles, top_k)` → cosine of the compound against each genetic reagent. By default ranked by |cosine|, because loss- and gain-of-function reagents can phenocopy or oppose an inhibitor; the signed value is kept.
- `prioritize_candidate_targets(matches, annotations)` → groups reagents by gene; gene score = best reagent score, ties broken by number of supporting reagents. Annotations (e.g. "listed as a known target of the query") are attached as evidence and do not change the score.

## 3. MoA inference — `core/moa_inference.py`

`infer_mechanism(compound_id, similar_compounds, annotations, top_k)`: each neighbour with positive similarity votes for its MoA label(s) with weight = similarity. Score = label weight / total weight of annotated, positively similar neighbours (0–1). The query's own annotation is never used.

## 4. Phenotypic rescue — `core/reversal.py`

- Signature = perturbation consensus − matched control consensus (same cell line and timepoint). Compound consensus profiles are control-subtracted the same way when `subtract_matched_controls=true`.
- `calculate_reversal_score(compound, signature)` = −cosine: 1 is exact opposition, −1 mimicry.
- `rank_reversal_candidates(signature, compound_profiles, top_k)`.

Reversal in profile space suggests, but does not establish, functional rescue.

## 5. Evaluation — `core/evaluation.py`, `services/evaluation_service.py`

Metrics:

- `precision_at_k` — relevant items in the top k / k (short rankings are penalized).
- `recall_at_k` — relevant items in the top k / all relevant (undefined, raises, with no relevant items).
- `ndcg_at_k` — linear gain, log2 discount, normalized by the ideal ordering; 0 if all relevance is 0 (matches `sklearn.metrics.ndcg_score`).
- `evaluate_moa_predictions` — accuracy and precision/recall/F1 macro-averaged over the true labels.

Benchmark (`python -m app.pipeline.evaluate_moa`), leave-one-out over annotated compounds in one context:

- top-1 MoA from kNN voting vs. annotation (single-label compounds only; no prediction counts as wrong);
- same-MoA retrieval: other annotated compounds ranked by similarity, relevant if they share any label → mean precision@k, recall@k, nDCG@k.

Results are stored with their parameters and `dataset_split="all"`. There is no train/test split yet; leave-one-out on the full annotated set measures neighbourhood consistency, not generalization to new chemistry.

## Known limitations

- Cosine on raw consensus features; no feature weighting, batch correction, or learned embedding beyond what the imported profiles already include.
- Consensus by median ignores replicate quality (e.g. mAP-based filtering of non-reproducible perturbations).
- No statistical significance (e.g. null distributions from shuffled profiles) attached to scores yet.
- Similarity search is exact and in-memory; very large libraries will need an ANN index or chunking.
