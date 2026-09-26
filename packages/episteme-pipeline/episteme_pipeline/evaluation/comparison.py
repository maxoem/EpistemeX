"""Comparison scaffolding for evaluating multiple runs against each other.

As described in docs/evaluation/methodology.md section 11, the pipeline
should evaluate not only whether a method works, but whether it works
better than alternatives. This module provides the scaffolding for
comparative evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ComparisonAxis(StrEnum):
    METHOD = "method"
    PROMPT = "prompt"
    SCHEMA = "schema"
    CHUNKING = "chunking"
    THRESHOLD = "threshold"
    CLUSTERING = "clustering"


class RunComparison(BaseModel):
    """Side-by-side metrics for two runs on the same dataset."""

    run_id_a: str
    run_id_b: str
    metric_name: str
    value_a: float
    value_b: float
    axis: ComparisonAxis = ComparisonAxis.METHOD
    delta: float = 0.0
    winner: str | None = None  # "a", "b", or None = tie


class EvaluationComparison(BaseModel):
    """A comparative evaluation across multiple runs and metrics.

    Each comparison references the runs being compared, the dataset
    used, and the set of metrics that were compared.
    """

    comparison_id: str
    run_ids: list[str]
    axis: ComparisonAxis
    dataset_ref: str | None = None
    dataset_type: str | None = None
    schema_version: str | None = None
    pipeline_version: str | None = None
    pairwise_comparisons: list[RunComparison] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)


def is_higher_better(metric_name: str) -> bool:
    """Determine whether higher metric values indicate superior performance.

    Parameters
    ----------
    metric_name : str
        Name of the metric being compared.

    Returns
    -------
    bool
        True if higher is better, False if lower is better.
    """
    lower_better_tokens = (
        "cost",
        "token",
        "latency",
        "duration",
        "time",
        "omission_rate",
        "hallucination_rate",
        "error",
        "aor",
    )
    name_lower = metric_name.lower()
    return not any(tok in name_lower for tok in lower_better_tokens)


def compute_run_comparisons(
    run_id_a: str,
    run_id_b: str,
    metrics_a: dict[str, float],
    metrics_b: dict[str, float],
    axis: ComparisonAxis = ComparisonAxis.METHOD,
    higher_is_better_overrides: dict[str, bool] | None = None,
) -> list[RunComparison]:
    """Compute pairwise metric comparisons and deltas between two runs.

    Parameters
    ----------
    run_id_a : str
        Identifier of run A (typically the baseline run).
    run_id_b : str
        Identifier of run B (typically the pipeline run).
    metrics_a : dict of str to float
        Metrics dictionary for run A.
    metrics_b : dict of str to float
        Metrics dictionary for run B.
    axis : ComparisonAxis, optional
        Comparison axis classification (default: ComparisonAxis.METHOD).
    higher_is_better_overrides : dict of str to bool, optional
        Explicit directional overrides for specific metric names.

    Returns
    -------
    list of RunComparison
        List of computed pairwise comparisons with deltas and winners.
    """
    overrides = higher_is_better_overrides or {}
    shared_metrics = set(metrics_a.keys()) | set(metrics_b.keys())

    comparisons: list[RunComparison] = []
    for metric_name in sorted(shared_metrics):
        val_a = float(metrics_a.get(metric_name, 0.0))
        val_b = float(metrics_b.get(metric_name, 0.0))
        delta = round(val_b - val_a, 4)

        higher_better = overrides.get(metric_name, is_higher_better(metric_name))
        winner: str | None = None
        if val_a != val_b:
            if higher_better:
                winner = "b" if val_b > val_a else "a"
            else:
                winner = "b" if val_b < val_a else "a"

        comparisons.append(
            RunComparison(
                run_id_a=run_id_a,
                run_id_b=run_id_b,
                metric_name=metric_name,
                value_a=val_a,
                value_b=val_b,
                axis=axis,
                delta=delta,
                winner=winner,
            )
        )

    return comparisons


def format_comparison_markdown(
    comparisons: list[RunComparison],
    title: str = "Comparative Evaluation",
    name_a: str = "Baseline",
    name_b: str = "Pipeline",
) -> str:
    """Format pairwise comparisons into a structured markdown report table.

    Parameters
    ----------
    comparisons : list of RunComparison
        Pairwise comparisons between baseline and candidate runs.
    title : str, optional
        Section header title for the markdown summary (default: "Comparative Evaluation").
    name_a : str, optional
        Human-readable label for run A (default: "Baseline").
    name_b : str, optional
        Human-readable label for run B (default: "Pipeline").

    Returns
    -------
    str
        Markdown formatted text table.
    """
    if not comparisons:
        return ""

    lines = [
        f"### {title}\n",
        f"| Metric | {name_a} (`{comparisons[0].run_id_a}`) | {name_b} (`{comparisons[0].run_id_b}`) | Delta | Winner |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in comparisons:
        sign = "+" if c.delta > 0 else ""
        delta_str = f"{sign}{c.delta:.4f}"
        winner_label = name_b if c.winner == "b" else (name_a if c.winner == "a" else "Tie")
        lines.append(
            f"| `{c.metric_name}` | {c.value_a:.4f} | {c.value_b:.4f} | {delta_str} | {winner_label} |"
        )

    return "\n".join(lines)
