"""Mechanism-of-action inference."""

from collections.abc import Mapping


def infer_moa(
    signature: Mapping[str, float],
    limit: int = 10,
) -> list[tuple[str, float]]:
    """Assign mechanism labels to a signature.

    Returns pairs of label and score, highest score first.
    """
    del signature, limit
    raise NotImplementedError("Mechanism inference is not implemented.")
