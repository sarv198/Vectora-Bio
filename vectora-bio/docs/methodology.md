# Methodology

Cellscope is organized around six stages. Preprocessing is implemented. The other stages have function boundaries and HTTP endpoints, and they return HTTP 501 until an implementation is added.

## 1. Preprocessing

Input is a map of gene symbol to a numeric value. The cleaner trims symbols, drops blank symbols, and drops values that are missing or not finite. Later scaling, probe collapsing, or gene-set restriction belongs in `app/core/preprocessing.py`.

## 2. Similarity

Compare one cleaned signature with a library of signatures and rank the library. The entry point is `rank_similar` in `app/core/similarity.py`. No similarity measure is selected yet.

## 3. Target prioritization

Rank genes implicated by a signature. The entry point is `prioritize_targets` in `app/core/target_prioritization.py`.

## 4. Mechanism inference

Assign mechanism labels to a signature. The entry point is `infer_moa` in `app/core/moa_inference.py`, exposed as `POST /api/mechanisms`.

## 5. Rescue

Score whether a query signature reverses a stored reference signature. `POST /api/rescue` loads `data/processed/signatures/<reference_id>.json` and calls `score_reversal` in `app/core/reversal.py`. Lookup failure is HTTP 404. The score itself is not implemented.

## 6. Evaluation

Compute benchmark metrics for a named task. The entry point is `run_evaluation` in `app/core/evaluation.py`, exposed as `POST /api/evaluation`. No benchmark dataset or metric is wired in yet.

## Status

Do not treat empty responses from the compound and gene lists as scientific results. Those lists are empty when the processed tables are absent. Scores from the analysis endpoints are not produced.
