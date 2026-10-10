"""Theoretical Enrichment and Tenability Evaluation Post-Processor.

Takes the domain-agnostic structural graph (Phi_gen) produced by initial NLP ingestion,
projects it into theory-specific parametric spaces (Phi_spec), and evaluates local and
intertheoretical tenability scores (Stegmüller 1976; Balzer et al. 1987; Schurz 2024).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactProvenance,
    TheoreticalEnrichmentArtifact,
)
from episteme_pipeline.config import TheoreticalEnrichmentConfig
from episteme_pipeline.contracts.domain import (
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.llm.structured import StructuredLLM, ensure_structured_llm
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    EmpiricalCluster,
    TheoryRegistry,
)
from episteme_pipeline.post_processing.theoretical_enrichment.events import (
    TenabilityAnomalyDetected,
    TenabilityEvaluationCompleted,
    TheoreticalClusterIdentified,
    TheoreticalParametersProjected,
)
from episteme_pipeline.post_processing.theoretical_enrichment.inducer import (
    LLMTheoryInducer,
    TheoryInducer,
)
from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
    CompositeTheoryProjector,
    LLMTheoryProjector,
    TheoryProjector,
)
from episteme_pipeline.post_processing.theoretical_enrichment.solvers import (
    TenabilitySolver,
)
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


class TheoreticalEnrichmentRunner(PhaseRunner[Phase4ArtifactsView]):
    """Executes Theoretical Enrichment & Tenability Evaluation post-processing.

    Parameters
    ----------
    config : TheoreticalEnrichmentConfig | None, optional
        Configuration block for Theoretical Enrichment, by default None.
    schema : SchemaConfig | None, optional
        Decoupled schema configuration, by default None.
    graph_store : ProjectionGraph | None, optional
        Graph backend to project enriched parameters and scores into, by default None.
    registry : TheoryRegistry | None, optional
        Registry of formal Theory-Element definitions, by default None.
    projector : TheoryProjector | None, optional
        Domain projection engine (Phi_spec), by default None.
    solver : TenabilitySolver | None, optional
        Tenability optimization solver, by default None.
    inducer : TheoryInducer | None, optional
        Dynamic Theory-Element induction engine, by default None.
    llm : Any | None, optional
        Underlying LLM facade for induction and projection, by default None.
    """

    name = "Theoretical Enrichment & Tenability Evaluation"
    phase_key = "theoretical_enrichment"
    input_view = Phase4ArtifactsView

    def __init__(
        self,
        config: TheoreticalEnrichmentConfig | None = None,
        schema: SchemaConfig | None = None,
        graph_store: ProjectionGraph | None = None,
        registry: TheoryRegistry | None = None,
        projector: TheoryProjector | None = None,
        solver: TenabilitySolver | None = None,
        inducer: TheoryInducer | None = None,
        llm: Any | None = None,
    ) -> None:
        self.config = config or TheoreticalEnrichmentConfig()
        self.schema = schema or SchemaConfig()
        self.graph_store = graph_store
        self.registry = registry or TheoryRegistry()
        self.llm: StructuredLLM | None = ensure_structured_llm(llm) if llm is not None else None

        if inducer is not None:
            self.inducer: TheoryInducer | None = inducer
        elif self.llm is not None and self.config.induce_theories:
            self.inducer = LLMTheoryInducer(
                llm=self.llm,
                prompts=self.config.induction_prompts,
                strategy=self.config.decoding_strategy,
            )
        else:
            self.inducer = None

        if projector is not None:
            self.projector = projector
        elif self.llm is not None:
            self.projector = LLMTheoryProjector(
                llm=self.llm,
                prompts=self.config.projection_prompts,
                strategy=self.config.decoding_strategy,
            )
        else:
            self.projector = CompositeTheoryProjector()

        self.solver = solver or TenabilitySolver(
            anomaly_threshold=self.config.tenability_threshold,
            weight_local=self.config.weight_local,
            weight_edge=self.config.weight_edge,
        )

    @property
    def event_emitter(self) -> EventEmitter:
        """Centralized event emitter."""
        return get_event_emitter()

    async def run(
        self, input: Phase4ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Run the Theoretical Enrichment and Tenability Evaluation post-processor.

        Parameters
        ----------
        input : Phase4ArtifactsView
            Typed slice of upstream Phase 4/5 theory atoms and relations.
        context : ArtifactExecutionContext
            Execution run context and manifest tracking.

        Returns
        -------
        ArtifactCollection
            Collection of emitted TheoreticalEnrichmentArtifact envelopes.
        """
        logger.info(
            "Theoretical Enrichment: Beginning evaluation on %d atoms and %d relations",
            len(input.theory_atoms),
            len(input.theory_relations),
        )

        if not self.config.enabled:
            logger.info("Theoretical Enrichment is disabled in config. Skipping.")
            return ArtifactCollection([])

        # -------------------------------------------------------------
        # Stage 0: Dynamic Theory-Element Induction (Macro Scope)
        # -------------------------------------------------------------
        if not self.registry.all_theories() and self.config.induce_theories and self.inducer:
            logger.info("Theoretical Enrichment: Registry is unseeded. Running LLM Theory-Element induction...")
            induced = await self.inducer.induce_theories(
                atoms=input.theory_atoms,
                relations=input.theory_relations,
                schema=self.schema,
                max_theories=self.config.max_theories,
            )
            for theory in induced:
                self.registry.register(theory)
            logger.info(
                "Theoretical Enrichment: Successfully induced and registered %d theories: %s",
                len(induced),
                [t.theory_id for t in induced],
            )

        # -------------------------------------------------------------
        # Step 1: Cluster Mapping (Application Identification)
        # -------------------------------------------------------------
        clusters = self._identify_empirical_clusters(
            input.theory_atoms, input.theory_relations
        )
        logger.info(
            "Theoretical Enrichment: Identified %d empirical clusters (Intended Applications I)",
            len(clusters),
        )

        # Map each cluster to claiming theories
        for cluster in clusters:
            claimants = self.registry.match_claimants(cluster)
            if not claimants:
                # Default to all registered theories for evaluation
                claimants = [t.theory_id for t in self.registry.all_theories()]
            cluster.claimant_theory_ids = claimants

            self.event_emitter.emit(
                TheoreticalClusterIdentified(
                    run_id=context.run_id,
                    phase=self.name,
                    cluster_id=cluster.cluster_id,
                    observation_count=len(cluster.observations),
                    claimant_theories=claimants,
                )
            )

        # -------------------------------------------------------------
        # Step 2: Domain-Specific Projections (Phi_spec)
        # Step 3: Local Tenability Calculation (TS_local)
        # Step 4: Global and Intertheoretical Consistency (GL)
        # -------------------------------------------------------------
        enrichment_artifacts: list[ArtifactEnvelope[TheoreticalEnrichmentArtifact]] = []
        cluster_theory_params: dict[tuple[str, str], dict[str, Any]] = {}
        atoms_to_update: list[TheoryAtom] = []
        relations_to_update: list[dict[str, Any]] = []

        {a.id: a for a in input.theory_atoms}

        for cluster in clusters:
            for theory_id in cluster.claimant_theory_ids:
                theory = self.registry.get(theory_id)
                if not theory:
                    continue

                # Step 2: Project cluster through the theory-specific lens (Phi_spec)
                if hasattr(self.projector, "aproject"):
                    projected_params = await self.projector.aproject(cluster, theory)
                else:
                    projected_params = self.projector.project(cluster, theory)
                cluster_theory_params[(cluster.cluster_id, theory_id)] = projected_params

                self.event_emitter.emit(
                    TheoreticalParametersProjected(
                        run_id=context.run_id,
                        phase=self.name,
                        cluster_id=cluster.cluster_id,
                        theory_id=theory_id,
                        parameters=projected_params,
                    )
                )

                # Step 3: Local Tenability Calculation (TS_local)
                ts_local, delta_star, local_anomalies = self.solver.solve_local_tenability(
                    projected_params, theory
                )

                for anom in local_anomalies:
                    self.event_emitter.emit(
                        TenabilityAnomalyDetected(
                            run_id=context.run_id,
                            phase=self.name,
                            element_id=cluster.cluster_id,
                            theory_id=theory_id,
                            score=ts_local,
                            reason=anom,
                        )
                    )

                # Step 4: Edge Tenability Calculation (TS_edge) across cluster relations
                edge_scores: dict[str, float] = {}
                edge_anomalies: list[str] = []

                for rel in cluster.relations:
                    rel_key = f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"

                    # Look up counterpart params (either target node's cluster or sibling theory)
                    target_params = self._find_target_parameters(
                        rel.target_id, clusters, cluster_theory_params, theory_id
                    )

                    ts_edge, _delta_c, anoms = self.solver.solve_edge_tenability(
                        source_params=projected_params,
                        target_params=target_params,
                        relation=rel,
                    )
                    edge_scores[rel_key] = ts_edge
                    edge_anomalies.extend(anoms)

                    for anom in anoms:
                        self.event_emitter.emit(
                            TenabilityAnomalyDetected(
                                run_id=context.run_id,
                                phase=self.name,
                                element_id=rel_key,
                                theory_id=theory_id,
                                score=ts_edge,
                                reason=anom,
                            )
                        )

                    # Stage relation for graph update
                    rel_copy = rel.model_copy()
                    rel_copy.tenability = ts_edge
                    relations_to_update.append(
                        {
                            "from_id": rel.source_id,
                            "relation_type": rel.relation_type,
                            "to_id": rel.target_id,
                            "properties": {
                                "confidence": rel.confidence,
                                "scope": rel.scope,
                                "tenability": ts_edge,
                                "weight": rel.weight,
                            },
                        }
                    )

                tenability_res = self.solver.evaluate_theory_tenability(
                    local_score=ts_local,
                    edge_scores=edge_scores,
                    delta_star=delta_star,
                    local_anomalies=local_anomalies,
                    edge_anomalies=edge_anomalies,
                )

                self.event_emitter.emit(
                    TenabilityEvaluationCompleted(
                        run_id=context.run_id,
                        phase=self.name,
                        theory_id=theory_id,
                        local_score=ts_local,
                        aggregated_score=tenability_res.aggregated_score,
                        is_tenable=tenability_res.is_tenable,
                        tightest_blur=delta_star,
                    )
                )

                # Attach parameters and scores to TheoreticalHypothesis nodes in the cluster
                for obs in cluster.observations:
                    if self.schema.component_partitions.get(obs.component_type) == "A":
                        obs_updated = obs.model_copy()
                        obs_updated.parameters.update(projected_params)
                        obs_updated.tenability = tenability_res
                        atoms_to_update.append(obs_updated)

                enrichment_payload = TheoreticalEnrichmentArtifact(
                    enrichment_id=f"enrichment-{uuid4()}",
                    cluster_id=cluster.cluster_id,
                    theory_id=theory_id,
                    projected_parameters=projected_params,
                    local_tenability=ts_local,
                    edge_tenabilities=edge_scores,
                    aggregated_tenability=tenability_res.aggregated_score,
                    admissible_blur_delta=delta_star,
                    is_tenable=tenability_res.is_tenable,
                    anomalies=tenability_res.anomalies,
                )

                envelope = ArtifactEnvelope[TheoreticalEnrichmentArtifact](
                    artifact_id=enrichment_payload.enrichment_id,
                    kind=ArtifactKind.THEORETICAL_ENRICHMENT,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="theoretical_enrichment",
                    payload=enrichment_payload,
                    provenance=ArtifactProvenance(
                        source_chunk_id=cluster.observations[0].source_chunk_id
                        if cluster.observations
                        else None
                    ),
                )
                enrichment_artifacts.append(envelope)

        # -------------------------------------------------------------
        # Step 5: Graph Persistence
        # -------------------------------------------------------------
        if self.graph_store:
            from itertools import batched

            if atoms_to_update:
                for batch in batched(atoms_to_update, 500):
                    await self.graph_store.upsert_argument_components(list(batch))

            if relations_to_update:
                for batch in batched(relations_to_update, 500):
                    await self.graph_store.upsert_relations(list(batch))

            logger.info(
                "Theoretical Enrichment: Projected %d enriched TheoryAtoms and %d relations to graph store",
                len(atoms_to_update),
                len(relations_to_update),
            )

        return ArtifactCollection(enrichment_artifacts)

    def _identify_empirical_clusters(
        self, atoms: list[TheoryAtom], relations: list[TheoryRelation]
    ) -> list[EmpiricalCluster]:
        """Group ObservationUnit nodes into empirical clusters (Intended Applications).

        Parameters
        ----------
        atoms : list[TheoryAtom]
            Input theory atoms.
        relations : list[TheoryRelation]
            Input theory relations.

        Returns
        -------
        list[EmpiricalCluster]
            List of empirical clusters.
        """
        # Group observation units by chunk id as base empirical partitions
        clusters_by_chunk: dict[str, list[TheoryAtom]] = {}
        for atom in atoms:
            clusters_by_chunk.setdefault(atom.source_chunk_id, []).append(atom)

        rel_by_chunk: dict[str, list[TheoryRelation]] = {}
        atom_chunk_map = {a.id: a.source_chunk_id for a in atoms}
        for rel in relations:
            chunk_s = atom_chunk_map.get(rel.source_id)
            if chunk_s:
                rel_by_chunk.setdefault(chunk_s, []).append(rel)

        clusters: list[EmpiricalCluster] = []
        for chunk_id, cluster_atoms in clusters_by_chunk.items():
            cluster_id = f"cluster-{chunk_id}"
            cluster_rels = rel_by_chunk.get(chunk_id, [])
            clusters.append(
                EmpiricalCluster(
                    cluster_id=cluster_id,
                    observations=cluster_atoms,
                    claimant_theory_ids=[],
                    relations=cluster_rels,
                )
            )

        return clusters

    def _find_target_parameters(
        self,
        target_id: str,
        clusters: list[EmpiricalCluster],
        cluster_theory_params: dict[tuple[str, str], dict[str, Any]],
        current_theory_id: str,
    ) -> dict[str, Any]:
        """Find parameters postulated at a target node or its associated theories."""
        # Find which cluster target_id belongs to
        for cluster in clusters:
            for obs in cluster.observations:
                if obs.id == target_id:
                    # Check if current theory or an overlapping theory has projected parameters
                    for (c_id, t_id), params in cluster_theory_params.items():
                        if c_id == cluster.cluster_id:
                            return params

        # Fallback to current parameters if self-referential or not yet resolved
        return {}
