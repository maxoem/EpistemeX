"""Extrinsic Information Retrieval (IR) evaluator."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from typing import Any

from episteme_pipeline.evaluation.extrinsic import (
    calculate_hits_at_k,
    calculate_mrr,
    calculate_ndcg,
)
from episteme_pipeline.protocols.graph_store import GraphReader


def default_deterministic_embedder(texts: list[str], dim: int = 128) -> list[list[float]]:
    """Generate deterministic normalized hash embeddings for offline evaluation.

    Parameters
    ----------
    texts : list of str
        Batch of input strings to embed.
    dim : int, optional
        Vector dimensionality (default: 128).

    Returns
    -------
    list of list of float
        Batch of L2-normalized dense embedding vectors.
    """
    embeddings: list[list[float]] = []
    for text in texts:
        if not text:
            embeddings.append([0.0] * dim)
            continue
        vec = [0.0] * dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            embeddings.append([0.0] * dim)
            continue
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h >> 7) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        embeddings.append(vec)
    return embeddings


class ExtrinsicRetrievalEvaluator:
    """Evaluates downstream knowledge graph utility via Information Retrieval metrics."""

    def __init__(
        self,
        graph_reader: GraphReader | None,
        embed_fn: Callable[[list[str]], Any] | None = None,
    ) -> None:
        """Initialize the extrinsic retrieval evaluator.

        Parameters
        ----------
        graph_reader : GraphReader, optional
            The protocol interface for executing queries against the graph store.
        embed_fn : Callable[[list[str]], Any], optional
            Function that takes query strings and returns vector embeddings.
            If None, a deterministic offline hash embedder is used.
        """
        self.graph_reader = graph_reader
        self.embed_fn = embed_fn or default_deterministic_embedder

    async def evaluate_query(
        self,
        query: str,
        gold_node_ids: set[str],
        top_k: int = 10,
        run_id: str | None = None,
    ) -> dict[str, float]:
        """Execute a query and calculate ranking metrics against gold standard IDs.

        Parameters
        ----------
        query : str
            Benchmark question or search query.
        gold_node_ids : set of str
            Ground-truth relevant identifiers.
        top_k : int, optional
            Maximum number of results to retrieve (default: 10).
        run_id : str | None, optional
            Optional run slice identifier to scope retrieval.

        Returns
        -------
        dict of str to float
            MRR, Hits@1, Hits@3, Hits@10, Hits@k, nDCG, and AP scores.
        """
        default_res = {
            "MRR": 0.0,
            "Hits@1": 0.0,
            "Hits@3": 0.0,
            "Hits@10": 0.0,
            f"Hits@{top_k}": 0.0,
            "nDCG": 0.0,
            "AP": 0.0,
        }
        if not gold_node_ids or self.graph_reader is None:
            return default_res

        # Embed query and search
        query_embedding = self.embed_fn([query])[0]
        results = await self.graph_reader.vector_search(
            embedding=query_embedding, top_k=top_k, run_id=run_id
        )

        retrieved_ids = [res.node_id for res in results]
        mrr = calculate_mrr([retrieved_ids], [gold_node_ids])
        hits_1 = calculate_hits_at_k([retrieved_ids], [gold_node_ids], k=1)
        hits_3 = calculate_hits_at_k([retrieved_ids], [gold_node_ids], k=3)
        hits_10 = calculate_hits_at_k([retrieved_ids], [gold_node_ids], k=10)
        hits_k = calculate_hits_at_k([retrieved_ids], [gold_node_ids], k=top_k)
        ndcg = calculate_ndcg([retrieved_ids], [{gid: 1.0 for gid in gold_node_ids}], k=top_k)
        ap = self._calculate_average_precision(retrieved_ids, gold_node_ids)

        return {
            "MRR": mrr,
            "Hits@1": hits_1,
            "Hits@3": hits_3,
            "Hits@10": hits_10,
            f"Hits@{top_k}": hits_k,
            "nDCG": ndcg,
            "AP": ap,
        }

    async def evaluate_batch(
        self,
        queries: list[dict[str, Any]],
        top_k: int = 10,
        run_id: str | None = None,
    ) -> dict[str, float]:
        """Execute a batch of competency queries and report macro-averaged IR metrics.

        Parameters
        ----------
        queries : list of dict of str to Any
            List of query descriptors containing 'query' and 'gold_target_ids'.
        top_k : int, optional
            Maximum retrieval cutoff (default: 10).
        run_id : str | None, optional
            Optional run slice scope.

        Returns
        -------
        dict of str to float
            Macro-averaged metrics: MRR, Hits@1, Hits@3, Hits@10, nDCG, AP.
        """
        if not queries:
            return {
                "MRR": 0.0,
                "Hits@1": 0.0,
                "Hits@3": 0.0,
                "Hits@10": 0.0,
                f"Hits@{top_k}": 0.0,
                "nDCG": 0.0,
                "AP": 0.0,
            }

        scores_acc: dict[str, float] = {
            "MRR": 0.0,
            "Hits@1": 0.0,
            "Hits@3": 0.0,
            "Hits@10": 0.0,
            f"Hits@{top_k}": 0.0,
            "nDCG": 0.0,
            "AP": 0.0,
        }

        for q in queries:
            q_text = str(q.get("query", ""))
            gold_ids = set(q.get("gold_target_ids", []))
            res = await self.evaluate_query(
                query=q_text,
                gold_node_ids=gold_ids,
                top_k=top_k,
                run_id=run_id,
            )
            for k in scores_acc:
                scores_acc[k] += res.get(k, 0.0)

        n = float(len(queries))
        return {k: v / n for k, v in scores_acc.items()}

    def _calculate_average_precision(self, retrieved: list[str], gold: set[str]) -> float:
        """Calculate Average Precision (AP) for a retrieved ranked list against gold IDs.

        Parameters
        ----------
        retrieved : list of str
            Ranked list of retrieved node IDs.
        gold : set of str
            Set of relevant gold standard node IDs.

        Returns
        -------
        float
            Average precision score in [0.0, 1.0].
        """
        num_relevant_found = 0
        sum_precisions = 0.0

        for i, doc_id in enumerate(retrieved):
            if doc_id in gold:
                num_relevant_found += 1
                precision_at_i = num_relevant_found / (i + 1)
                sum_precisions += precision_at_i

        return sum_precisions / len(gold) if len(gold) > 0 else 0.0
