"""Compound and genetic metadata tables built from source metadata plus optional external annotations.

Only annotations present in the input files are used; nothing is inferred.
"""

from dataclasses import dataclass, field

import pandas as pd

from app.config import resolve_project_path
from app.preprocessing.config import AnnotationConfig

LABEL_SEPARATOR = "|"


@dataclass
class AnnotationReport:
    n_compounds: int = 0
    n_with_moa: int = 0
    n_with_known_target: int = 0
    moa_source: str | None = None
    n_genetic: int = 0
    n_with_mapped_gene_id: int = 0
    gene_id_source: str | None = None
    warnings: list[str] = field(default_factory=list)


def _normalize_key(values: pd.Series) -> pd.Series:
    return values.astype("string").str.strip().str.casefold()


def _join_labels(values: pd.Series) -> str | None:
    labels: list[str] = []
    for value in values.dropna():
        for part in str(value).split(LABEL_SEPARATOR):
            label = part.strip()
            if label and label not in labels:
                labels.append(label)
    return LABEL_SEPARATOR.join(labels) or None


def load_moa_table(config: AnnotationConfig) -> pd.DataFrame | None:
    """``key -> moa`` from the configured annotation file (e.g. Drug Repurposing Hub drugs)."""
    if config.moa_file is None:
        return None
    path = resolve_project_path(config.moa_file)
    if not path.is_file():
        raise FileNotFoundError(f"MoA annotation file not found: {path}")
    table = pd.read_csv(path, sep=None, engine="python", comment=config.moa_comment_prefix, dtype=str)
    missing = [c for c in (config.moa_key_column, config.moa_column) if c not in table.columns]
    if missing:
        raise ValueError(f"MoA annotation file {path.name} lacks column(s) {missing}; has {list(table.columns)[:10]}")
    table = table.assign(_key=_normalize_key(table[config.moa_key_column]))
    return table.groupby("_key")[config.moa_column].agg(_join_labels).rename("moa").reset_index()


def load_gene_id_map(config: AnnotationConfig) -> dict[str, str] | None:
    if config.gene_id_file is None:
        return None
    path = resolve_project_path(config.gene_id_file)
    if not path.is_file():
        raise FileNotFoundError(f"Gene id file not found: {path}")
    table = pd.read_csv(path, sep=None, engine="python", dtype=str)
    missing = [c for c in (config.gene_symbol_column, config.gene_id_column) if c not in table.columns]
    if missing:
        raise ValueError(f"Gene id file {path.name} lacks column(s) {missing}.")
    table = table.dropna(subset=[config.gene_symbol_column, config.gene_id_column])
    return dict(
        zip(table[config.gene_symbol_column].str.strip(), table[config.gene_id_column].str.strip(), strict=True)
    )


def build_compound_metadata(
    compounds: pd.DataFrame,
    source_metadata: pd.DataFrame,
    config: AnnotationConfig,
    report: AnnotationReport,
) -> pd.DataFrame:
    """One row per compound consensus profile, in the API's ``Compound`` shape plus provenance columns.

    ``known_target`` is the annotated target list from the source metadata (``target_list``,
    falling back to the plate-level ``gene``); ``moa`` comes only from the optional MoA file.
    """
    source = source_metadata.drop_duplicates("broad_sample").set_index("broad_sample")
    target_list = source["target_list"] if "target_list" in source.columns else pd.Series(dtype=str)
    table = pd.DataFrame(
        {
            "compound_id": compounds["perturbation_id"].astype(str),
            "compound_name": compounds["Metadata_pert_iname"].astype("string").fillna(compounds["perturbation_id"]),
            "known_target": compounds["perturbation_id"].map(target_list).fillna(compounds["Metadata_gene"]),
            "cell_line": compounds["cell_line"],
            "timepoint": compounds["timepoint"].astype(float),
            "replicate_count": compounds["Metadata_n_replicates"].astype(int),
            "inchikey": compounds["Metadata_InChIKey"],
            "primary_target": compounds["Metadata_gene"],
            "control_type": compounds["Metadata_control_type"],
            "replicate_cosine": compounds["Metadata_replicate_cosine"],
        }
    )

    moa = load_moa_table(config)
    if moa is None:
        table["moa"] = None
        report.warnings.append("No MoA annotation file configured; compound moa is empty.")
    else:
        report.moa_source = str(config.moa_file)
        key_source = table["compound_name"] if config.moa_match_on == "pert_iname" else table["inchikey"]
        table["moa"] = _normalize_key(key_source).map(moa.set_index("_key")["moa"])

    table = table.astype(object).where(table.notna(), None)
    report.n_compounds = len(table)
    report.n_with_moa = int(table["moa"].notna().sum())
    report.n_with_known_target = int(table["known_target"].notna().sum())
    columns = ["compound_id", "compound_name", "moa", "known_target", "cell_line", "timepoint", "replicate_count"]
    return table[columns + [c for c in table.columns if c not in columns]]


def build_genetic_metadata(genetic: pd.DataFrame, config: AnnotationConfig, report: AnnotationReport) -> pd.DataFrame:
    """One row per genetic reagent consensus profile, in the API's ``GeneticPerturbation`` shape.

    The pilot metadata gives gene symbols only. ``gene_id`` comes from the optional gene id
    file; unmapped symbols use the symbol itself as the id (counted in the report).
    """
    gene_ids = load_gene_id_map(config)
    symbols = genetic["Metadata_gene"].astype("string").str.strip()
    if gene_ids is None:
        mapped = pd.Series(pd.NA, index=genetic.index, dtype="string")
        report.warnings.append("No gene id file configured; gene_id falls back to the gene symbol.")
    else:
        report.gene_id_source = str(config.gene_id_file)
        mapped = symbols.map(gene_ids).astype("string")
    table = pd.DataFrame(
        {
            "perturbation_id": genetic["perturbation_id"].astype(str),
            "gene_id": mapped.fillna(symbols),
            "gene_symbol": symbols,
            "perturbation_type": genetic["Metadata_modality"],
            "cell_line": genetic["cell_line"],
            "timepoint": genetic["timepoint"].astype(float),
            "control_type": genetic["Metadata_control_type"],
            "replicate_count": genetic["Metadata_n_replicates"].astype(int),
            "replicate_cosine": genetic["Metadata_replicate_cosine"],
        }
    )
    unmapped = table["gene_symbol"].isna()
    if unmapped.any():
        report.warnings.append(f"{int(unmapped.sum())} genetic perturbation(s) have no gene symbol and were dropped.")
        table = table[~unmapped]
    report.n_genetic = len(table)
    report.n_with_mapped_gene_id = int(mapped.notna().sum())
    return table.astype(object).where(table.notna(), None).reset_index(drop=True)
