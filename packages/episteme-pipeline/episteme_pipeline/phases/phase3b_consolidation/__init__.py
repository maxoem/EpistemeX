"""Phase 3b: Latent Graph Consolidation."""

from episteme_pipeline.config import Phase3bConfig
from episteme_pipeline.artifacts.builders import build_canonicalization_artifact
from episteme_pipeline.phases.phase3b_consolidation.clustering import (
    elect_canonical_representative,
    verify_borderline_pair,
)
from episteme_pipeline.phases.phase3b_consolidation.consolidation import LatentGraphConsolidation
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import InstanceFusion
from episteme_pipeline.protocols.graph_store import FusionGraph
from episteme_pipeline.artifacts.execution import ArtifactCollection, ArtifactExecutionContext, Phase3ArtifactsView
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import ProgressCompleted, ProgressStarted
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
        graph_store: FusionGraph,
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
        graph_store : FusionGraph
            The graph database store to interact with the constructed graph.
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

    @property
    def event_emitter(self) -> EventEmitter:
        from episteme_pipeline.events.context import get_event_emitter
        return get_event_emitter()

    async def run(self, input: Phase3ArtifactsView, context: ArtifactExecutionContext) -> ArtifactCollection:
        """Run the Latent Graph Consolidation phase.

        Sweeps the graph L2 nodes, finds duplicates using vector similarity and 1-hop relation overlap,
        and generates Canonicalization artifacts representing the duplicate-to-canonical mapping.

        Parameters
        ----------
        input : Phase3ArtifactsView
            View of the artifacts generated up to Phase 3.
        context : ArtifactExecutionContext
            The context of the current pipeline execution.

        Returns
        -------
        ArtifactCollection
            A collection of canonicalization artifacts.
        """
        if not self.config.enabled:
            return ArtifactCollection([])
        
        progress_task = "Phase 3b: Latent Consolidation"
        self.event_emitter.emit(
            ProgressStarted(task_name=progress_task, total_items=1, description="Latent Consolidation")
        )
        fused_map = await self.instance_fusion.fuse(self.graph_store)
        self.event_emitter.emit(ProgressCompleted(task_name=progress_task))

        artifacts = []
        for original_id, canonical_id in fused_map.items():
            artifacts.append(
                build_canonicalization_artifact(
                    original_id, 
                    canonical_id, 
                    run_id=context.run_id, 
                    phase_name=self.name, 
                    method="phase3b.latent_consolidation"
                )
            )
        return ArtifactCollection(artifacts)

