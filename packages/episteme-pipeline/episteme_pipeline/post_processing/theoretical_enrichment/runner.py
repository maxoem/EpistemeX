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
from episteme_pipeline.protocols.graph_store import PhaseCheckpointStore, ProjectionGraph
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runtime.batch_executor import CheckpointedBatchExecutor
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
    dependencies = ("phase4",)
    input_view = Phase4ArtifactsView
    reads_kinds = frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION})
    writes_kinds = frozenset({ArtifactKind.THEORETICAL_ENRICHMENT})

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
        atoms = (
            input.canonical_theory_atoms
            if input.canonical_theory_atoms
            else input.theory_atoms
        )
        relations = (
            input.canonical_theory_relations
            if input.canonical_theory_relations
            else input.theory_relations
        )
        logger.info(
            "Theoretical Enrichment: Beginning evaluation on %d atoms and %d relations",
            len(atoms),
            len(relations),
        )

        if not self.config.enabled:
            logger.info("Theoretical Enrichment is disabled in config. Skipping.")
            return ArtifactCollection([])

        total_items = len(atoms) + len(relations)
        with self.progress_scope(
            "Theoretical Enrichment",
            total_items=total_items,
            description="Theoretical Enrichment",
        ) as advance:
            artifacts, updated_count = await self._run_enrichment(input, context)
            advance(updated_count)
            return artifacts

    async def _run_enrichment(
        self, input: Phase4ArtifactsView, context: ArtifactExecutionContext
    ) -> tuple[ArtifactCollection, int]:
        """Execute core enrichment and tenability evaluation passes.

        Parameters
        ----------
        input : Phase4ArtifactsView
            Typed slice of upstream Phase 4/5 theory atoms and relations.
        context : ArtifactExecutionContext
            Execution run context.

        Returns
        -------
        tuple of (ArtifactCollection, int)
            Collection of generated artifacts and total update count.
        """
        atoms = (
            input.canonical_theory_atoms
            if input.canonical_theory_atoms
            else input.theory_atoms
        )
        relations = (
            input.canonical_theory_relations
            if input.canonical_theory_relations
            else input.theory_relations
        )
        # -------------------------------------------------------------
        # Stage 0: Dynamic Theory-Element Induction (Macro Scope)
        # -------------------------------------------------------------
        if not self.registry.all_theories() and self.config.induce_theories and self.inducer:
            logger.info("Theoretical Enrichment: Registry is unseeded. Running LLM Theory-Element induction...")
            induced = await self.inducer.induce_theories(
                atoms=atoms,
                relations=relations,
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
        clusters = self._identify_empirical_clusters(atoms, relations)
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
        # -------------------------------------------------------------
        # Step 2: Domain-Specific Projections (Phi_spec) & Local Tenability (TS_local)
        # Pass 1: Project parameters and evaluate local tenability for all (cluster, theory) pairs
        # -------------------------------------------------------------
        cluster_theory_params: dict[tuple[str, str], dict[str, Any]] = {}
        cluster_local_results: dict[tuple[str, str], tuple[float, float, list[str]]] = {}

        checkpoint_store = (
            self.graph_store
            if isinstance(self.graph_store, PhaseCheckpointStore)
            else None
        )
        effective_phase = (
            f"{self.phase_key}:{context.lineage_fingerprint}"
            if context and context.lineage_fingerprint
            else self.phase_key
        )

        eval_items: list[tuple[EmpiricalCluster, str]] = [
            (cluster, theory_id)
            for cluster in clusters
            for theory_id in cluster.claimant_theory_ids
            if self.registry.get(theory_id) is not None
        ]

        async def _eval_cluster_theory(
            item: tuple[EmpiricalCluster, str],
        ) -> tuple[str, str, dict[str, Any], tuple[float, float, list[str]]]:
            cluster, theory_id = item
            theory = self.registry.get(theory_id)
            assert theory is not None
            projected_params = await self.projector.aproject(cluster, theory)
            ts_local, delta_star, local_anomalies = self.solver.solve_local_tenability(
                projected_params, theory
            )
            return (
                cluster.cluster_id,
                theory_id,
                projected_params,
                (ts_local, delta_star, local_anomalies),
            )

        async def _on_enrichment_batch(
            batch_results: list[
                tuple[str, str, dict[str, Any], tuple[float, float, list[str]]]
            ],
            records: list[PhaseItemRecord],
        ) -> None:
            for cluster_id, theory_id, params, local_res in batch_results:
                cluster_theory_params[(cluster_id, theory_id)] = params
                cluster_local_results[(cluster_id, theory_id)] = local_res
                self.event_emitter.emit(
                    TheoreticalParametersProjected(
                        run_id=context.run_id,
                        phase=self.name,
                        cluster_id=cluster_id,
                        theory_id=theory_id,
                        parameters=params,
                    )
                )
                ts_local, delta_star, local_anomalies = local_res
                for anom in local_anomalies:
                    self.event_emitter.emit(
                        TenabilityAnomalyDetected(
                            run_id=context.run_id,
                            phase=self.name,
                            element_id=cluster_id,
                            theory_id=theory_id,
                            score=ts_local,
                            reason=anom,
                        )
                    )

        executor = CheckpointedBatchExecutor[
            tuple[EmpiricalCluster, str],
            tuple[str, str, dict[str, Any], tuple[float, float, list[str]]],
        ](
            checkpoint_store=checkpoint_store,
            phase_tag=effective_phase,
            batch_size=10,
            item_key_fn=lambda it: f"enrichment::{it[0].cluster_id}::{it[1]}",
            process_item_fn=_eval_cluster_theory,
            on_batch_complete=_on_enrichment_batch,
            guard_systematic_failure=False,
        )
        await executor.execute(eval_items)

        # -------------------------------------------------------------
        # Step 4: Edge Tenability & Aggregated Consistency (TS_edge, GL)
        # Pass 2: Evaluate inter-cluster / intertheoretical edge tenability with complete parameter map
        # -------------------------------------------------------------
        from episteme_pipeline.artifacts.builders import (
            build_argument_relation_artifact,
            build_theory_atom_artifact,
        )
        from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector

        enrichment_artifacts: list[ArtifactEnvelope[Any]] = []
        enrichment_payloads: list[tuple[TheoreticalEnrichmentArtifact, EmpiricalCluster]] = []
        updated_atoms_by_id: dict[str, TheoryAtom] = {}
        updated_rels_by_key: dict[str, TheoryRelation] = {}
        atoms_by_id: dict[str, TheoryAtom] = {a.id: a for a in atoms}

        for cluster in clusters:
            for theory_id in cluster.claimant_theory_ids:
                theory = self.registry.get(theory_id)
                if not theory or (cluster.cluster_id, theory_id) not in cluster_theory_params:
                    continue

                projected_params = cluster_theory_params[(cluster.cluster_id, theory_id)]
                ts_local, delta_star, local_anomalies = cluster_local_results[
                    (cluster.cluster_id, theory_id)
                ]

                # Step 4: Edge Tenability Calculation (TS_edge) across cluster relations
                edge_scores: dict[str, float] = {}
                edge_anomalies: list[str] = []

                for rel in cluster.relations:
                    rel_key = f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"

                    # Look up counterpart params across fully-populated cluster_theory_params
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

                    # Stage relation for graph and D-QBAF update
                    base_rel = updated_rels_by_key.get(rel_key, rel)
                    rel_copy = base_rel.model_copy()
                    rel_copy.tenability = ts_edge
                    rel_copy.edge_tenability = ts_edge
                    updated_rels_by_key[rel_key] = rel_copy

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

                # Attach parameters and local tenability scores to claimant hypothesis nodes
                claimant_ids = set(theory.claimant_hypothesis_ids or [])
                matched_atom_ids: list[str] = []
                candidate_atoms: list[TheoryAtom] = []
                cluster_has_measurements = any(
                    bool(obs.measurements) for obs in cluster.observations
                )
                if claimant_ids:
                    candidate_atoms = [
                        obs for obs in cluster.observations if obs.id in claimant_ids
                    ]
                    if not candidate_atoms and (
                        cluster_has_measurements or len(clusters) == 1
                    ):
                        candidate_atoms = [
                            atoms_by_id[cid]
                            for cid in claimant_ids
                            if cid in atoms_by_id
                        ]
                if not candidate_atoms:
                    candidate_atoms = [
                        obs
                        for obs in cluster.observations
                        if self.schema.component_partitions.get(obs.component_type) == "A"
                        or obs.component_type != "ObservationUnit"
                    ]
                if not candidate_atoms:
                    candidate_atoms = list(cluster.observations)

                for obs in candidate_atoms:
                    base_atom = updated_atoms_by_id.get(obs.id, obs)
                    obs_updated = base_atom.model_copy()
                    obs_updated.parameters.update(projected_params)
                    if (
                        obs_updated.local_tenability is None
                        or ts_local <= obs_updated.local_tenability
                    ):
                        obs_updated.tenability = tenability_res
                        obs_updated.local_tenability = ts_local
                    updated_atoms_by_id[obs_updated.id] = obs_updated
                    matched_atom_ids.append(obs_updated.id)

                enrichment_payload = TheoreticalEnrichmentArtifact(
                    enrichment_id=f"enrichment-{uuid4()}",
                    cluster_id=cluster.cluster_id,
                    theory_id=theory_id,
                    claimant_atom_ids=matched_atom_ids,
                    projected_parameters=projected_params,
                    local_tenability=ts_local,
                    edge_tenabilities=edge_scores,
                    aggregated_tenability=tenability_res.aggregated_score,
                    admissible_blur_delta=delta_star,
                    is_tenable=tenability_res.is_tenable,
                    anomalies=tenability_res.anomalies,
                )
                enrichment_payloads.append((enrichment_payload, cluster))

        # -------------------------------------------------------------
        # Step 4.5: Coupled D-QBAF Equilibrium Re-Convergence
        # Propagate empirical tenability (TS_local, TS_edge) into D-QBAF tau*(a)
        # -------------------------------------------------------------
        merged_atoms = [updated_atoms_by_id.get(a.id, a) for a in atoms]
        merged_relations = [
            updated_rels_by_key.get(
                f"{r.source_id}->{r.relation_type}->{r.target_id}", r
            )
            for r in relations
        ]
        reconverged_net = TheoryNetProjector(schema=self.schema).project(
            Phase4ArtifactsView(
                theory_atoms=merged_atoms,
                theory_relations=merged_relations,
            )
        )
        reconverged_atoms_by_id = {a.id: a for a in reconverged_net.atoms}
        reconverged_rels_by_key = {
            f"{r.source_id}->{r.relation_type}->{r.target_id}": r
            for r in reconverged_net.relations
        }
        equilibrium_map = {
            a.id: float(a.equilibrium_strength)
            for a in reconverged_net.atoms
            if a.equilibrium_strength is not None
        }

        atoms_to_update: list[TheoryAtom] = []
        for aid, orig_updated in updated_atoms_by_id.items():
            reconv = reconverged_atoms_by_id.get(aid)
            if reconv is not None:
                orig_updated.equilibrium_strength = reconv.equilibrium_strength
                orig_updated.plausibility = reconv.plausibility
                orig_updated.controversy_volatility = reconv.controversy_volatility
            atoms_to_update.append(orig_updated)

        # Also include downstream atoms whose D-QBAF equilibrium shifted due to tenability feedback
        for reconv in reconverged_net.atoms:
            if reconv.id not in updated_atoms_by_id:
                orig_atom = atoms_by_id.get(reconv.id)
                if orig_atom is not None and (
                    orig_atom.plausibility != reconv.plausibility
                    or orig_atom.equilibrium_strength != reconv.equilibrium_strength
                ):
                    atoms_to_update.append(reconv)

        relations_to_update: list[TheoryRelation] = [
            reconverged_rels_by_key.get(rkey, rel_obj)
            for rkey, rel_obj in updated_rels_by_key.items()
        ]

        for enrichment_payload, cluster in enrichment_payloads:
            enrichment_payload.equilibrium_strengths = dict(equilibrium_map)
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

        for atom_upd in atoms_to_update:
            enrichment_artifacts.append(
                build_theory_atom_artifact(
                    atom_upd,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="theoretical_enrichment.dqbaf_reconvergence",
                )
            )
        for rel_upd in relations_to_update:
            enrichment_artifacts.append(
                build_argument_relation_artifact(
                    rel_upd,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="theoretical_enrichment.dqbaf_reconvergence",
                )
            )

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
                    await self.graph_store.upsert_theory_relations(list(batch))

            logger.info(
                "Theoretical Enrichment: Projected %d enriched TheoryAtoms and %d relations to graph store",
                len(atoms_to_update),
                len(relations_to_update),
            )

        return ArtifactCollection(enrichment_artifacts), len(atoms_to_update) + len(relations_to_update)

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
        """Find parameters postulated at a target node or its associated theories.

        Parameters
        ----------
        target_id : str
            Identifier of target observation node.
        clusters : list of EmpiricalCluster
            All empirical clusters.
        cluster_theory_params : dict
            Projected parameters mapped by (cluster_id, theory_id).
        current_theory_id : str
            Identifier of the evaluating theory.

        Returns
        -------
        dict[str, Any]
            Parameters for the target node/cluster, or empty dict if unresolved.
        """
        for cluster in clusters:
            for obs in cluster.observations:
                if obs.id == target_id:
                    # Prefer matching current_theory_id first if present
                    if (cluster.cluster_id, current_theory_id) in cluster_theory_params:
                        return cluster_theory_params[(cluster.cluster_id, current_theory_id)]
                    for (c_id, t_id), params in cluster_theory_params.items():
                        if c_id == cluster.cluster_id:
                            return params

        # Fallback to current parameters if self-referential or not yet resolved
        return {}
