# Data

- `raw/cpjump1/` — JUMP pilot plates and metadata, fetched by `python -m app.pipeline.download_cpjump1` (only the plates a config selects).
- `raw/annotations/` — optional files you provide (MoA annotations, gene id table).
- `processed/` — written by `python -m app.pipeline.build_profiles` (or `import_profiles`): `profiles/`, `metadata/`, `wells/`, `build/manifest.json`. The API reads `processed/profiles/`.

Everything here except this file and the `.gitkeep` markers is gitignored; so are `*.parquet` and `*.csv.gz` anywhere in the repository. Do not commit datasets.

Column requirements and validation rules: [../docs/data_dictionary.md](../docs/data_dictionary.md).
