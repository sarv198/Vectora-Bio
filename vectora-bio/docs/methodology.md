# Methodology

All methods operate on **consensus profiles**: replicate profiles of one perturbation in one (cell line, timepoint) context, aggregated by median. They are deliberately simple, transparent baselines. None of them encodes biological priors, and annotations are only ever taken from imported data.

Input validation shared by every function (`app/core/vectors.py`): vectors must be 1-D/2-D with matching feature counts (labelled pandas inputs are aligned by feature name and rejected if the sets differ), finite, and non-zero-norm.

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
