# Cellscope

Cellscope is a local application for comparing compound and gene signatures, prioritizing targets, inferring mechanisms, scoring transcriptional rescue, and evaluating those results.

The analytical routines are explicit placeholders. Data loading, the HTTP API, and the database schema are in place so those routines can be added without rearranging the project.

## Layout

```text
cellscope/
├── data/                 # raw inputs and processed tables
├── notebooks/            # exploratory analysis
├── backend/              # FastAPI application
├── frontend/             # web client (directories reserved)
└── docs/                 # architecture, data dictionary, methodology
```

## Requirements

- Python 3.12
- Optional: Docker, for Postgres

The API uses a local SQLite file by default (`backend/cellscope.db`).

## Run the API

From `cellscope/backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Copy `.env.example` to `.env` in this directory when you want to override the defaults. Settings are read from the environment and from `cellscope/.env`.

## Run with Docker

From `cellscope`:

```powershell
docker compose up
```

The API is published on port 8000 and Postgres on port 5432. The database credentials in `docker-compose.yml` are for this local stack only.

## HTTP API

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/health` | Service status |
| `GET` | `/api/compounds` | Compounds from `data/processed/compounds.csv` or `.parquet` |
| `GET` | `/api/genes` | Genes from `data/processed/genes.csv` or `.parquet` |
| `POST` | `/api/mechanisms` | Mechanism inference (not implemented) |
| `POST` | `/api/rescue` | Rescue scoring against a stored reference signature |
| `POST` | `/api/evaluation` | Evaluation (not implemented) |

Processed-file columns and the signature JSON shape are described in [docs/data_dictionary.md](docs/data_dictionary.md).
