"""Closed-loop hermeneutic refinement coordinator (ISSUE-053).

Implements :class:`ClosedLoopRefinementCoordinator`, satisfying
:class:`~episteme_pipeline.protocols.refinement.HermeneuticRefinementCoordinator`,
:class:`~episteme_pipeline.protocols.refinement.TargetedRefinementPort`, and
:class:`~episteme_pipeline.protocols.fingerprint.Fingerprintable`.

Executes bounded top-down feedback cycles (``1..max_refinement_cycles``) over an
:class:`~episteme_pipeline.artifacts.execution.ArtifactCollection`:

1. Detects epistemic deficits (``ENTHYMEME_GAP``, ``POLYSEMY_COLLISION``,
   ``UNGROUNDED_AXIOM``) via an injected :class:`EpistemicDeficitDetector`.
2. Dispatches prioritized deficits to localized refinement ports
   (:class:`TheoryGuidedPremiseRecoverer`, :class:`TargetedConceptSplitter`,
   :class:`LocalizedAxiomGrounder`).
3. Applies non-empty :class:`RefinementDelta` outputs as localized
   identity-keyed :class:`ArtifactEnvelope` overlays without invalidating or
   re-processing unaffected corpus subgraphs.
4. Persists ``cannot_link_pairs`` onto the run's :class:`EpistemicCurationLedger`,
   runs optional localized enrichment re-scoring and TheoryNet D-QBAF
   equilibrium reconvergence, stamps ``refinement_pass`` lineage on
   :class:`RunManifest` and :class:`RunPhaseRecord`, and emits lifecycle events.
"""

from __future__ import annotations

import logging
import math
import time
from collections import Counter, deque
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_epistemic_deficit_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicDeficitArtifactsView,
    EpistemicStateView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactPayload,
    ArtifactProvenance,
    TheoreticalEnrichmentArtifact,
)
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    RefinementCycleCompleted,
    RefinementCycleStarted,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.refinement import (
    EpistemicDeficitDetector,
    LocalizedAxiomGrounder,
    TargetedConceptSplitter,
    TheoryGuidedPremiseRecoverer,
    ensure_deficit_detector,
)
from episteme_pipeline.runs.fingerprints import fingerprint_method, stable_fingerprint
from episteme_pipeline.runs.models import RunPhaseRecord, RunStatus
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.post_processing.theoretical_enrichment.runner import (
        TheoreticalEnrichmentRunner,
    )
    from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector

logger = logging.getLogger(__name__)


def _dedup_preserve_order(items: Iterable[str]) -> list[str]:
    """Return unique non-empty strings while preserving first-seen order.

    Parameters
    ----------
    items : Iterable of str
        Input sequence of string identifiers.

    Returns
    -------
    list of str
        Deduplicated non-empty identifiers.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _deficit_signature(deficit: EpistemicDeficit) -> str:
    """Compute a deterministic signature distinguishing genuinely new anomalies.

    Parameters
    ----------
    deficit : EpistemicDeficit
        Candidate epistemic deficit signal.

    Returns
    -------
    str
        SHA-256 hex digest capturing deficit identity, targets, and anomaly cues.
    """
    anomalies_raw = deficit.theory_lens.get("anomalies", [])
    conflicts_raw = deficit.theory_lens.get("conflict_signals", [])
    missing_raw = deficit.theory_lens.get("missing_dimensions", [])
    return stable_fingerprint(
        {
            "deficit_id": deficit.deficit_id,
            "deficit_kind": deficit.deficit_kind.value,
            "target_chunk_ids": sorted(deficit.target_chunk_ids),
            "target_entity_ids": sorted(deficit.target_entity_ids),
            "target_atom_ids": sorted(deficit.target_atom_ids),
            "target_relation_ids": sorted(deficit.target_relation_ids),
            "theory_id": deficit.theory_id,
            "anomalies": sorted(str(a) for a in anomalies_raw)
            if isinstance(anomalies_raw, list)
            else str(anomalies_raw),
            "conflict_signals": sorted(str(c) for c in conflicts_raw)
            if isinstance(conflicts_raw, list)
            else str(conflicts_raw),
            "missing_dimensions": sorted(str(m) for m in missing_raw)
            if isinstance(missing_raw, list)
            else str(missing_raw),
        }
    )


def _float_differs(val_a: float | None, val_b: float | None, tol: float = 1e-6) -> bool:
    """Compare two optional floats using a numerical convergence tolerance.

    Parameters
    ----------
    val_a : float or None
        First optional scalar value.
    val_b : float or None
        Second optional scalar value.
    tol : float, default 1e-6
        Absolute tolerance under which values are treated as identical.

    Returns
    -------
    bool
        ``True`` if one is ``None`` and the other is not, or if they differ
        by more than ``tol``.
    """
    if val_a is None and val_b is None:
        return False
    if val_a is None or val_b is None:
        return True
    if math.isnan(val_a) and math.isnan(val_b):
        return False
    return abs(float(val_a) - float(val_b)) > tol


def _theory_atom_changed(before: TheoryAtom | None, after: TheoryAtom) -> bool:
    """Determine whether a ``TheoryAtom`` changed meaningfully after re-convergence.

    Parameters
    ----------
    before : TheoryAtom or None
        Prior atom state before re-projection, or ``None`` if newly introduced.
    after : TheoryAtom
        Atom state after localized enrichment or TheoryNet re-projection.

    Returns
    -------
    bool
        ``True`` if any score or structural field changed beyond tolerance.
    """
    if before is None:
        return True
    if (
        _float_differs(before.modal_prior, after.modal_prior)
        or _float_differs(before.local_tenability, after.local_tenability)
        or _float_differs(before.equilibrium_strength, after.equilibrium_strength)
        or _float_differs(before.controversy_volatility, after.controversy_volatility)
        or _float_differs(before.confidence, after.confidence)
    ):
        return True
    return (
        before.text != after.text
        or before.component_type != after.component_type
        or before.source_chunk_id != after.source_chunk_id
        or before.entity_ids != after.entity_ids
        or before.parameters != after.parameters
        or before.measurements != after.measurements
        or before.tenability != after.tenability
        or before.intensional_mode != after.intensional_mode
        or before.attributed_to != after.attributed_to
        or before.resolver_type != after.resolver_type
    )


def _theory_relation_changed(
    before: TheoryRelation | None, after: TheoryRelation
) -> bool:
    """Determine whether a ``TheoryRelation`` changed meaningfully after re-convergence.

    Parameters
    ----------
    before : TheoryRelation or None
        Prior relation state before re-projection, or ``None`` if newly introduced.
    after : TheoryRelation
        Relation state after localized enrichment or TheoryNet re-projection.

    Returns
    -------
    bool
        ``True`` if any score, admissibility flag, or structural field changed.
    """
    if before is None:
        return True
    if (
        _float_differs(before.weight, after.weight)
        or _float_differs(before.edge_tenability, after.edge_tenability)
        or _float_differs(before.inferential_warrant, after.inferential_warrant)
        or _float_differs(before.active_weight, after.active_weight)
        or _float_differs(before.effective_weight, after.effective_weight)
        or _float_differs(before.confidence, after.confidence)
        or _float_differs(before.calibrated_confidence, after.calibrated_confidence)
    ):
        return True
    return (
        before.is_admissible != after.is_admissible
        or before.relation_type != after.relation_type
        or before.source_id != after.source_id
        or before.target_id != after.target_id
        or before.effective_premise_ids != after.effective_premise_ids
        or before.undercuts_relation_id != after.undercuts_relation_id
        or before.scope != after.scope
    )


def _relation_lookup_key(rel: TheoryRelation) -> str:
    """Return a stable lookup key distinguishing pairwise and reified relations.

    Parameters
    ----------
    rel : TheoryRelation
        Theory relation domain contract.

    Returns
    -------
    str
        Canonical relation identifier string.
    """
    if (
        rel.has_conjunctive_premises
        or rel.undercuts_relation_id is not None
        or rel.id is not None
    ):
        return rel.relation_id
    return f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"


def _connected_component_atoms(
    seed_atom_ids: set[str],
    atoms: Sequence[TheoryAtom],
    relations: Sequence[TheoryRelation],
) -> set[str]:
    """Expand seed atom IDs across undirected theory relation connectivity.

    Parameters
    ----------
    seed_atom_ids : set of str
        Initial atom identifiers affected by refinement deltas.
    atoms : Sequence of TheoryAtom
        Active theory atoms in the current epistemic state.
    relations : Sequence of TheoryRelation
        Active theory relations in the current epistemic state.

    Returns
    -------
    set of str
        All atom identifiers belonging to weakly connected components touching
        ``seed_atom_ids``.
    """
    known_atoms = {a.id for a in atoms}
    active_seeds = {aid for aid in seed_atom_ids if aid in known_atoms}
    if not active_seeds:
        return set()

    adj: dict[str, set[str]] = {}
    for rel in relations:
        endpoints = [pid for pid in rel.effective_premise_ids if pid in known_atoms]
        if rel.target_id in known_atoms:
            endpoints.append(rel.target_id)
        for src in endpoints:
            bucket = adj.setdefault(src, set())
            for dst in endpoints:
                if dst != src:
                    bucket.add(dst)

    visited = set(active_seeds)
    queue: deque[str] = deque(sorted(active_seeds))
    while queue:
        curr = queue.popleft()
        for nbr in sorted(adj.get(curr, ())):
            if nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)
    return visited


class ClosedLoopRefinementCoordinator:
    """Coordinator executing bounded top-down hermeneutic refinement cycles.

    Implements :class:`HermeneuticRefinementCoordinator`,
    :class:`TargetedRefinementPort`, and :class:`Fingerprintable`. Coordinates
    deficit detection, dispatch to localized refinement ports, identity-keyed
    overlay construction on :class:`ArtifactCollection`, curation ledger
    ``cannot_link`` updates, localized enrichment/TheoryNet re-convergence,
    and manifest/event lineage tracking.

    Parameters
    ----------
    detector : EpistemicDeficitDetector
        Top-down epistemic deficit detector inspecting cumulative L1–L4 state.
    premise_recoverer : TheoryGuidedPremiseRecoverer or None, optional
        Handler port resolving ``ENTHYMEME_GAP`` deficits.
    concept_splitter : TargetedConceptSplitter or None, optional
        Handler port resolving ``POLYSEMY_COLLISION`` deficits.
    axiom_grounder : LocalizedAxiomGrounder or None, optional
        Handler port resolving ``UNGROUNDED_AXIOM`` deficits.
    theorynet_projector : TheoryNetProjector or None, optional
        Optional D-QBAF TheoryNet projector re-converging justification degrees
        on affected subgraphs after refinement deltas are applied.
    enrichment_runner : TheoreticalEnrichmentRunner or None, optional
        Optional localized enrichment post-processor re-evaluating affected
        empirical clusters after grounding or concept splits.
    config : HermeneuticRefinementConfig or None, optional
        Default refinement configuration; defaults to
        :class:`HermeneuticRefinementConfig`.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.

    Raises
    ------
    TypeError
        If ``detector`` does not satisfy :class:`EpistemicDeficitDetector`, or
        any provided refinement handler fails its protocol check.
    """

    def __init__(
        self,
        detector: EpistemicDeficitDetector,
        premise_recoverer: TheoryGuidedPremiseRecoverer | None = None,
        concept_splitter: TargetedConceptSplitter | None = None,
        axiom_grounder: LocalizedAxiomGrounder | None = None,
        theorynet_projector: TheoryNetProjector | None = None,
        enrichment_runner: TheoreticalEnrichmentRunner | None = None,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
    ) -> None:
        normalized_detector = ensure_deficit_detector(detector)
        if normalized_detector is None:
            raise TypeError(
                "ClosedLoopRefinementCoordinator requires a non-None "
                "EpistemicDeficitDetector implementation."
            )
        if premise_recoverer is not None and not isinstance(
            premise_recoverer, TheoryGuidedPremiseRecoverer
        ):
            raise TypeError(
                f"{type(premise_recoverer).__name__} does not satisfy the "
                "TheoryGuidedPremiseRecoverer protocol."
            )
        if concept_splitter is not None and not isinstance(
            concept_splitter, TargetedConceptSplitter
        ):
            raise TypeError(
                f"{type(concept_splitter).__name__} does not satisfy the "
                "TargetedConceptSplitter protocol."
            )
        if axiom_grounder is not None and not isinstance(
            axiom_grounder, LocalizedAxiomGrounder
        ):
            raise TypeError(
                f"{type(axiom_grounder).__name__} does not satisfy the "
                "LocalizedAxiomGrounder protocol."
            )

        self.detector: EpistemicDeficitDetector = normalized_detector
        self.premise_recoverer = premise_recoverer
        self.concept_splitter = concept_splitter
        self.axiom_grounder = axiom_grounder
        self.theorynet_projector = theorynet_projector
        self.enrichment_runner = enrichment_runner
        self.config: HermeneuticRefinementConfig = (
            config or HermeneuticRefinementConfig()
        )
        self.schema: SchemaConfig = schema

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration and collaborator fingerprint.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of refinement configuration, schema
            version, detector, handlers, projector, and enrichment runner.
        """
        enrichment_fp: Any = None
        if self.enrichment_runner is not None:
            if isinstance(self.enrichment_runner, Fingerprintable):
                enrichment_fp = self.enrichment_runner.fingerprint()
            elif isinstance(self.enrichment_runner, PhaseRunner):
                enrichment_fp = {
                    "class": type(self.enrichment_runner).__name__,
                    "config": self.enrichment_runner.config_fingerprint()
                    or fingerprint_method(self.enrichment_runner),
                }
            else:
                enrichment_fp = fingerprint_method(self.enrichment_runner)

        return {
            "class": self.__class__.__name__,
            "config": self.config.model_dump(mode="json"),
            "schema_version": self.schema.version,
            "detector": self.detector.fingerprint(),
            "premise_recoverer": (
                self.premise_recoverer.fingerprint()
                if self.premise_recoverer is not None
                else None
            ),
            "concept_splitter": (
                self.concept_splitter.fingerprint()
                if self.concept_splitter is not None
                else None
            ),
            "axiom_grounder": (
                self.axiom_grounder.fingerprint()
                if self.axiom_grounder is not None
                else None
            ),
            "theorynet_projector": (
                self.theorynet_projector.fingerprint()
                if isinstance(self.theorynet_projector, Fingerprintable)
                else fingerprint_method(self.theorynet_projector)
            ),
            "enrichment_runner": enrichment_fp,
        }

    def _is_handler_enabled(
        self,
        deficit_kind: EpistemicDeficitKind,
        config: HermeneuticRefinementConfig,
    ) -> bool:
        """Check whether ``config`` enables handling for ``deficit_kind``."""
        mapping = {
            EpistemicDeficitKind.ENTHYMEME_GAP: (
                config.enable_theory_guided_premise_recovery
            ),
            EpistemicDeficitKind.POLYSEMY_COLLISION: (
                config.enable_targeted_concept_split
            ),
            EpistemicDeficitKind.UNGROUNDED_AXIOM: (
                config.enable_localized_axiom_grounding
            ),
        }
        return mapping.get(deficit_kind, False)

    def _filter_actionable_deficits(
        self,
        deficits: Sequence[EpistemicDeficit],
        config: HermeneuticRefinementConfig,
        handled_signatures: dict[str, set[str]],
    ) -> list[EpistemicDeficit]:
        """Filter, deduplicate, prioritize, and cap detected epistemic deficits."""
        filtered: list[EpistemicDeficit] = []
        seen_ids: set[str] = set()
        for deficit in deficits:
            if not self._is_handler_enabled(deficit.deficit_kind, config):
                continue
            sig = _deficit_signature(deficit)
            if sig in handled_signatures.get(deficit.deficit_id, set()):
                continue
            if deficit.deficit_id in seen_ids:
                continue
            seen_ids.add(deficit.deficit_id)
            filtered.append(deficit)

        filtered.sort(
            key=lambda d: (-d.severity, d.deficit_kind.value, d.deficit_id)
        )
        return filtered[: config.max_deficits_per_cycle]

    async def refine_deficit(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Route a single epistemic deficit to its matching localized handler.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Epistemic deficit signal to resolve.
        state : EpistemicStateView
            Cumulative epistemic state view.
        context : ArtifactExecutionContext or None, optional
            Active execution context for telemetry and lineage.

        Returns
        -------
        RefinementDelta
            Localized refinement output delta (empty when no handler is bound
            for ``deficit.deficit_kind``).
        """
        if deficit.deficit_kind == EpistemicDeficitKind.ENTHYMEME_GAP:
            if self.premise_recoverer is None:
                return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)
            return await self.premise_recoverer.recover_premises(
                deficit, state, context=context
            )
        if deficit.deficit_kind == EpistemicDeficitKind.POLYSEMY_COLLISION:
            if self.concept_splitter is None:
                return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)
            return await self.concept_splitter.split_concept(
                deficit, state, context=context
            )
        if deficit.deficit_kind == EpistemicDeficitKind.UNGROUNDED_AXIOM:
            if self.axiom_grounder is None:
                return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)
            return await self.axiom_grounder.ground_axiom(
                deficit, state, context=context
            )
        return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)

    def _handler_method_name(self, deficit_kind: EpistemicDeficitKind) -> str:
        """Resolve human-readable handler method tag for provenance metadata."""
        if deficit_kind == EpistemicDeficitKind.ENTHYMEME_GAP:
            return (
                type(self.premise_recoverer).__name__
                if self.premise_recoverer is not None
                else "refinement.premise_recovery"
            )
        if deficit_kind == EpistemicDeficitKind.POLYSEMY_COLLISION:
            return (
                type(self.concept_splitter).__name__
                if self.concept_splitter is not None
                else "refinement.concept_split"
            )
        if deficit_kind == EpistemicDeficitKind.UNGROUNDED_AXIOM:
            return (
                type(self.axiom_grounder).__name__
                if self.axiom_grounder is not None
                else "refinement.axiom_grounding"
            )
        return type(self).__name__

    def _resolve_latest_artifact_id(
        self,
        collection: ArtifactCollection,
        identity_key: str,
        fallback_domain_id: str,
    ) -> str:
        """Resolve the latest ``artifact_id`` for ``identity_key`` in ``collection``."""
        existing = collection.latest_by_identity.get(identity_key)
        if existing is not None:
            return existing.artifact_id
        return f"artifact::{fallback_domain_id}"

    def _materialize_deficit_envelope(
        self,
        deficit: EpistemicDeficit,
        collection: ArtifactCollection,
        *,
        run_id: str,
        phase_name: str,
        pass_idx: int,
    ) -> tuple[ArtifactEnvelope[ArtifactPayload], bool]:
        """Materialize an :class:`EpistemicDeficitArtifact` if not already present."""
        upstream_ids: list[str] = []
        for cid in deficit.target_chunk_ids:
            upstream_ids.append(
                self._resolve_latest_artifact_id(collection, f"chunk::{cid}", cid)
            )
        for eid in deficit.target_entity_ids:
            upstream_ids.append(
                self._resolve_latest_artifact_id(
                    collection, f"linked_entity::{eid}", eid
                )
            )
        for aid in deficit.target_atom_ids:
            upstream_ids.append(
                self._resolve_latest_artifact_id(
                    collection, f"argument_component::{aid}", aid
                )
            )
        for rid in deficit.target_relation_ids:
            upstream_ids.append(
                self._resolve_latest_artifact_id(
                    collection, f"argument_relation::{rid}", rid
                )
            )

        envelope = build_epistemic_deficit_artifact(
            deficit,
            run_id=run_id,
            phase_name=phase_name,
            method=type(self.detector).__name__,
            upstream_artifact_ids=_dedup_preserve_order(upstream_ids),
            refinement_pass=pass_idx - 1,
        )
        existing = collection.latest_by_identity.get(
            envelope.identity_key or envelope.artifact_id
        )
        if existing is not None and existing.artifact_id == envelope.artifact_id:
            return existing, False
        return envelope, True

    def _record_cannot_link_constraints(
        self,
        cannot_link_pairs: Sequence[tuple[str, str]],
        context: ArtifactExecutionContext,
    ) -> None:
        """Persist ``cannot_link_pairs`` into ``context.pipeline_input.curation_ledger``."""
        if not cannot_link_pairs or context.pipeline_input is None:
            return
        ledger = context.pipeline_input.resolved_curation_ledger()
        if ledger is None:
            ledger = EpistemicCurationLedger()
        for id_a, id_b in cannot_link_pairs:
            if id_a and id_b and id_a != id_b:
                ledger.cannot_link_entities.add((id_a, id_b))
        context.pipeline_input.curation_ledger = ledger

    def _build_delta_envelopes(
        self,
        delta: RefinementDelta,
        *,
        deficit: EpistemicDeficit,
        deficit_artifact_id: str,
        collection: ArtifactCollection,
        run_id: str,
        phase_name: str,
        pass_idx: int,
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """Wrap non-empty ``RefinementDelta`` elements as localized envelopes."""
        method_name = self._handler_method_name(deficit.deficit_kind)
        envelopes: list[ArtifactEnvelope[ArtifactPayload]] = []

        entity_art_ids: dict[str, str] = {}
        atom_art_ids: dict[str, str] = {}
        chunk_art_ids: dict[str, str] = {}

        for chunk in delta.chunks:
            upstreams = [deficit_artifact_id]
            doc_key = f"document::{chunk.source_doc_id}"
            if doc_key in collection.latest_by_identity:
                upstreams.append(collection.latest_by_identity[doc_key].artifact_id)
            env = build_chunk_artifact(
                chunk,
                run_id=run_id,
                phase_name=phase_name,
                method=method_name,
                upstream_artifact_ids=_dedup_preserve_order(upstreams),
                refinement_pass=pass_idx,
                deficit_id=deficit.deficit_id,
            )
            chunk_art_ids[chunk.id] = env.artifact_id
            envelopes.append(env)

        for entity in delta.entities:
            mention_ids = [
                f"artifact::mention::{entity.id}::{cid}"
                for cid in entity.source_chunk_ids
            ]
            upstreams = [deficit_artifact_id]
            for cid in entity.source_chunk_ids:
                if cid in chunk_art_ids:
                    upstreams.append(chunk_art_ids[cid])
                elif f"chunk::{cid}" in collection.latest_by_identity:
                    upstreams.append(
                        collection.latest_by_identity[f"chunk::{cid}"].artifact_id
                    )
            env = build_linked_entity_artifact(
                entity,
                mention_ids,
                run_id=run_id,
                phase_name=phase_name,
                method=method_name,
                upstream_artifact_ids=_dedup_preserve_order(upstreams),
                refinement_pass=pass_idx,
                deficit_id=deficit.deficit_id,
            )
            entity_art_ids[entity.id] = env.artifact_id
            envelopes.append(env)

        def _entity_up(eid: str) -> str:
            if eid in entity_art_ids:
                return entity_art_ids[eid]
            return self._resolve_latest_artifact_id(
                collection, f"linked_entity::{eid}", eid
            )

        for triple in delta.local_triples:
            upstreams = [deficit_artifact_id, _entity_up(triple.subject_id), _entity_up(triple.object_id)]
            if triple.source_chunk_id:
                c_art = chunk_art_ids.get(triple.source_chunk_id)
                if c_art is not None:
                    upstreams.append(c_art)
                elif f"chunk::{triple.source_chunk_id}" in collection.latest_by_identity:
                    upstreams.append(
                        collection.latest_by_identity[
                            f"chunk::{triple.source_chunk_id}"
                        ].artifact_id
                    )
            envelopes.append(
                build_local_relation_artifact(
                    triple,
                    run_id=run_id,
                    phase_name=phase_name,
                    method=method_name,
                    upstream_artifact_ids=_dedup_preserve_order(upstreams),
                    refinement_pass=pass_idx,
                    deficit_id=deficit.deficit_id,
                )
            )

        if delta.global_triples:
            rel_dist = dict(Counter(t.predicate for t in delta.global_triples))
            for triple in delta.global_triples:
                upstreams = [
                    deficit_artifact_id,
                    _entity_up(triple.subject_id),
                    _entity_up(triple.object_id),
                ]
                envelopes.append(
                    build_global_relation_artifact(
                        triple,
                        rel_dist,
                        run_id=run_id,
                        phase_name=phase_name,
                        method=method_name,
                        upstream_artifact_ids=_dedup_preserve_order(upstreams),
                        refinement_pass=pass_idx,
                        deficit_id=deficit.deficit_id,
                    )
                )

        for atom in delta.theory_atoms:
            upstreams = [deficit_artifact_id]
            if atom.source_chunk_id in chunk_art_ids:
                upstreams.append(chunk_art_ids[atom.source_chunk_id])
            elif f"chunk::{atom.source_chunk_id}" in collection.latest_by_identity:
                upstreams.append(
                    collection.latest_by_identity[
                        f"chunk::{atom.source_chunk_id}"
                    ].artifact_id
                )
            for eid in atom.entity_ids:
                if eid in entity_art_ids:
                    upstreams.append(entity_art_ids[eid])
            env = build_theory_atom_artifact(
                atom,
                run_id=run_id,
                phase_name=phase_name,
                method=method_name,
                upstream_artifact_ids=_dedup_preserve_order(upstreams),
                refinement_pass=pass_idx,
                deficit_id=deficit.deficit_id,
            )
            atom_art_ids[atom.id] = env.artifact_id
            envelopes.append(env)

        def _atom_up(aid: str) -> str:
            if aid in atom_art_ids:
                return atom_art_ids[aid]
            return self._resolve_latest_artifact_id(
                collection, f"argument_component::{aid}", aid
            )

        for rel in delta.theory_relations:
            upstreams = [deficit_artifact_id]
            for pid in rel.effective_premise_ids:
                upstreams.append(_atom_up(pid))
            target_ref = rel.undercuts_relation_id or rel.target_id
            if rel.undercuts_relation_id is not None:
                upstreams.append(
                    self._resolve_latest_artifact_id(
                        collection, f"argument_relation::{target_ref}", target_ref
                    )
                )
            else:
                upstreams.append(_atom_up(target_ref))
            envelopes.append(
                build_theory_relation_artifact(
                    rel,
                    run_id=run_id,
                    phase_name=phase_name,
                    method=method_name,
                    upstream_artifact_ids=_dedup_preserve_order(upstreams),
                    refinement_pass=pass_idx,
                    deficit_id=deficit.deficit_id,
                )
            )

        return envelopes

    def _merge_pass_envelopes(
        self,
        pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]],
        new_envelopes: Sequence[ArtifactEnvelope[ArtifactPayload]],
    ) -> None:
        """Insert or update envelopes generated within the current refinement pass."""
        for env in new_envelopes:
            pass_envelopes_by_id[env.artifact_id] = env

    async def _run_localized_enrichment(
        self,
        working_collection: ArtifactCollection,
        context: ArtifactExecutionContext,
        *,
        affected_chunk_ids: set[str],
        affected_atom_ids: set[str],
        affected_component_atoms: set[str],
        phase_name: str,
        pass_idx: int,
        pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]],
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """Re-run enrichment strictly over affected clusters and return delta envelopes."""
        if self.enrichment_runner is None:
            return []

        full_view = Phase4ArtifactsView.from_collection(working_collection)
        all_atoms = (
            full_view.canonical_theory_atoms
            if full_view.canonical_theory_atoms
            else full_view.theory_atoms
        )
        all_relations = (
            full_view.canonical_theory_relations
            if full_view.canonical_theory_relations
            else full_view.theory_relations
        )

        direct_atom_ids = {
            a.id
            for a in all_atoms
            if a.source_chunk_id in affected_chunk_ids or a.id in affected_atom_ids
        }
        if not direct_atom_ids:
            return []

        # Include 1-hop neighbor atoms so cross-cluster edge tenabilities remain evaluable
        scope_atom_ids = set(direct_atom_ids)
        scoped_relations: list[TheoryRelation] = []
        for rel in all_relations:
            endpoints = {*rel.effective_premise_ids, rel.target_id}
            if endpoints & direct_atom_ids:
                scoped_relations.append(rel)
                scope_atom_ids.update(endpoints)

        scoped_atoms = [a for a in all_atoms if a.id in scope_atom_ids]
        localized_view = Phase4ArtifactsView(
            documents=full_view.documents,
            chunks=[c for c in full_view.chunks if c.id in affected_chunk_ids],
            entities=full_view.entities,
            local_triples=full_view.local_triples,
            entity_count_by_type=full_view.entity_count_by_type,
            global_triples=full_view.global_triples,
            relation_type_distribution=full_view.relation_type_distribution,
            theory_atoms=scoped_atoms,
            theory_relations=scoped_relations,
            fusion_decisions=full_view.fusion_decisions,
            canonical_theory_atoms=scoped_atoms,
            canonical_theory_relations=scoped_relations,
            entity_envelopes_by_id=full_view.entity_envelopes_by_id,
            entity_mentions_by_id=full_view.entity_mentions_by_id,
            theoretical_enrichments=full_view.theoretical_enrichments,
            consumed_artifact_ids=full_view.consumed_artifact_ids,
        )

        # Preserve original manifest intact until pass completion while giving
        # TheoreticalEnrichmentRunner the current pass index.
        pass_manifest = context.manifest.model_copy(update={"refinement_pass": pass_idx})
        enrichment_ctx = ArtifactExecutionContext(
            run_id=context.run_id,
            manifest=pass_manifest,
            pipeline_input=context.pipeline_input,
            previous=working_collection,
            lineage_fingerprint=context.lineage_fingerprint,
            prior_artifacts=context.prior_artifacts,
            prior_manifest=context.prior_manifest,
        )
        te_collection = await self.enrichment_runner.run(localized_view, enrichment_ctx)

        existing_enr_keys: dict[tuple[str, str], tuple[str, str]] = {}
        for env in working_collection.of_kind(
            ArtifactKind.THEORETICAL_ENRICHMENT, latest_only=True
        ):
            payload = env.payload
            if isinstance(payload, TheoreticalEnrichmentArtifact):
                ikey = env.identity_key or env.artifact_id
                base_id = ikey
                existing_enr_keys[(payload.theory_id, payload.cluster_id)] = (
                    ikey,
                    base_id,
                )

        prior_atoms_by_id = {a.id: a for a in all_atoms}
        prior_rels_by_key = {_relation_lookup_key(r): r for r in all_relations}
        emitted: list[ArtifactEnvelope[ArtifactPayload]] = []

        for env in te_collection.history:
            if env.kind == ArtifactKind.EPISTEMIC_DEFICIT:
                continue

            if env.kind == ArtifactKind.THEORETICAL_ENRICHMENT and isinstance(
                env.payload, TheoreticalEnrichmentArtifact
            ):
                enr_payload = env.payload
                cluster_chunk = enr_payload.cluster_id.removeprefix("cluster-")
                in_affected_cluster = cluster_chunk in affected_chunk_ids or any(
                    aid in affected_atom_ids for aid in enr_payload.claimant_atom_ids
                )
                if not in_affected_cluster:
                    continue

                pair_key = (enr_payload.theory_id, enr_payload.cluster_id)
                if pair_key in existing_enr_keys:
                    identity_key, base_id = existing_enr_keys[pair_key]
                    art_id = f"{base_id}::pass{pass_idx}"
                else:
                    identity_key = (
                        f"theoretical_enrichment::{enr_payload.theory_id}::{enr_payload.cluster_id}"
                    )
                    art_id = f"artifact::{identity_key}::pass{pass_idx}"

                prov = ArtifactProvenance(
                    source_chunk_id=env.provenance.source_chunk_id,
                    upstream_artifact_ids=list(env.provenance.upstream_artifact_ids),
                    refinement_pass=pass_idx,
                )
                emitted.append(
                    ArtifactEnvelope[TheoreticalEnrichmentArtifact](
                        artifact_id=art_id,
                        identity_key=identity_key,
                        kind=ArtifactKind.THEORETICAL_ENRICHMENT,
                        run_id=context.run_id,
                        phase_name=phase_name,
                        method="refinement.theoretical_enrichment",
                        provenance=prov,
                        payload=enr_payload,
                        dependency_fingerprint=stable_fingerprint(
                            {
                                "cluster_id": enr_payload.cluster_id,
                                "theory_id": enr_payload.theory_id,
                                "local_tenability": enr_payload.local_tenability,
                                "is_tenable": enr_payload.is_tenable,
                            }
                        ),
                    )
                )
            elif env.kind == ArtifactKind.THEORY_ATOM:
                domain_atom = env.payload.to_domain()
                if domain_atom.id not in affected_component_atoms:
                    continue
                if not _theory_atom_changed(
                    prior_atoms_by_id.get(domain_atom.id), domain_atom
                ):
                    continue
                existing_in_pass = pass_envelopes_by_id.get(
                    f"artifact::{domain_atom.id}::pass{pass_idx}"
                )
                deficit_id = (
                    existing_in_pass.provenance.deficit_id
                    if existing_in_pass is not None
                    else None
                )
                upstreams = (
                    list(existing_in_pass.provenance.upstream_artifact_ids)
                    if existing_in_pass is not None
                    else [
                        self._resolve_latest_artifact_id(
                            working_collection,
                            f"argument_component::{domain_atom.id}",
                            domain_atom.id,
                        )
                    ]
                )
                emitted.append(
                    build_theory_atom_artifact(
                        domain_atom,
                        run_id=context.run_id,
                        phase_name=phase_name,
                        method="refinement.theoretical_enrichment",
                        upstream_artifact_ids=upstreams,
                        refinement_pass=pass_idx,
                        deficit_id=deficit_id,
                    )
                )
            elif env.kind == ArtifactKind.THEORY_RELATION:
                domain_rel = env.payload.to_domain()
                rel_endpoints = {*domain_rel.effective_premise_ids, domain_rel.target_id}
                if not (rel_endpoints & affected_component_atoms):
                    continue
                if not _theory_relation_changed(
                    prior_rels_by_key.get(_relation_lookup_key(domain_rel)),
                    domain_rel,
                ):
                    continue
                existing_in_pass = pass_envelopes_by_id.get(
                    f"artifact::{domain_rel.relation_id}::pass{pass_idx}"
                )
                deficit_id = (
                    existing_in_pass.provenance.deficit_id
                    if existing_in_pass is not None
                    else None
                )
                upstreams = (
                    list(existing_in_pass.provenance.upstream_artifact_ids)
                    if existing_in_pass is not None
                    else None
                )
                emitted.append(
                    build_theory_relation_artifact(
                        domain_rel,
                        run_id=context.run_id,
                        phase_name=phase_name,
                        method="refinement.theoretical_enrichment",
                        upstream_artifact_ids=upstreams,
                        refinement_pass=pass_idx,
                        deficit_id=deficit_id,
                    )
                )

        return emitted

    def _run_theorynet_reconvergence(
        self,
        working_collection: ArtifactCollection,
        *,
        affected_component_atoms: set[str],
        run_id: str,
        phase_name: str,
        pass_idx: int,
        pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]],
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """Re-project TheoryNet equilibrium scores and emit only changed envelopes."""
        if self.theorynet_projector is None or not affected_component_atoms:
            return []

        updated_view = Phase4ArtifactsView.from_collection(working_collection)
        prior_atoms = (
            updated_view.canonical_theory_atoms
            if updated_view.canonical_theory_atoms
            else updated_view.theory_atoms
        )
        prior_rels = (
            updated_view.canonical_theory_relations
            if updated_view.canonical_theory_relations
            else updated_view.theory_relations
        )
        prior_atoms_by_id = {a.id: a for a in prior_atoms}
        prior_rels_by_key = {_relation_lookup_key(r): r for r in prior_rels}

        reprojected_net = self.theorynet_projector.project(updated_view)
        emitted: list[ArtifactEnvelope[ArtifactPayload]] = []

        for atom in reprojected_net.atoms:
            if atom.id not in affected_component_atoms:
                continue
            if not _theory_atom_changed(prior_atoms_by_id.get(atom.id), atom):
                continue

            existing_in_pass = pass_envelopes_by_id.get(
                f"artifact::{atom.id}::pass{pass_idx}"
            )
            deficit_id = (
                existing_in_pass.provenance.deficit_id
                if existing_in_pass is not None
                else None
            )
            upstreams = (
                list(existing_in_pass.provenance.upstream_artifact_ids)
                if existing_in_pass is not None
                else [
                    self._resolve_latest_artifact_id(
                        working_collection,
                        f"argument_component::{atom.id}",
                        atom.id,
                    )
                ]
            )
            emitted.append(
                build_theory_atom_artifact(
                    atom,
                    run_id=run_id,
                    phase_name=phase_name,
                    method="refinement.theorynet_reconvergence",
                    upstream_artifact_ids=upstreams,
                    refinement_pass=pass_idx,
                    deficit_id=deficit_id,
                )
            )

        for rel in reprojected_net.relations:
            endpoints = {*rel.effective_premise_ids, rel.target_id}
            if not (endpoints & affected_component_atoms):
                continue
            if not _theory_relation_changed(
                prior_rels_by_key.get(_relation_lookup_key(rel)), rel
            ):
                continue

            existing_in_pass = pass_envelopes_by_id.get(
                f"artifact::{rel.relation_id}::pass{pass_idx}"
            )
            deficit_id = (
                existing_in_pass.provenance.deficit_id
                if existing_in_pass is not None
                else None
            )
            upstreams = (
                list(existing_in_pass.provenance.upstream_artifact_ids)
                if existing_in_pass is not None
                else [
                    self._resolve_latest_artifact_id(
                        working_collection,
                        f"argument_component::{pid}",
                        pid,
                    )
                    for pid in rel.effective_premise_ids
                ]
                + [
                    self._resolve_latest_artifact_id(
                        working_collection,
                        (
                            f"argument_relation::{rel.undercuts_relation_id}"
                            if rel.undercuts_relation_id is not None
                            else f"argument_component::{rel.target_id}"
                        ),
                        rel.undercuts_relation_id or rel.target_id,
                    )
                ]
            )
            emitted.append(
                build_theory_relation_artifact(
                    rel,
                    run_id=run_id,
                    phase_name=phase_name,
                    method="refinement.theorynet_reconvergence",
                    upstream_artifact_ids=_dedup_preserve_order(upstreams),
                    refinement_pass=pass_idx,
                    deficit_id=deficit_id,
                )
            )

        return emitted

    @staticmethod
    def _build_overlay_collection(
        base_collection: ArtifactCollection,
        pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]],
    ) -> ArtifactCollection:
        """Overlay finalized pass envelopes onto ``base_collection`` preserving history."""
        if not pass_envelopes_by_id:
            return base_collection
        merged_history = list(base_collection.history)
        index_by_artifact_id = {
            env.artifact_id: idx for idx, env in enumerate(merged_history)
        }
        for env in pass_envelopes_by_id.values():
            existing_idx = index_by_artifact_id.get(env.artifact_id)
            if existing_idx is not None:
                merged_history[existing_idx] = env
            else:
                index_by_artifact_id[env.artifact_id] = len(merged_history)
                merged_history.append(env)
        return ArtifactCollection(merged_history)

    async def refine(
        self,
        collection: ArtifactCollection,
        context: ArtifactExecutionContext,
        *,
        config: HermeneuticRefinementConfig | None = None,
    ) -> ArtifactCollection:
        """Execute bounded top-down refinement cycles over ``collection``.

        Parameters
        ----------
        collection : ArtifactCollection
            Cumulative artifact collection emitted by the forward pipeline pass.
        context : ArtifactExecutionContext
            Active run execution context carrying manifest and curation ledger.
        config : HermeneuticRefinementConfig or None, optional
            Optional refinement configuration overriding coordinator defaults.

        Returns
        -------
        ArtifactCollection
            Updated artifact collection overlaying localized delta artifacts,
            ``EpistemicDeficitArtifact`` records, and re-converged L3/L4 outputs.
        """
        effective_config = config or self.config
        if effective_config.max_refinement_cycles <= 0:
            return collection

        emitter = get_event_emitter()
        working_collection = ArtifactCollection(collection.history)
        handled_signatures: dict[str, set[str]] = {}
        pending_detected: list[EpistemicDeficit] | None = None

        for pass_idx in range(1, effective_config.max_refinement_cycles + 1):
            cycle_start = time.perf_counter()
            pass_started_at = datetime.now(UTC)
            phase_name = f"Hermeneutic Refinement (Pass {pass_idx})"

            state = EpistemicDeficitArtifactsView.from_collection(working_collection)
            raw_deficits = (
                pending_detected
                if pending_detected is not None
                else self.detector.detect_deficits(
                    state,
                    refinement_pass=pass_idx - 1,
                    config=effective_config,
                    context=context,
                )
            )
            scheduled = self._filter_actionable_deficits(
                raw_deficits, effective_config, handled_signatures
            )
            if not scheduled:
                break

            emitter.emit(
                RefinementCycleStarted(
                    run_id=context.run_id,
                    phase=phase_name,
                    refinement_pass=pass_idx,
                    deficit_count=len(scheduled),
                    deficit_ids=[d.deficit_id for d in scheduled],
                    target_chunk_ids=_dedup_preserve_order(
                        cid for d in scheduled for cid in d.target_chunk_ids
                    ),
                    target_entity_ids=_dedup_preserve_order(
                        eid for d in scheduled for eid in d.target_entity_ids
                    ),
                )
            )

            pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]] = {}
            delta_artifact_ids: set[str] = set()
            resolved_ids: list[str] = []
            affected_chunk_ids: set[str] = set()
            affected_entity_ids: set[str] = set()
            affected_atom_ids: set[str] = set()
            changed_graph_structure = False

            for deficit in scheduled:
                deficit_env, is_new_deficit_env = self._materialize_deficit_envelope(
                    deficit,
                    working_collection,
                    run_id=context.run_id,
                    phase_name=phase_name,
                    pass_idx=pass_idx,
                )
                if is_new_deficit_env:
                    pass_envelopes_by_id[deficit_env.artifact_id] = deficit_env

                sig = _deficit_signature(deficit)
                handled_signatures.setdefault(deficit.deficit_id, set()).add(sig)

                delta = await self.refine_deficit(deficit, state, context=context)
                if delta.is_empty:
                    continue

                self._record_cannot_link_constraints(delta.cannot_link_pairs, context)

                delta_envelopes = self._build_delta_envelopes(
                    delta,
                    deficit=deficit,
                    deficit_artifact_id=deficit_env.artifact_id,
                    collection=working_collection,
                    run_id=context.run_id,
                    phase_name=phase_name,
                    pass_idx=pass_idx,
                )
                self._merge_pass_envelopes(pass_envelopes_by_id, delta_envelopes)
                delta_artifact_ids.update(env.artifact_id for env in delta_envelopes)

                if delta.resolved_deficit_ids:
                    resolved_ids.extend(delta.resolved_deficit_ids)
                elif delta_envelopes or delta.cannot_link_pairs:
                    resolved_ids.append(deficit.deficit_id)

                affected_chunk_ids.update(deficit.target_chunk_ids)
                affected_chunk_ids.update(c.id for c in delta.chunks)
                affected_chunk_ids.update(
                    a.source_chunk_id for a in delta.theory_atoms if a.source_chunk_id
                )
                affected_chunk_ids.update(
                    t.source_chunk_id for t in delta.local_triples if t.source_chunk_id
                )

                affected_entity_ids.update(deficit.target_entity_ids)
                affected_entity_ids.update(e.id for e in delta.entities)

                affected_atom_ids.update(deficit.target_atom_ids)
                affected_atom_ids.update(a.id for a in delta.theory_atoms)
                for rel in delta.theory_relations:
                    affected_atom_ids.update(rel.effective_premise_ids)
                    if rel.undercuts_relation_id is None and rel.target_id:
                        affected_atom_ids.add(rel.target_id)

                if (
                    delta.entities
                    or delta.local_triples
                    or delta.global_triples
                    or delta.theory_atoms
                    or delta.theory_relations
                ):
                    changed_graph_structure = True

            # Apply delta overlay onto working_collection before localized re-convergence
            working_collection = self._build_overlay_collection(
                working_collection, pass_envelopes_by_id
            )

            if changed_graph_structure:
                reconv_view = Phase4ArtifactsView.from_collection(working_collection)
                reconv_atoms = (
                    reconv_view.canonical_theory_atoms
                    if reconv_view.canonical_theory_atoms
                    else reconv_view.theory_atoms
                )
                reconv_rels = (
                    reconv_view.canonical_theory_relations
                    if reconv_view.canonical_theory_relations
                    else reconv_view.theory_relations
                )
                seed_atoms = set(affected_atom_ids)
                for atom in reconv_atoms:
                    if atom.source_chunk_id in affected_chunk_ids or any(
                        eid in affected_entity_ids for eid in atom.entity_ids
                    ):
                        seed_atoms.add(atom.id)

                affected_component_atoms = _connected_component_atoms(
                    seed_atoms, reconv_atoms, reconv_rels
                )

                if self.enrichment_runner is not None:
                    enrichment_envelopes = await self._run_localized_enrichment(
                        working_collection,
                        context,
                        affected_chunk_ids=affected_chunk_ids,
                        affected_atom_ids=affected_atom_ids,
                        affected_component_atoms=affected_component_atoms,
                        phase_name=phase_name,
                        pass_idx=pass_idx,
                        pass_envelopes_by_id=pass_envelopes_by_id,
                    )
                    if enrichment_envelopes:
                        self._merge_pass_envelopes(
                            pass_envelopes_by_id, enrichment_envelopes
                        )
                        delta_artifact_ids.update(
                            env.artifact_id for env in enrichment_envelopes
                        )
                        working_collection = self._build_overlay_collection(
                            working_collection, pass_envelopes_by_id
                        )

                if self.theorynet_projector is not None:
                    projected_envelopes = self._run_theorynet_reconvergence(
                        working_collection,
                        affected_component_atoms=affected_component_atoms,
                        run_id=context.run_id,
                        phase_name=phase_name,
                        pass_idx=pass_idx,
                        pass_envelopes_by_id=pass_envelopes_by_id,
                    )
                    if projected_envelopes:
                        self._merge_pass_envelopes(
                            pass_envelopes_by_id, projected_envelopes
                        )
                        delta_artifact_ids.update(
                            env.artifact_id for env in projected_envelopes
                        )
                        working_collection = self._build_overlay_collection(
                            working_collection, pass_envelopes_by_id
                        )

            post_state = EpistemicDeficitArtifactsView.from_collection(
                working_collection
            )
            next_detected = self.detector.detect_deficits(
                post_state,
                refinement_pass=pass_idx,
                config=effective_config,
                context=context,
            )
            remaining_actionable = self._filter_actionable_deficits(
                next_detected, effective_config, handled_signatures
            )

            next_ids = {d.deficit_id for d in next_detected}
            for d in scheduled:
                if d.deficit_id not in next_ids and d.deficit_id not in resolved_ids:
                    resolved_ids.append(d.deficit_id)
            resolved_ids = _dedup_preserve_order(resolved_ids)

            delta_count = len(delta_artifact_ids)
            converged = (len(remaining_actionable) == 0) or (delta_count == 0)

            pass_output_envelopes = list(pass_envelopes_by_id.values())
            pass_output_ids = [env.artifact_id for env in pass_output_envelopes]
            next_ordinal = (
                max(r.phase_ordinal for r in context.manifest.phase_records) + 1
                if context.manifest.phase_records
                else 1
            )
            context.manifest.refinement_pass = pass_idx
            context.manifest.phase_records.append(
                RunPhaseRecord(
                    phase_name=phase_name,
                    ordinal=next_ordinal,
                    phase_key="refinement",
                    status=RunStatus.COMPLETED,
                    started_at=pass_started_at,
                    completed_at=datetime.now(UTC),
                    config_fingerprint=stable_fingerprint(
                        effective_config.model_dump(mode="json")
                    ),
                    output_fingerprint=stable_fingerprint(
                        sorted(
                            [
                                env.identity_key or env.artifact_id,
                                env.dependency_fingerprint or "",
                            ]
                            for env in pass_output_envelopes
                        )
                    ),
                    input_artifact_ids=_dedup_preserve_order(
                        state.consumed_artifact_ids
                    ),
                    output_artifact_ids=pass_output_ids,
                    artifact_ids=pass_output_ids,
                    refinement_pass=pass_idx,
                    notes={
                        "deficit_count": str(len(scheduled)),
                        "resolved_count": str(len(resolved_ids)),
                        "delta_artifact_count": str(delta_count),
                        "converged": str(converged),
                    },
                )
            )

            emitter.emit(
                RefinementCycleCompleted(
                    run_id=context.run_id,
                    phase=phase_name,
                    refinement_pass=pass_idx,
                    resolved_deficit_count=len(resolved_ids),
                    remaining_deficit_count=len(remaining_actionable),
                    resolved_deficit_ids=resolved_ids,
                    delta_artifact_count=delta_count,
                    duration_seconds=time.perf_counter() - cycle_start,
                    converged=converged,
                )
            )

            if converged:
                break
            pending_detected = next_detected

        return working_collection


__all__ = ["ClosedLoopRefinementCoordinator"]
