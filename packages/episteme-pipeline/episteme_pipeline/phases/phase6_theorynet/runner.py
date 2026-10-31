"""Phase 6 runner for TheoryNet materialization and projection.

Coordinates the translation of Phase 4 argument components and dialectical relations
into the formal mathematical TheoryNet model, applying decoupled calibrated edge
weights and persisting probability distributions into the Neo4j projection graph.
"""

from __future__ import annotations

import logging
from typing import Any

from episteme_pipeline.artifacts.builders import (
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import Phase6Config
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryNet
from episteme_pipeline.decision.modal_resolver import HybridModalResolver
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.protocols.modality import (
    ModalStrengthResolver,
    ensure_modal_strength_resolver,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.schema.default_schema import SchemaConfig

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
    writes_kinds = frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION})

    def __init__(
        self,
        config: Phase6Config | dict[str, Any] | None = None,
        schema: SchemaConfig | None = None,
        graph_store: ProjectionGraph | None = None,
        projector: TheoryNetProjector | None = None,
        decision_engine: DecisionEngine | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
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
        self.modal_resolver = ensure_modal_strength_resolver(modal_resolver) or HybridModalResolver.create(
            config=config.modal_resolver,
            decision_engine=self.decision_engine,
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
            # Resolve propositional modal certainty for atoms missing explicit scores or with ledger overrides
            for atom in source_atoms:
                if curation_ledger is not None:
                    override_val = curation_ledger.get_modality_override(atom.id)
                    if override_val is not None:
                        atom.modal_strength = override_val
                        atom.base_score = override_val
                        continue
                if "modal_strength" not in atom.model_fields_set and "base_score" not in atom.model_fields_set:
                    atom.modal_strength = await self.modal_resolver.resolve_modality(atom)
                    atom.base_score = atom.modal_strength

            if curation_ledger is not None:
                source_relations = curation_ledger.apply_to_theory_relations(
                    source_relations, {a.id for a in source_atoms}
                )
                if input.canonical_theory_relations:
                    input.canonical_theory_relations = source_relations
                else:
                    input.theory_relations = source_relations

            theory_net: TheoryNet = self.projector.project(input)

            atoms_updated = 0
            relations_updated = 0

            atoms_to_upsert: list[TheoryAtom] = []
            for atom in theory_net.atoms:
                if atom.plausibility is None:
                    atom.plausibility = atom.confidence if atom.confidence is not None else 1.0
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
        a_atoms = {
            a.id
            for a in theory_net.atoms
            if self.schema.component_partitions.get(a.component_type) == "A"
        }
        b_atoms = {
            a.id
            for a in theory_net.atoms
            if self.schema.component_partitions.get(a.component_type) == "B"
        }

        adj: dict[str, set[str]] = {a_id: set() for a_id in a_atoms}
        z1_connected: set[str] = set()

        for rel in theory_net.relations:
            if rel.source_id in a_atoms and rel.target_id in b_atoms:
                z1_connected.add(rel.source_id)
            elif rel.target_id in a_atoms and rel.source_id in b_atoms:
                z1_connected.add(rel.target_id)
            elif rel.source_id in a_atoms and rel.target_id in a_atoms:
                adj[rel.source_id].add(rel.target_id)
                adj[rel.target_id].add(rel.source_id)

        visited = set(z1_connected)
        queue = list(z1_connected)
        while queue:
            curr = queue.pop(0)
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        empirical_content = len(visited) / len(a_atoms) if a_atoms else 0.0
        logger.info(
            "Phase 6: Empirical Content metric = %.3f (%d/%d A-atoms with a Z1 path to B)",
            empirical_content,
            len(visited),
            len(a_atoms),
        )

        artifacts = [
            build_theory_atom_artifact(
                atom,
                run_id=context.run_id,
                phase_name=self.name,
                method="phase6.theorynet",
            )
            for atom in theory_net.atoms
        ]
        artifacts.extend(
            build_theory_relation_artifact(
                rel,
                run_id=context.run_id,
                phase_name=self.name,
                method="phase6.theorynet",
            )
            for rel in theory_net.relations
        )
        return ArtifactCollection(artifacts)
