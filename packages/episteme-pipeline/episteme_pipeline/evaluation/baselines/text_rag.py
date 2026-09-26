"""Flat Text RAG baseline evaluating dense vector search over raw text chunks.

Implements BaselineTextRAG for ISSUE-033, evaluating retrieval utility of raw
L1Chunks indexed in InMemoryGraphStore without graph structure.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from episteme_pipeline.contracts.domain import L1Chunk
from episteme_pipeline.evaluation.benchmarks.structuralist import load_structuralist_benchmark
from episteme_pipeline.evaluation.models import (
    DatasetType,
    EvaluationLevel,
    EvaluationMetric,
    EvaluationOutcome,
    EvaluationResult,
)
from episteme_pipeline.evaluation.scorers.retrieval import ExtrinsicRetrievalEvaluator
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore

logger = logging.getLogger(__name__)


class BaselineTextRAG:
    """Evaluates flat vector search over raw L1Chunks without graph structure.

    Parameters
    ----------
    graph_store : InMemoryGraphStore, optional
        In-memory graph store holding chunk vectors and raw texts. If None,
        a fresh instance is created.
    retrieval_evaluator : ExtrinsicRetrievalEvaluator, optional
        Evaluator computing extrinsic ranking metrics (MRR, Hits@k, nDCG).
    embed_fn : Callable[[list[str]], Any], optional
        Vector embedding function applied to queries and passages.
    """

    def __init__(
        self,
        graph_store: InMemoryGraphStore | None = None,
        retrieval_evaluator: ExtrinsicRetrievalEvaluator | None = None,
        embed_fn: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self.graph_store = graph_store or InMemoryGraphStore()
        self.embed_fn = embed_fn
        self.retrieval_evaluator = retrieval_evaluator or ExtrinsicRetrievalEvaluator(
            graph_reader=self.graph_store,
            embed_fn=self.embed_fn,
        )

    def index_chunks(
        self,
        chunks: list[L1Chunk],
        run_id: str = "baseline_text_rag",
    ) -> int:
        """Index raw L1Chunks into in-memory store for vector search.

        Parameters
        ----------
        chunks : list of L1Chunk
            List of raw text chunks to index without graph entities or relations.
        run_id : str, optional
            Run slice identifier (default: "baseline_text_rag").

        Returns
        -------
        int
            Number of indexed text chunks.
        """
        return self.graph_store.index_for_search(chunks, run_id=run_id)

    async def evaluate_queries(
        self,
        queries: list[dict[str, Any]],
        chunks: list[L1Chunk] | None = None,
        top_k: int = 10,
        run_id: str = "baseline_text_rag",
    ) -> dict[str, float]:
        """Evaluate competency queries against indexed text chunks.

        If chunks are provided with anchor annotations (e.g., from STNB),
        target IDs are adapted to ensure both chunk identifiers and anchored
        formal node identifiers are matched.

        Parameters
        ----------
        queries : list of dict of str to Any
            Competency queries containing 'query' and 'gold_target_ids'.
        chunks : list of L1Chunk, optional
            Chunks used to resolve anchor-to-node provenance mappings.
        top_k : int, optional
            Cutoff ranking depth for IR metrics (default: 10).
        run_id : str, optional
            Run slice identifier (default: "baseline_text_rag").

        Returns
        -------
        dict of str to float
            Aggregated retrieval metrics (MRR, Hits@1, Hits@3, Hits@10, nDCG, AP).
        """
        adapted_queries: list[dict[str, Any]] = []

        # Build bidirectional mapping between chunk_id and anchored_node_id
        chunk_to_node: dict[str, str] = {}
        node_to_chunk: dict[str, str] = {}
        if chunks:
            for c in chunks:
                anchored_node = c.metadata.get("anchored_node_id") if c.metadata else None
                if anchored_node:
                    chunk_to_node[c.id] = str(anchored_node)
                    node_to_chunk[str(anchored_node)] = c.id

        for q in queries:
            raw_targets = set(q.get("gold_target_ids", []))
            expanded_targets = set(raw_targets)

            for target in raw_targets:
                if target in node_to_chunk:
                    expanded_targets.add(node_to_chunk[target])
                if target in chunk_to_node:
                    expanded_targets.add(chunk_to_node[target])

            adapted_queries.append({
                "query": q["query"],
                "gold_target_ids": list(expanded_targets),
                "id": q.get("id"),
            })

        return await self.retrieval_evaluator.evaluate_batch(
            adapted_queries,
            top_k=top_k,
            run_id=run_id,
        )

    async def run_and_evaluate(
        self,
        corpus: list[L1Chunk] | str | Path,
        queries: list[dict[str, Any]] | str | Path,
        run_id: str = "baseline_text_rag",
        top_k: int = 10,
    ) -> tuple[EvaluationResult, dict[str, Any]]:
        """Execute flat vector search baseline and compute evaluation result.

        Parameters
        ----------
        corpus : list of L1Chunk, str, or Path
            Input text chunks or path to STNB JSON-LD file.
        queries : list of dict, str, or Path
            Queries list or path to queries YAML file.
        run_id : str, optional
            Identifier for this baseline run (default: "baseline_text_rag").
        top_k : int, optional
            Maximum retrieval cutoff (default: 10).

        Returns
        -------
        tuple of (EvaluationResult, dict)
            Result model containing IR metrics and metadata dictionary with
            latency and token costs.
        """
        start_time = time.perf_counter()

        # 1. Resolve chunks
        chunks: list[L1Chunk] = []
        dataset_ref = "in_memory_corpus"
        if isinstance(corpus, (str, Path)) and Path(corpus).is_file():
            dataset_ref = str(corpus)
            if str(corpus).endswith(".jsonld") or str(corpus).endswith(".json"):
                chunks, _ = load_structuralist_benchmark(corpus)
            else:
                with open(corpus, "r", encoding="utf-8") as f:
                    text = f.read()
                chunks = [
                    L1Chunk(
                        id="chunk_0",
                        text=text,
                        source_doc_id=str(corpus),
                        sequence_index=0,
                        token_count=len(text.split()),
                    )
                ]
        elif isinstance(corpus, list):
            chunks = corpus

        # 2. Resolve queries
        query_list: list[dict[str, Any]] = []
        queries_ref = "in_memory_queries"
        if isinstance(queries, (str, Path)) and Path(queries).is_file():
            queries_ref = str(queries)
            with open(queries, "r", encoding="utf-8") as qf:
                qdata = yaml.safe_load(qf)
            query_list = qdata.get("queries", [])
        elif isinstance(queries, list):
            query_list = queries

        # 3. Index raw chunks only (no graph structure)
        self.index_chunks(chunks, run_id=run_id)

        # 4. Evaluate queries
        metrics_dict = await self.evaluate_queries(
            query_list,
            chunks=chunks,
            top_k=top_k,
            run_id=run_id,
        )

        latency = time.perf_counter() - start_time
        token_cost = 0.0  # Offline deterministic embedder has zero API token cost

        mrr_val = metrics_dict.get("MRR", 0.0)
        outcome = EvaluationOutcome.PASS if mrr_val > 0.0 else EvaluationOutcome.WARNING

        result = EvaluationResult(
            run_id=run_id,
            evaluation_level=EvaluationLevel.DOWNSTREAM,
            phase_name="Baseline: Flat Text RAG",
            dataset_ref=dataset_ref,
            dataset_type=DatasetType.GOLD,
            metrics=[
                EvaluationMetric(name="mrr", value=mrr_val),
                EvaluationMetric(name="hits@1", value=metrics_dict.get("Hits@1", 0.0)),
                EvaluationMetric(name="hits@3", value=metrics_dict.get("Hits@3", 0.0)),
                EvaluationMetric(name="hits@10", value=metrics_dict.get("Hits@10", 0.0)),
                EvaluationMetric(name="ndcg", value=metrics_dict.get("nDCG", 0.0)),
                EvaluationMetric(name="latency", value=round(latency, 4), unit="seconds"),
                EvaluationMetric(name="token_cost", value=token_cost, unit="USD"),
            ],
            outcome=outcome,
            notes={
                "category": "baseline_text_rag",
                "queries_ref": queries_ref,
                "latency_seconds": str(round(latency, 4)),
                "token_cost": str(token_cost),
                "markdown_report": (
                    "### Baseline Text RAG Evaluation Report\n\n"
                    f"- **MRR:** {mrr_val:.4f}\n"
                    f"- **Hits@1:** {metrics_dict.get('Hits@1', 0.0):.4f}\n"
                    f"- **Hits@3:** {metrics_dict.get('Hits@3', 0.0):.4f}\n"
                    f"- **Hits@10:** {metrics_dict.get('Hits@10', 0.0):.4f}\n"
                    f"- **nDCG:** {metrics_dict.get('nDCG', 0.0):.4f}\n"
                    f"- **Latency:** {latency:.4f}s\n"
                    f"- **Token Cost:** ${token_cost:.4f}\n"
                ),
            },
        )

        metadata = {
            "latency": latency,
            "token_cost": token_cost,
            "metrics": metrics_dict,
        }
        return result, metadata
