"""Transcriptional reversal scoring."""

from collections.abc import Mapping


def score_reversal(
    query: Mapping[str, float],
    reference: Mapping[str, float],
) -> float:
    """Score how completely the query signature reverses the reference."""
    del query, reference
    raise NotImplementedError("Signature reversal scoring is not implemented.")
