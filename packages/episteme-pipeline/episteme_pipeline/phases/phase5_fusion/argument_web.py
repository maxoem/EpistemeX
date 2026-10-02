from episteme_pipeline.artifacts.builders import build_fusion_cluster_artifact
from episteme_pipeline.artifacts.execution import ArtifactCollection, ArtifactExecutionContext, Phase4ArtifactsView
from episteme_pipeline.config import Phase5Config
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import ProgressCompleted, ProgressStarted
from episteme_pipeline.phases.phase5_fusion.argument_clustering import (
    EmbeddingArgumentClustering,
    InterDocumentClusterVerifier,
)
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import ArgumentClustering, TheoryFusion
from episteme_pipeline.protocols.graph_store import FusionGraph
from episteme_pipeline.protocols.phase_runner import PhaseRunner


class Phase5ArgumentWebRunner(PhaseRunner[Phase4ArtifactsView]):
    """Runner for Phase 5: Inter-Document Argument Web and Global Theory Fusion.

    Constructs cross-document argument networks, detects macro-communities of
    theories, and verifies inter-document cluster equivalence using calibrated
    decision engine gating and conformal prediction sets.
    """
    name = "Phase 5: Inter-Document Argument Web"
    phase_key = "phase5"
    input_view = Phase4ArtifactsView

    def __init__(
        self,
        config: Phase5Config,
        *,
        embedding_model,
        graph_store: FusionGraph,
        argument_clustering: ArgumentClustering | None = None,
        theory_fusion: TheoryFusion | None = None,
        decision_engine: DecisionEngine | None = None,
        cluster_verifier: InterDocumentClusterVerifier | None = None,
    ) -> None:
        """Initialize Phase 5 Argument Web and Theory Fusion runner.

        Parameters
        ----------
        config : Phase5Config
            Phase 5 configuration parameters.
        embedding_model : object
            Embedding model for projecting argument and entity texts.
        graph_store : FusionGraph
            Graph database store containing TheoryAtom and L2Entity nodes.
        argument_clustering : ArgumentClustering, optional
            Clustering engine for grouping equivalent argument components.
        theory_fusion : TheoryFusion, optional
            Theory fusion engine (e.g. Leiden community detection).
        decision_engine : DecisionEngine, optional
            Calibrated decision engine for System 1 semantic cluster verification.
        cluster_verifier : InterDocumentClusterVerifier, optional
            Verifier for candidate inter-document cluster equivalence.
        """
        self.config = config
        self.graph_store = graph_store
        self.embedding_model = embedding_model
        self.decision_engine = decision_engine
        self.cluster_verifier = cluster_verifier or (
            InterDocumentClusterVerifier.from_config(config.gating, decision_engine)
            if config.gating.enabled and decision_engine is not None
            else None
        )
        self.argument_clustering = argument_clustering or EmbeddingArgumentClustering(
            embedding_model=embedding_model,
            similarity_threshold=config.fusion_similarity_threshold,
        )
        from episteme_pipeline.phases.phase5_fusion.leiden_clustering import LeidenTheoryClustering

        self.theory_fusion = theory_fusion or LeidenTheoryClustering.from_config(
            config,
            decision_engine=decision_engine,
            cluster_verifier=self.cluster_verifier,
        )

    @property
    def event_emitter(self) -> EventEmitter:
        from episteme_pipeline.events.context import get_event_emitter
        return get_event_emitter()

    async def run(self, input: Phase4ArtifactsView, context: ArtifactExecutionContext) -> ArtifactCollection:
        """Execute Phase 5 argument clustering and theory fusion passes.

        Parameters
        ----------
        input : Phase4ArtifactsView
            Artifacts from Phase 4 argument mining.
        context : ArtifactExecutionContext
            Run context.
        Returns
        -------
        ArtifactCollection
            Generated fusion cluster artifacts.
        """
        progress_task = "Phase 5: Argument Web & Theory Fusion"
        self.event_emitter.emit(
            ProgressStarted(task_name=progress_task, total_items=1, description="Theory Fusion")
        )

        cluster_ids: list[list[str]] = []
        if self.config.argument_clustering_enabled:
            raw_cluster_ids = await self.argument_clustering.cluster(self.graph_store)
            if self.cluster_verifier is not None:
                cluster_ids = await self.cluster_verifier.filter_clusters(raw_cluster_ids, self.graph_store)
            else:
                cluster_ids = raw_cluster_ids

        theory_fusion_applied = False
        if self.config.theory_fusion_enabled and self.theory_fusion is not None:
            await self.theory_fusion.fuse(self.graph_store)
            theory_fusion_applied = True

        self.event_emitter.emit(ProgressCompleted(task_name=progress_task))

        artifacts = [
            build_fusion_cluster_artifact(
                cluster,
                theory_fusion_applied,
                run_id=context.run_id,
                phase_name=self.name,
                method="phase5.fusion",
            )
            for cluster in cluster_ids
        ]
        return ArtifactCollection(artifacts)

