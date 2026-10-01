"""TypeSafe Jev and Cascading Entity Linkers.

Provides System 1 fast candidate disambiguation (:class:`JevEntityLinker`) and
cascading triage (:class:`CascadingEntityLinker`) satisfying the :class:`EntityLinker`
protocol.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

import torch

from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    EntityLinkingCandidatesRetrieved,
    EntityLinkingReranked,
    UnlinkableMentionError,
)
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionScore,
    ensure_decision_engine,
)
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    EntityLinker,
    as_tensor,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.graph_store import GraphReader

logger = logging.getLogger(__name__)


class JevEntityLinker(EntityLinker):
    """Entity linker backed by TypeSafe Jev / Laya calibrated decision engine.

    Performs bi-encoder candidate retrieval from the active graph store followed
    by Jev categorical choice disambiguation with conformal prediction guarantees
    and explicit Out-of-Ontology (OoO) detection.

    Parameters
    ----------
    decision_engine : DecisionEngine
        Calibrated decision engine supporting ``evaluate_choice``.
    embedding_model : EmbeddingModel or str or None, default None
        Bi-encoder used to embed mentions and candidate nodes. If None,
        defaults to ``HuggingFaceEmbeddingModel``.
    alpha : float, default 0.05
        Conformal significance level providing 1 - alpha prediction set coverage.
    top_k : int, default 5
        Maximum number of candidate entities evaluated in the Jev choice prompt.
        Bounded to 5 by default to prevent context window saturation.
    ooo_threshold : float, default 0.75
        Confidence threshold fallback for Out-of-Ontology decisions.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        embedding_model: EmbeddingModel | Any,
        alpha: float = 0.05,
        top_k: int = 5,
        ooo_threshold: float = 0.75,
    ) -> None:
        engine = ensure_decision_engine(decision_engine)
        if engine is None:
            raise ValueError("A valid DecisionEngine must be provided to JevEntityLinker.")
        self.decision_engine: DecisionEngine = engine

        model = ensure_embedding_model(embedding_model)
        if model is None:
            raise ValueError("A valid EmbeddingModel must be provided to JevEntityLinker.")
        self.embedding_model: EmbeddingModel = model

        self.alpha = alpha
        self.top_k = top_k
        self.ooo_threshold = ooo_threshold

        # Candidate envelope cache: entity_id -> (text, embedding)
        self._candidate_cache: dict[str, tuple[str, list[float]]] = {}

    @property
    def event_emitter(self) -> EventEmitter:
        """Return the bound domain event emitter."""
        return get_event_emitter()

    @staticmethod
    def _canonical_entity_string(candidate: L2Entity) -> str:
        """Format candidate entity for bi-encoder embedding with explicit type grounding."""
        return f"[{candidate.label}] {candidate.name}: {candidate.description or ''}"

    async def _populate_candidate_cache(self, candidates: list[L2Entity]) -> None:
        """Pre-fetch embeddings for new or stale candidates."""
        stale_candidates = []
        stale_basic_texts = []
        for c in candidates:
            basic_text = self._canonical_entity_string(c)
            cached = self._candidate_cache.get(c.id)
            if not cached or cached[0] != basic_text:
                stale_candidates.append(c)
                stale_basic_texts.append(basic_text)

        if not stale_candidates:
            return

        fresh_vectors = await self.embedding_model.aget_text_embedding_batch(stale_basic_texts)
        for c, b_text, vec in zip(stale_candidates, stale_basic_texts, fresh_vectors):
            self._candidate_cache[c.id] = (b_text, vec)

    async def _candidate_embeddings(self, candidates: list[L2Entity]) -> torch.Tensor:
        """Return cached embeddings as a torch Tensor."""
        embs = [self._candidate_cache[c.id][1] for c in candidates]
        return as_tensor(embs)

    async def link_with_decision(
        self,
        mention: L2Entity,
        graph_store: GraphReader,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
        alpha: float | None = None,
    ) -> tuple[L2Entity | None, DecisionScore | None, bool]:
        """Link a mention to a canonical entity and return detailed decision telemetry.

        Parameters
        ----------
        mention : L2Entity
            The extracted entity mention to link.
        graph_store : GraphReader
            Active graph store holding canonical entities.
        top_k : int or None, default None
            Optional override for candidate retrieval count (bounded to 5).
        threshold : float or None, default None
            Optional override for acceptance threshold.
        alpha : float or None, default None
            Optional override for conformal significance level.

        Returns
        -------
        tuple of (L2Entity or None, DecisionScore or None, bool)
            - Matched canonical entity, or None if novel/ambiguous.
            - Decision score telemetry from the DecisionEngine.
            - ``is_ambiguous`` flag indicating whether decision escalated (e.g.
              conformal set size > 1 or empty).
        """
        if not mention.textual_envelope:
            logger.warning("Mention %s lacks textual envelope. Raising UnlinkableMentionError.", mention.name)
            raise UnlinkableMentionError(f"Mention {mention.name} lacks textual envelope.")

        effective_top_k = min(self.top_k if top_k is None else top_k, 5)
        effective_alpha = self.alpha if alpha is None else alpha
        effective_threshold = self.ooo_threshold if threshold is None else threshold

        candidates = await graph_store.get_entities()
        if not candidates:
            return None, None, False

        # 1. Bi-Encoder retrieval
        t_n = f"[{mention.label}] {mention.textual_envelope}"
        raw_t_n_emb = await self.embedding_model.aget_text_embedding_batch([t_n])
        t_n_emb = as_tensor(raw_t_n_emb)[0]
        t_n_emb = torch.nn.functional.normalize(t_n_emb, p=2, dim=0)

        await self._populate_candidate_cache(candidates)
        g_embs = await self._candidate_embeddings(candidates)
        g_embs = torch.nn.functional.normalize(g_embs, p=2, dim=1)

        scores = torch.matmul(g_embs, t_n_emb)
        top_k_indices = torch.topk(scores, min(effective_top_k, len(candidates))).indices

        top_candidates = [candidates[i] for i in top_k_indices]
        top_scores = scores[top_k_indices].tolist()

        self.event_emitter.emit(
            EntityLinkingCandidatesRetrieved(
                mention_id=mention.id,
                mention_name=mention.name,
                candidate_count=len(top_candidates),
                candidates=[
                    {"id": c.id, "name": c.name, "score": float(s)}
                    for c, s in zip(top_candidates, top_scores)
                ],
            )
        )

        # 2. In-context Jev Choice options formulation
        options: dict[str, str] = {}
        key_to_candidate: dict[str, L2Entity] = {}
        for c in top_candidates:
            key = c.name
            if key in options:
                key = f"{c.name} ({c.id})"
            options[key] = c.description or f"Entity [{c.label}]"
            key_to_candidate[key] = c

        options["OUT_OF_ONTOLOGY"] = "Novel entity not represented in candidates"

        # 3. Jev Choice evaluation
        state = f"Mention: {mention.name}\nContext:\n{t_n}"
        question = "Which entity best matches this mention?"
        decision = await self.decision_engine.evaluate_choice(
            state=state,
            question=question,
            options=options,
            alpha=effective_alpha,
        )

        conformal_set = decision.prediction_set
        if conformal_set is None:
            conformal_set = [str(decision.selected_option)] if decision.selected_option is not None else []

        # If conformal set contains multiple candidates or is empty (uncertain), mark ambiguous
        if len(conformal_set) > 1 or len(conformal_set) == 0:
            logger.debug(
                "JevEntityLinker: ambiguous conformal set %s for mention %s",
                conformal_set,
                mention.name,
            )
            return None, decision, True

        selected = conformal_set[0]

        # Case: Confidently novel Out-of-Ontology
        if selected == "OUT_OF_ONTOLOGY":
            logger.debug("JevEntityLinker: Out-of-Ontology declared for %s", mention.name)
            self.event_emitter.emit(
                EntityLinkingReranked(
                    mention_id=mention.id,
                    mention_name=mention.name,
                    candidate_id="OUT_OF_ONTOLOGY",
                    candidate_name="OUT_OF_ONTOLOGY",
                    score=decision.empirical_accuracy,
                    accepted=False,
                    threshold=effective_threshold,
                )
            )
            return None, decision, False

        # Case: Confidently matched single canonical entity
        matched = key_to_candidate.get(selected)
        if matched is not None:
            logger.debug(
                "JevEntityLinker: linked %s -> %s (Acc: %s)",
                mention.name,
                matched.name,
                decision.empirical_accuracy,
            )
            self.event_emitter.emit(
                EntityLinkingReranked(
                    mention_id=mention.id,
                    mention_name=mention.name,
                    candidate_id=matched.id,
                    candidate_name=matched.name,
                    score=decision.empirical_accuracy,
                    accepted=True,
                    threshold=effective_threshold,
                )
            )
            return matched, decision, False

        return None, decision, True

    async def link(
        self,
        mention: L2Entity,
        graph_store: GraphReader,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> L2Entity | None:
        """Link an extracted entity mention to an existing canonical graph node.

        Parameters
        ----------
        mention : L2Entity
            The extracted entity mention.
        graph_store : GraphReader
            Active graph store.
        top_k : int or None, default None
            Optional override for candidate retrieval count.
        threshold : float or None, default None
            Optional override for confidence threshold.

        Returns
        -------
        L2Entity or None
            The matched canonical entity, or None if novel or ambiguous.
        """
        matched, _, _ = await self.link_with_decision(
            mention, graph_store, top_k=top_k, threshold=threshold
        )
        return matched


class CascadingEntityLinker(EntityLinker):
    """Cascading entity linker combining System 1 triage with System 2 verification.

    Routes mentions first to a primary linker (typically :class:`JevEntityLinker`).
    If the primary decision is ambiguous (e.g. conformal prediction set contains
    multiple candidates or is uncertain), the mention cascades to a fallback
    linker (typically :class:`DenseEntityLinker` using cross-encoder reranking).

    Parameters
    ----------
    primary : EntityLinker
        Primary fast triage linker (typically :class:`JevEntityLinker`).
    fallback : EntityLinker
        Secondary fallback linker (typically :class:`DenseEntityLinker`).
    audit_rate : float, default 0.0
        Stochastic rate at which mentions bypass the primary linker and run
        directly through the fallback linker for calibration auditing.
    """

    def __init__(
        self,
        primary: EntityLinker,
        fallback: EntityLinker,
        audit_rate: float = 0.0,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.audit_rate = audit_rate

    async def link(
        self,
        mention: L2Entity,
        graph_store: GraphReader,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> L2Entity | None:
        """Link mention via cascading triage with fallback.

        Parameters
        ----------
        mention : L2Entity
            The extracted entity mention.
        graph_store : GraphReader
            Active graph store.
        top_k : int or None, default None
            Optional override for candidate retrieval count.
        threshold : float or None, default None
            Optional override for confidence threshold.

        Returns
        -------
        L2Entity or None
            The matched canonical entity, or None to mint a novel entity.
        """
        if self.audit_rate > 0.0 and random.random() < self.audit_rate:
            logger.debug("CascadingEntityLinker: stochastic audit triggered for %s", mention.name)
            return await self.fallback.link(mention, graph_store, top_k=top_k, threshold=threshold)

        if isinstance(self.primary, JevEntityLinker):
            matched, decision, is_ambiguous = await self.primary.link_with_decision(
                mention, graph_store, top_k=top_k, threshold=threshold
            )
            if not is_ambiguous:
                return matched
            logger.debug(
                "CascadingEntityLinker: primary returned ambiguous decision for %s; escalating to fallback",
                mention.name,
            )
        else:
            matched = await self.primary.link(mention, graph_store, top_k=top_k, threshold=threshold)
            if matched is not None:
                return matched

        return await self.fallback.link(mention, graph_store, top_k=top_k, threshold=threshold)
