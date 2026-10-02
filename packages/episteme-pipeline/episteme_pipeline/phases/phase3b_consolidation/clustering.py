"""Borderline cluster verification and canonical representative election (ISSUE-045).

This module provides Jev decision oracles for Phase 3b Latent Graph Consolidation:
1. :func:`verify_borderline_pair`: Semantically guards against over-merging in the
   ambiguous vector similarity band (0.75 <= cosine <= 0.88).
2. :func:`elect_canonical_representative`: Elects the standard academic surface
   form from candidate cluster entities using calibrated categorical choice.
"""

from __future__ import annotations

import logging
from typing import Any

from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.prompts.default_prompts import (
    DECISION_BORDERLINE_MERGE_CRITERIA,
    DECISION_BORDERLINE_MERGE_QUESTION,
    DECISION_CANONICAL_ELECTION_QUESTION,
)
from episteme_pipeline.protocols.decision import DecisionEngine

logger = logging.getLogger(__name__)


def _format_entity_summary(entity: L2Entity, relation_signatures: set[str] | None = None) -> str:
    """Format an entity into a summary for decision evaluation.

    Parameters
    ----------
    entity : L2Entity
        Entity to format.
    relation_signatures : set of str or None, default None
        Optional 1-hop relation signatures.

    Returns
    -------
    str
        Summary string.
    """
    rels = sorted(list(relation_signatures))[:10] if relation_signatures else []
    rel_str = ", ".join(rels) if rels else "None"
    envelope = entity.textual_envelope or ""
    return (
        f"Name: {entity.name}\n"
        f"Type: {entity.label}\n"
        f"Envelope: {envelope}\n"
        f"1-Hop Relational Neighborhood: {rel_str}"
    )


class BorderlinePairVerifier:
    """Evaluates whether borderline entity pairs should be merged in consolidation.

    Uses calibrated decision engine with conformal prediction sets to protect
    against over-merging conceptually distinct entities in the ambiguous similarity band.

    Parameters
    ----------
    decision_engine : DecisionEngine
        Calibrated decision engine for categorical choices.
    confidence_threshold : float, default 0.80
        Empirical accuracy threshold for confirming borderline merges.
    conformal_alpha : float, default 0.05
        Conformal significance level for prediction set coverage.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        confidence_threshold: float = 0.80,
        conformal_alpha: float = 0.05,
    ) -> None:
        self.decision_engine = decision_engine
        self.confidence_threshold = confidence_threshold
        self.conformal_alpha = conformal_alpha

    @classmethod
    def from_config(
        cls,
        config: Any,
        decision_engine: DecisionEngine,
    ) -> BorderlinePairVerifier:
        """Construct BorderlinePairVerifier from configuration.

        Parameters
        ----------
        config : ConsolidationVerificationConfig
            Verification configuration sub-model.
        decision_engine : DecisionEngine
            Calibrated decision engine.

        Returns
        -------
        BorderlinePairVerifier
            Configured verifier instance.
        """
        return cls(
            decision_engine=decision_engine,
            confidence_threshold=config.confidence_threshold,
            conformal_alpha=config.conformal_alpha,
        )

    async def verify(
        self,
        entity_a: L2Entity,
        entity_b: L2Entity,
        relation_signatures_a: set[str] | None = None,
        relation_signatures_b: set[str] | None = None,
    ) -> tuple[str, float, list[str]]:
        """Verify whether candidate pair (entity_a, entity_b) should be merged.

        Parameters
        ----------
        entity_a : L2Entity
            First candidate entity.
        entity_b : L2Entity
            Second candidate entity.
        relation_signatures_a : set of str or None, default None
            1-hop relation signatures for entity A.
        relation_signatures_b : set of str or None, default None
            1-hop relation signatures for entity B.

        Returns
        -------
        tuple of (str, float, list of str)
            Tuple of (selected_option, empirical_accuracy, prediction_set).
        """
        summary_a = _format_entity_summary(entity_a, relation_signatures_a)
        summary_b = _format_entity_summary(entity_b, relation_signatures_b)

        state = {
            "entity_a": summary_a,
            "entity_b": summary_b,
        }

        score = await self.decision_engine.evaluate_choice(
            state=state,
            question=DECISION_BORDERLINE_MERGE_QUESTION,
            options=DECISION_BORDERLINE_MERGE_CRITERIA,
            alpha=self.conformal_alpha,
        )

        selected = str(score.selected_option) if score.selected_option is not None else "DISTINCT_SEPARATE"
        pred_set = score.prediction_set or [selected]
        emp_acc = score.empirical_accuracy

        is_singleton_identical = (pred_set == ["IDENTICAL_MERGE"])
        is_high_confidence = (selected == "IDENTICAL_MERGE" and emp_acc >= self.confidence_threshold)
        approved_merge = is_singleton_identical or is_high_confidence

        action_taken = "merge_approved" if approved_merge else "merge_aborted"

        get_event_emitter().emit(
            DecisionGatingTriggered(
                gate_name="borderline_merge_gate",
                action_taken=action_taken,
                empirical_accuracy=emp_acc,
                threshold=self.confidence_threshold,
                prediction_set_size=len(pred_set),
            )
        )

        logger.debug(
            "BorderlinePairVerifier: %s vs %s -> %s (pred_set=%s, emp_acc=%.3f, action=%s)",
            entity_a.name,
            entity_b.name,
            selected,
            pred_set,
            emp_acc,
            action_taken,
        )

        return selected, emp_acc, pred_set


class CanonicalRepresentativeElector:
    """Elects the canonical scholarly surface form for an entity cluster.

    Uses calibrated decision engine categorical choice when available, falling back
    to groundedness heuristics (source chunk count and text length).

    Parameters
    ----------
    decision_engine : DecisionEngine or None, default None
        Optional calibrated decision engine for System 1 selection.
    """

    def __init__(self, decision_engine: DecisionEngine | None = None) -> None:
        self.decision_engine = decision_engine

    async def elect(self, cluster_entities: list[L2Entity]) -> L2Entity:
        """Elect the canonical representative from candidate cluster entities.

        Parameters
        ----------
        cluster_entities : list of L2Entity
            Candidate entities belonging to the same cluster.

        Returns
        -------
        L2Entity
            The elected canonical representative entity.
        """
        if not cluster_entities:
            raise ValueError("Cannot elect canonical representative from an empty cluster.")

        if len(cluster_entities) == 1:
            return cluster_entities[0]

        if self.decision_engine is not None:
            options: dict[str, str] = {}
            id_to_entity: dict[str, L2Entity] = {}

            for idx, e in enumerate(cluster_entities):
                opt_key = f"candidate_{idx}_{e.id}"
                id_to_entity[opt_key] = e
                desc = (e.textual_envelope or e.name)[:150]
                options[opt_key] = f"Name: {e.name}. Context: {desc}"

            state = {
                "cluster_size": len(cluster_entities),
                "candidates": [
                    {"name": e.name, "occurrences": len(e.source_chunk_ids), "envelope": e.textual_envelope or ""}
                    for e in cluster_entities
                ],
            }

            try:
                score = await self.decision_engine.evaluate_choice(
                    state=state,
                    question=DECISION_CANONICAL_ELECTION_QUESTION,
                    options=options,
                )

                selected_key = str(score.selected_option) if score.selected_option is not None else None
                if selected_key in id_to_entity:
                    return id_to_entity[selected_key]

                for e in cluster_entities:
                    if selected_key and (e.name.lower() == selected_key.lower() or e.id == selected_key):
                        return e

            except Exception as exc:
                logger.warning(
                    "Canonical election via decision engine failed: %s; using heuristic fallback.",
                    exc,
                )

        # Heuristic fallback: entity with the most source chunks, then longest name
        sorted_entities = sorted(
            cluster_entities,
            key=lambda e: (len(e.source_chunk_ids), len(e.name)),
            reverse=True,
        )
        return sorted_entities[0]


async def verify_borderline_pair(
    entity_a: L2Entity,
    entity_b: L2Entity,
    decision_engine: DecisionEngine,
    relation_signatures_a: set[str] | None = None,
    relation_signatures_b: set[str] | None = None,
    alpha: float = 0.05,
    threshold: float = 0.80,
) -> tuple[str, float, list[str]]:
    """Functional convenience wrapper around :class:`BorderlinePairVerifier`."""
    verifier = BorderlinePairVerifier(
        decision_engine=decision_engine,
        confidence_threshold=threshold,
        conformal_alpha=alpha,
    )
    return await verifier.verify(
        entity_a=entity_a,
        entity_b=entity_b,
        relation_signatures_a=relation_signatures_a,
        relation_signatures_b=relation_signatures_b,
    )


async def elect_canonical_representative(
    cluster_entities: list[L2Entity],
    decision_engine: DecisionEngine | None = None,
) -> L2Entity:
    """Functional convenience wrapper around :class:`CanonicalRepresentativeElector`."""
    elector = CanonicalRepresentativeElector(decision_engine=decision_engine)
    return await elector.elect(cluster_entities)
