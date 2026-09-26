"""Open-IE / flat entity-relation graph baseline.

Implements BaselineNaiveKG for ISSUE-033, evaluating flat entity discovery
and relation extraction via ExtractionStrategy without hierarchical theory layers.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

import networkx as nx

from episteme_pipeline.contracts.domain import L1Chunk, L2Entity, L2Triple
from episteme_pipeline.evaluation.benchmarks.scierc import load_scierc_subset
from episteme_pipeline.evaluation.benchmarks.structuralist import load_structuralist_benchmark
from episteme_pipeline.evaluation.models import EvaluationMetric, EvaluationResult
from episteme_pipeline.evaluation.scorers.domain_bridge import l2_triples_to_digraph
from episteme_pipeline.evaluation.strategies import ExtractionStrategy
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

logger = logging.getLogger(__name__)


class BaselineNaiveKG:
    """Open-IE flat entity-relation graph baseline dynamically driven by SchemaConfig.

    Parameters
    ----------
    schema : SchemaConfig, optional
        Schema defining canonical node types, relation types, and polarities.
    extraction_strategy : ExtractionStrategy, optional
        Underlying evaluation strategy for Layer 2 entities and triples.
    extractor_fn : Callable[[str], tuple[list[L2Entity], list[L2Triple]]], optional
        Optional custom or LLM extraction function. If None, a deterministic
        schema-guided Open-IE parser is used.
    """

    def __init__(
        self,
        schema: SchemaConfig | None = None,
        extraction_strategy: ExtractionStrategy | None = None,
        extractor_fn: Callable[[str], tuple[list[L2Entity], list[L2Triple]]] | None = None,
    ) -> None:
        self.schema = schema or DEFAULT_SCHEMA
        self.extraction_strategy = extraction_strategy or ExtractionStrategy(schema=self.schema)
        self.extractor_fn = extractor_fn

    def _extract_from_text(self, text: str) -> tuple[list[L2Entity], list[L2Triple]]:
        """Perform schema-guided Open-IE triple extraction on raw string text.

        Parameters
        ----------
        text : str
            Input scientific passage or sentence.

        Returns
        -------
        tuple of (list of L2Entity, list of L2Triple)
            Extracted entities and directed relational triples.
        """
        if self.extractor_fn is not None:
            return self.extractor_fn(text)

        entities: dict[str, L2Entity] = {}
        triples: list[L2Triple] = []

        # Canonical relations directly from the injected schema
        candidate_relations = list(self.schema.relation_types) + list(self.schema.argument_relation_types)

        # Split text into sentences/clauses
        clauses = re.split(r"[.;\n]+", text)
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            for rel in candidate_relations:
                # Direct case-insensitive search for canonical schema relation phrases
                # (handling underscores as spaces, e.g. "PART_OF" -> "part of", "SUPPORTS" -> "supports")
                rel_phrase = rel.lower().replace("_", " ")
                pattern = rf"\b{re.escape(rel_phrase)}(?:s|ed|ing)?\b"
                match = re.search(pattern, clause, re.IGNORECASE)
                if match:
                    subj_text = clause[:match.start()].strip()
                    obj_text = clause[match.end():].strip()

                    # Clean candidate subject and object spans
                    subj_cleaned = re.sub(r"^(?:the|a|an|where)\s+", "", subj_text, flags=re.IGNORECASE).strip()
                    obj_cleaned = re.sub(r"^(?:the|a|an)\s+", "", obj_text, flags=re.IGNORECASE).strip()

                    # Restrict span lengths to plausible entity phrases
                    if 2 <= len(subj_cleaned) <= 60 and 2 <= len(obj_cleaned) <= 60:
                        s_id = re.sub(r"\W+", "_", subj_cleaned.lower()).strip("_")
                        o_id = re.sub(r"\W+", "_", obj_cleaned.lower()).strip("_")

                        if s_id and o_id and s_id != o_id:
                            if s_id not in entities:
                                entities[s_id] = L2Entity(
                                    id=s_id,
                                    name=subj_cleaned,
                                    label="Entity",
                                )
                            if o_id not in entities:
                                entities[o_id] = L2Entity(
                                    id=o_id,
                                    name=obj_cleaned,
                                    label="Entity",
                                )

                            triples.append(
                                L2Triple(
                                    subject_id=s_id,
                                    predicate=rel,
                                    object_id=o_id,
                                    confidence=0.85,
                                    scope="local",
                                )
                            )

        return list(entities.values()), triples

    def extract(
        self,
        text_or_chunks: str | list[str] | list[L1Chunk],
    ) -> tuple[list[L2Entity], list[L2Triple]]:
        """Extract flat entities and relation triples from text inputs or chunks.

        Parameters
        ----------
        text_or_chunks : str, list of str, or list of L1Chunk
            Input texts or chunks to process.

        Returns
        -------
        tuple of (list of L2Entity, list of L2Triple)
            Aggregated entities and triples.
        """
        all_entities: dict[str, L2Entity] = {}
        all_triples: list[L2Triple] = []

        inputs: list[str] = []
        if isinstance(text_or_chunks, str):
            inputs = [text_or_chunks]
        elif isinstance(text_or_chunks, list):
            for item in text_or_chunks:
                if isinstance(item, L1Chunk):
                    inputs.append(item.text)
                elif isinstance(item, str):
                    inputs.append(item)

        for text in inputs:
            ents, trips = self._extract_from_text(text)
            for e in ents:
                if e.id not in all_entities:
                    all_entities[e.id] = e
            all_triples.extend(trips)

        return list(all_entities.values()), all_triples

    def build_graph(
        self,
        text_or_chunks: str | list[str] | list[L1Chunk],
    ) -> nx.DiGraph:
        """Construct a NetworkX DiGraph directly from Open-IE extractions.

        Parameters
        ----------
        text_or_chunks : str, list of str, or list of L1Chunk
            Input raw passages.

        Returns
        -------
        nx.DiGraph
            Directed graph containing extracted entity nodes and relational edges.
        """
        entities, triples = self.extract(text_or_chunks)
        graph = l2_triples_to_digraph(entities, triples)
        for u, v, data in graph.edges(data=True):
            lbl = str(data.get("label", data.get("relation", "")))
            data["polarity"] = self.schema.relation_polarities.get(lbl, self.schema.relation_polarities.get(lbl.upper(), 0))
        return graph

    async def evaluate(
        self,
        predicted: Any,
        gold: Any,
        run_id: str = "baseline_naive_kg",
        context: dict[str, Any] | None = None,
    ) -> list[EvaluationResult]:
        """Evaluate predicted entities and relation triples against gold standard.

        Parameters
        ----------
        predicted : Any
            Predicted entities/triples, DiGraph, or ArtifactCollection.
        gold : Any
            Gold standard annotations, dataset file path, or DiGraph.
        run_id : str, optional
            Evaluation run identifier (default: "baseline_naive_kg").
        context : dict of str to Any, optional
            Evaluation context parameters forwarded to ExtractionStrategy.

        Returns
        -------
        list of EvaluationResult
            Evaluation results containing F1, precision, recall, and error rates.
        """
        ctx = dict(context or {})
        ctx.setdefault("phase_name", "Baseline: Naive Open-IE KG")
        ctx.setdefault("schema", self.schema)
        return await self.extraction_strategy.evaluate(
            predicted=predicted,
            gold=gold,
            run_id=run_id,
            context=ctx,
        )

    async def run_and_evaluate(
        self,
        corpus: list[L1Chunk] | list[str] | str | Path,
        gold: Any,
        run_id: str = "baseline_naive_kg",
        context: dict[str, Any] | None = None,
    ) -> tuple[list[EvaluationResult], dict[str, Any]]:
        """Extract flat Open-IE KG and evaluate directly against gold benchmark.

        Parameters
        ----------
        corpus : list of L1Chunk, list of str, str, or Path
            Input text corpus or file path.
        gold : Any
            Gold standard reference graph, SciERC path, or STNB path.
        run_id : str, optional
            Identifier for this baseline run (default: "baseline_naive_kg").
        context : dict of str to Any, optional
            Evaluation context settings.

        Returns
        -------
        tuple of (list of EvaluationResult, dict)
            List of evaluated results and execution metadata (latency, token_cost).
        """
        start_time = time.perf_counter()

        # 1. Resolve corpus texts/chunks
        items: list[L1Chunk] | list[str] = []
        if isinstance(corpus, (str, Path)) and Path(corpus).is_file():
            path_str = str(corpus)
            if path_str.endswith(".jsonld"):
                chunks, _ = load_structuralist_benchmark(path_str)
                items = chunks
            elif path_str.endswith(".json"):
                scierc_data = load_scierc_subset(path_str)
                items = scierc_data.get("texts", [])
            else:
                with open(corpus, "r", encoding="utf-8") as f:
                    items = [f.read()]
        elif isinstance(corpus, list):
            items = corpus
        elif isinstance(corpus, str):
            items = [corpus]

        # 2. Extract Open-IE flat graph
        entities, triples = self.extract(items)
        graph = l2_triples_to_digraph(entities, triples)

        # 3. Evaluate via ExtractionStrategy
        results = await self.evaluate(
            predicted=graph,
            gold=gold,
            run_id=run_id,
            context=context,
        )

        latency = time.perf_counter() - start_time
        token_cost = 0.0  # Heuristic rule-based extraction has zero API token cost

        # Inject latency and token_cost metrics into the primary result
        if results:
            results[0].metrics.extend([
                EvaluationMetric(name="latency", value=round(latency, 4), unit="seconds"),
                EvaluationMetric(name="token_cost", value=token_cost, unit="USD"),
            ])

        metadata = {
            "latency": latency,
            "token_cost": token_cost,
            "entity_count": len(entities),
            "triple_count": len(triples),
        }
        return results, metadata
