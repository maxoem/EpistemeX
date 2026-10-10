"""Benchmark dataset loaders and format adapters for Episteme evaluation."""

from __future__ import annotations

from episteme_pipeline.evaluation.benchmarks.arg_microtexts import load_arg_microtexts_subset
from episteme_pipeline.evaluation.benchmarks.baseline import export_baseline, load_gold_standard
from episteme_pipeline.evaluation.benchmarks.neo4j_to_epistemetrics import export_neo4j_to_theory_graph
from episteme_pipeline.evaluation.benchmarks.scierc import load_scierc_subset
from episteme_pipeline.evaluation.benchmarks.scifact import load_scifact_subset
from episteme_pipeline.evaluation.benchmarks.structuralist import (
    load_structuralist_benchmark,
    load_structuralist_theory_graph,
    structuralist_digraph_to_theory_graph,
)

__all__ = [
    "load_structuralist_benchmark",
    "load_structuralist_theory_graph",
    "structuralist_digraph_to_theory_graph",
    "load_scierc_subset",
    "load_arg_microtexts_subset",
    "load_scifact_subset",
    "export_baseline",
    "load_gold_standard",
    "export_neo4j_to_theory_graph",
]
