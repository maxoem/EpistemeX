"""Closed-loop hermeneutic refinement coordinator (ISSUE-053 / ADR-0024).

Implements :class:`ClosedLoopRefinementCoordinator`, satisfying both
:class:`~episteme_pipeline.protocols.refinement.HermeneuticRefinementCoordinator`
and :class:`~episteme_pipeline.protocols.refinement.TargetedRefinementPort`.

After the forward pipeline reaches Phase 6 / Theoretical Enrichment, the
coordinator runs bounded refinement passes (``1..max_refinement_cycles``) that:

1. Inspect L1–L4 state with :class:`EpistemicDeficitDetector`.
2. Route each deficit sequentially to its localized refinement handler
   (:class:`TheoryGuidedPremiseRecoverer`, :class:`TargetedConceptSplitter`,
   :class:`LocalizedAxiomGrounder`), refreshing ``working_collection`` and
   ``current_state`` after each non-empty delta so intra-pass handlers never
   read stale pre-split or pre-grounding state.
3. Materialize incremental delta overlays (including split parent retirements
   and mention updates) via :mod:`episteme_pipeline.artifacts.refinement_overlay`.
4. Persist ``cannot_link_pairs`` onto :class:`EpistemicCurationLedger`, execute
   localized enrichment re-scoring and connected-component TheoryNet D-QBAF
   equilibrium reconvergence, stamp ``refinement_pass`` lineage on
   :class:`RunManifest` and :class:`RunPhaseRecord`, and emit lifecycle events.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from episteme_pipeline.artifacts.builders import (
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
from episteme_pipeline.artifacts.refinement_overlay import (
    build_deficit_envelope,
    build_delta_envelopes,
    canonical_relation_key,
    merge_pass_envelopes,
    overlay_collection,
    resolve_latest_artifact_id,
    slice_phase4_component_view,
    theory_atom_changed,
    theory_relation_changed,
)
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    RefinementDelta,
    TheoryAtom,
)
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    RefinementCycleCompleted,
    RefinementCycleStarted,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.refinement import (
    ConditionalRefinementHandler,
    EpistemicDeficitDetector,
    LocalizedAxiomGrounder,
    TargetedConceptSplitter,
    TheoryGuidedPremiseRecoverer,
    ensure_deficit_detector,
)
from episteme_pipeline.runs.fingerprints import fingerprint_method, stable_fingerprint
from episteme_pipeline.runs.models import RunPhaseRecord, RunStatus
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig
from episteme_pipeline.utils.identifiers import dedup_preserve_order

if TYPE_CHECKING:
    from episteme_pipeline.post_processing.theoretical_enrichment.runner import (
        TheoreticalEnrichmentRunner,
    )
    from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector

logger = logging.getLogger(__name__)


def _deficit_signature(deficit: EpistemicDeficit) -> str:
    """Build a stable structural signature suppressing redundant cross-cycle retries."""
    return stable_fingerprint(
        {
            "deficit_id": deficit.deficit_id,
            "kind": deficit.deficit_kind.value,
            "target_chunks": sorted(deficit.target_chunk_ids),
            "target_entities": sorted(deficit.target_entity_ids),
            "target_atoms": sorted(deficit.target_atom_ids),
            "target_relations": sorted(deficit.target_relation_ids),
            "theory_id": deficit.theory_id,
            "theory_lens": deficit.theory_lens,
        }
    )


class ClosedLoopRefinementCoordinator:
    """Coordinator executing bounded top-down hermeneutic refinement cycles.

    Implements :class:`HermeneuticRefinementCoordinator`,
    :class:`TargetedRefinementPort`, and :class:`Fingerprintable`.

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
        on affected connected components after refinement deltas are applied.
    enrichment_runner : TheoreticalEnrichmentRunner or None, optional
        Optional localized enrichment post-processor re-evaluating affected
        empirical clusters after grounding or concept splits.
    modal_resolver : ModalStrengthResolver or None, optional
        Optional async modal prior resolver applied before reconvergence for
        newly recovered atoms lacking explicit resolver provenance.
    config : HermeneuticRefinementConfig or None, optional
        Default refinement configuration.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.

    Raises
    ------
    TypeError
        If ``detector`` or any supplied handler fails its protocol check.
    """

    def __init__(
        self,
        detector: EpistemicDeficitDetector,
        premise_recoverer: TheoryGuidedPremiseRecoverer | None = None,
        concept_splitter: TargetedConceptSplitter | None = None,
        axiom_grounder: LocalizedAxiomGrounder | None = None,
        theorynet_projector: TheoryNetProjector | None = None,
        enrichment_runner: TheoreticalEnrichmentRunner | None = None,
        *,
        modal_resolver: ModalStrengthResolver | None = None,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
    ) -> None:
        self.detector: EpistemicDeficitDetector = ensure_deficit_detector(detector)
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

        self.premise_recoverer = premise_recoverer
        self.concept_splitter = concept_splitter
        self.axiom_grounder = axiom_grounder
        self.theorynet_projector = theorynet_projector
        self.enrichment_runner = enrichment_runner
        self.modal_resolver = modal_resolver
        self.config = config or HermeneuticRefinementConfig()
        self.schema = schema

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration and collaborator fingerprint.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of configuration and components.
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
            "modal_resolver": (
                self.modal_resolver.fingerprint()
                if isinstance(self.modal_resolver, Fingerprintable)
                else fingerprint_method(self.modal_resolver)
            ),
        }

    def _is_handler_enabled(
        self,
        deficit_kind: EpistemicDeficitKind,
        config: HermeneuticRefinementConfig,
    ) -> bool:
        """Check whether ``config`` and wired ports enable handling ``deficit_kind``."""
        if deficit_kind == EpistemicDeficitKind.ENTHYMEME_GAP:
            if (
                not config.enable_theory_guided_premise_recovery
                or self.premise_recoverer is None
            ):
                return False
            if isinstance(self.premise_recoverer, ConditionalRefinementHandler):
                return self.premise_recoverer.is_available
            return True
        if deficit_kind == EpistemicDeficitKind.POLYSEMY_COLLISION:
            return (
                config.enable_targeted_concept_split
                and self.concept_splitter is not None
            )
        if deficit_kind == EpistemicDeficitKind.UNGROUNDED_AXIOM:
            return (
                config.enable_localized_axiom_grounding
                and self.axiom_grounder is not None
            )
        return False

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

        filtered.sort(key=lambda d: (-d.severity, d.deficit_kind.value, d.deficit_id))
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
            Localized refinement output delta.
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

    def _handler_method_name(self, kind: EpistemicDeficitKind) -> str:
        """Return stable method attribution label for a handler kind."""
        if kind == EpistemicDeficitKind.ENTHYMEME_GAP:
            return (
                type(self.premise_recoverer).__name__
                if self.premise_recoverer is not None
                else "TheoryGuidedPremiseRecoverer"
            )
        if kind == EpistemicDeficitKind.POLYSEMY_COLLISION:
            return (
                type(self.concept_splitter).__name__
                if self.concept_splitter is not None
                else "TargetedConceptSplitter"
            )
        if kind == EpistemicDeficitKind.UNGROUNDED_AXIOM:
            return (
                type(self.axiom_grounder).__name__
                if self.axiom_grounder is not None
                else "LocalizedAxiomGrounder"
            )
        return type(self).__name__

    @staticmethod
    def _record_cannot_link_constraints(
        cannot_link_pairs: Sequence[tuple[str, str]],
        context: ArtifactExecutionContext,
    ) -> None:
        """Persist ``cannot_link_pairs`` onto ``context.pipeline_input.curation_ledger``."""
        if not cannot_link_pairs or context.pipeline_input is None:
            return
        ledger = context.pipeline_input.resolved_curation_ledger()
        if ledger is None:
            ledger = EpistemicCurationLedger()
        for id_a, id_b in cannot_link_pairs:
            if id_a and id_b and id_a != id_b:
                ledger.cannot_link_entities.add((id_a, id_b))
        context.pipeline_input.curation_ledger = ledger

    async def _resolve_delta_atom_modalities(
        self,
        delta: RefinementDelta,
        state: EpistemicStateView,
    ) -> RefinementDelta:
        """Run optional async ``modal_resolver`` over newly introduced atoms."""
        if self.modal_resolver is None or not delta.theory_atoms:
            return delta
        chunks_by_id = {c.id: c.text for c in state.chunks}
        updated_atoms: list[TheoryAtom] = []
        changed = False
        for atom in delta.theory_atoms:
            if atom.resolver_type is None:
                c_text = chunks_by_id.get(atom.source_chunk_id)
                resolved = await self.modal_resolver.resolve_modality(
                    atom, context=c_text
                )
                clamped = max(0.0, min(1.0, float(resolved)))
                if abs(clamped - atom.modal_prior) > 1e-6:
                    updated_atoms.append(
                        atom.model_copy(update={"modal_prior": clamped})
                    )
                    changed = True
                    continue
            updated_atoms.append(atom)
        if not changed:
            return delta
        return delta.model_copy(update={"theory_atoms": updated_atoms})

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

        scope_atom_ids = set(direct_atom_ids)
        scoped_relations = []
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

        pass_manifest = context.manifest.model_copy(
            update={"refinement_pass": pass_idx}
        )
        pass_lineage_fp = (
            f"{context.lineage_fingerprint}::refine_pass{pass_idx}"
            if context.lineage_fingerprint
            else f"refine_pass{pass_idx}"
        )
        enrichment_ctx = ArtifactExecutionContext(
            run_id=context.run_id,
            manifest=pass_manifest,
            pipeline_input=context.pipeline_input,
            previous=working_collection,
            lineage_fingerprint=pass_lineage_fp,
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
                existing_enr_keys[(payload.theory_id, payload.cluster_id)] = (
                    ikey,
                    ikey,
                )

        prior_atoms_by_id = {a.id: a for a in all_atoms}
        prior_rels_by_key = {
            canonical_relation_key(
                r.effective_premise_ids, r.target_id, r.relation_type
            ): r
            for r in all_relations
        }
        emitted: list[ArtifactEnvelope[ArtifactPayload]] = []

        for env in te_collection.history:
            if env.kind == ArtifactKind.EPISTEMIC_DEFICIT:
                continue

            if env.kind == ArtifactKind.THEORETICAL_ENRICHMENT and isinstance(
                env.payload, TheoreticalEnrichmentArtifact
            ):
                enr_payload = env.payload
                cluster_chunk = enr_payload.cluster_id.removeprefix("cluster-")
                in_affected = cluster_chunk in affected_chunk_ids or any(
                    aid in affected_atom_ids for aid in enr_payload.claimant_atom_ids
                )
                if not in_affected:
                    continue

                pair_key = (enr_payload.theory_id, enr_payload.cluster_id)
                if pair_key in existing_enr_keys:
                    identity_key, base_id = existing_enr_keys[pair_key]
                    art_id = f"{base_id}::pass{pass_idx}"
                else:
                    identity_key = f"theoretical_enrichment::{enr_payload.theory_id}::{enr_payload.cluster_id}"
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
                if not theory_atom_changed(
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
                        resolve_latest_artifact_id(
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
                        upstream_artifact_ids=dedup_preserve_order(upstreams),
                        refinement_pass=pass_idx,
                        deficit_id=deficit_id,
                    )
                )
            elif env.kind == ArtifactKind.THEORY_RELATION:
                domain_rel = env.payload.to_domain()
                endpoints = {*domain_rel.effective_premise_ids, domain_rel.target_id}
                if not (endpoints & affected_component_atoms):
                    continue
                r_key = canonical_relation_key(
                    domain_rel.effective_premise_ids,
                    domain_rel.target_id,
                    domain_rel.relation_type,
                )
                if not theory_relation_changed(
                    prior_rels_by_key.get(r_key), domain_rel
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
                    else [
                        resolve_latest_artifact_id(
                            working_collection,
                            f"argument_component::{pid}",
                            pid,
                        )
                        for pid in domain_rel.effective_premise_ids
                    ]
                    + [
                        resolve_latest_artifact_id(
                            working_collection,
                            (
                                f"argument_relation::{domain_rel.undercuts_relation_id}"
                                if domain_rel.undercuts_relation_id is not None
                                else f"argument_component::{domain_rel.target_id}"
                            ),
                            domain_rel.undercuts_relation_id or domain_rel.target_id,
                        )
                    ]
                )
                emitted.append(
                    build_theory_relation_artifact(
                        domain_rel,
                        run_id=context.run_id,
                        phase_name=phase_name,
                        method="refinement.theoretical_enrichment",
                        upstream_artifact_ids=dedup_preserve_order(upstreams),
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
        """Re-project TheoryNet D-QBAF scores strictly over the affected component."""
        if self.theorynet_projector is None or not affected_component_atoms:
            return []

        updated_view = Phase4ArtifactsView.from_collection(working_collection)
        localized_view = slice_phase4_component_view(
            updated_view, affected_component_atoms
        )
        prior_atoms = (
            localized_view.canonical_theory_atoms
            if localized_view.canonical_theory_atoms
            else localized_view.theory_atoms
        )
        prior_rels = (
            localized_view.canonical_theory_relations
            if localized_view.canonical_theory_relations
            else localized_view.theory_relations
        )
        prior_atoms_by_id = {a.id: a for a in prior_atoms}
        prior_rels_by_key = {
            canonical_relation_key(
                r.effective_premise_ids, r.target_id, r.relation_type
            ): r
            for r in prior_rels
        }

        reprojected_net = self.theorynet_projector.project(localized_view)
        emitted: list[ArtifactEnvelope[ArtifactPayload]] = []

        for atom in reprojected_net.atoms:
            if atom.id not in affected_component_atoms:
                continue
            if not theory_atom_changed(prior_atoms_by_id.get(atom.id), atom):
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
                    resolve_latest_artifact_id(
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
                    upstream_artifact_ids=dedup_preserve_order(upstreams),
                    refinement_pass=pass_idx,
                    deficit_id=deficit_id,
                )
            )

        for rel in reprojected_net.relations:
            endpoints = {*rel.effective_premise_ids, rel.target_id}
            if not (endpoints & affected_component_atoms):
                continue
            r_key = canonical_relation_key(
                rel.effective_premise_ids, rel.target_id, rel.relation_type
            )
            if not theory_relation_changed(prior_rels_by_key.get(r_key), rel):
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
                    resolve_latest_artifact_id(
                        working_collection,
                        f"argument_component::{pid}",
                        pid,
                    )
                    for pid in rel.effective_premise_ids
                ]
                + [
                    resolve_latest_artifact_id(
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
                    upstream_artifact_ids=dedup_preserve_order(upstreams),
                    refinement_pass=pass_idx,
                    deficit_id=deficit_id,
                )
            )

        return emitted

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
            Optional per-call configuration override.

        Returns
        -------
        ArtifactCollection
            Updated collection containing forward history plus overlaid
            localized refinement artifacts and convergence lineage.
        """
        effective_config = config or self.config
        if effective_config.max_refinement_cycles <= 0:
            return collection

        working_collection = collection
        emitter = get_event_emitter()
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
                    target_chunk_ids=dedup_preserve_order(
                        cid for d in scheduled for cid in d.target_chunk_ids
                    ),
                    target_entity_ids=dedup_preserve_order(
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
            current_state = state

            for deficit in scheduled:
                deficit_env, is_new_deficit_env = build_deficit_envelope(
                    deficit,
                    working_collection,
                    run_id=context.run_id,
                    phase_name=phase_name,
                    detector_method=type(self.detector).__name__,
                    pass_idx=pass_idx,
                )
                if is_new_deficit_env:
                    pass_envelopes_by_id[deficit_env.artifact_id] = deficit_env

                sig = _deficit_signature(deficit)
                handled_signatures.setdefault(deficit.deficit_id, set()).add(sig)

                delta = await self.refine_deficit(
                    deficit, current_state, context=context
                )
                if delta.is_empty:
                    continue

                delta = await self._resolve_delta_atom_modalities(delta, current_state)
                self._record_cannot_link_constraints(delta.cannot_link_pairs, context)

                delta_envelopes = build_delta_envelopes(
                    delta,
                    deficit=deficit,
                    deficit_artifact_id=deficit_env.artifact_id,
                    collection=working_collection,
                    run_id=context.run_id,
                    phase_name=phase_name,
                    method_name=self._handler_method_name(deficit.deficit_kind),
                    pass_idx=pass_idx,
                )
                merge_pass_envelopes(pass_envelopes_by_id, delta_envelopes)
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
                    or delta.retired_entity_ids
                ):
                    changed_graph_structure = True

                # Apply incremental overlay immediately so subsequent deficits in this pass
                # observe updated entities, retired hubs, and recovered atoms.
                working_collection = overlay_collection(
                    working_collection, pass_envelopes_by_id
                )
                current_state = EpistemicDeficitArtifactsView.from_collection(
                    working_collection
                )

            if pass_envelopes_by_id:
                working_collection = overlay_collection(
                    working_collection, pass_envelopes_by_id
                )

            if changed_graph_structure:
                reconv_view = Phase4ArtifactsView.from_collection(working_collection)
                reconv_atoms = (
                    reconv_view.canonical_theory_atoms
                    if reconv_view.canonical_theory_atoms
                    else reconv_view.theory_atoms
                )
                seed_atoms = set(affected_atom_ids)
                for atom in reconv_atoms:
                    if atom.source_chunk_id in affected_chunk_ids or any(
                        eid in affected_entity_ids for eid in atom.entity_ids
                    ):
                        seed_atoms.add(atom.id)

                component_view = slice_phase4_component_view(reconv_view, seed_atoms)
                affected_component_atoms = {
                    a.id
                    for a in (
                        component_view.canonical_theory_atoms
                        or component_view.theory_atoms
                    )
                }

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
                        merge_pass_envelopes(pass_envelopes_by_id, enrichment_envelopes)
                        delta_artifact_ids.update(
                            env.artifact_id for env in enrichment_envelopes
                        )
                        working_collection = overlay_collection(
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
                        merge_pass_envelopes(pass_envelopes_by_id, projected_envelopes)
                        delta_artifact_ids.update(
                            env.artifact_id for env in projected_envelopes
                        )
                        working_collection = overlay_collection(
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
            resolved_ids = dedup_preserve_order(resolved_ids)

            delta_count = len(delta_artifact_ids)
            converged = delta_count == 0 or not remaining_actionable

            context.manifest.refinement_pass = pass_idx
            next_ordinal = (
                max(
                    (r.phase_ordinal for r in context.manifest.phase_records), default=0
                )
                + 1
            )
            pass_output_envelopes = [
                env
                for env in pass_envelopes_by_id.values()
                if env.provenance.refinement_pass == pass_idx
                or env.kind == ArtifactKind.EPISTEMIC_DEFICIT
            ]
            pass_output_ids = [env.artifact_id for env in pass_output_envelopes]
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
                    input_artifact_ids=dedup_preserve_order(
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
