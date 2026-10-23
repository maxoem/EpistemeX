"""Phase 3b: Latent Graph Consolidation."""

from __future__ import annotations

from episteme_pipeline.artifacts.builders import build_canonicalization_artifact
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
)
from episteme_pipeline.config import Phase3bConfig
from episteme_pipeline.phases.phase3b_consolidation.clustering import (
    elect_canonical_representative,
    verify_borderline_pair,
)
from episteme_pipeline.phases.phase3b_consolidation.consolidation import (
    LatentGraphConsolidation,
)
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import InstanceFusion
from episteme_pipeline.protocols.graph_store import FusionGraph, GraphReader
from episteme_pipeline.protocols.phase_runner import PhaseRunner


class Phase3bLatentConsolidationRunner(PhaseRunner[Phase3ArtifactsView]):
    """Runner for Phase 3b: Latent Graph Consolidation.

    A fast mathematical sweep over dense vectors to merge duplicate nodes
    caused by parallel processing collisions. Runs without LLM calls.
    """

    name = "Phase 3b: Latent Graph Consolidation"
    phase_key = "phase3b"
    input_view = Phase3ArtifactsView

    def __init__(
        self,
        config: Phase3bConfig,
        *,
        embedding_model,
        graph_store: FusionGraph | GraphReader | None = None,
        instance_fusion: InstanceFusion | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        """Initialize the Phase 3b runner.

        Parameters
        ----------
        config : Phase3bConfig
            Configuration settings for Phase 3b.
        embedding_model : object
            The embedding model used to project textual envelopes into vector space.
        graph_store : FusionGraph | GraphReader | None, optional
            Optional graph store fallback when running outside artifact-native views.
        instance_fusion : InstanceFusion, optional
            An optional custom InstanceFusion implementation. Defaults to LatentGraphConsolidation.
        decision_engine : DecisionEngine, optional
            Calibrated decision engine for System 1 borderline pair verification
            and canonical representative election.
        """
        self.config = config
        self.graph_store = graph_store
        # Kept on the runner so Pipeline._method_fingerprints can see it — a
        # phase whose embedding model is invisible to invalidation is reused
        # across a model change (O-15).
        self.embedding_model = embedding_model
        self.decision_engine = decision_engine
        self.instance_fusion = instance_fusion or LatentGraphConsolidation.from_config(
            config=config,
            embedding_model=embedding_model,
            decision_engine=decision_engine,
        )

    async def run(
        self, input: Phase2ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Run the Latent Graph Consolidation phase.

        Sweeps the graph L2 nodes, finds duplicates using vector similarity and 1-hop relation overlap,
        and generates Canonicalization artifacts representing the duplicate-to-canonical mapping.

        Parameters
        ----------
        input : Phase2ArtifactsView
            View of the artifacts generated up to Phase 2 / Phase 3.
        context : ArtifactExecutionContext
            The context of the current pipeline execution.

        Returns
        -------
        ArtifactCollection
            A collection of canonicalization artifacts.
        """
        if not self.config.enabled:
            return ArtifactCollection([])

        reader = (
            input.to_graph_reader()
            if (input.entities or self.graph_store is None)
            else self.graph_store
        )

        ledger = (
            context.pipeline_input.resolved_curation_ledger()
            if context and context.pipeline_input
            else None
        )

        progress_task = "Phase 3b: Latent Consolidation"
        with self.progress_scope(
            progress_task, total_items=1, description="Latent Consolidation"
        ) as advance:
            fused_map = await self.instance_fusion.fuse(reader, curation_ledger=ledger)  # type: ignore[arg-type]
            advance(1)

        artifacts = []
        for original_id, canonical_id in fused_map.items():
            artifacts.append(
                build_canonicalization_artifact(
                    original_id,
                    canonical_id,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="phase3b.latent_consolidation",
                )
            )
        return ArtifactCollection(artifacts)


__all__ = [
    "LatentGraphConsolidation",
    "Phase3bLatentConsolidationRunner",
    "elect_canonical_representative",
    "verify_borderline_pair",
]

