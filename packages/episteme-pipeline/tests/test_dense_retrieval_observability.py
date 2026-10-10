from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from typing import Iterator

import pytest

from episteme_pipeline.config import Phase3Config
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, SearchResult, SubGraph
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
    make_reduce_depth_overflow_handler,
)
from episteme_pipeline.phases.phase3_global_relations.models import GlobalRelationOutput
from episteme_pipeline.schema.default_schema import SchemaConfig


class FakeSpan:
    """Collects span updates for assertions.

    Parameters
    ----------
    name
        Span name.
    input
        Structured span input.
    spans
        Shared list receiving span records.
    """

    def __init__(
        self,
        name: str,
        input: dict[str, object] | None,
        spans: list[dict[str, object]],
    ) -> None:
        """Initialize the fake span."""
        self.record: dict[str, object] = {"name": name, "input": input}
        spans.append(self.record)

    def update(self, **kwargs: object) -> None:
        """Record span updates."""
        self.record.update(kwargs)


class FakeTraceSink:
    """Trace sink that records enabled spans."""

    def __init__(self) -> None:
        """Initialize the fake trace sink."""
        self.spans: list[dict[str, object]] = []

    @contextmanager
    def span(
        self,
        *,
        name: str,
        input: dict[str, object] | None = None,
        enabled: bool = True,
    ) -> Iterator[FakeSpan | _DisabledSpan]:
        """Record enabled spans and no-op disabled spans.

        Parameters
        ----------
        name
            Span name.
        input
            Structured span input.
        enabled
            Whether the span should be recorded.

        Yields
        ------
        FakeSpan | _DisabledSpan
            Recorded span when enabled, otherwise a no-op span.
        """
        if not enabled:
            yield _DisabledSpan()
            return
        yield FakeSpan(name=name, input=input, spans=self.spans)


class FakeEmbedModel:
    """Embedding model with deterministic two-dimensional vectors."""

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic embeddings for input texts.

        Parameters
        ----------
        texts
            Texts to embed.

        Returns
        -------
        list[list[float]]
            Embeddings aligned with ``texts``.
        """
        return [[1.0, 0.0], [0.8, 0.6]]


class FakeReranker:
    """Relation reranker with a fixed score."""

    async def score_relation(self, *args: Any, **kwargs: Any) -> float:
        """Return a score above the configured threshold.

        Returns
        -------
        float
            Fixed reranker score.
        """
        return 0.9


class FakeLLM:
    """LLM that returns a valid global relation."""

    async def astructured_predict(self, model_class, prompt, **kwargs):
        """Return a deterministic relation extraction result.

        Parameters
        ----------
        model_class
            Structured output class requested by the caller.
        prompt
            Prompt template provided by the extractor.
        **kwargs
            Prompt variables.

        Returns
        -------
        GlobalRelationOutput
            Valid relation output.
        """
        return GlobalRelationOutput(
            relation="IMPLIES",
            confidence=0.8,
            direction="A_to_B",
        )


class RecordingGraphStore:
    """Graph store test double that records requested neighborhood depths."""

    def __init__(self) -> None:
        """Initialize depth recording state."""
        self.depth_calls: list[tuple[str, int]] = []

    async def get_neighborhood(self, node_id: str, depth: int = 1) -> SubGraph:
        """Return a synthetic subgraph with depth-dependent text volume."""
        self.depth_calls.append((node_id, depth))
        node = L2Entity(
            id=f"{node_id}_neighbor",
            label="KONZEPT",
            name=f"{node_id} detail",
            description="context " * max(depth, 1),
        )
        triple = L2Triple(
            subject_id=node_id,
            predicate="REL",
            object_id=node.id,
            confidence=1.0,
            scope="local",
            source_chunk_id="global",
        )
        return SubGraph(
            center_id=node_id,
            nodes=[node],
            triples=[triple],
            depth=depth,
        )

    async def get_entities(self, labels=None, filters=None) -> list[L2Entity]:
        """Unused graph method required by the reader protocol."""
        return []

    async def vector_search(
        self,
        embedding,
        top_k,
        node_label=None,
    ) -> list[SearchResult]:
        """Unused graph method required by the reader protocol."""
        return []


class OverflowOnceReranker:
    """Reranker that overflows once before succeeding on shallower inputs."""

    def __init__(self) -> None:
        """Initialize call recording."""
        self.calls: list[tuple[int, int]] = []

    async def score_relation(self, *args: Any, **kwargs: Any) -> float:
        """Raise an overflow on depth 2 and succeed afterward."""
        env_a = args[1]
        env_b = args[3]
        self.calls.append((env_a.depth, env_b.depth))
        if env_a.depth >= 2:
            raise ValueError("Invalid buffer size: 50.00 GiB")
        return 0.91


@pytest.mark.asyncio
async def test_dense_extractor_emits_optional_observability_spans(
    graph_store,
) -> None:
    """Dense extraction emits candidate, rerank, and LLM extraction spans."""
    trace_sink = FakeTraceSink()

    entities = [
        L2Entity(id="e1", label="KONZEPT", name="Theory"),
        L2Entity(id="e2", label="KONZEPT", name="Observation"),
    ]
    extractor = DenseRetrievalGlobalRelationExtractor(
        llm=FakeLLM(),
        embedding_model=FakeEmbedModel(),
        reranker=FakeReranker(),
        config=Phase3Config(
            dense_similarity_threshold=0.5,
            reranker_threshold=0.6,
            trace_dense_retrieval=True,
        ),
        trace_sink=trace_sink,
    )

    triples = await extractor.extract(entities, graph_store, SchemaConfig())

    assert len(triples) == 1
    assert triples[0].confidence == 0.8
    assert [span["name"] for span in trace_sink.spans] == [
        "phase3.dense.candidates",
        "phase3.dense.rerank",
        "phase3.dense.llm_extract",
    ]

    candidates_output = trace_sink.spans[0]["output"]
    assert candidates_output["candidate_count"] == 1
    assert candidates_output["candidates"][0]["dense_score"] == pytest.approx(0.8)

    rerank_output = trace_sink.spans[1]["output"]
    assert rerank_output["rerank_score"] == 0.9
    assert rerank_output["accepted"] is True
    assert rerank_output["reranker_input"]["pair_byte_count"] > 0
    assert rerank_output["recovery_attempts"] == []

    rerank_input = trace_sink.spans[1]["input"]
    assert rerank_input["requested_subgraph_depth"] == 2
    assert rerank_input["env_a"]["byte_count"] > 0
    assert rerank_input["env_b"]["char_count"] > 0
    assert rerank_input["reranker_input"]["pair_char_count"] > 0
    assert rerank_input["reranker_payload"]["query"].startswith("Entity: Theory")
    assert rerank_input["reranker_payload"]["document"].startswith("Entity: Observation")

    llm_output = trace_sink.spans[2]["output"]
    assert llm_output["relation"] == "IMPLIES"
    assert llm_output["direction"] == "A_to_B"

    llm_input = trace_sink.spans[2]["input"]
    assert llm_input["merged_envelope"]["byte_count"] > 0


class _DisabledSpan:
    """No-op span used when tracing is disabled in tests."""

    def update(self, **kwargs: object) -> None:
        """Ignore span updates."""


@pytest.mark.asyncio
async def test_dense_extractor_can_omit_optional_observability_spans(
    graph_store,
) -> None:
    """Dense extraction omits custom spans when tracing is disabled."""
    trace_sink = FakeTraceSink()

    entities = [
        L2Entity(id="e1", label="KONZEPT", name="Theory"),
        L2Entity(id="e2", label="KONZEPT", name="Observation"),
    ]
    extractor = DenseRetrievalGlobalRelationExtractor(
        llm=FakeLLM(),
        embedding_model=FakeEmbedModel(),
        reranker=FakeReranker(),
        config=Phase3Config(
            dense_similarity_threshold=0.5,
            reranker_threshold=0.6,
            trace_dense_retrieval=False,
        ),
        trace_sink=trace_sink,
    )

    triples = await extractor.extract(entities, graph_store, SchemaConfig())

    assert len(triples) == 1
    assert trace_sink.spans == []


@pytest.mark.asyncio
async def test_dense_extractor_supports_event_emitter_without_trace_sink(
    graph_store,
) -> None:
    """Dense extraction falls back to a no-op trace sink when only events are configured."""
    entities = [
        L2Entity(id="e1", label="KONZEPT", name="Theory"),
        L2Entity(id="e2", label="KONZEPT", name="Observation"),
    ]
    extractor = DenseRetrievalGlobalRelationExtractor(
        llm=FakeLLM(),
        embedding_model=FakeEmbedModel(),
        reranker=FakeReranker(),
        config=Phase3Config(
            dense_similarity_threshold=0.5,
            reranker_threshold=0.6,
            trace_dense_retrieval=True,
        ),
    )

    triples = await extractor.extract(entities, graph_store, SchemaConfig())

    assert len(triples) == 1


@pytest.mark.asyncio
async def test_dense_extractor_recovers_from_reranker_overflow_with_refetch() -> None:
    """Overflow handler refetches shallower envelopes and records the recovery."""
    trace_sink = FakeTraceSink()
    graph_store = RecordingGraphStore()
    reranker = OverflowOnceReranker()
    entities = [
        L2Entity(id="e1", label="KONZEPT", name="Theory"),
        L2Entity(id="e2", label="KONZEPT", name="Observation"),
    ]
    extractor = DenseRetrievalGlobalRelationExtractor(
        llm=FakeLLM(),
        embedding_model=FakeEmbedModel(),
        reranker=reranker,
        config=Phase3Config(
            dense_similarity_threshold=0.5,
            reranker_threshold=0.6,
            subgraph_depth=2,
            trace_dense_retrieval=True,
        ),
        envelope_overflow_handler=make_reduce_depth_overflow_handler(),
        trace_sink=trace_sink,
    )

    triples = await extractor.extract(entities, graph_store, SchemaConfig())

    assert len(triples) == 1
    assert reranker.calls == [(2, 2), (1, 1)]
    assert graph_store.depth_calls == [("e1", 2), ("e2", 2), ("e1", 1), ("e2", 1)]

    rerank_output = trace_sink.spans[1]["output"]
    assert rerank_output["rerank_score"] == 0.91
    assert rerank_output["accepted"] is True
    assert len(rerank_output["recovery_attempts"]) == 1
    assert rerank_output["recovery_attempts"][0]["strategy"] == "reduce_subgraph_depth"
    assert rerank_output["recovery_attempts"][0]["metadata"] == {
        "previous_depth": 2,
        "next_depth": 1,
        "depth_step": 1,
    }
    assert rerank_output["recovery_attempts"][0]["reranker_input"]["pair_byte_count"] > 0
