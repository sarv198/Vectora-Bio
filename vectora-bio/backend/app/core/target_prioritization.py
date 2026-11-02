"""Target ranking from a gene signature."""

from collections.abc import Mapping


def prioritize_targets(
    signature: Mapping[str, float],
    limit: int = 50,
) -> list[tuple[str, float]]:
    """Rank genes by how strongly the signature implicates them.

    Returns pairs of gene symbol and score, highest score first.
    """
    del signature, limit
    raise NotImplementedError("Target prioritization is not implemented.")
