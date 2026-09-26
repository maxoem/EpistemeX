"""Comparative baseline runners for the Episteme evaluation subsystem.

Provides standard baselines (Text RAG, Naive Open-IE KG, Zero-Shot LLM)
for rigorous comparative evaluation across pipeline layers.
"""

from __future__ import annotations

from episteme_pipeline.evaluation.baselines.naive_kg import BaselineNaiveKG
from episteme_pipeline.evaluation.baselines.text_rag import BaselineTextRAG
from episteme_pipeline.evaluation.baselines.zero_shot import BaselineZeroShotLLM

__all__ = [
    "BaselineTextRAG",
    "BaselineNaiveKG",
    "BaselineZeroShotLLM",
]
