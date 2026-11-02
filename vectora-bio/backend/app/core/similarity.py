"""Signature similarity."""

from collections.abc import Mapping


def rank_similar(
    query: Mapping[str, float],
    library: Mapping[str, Mapping[str, float]],
    limit: int = 20,
) -> list[tuple[str, float]]:
    """Rank library signatures by similarity to the query.

    Returns pairs of library id and score, highest score first.
    """
    del query, library, limit
    raise NotImplementedError("Signature similarity ranking is not implemented.")
