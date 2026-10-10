"""Optimal Edit Path (OEP) evaluator diagnosing hallucination and omission rates."""

from __future__ import annotations

from typing import Any

import networkx as nx


class OptimalEditPathEvaluator:
    """Computes Optimal Edit Paths (OEP) to calculate hallucination and omission rates."""

    @staticmethod
    def compute_rates(
        pred_graph: nx.DiGraph,
        gold_graph: nx.DiGraph,
        matched_pred_edges: list[Any],
        matched_gold_edges: list[Any],
    ) -> tuple[float, float]:
        """Calculate Hallucination Rate and Omission Rate based on edge matches.

        Parameters
        ----------
        pred_graph : nx.DiGraph
            The predicted knowledge graph.
        gold_graph : nx.DiGraph
            The ground-truth knowledge graph.
        matched_pred_edges : list
            List of edges from the predicted graph that found a semantic match in the gold graph.
        matched_gold_edges : list
            List of edges from the gold graph that were matched.

        Returns
        -------
        tuple of (float, float)
            - hallucination_rate: % of predicted edges without a match.
            - omission_rate: % of gold edges that were not matched.
        """
        num_pred_edges = pred_graph.number_of_edges()
        num_gold_edges = gold_graph.number_of_edges()

        if num_pred_edges == 0:
            hallucination_rate = 0.0
        else:
            hallucinated_edges = num_pred_edges - len(matched_pred_edges)
            hallucination_rate = hallucinated_edges / num_pred_edges

        if num_gold_edges == 0:
            omission_rate = 0.0
        else:
            unique_matched_gold = len(set(matched_gold_edges))
            omitted_edges = num_gold_edges - unique_matched_gold
            omission_rate = omitted_edges / num_gold_edges

        return hallucination_rate, omission_rate
