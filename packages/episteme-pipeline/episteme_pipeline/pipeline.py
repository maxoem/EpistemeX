"""Main pipeline orchestration facade (ISSUE-058).

Delegates dependency injection and component normalization to
:class:`~episteme_pipeline.runtime.pipeline_factory.PipelineFactory`,
declarative phase topology and quality gate binding to
:class:`~episteme_pipeline.runtime.workflow_dag.WorkflowDAG`, and artifact-native
execution, caching, hydration, and observability to
:class:`~episteme_pipeline.runtime.execution_engine.ArtifactExecutionEngine`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import EventEmitter, NoOpEventEmitter
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.extractors import (
    CrossEncoder,
    EmbeddingModel,
    RelationReranker,
)
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.quality_gate import EpistemicQualityGate
from episteme_pipeline.runs.models import (
    ArtifactReportEntry,
    ExecutionResult,
    RunReport,
)
from episteme_pipeline.runs.persistence import JsonRunManifestStore
from episteme_pipeline.runtime.execution_engine import (
    ArtifactExecutionEngine,
    _artifact_kind_str,
)
from episteme_pipeline.runtime.pipeline_factory import (
    SUPPORTED_TASKS,
    PipelineFactory,
)
from episteme_pipeline.runtime.quality_gates import build_default_quality_gates
from episteme_pipeline.runtime.workflow_dag import WorkflowDAG, WorkflowNode

_SUPPORTED_TASKS = SUPPORTED_TASKS
_PhaseEntry = WorkflowNode


class Pipeline:
    """High-level pipeline orchestrator facade.

    Coordinates :class:`PipelineFactory` (composition root), :class:`WorkflowDAG`
    (declarative phase topology and epistemic quality gates), and
    :class:`ArtifactExecutionEngine` (manifest fingerprinting, DAG cache reuse,
    artifact hydration, graph projection, and event lifecycle management).

    Parameters
    ----------
    phases : list of PhaseRunner, optional
        Ordered phase runners. Ignored when ``workflow`` is explicitly provided.
    config : PipelineConfig
        Top-level pipeline configuration.
    graph_reader : Any, optional
        Graph reader implementation.
    projection_graph : Any, optional
        Projection graph implementation.
    checkpoint_store : Any, optional
        Within-phase checkpoint store.
    event_emitter : EventEmitter or None, optional
        Domain event emitter.
    decision_engine : DecisionEngine or None, optional
        Optional System 1 decision engine.
    modal_resolver : ModalStrengthResolver or None, optional
        Optional modal strength resolver.
    quality_gates : Sequence of EpistemicQualityGate or None, optional
        Explicit inter-phase quality gates. When None and
        ``config.quality_gates.enabled`` is True, default quality gates are
        constructed via :func:`build_default_quality_gates`.
    workflow : WorkflowDAG or None, optional
        Pre-constructed declarative workflow DAG.
    engine : ArtifactExecutionEngine or None, optional
        Pre-constructed artifact execution engine.
    """

    def __init__(
        self,
        *,
        phases: list[PhaseRunner[Any]] | None = None,
        config: PipelineConfig,
        graph_reader: Any = None,
        projection_graph: Any = None,
        checkpoint_store: Any = None,
        event_emitter: EventEmitter | None = None,
        decision_engine: DecisionEngine | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        quality_gates: Sequence[EpistemicQualityGate] | None = None,
        workflow: WorkflowDAG | None = None,
        engine: ArtifactExecutionEngine | None = None,
    ) -> None:
        self.config = config
        self.graph_reader = graph_reader
        self.projection_graph = projection_graph
        if checkpoint_store is None:
            checkpoint_store = FileSystemCheckpointStore(
                Path(self.config.execution.artifacts_dir) / "_checkpoints"
            )
        self.checkpoint_store = checkpoint_store
        self.event_emitter: EventEmitter = event_emitter or NoOpEventEmitter()
        self.decision_engine = decision_engine
        self.modal_resolver = modal_resolver

        resolved_gates: Sequence[EpistemicQualityGate] = (
            quality_gates
            if quality_gates is not None
            else build_default_quality_gates(
                config, decision_engine=decision_engine
            )
        )

        if workflow is not None:
            self.workflow = workflow
            self.phases = list(workflow.phases)
        else:
            resolved_phases = list(phases or [])
            self.phases = resolved_phases
            self.workflow = WorkflowDAG(
                phases=resolved_phases,
                quality_gates=resolved_gates,
            )

        self.engine = engine or ArtifactExecutionEngine(
            workflow=self.workflow,
            config=self.config,
            projection_graph=self.projection_graph,
            checkpoint_store=self.checkpoint_store,
            event_emitter=self.event_emitter,
            decision_engine=self.decision_engine,
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic fingerprint dictionary for the pipeline.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of the pipeline's workflow and engine.
        """
        return {
            "class": self.__class__.__name__,
            "workflow": self.workflow.fingerprint(),
            "engine": self.engine.fingerprint(),
        }

    @property
    def quality_gates(self) -> tuple[EpistemicQualityGate, ...]:
        """Return the epistemic quality gates attached to the workflow DAG."""
        return self.workflow.quality_gates

    @property
    def manifest_store(self) -> JsonRunManifestStore:
        """Return the underlying run manifest store."""
        return self.engine.manifest_store

    @manifest_store.setter
    def manifest_store(self, value: JsonRunManifestStore) -> None:
        self.engine.manifest_store = value

    @property
    def artifact_store(self) -> JsonArtifactStore:
        """Return the underlying artifact store."""
        return self.engine.artifact_store

    @artifact_store.setter
    def artifact_store(self, value: JsonArtifactStore) -> None:
        self.engine.artifact_store = value

    @property
    def projector(self) -> ArtifactGraphProjector:
        """Return the underlying artifact graph projector."""
        return self.engine.projector

    @projector.setter
    def projector(self, value: ArtifactGraphProjector) -> None:
        self.engine.projector = value

    @classmethod
    def for_task(
        cls,
        *,
        task: str = "knowledge_graph",
        llm: Any,
        relation_reranker: RelationReranker | None = None,
        cross_encoder: CrossEncoder | None = None,
        entity_linker: Any | None = None,
        embedding_model: EmbeddingModel | Any = None,
        config: PipelineConfig,
        graph_reader: Any = None,
        projection_graph: Any = None,
        checkpoint_store: Any = None,
        event_emitter: EventEmitter | None = None,
        extra_phases: list[PhaseRunner[Any]] | None = None,
        post_processors: list[PhaseRunner[Any]] | None = None,
        working_memory_manager: Any | None = None,
        decision_engine: DecisionEngine | None = None,
        acc_classifier: Any | None = None,
        arc_classifier: Any | None = None,
        ner_extractor: Any | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        quality_gates: Sequence[EpistemicQualityGate] | None = None,
    ) -> Pipeline:
        """Create a pipeline for a specific task via :class:`PipelineFactory`.

        Parameters
        ----------
        task : str, default "knowledge_graph"
            Workflow task identifier.
        llm : Any
            Generative LLM instance.
        relation_reranker : RelationReranker or None, optional
            Scores candidate relations between entities and their subgraph envelopes.
        cross_encoder : CrossEncoder or None, optional
            Scores raw ``(query, document)`` text pairs.
        entity_linker : Any or None, optional
            Optional pre-constructed ``EntityLinker`` instance for Phase 2.
        embedding_model : EmbeddingModel or Any, optional
            Embedding model instance (normalized via ``ensure_embedding_model``).
        config : PipelineConfig
            Pipeline configuration.
        graph_reader : Any, optional
            Graph reader implementation.
        projection_graph : Any, optional
            Projection graph implementation.
        checkpoint_store : Any, optional
            Within-phase checkpoint store.
        event_emitter : EventEmitter or None, optional
            Domain event emitter.
        extra_phases : list of PhaseRunner or None, optional
            Additional phases appended to the workflow.
        post_processors : list of PhaseRunner or None, optional
            Post-processing phases appended after Phase 6.
        working_memory_manager : Any or None, optional
            Working memory manager for Phase 2.
        decision_engine : DecisionEngine or None, optional
            System 1 decision engine.
        acc_classifier : Any or None, optional
            Argument component classifier for Phase 4.
        arc_classifier : Any or None, optional
            Argument relation classifier for Phase 4.
        ner_extractor : Any or None, optional
            NER extractor for Phase 2.
        modal_resolver : ModalStrengthResolver or None, optional
            Modal strength resolver for Phase 4 and Phase 6.
        quality_gates : Sequence of EpistemicQualityGate or None, optional
            Explicit inter-phase quality gates.

        Returns
        -------
        Pipeline
            Configured pipeline instance backed by :class:`WorkflowDAG` and
            :class:`ArtifactExecutionEngine`.
        """
        return PipelineFactory.create_for_task(
            pipeline_cls=cls,
            task=task,
            llm=llm,
            relation_reranker=relation_reranker,
            cross_encoder=cross_encoder,
            entity_linker=entity_linker,
            embedding_model=embedding_model,
            config=config,
            graph_reader=graph_reader,
            projection_graph=projection_graph,
            checkpoint_store=checkpoint_store,
            event_emitter=event_emitter,
            extra_phases=extra_phases,
            post_processors=post_processors,
            working_memory_manager=working_memory_manager,
            decision_engine=decision_engine,
            acc_classifier=acc_classifier,
            arc_classifier=arc_classifier,
            ner_extractor=ner_extractor,
            modal_resolver=modal_resolver,
            quality_gates=quality_gates,
        )

    def phase_boundaries(self) -> list[tuple[int, str]]:
        """Return ``(ordinal, phase_name)`` boundaries for all workflow nodes.

        Returns
        -------
        list of tuple of (int, str)
            Ordered list of ``(ordinal, phase_name)`` pairs.
        """
        return self.workflow.phase_boundaries()

    async def run(
        self,
        input: PipelineInput,
        run_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> ExecutionResult:
        """Execute the pipeline with the given input using persisted-run semantics.

        Parameters
        ----------
        input : PipelineInput
            Pipeline input holding source documents, bib paths, and metadata.
        run_id : str or None, optional
            Explicit identifier for this execution run.
        parent_run_id : str or None, optional
            Optional identifier of parent run to fork or resume from.

        Returns
        -------
        ExecutionResult
            Execution result containing the run manifest and report.
        """
        return await self.engine.run(
            input=input, run_id=run_id, parent_run_id=parent_run_id
        )

    async def run_from_phase(
        self,
        phase_number: int,
        input: PipelineInput | None = None,
        run_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> ExecutionResult:
        """Execute or resume the pipeline starting from a specific phase boundary.

        Parameters
        ----------
        phase_number : int
            The 1-based index of the phase runner to start or resume from.
        input : PipelineInput or None, optional
            The pipeline input. If None, input paths are recovered from the latest
            manifest.
        run_id : str or None, optional
            Explicit identifier for this execution run.
        parent_run_id : str or None, optional
            Optional identifier of parent run to fork or resume from.

        Returns
        -------
        ExecutionResult
            Execution result containing the run manifest and report.
        """
        return await self.engine.run_from_phase(
            phase_number=phase_number,
            input=input,
            run_id=run_id,
            parent_run_id=parent_run_id,
        )

    async def resume_from_run(
        self,
        run_id: str,
        input: PipelineInput,
        from_phase: int | None = None,
    ) -> ExecutionResult:
        """Resume pipeline execution from a prior run within observability context."""
        return await self.engine.resume_from_run(
            run_id=run_id, input=input, from_phase=from_phase
        )

    async def diff_artifacts(
        self, run_id: str, baseline_run_id: str
    ) -> dict[str, list[str]]:
        """Compare artifacts of ``run_id`` against ``baseline_run_id``."""
        return await self.engine.diff_artifacts(run_id, baseline_run_id)

    async def get_run_report(self, run_id: str) -> RunReport:
        """Assemble a :class:`RunReport` for ``run_id``."""
        return await self.engine.get_run_report(run_id)

    async def get_run_artifacts(
        self,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Retrieve all report-level artifact entries associated with a run."""
        return await self.engine.get_run_artifacts(
            run_id, phase_name=phase_name, kind=kind
        )


__all__ = [
    "_SUPPORTED_TASKS",
    "ArtifactExecutionEngine",
    "Pipeline",
    "PipelineFactory",
    "WorkflowDAG",
    "WorkflowNode",
    "_PhaseEntry",
    "_artifact_kind_str",
]
