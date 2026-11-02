"""Benchmark evaluation."""


def run_evaluation(task: str) -> list[tuple[str, float]]:
    """Compute named metrics for a benchmark task.

    Returns pairs of metric name and value.
    """
    raise NotImplementedError(f"Evaluation for '{task}' is not implemented.")
