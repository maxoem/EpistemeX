"""Main pipeline orchestration facade (ISSUE-058).

Delegates dependency injection and component normalization to
:class:`~episteme_pipeline.runtime.pipeline_factory.PipelineFactory`,
declarative phase topology and quality gate binding to
:class:`~episteme_pipeline.runtime.workflow_dag.WorkflowDAG`, and artifact-native
execution, caching, hydration, and observability to
:class:`~episteme_pipeline.runtime.execution_engine.ArtifactExecutionEngine`.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
from episteme_pipeline.artifacts.execution import ArtifactCollection
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
    InvalidationDecision,
    ResumePoint,
    RunManifest,
    RunPhaseRecord,
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

    workflow: WorkflowDAG | None = None
    engine: ArtifactExecutionEngine | None = None
    event_emitter: EventEmitter | None = None
    decision_engine: DecisionEngine | None = None
    modal_resolver: ModalStrengthResolver | None = None
    _custom_phase_entries: list[WorkflowNode] | None = None

    def __init__(
        self,
        *,
        phases: list[PhaseRunner] | None = None,
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
        self._custom_phase_entries = None

        resolved_gates: Sequence[EpistemicQualityGate]
        if quality_gates is not None:
            resolved_gates = quality_gates
        else:
            resolved_gates = build_default_quality_gates(
                config, decision_engine=decision_engine
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

        if engine is not None:
            self.engine = engine
        else:
            self.engine = ArtifactExecutionEngine(
                workflow=self.workflow,
                config=self.config,
                projection_graph=self.projection_graph,
                checkpoint_store=self.checkpoint_store,
                event_emitter=self.event_emitter,
                decision_engine=self.decision_engine,
            )

    def _ensure_engine(self) -> ArtifactExecutionEngine:
        """Return the active execution engine, initializing a fallback if needed."""
        if self.engine is None:
            fallback_workflow = (
                self.workflow
                if self.workflow is not None
                else WorkflowDAG(phases=[])
            )
            self.engine = ArtifactExecutionEngine(
                workflow=fallback_workflow,
                config=self.config,
                decision_engine=self.decision_engine,
            )
        else:
            self.engine.config = self.config
            self.engine.event_emitter = self.event_emitter or NoOpEventEmitter()
            self.engine.decision_engine = self.decision_engine
        return self.engine

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic fingerprint dictionary for the pipeline.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of the pipeline's workflow and engine.
        """
        return {
            "class": self.__class__.__name__,
            "workflow": self.workflow.fingerprint() if self.workflow else {},
            "engine": self._ensure_engine().fingerprint(),
        }

    @property
    def quality_gates(self) -> tuple[EpistemicQualityGate, ...]:
        """Return the epistemic quality gates attached to the workflow DAG."""
        if self.workflow is None:
            return ()
        return self.workflow.quality_gates

    @property
    def _phase_entries(self) -> list[WorkflowNode]:
        """Return the ordered workflow nodes for this pipeline."""
        if self._custom_phase_entries is not None:
            return self._custom_phase_entries
        if self.workflow is not None:
            return list(self.workflow.nodes)
        return []

    @_phase_entries.setter
    def _phase_entries(self, value: list[WorkflowNode]) -> None:
        self._custom_phase_entries = list(value)
        if self.workflow is not None:
            self.workflow._nodes = tuple(value)

    @property
    def _manifest_store(self) -> JsonRunManifestStore:
        """Return the underlying run manifest store."""
        return self._ensure_engine().manifest_store

    @_manifest_store.setter
    def _manifest_store(self, value: JsonRunManifestStore) -> None:
        self._ensure_engine().manifest_store = value

    @property
    def _artifact_store(self) -> JsonArtifactStore:
        """Return the underlying artifact store."""
        return self._ensure_engine().artifact_store

    @_artifact_store.setter
    def _artifact_store(self, value: JsonArtifactStore) -> None:
        self._ensure_engine().artifact_store = value

    @property
    def _projector(self) -> ArtifactGraphProjector:
        """Return the underlying artifact graph projector."""
        return self._ensure_engine().projector

    @_projector.setter
    def _projector(self, value: ArtifactGraphProjector) -> None:
        self._ensure_engine().projector = value

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
        extra_phases: list[PhaseRunner] | None = None,
        post_processors: list[PhaseRunner] | None = None,
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
        return [(entry.index, entry.runner.name) for entry in self._phase_entries]

    @contextmanager
    def _run_observability_scope(self, run_id: str) -> Iterator[None]:
        """Establish contextual event emission and run-scoped folder logging."""
        with self._ensure_engine().run_observability_scope(run_id):
            yield

    async def _hydrate_previous_collection(
        self,
        phase_number: int = 1,
        source_run_id: str | None = None,
        wanted_phase_names: set[str] | None = None,
    ) -> ArtifactCollection | None:
        """Delegate artifact collection hydration to :class:`ArtifactExecutionEngine`."""
        return await self._ensure_engine().hydrate_previous_collection(
            phase_number=phase_number,
            source_run_id=source_run_id,
            wanted_phase_names=wanted_phase_names,
        )

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
        resolved_run_id = run_id or f"run-{uuid4()}"
        with self._run_observability_scope(resolved_run_id):
            manifest = self._build_manifest(
                run_id=resolved_run_id, pipeline_input=input
            )
            if parent_run_id:
                manifest.parent_run_id = parent_run_id
            decision = await self._choose_reuse_source(manifest)
            effective_start = (
                decision.invalidated_phase_ordinals[0]
                if decision.invalidated_phase_ordinals
                else len(self._phase_entries) + 1
            )
            allow_hydration = self.config.execution.allow_artifact_hydration
            wanted_phases = self._reused_phase_names(decision)
            previous_collection = (
                await self._hydrate_previous_collection(
                    effective_start,
                    source_run_id=decision.resume_point.run_id,
                    wanted_phase_names=wanted_phases,
                )
                if allow_hydration
                and decision.resume_point.run_id
                and wanted_phases
                else None
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = decision.resume_point.run_id
            return await self._execute(
                run_id=resolved_run_id,
                manifest=manifest,
                start_index=effective_start,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
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
        valid_ordinals = {entry.index for entry in self._phase_entries}
        if phase_number not in valid_ordinals:
            raise ValueError(
                f"Invalid phase boundary {phase_number}. Valid boundaries: {self.phase_boundaries()}"
            )
        latest = (
            (
                self._manifest_store.read_manifest(parent_run_id)
                if parent_run_id
                else None
            )
            or self._manifest_store.latest_manifest()
            or self._manifest_store.latest_manifest(only_completed=False)
        )
        if input is None:
            if latest is None:
                raise ValueError(
                    "No previous run manifest found and no PipelineInput provided."
                )
            input = PipelineInput(
                source_paths=list(
                    latest.input_fingerprint_inputs.get("source_paths", [])
                ),
                bib_paths=list(
                    latest.input_fingerprint_inputs.get("bib_paths", [])
                ),
            )
        resolved_run_id = run_id or f"run-{uuid4()}"

        with self._run_observability_scope(resolved_run_id):
            manifest = self._build_manifest(
                run_id=resolved_run_id, pipeline_input=input
            )
            if parent_run_id:
                manifest.parent_run_id = parent_run_id
            decision = await self._choose_reuse_source(manifest)
            effective_start = phase_number
            if (
                phase_number in decision.reused_phase_ordinals
                and decision.invalidated_phase_ordinals
            ):
                effective_start = min(
                    phase_number, decision.invalidated_phase_ordinals[0]
                )

            forced_reused = [
                ord for ord in decision.reused_phase_ordinals if ord < phase_number
            ]
            forced_invalidated = sorted(
                set(decision.invalidated_phase_ordinals)
                | set(range(phase_number, len(self._phase_entries) + 1))
            )
            decision = InvalidationDecision(
                resume_point=decision.resume_point,
                reused_phase_ordinals=forced_reused,
                invalidated_phase_ordinals=forced_invalidated,
                reason=(
                    decision.reason
                    if forced_invalidated == decision.invalidated_phase_ordinals
                    else f"run-from-phase:{phase_number}"
                ),
            )
            allow_hydration = self.config.execution.allow_artifact_hydration
            wanted_phases = self._reused_phase_names(decision)
            previous_collection = (
                await self._hydrate_previous_collection(
                    effective_start,
                    source_run_id=decision.resume_point.run_id,
                    wanted_phase_names=wanted_phases,
                )
                if allow_hydration
                and decision.resume_point.run_id
                and wanted_phases
                else None
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = decision.resume_point.run_id
            return await self._execute(
                run_id=resolved_run_id,
                manifest=manifest,
                start_index=effective_start,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
            )

    def _prompt_fingerprints(self) -> dict[str, dict[str, str]]:
        """Discover and fingerprint prompt bundles across all pipeline phases."""
        return self._ensure_engine().prompt_fingerprints(self._phase_entries)

    def _method_fingerprints(self) -> dict[str, str]:
        """Compute method and component fingerprints across all pipeline phases."""
        return self._ensure_engine().method_fingerprints(
            self._phase_entries, prompt_fps=self._prompt_fingerprints()
        )

    def _phase_config(self, entry: _PhaseEntry) -> BaseModel | None:
        """Resolve the configuration block for ``entry``."""
        return self._ensure_engine().phase_config(entry)

    def _phase_config_fingerprints(self) -> dict[str, str]:
        """Compute configuration fingerprints keyed by semantic ``phase_key``."""
        return self._ensure_engine().phase_config_fingerprints(self._phase_entries)

    def _phase_dependencies(self) -> dict[str, set[str]]:
        """Compute direct upstream phase dependencies from the workflow DAG."""
        return self._ensure_engine().phase_dependencies()

    def _build_manifest(
        self, *, run_id: str, pipeline_input: PipelineInput
    ) -> RunManifest:
        """Assemble a :class:`RunManifest` using the execution engine."""
        return self._ensure_engine().build_manifest(
            run_id=run_id,
            pipeline_input=pipeline_input,
            method_fps=self._method_fingerprints(),
            phase_cfg_fps=self._phase_config_fingerprints(),
        )

    async def _choose_reuse_source(
        self, current: RunManifest
    ) -> InvalidationDecision:
        """Delegate DAG-based cache reuse resolution to :class:`ArtifactExecutionEngine`."""
        return await self._ensure_engine().choose_reuse_source(current)

    async def diff_artifacts(
        self, run_id: str, baseline_run_id: str
    ) -> dict[str, list[str]]:
        """Compare artifacts of ``run_id`` against ``baseline_run_id``."""
        return await self._ensure_engine().diff_artifacts(
            run_id, baseline_run_id
        )

    async def _execute(
        self,
        *,
        run_id: str,
        manifest: RunManifest,
        start_index: int,
        pipeline_input: PipelineInput,
        initial_previous_collection: ArtifactCollection | None,
        invalidation_decision: InvalidationDecision,
    ) -> ExecutionResult:
        """Delegate phase execution and quality gate evaluation to :class:`ArtifactExecutionEngine`."""
        return await self._ensure_engine().execute(
            run_id=run_id,
            manifest=manifest,
            start_index=start_index,
            pipeline_input=pipeline_input,
            initial_previous_collection=initial_previous_collection,
            invalidation_decision=invalidation_decision,
        )

    @staticmethod
    def _fingerprint_collection(collection: ArtifactCollection) -> str:
        """Fingerprint a phase's output collection deterministically."""
        return ArtifactExecutionEngine.fingerprint_collection(collection)

    def _build_phase_input(
        self,
        *,
        entry: _PhaseEntry,
        pipeline_input: PipelineInput,
        previous: ArtifactCollection | None,
    ) -> Any:
        """Return the phase-specific input expected by a runner."""
        return ArtifactExecutionEngine.build_phase_input(
            entry=entry,
            pipeline_input=pipeline_input,
            previous=previous,
        )

    def _reused_phase_names(self, decision: InvalidationDecision) -> set[str]:
        """Names of the phases this run reuses."""
        return self._ensure_engine().reused_phase_names(decision)

    def _reused_phase_records(
        self, decision: InvalidationDecision
    ) -> list[RunPhaseRecord]:
        """Phase records copied from the reuse source manifest."""
        return self._ensure_engine().reused_phase_records(decision)

    @staticmethod
    def _increment_count(
        bucket: dict[str, int], key: str, amount: int = 1
    ) -> None:
        """Increment a count in ``bucket`` by ``amount``."""
        ArtifactExecutionEngine._increment_count(bucket, key, amount)

    async def _reused_artifact_entries(
        self, decision: InvalidationDecision
    ) -> list[ArtifactReportEntry]:
        """Artifact report entries for reused phases."""
        return await self._ensure_engine().reused_artifact_entries(decision)

    async def _get_run_artifacts_raw(self, run_id: str) -> list[Any]:
        """All artifacts visible from ``run_id``, walking the parent-run chain."""
        return await self._ensure_engine().get_run_artifacts_raw(run_id)

    async def get_run_report(self, run_id: str) -> RunReport:
        """Assemble a :class:`RunReport` for ``run_id``."""
        return await self._ensure_engine().get_run_report(run_id)

    def _collect_run_artifact_entries(
        self,
        artifacts: list[Any],
        manifest: RunManifest | None,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Collect and tag :class:`ArtifactReportEntry` items indicating reuse status."""
        return ArtifactExecutionEngine.collect_run_artifact_entries(
            artifacts,
            manifest,
            run_id,
            phase_name=phase_name,
            kind=kind,
        )

    async def get_run_artifacts(
        self,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Retrieve all report-level artifact entries associated with a run."""
        return await self._ensure_engine().get_run_artifacts(
            run_id, phase_name=phase_name, kind=kind
        )

    async def resume_from_run(
        self,
        run_id: str,
        input: PipelineInput,
        from_phase: int | None = None,
    ) -> ExecutionResult:
        """Resume pipeline execution from a prior run within observability context."""
        target_run_id = f"run-resume-{run_id}"
        with self._run_observability_scope(target_run_id):
            manifest = self._build_manifest(
                run_id=target_run_id, pipeline_input=input
            )
            if from_phase is None:
                from_phase = 1
            decision = InvalidationDecision(
                resume_point=ResumePoint(run_id=run_id),
                reused_phase_ordinals=[i for i in range(1, from_phase)],
                invalidated_phase_ordinals=[
                    i for i in range(from_phase, len(self._phase_entries) + 1)
                ],
                reason="explicit-resume-boundary",
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = run_id
            previous_collection = await self._hydrate_previous_collection(
                from_phase, source_run_id=run_id
            )
            return await self._execute(
                run_id=target_run_id,
                manifest=manifest,
                start_index=from_phase,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
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
