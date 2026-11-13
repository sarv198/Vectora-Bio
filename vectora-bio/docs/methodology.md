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

## 1. Compound similarity (Phase 2) — `core/similarity.py`

- `calculate_cosine_similarity(query_profile, candidate_profiles)` → cosine per candidate, in [−1, 1].
- `rank_similar_compounds(compound_id, profiles, metadata, top_k)` → other compounds by descending cosine; ties broken by id; optional metadata attached.
- `pairwise_cosine_similarity(profiles)` → the full labelled n × n matrix.
- `similarity_background(profiles)` → sorted similarities of all distinct compound pairs in a context. Above 200,000 pairs it uses a reproducible random sample of pairs instead, so it scales to the full JUMP library. Cached per context by the `ProfileStore`.
- `score_percentile(scores, background)` → where each score falls in that background (0–100). The UI shows it as "Top x%".

`POST /api/similarity/compounds` returns, for the query and every candidate:
- the compound name, known MoA and known targets from imported metadata;
- the labels it shares with the query;
- the score percentile;
- the replicate agreement recorded by the Phase 1 build.

Two optional filters run before ranking: `annotated_only` (candidates with a known MoA) and `min_replicate_cosine` (drop compounds whose replicate wells disagree, since their consensus profile is unreliable). Annotations are displayed only; they never change a score.

Interpretation: a high score means the cellular profiles are alike in this assay. It suggests, but does not establish, a shared mechanism.

## 2. Compound-to-gene matching and target prioritization (Phase 3) — `core/target_prioritization.py`

These answer two separate questions, served by two endpoints and shown as two tabs in the UI.

**Matching** (`POST /api/targets/match`, `match_compound_to_genes`): which genetic reagents produce profiles that resemble the compound's?
- The compound's consensus profile is compared with every CRISPR and ORF reagent by cosine.
- Ranking uses |cosine| by default. On the JUMP pilot, assuming that overexpression should look opposite to inhibition cut known-target recovery from 13.4% to 7.2% (top-10 of 160 genes), consistent with the pilot paper's observation that ORF and CRISPR profiles of a gene often do not mirror each other.
- Each match is also given as a percentile among all compound-reagent similarities in the same contexts (`cross_similarity_background`).

**Prioritization** (`POST /api/targets/prioritize`, `rank_candidate_targets`): which genes have the strongest combined evidence? It uses two components:
- **Phenotypic score:** the best reagent's match percentile for the gene (0–1).
- **Neighbour-target support** (`neighbor_target_support`): among the query's `n_neighbors` (default 10) most similar compounds, the similarity-weighted share annotated to act on the gene (0–1).

`priority = (phenotypic + w · neighbour_support) / (1 + w)`, with `w = neighbor_weight` (default 2; 0 = phenotype only).

Each gene is shown with its evidence:
- every reagent with its signed cosine and percentile;
- how many of its reagents sit in the top 10% (agreement between independent reagents);
- the similar compounds annotated to act on it;
- all compounds annotated to act on it, with their similarity to the query.

**No leakage:** the query's own annotated targets never enter the score. They are only flagged ("Known target of query") and their rank is reported for comparison.

**Why these defaults:** on the 306 JUMP pilot compounds, top-10 recovery of the annotated primary target among 160 genes was:

| Method | Top-10 recovery |
|---|---|
| Chance | 6.2% |
| Phenotype only | 13.4% |
| Phenotype + neighbours (k = 10, w = 2) | 17.3% |

These figures are on the same data used to choose the defaults (±~2% sampling noise). JUMP-Target-1 also deliberately pairs two compounds per target, which favours neighbour evidence. Held-out validation belongs to Phase 6.

**Interpretation:** results are candidate associations. A gene whose perturbation resembles a compound may act upstream, downstream or in parallel to the compound's true target.

## 3. MoA inference (Phase 4) — `core/moa_inference.py`

`infer_mechanism(compound_id, similar_compounds, annotations, top_k)`:
- Each of the query's `n_neighbors` nearest compounds (default 10) with positive similarity votes for its annotated MoA labels, weighted by similarity.
- **Vote share** is a label's fraction of the total weight of annotated, positively similar neighbours.
- The query's own annotation is never used.

**Evidence strength:** each call reports
- the supporting compounds and their similarities;
- how many of the annotated neighbours agree (`n_supporting` / `n_annotated_neighbors`);
- their mean similarity;
- how many other compounds in the reference set carry the label (a label carried by no other compound cannot be recovered by voting).

**Calibrated confidence** (`leave_one_out_moa_calls`, `fit_moa_confidence`):
1. Every annotated compound is hidden in turn and its MoA inferred from the others; each call is marked correct or not.
2. Isotonic regression maps vote share to the observed hit rate, giving a monotone, empirical P(correct).
3. The query's own leave-one-out calls are excluded when calibrating the query's confidence.
4. Results are cached per context, neighbourhood size and annotation set.

**What to expect on the JUMP pilot:**
- The 292 annotated compounds carry 189 distinct labels, and 98 compounds have a label no other compound shares.
- Leave-one-out top-1 accuracy is 5.8%, or 8.8% among recoverable compounds, against 4.1% for always guessing the most common label.
- Confidence values are therefore low (mostly under 20%). This reflects the dataset, which was designed around targets rather than mechanisms.

`GET /api/compounds?annotated=false` lists the unannotated compounds, the real targets for inference; the MoA page offers them as quick picks.

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
