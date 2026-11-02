# Architecture

Cellscope is a single backend process with a file store for signatures and a relational database for compound, gene, and analysis-run records. The web client directories are reserved and do not yet serve an application.

```text
frontend (reserved)
    │
    ▼
FastAPI  app/main.py
    │
    ├── api/            HTTP routers
    ├── services/       use-case orchestration and file lookup
    ├── core/           preprocessing and analytical routines
    ├── schemas/        request and response models
    └── db/             SQLAlchemy models and sessions
            │
            ├── SQLite (default) or Postgres (Docker)
            └── data/processed  tables and signature JSON
```

## Request path

1. A router validates the body with a Pydantic schema.
2. The matching service loads processed data when the use case needs it.
3. The service calls a function in `core/`.
4. Similarity, target prioritization, mechanism inference, reversal, and evaluation raise `NotImplementedError`. The API returns HTTP 501 for those cases.
5. A missing rescue reference signature returns HTTP 404 before scoring is attempted.

## Modules

| Path | Responsibility |
| --- | --- |
| `app/main.py` | Application, router mounting, 501 handler |
| `app/config.py` | Environment-backed paths and database URL |
| `app/api/compounds.py` | List and fetch compounds |
| `app/api/genes.py` | List and fetch genes |
| `app/api/mechanisms.py` | Mechanism inference requests |
| `app/api/rescue.py` | Rescue scoring requests |
| `app/api/evaluation.py` | Evaluation requests |
| `app/core/preprocessing.py` | Signature cleanup |
| `app/core/similarity.py` | Signature similarity |
| `app/core/target_prioritization.py` | Target ranking |
| `app/core/moa_inference.py` | Mechanism labels |
| `app/core/reversal.py` | Reversal score |
| `app/core/evaluation.py` | Benchmark metrics |
| `app/services/data_loader.py` | Processed tables and signature files |
| `app/services/compound_service.py` | Compound queries |
| `app/services/analysis_service.py` | Analysis use cases |
| `app/db/models.py` | `compounds`, `genes`, `analysis_runs` |
| `app/db/session.py` | Engine, session, schema creation |

Startup calls `init_db()`, which creates tables if they are missing. Compound and gene endpoints currently read processed files. The tables are the place to persist imported records and analysis runs.

## Configuration

`app/config.py` resolves `cellscope/` from the package location. `DATABASE_URL`, `DATA_RAW_DIR`, and `DATA_PROCESSED_DIR` override the defaults. Relative paths in those variables are resolved from `cellscope/`.
