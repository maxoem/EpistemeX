"""Alias and backward-compatibility bridge for ExtrinsicRetrievalEvaluator."""

from __future__ import annotations

from episteme_pipeline.evaluation.scorers.retrieval import (
    ExtrinsicRetrievalEvaluator,
    default_deterministic_embedder,
)

__all__ = [
    "ExtrinsicRetrievalEvaluator",
    "default_deterministic_embedder",
]
