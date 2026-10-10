"""Interfaces the pipeline expects from user-supplied models and extractors.

The composition root (``Pipeline.for_task``) receives concrete model objects from
the caller and passes them down to the phase runners. This module defines what
"compatible" means for each of those slots.

Two kinds of contract are used deliberately:

``Protocol`` (structural)
    Used for objects the *user* brings — an embedding model, a cross-encoder.
    The pipeline must accept anything with the right shape (a llama-index
    ``BaseEmbedding``, a sentence-transformers model, a bespoke wrapper), so the
    contract cannot require inheritance. Adapters in this module therefore do
    **not** subclass the Protocols: inheriting from a Protocol turns its
    ``...``-bodied members into concrete methods returning ``None``, which
    silently masks missing implementations. Conformance is checked statically
    (see ``_static_conformance`` at the bottom of this module) and, where a
    runtime decision is needed, by ``ensure_embedding_model``.

``ABC`` (nominal)
    Used for pipeline-internal extension points — extractors, linkers,
    rerankers. These are implemented inside the pipeline and a partial
    implementation should fail loudly at construction time.

Embedding contract
------------------
There is one embedding contract: the **async, ``list[float]``** form.
It was chosen because remote embedding APIs (LiteLLM, OpenAI, Ollama via
llama-index) already satisfy it natively, so no wrapping is needed for the
common case. Local torch models expose a synchronous ``encode`` returning a
tensor instead; those are adapted by ``SyncEncoderEmbeddingModel`` (or wrap
themselves, as ``HuggingFaceEmbeddingModel`` and ``EnvelopeBiEncoder`` do).

Consumers that need a tensor (dense entity linking, entity maturation) convert
at the call site via ``as_tensor`` rather than requiring a second method on the
contract.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from episteme_pipeline.contracts.domain import (
    L2Entity,
    L2Triple,
    SubGraph,
    CandidatePair,
    PhaseItemRecord,
)
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.schema.default_schema import SchemaConfig

if TYPE_CHECKING:  # torch is only needed by callers that want tensors
    import torch


@runtime_checkable
class EmbeddingModel(Protocol):
    """Protocol for vector embedding models.

    The single embedding contract used throughout the pipeline: asynchronous,
    returning plain ``list[float]`` vectors.

    A llama-index ``BaseEmbedding`` (``LiteLLMEmbedding``, ``OllamaEmbedding``,
    ...) satisfies this natively. Synchronous, tensor-returning local models are
    adapted via :class:`SyncEncoderEmbeddingModel`.

    Implementations must return vectors of a consistent dimensionality; the
    Neo4j vector indexes are created against that dimension.
    """

    async def aget_text_embedding(self, text: str) -> list[float]: ...

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class CrossEncoder(Protocol):
    """Protocol for cross-encoders predicting a relevance score for text pairs.

    Score domain
    ------------
    ``predict`` must return **probability-like scores in ``[0, 1]``** (i.e. an
    activation such as sigmoid has already been applied). The pipeline compares
    these scores against configured thresholds
    (``Phase2Config.linking_confidence_threshold``, ``Phase3Config.reranker_threshold``)
    that are expressed as probabilities. A model returning raw logits will make
    those thresholds meaningless — see
    :func:`episteme_pipeline.protocols.extractors.normalize_scores`, which consumers use
    to detect and correct that case.

    Returns a sequence of floats aligned with ``pairs``; a numpy array or torch
    tensor is acceptable since both are sequences of floats, but consumers must
    not rely on array-only APIs (``.argmax()`` etc.).
    """

    def predict(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]: ...


# ----------------------------------------------------------------------
# Helpers shared by consumers of the contracts above
# ----------------------------------------------------------------------


def as_tensor(embeddings: Sequence[Sequence[float]]) -> "torch.Tensor":
    """Convert protocol-shaped embeddings into a ``[n, dim]`` float tensor.

    Kept out of the :class:`EmbeddingModel` contract on purpose: only two
    consumers need tensors, and requiring a tensor-returning method would
    exclude every remote embedding API.
    """
    import torch

    if isinstance(embeddings, torch.Tensor):
        return embeddings.to(dtype=torch.float32)
    return torch.tensor(embeddings, dtype=torch.float32)


def normalize_scores(scores: Sequence[float]) -> list[float]:
    """Coerce cross-encoder output to a ``list[float]`` in ``[0, 1]``.

    Accepts a list, numpy array or torch tensor. If any value falls outside
    ``[0, 1]`` the model is emitting raw logits despite the
    :class:`CrossEncoder` contract, and a logistic sigmoid is applied to the
    whole batch so that configured probability thresholds remain meaningful.
    """
    import math

    values = [float(s) for s in scores]
    if any(v < 0.0 or v > 1.0 for v in values):
        return [1.0 / (1.0 + math.exp(-v)) for v in values]
    return values


def argmax(values: Sequence[float]) -> int:
    """Index of the largest value. Works on lists, numpy arrays and tensors."""
    return max(range(len(values)), key=values.__getitem__)


# ----------------------------------------------------------------------
# Embedding adapters (plain classes — deliberately not Protocol subclasses)
# ----------------------------------------------------------------------


class SyncEncoderEmbeddingModel:
    """Adapt a synchronous, tensor-returning encoder to :class:`EmbeddingModel`.

    Covers sentence-transformers ``SentenceTransformer`` objects and any local
    model exposing ``encode(list[str]) -> Tensor | ndarray | list[list[float]]``.
    The synchronous forward pass is moved off the event loop with
    ``asyncio.to_thread`` so it does not block concurrent phase work.
    """

    def __init__(self, encoder: Any, model_name: str | None = None) -> None:
        if not hasattr(encoder, "encode"):
            raise TypeError(
                f"{type(encoder).__name__} has no .encode(list[str]) method; "
                "it cannot be adapted to EmbeddingModel."
            )
        self.encoder = encoder
        self.model_name: str = (
            model_name
            or getattr(encoder, "model_name", None)
            or getattr(encoder, "name", None)
            or type(encoder).__name__
        )
        self.device = getattr(encoder, "device", None)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        raw = self.encoder.encode(texts)
        tolist = getattr(raw, "tolist", None)
        rows = tolist() if callable(tolist) else raw
        return [[float(x) for x in row] for row in rows]

    async def aget_text_embedding(self, text: str) -> list[float]:
        rows = await asyncio.to_thread(self._encode, [text])
        return rows[0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._encode, list(texts))


class HuggingFaceEmbeddingModel:
    """Local Hugging Face ``AutoModel`` embedding model.

    Implements :class:`EmbeddingModel` directly. Uses mean pooling over the
    attention mask, which is the pooling strategy the default
    ``sentence-transformers/*`` checkpoints were trained with.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer
        from episteme_pipeline.config import PipelineConfig

        selected_model = model_name or PipelineConfig().default_embedding_model
        self.model_name = selected_model
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(selected_model)
        self.model = AutoModel.from_pretrained(selected_model)
        self.model.to(self.device)
        self.model.eval()
        self.dimension = (
            self.model.config.hidden_size if hasattr(self.model, "config") else None
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic Hugging Face embedding model configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing model name, device, and embedding dimension.
        """
        return {
            "class": self.__class__.__name__,
            "model_name": str(self.model_name),
            "device": str(self.device) if self.device else None,
            "dimension": self.dimension,
        }

    def encode(self, texts: list[str]) -> "torch.Tensor":
        """Synchronous forward pass returning a ``[n, hidden]`` tensor."""
        import torch

        with torch.no_grad():
            inputs = self.tokenizer(
                texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            hidden = outputs.last_hidden_state  # [batch, seq, hidden]
            mask = inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            summed = (hidden * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1e-9)
            return summed / counts

    async def aget_text_embedding(self, text: str) -> list[float]:
        batch = await self.aget_text_embedding_batch([text])
        return batch[0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        tensor = await asyncio.to_thread(self.encode, list(texts))
        return [[float(x) for x in row] for row in tensor.tolist()]


class ObservableEmbeddingModel:
    """Wraps an :class:`EmbeddingModel` to emit domain and telemetry events upon execution.

    Adheres to the Decorator and Single Responsibility principles by augmenting
    vector computation with latency tracking, token estimation, and event publishing.

    Parameters
    ----------
    inner : EmbeddingModel
        Underlying embedding model facade or instance.
    model_name : str, optional
        Explicit model name. If not provided, inferred from the inner instance.
    """

    def __init__(self, inner: Any, model_name: str | None = None) -> None:
        self.inner = inner
        self.model_name = (
            model_name
            or getattr(inner, "model_name", None)
            or getattr(inner, "model", None)
            or getattr(inner, "_model_name", None)
            or type(inner).__name__
        )
        self.device = getattr(inner, "device", None)
        self.dimension = getattr(inner, "dimension", None)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic observable embedding model configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing model name, device, dimension, and inner fingerprint.
        """
        from episteme_pipeline.runs.fingerprints import fingerprint_method

        inner_fp = (
            self.inner.fingerprint()
            if hasattr(self.inner, "fingerprint") and callable(self.inner.fingerprint)
            else fingerprint_method(self.inner)
        )
        return {
            "class": self.__class__.__name__,
            "model_name": str(self.model_name) if self.model_name else None,
            "device": str(self.device) if self.device else None,
            "dimension": self.dimension,
            "inner": inner_fp,
        }

    async def aget_text_embedding(self, text: str) -> list[float]:
        """Compute embedding vector for a single text with observability."""
        batch = await self.aget_text_embedding_batch([text])
        return batch[0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        """Compute embedding vectors for a batch of texts with observability."""
        if not texts:
            return []

        import time
        from episteme_pipeline.events.context import get_event_emitter
        from episteme_pipeline.events.models import EmbeddingGenerationCompleted
        from episteme_pipeline.llm.metadata import LLMResponseMetadataExtractor

        t0 = time.perf_counter()
        embeddings = await self.inner.aget_text_embedding_batch(texts)
        duration = time.perf_counter() - t0

        total_chars = sum(len(t) for t in texts)
        total_tokens = sum(LLMResponseMetadataExtractor.estimate_tokens(t) for t in texts)
        vector_dim = len(embeddings[0]) if embeddings and embeddings[0] else self.dimension

        try:
            get_event_emitter().emit(
                EmbeddingGenerationCompleted(
                    model_name=str(self.model_name),
                    text_count=len(texts),
                    total_characters=total_chars,
                    prompt_tokens=total_tokens,
                    total_tokens=total_tokens,
                    duration_seconds=duration,
                    vector_dim=vector_dim,
                    operation="embedding",
                )
            )
        except Exception:
            pass

        return embeddings

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def ensure_embedding_model(model: Any | None) -> EmbeddingModel | None:
    """Normalise a user-supplied object into an observable :class:`EmbeddingModel`.

    Called **once**, at the composition root, so that no phase runner ever sees
    a raw third-party object:

    * ``None`` passes through (embedding is optional for some runners);
    * an already-wrapped :class:`ObservableEmbeddingModel` is returned directly;
    * a string model name is resolved to :class:`HuggingFaceEmbeddingModel` and wrapped;
    * anything that already exposes the async contract is wrapped in :class:`ObservableEmbeddingModel`;
    * anything exposing a synchronous ``encode`` is adapted via :class:`SyncEncoderEmbeddingModel`
      and wrapped in :class:`ObservableEmbeddingModel`;
    * anything else raises ``TypeError`` immediately, at configuration time.
    """
    if model is None:
        return None
    if isinstance(model, ObservableEmbeddingModel):
        return model
    if isinstance(model, str):
        hf = HuggingFaceEmbeddingModel(model_name=model)
        return ObservableEmbeddingModel(hf, model_name=model)
    if hasattr(model, "aget_text_embedding") and hasattr(model, "aget_text_embedding_batch"):
        return ObservableEmbeddingModel(model)
    if hasattr(model, "encode"):
        sync_model = SyncEncoderEmbeddingModel(model)
        return ObservableEmbeddingModel(sync_model)
    raise TypeError(
        f"{type(model).__name__} does not satisfy the EmbeddingModel protocol: it "
        "must provide either async aget_text_embedding/aget_text_embedding_batch "
        "(llama-index style) or a synchronous encode(list[str]) (torch style)."
    )



# ----------------------------------------------------------------------
# Pipeline extension points (nominal — implement by subclassing)
# ----------------------------------------------------------------------


class RelationReranker(ABC):
    """
    Scores the likelihood of a relationship existing between two entities
    based on their contextual subgraph envelopes.

    Note: This is distinct from the CrossEncoder protocol. While a CrossEncoder
    operates on raw text pairs, a RelationReranker operates on domain objects
    (L2Entity, SubGraph) to support structural (e.g. GNN) and non-textual rerankers.

    A text cross-encoder can be lifted into this interface with
    ``episteme_pipeline.phases.phase3_global_relations.rerankers.CrossEncoderRelationReranker``.
    Do not rely on a single object happening to satisfy both interfaces — wire
    the two slots explicitly at the composition root.
    """

    @abstractmethod
    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: SubGraph,
        entity_b: L2Entity,
        env_b: SubGraph,
    ) -> float: ...


class NERExtractor(ABC):
    """
    Local Relation & Entity Extractor (Phase 2).

    This extractor takes raw text from a document chunk and performs Named Entity
    Recognition and local relation extraction simultaneously using structured LLM decoding.
    It returns newly discovered entities and local triples.
    """

    @abstractmethod
    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: Any | None = None,
        anchor: Any | None = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]: ...


class GlobalRelationExtractor(ABC):
    """
    Global Relation Extractor (Phase 3).

    Unlike the NERExtractor which operates on raw text locally, this extractor
    operates globally on previously extracted graph entities to find missing
    relationships that span across distant chunks.

    Used by:
      - Phase 3: populating global L2 triples in the KG
      - Phase 4 ARC: classifying global argument relations (support/attack)
        across distant argument components

    The TAG + reranker default implementation retrieves local subgraph
    envelopes via embedding similarity and scores candidate relations via a
    reranker model before LLM triple decoding.
    """

    async def candidate_pairs(
        self, entities: list[L2Entity]
    ) -> list[CandidatePair]:
        """Generate candidate entity pairs for relation extraction.

        Parameters
        ----------
        entities : list[L2Entity]
            Entities considered for candidate pairing.

        Returns
        -------
        list[CandidatePair]
            Candidate entity pairs.
        """
        pairs: list[CandidatePair] = []
        sorted_ents = sorted(entities, key=lambda e: e.id)
        for i, a in enumerate(sorted_ents):
            for b in sorted_ents[i + 1 :]:
                pairs.append(CandidatePair(entity_a=a, entity_b=b))
        return pairs

    async def extract_pair(
        self,
        pair: CandidatePair,
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> L2Triple | None:
        """Extract a relation triple for a single candidate pair.

        Parameters
        ----------
        pair : CandidatePair
            Candidate entity pair to evaluate.
        graph_store : GraphReader
            Graph reader for envelope/neighborhood retrieval.
        schema : SchemaConfig
            Schema configuration defining valid relation types.

        Returns
        -------
        L2Triple | None
            Extracted triple if validated above threshold, otherwise None.
        """
        return None

    async def extract_pairs(
        self,
        pairs: Sequence[CandidatePair],
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> tuple[list[L2Triple], list[PhaseItemRecord]]:
        """Extract relation triples for a batch of candidate pairs, isolating errors.

        Parameters
        ----------
        pairs : Sequence[CandidatePair]
            Batch of candidate entity pairs to evaluate.
        graph_store : GraphReader
            Graph reader for envelope/neighborhood retrieval.
        schema : SchemaConfig
            Schema configuration defining valid relation types.

        Returns
        -------
        tuple[list[L2Triple], list[PhaseItemRecord]]
            Tuple of extracted triples and corresponding checkpoint item records.
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        async def _eval_one(pair: CandidatePair) -> tuple[L2Triple | None, PhaseItemRecord]:
            try:
                triple = await self.extract_pair(pair, graph_store, schema)
                return triple, PhaseItemRecord(key=pair.key, status="completed")
            except Exception as exc:
                logger.error("Phase 3 quarantined failed pair %s: %s", pair.key, exc)
                return None, PhaseItemRecord(
                    key=pair.key,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )

        tasks = [_eval_one(pair) for pair in pairs]
        results = await asyncio.gather(*tasks)

        triples: list[L2Triple] = []
        item_records: list[PhaseItemRecord] = []
        for triple, record in results:
            item_records.append(record)
            if triple is not None:
                triples.append(triple)
        return triples, item_records

    async def extract(
        self,
        entities: list[L2Entity],
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> list[L2Triple]:
        """Extract global relations across all entities.

        Parameters
        ----------
        entities : list[L2Entity]
            Entities to extract relations between.
        graph_store : GraphReader
            Graph reader for neighborhood retrieval.
        schema : SchemaConfig
            Schema configuration.

        Returns
        -------
        list[L2Triple]
            Extracted relation triples.
        """
        pairs = await self.candidate_pairs(entities)
        triples, _ = await self.extract_pairs(pairs, graph_store, schema)
        return triples

    async def get_structural_neighborhood(
        self, entity: L2Entity, graph_store: GraphReader, depth: int = 2,
    ) -> SubGraph:
        """Default structural neighborhood retrieval via graph_store."""
        return await graph_store.get_neighborhood(entity.id, depth=depth)


class EntityLinker(ABC):
    """
    Phase 2 Step 3: Links extracted entity mentions to canonical graph nodes.
    Bi-encoder retrieval + cross-encoder reranking.
    """

    @abstractmethod
    async def link(
        self,
        mention: L2Entity,
        graph_store: GraphReader,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> L2Entity | None:
        """
        Returns the canonical graph entity if a match above threshold is found,
        or None to mint a new entity.

        ``top_k`` and ``threshold`` are per-call overrides. ``None`` means "use
        the value this linker was constructed with", so that the configured
        defaults live in exactly one place (``Phase2Config``) instead of being
        duplicated as signature defaults.
        """
        ...


def _static_conformance() -> None:
    """Type-checker-only assertions that the adapters satisfy the Protocols.

    Never called. Exists so that ``mypy``/``pyright`` fail if an adapter drifts
    out of conformance — the check that explicit Protocol inheritance would
    otherwise have silently suppressed.
    """
    _hf: EmbeddingModel = HuggingFaceEmbeddingModel.__new__(HuggingFaceEmbeddingModel)
    _sync: EmbeddingModel = SyncEncoderEmbeddingModel.__new__(SyncEncoderEmbeddingModel)
    del _hf, _sync
