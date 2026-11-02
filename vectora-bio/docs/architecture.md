# Architecture

```text
Next.js frontend (app router, client components)
        │  fetch, JSON  (NEXT_PUBLIC_API_BASE_URL)
        ▼
FastAPI  app/main.py  ── CORS, error handlers, OpenAPI
        │
        ├── api/          routers: health, compounds, genes, similarity, targets, moa, rescue, evaluation
        ├── services/     use cases: load data + metadata, call core, build predictions, persist runs
        ├── core/         pure scientific functions (NumPy / pandas / scikit-learn)
        ├── data/         read + validate tables, ProfileStore (Parquet cache, consensus per context)
        ├── schemas/      Pydantic models (Compound, GeneticPerturbation, Profile, Prediction, Evaluation, …)
        └── db/           SQLAlchemy models
                │
                ├── PostgreSQL    metadata, dataset registry, analysis runs, predictions, evaluations
                └── data/processed/profiles/*.parquet   high-dimensional feature matrices
```

## Storage split

| What | Where | Why |
| --- | --- | --- |
| Feature vectors (hundreds–thousands of columns) | Parquet | Columnar, compressed, fast to load into NumPy. Never in Postgres. |
| Compound and genetic perturbation metadata, annotations | Postgres | Filtering, search, joins, pagination. |
| Import provenance (`profile_datasets`) | Postgres | Source path, feature hash, contexts per imported file. |
| Analysis runs and predictions | Postgres | Reproducibility; each analysis response carries a `run_id`. |
| Evaluation metrics | Postgres | Written by `app.pipeline.evaluate_moa`, read by `GET /api/evaluation`. |

## Request path (analysis endpoints)

1. The router validates the body (Pydantic) and injects `Settings`, a DB session, and the `ProfileStore`.
2. The service asks the store for **consensus profiles** of the requested context (cell line, timepoint). The store loads the Parquet file once (re-loaded when its mtime changes), filters, and aggregates replicates by `perturbation_id` (median by default). Missing files raise `DataNotLoadedError` → 503.
3. The service checks feature compatibility across datasets (→ 409), loads annotations from Postgres, and calls a `core/` function.
4. Results become `Prediction` objects with `supporting_evidence`, wrapped in an `AnalysisResponse`, and persisted when `PERSIST_ANALYSIS_RUNS=true`. Persistence failure never fails the request.

## Errors

All application errors share one body: `{"error": code, "message": text, "details": {...}}`.

| Code | HTTP | Meaning |
| --- | --- | --- |
| `data_not_loaded` | 503 | A profile file or metadata table the request needs is empty/missing. `details.missing_datasets`, `details.hint`. |
| `database_unavailable` | 503 | Postgres unreachable or tables missing. |
| `invalid_query` | 400 | e.g. no profiles in the requested context (lists `available_contexts`), ambiguous context, `top_k` above `MAX_TOP_K`, zero-norm signature. |
| `not_found` | 404 | Unknown compound / gene / perturbation. |
| `feature_mismatch` | 409 | Profile datasets do not share the same feature columns. |
| `profile_validation_failed` | 422 | Import-time validation report. |

FastAPI's own 422 is returned for malformed request bodies.

## Configuration

`app/config.py` (pydantic-settings) reads environment variables and `vectora-bio/.env`. See `.env.example` for every setting. `get_settings()`, `get_engine()` and `get_profile_store()` are cached factories so tests can swap configuration by clearing them.

## Testing

`backend/tests` runs against a per-test SQLite database and a temporary data directory populated with synthetic profiles (`tests/synthetic.py`, arbitrary geometry and placeholder labels). Coverage: core math, validation, import pipeline (CLI included), every endpoint in both the no-data and loaded states, and the DB-unavailable path. Frontend: `vitest` covers the API client and formatting helpers.
