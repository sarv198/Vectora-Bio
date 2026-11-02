"""Signature cleanup before analysis."""

import math
from collections.abc import Mapping


def standardize_signature(values: Mapping[str, float]) -> dict[str, float]:
    """Trim gene symbols and drop blank or non-finite entries.

    When a symbol appears more than once, the last finite value is kept.
    """
    cleaned: dict[str, float] = {}
    for gene, value in values.items():
        symbol = str(gene).strip()
        if not symbol or value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        cleaned[symbol] = number
    return cleaned
