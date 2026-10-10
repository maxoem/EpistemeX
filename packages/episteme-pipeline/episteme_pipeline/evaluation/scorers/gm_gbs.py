"""Graph BERTScore (GM-GBS) intrinsic evaluator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import networkx as nx
import numpy as np


class GraphBERTScoreEvaluator:
    """Computes Graph BERTScore (GM-GBS) between two directed graphs.

    This evaluator compares edges from a predicted graph against a gold
    standard graph by embedding the edge labels (relations) and computing
    cosine similarity.
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], np.ndarray],
        threshold: float = 0.95,
    ) -> None:
        """Initialize the GM-GBS evaluator.

        Parameters
        ----------
        embed_fn : Callable[[list[str]], np.ndarray]
            Function taking relation strings and returning 2D numpy embedding array.
        threshold : float, optional
            Cosine similarity threshold above which edges match (default: 0.95).
        """
        self.embed_fn = embed_fn
        self.threshold = threshold

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Calculate pairwise cosine similarity between two matrices of vectors."""
        a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
        b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
        return np.dot(a_norm, b_norm.T)

    def compute_matches(
        self, pred_graph: nx.DiGraph, gold_graph: nx.DiGraph
    ) -> tuple[float, list[tuple[Any, Any]], list[tuple[Any, Any]]]:
        """Compute the soft-matching score and matched edges.

        Parameters
        ----------
        pred_graph : nx.DiGraph
            Predicted graph.
        gold_graph : nx.DiGraph
            Gold ground-truth graph.

        Returns
        -------
        tuple of (float, list, list)
            Score, matched predicted edges, and matched gold edges.
        """
        pred_edges = list(pred_graph.edges(data="label"))
        gold_edges = list(gold_graph.edges(data="label"))

        if not pred_edges or not gold_edges:
            return 0.0, [], []

        # Extract labels
        pred_labels = [str(data) for _, _, data in pred_edges]
        gold_labels = [str(data) for _, _, data in gold_edges]

        # Embed labels
        pred_embeddings = self.embed_fn(pred_labels)
        gold_embeddings = self.embed_fn(gold_labels)

        # Compute similarity matrix
        sim_matrix = self._cosine_similarity(pred_embeddings, gold_embeddings)

        matched_pred = []
        matched_gold = []

        # Greedy matching
        for i, pred_edge in enumerate(pred_edges):
            best_match_idx = int(np.argmax(sim_matrix[i]))
            best_score = float(sim_matrix[i][best_match_idx])

            if best_score >= self.threshold:
                matched_pred.append(pred_edge)
                matched_gold.append(gold_edges[best_match_idx])

        score = len(matched_pred) / len(pred_edges) if pred_edges else 0.0
        return score, matched_pred, matched_gold
