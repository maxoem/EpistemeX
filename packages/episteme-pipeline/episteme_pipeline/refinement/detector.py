"""Deterministic L4/L3 -> L2/L1 epistemic deficit detector (ISSUE-053).

Analyzes finalized Phase 4/6 TheoryNet graphs and TheoreticalEnrichment
cluster assessments using schema partitions, :math:`Z_1` empirical-base
reachability, ``epistemetrics`` centrality and community structure, and
structuralist tenability metrics (:math:`TS_{local}`, :math:`TS_{edge}`) to
emit prioritized :class:`~episteme_pipeline.contracts.domain.EpistemicDeficit`
signals for closed-loop refinement.
"""

from __future__ import annotations

import logging
from typing import Any

from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    EpistemicStateView,
)
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import EpistemicDeficit
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import EpistemicDeficitDetected
from episteme_pipeline.refinement._detector_analysis import analyze_detector_state
from episteme_pipeline.refinement._shared import resolve_curation_ledger
from episteme_pipeline.refinement._sub_detectors import (
    EnthymemeGapSubDetector,
    PolysemyCollisionSubDetector,
    UngroundedAxiomSubDetector,
)
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

logger = logging.getLogger(__name__)


class TheoryNetDeficitDetector:
    """Deterministic epistemic deficit detector over L1–L4 TheoryNet state.

    Composes three single-responsibility detectors implementing ISSUE-053:

    1. ``ENTHYMEME_GAP``: ``A``-partition claims with centrality meeting
       ``enthymeme_min_centrality`` that lack incoming positive support or a
       valid :math:`Z_1` grounding path from ``B``-partition observations.
    2. ``POLYSEMY_COLLISION``: ``L2Entity`` or ``TheoryAtom`` hubs bridging
       incompatible theory clusters, communities, conceptions, or conflicting
       support/attack edges with ``controversy_volatility >=
       polysemy_volatility_threshold`` or ``TS_edge <
       polysemy_edge_tenability_threshold``.
    3. ``UNGROUNDED_AXIOM``: ``A``-partition axioms or empirical clusters with
       ``TS_local < ungrounded_local_tenability_threshold``, failed tenability
       evaluation (``is_tenable == False``, local anomalies, missing ``M_pp``
       observation dimensions), or missing observational base.

    Parameters
    ----------
    config : HermeneuticRefinementConfig or None, optional
        Default refinement thresholds and cycle caps.
    schema : SchemaConfig or None, optional
        Schema configuration specifying A/B partitions and relation polarities.
    detected_in_phase : str or None, optional
        Optional fixed phase tag recorded on emitted deficits and events. When
        ``None``, resolves to ``"theoretical_enrichment"`` if
        ``state.theoretical_enrichments`` is non-empty, else ``"phase6"``.

    References
    ----------
    .. [1] Pan, S., Luo, L., Wang, Y., Chen, C., Wang, J., & Wu, X. (2024).
       Unifying Large Language Models and Knowledge Graphs: A Roadmap. IEEE TKDE.
    .. [2] Schurz, G. (2014). Philosophy of Science: A Unified Approach.
       Routledge.
    """

    def __init__(
        self,
        *,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig | None = None,
        detected_in_phase: str | None = None,
    ) -> None:
        self.config = config or HermeneuticRefinementConfig()
        self.schema = schema or DEFAULT_SCHEMA
        self.detected_in_phase = detected_in_phase
        self._enthymeme_detector = EnthymemeGapSubDetector()
        self._polysemy_detector = PolysemyCollisionSubDetector(schema=self.schema)
        self._ungrounded_detector = UngroundedAxiomSubDetector()

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            Structured fingerprint over detector thresholds and canonical schema
            partition/polarity definitions.
        """
        return {
            "class": self.__class__.__name__,
            "enthymeme_min_centrality": self.config.enthymeme_min_centrality,
            "polysemy_edge_tenability_threshold": self.config.polysemy_edge_tenability_threshold,
            "polysemy_volatility_threshold": self.config.polysemy_volatility_threshold,
            "ungrounded_local_tenability_threshold": self.config.ungrounded_local_tenability_threshold,
            "max_deficits_per_cycle": self.config.max_deficits_per_cycle,
            "detected_in_phase": self.detected_in_phase,
            "component_partitions": dict(sorted(self.schema.component_partitions.items())),
            "relation_polarities": dict(sorted(self.schema.relation_polarities.items())),
        }

    def detect_deficits(
        self,
        state: EpistemicStateView,
        *,
        refinement_pass: int = 0,
        config: HermeneuticRefinementConfig | None = None,
        context: ArtifactExecutionContext | None = None,
    ) -> list[EpistemicDeficit]:
        """Detect, rank, cap, and emit ``EpistemicDeficit`` signals over ``state``.

        Parameters
        ----------
        state : EpistemicStateView
            Cumulative epistemic state across L1–L4 layers and enrichments.
        refinement_pass : int, default 0
            Zero-based refinement pass producing these deficit signals.
        config : HermeneuticRefinementConfig or None, optional
            Optional per-call threshold override.
        context : ArtifactExecutionContext or None, optional
            Optional execution context providing ``run_id`` and curation ledger.

        Returns
        -------
        list of EpistemicDeficit
            Deterministically ordered, capped list of epistemic deficits sorted
            by descending severity.
        """
        cfg = config or self.config
        phase_label = (
            self.detected_in_phase
            if self.detected_in_phase is not None
            else (
                "theoretical_enrichment"
                if state.theoretical_enrichments
                else "phase6"
            )
        )
        curation_ledger: EpistemicCurationLedger | None = resolve_curation_ledger(
            context
        )

        analysis = analyze_detector_state(state, self.schema)
        if not analysis.atoms:
            return []

        raw_deficits: list[EpistemicDeficit] = [
            *self._enthymeme_detector.detect(
                analysis,
                cfg=cfg,
                phase_label=phase_label,
                refinement_pass=refinement_pass,
            ),
            *self._polysemy_detector.detect(
                state,
                analysis,
                cfg=cfg,
                phase_label=phase_label,
                refinement_pass=refinement_pass,
                curation_ledger=curation_ledger,
            ),
            *self._ungrounded_detector.detect(
                state.theoretical_enrichments,
                analysis,
                cfg=cfg,
                phase_label=phase_label,
                refinement_pass=refinement_pass,
            ),
        ]

        deduped_by_id: dict[str, EpistemicDeficit] = {}
        for deficit in raw_deficits:
            existing = deduped_by_id.get(deficit.deficit_id)
            if existing is None or deficit.severity > existing.severity:
                deduped_by_id[deficit.deficit_id] = deficit

        ranked = sorted(
            deduped_by_id.values(),
            key=lambda d: (-float(d.severity), d.deficit_kind.value, d.deficit_id),
        )
        capped = ranked[: cfg.max_deficits_per_cycle]

        self._emit_deficit_events(capped, phase_label=phase_label, context=context)
        logger.info(
            "TheoryNetDeficitDetector pass=%d detected=%d returned=%d (cap=%d)",
            refinement_pass,
            len(ranked),
            len(capped),
            cfg.max_deficits_per_cycle,
        )
        return capped

    @staticmethod
    def _emit_deficit_events(
        deficits: list[EpistemicDeficit],
        *,
        phase_label: str,
        context: ArtifactExecutionContext | None,
    ) -> None:
        """Publish :class:`EpistemicDeficitDetected` domain events for deficits."""
        if not deficits:
            return
        emitter = get_event_emitter()
        run_id = context.run_id if context is not None and context.run_id else None
        for deficit in deficits:
            emitter.emit(
                EpistemicDeficitDetected(
                    run_id=run_id,
                    phase=phase_label,
                    deficit_id=deficit.deficit_id,
                    deficit_kind=deficit.deficit_kind.value,
                    severity=deficit.severity,
                    target_chunk_ids=list(deficit.target_chunk_ids),
                    target_entity_ids=list(deficit.target_entity_ids),
                    target_atom_ids=list(deficit.target_atom_ids),
                    target_relation_ids=list(deficit.target_relation_ids),
                    theory_id=deficit.theory_id,
                    refinement_pass=deficit.refinement_pass,
                    rationale=deficit.rationale,
                )
            )


__all__ = ["TheoryNetDeficitDetector"]
