"""Synthetic profile tables for tests.

The geometry is arbitrary and labels are placeholders ("class_x", "GENE1"); none of it
represents real biology.
"""

import numpy as np
import pandas as pd

N_FEATURES = 12
FEATURES = [f"feat_{i:03d}" for i in range(N_FEATURES)]
CELL_LINE = "CELL_A"
COMPOUND_TIMEPOINT = 48.0
GENETIC_TIMEPOINT = 96.0


def basis(index: int, sign: float = 1.0) -> np.ndarray:
    vector = np.zeros(N_FEATURES)
    vector[index] = sign * 1.0
    return vector


def profile_table(
    centers: dict[str, np.ndarray],
    profile_type: str,
    *,
    cell_line: str = CELL_LINE,
    timepoint: float = COMPOUND_TIMEPOINT,
    n_replicates: int = 3,
    noise: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for perturbation_id, center in centers.items():
        for replicate in range(n_replicates):
            values = center + rng.normal(0, noise, N_FEATURES)
            rows.append(
                {
                    "profile_id": f"{perturbation_id}:{cell_line}:{timepoint:g}:r{replicate}",
                    "perturbation_id": perturbation_id,
                    "profile_type": profile_type,
                    "cell_line": cell_line,
                    "timepoint": timepoint,
                    "Metadata_Well": f"W{replicate:02d}",
                    **dict(zip(FEATURES, values, strict=True)),
                }
            )
    return pd.DataFrame(rows)


COMPOUND_CENTERS = {
    "CMPD_A1": basis(0) + 0.2 * basis(5),
    "CMPD_A2": basis(0) + 0.1 * basis(6),
    "CMPD_A3": basis(0) - 0.1 * basis(7),
    "CMPD_B1": basis(1),
    "CMPD_B2": basis(1) + 0.1 * basis(8),
    "CMPD_C": basis(2, -1.0),
    "CMPD_D": basis(3),
}

GENETIC_CENTERS = {
    "GUIDE_G1_1": basis(0),
    "GUIDE_G1_2": basis(0) + 0.2 * basis(9),
    "ORF_G2": basis(1, -1.0),
    "GUIDE_G3": basis(2),
}

GENETIC_METADATA = pd.DataFrame(
    [
        ("GUIDE_G1_1", 1001, "GENE1", "crispr"),
        ("GUIDE_G1_2", 1001, "GENE1", "crispr"),
        ("ORF_G2", 1002, "GENE2", "orf"),
        ("GUIDE_G3", 1003, "GENE3", "crispr"),
    ],
    columns=["perturbation_id", "gene_id", "gene_symbol", "perturbation_type"],
).assign(cell_line=CELL_LINE, timepoint=GENETIC_TIMEPOINT)

COMPOUND_METADATA = pd.DataFrame(
    [
        ("CMPD_A1", "compound a1", "class_x", "GENE1"),
        ("CMPD_A2", "compound a2", "class_x", None),
        ("CMPD_A3", "compound a3", "class_x|class_z", None),
        ("CMPD_B1", "compound b1", "class_y", None),
        ("CMPD_B2", "compound b2", "class_y", None),
        ("CMPD_C", "compound c", None, None),
        ("CMPD_D", "compound d", None, None),
    ],
    columns=["compound_id", "compound_name", "moa", "known_target"],
).assign(cell_line=CELL_LINE, timepoint=COMPOUND_TIMEPOINT)


def compound_profiles(**kwargs) -> pd.DataFrame:
    return profile_table(COMPOUND_CENTERS, "compound", **kwargs)


def genetic_profiles(**kwargs) -> pd.DataFrame:
    kwargs.setdefault("timepoint", GENETIC_TIMEPOINT)
    kwargs.setdefault("seed", 1)
    return profile_table(GENETIC_CENTERS, "genetic", **kwargs)


def control_profiles(timepoint: float, seed: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    centers = {f"CTRL_{timepoint:g}_{i}": rng.normal(0, 0.02, N_FEATURES) for i in range(4)}
    return profile_table(centers, "control", timepoint=timepoint, n_replicates=2, noise=0.01, seed=seed)
