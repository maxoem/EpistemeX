"""Phase 6 runner for TheoryNet materialization and projection.

Coordinates the translation of Phase 4 argument components and dialectical relations
into the formal mathematical TheoryNet model, applying decoupled calibrated edge
weights and persisting probability distributions into the Neo4j projection graph.
"""

from __future__ import annotations

import logging
from typing import Any

from episteme_pipeline.artifacts.builders import (
    build_epistemic_deficit_artifact,
    build_theory_graph_update_artifacts,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import Phase6Config
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryNet
from episteme_pipeline.contracts.phase_contracts import CURATION_LEDGER_RESOLVER_TYPE
from episteme_pipeline.decision.modal_resolver import HybridModalResolver
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.protocols.modality import (
    ModalStrengthResolver,
    ensure_modal_strength_resolver,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.refinement import (
    EpistemicDeficitDetector,
    ensure_deficit_detector,
)
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils.graph_algorithms import compute_z1_grounding

logger = logging.getLogger(__name__)


class Phase6Runner(PhaseRunner[Phase4ArtifactsView]):
    """Executes the Phase 6 TheoryNet materialization and projection.

    Constructs the formalized argument graph (:math:`\\rho`, :math:`\\alpha`) from
    Phase 4 mined theories, applying calibrated edge weights and QBAF
    gradual semantics.

    Parameters
    ----------
    config : Phase6Config | dict | None, optional
        Phase 6 configuration options (iterations, tolerance, admissibility).
    schema : SchemaConfig | None, optional
        Pipeline schema taxonomy and polarities.
    graph_store : ProjectionGraph | None, optional
        Target Neo4j or in-memory projection graph store.
    projector : TheoryNetProjector | None, optional
        TheoryNet projector instance.
    decision_engine : DecisionEngine | None, optional
        System 1 calibrated decision engine instance.
    modal_resolver : ModalStrengthResolver | None, optional
        Propositional modal strength resolver. If None, initialized from config and decision engine.
    deficit_detector : EpistemicDeficitDetector | None, optional
        Optional top-down epistemic deficit detector invoked after TheoryNet
        projection to emit :class:`EpistemicDeficitArtifact` signals.
    """

    name = "Phase 6: TheoryNet Projection"
    phase_key = "phase6"
    input_view = Phase4ArtifactsView
    reads_kinds = frozenset(
        {
            ArtifactKind.THEORY_ATOM,
            ArtifactKind.THEORY_RELATION,
            ArtifactKind.FUSION_DECISION,
        }
    )
    writes_kinds = frozenset(
        {
            ArtifactKind.THEORY_ATOM,
            ArtifactKind.THEORY_RELATION,
            ArtifactKind.EPISTEMIC_DEFICIT,
        }
    )

    def __init__(
        self,
        config: Phase6Config | dict[str, Any] | None = None,
        schema: SchemaConfig | None = None,
        graph_store: ProjectionGraph | None = None,
        projector: TheoryNetProjector | None = None,
        decision_engine: DecisionEngine | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        deficit_detector: EpistemicDeficitDetector | None = None,
    ) -> None:
        if config is None:
            config = Phase6Config()
        elif isinstance(config, dict):
            config = Phase6Config.model_validate(config)
        self.config = config
        self.schema = schema or SchemaConfig()
        self.graph_store = graph_store
        self.decision_engine = decision_engine

        self.admissibility_threshold = config.admissibility_threshold
        self.prune_inadmissible = config.prune_inadmissible
        self.admissibility_mode = config.admissibility_mode
        self.tau_p = config.tau_p
        self.tau_c = config.tau_c

        # Resolve ModalStrengthResolver
        self.modal_resolver = ensure_modal_strength_resolver(
            modal_resolver
        ) or HybridModalResolver.create(
            config=config.modal_resolver,
            decision_engine=self.decision_engine,
        )
        self.deficit_detector: EpistemicDeficitDetector | None = (
            ensure_deficit_detector(deficit_detector)
        )

        self.projector = projector or TheoryNetProjector(
            schema=self.schema,
            admissibility_threshold=config.admissibility_threshold,
            admissibility_mode=config.admissibility_mode,
            tau_p=config.tau_p,
            tau_c=config.tau_c,
            prune_inadmissible=config.prune_inadmissible,
            iterations=config.iterations,
            tolerance=config.tolerance,
            semantics_model=config.semantics_model,
            modal_resolver=self.modal_resolver,
            use_continuous=config.use_continuous,
            perspective=config.perspective,
            isolate_suppositional=config.isolate_suppositional,
            isolate_attributed=config.isolate_attributed,
            t_norm=config.conjunctive_t_norm,
        )

    async def run(
        self, input: Phase4ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Execute Phase 6 TheoryNet formalization and Neo4j graph projection.

        Parameters
        ----------
        input : Phase4ArtifactsView
            Extracted theory atoms and relations from Phase 4.
        context : ArtifactExecutionContext
            Run execution context.

        Returns
        -------
        ArtifactCollection
            TheoryAtomArtifact and TheoryRelationArtifact envelopes.
        """
        logger.info("Phase 6: Projecting formal TheoryNet with calibrated weights")

        source_atoms = (
            input.canonical_theory_atoms
            if input.canonical_theory_atoms
            else input.theory_atoms
        )
        source_relations = (
            input.canonical_theory_relations
            if input.canonical_theory_relations
            else input.theory_relations
        )
        curation_ledger = (
            context.pipeline_input.resolved_curation_ledger()
            if context and context.pipeline_input
            else None
        )

        total_items = len(source_atoms) + len(source_relations)
        with self.progress_scope(
            "Phase 6: TheoryNet Projection",
            total_items=total_items,
            description="TheoryNet Projection",
        ) as advance:
            if curation_ledger is not None:
                source_atoms = curation_ledger.apply_to_theory_atoms(source_atoms)
                if input.canonical_theory_atoms:
                    input.canonical_theory_atoms = source_atoms
                else:
                    input.theory_atoms = source_atoms
                source_relations = curation_ledger.apply_to_theory_relations(
                    source_relations,
                    {a.id for a in source_atoms},
                    schema=self.schema,
                )
                if input.canonical_theory_relations:
                    input.canonical_theory_relations = source_relations
                else:
                    input.theory_relations = source_relations

            # Resolve propositional modal certainty for atoms missing explicit scores
            for atom in source_atoms:
                if (
                    atom.resolver_type != CURATION_LEDGER_RESOLVER_TYPE
                    and "modal_prior" not in atom.model_fields_set
                    and atom.resolver_type is None
                ):
                    resolved_mod = await self.modal_resolver.resolve_modality(atom)
                    atom.modal_prior = resolved_mod

            theory_net: TheoryNet = self.projector.project(input)

            atoms_updated = 0
            relations_updated = 0

            atoms_to_upsert: list[TheoryAtom] = []
            for atom in theory_net.atoms:
                if atom.equilibrium_strength is None:
                    atom.equilibrium_strength = atom.effective_base_prior(
                        include_suppositional=not self.config.isolate_suppositional,
                        perspective=self.config.perspective,
                    )
                atoms_to_upsert.append(atom)
                atoms_updated += 1

            relations_updated = len(theory_net.relations)

            if self.graph_store is not None:
                from itertools import batched

                for atom_batch in batched(atoms_to_upsert, 500):
                    await self.graph_store.upsert_argument_components(list(atom_batch))

                for rel_batch in batched(theory_net.relations, 500):
                    batch_list = list(rel_batch)
                    await self.graph_store.upsert_theory_relations(batch_list)
            else:
                logger.debug(
                    "Phase 6: Running in artifact-native mode without direct graph_store write."
                )

            advance(atoms_updated + relations_updated)

            logger.info(
                "Phase 6: Projected %d TheoryAtoms and %d TheoryRelations with calibrated weights",
                atoms_updated,
                relations_updated,
            )

        # Baseline empirical content ratio calculation (Z1 path from theoretical antecedents to empirical base)
        z1_result = compute_z1_grounding(
            theory_net.atoms,
            theory_net.relations,
            self.schema,
        )
        logger.info(
            "Phase 6: Empirical Content metric = %.3f (%d/%d A-atoms with a Z1 path to B)",
            z1_result.empirical_content_ratio,
            len(z1_result.z1_grounded_ids),
            len(z1_result.a_atom_ids),
        )

        refinement_pass = (
            context.manifest.refinement_pass
            if context is not None and context.manifest is not None
            else 0
        )

        prev_collection = context.previous if context is not None else None
        artifacts = build_theory_graph_update_artifacts(
            theory_net.atoms,
            theory_net.relations,
            previous_collection=prev_collection,
            run_id=context.run_id,
            phase_name=self.name,
            method="phase6.theorynet",
            refinement_pass=refinement_pass,
            phase_tag=self.phase_key,
            include_fusion_decisions=True,
        )

        if self.deficit_detector is not None:
            updated_state = Phase4ArtifactsView(
                documents=input.documents,
                chunks=input.chunks,
                entities=input.entities,
                local_triples=input.local_triples,
                entity_count_by_type=input.entity_count_by_type,
                global_triples=input.global_triples,
                relation_type_distribution=input.relation_type_distribution,
                theory_atoms=theory_net.atoms,
                theory_relations=theory_net.relations,
                fusion_decisions=input.fusion_decisions,
                canonical_theory_atoms=theory_net.atoms,
                canonical_theory_relations=theory_net.relations,
                entity_envelopes_by_id=input.entity_envelopes_by_id,
                entity_mentions_by_id=input.entity_mentions_by_id,
                theoretical_enrichments=input.theoretical_enrichments,
                epistemic_deficits=input.epistemic_deficits,
                consumed_artifact_ids=input.consumed_artifact_ids,
            )
            deficits = self.deficit_detector.detect_deficits(
                updated_state,
                refinement_pass=refinement_pass,
                context=context,
            )
            for deficit in deficits:
                stamped = (
                    deficit
                    if deficit.detected_in_phase
                    else deficit.model_copy(
                        update={"detected_in_phase": self.phase_key}
                    )
                )
                artifacts.append(
                    build_epistemic_deficit_artifact(
                        stamped,
                        run_id=context.run_id,
                        phase_name=self.name,
                        method=type(self.deficit_detector).__name__,
                        refinement_pass=refinement_pass,
                    )
                )

        return ArtifactCollection(artifacts)
