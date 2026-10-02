"""
EmbeddingArgumentClustering — global argument resolution via Key Point Analysis.

Groups semantically equivalent argument components across chunks/documents.
Each cluster represents arguments that are logically the same claim or premise,
possibly restated in different sections.

Strategy:
  1. Retrieve all TheoryAtom nodes from the graph
  2. Embed their texts using the embedding_model (async, batched)
  3. Compute pairwise cosine similarity
  4. Find connected components where any pair exceeds the similarity threshold
     (single-linkage clustering — fast, O(N²) which is fine for V1)
  5. Return clusters of size ≥ 2 (singletons need no merging)

The caller (`Phase5bTheoryFusionRunner.run`) receives the cluster list and can use it
to merge or link canonical nodes. No graph mutations are performed here — the
cluster structure is returned for the caller to act on.

This is intentionally simple. More sophisticated approaches (HDBSCAN, Key Point
Analysis from IBM, or a fine-tuned cross-encoder for argument similarity) can be
plugged in by subclassing ArgumentClustering and injecting the new implementation.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.prompts.default_prompts import (
    DECISION_THEORY_FUSION_CRITERIA,
    DECISION_THEORY_FUSION_QUESTION,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import ArgumentClustering
from episteme_pipeline.protocols.graph_store import GraphReader

logger = logging.getLogger(__name__)


def _union_find_components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Union-find connected components from a list of (i, j) edges."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i, j in edges:
        union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


class EmbeddingArgumentClustering(ArgumentClustering):
    """
    Cosine-similarity connected-components clustering over L3 argument components.

    Requires an embedding_model to be injected. Falls back to empty clusters if
    no embedding_model is available (safe for pipelines without argument mining).
    """

    def __init__(
        self,
        embedding_model=None,
        similarity_threshold: float = 0.85,
        max_components: int = 10000,
    ) -> None:
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.max_components = max_components

    async def cluster(
        self,
        graph_store: GraphReader,
    ) -> list[list[str]]:
        if self.embedding_model is None:
            logger.warning(
                "EmbeddingArgumentClustering: no embedding_model — skipping clustering."
            )
            return []

        components = await graph_store.get_theory_atoms()
        n = len(components)

        if n < 2:
            return []

        if n > self.max_components:
            logger.warning(
                "Phase 5b: %d components exceeds max_components=%d — clustering skipped to avoid O(%.0f) memory usage",
                n,
                self.max_components,
                n * n,
            )
            return []

        logger.info("Phase 5b: clustering %d argument components.", n)

        # Embed all component texts (concurrent)
        texts = [c.text for c in components]
        # The EmbeddingModel contract is async-only; no sync fallback needed.
        raw_embeddings = await self.embedding_model.aget_text_embedding_batch(texts)

        import numpy as np

        matrix = np.array(raw_embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms

        # Pairwise cosine similarity (N×N, vectorized)
        sim = matrix @ matrix.T

        # Collect edges where similarity ≥ threshold (upper triangle only)
        edges = [
            (i, j)
            for i in range(n)
            for j in range(i + 1, n)
            if sim[i, j] >= self.similarity_threshold
        ]

        if not edges:
            return []

        groups = _union_find_components(n, edges)
        ids = [c.id for c in components]

        clusters = [[ids[i] for i in group] for group in groups if len(group) > 1]

        logger.info(
            "Phase 5b: found %d argument clusters (threshold=%.2f).",
            len(clusters),
            self.similarity_threshold,
        )
        return clusters


def _format_cluster_summary(cluster_nodes: list[TheoryAtom | L2Entity]) -> dict[str, Any]:
    """Format cluster members into a structured state block for decision evaluation.

    Parameters
    ----------
    cluster_nodes : list of (TheoryAtom or L2Entity)
        Nodes belonging to the candidate cluster.

    Returns
    -------
    dict of str to Any
        Structured state dictionary.
    """
    items = []
    for node in cluster_nodes[:10]:
        if hasattr(node, "text"):
            items.append({
                "id": node.id,
                "type": getattr(node, "component_type", "TheoryAtom"),
                "text": node.text,
                "epistemic_status": getattr(node, "epistemic_status", None),
                "scope_type": getattr(node, "scope_type", None),
            })
        elif hasattr(node, "name"):
            items.append({
                "id": node.id,
                "type": getattr(node, "label", "L2Entity"),
                "name": node.name,
                "envelope": getattr(node, "textual_envelope", "") or "",
            })
        else:
            items.append({"id": getattr(node, "id", "unknown"), "summary": str(node)})
    return {
        "cluster_node_count": len(cluster_nodes),
        "cluster_members": items,
    }


class InterDocumentClusterVerifier:
    """Calibrated decision oracle for inter-document theory cluster gating.

    Parameters
    ----------
    decision_engine : DecisionEngine
        System 1 decision engine.
    confidence_threshold : float, default 0.85
        Empirical accuracy threshold for confirming cluster fusion.
    conformal_alpha : float, default 0.05
        Conformal error significance level.
    audit_rate : float, default 0.02
        Stochastic false-negative audit rate (e.g. 2%).
    prompt_bundle : StructuredPromptBundle or None, default None
        Optional custom prompt bundle.
    calibrator : ConformalCalibrator or None, default None
        Optional pre-calibrated conformal prediction engine.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
        audit_rate: float = 0.02,
        prompt_bundle: StructuredPromptBundle | None = None,
        calibrator: ConformalCalibrator | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.confidence_threshold = confidence_threshold
        self.conformal_alpha = conformal_alpha
        self.audit_rate = audit_rate
        self.prompt_bundle = prompt_bundle
        self.calibrator = calibrator

    @classmethod
    def from_config(
        cls,
        config: Any,
        decision_engine: DecisionEngine,
        prompt_bundle: StructuredPromptBundle | None = None,
        calibrator: ConformalCalibrator | None = None,
    ) -> InterDocumentClusterVerifier:
        """Construct InterDocumentClusterVerifier from configuration.

        Parameters
        ----------
        config : FusionGatingConfig
            Fusion gating configuration.
        decision_engine : DecisionEngine
            Calibrated decision engine.
        prompt_bundle : StructuredPromptBundle or None, default None
            Optional prompt bundle.
        calibrator : ConformalCalibrator or None, default None
            Optional pre-calibrated conformal prediction engine.

        Returns
        -------
        InterDocumentClusterVerifier
            Configured verifier instance.
        """
        return cls(
            decision_engine=decision_engine,
            confidence_threshold=config.confidence_threshold,
            conformal_alpha=config.conformal_alpha,
            audit_rate=config.audit_rate,
            prompt_bundle=prompt_bundle,
            calibrator=calibrator,
        )

    async def verify(
        self,
        cluster_nodes: list[TheoryAtom | L2Entity],
    ) -> tuple[bool, float, list[str]]:
        """Verify semantic coherence and equivalence of an inter-document cluster.

        Parameters
        ----------
        cluster_nodes : list of (TheoryAtom or L2Entity)
            Candidate cluster nodes.

        Returns
        -------
        tuple of (bool, float, list of str)
            Tuple containing (is_confirmed, empirical_accuracy, prediction_set).
        """
        if not cluster_nodes:
            return False, 0.0, []

        state = _format_cluster_summary(cluster_nodes)
        question = (
            self.prompt_bundle.decision_template
            if self.prompt_bundle and self.prompt_bundle.decision_template
            else DECISION_THEORY_FUSION_QUESTION
        )
        options = (
            self.prompt_bundle.decision_criteria
            if self.prompt_bundle and self.prompt_bundle.decision_criteria
            else DECISION_THEORY_FUSION_CRITERIA
        )

        score = await self.decision_engine.evaluate_choice(
            state=state,
            question=question,
            options=options,
            alpha=self.conformal_alpha,
        )

        if self.calibrator is not None:
            pred_set = self.calibrator.predict_set(score, alpha=self.conformal_alpha)
        else:
            pred_set = score.prediction_set or ([str(score.selected_option)] if score.selected_option is not None else [])

        selected = str(score.selected_option) if score.selected_option is not None else ""
        emp_acc = score.empirical_accuracy

        has_equivalent = ("EQUIVALENT_FUSION" in pred_set or selected == "EQUIVALENT_FUSION")
        is_confirmed = has_equivalent and (len(pred_set) == 1 or emp_acc >= self.confidence_threshold)

        if len(pred_set) > 1:
            action_taken = "active_learning"
        elif is_confirmed:
            action_taken = "fast_exit"
        else:
            action_taken = "rejected"

        get_event_emitter().emit(
            DecisionGatingTriggered(
                gate_name="fusion_gate",
                action_taken=action_taken,
                empirical_accuracy=emp_acc,
                threshold=self.confidence_threshold,
                prediction_set_size=len(pred_set),
            )
        )

        logger.debug(
            "InterDocumentClusterVerifier: nodes=%d -> selected=%s, pred_set=%s, emp_acc=%.3f, action=%s",
            len(cluster_nodes),
            selected,
            pred_set,
            emp_acc,
            action_taken,
        )

        return is_confirmed, emp_acc, pred_set

    async def should_fuse(
        self,
        cluster_nodes: list[TheoryAtom | L2Entity],
    ) -> bool:
        """Evaluate whether a candidate cluster should be merged or fused.

        Applies conformal prediction verification, followed by stochastic audit
        if the cluster was initially rejected.

        Parameters
        ----------
        cluster_nodes : list of (TheoryAtom or L2Entity)
            Candidate cluster nodes.

        Returns
        -------
        bool
            True if verified or passed by stochastic audit; False otherwise.
        """
        import random

        if len(cluster_nodes) < 2:
            return True

        is_confirmed, emp_acc, pred_set = await self.verify(cluster_nodes)
        if is_confirmed:
            return True

        if random.random() < self.audit_rate:
            get_event_emitter().emit(
                DecisionGatingTriggered(
                    gate_name="fusion_gate",
                    action_taken="stochastic_audit",
                    empirical_accuracy=emp_acc,
                    threshold=self.confidence_threshold,
                    prediction_set_size=len(pred_set),
                )
            )
            return True

        return False

    async def filter_clusters(
        self,
        cluster_ids: list[list[str]],
        graph_store: Any,
    ) -> list[list[str]]:
        """Filter candidate cluster groupings against calibrated fusion decisions.

        Parameters
        ----------
        cluster_ids : list of list of str
            Raw community or component entity/atom IDs.
        graph_store : FusionGraph
            Graph store to query node metadata from.

        Returns
        -------
        list of list of str
            Verified clusters passing gating or stochastic audit.
        """
        atoms = await graph_store.get_theory_atoms()
        atom_map = {a.id: a for a in atoms}
        verified_clusters: list[list[str]] = []

        for cluster in cluster_ids:
            nodes = [atom_map[cid] for cid in cluster if cid in atom_map]
            if await self.should_fuse(nodes):
                verified_clusters.append(cluster)

        return verified_clusters


async def verify_inter_document_cluster(
    cluster_nodes: list[TheoryAtom | L2Entity],
    decision_engine: DecisionEngine,
    prompt_bundle: StructuredPromptBundle | None = None,
    alpha: float = 0.05,
    threshold: float = 0.85,
    calibrator: ConformalCalibrator | None = None,
) -> tuple[bool, float, list[str]]:
    """Functional convenience wrapper around :class:`InterDocumentClusterVerifier`."""
    verifier = InterDocumentClusterVerifier(
        decision_engine=decision_engine,
        confidence_threshold=threshold,
        conformal_alpha=alpha,
        prompt_bundle=prompt_bundle,
        calibrator=calibrator,
    )
    return await verifier.verify(cluster_nodes)
