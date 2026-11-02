# Data dictionary

Processed files are optional. Endpoints that read them return an empty list until the files exist. Column names below are the ones the loaders accept.

## `data/processed/compounds.csv` or `compounds.parquet`

| Column | Required | Description |
| --- | --- | --- |
| `compound_id` | yes | Stable identifier. `id` is accepted as a fallback. |
| `name` | yes | Display name |
| `smiles` | no | Structure string |
| `inchikey` | no | InChIKey |

## `data/processed/genes.csv` or `genes.parquet`

| Column | Required | Description |
| --- | --- | --- |
| `symbol` | yes | Gene symbol |
| `entrez_id` | no | NCBI Entrez gene id |
| `name` | no | Gene name |

## `data/processed/signatures/<reference_id>.json`

Used by `POST /api/rescue`. `<reference_id>` is the file name without `.json`.

```json
{
  "values": {
    "GENE_A": 1.2,
    "GENE_B": -0.4
  }
}
```

A bare object of gene symbol to number is also accepted. Values must be finite numbers. Symbols are matched after trimming whitespace.

## Database tables

Created on API startup. These tables are empty until a later import writes to them.

### `compounds`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | Primary key |
| `compound_id` | string | Unique |
| `name` | string | |
| `smiles` | string, nullable | |
| `inchikey` | string, nullable | |

### `genes`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | Primary key |
| `symbol` | string | Unique |
| `entrez_id` | integer, nullable | |
| `name` | string, nullable | |

### `analysis_runs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | Primary key |
| `kind` | string | `similarity`, `targets`, `moa`, `reversal`, or `evaluation` |
| `subject_id` | string, nullable | Compound, gene, or signature id the run refers to |
| `status` | string | |
| `result_json` | text, nullable | Serialized result |
| `created_at` | datetime | UTC |

## API objects

| Schema | Fields |
| --- | --- |
| Compound | `compound_id`, `name`, `smiles`, `inchikey` |
| Gene | `symbol`, `entrez_id`, `name` |
| Mechanism request | `values`: object of gene symbol to number |
| Mechanism prediction | `label`, `score`, `supporting_genes` |
| Rescue request | `values`, `reference_id`, optional `query_id` |
| Reversal score | `query_id`, `reference_id`, `score`, `method` |
| Evaluation request | `task` |
| Evaluation report | `task`, `metrics` (`name`, `value`, optional `n`) |
