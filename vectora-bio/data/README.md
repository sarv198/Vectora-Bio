# Data

- `raw/` — files you download yourself (JUMP profiles, metadata, annotation tables). Nothing is downloaded automatically.
- `processed/profiles/` — Parquet files written by `python -m app.pipeline.import_profiles`. The API reads only these.

Everything here except this file and the `.gitkeep` markers is gitignored; so are `*.parquet` and `*.csv.gz` anywhere in the repository. Do not commit datasets.

Column requirements and validation rules: [../docs/data_dictionary.md](../docs/data_dictionary.md).
