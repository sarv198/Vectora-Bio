# Vectora Bio

Vectora Bio analyzes high-dimensional cellular phenotypic profiles (e.g. processed JUMP Cell Painting data) from chemical and genetic perturbation experiments to support computational drug discovery.

| Capability | API | Status |
| --- | --- | --- |
| Compound-to-compound phenotypic similarity | `POST /api/similarity/compounds` | Cosine similarity of consensus profiles |
| Compound-to-gene matching, target prioritization | `POST /api/targets/prioritize` | Cosine / \|cosine\| matching, max per gene |
| Similarity-based MoA inference | `POST /api/moa/infer` | Similarity-weighted kNN vote |
| Phenotypic rescue / perturbation reversal | `POST /api/rescue/search` | Negative cosine vs. control-subtracted signature |
| Model evaluation | `GET /api/evaluation` + `python -m app.pipeline.evaluate_moa` | Leave-one-out MoA + retrieval metrics |

These are baseline methods, not tuned models. No endpoint returns placeholder results: when the data a request needs has not been imported, it returns **HTTP 503** with `error: "data_not_loaded"` and the list of missing datasets.

## Layout

```text
vectora-bio/
├── backend/
│   ├── app/
│   │   ├── api/         one FastAPI router per capability
│   │   ├── core/        scientific functions (pure NumPy/pandas, no I/O)
│   │   ├── data/        profile loading, validation, consensus, Parquet store
│   │   ├── db/          SQLAlchemy models and sessions (PostgreSQL)
│   │   ├── preprocessing/ Phase 1: raw plates -> normalized consensus profiles
│   │   ├── pipeline/    CLI: download, build, import profiles/metadata, run evaluation
│   │   ├── schemas/     Pydantic request/response models
│   │   └── services/    use cases joining data, DB, and core
│   ├── config/          example column maps for JUMP files
│   └── tests/           pytest suite (synthetic data only)
├── frontend/            Next.js App Router + TypeScript + Tailwind + Recharts
├── data/                raw/ and processed/ (gitignored payloads)
├── docs/                architecture, data dictionary, methodology
├── scripts/             setup_postgres.sql
└── docker-compose.yml   optional Postgres + API stack
```

## Requirements

- Python 3.11+
- Node.js 20.9+
- PostgreSQL 14+ (local install or `docker compose up db`)

## 1. Database

Create a role and database once (as a Postgres superuser), then put the URL in `vectora-bio/.env`:

```powershell
psql -U postgres -h localhost -f scripts/setup_postgres.sql
copy .env.example .env   # then edit DATABASE_URL / password
```

Tables are created by the app on startup, or explicitly:

```powershell
cd backend
python -m app.db.init_db
```

## 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs. If Postgres is unreachable the API still starts; `/api/health` reports `degraded` and DB-backed endpoints return 503 `database_unavailable`.

Tests use a temporary SQLite database and synthetic profiles, so they need no Postgres or downloads:

```powershell
python -m pytest
ruff check app tests
```

## 3. Build data (Phase 1: JUMP pilot)

Nothing is downloaded until you run the download command, and it fetches only the plates your config selects. [`backend/config/phase1_cpjump1_u2os.toml`](backend/config/phase1_cpjump1_u2os.toml) selects 10 U2OS plates (~71 MB) from the JUMP Cell Painting pilot (`cpg0000-jump-pilot`, batch `2020_11_04_CPJUMP1`): 4 compound plates at 48 h, 2 ORF plates at 48 h and 4 CRISPR plates at 144 h.

```powershell
cd backend
python -m app.pipeline.download_cpjump1 --config config\phase1_cpjump1_u2os.toml --dry-run   # list plates and sizes
python -m app.pipeline.download_cpjump1 --config config\phase1_cpjump1_u2os.toml             # -> data/raw/cpjump1/
python -m app.pipeline.build_profiles   --config config\phase1_cpjump1_u2os.toml --load-db  # -> data/processed/ + Postgres
```

The build selects plates, separates compounds / genetic reagents / negative controls, normalizes every plate to its own negative controls, selects one shared feature set, aggregates replicates, and writes the outputs listed in [docs/data_dictionary.md](docs/data_dictionary.md#phase-1-build-outputs) plus `data/processed/build/manifest.json` (config, plates, input checksums, feature-selection counts, warnings). Method details: [docs/methodology.md](docs/methodology.md#phase-1--preprocessing).

## 3b. Import already-processed data (alternative)

If you have profiles processed elsewhere, import them directly. See [docs/data_dictionary.md](docs/data_dictionary.md) for the canonical columns.

```powershell
cd backend
# Profiles -> data/processed/profiles/*.parquet (validated, feature-checked, registered in the DB)
python -m app.pipeline.import_profiles --input ..\data\raw\compound_profiles.parquet --profile-type compound `
  --column-map config\jump_column_map.example.json --set cell_line=U2OS --set timepoint=48 `
  --profile-id-columns Metadata_Source Metadata_Plate Metadata_Well --missing drop-features

python -m app.pipeline.import_profiles --input ..\data\raw\crispr_profiles.parquet --profile-type genetic ...
python -m app.pipeline.import_profiles --input ..\data\raw\control_profiles.parquet --profile-type control ...

# Metadata -> PostgreSQL
python -m app.pipeline.import_metadata compounds --input ..\data\raw\compounds_annotated.csv `
  --column-map config\compound_metadata_map.example.json --set cell_line=U2OS --set timepoint=48
python -m app.pipeline.import_metadata genetic --input ..\data\raw\crispr.csv.gz `
  --column-map config\genetic_metadata_map.example.json --set perturbation_type=crispr --set cell_line=U2OS --set timepoint=96

# Evaluation (stores metrics shown at /api/evaluation)
python -m app.pipeline.evaluate_moa --cell-line U2OS --timepoint 48
```

Every command accepts `--help` and `--dry-run` (except evaluation). Validation errors are printed with examples of the offending rows or columns.

## 4. Frontend

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev        # http://localhost:3000
npm run typecheck
npm test
```

## Docker (optional)

`docker compose up` starts Postgres (host port 5433) and the API (port 8000) with `./data` mounted.
