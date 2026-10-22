"""
Main pipeline orchestration module.

This module defines the core Pipeline class and high-level construction functions.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import (
    ComponentCompleted,
    ComponentStarted,
    ContextualEventEmitter,
    EventEmitter,
    NoOpEventEmitter,
    PhaseCompleted,
    PhaseFailed,
    PhaseReused,
    RunCompleted,
    RunFailed,
    RunStarted,
    use_event_emitter,
)
from episteme_pipeline.observability.logging import run_folder_logger
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.protocols.decision import DecisionEngine, ensure_decision_engine
from episteme_pipeline.protocols.extractors import (
    CrossEncoder,
    EmbeddingModel,
    RelationReranker,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.graph_store import PhaseCheckpointStore
from episteme_pipeline.protocols.modality import (
    ModalStrengthResolver,
    ensure_modal_strength_resolver,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.fingerprints import (
    fingerprint_existing_sources,
    fingerprint_method,
    fingerprint_phase_config,
    fingerprint_structural_anchor,
    stable_fingerprint,
)
from episteme_pipeline.runs.models import (
    ArtifactReportEntry,
    ExecutionResult,
    InvalidationDecision,
    ResumePoint,
    RunManifest,
    RunPhaseRecord,
    RunReport,
    RunStatus,
)
from episteme_pipeline.runs.persistence import JsonRunManifestStore

logger = logging.getLogger(__name__)


def _artifact_kind_str(kind: Any) -> str:
    """Format an artifact kind value safely without reflection.

    Parameters
    ----------
    kind : Any
        Enum member or string representation of artifact kind.

    Returns
    -------
    str
        Normalized string name of the artifact kind.
    """
    if isinstance(kind, Enum):
        return str(kind.value)
    return str(kind)


#: Tasks ``Pipeline.for_task`` knows how to build. Adding a task-specific phase
#: list means adding an entry here and a branch in ``for_task`` — until
#: then the parameter is validated rather than silently ignored.
_SUPPORTED_TASKS = frozenset({"knowledge_graph"})


@dataclass(frozen=True)
class _PhaseEntry:
    """A phase plus everything the orchestrator needs to dispatch on it.

    ``phase_key`` and ``input_view`` are copied off the runner class at
    construction time so no orchestrator code has to string-match ``name``.
    """

    index: int
    runner: PhaseRunner
    phase_key: str
    input_view: type | None

    @property
    def name(self) -> str:
        return self.runner.name

class Pipeline:
    """Main pipeline orchestrator."""

    decision_engine: DecisionEngine | None = None
    modal_resolver: ModalStrengthResolver | None = None

    def __init__(
        self,
        *,
        phases: list[PhaseRunner],
        config: PipelineConfig,
        graph_reader: Any,
        projection_graph: Any,
        checkpoint_store: Any,
        event_emitter: EventEmitter | None = None,
        decision_engine: DecisionEngine | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
    ) -> None:
        self.phases = phases
        self.config = config
        self.graph_reader = graph_reader
        self.projection_graph = projection_graph
        if checkpoint_store is None:
            from pathlib import Path

            from episteme_pipeline.artifacts.checkpoint_store import (
                FileSystemCheckpointStore,
            )

            checkpoint_store = FileSystemCheckpointStore(
                Path(self.config.execution.artifacts_dir) / "_checkpoints"
            )
        self.checkpoint_store = checkpoint_store
        self.event_emitter = event_emitter or NoOpEventEmitter()
        self.decision_engine = decision_engine
        self.modal_resolver = modal_resolver
        # Stores
        self._manifest_store = JsonRunManifestStore(self.config.execution.runs_dir)
        self._artifact_store = JsonArtifactStore(self.config.execution.artifacts_dir)
        from episteme_pipeline.projection.artifact_projector import (
            ArtifactGraphProjector,
        )

        self._projector = ArtifactGraphProjector(projection_graph)

        # Build internal phase entries (1-based ordinals). Validate the dispatch
        # contract here so a runner with a missing or misspelled `phase_key`
        # fails at composition time instead of quietly falling through to the
        # wrong config block.
        entries: list[_PhaseEntry] = []
        for i, runner in enumerate(self.phases, start=1):
            try:
                phase_key = runner.phase_key
            except AttributeError:
                try:
                    name_str = str(runner.name)
                except AttributeError:
                    name_str = str(runner)

                if "Phase 1" in name_str:
                    phase_key = "phase1"
                elif "Phase 2" in name_str:
                    phase_key = "phase2"
                elif "Phase 3b" in name_str:
                    phase_key = "phase3b"
                elif "Phase 3" in name_str:
                    phase_key = "phase3"
                elif "Entity Maturation" in name_str:
                    phase_key = "phase4_maturation"
                elif "Phase 4" in name_str:
                    phase_key = "phase4"
                elif "Phase 5" in name_str:
                    phase_key = "phase5"
                elif "Phase 6" in name_str:
                    phase_key = "phase6"
                elif "Theoretical Enrichment" in name_str:
                    phase_key = "theoretical_enrichment"
                else:
                    phase_key = f"phase{i}"

            try:
                input_view = runner.input_view
            except AttributeError:
                try:
                    input_view = runner.input_view_type
                except AttributeError:
                    input_view = None

            entries.append(
                _PhaseEntry(
                    index=i,
                    runner=runner,
                    phase_key=phase_key,
                    input_view=input_view,
                )
            )
        self._phase_entries = entries

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
    ) -> Pipeline:
        """Create a pipeline for a specific task.

        Parameters
        ----------
        task
            Which phase list to build. Only ``"knowledge_graph"`` exists today;
            an unknown value raises rather than silently building the default
            pipeline.
        relation_reranker
            Scores candidate relations between two entities and their subgraph
            envelopes (Phase 3, and Phase 4 ARC through it). If omitted but a
            ``cross_encoder`` is supplied, the cross-encoder is lifted into this
            role via ``CrossEncoderRelationReranker``.
        cross_encoder
            Scores raw ``(query, document)`` text pairs (Phase 2 entity
            linking). These are two different contracts; if one object
            implements both, pass it to both parameters explicitly rather than
            relying on the coincidence.
        entity_linker
            Optional pre-constructed EntityLinker instance (e.g. JevEntityLinker,
            DenseEntityLinker, or CascadingEntityLinker) to inject into Phase 2.
            If omitted, defaults to DenseEntityLinker with the supplied cross_encoder
            and embedding_model.
        embedding_model
            Any embedding model — a llama-index ``BaseEmbedding``, a
            sentence-transformers model, or a custom object. It is normalised
            once here via ``ensure_embedding_model`` so that no phase runner
            ever receives a raw third-party object, and an incompatible one
            fails at construction rather than inside a gathered task.
        extra_phases
            Optional additional PhaseRunners to append to the pipeline phases.
        post_processors
            Optional list of post-processing PhaseRunners (such as
            TheoreticalEnrichmentRunner or custom analytical passes) to execute
            following the core pipeline phases.
        working_memory_manager
            Optional custom EpisodicWorkingMemoryManager to inject into Phase 2.
        decision_engine
            Optional System 1 DecisionEngine implementation (e.g. TypeSafe Jev
            or Laya adapter). Normalised once here via ``resolve_decision_engine``.
            When None (the default), pipeline phases execute baseline generative
            LLM or CrossEncoder routines without modification.
        """
        if task not in _SUPPORTED_TASKS:
            raise ValueError(
                f"Unknown task {task!r}. Supported: {sorted(_SUPPORTED_TASKS)}."
            )

        from pathlib import Path

        from episteme_pipeline.artifacts.checkpoint_store import (
            FileSystemCheckpointStore,
        )
        from episteme_pipeline.phases.phase1_foundation import Phase1Runner
        from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
        from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
        from episteme_pipeline.phases.phase3_global_relations.rerankers import (
            CrossEncoderRelationReranker,
        )
        from episteme_pipeline.phases.phase3b_consolidation import (
            Phase3bLatentConsolidationRunner,
        )
        from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
        from episteme_pipeline.phases.phase4_entity_maturation import (
            Phase4EntityMaturationRunner,
        )
        from episteme_pipeline.phases.phase5_fusion.argument_web import (
            Phase5ArgumentWebRunner,
        )
        from episteme_pipeline.phases.phase6_theorynet import Phase6Runner

        emitter = event_emitter or NoOpEventEmitter()
        embedding_model = ensure_embedding_model(embedding_model)

        resolved_checkpoint_store: PhaseCheckpointStore = (
            checkpoint_store
            if (
                isinstance(checkpoint_store, PhaseCheckpointStore)
                and checkpoint_store is not projection_graph
            )
            else FileSystemCheckpointStore(
                Path(config.execution.artifacts_dir) / "_checkpoints"
            )
        )

        from episteme_pipeline.decision.observable import ObservableDecisionEngine

        if decision_engine is None and config.decision_engine is not None:
            from episteme_pipeline.decision.jev_client import resolve_decision_engine

            decision_engine = resolve_decision_engine(config.decision_engine)

        decision_engine = ensure_decision_engine(decision_engine)
        if decision_engine is not None and not isinstance(
            decision_engine, ObservableDecisionEngine
        ):
            stochastic_rate = (
                config.decision_engine.stochastic_audit_rate
                if config.decision_engine
                else 0.0
            )
            from episteme_pipeline.decision.conformal import ConformalCalibrator

            conformal_alpha = (
                config.decision_engine.conformal_alpha
                if config.decision_engine
                else 0.05
            )
            calibrator = ConformalCalibrator(
                alpha=conformal_alpha,
                global_alpha=(
                    config.decision_engine.global_alpha
                    if config.decision_engine
                    else None
                ),
                risk_budget_weights=(
                    config.decision_engine.risk_budget_weights
                    if config.decision_engine
                    else None
                ),
            )
            seed = (
                config.models.seed
                if config.models and config.models.seed is not None
                else 42
            )
            decision_engine = ObservableDecisionEngine(
                inner=decision_engine,
                stochastic_audit_rate=stochastic_rate,
                seed=seed,
            )
            decision_engine.calibrator = calibrator

        if config.decision_engine is not None:
            config.sync_allocated_risk_budgets()

        from episteme_pipeline.decision.modal_resolver import HybridModalResolver

        modal_resolver = ensure_modal_strength_resolver(
            modal_resolver
        ) or HybridModalResolver.create(
            config=config.modal_resolver,
            decision_engine=decision_engine,
        )

        from episteme_pipeline.llm.cache import (
            DiskCachedStructuredLLM,
            default_cache_dir,
        )
        from episteme_pipeline.llm.structured import ensure_structured_llm

        if not isinstance(llm, DiskCachedStructuredLLM):
            llm = DiskCachedStructuredLLM(
                cast(Any, ensure_structured_llm(llm, use_cache=False)),
                cache_dir=default_cache_dir(config.execution.runs_dir),
            )

        if config.phase3.use_jev_reranker and decision_engine is not None:
            from episteme_pipeline.phases.phase3_global_relations.rerankers import (
                JevRelationReranker,
            )

            relation_reranker = JevRelationReranker(
                decision_engine,
                prompts=config.phase3.global_relation_prompts,
            )
        elif relation_reranker is None and cross_encoder is not None:
            relation_reranker = CrossEncoderRelationReranker(cross_encoder)
        if relation_reranker is None:
            raise ValueError(
                "A relation_reranker or cross_encoder must be supplied. "
                "The previous DummyReranker fallback has been removed (issue D-05) "
                "because scoring every pair 1.0 leads to catastrophic O(n^2) LLM calls."
            )

        global_extractor = DenseRetrievalGlobalRelationExtractor(
            llm,
            embedding_model,
            relation_reranker,
            config.phase3,
            decision_engine=decision_engine,
        )

        phases: list[Any] = [
            Phase1Runner(
                config.phase1,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=None,
            ),
            Phase2Runner(
                config.phase2,
                config.graph_schema,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=resolved_checkpoint_store,
                cross_encoder=cross_encoder,
                working_memory_manager=working_memory_manager,
                decision_engine=decision_engine,
                entity_linker=entity_linker,
                ner_extractor=ner_extractor,
            ),
            Phase3Runner(
                config.phase3,
                config.graph_schema,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=resolved_checkpoint_store,
                global_extractor=global_extractor,
            ),
            Phase3bLatentConsolidationRunner(
                config.phase3b,
                embedding_model=embedding_model,
                graph_store=None,
                decision_engine=decision_engine,
            ),
            Phase4EntityMaturationRunner(
                config.phase4_maturation,
                llm=llm,
                graph_store=None,
                embedding_model=embedding_model,
            ),
            Phase4Runner(
                config.phase4,
                config.graph_schema,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=resolved_checkpoint_store,
                global_extractor=global_extractor,
                acc_classifier=acc_classifier,
                arc_classifier=arc_classifier,
                decision_engine=decision_engine,
                modal_resolver=modal_resolver,
            ),
            Phase5ArgumentWebRunner(
                config.phase5,
                embedding_model=embedding_model,
                graph_store=None,
                decision_engine=decision_engine,
            ),
            Phase6Runner(
                cast(Any, config.phase6),
                config.graph_schema,
                graph_store=None,
                decision_engine=decision_engine,
                modal_resolver=modal_resolver,
            ),
        ]

        if (
            config.theoretical_enrichment is not None
            and config.theoretical_enrichment.enabled
        ):
            from episteme_pipeline.post_processing.theoretical_enrichment import (
                TheoreticalEnrichmentRunner,
            )

            phases.append(
                TheoreticalEnrichmentRunner(
                    config=config.theoretical_enrichment,
                    schema=config.graph_schema,
                    graph_store=None,
                    llm=llm,
                )
            )

        if post_processors:
            phases.extend(post_processors)

        if extra_phases:
            phases.extend(extra_phases)

        return cls(
            phases=phases,
            config=config,
            graph_reader=graph_reader,
            projection_graph=projection_graph,
            checkpoint_store=resolved_checkpoint_store,
            event_emitter=emitter,
            decision_engine=decision_engine,
            modal_resolver=modal_resolver,
        )

    async def _hydrate_previous_collection(
        self, phase_number: int, source_run_id: str | None = None
    ) -> ArtifactCollection | None:
        """Rebuild the artifact collection the phase at ``phase_number`` expects.

        Walks the parent-run chain rather than reading a single run directory.
        A reused phase's artifacts are never re-persisted under the new
        run id, so after two resume hops the immediate parent holds nothing for
        the earliest phases — only its own parent does. ``_get_run_artifacts_raw``
        performs the same traversal for reporting; both now prefer the nearest
        run when the same artifact appears more than once in the chain.
        """
        if phase_number <= 1:
            return None
        run_id = source_run_id
        if run_id is None:
            latest = self._manifest_store.latest_manifest()
            if latest is None:
                return None
            run_id = latest.run_id

        wanted_phases = {
            self._phase_entries[idx - 1].name for idx in range(1, phase_number)
        }
        chain_artifacts = await self._get_run_artifacts_raw(run_id)
        all_artifacts = [a for a in chain_artifacts if a.phase_name in wanted_phases]
        if not all_artifacts:
            return None
        return ArtifactCollection(all_artifacts)

    @contextmanager
    def _run_observability_scope(self, run_id: str) -> Iterator[None]:
        """Establish contextual event emission and run-scoped folder logging.

        Parameters
        ----------
        run_id : str
            Unique execution run identifier.

        Yields
        ------
        None
            Yields execution context within active event emitter and logger contexts.
        """
        contextual_emitter = ContextualEventEmitter(
            self.event_emitter, defaults={"run_id": run_id}
        )
        with (
            use_event_emitter(contextual_emitter),
            run_folder_logger(self.config.execution.runs_dir, run_id),
        ):
            yield

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
            The pipeline input holding source documents, bib paths, and execution metadata.
        run_id : str | None, optional
            Explicit identifier for this execution run. If None, a unique run ID
            in the format ``"run-<uuid4>"`` will be generated automatically.
        parent_run_id : str | None, optional
            Optional identifier of parent run to fork or resume from. If provided,
            manifest fingerprints will be evaluated against this run for phase reuse.

        Returns
        -------
        ExecutionResult
            The execution result containing the run manifest and report.
        """
        if run_id is None:
            from uuid import uuid4

            run_id = f"run-{uuid4()}"

        with self._run_observability_scope(run_id):
            manifest = self._build_manifest(run_id=run_id, pipeline_input=input)
            if parent_run_id:
                manifest.parent_run_id = parent_run_id
            decision = await self._choose_reuse_source(manifest)
            effective_start = (
                decision.invalidated_phase_ordinals[0]
                if decision.invalidated_phase_ordinals
                else len(self._phase_entries) + 1
            )
            allow_hydration = self.config.execution.allow_artifact_hydration
            previous_collection = (
                await self._hydrate_previous_collection(
                    effective_start, source_run_id=decision.resume_point.run_id
                )
                if allow_hydration
                and decision.resume_point.run_id
                and effective_start <= len(self._phase_entries)
                else None
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = decision.resume_point.run_id
            return await self._execute(
                run_id=run_id,
                manifest=manifest,
                start_index=effective_start,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
            )

    def phase_boundaries(self) -> list[tuple[int, str]]:
        return [(entry.index, entry.runner.name) for entry in self._phase_entries]

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
        input : PipelineInput | None, optional
            The pipeline input. If None, input paths are recovered from the latest
            manifest.
        run_id : str | None, optional
            Explicit identifier for this execution run. If None, a unique run ID
            in the format ``"run-<uuid4>"`` will be generated automatically.
        parent_run_id : str | None, optional
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
        # Recovering the source paths does not require a *successful* prior run,
        # so fall back to the latest manifest of any status.
        latest = (
            (self._manifest_store.read_manifest(parent_run_id) if parent_run_id else None)
            or self._manifest_store.latest_manifest()
            or self._manifest_store.latest_manifest(only_completed=False)
        )
        if input is None:
            if latest is None:
                raise ValueError(
                    "No previous run manifest found and no PipelineInput provided."
                )
            input = PipelineInput(
                source_paths=cast(list, latest.input_fingerprint_inputs.get("source_paths", [])),
                bib_paths=cast(list, latest.input_fingerprint_inputs.get("bib_paths", [])),
            )
        if run_id is None:
            from uuid import uuid4

            run_id = f"run-{uuid4()}"

        with self._run_observability_scope(run_id):
            manifest = self._build_manifest(run_id=run_id, pipeline_input=input)
            if parent_run_id:
                manifest.parent_run_id = parent_run_id
            decision = await self._choose_reuse_source(manifest)
            effective_start = phase_number
            if (
                phase_number in decision.reused_phase_ordinals
                and decision.invalidated_phase_ordinals
            ):
                effective_start = decision.invalidated_phase_ordinals[0]
            allow_hydration = self.config.execution.allow_artifact_hydration
            previous_collection = (
                await self._hydrate_previous_collection(
                    effective_start, source_run_id=decision.resume_point.run_id
                )
                if allow_hydration and decision.resume_point.run_id
                else None
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = decision.resume_point.run_id
            return await self._execute(
                run_id=run_id,
                manifest=manifest,
                start_index=effective_start,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
            )


    # -------------------- Helper methods --------------------

    def _prompt_fingerprints(self) -> dict[str, dict[str, str]]:
        """Discover and fingerprint prompt bundles across all pipeline phases.

        Inspects phase configs dynamically to discover all StructuredPromptBundle
        instances without hardcoded phase dictionaries.

        Returns
        -------
        dict of str to dict of str to str
            Mapping from phase_key to prompt_name -> stable fingerprint.
        """
        from episteme_pipeline.prompts.models import StructuredPromptBundle
        from episteme_pipeline.protocols.fingerprint import find_components

        fps: dict[str, dict[str, str]] = {}
        for phase_key, cfg in vars(self.config).items():
            if not isinstance(cfg, BaseModel):
                continue
            prompts: dict[str, str] = {}
            for comp_name, comp_obj in find_components(cfg).items():
                if isinstance(comp_obj, StructuredPromptBundle):
                    pname = comp_obj.name or comp_name.split(".")[-1].removesuffix("_prompts")
                    prompts[pname] = stable_fingerprint(comp_obj.fingerprint())
            if prompts:
                fps[phase_key] = prompts

        # Also inspect runner components
        for entry in self._phase_entries:
            runner = entry.runner
            comps = runner.components() if isinstance(runner, PhaseRunner) else find_components(runner)
            runner_prompts: dict[str, str] = {}
            for comp_name, comp_obj in comps.items():
                if isinstance(comp_obj, StructuredPromptBundle):
                    pname = comp_obj.name or comp_name.split(".")[-1].removesuffix("_prompts")
                    runner_prompts[pname] = stable_fingerprint(comp_obj.fingerprint())
            if runner_prompts:
                fps.setdefault(entry.phase_key, {}).update(runner_prompts)

        return fps

    def _method_fingerprints(self) -> dict[str, str]:
        fps: dict[str, str] = {}
        prompt_fps = self._prompt_fingerprints()
        from episteme_pipeline.protocols.fingerprint import find_components

        for entry in self._phase_entries:
            runner = entry.runner
            try:
                prefix = str(runner.name)
            except AttributeError:
                prefix = f"phase{entry.index}"
            if not prefix:
                prefix = f"phase{entry.index}"

            # Recursively discover and fingerprint all attached components
            if isinstance(runner, PhaseRunner):
                comps = runner.components()
            else:
                comps = find_components(runner)

            for comp_name, comp_obj in comps.items():
                fp = fingerprint_method(comp_obj)
                if fp:
                    fps[f"{prefix}.{comp_name}"] = fp
            for pname, pfp in prompt_fps.get(entry.phase_key, {}).items():
                fps[f"{prefix}.prompt.{pname}"] = pfp

        if self.decision_engine is not None:
            engine_comps = find_components(self.decision_engine)
            for comp_name, comp_obj in engine_comps.items():
                fp = fingerprint_method(comp_obj)
                if fp:
                    fps[f"decision_engine.{comp_name}"] = fp
            engine_fp = fingerprint_method(self.decision_engine)
            if engine_fp:
                fps["decision_engine"] = engine_fp

        return fps


    def _phase_config(self, entry: _PhaseEntry) -> BaseModel | None:
        """The config block this phase runs on, resolved from ``phase_key``."""
        return self.config.get_phase_config(entry.phase_key)

    def _phase_config_fingerprints(self) -> dict[int, str]:
        fps: dict[int, str] = {}
        for entry in self._phase_entries:
            cfg = self._phase_config(entry)
            if cfg is not None:
                fps[entry.index] = fingerprint_phase_config(cfg)
        return fps

    def _build_manifest(self, *, run_id: str, pipeline_input: PipelineInput) -> RunManifest:
        # Assemble manifest with fingerprints and config snapshot
        method_fps = self._method_fingerprints()
        phase_cfg_fps = self._phase_config_fingerprints()
        source_fp = fingerprint_existing_sources(
            [str(p) for p in pipeline_input.source_paths],
            [str(p) for p in pipeline_input.bib_paths]
        )
        anchor_fp = fingerprint_structural_anchor(pipeline_input.structural_anchor)
        input_fp = (
            stable_fingerprint({"source": source_fp, "anchor": anchor_fp})
            if anchor_fp is not None
            else source_fp
        )
        cfg_snapshot = self.config.model_dump(mode="json")
        anchor_dump = (
            pipeline_input.structural_anchor.model_dump(mode="json")
            if pipeline_input.structural_anchor
            else None
        )
        return RunManifest(
            run_id=run_id,
            status=RunStatus.RUNNING,
            schema_version=self.config.graph_schema.version,
            source_fingerprint=source_fp,
            input_fingerprint=input_fp,
            input_fingerprint_inputs={
                "source_paths": list(pipeline_input.source_paths),
                "bib_paths": list(pipeline_input.bib_paths),
                "metadata": dict(pipeline_input.metadata),
                "structural_anchor": anchor_dump,
                "source_fingerprint": source_fp,
                "structural_anchor_fingerprint": anchor_fp,
            },
            config_snapshot=cfg_snapshot,
            phase_config_fingerprints={f"phase_{i}": v for i, v in phase_cfg_fps.items()},
            method_fingerprints=method_fps,
            input_sources=list(pipeline_input.source_paths),
            phase_records=[
                RunPhaseRecord(phase_name=entry.runner.name, ordinal=entry.index)
                for entry in self._phase_entries
            ],
        )



    def _phase_lists_match(self, prior: RunManifest) -> bool:
        """True when the prior run ran exactly this phase list, in this order.

        Reuse copies phase records and artifacts across run. Matching
        them by ordinal alone is only safe if both runs had the same phases:
        ``Pipeline.__init__`` accepts an arbitrary ``phases`` list, so dropping
        one phase shifts every later ordinal.
        """
        prior_names = [rec.phase_name for rec in sorted(prior.phase_records, key=lambda r: r.phase_ordinal)]
        current_names = [entry.name for entry in self._phase_entries]
        return prior_names == current_names

    async def _choose_reuse_source(self, current: RunManifest) -> InvalidationDecision:
        """Decide which phases can be reused from the most recent completed run.

        The decision is made purely by comparing *manifest* fingerprints —
        source, per-phase config, and per-phase method/prompt — between the
        prior run and this one.

        It deliberately does **not** consult the artifact dependency graph.
        Staleness means "would re-running produce something different
        from what is stored", and this run's artifacts do not exist yet at
        decision time; The DAG is used for the question it can answer, in
        :meth:`diff_artifacts`.
        """
        # Prior is either the explicit parent_run_id or the latest completed manifest.
        prior: RunManifest | None = None
        if current.parent_run_id:
            prior = self._manifest_store.read_manifest(current.parent_run_id)
        if prior is None:
            prior = self._manifest_store.latest_manifest()
        resume_point = ResumePoint(run_id=prior.run_id if prior else None)

        if not prior or not self.config.execution.allow_phase_reuse:
            return InvalidationDecision(
                resume_point=resume_point,
                reused_phase_ordinals=[],
                invalidated_phase_ordinals=[e.index for e in self._phase_entries],
                reason="no-prior-or-reuse-disabled",
            )

        if not self._phase_lists_match(prior):
            return InvalidationDecision(
                resume_point=ResumePoint(run_id=None),
                reused_phase_ordinals=[],
                invalidated_phase_ordinals=[e.index for e in self._phase_entries],
                reason="phase-list-changed",
            )

        earliest_invalid: int | None = None
        reason = "all-reused"

        # If prior was partially executed, invalidation must start at the first incomplete phase
        prior_completed_ordinals = {
            rec.phase_ordinal for rec in prior.phase_records if rec.status == RunStatus.COMPLETED
        }
        for entry in self._phase_entries:
            if entry.index not in prior_completed_ordinals:
                earliest_invalid = entry.index
                reason = f"prior-phase-incomplete:{entry.name}"
                break

        # A changed input invalidates everything from phase 1 on.
        if prior.input_fingerprint != current.input_fingerprint:
            earliest_invalid = 1
            reason = "source-changed"

        # A changed pipeline-wide decision engine or calibrator invalidates from phase 1 on.
        if earliest_invalid is None:
            de_keys = {
                k
                for k in (set(current.method_fingerprints) | set(prior.method_fingerprints))
                if k == "decision_engine" or k.startswith("decision_engine.")
            }
            if any(
                prior.method_fingerprints.get(k) != current.method_fingerprints.get(k)
                for k in de_keys
            ):
                earliest_invalid = 1
                reason = "method-changed:decision_engine"

        # Otherwise find the first phase whose config, method or prompt moved.
        if earliest_invalid is None:
            all_method_keys = set(current.method_fingerprints) | set(prior.method_fingerprints)
            for entry in self._phase_entries:
                key = f"phase_{entry.index}"
                if prior.phase_config_fingerprints.get(key) != current.phase_config_fingerprints.get(key):
                    earliest_invalid = entry.index
                    reason = f"config-changed:{entry.name}"
                    break
                method_keys = [
                    k for k in all_method_keys if k.startswith(f"{entry.name}.")
                ]
                if any(
                    prior.method_fingerprints.get(k) != current.method_fingerprints.get(k)
                    for k in method_keys
                ):
                    earliest_invalid = entry.index
                    reason = f"method-changed:{entry.name}"
                    break

        if earliest_invalid is None:
            reused = [e.index for e in self._phase_entries]
            invalidated = []
        else:
            reused = [e.index for e in self._phase_entries if e.index < earliest_invalid]
            invalidated = [e.index for e in self._phase_entries if e.index >= earliest_invalid]

        return InvalidationDecision(
            resume_point=resume_point,
            reused_phase_ordinals=reused,
            invalidated_phase_ordinals=invalidated,
            reason=reason,
        )

    async def diff_artifacts(
        self, run_id: str, baseline_run_id: str
    ) -> dict[str, list[str]]:
        """``{phase_name: [identity_key, ...]}`` — artifacts of ``run_id`` that
        differ from ``baseline_run_id``.

        This is the job the artifact dependency graph is actually good at:
        comparing two runs that both already exist. An artifact counts as
        changed when its ``dependency_fingerprint`` moved, when its upstream
        edge set moved, or when it transitively depends on one that did.

        Diagnostic only — it is not consulted by :meth:`_choose_reuse_source`.
        Its intended use is deciding which artifacts *within*
        an already-invalidated phase are worth recomputing, and answering "what
        did this parameter change actually affect?" between two research runs.
        """
        from episteme_pipeline.artifacts.invalidate import (
            ArtifactDependencyGraph,
            build_prior_fingerprints,
        )

        current_artifacts = await self._artifact_store.list_run_artifacts(run_id)
        baseline_artifacts = await self._artifact_store.list_run_artifacts(
            baseline_run_id
        )
        if not current_artifacts:
            return {}
        dag = ArtifactDependencyGraph.from_artifacts(current_artifacts)
        return dag.build_phase_staleness_map(
            build_prior_fingerprints(baseline_artifacts),
            prior_artifacts=baseline_artifacts,
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
        from datetime import datetime

        # Persist initial manifest
        if self.config.execution.persist_run_manifests:
            self._manifest_store.write_manifest(manifest)

        report = RunReport(
            manifest=manifest,
            run_id=manifest.run_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            phase_records=manifest.phase_records,
            reused_phase_ordinals=list(invalidation_decision.reused_phase_ordinals),
            invalidated_phase_ordinals=list(invalidation_decision.invalidated_phase_ordinals),
            invalidation_reason=invalidation_decision.reason,
        )

        self.event_emitter.emit(
            RunStarted(
                run_id=run_id,
                parent_run_id=invalidation_decision.resume_point.run_id,
                reused_phase_ordinals=list(invalidation_decision.reused_phase_ordinals),
                invalidated_phase_ordinals=list(invalidation_decision.invalidated_phase_ordinals),
                invalidation_reason=invalidation_decision.reason,
            )
        )

        # Mark reused phase records in manifest. Keyed by phase name, not by ordinal.
        reused_records = self._reused_phase_records(invalidation_decision)
        reused_by_name = {r.phase_name: r for r in reused_records}
        for rec in manifest.phase_records:
            prior_rec = reused_by_name.get(rec.phase_name)
            if prior_rec is not None:
                rec.reused = True
                rec.status = prior_rec.status
                rec.started_at = prior_rec.started_at
                rec.completed_at = prior_rec.completed_at
                rec.artifact_ids = prior_rec.artifact_ids
                rec.input_artifact_ids = prior_rec.input_artifact_ids
                rec.output_artifact_ids = prior_rec.output_artifact_ids
                rec.output_fingerprint = prior_rec.output_fingerprint
                self.event_emitter.emit(
                    PhaseReused(
                        phase_name=rec.phase_name,
                        source_run_id=invalidation_decision.resume_point.run_id or "",
                        artifact_count=len(prior_rec.artifact_ids or []),
                        run_id=run_id,
                        phase=rec.phase_name,
                    )
                )

        # Populate reused artifacts in report
        reused_entries = await self._reused_artifact_entries(invalidation_decision)
        report.artifact_entries.extend(reused_entries)
        for entry in reused_entries:
            self._increment_count(report.artifact_counts_by_kind, entry.kind)
            self._increment_count(report.artifact_counts_by_phase, entry.phase_name)
            self._increment_count(report.reused_artifact_counts_by_kind, entry.kind)
            self._increment_count(report.reused_artifact_counts_by_phase, entry.phase_name)

        previous = initial_previous_collection
        if (
            self.config.execution.project_artifacts_to_graph
            and initial_previous_collection is not None
            and initial_previous_collection.artifacts
        ):
            await self._projector.project_collection(
                initial_previous_collection, batch_size=500
            )

        # Ids produced by the phase that ran immediately before the current one,
        # used as fallback when a phase view does not track consumed_artifact_ids.
        upstream_artifact_ids: list[str] = (
            [a.artifact_id for a in initial_previous_collection.artifacts]
            if initial_previous_collection is not None
            else []
        )
        records_by_ordinal = {rec.phase_ordinal: rec for rec in manifest.phase_records}
        from episteme_pipeline.artifacts.execution import EpistemicStateView

        # Execute phases starting from start_index (1-based). If start_index > len, nothing to run.
        for ordinal in range(start_index, len(self._phase_entries) + 1):
            entry = self._phase_entries[ordinal - 1]
            phase_name = entry.name
            phase_input = self._build_phase_input(
                entry=entry,
                pipeline_input=pipeline_input,
                previous=previous,
            )

            lineage_fp = stable_fingerprint(
                {
                    "phase_key": entry.phase_key,
                    "input_fingerprint": manifest.input_fingerprint,
                    "config_fingerprint": manifest.phase_config_fingerprints.get(
                        f"phase_{ordinal}"
                    ),
                    "method_fingerprints": {
                        k: v
                        for k, v in sorted(manifest.method_fingerprints.items())
                        if k.startswith(f"{entry.name}.")
                        or k == "decision_engine"
                        or k.startswith("decision_engine.")
                    },
                    "upstream_fingerprint": (
                        self._fingerprint_collection(previous)
                        if previous is not None
                        else ""
                    ),
                }
            )

            context = ArtifactExecutionContext(
                run_id=run_id,
                manifest=manifest,
                pipeline_input=pipeline_input,
                previous=previous,
                lineage_fingerprint=lineage_fp,
            )

            if (
                ordinal in invalidation_decision.invalidated_phase_ordinals
                and not (
                    invalidation_decision.reason
                    and invalidation_decision.reason.startswith(
                        "prior-phase-incomplete"
                    )
                )
            ):
                chk_store = None
                try:
                    chk_store = entry.runner.checkpoint_store
                except AttributeError:
                    pass
                if isinstance(chk_store, PhaseCheckpointStore):
                    await chk_store.clear_phase_checkpoints(entry.phase_key)

            record = records_by_ordinal.get(ordinal)
            if record is not None:
                record.status = RunStatus.RUNNING
                record.started_at = datetime.now(UTC)
                if isinstance(phase_input, EpistemicStateView):
                    record.input_artifact_ids = list(
                        phase_input.consumed_artifact_ids or upstream_artifact_ids
                    )
                elif entry.input_view is None:
                    record.input_artifact_ids = []
                else:
                    record.input_artifact_ids = list(upstream_artifact_ids)

            phase_emitter = ContextualEventEmitter(
                self.event_emitter,
                defaults={"run_id": run_id, "phase": phase_name},
            )
            phase_emitter.emit(
                ComponentStarted(
                    component_name=phase_name,
                    phase=phase_name,
                    run_id=run_id,
                )
            )
            if self.config.execution.persist_run_manifests:
                self._manifest_store.write_manifest(manifest)

            # a raising phase must not leave the manifest at RUNNING —
            # a RUNNING manifest that is newer than the last good one used to be
            # picked as the next run's reuse parent.
            try:
                with use_event_emitter(phase_emitter):
                    collection: ArtifactCollection = await entry.runner.run(
                        phase_input, context
                    )
            except Exception as exc:
                logger.exception("Phase %s failed", phase_name)
                fail_time = datetime.now(UTC)
                duration_sec = (
                    (fail_time - record.started_at).total_seconds()
                    if record and record.started_at
                    else 0.0
                )
                if record is not None:
                    record.status = RunStatus.FAILED
                    record.completed_at = fail_time
                    record.notes["error"] = f"{type(exc).__name__}: {exc}"
                manifest.status = RunStatus.FAILED
                manifest.completed_at = fail_time
                report.status = RunStatus.FAILED
                report.completed_at = manifest.completed_at

                total_run_duration = (
                    (manifest.completed_at - report.started_at).total_seconds()
                    if report.started_at and manifest.completed_at
                    else duration_sec
                )

                phase_emitter.emit(
                    ComponentCompleted(
                        component_name=phase_name,
                        duration_seconds=duration_sec,
                        success=False,
                        error_message=str(exc),
                        phase=phase_name,
                        run_id=run_id,
                    )
                )
                phase_emitter.emit(
                    PhaseCompleted(
                        phase_name=phase_name,
                        duration_seconds=duration_sec,
                        artifact_count=0,
                        success=False,
                        error_message=str(exc),
                        phase=phase_name,
                        run_id=run_id,
                    )
                )
                phase_emitter.emit(
                    PhaseFailed(
                        phase_name=phase_name,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        duration_seconds=duration_sec,
                        phase=phase_name,
                        run_id=run_id,
                    )
                )
                self.event_emitter.emit(
                    RunFailed(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        duration_seconds=total_run_duration,
                        run_id=run_id,
                    )
                )
                self.event_emitter.flush()
                report.observer_telemetry = self.event_emitter.get_observer_telemetry()
                if self.config.execution.persist_run_manifests:
                    self._manifest_store.write_manifest(manifest)
                raise

            if self.config.execution.should_persist_artifacts(entry.phase_key):
                for art in collection.artifacts:
                    await self._artifact_store.write_artifact(art)

            if self.config.execution.project_artifacts_to_graph:
                await self._projector.project_collection(collection, batch_size=500)

            produced_ids = [a.artifact_id for a in collection.artifacts]
            if record is not None:
                record.status = RunStatus.COMPLETED
                record.completed_at = datetime.now(UTC)
                record.artifact_ids = produced_ids
                record.output_artifact_ids = produced_ids
                record.config_fingerprint = cast(str, manifest.phase_config_fingerprints.get(f"phase_{ordinal}"))
                record.output_fingerprint = self._fingerprint_collection(collection)

            duration_sec = (
                (record.completed_at - record.started_at).total_seconds()
                if record and record.started_at and record.completed_at
                else 0.0
            )

            phase_emitter.emit(
                ComponentCompleted(
                    component_name=phase_name,
                    duration_seconds=duration_sec,
                    success=True,
                    phase=phase_name,
                    run_id=run_id,
                )
            )
            phase_emitter.emit(
                PhaseCompleted(
                    phase_name=phase_name,
                    duration_seconds=duration_sec,
                    artifact_count=len(produced_ids),
                    success=True,
                    phase=phase_name,
                    run_id=run_id,
                )
            )

            if self.config.execution.persist_run_manifests:
                self._manifest_store.write_manifest(manifest)

            # Aggregate into report
            for a in collection.artifacts:
                self._increment_count(report.artifact_counts_by_kind, a.kind.value)
                self._increment_count(report.artifact_counts_by_phase, phase_name)
                self._increment_count(report.new_artifact_counts_by_kind, a.kind.value)
                self._increment_count(report.new_artifact_counts_by_phase, phase_name)
                report.artifact_entries.append(
                    ArtifactReportEntry(
                        artifact_id=a.artifact_id,
                        identity_key=a.identity_key or a.artifact_id,
                        kind=a.kind.value,
                        phase_name=a.phase_name,
                        run_id=a.run_id,
                        reused=False,
                    )
                )

            upstream_artifact_ids = produced_ids
            if previous is None:
                previous = collection
            else:
                previous = ArtifactCollection(previous.artifacts + collection.artifacts)

        # Finalize manifest/report
        manifest.status = RunStatus.COMPLETED
        manifest.completed_at = datetime.now(UTC)
        report.status = RunStatus.COMPLETED
        report.completed_at = manifest.completed_at

        total_run_duration = (
            (manifest.completed_at - report.started_at).total_seconds()
            if report.started_at and manifest.completed_at
            else 0.0
        )
        total_artifacts = len(report.artifact_entries)

        self.event_emitter.emit(
            RunCompleted(
                duration_seconds=total_run_duration,
                total_artifacts=total_artifacts,
                run_id=run_id,
            )
        )
        self.event_emitter.flush()
        report.observer_telemetry = self.event_emitter.get_observer_telemetry()

        if self.config.execution.persist_run_manifests:
            self._manifest_store.write_manifest(manifest)

        return ExecutionResult(manifest=manifest, report=report)

    @staticmethod
    def _fingerprint_collection(collection: ArtifactCollection) -> str:
        """Fingerprint a phase's output so the next run has something to diff against.

        Built from each artifact's identity and dependency fingerprint, sorted so
        it does not depend on the order the phase happened to emit them in.
        """
        return stable_fingerprint(
            sorted(
                [
                    a.identity_key or a.artifact_id,
                    a.dependency_fingerprint or "",
                ]
                for a in collection.artifacts
            )
        )

    def _build_phase_input(
        self,
        *,
        entry: _PhaseEntry,
        pipeline_input: PipelineInput,
        previous: ArtifactCollection | None,
    ) -> Any:
        """Return the phase-specific input expected by a runner.

        Parameters
        ----------
        entry
            The phase to build input for. ``entry.input_view`` declares which
            artifact view the runner consumes; ``None`` means it takes the raw
            ``PipelineInput``.
        pipeline_input
            Original pipeline invocation input.
        previous
            Artifact collection accumulated by the preceding phases.

        Returns
        -------
        Any
            Input payload or artifact view appropriate for the phase.
        """
        if entry.input_view is None:
            return pipeline_input
        return entry.input_view.from_collection(previous or ArtifactCollection([]))

    # -------------------- Read APIs --------------------
    def _reused_phase_names(self, decision: InvalidationDecision) -> set[str]:
        """Names of the phases this run reuses, resolved against *this* phase list."""
        reused = set(decision.reused_phase_ordinals)
        return {entry.name for entry in self._phase_entries if entry.index in reused}

    def _reused_phase_records(
        self, decision: InvalidationDecision
    ) -> list[RunPhaseRecord]:
        if not decision.resume_point.run_id or not decision.reused_phase_ordinals:
            return []
        source_manifest = self._manifest_store.read_manifest(
            decision.resume_point.run_id
        )
        if source_manifest is None:
            return []
        # Match on phase name rather than ordinal (O-07).
        wanted = self._reused_phase_names(decision)
        return [
            record.model_copy(update={"reused": True})
            for record in source_manifest.phase_records
            if record.phase_name in wanted
        ]

    @staticmethod
    def _increment_count(bucket: dict[str, int], key: str, amount: int = 1) -> None:
        bucket[key] = bucket.get(key, 0) + amount

    async def _reused_artifact_entries(
        self, decision: InvalidationDecision
    ) -> list[ArtifactReportEntry]:
        if not decision.resume_point.run_id or not decision.reused_phase_ordinals:
            return []

        source_manifest = self._manifest_store.read_manifest(
            decision.resume_point.run_id
        )
        if source_manifest is None:
            return []

        source_phase_names = {record.phase_name for record in source_manifest.phase_records}
        reused_phase_names = self._reused_phase_names(decision) & source_phase_names
        if not reused_phase_names:
            return []

        artifacts = await self._get_run_artifacts_raw(decision.resume_point.run_id)

        return [
            ArtifactReportEntry(
                artifact_id=artifact.artifact_id,
                identity_key=artifact.identity_key or artifact.artifact_id,
                kind=_artifact_kind_str(artifact.kind),
                phase_name=artifact.phase_name,
                run_id=artifact.run_id,
                reused=True,
            )
            for artifact in artifacts
            if artifact.phase_name in reused_phase_names
        ]

    async def _get_run_artifacts_raw(self, run_id: str) -> list[Any]:
        """All artifacts visible from ``run_id``, walking the parent-run chain.

        The chain is walked nearest-first and the **nearest** occurrence of an
        identity wins: a re-run that recomputed an artifact must not have its
        result overwritten by the ancestor version it replaced. Results are
        sorted by identity key so hydration is reproducible — the underlying
        store lists files in filesystem order.
        """
        all_artifacts = list(await self._artifact_store.list_run_artifacts(run_id))
        visited_runs = {run_id}
        manifest = self._manifest_store.read_manifest(run_id)
        if manifest:
            current_parent = manifest.parent_run_id
            while current_parent and current_parent not in visited_runs:
                visited_runs.add(current_parent)
                all_artifacts.extend(
                    await self._artifact_store.list_run_artifacts(current_parent)
                )
                parent_manifest = self._manifest_store.read_manifest(current_parent)
                if parent_manifest is None:
                    break
                current_parent = parent_manifest.parent_run_id

        unique_artifacts: dict[str, Any] = {}
        for a in all_artifacts:
            key = a.identity_key or a.artifact_id
            if key not in unique_artifacts:
                unique_artifacts[key] = a
        return [unique_artifacts[key] for key in sorted(unique_artifacts)]

    async def get_run_report(self, run_id: str) -> RunReport:
        manifest = self._manifest_store.read_manifest(run_id)
        if manifest is None:
            raise ValueError(f"No manifest found for run_id={run_id}")

        artifacts = await self._get_run_artifacts_raw(run_id)

        # Filter artifacts to only those belonging to phases defined in the current manifest
        active_phase_names = {rec.phase_name for rec in manifest.phase_records}
        artifacts = [a for a in artifacts if a.phase_name in active_phase_names]

        by_kind: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        new_by_kind: dict[str, int] = {}
        new_by_phase: dict[str, int] = {}
        reused_by_kind: dict[str, int] = {}
        reused_by_phase: dict[str, int] = {}

        reused_phase_ordinals = [
            rec.phase_ordinal for rec in manifest.phase_records if rec.reused
        ]
        invalidated_phase_ordinals = [
            rec.phase_ordinal for rec in manifest.phase_records if not rec.reused
        ]

        entries = self._collect_run_artifact_entries(artifacts, manifest, run_id)
        for entry in entries:
            kind_val = entry.kind
            self._increment_count(by_kind, kind_val)
            self._increment_count(by_phase, entry.phase_name)

            if entry.reused:
                self._increment_count(reused_by_kind, kind_val)
                self._increment_count(reused_by_phase, entry.phase_name)
            else:
                self._increment_count(new_by_kind, kind_val)
                self._increment_count(new_by_phase, entry.phase_name)

        return RunReport(
            manifest=manifest,
            run_id=manifest.run_id,
            status=manifest.status,
            started_at=manifest.started_at,
            completed_at=manifest.completed_at,
            phase_records=manifest.phase_records,
            artifact_counts_by_kind=by_kind,
            artifact_counts_by_phase=by_phase,
            new_artifact_counts_by_kind=new_by_kind,
            new_artifact_counts_by_phase=new_by_phase,
            reused_artifact_counts_by_kind=reused_by_kind,
            reused_artifact_counts_by_phase=reused_by_phase,
            reused_phase_ordinals=reused_phase_ordinals,
            invalidated_phase_ordinals=invalidated_phase_ordinals,
            invalidation_reason=manifest.invalidation_reason,
            artifact_entries=entries,
        )

    def _collect_run_artifact_entries(
        self,
        artifacts: list[Any],
        manifest: RunManifest | None,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Collect and tag typed ArtifactReportEntry items indicating reuse status.

        Parameters
        ----------
        artifacts : list of Any
            Artifact envelopes to process.
        manifest : RunManifest or None
            Associated run manifest containing phase records.
        run_id : str
            Current run identifier.
        phase_name : str or None, optional
            Filter for specific phase name.
        kind : str or None, optional
            Filter for specific artifact kind.

        Returns
        -------
        list of ArtifactReportEntry
            Processed and tagged artifact report entries.
        """
        entries: list[ArtifactReportEntry] = []
        for a in artifacts:
            if phase_name is not None and a.phase_name != phase_name:
                continue

            kind_str = _artifact_kind_str(a.kind)
            if kind is not None and kind_str != kind:
                continue

            is_reused = False
            if a.run_id != run_id:
                is_reused = True
            elif manifest is not None:
                for rec in manifest.phase_records:
                    if rec.reused and a.artifact_id in rec.artifact_ids:
                        is_reused = True
                        break
                else:
                    for rec in manifest.phase_records:
                        if rec.phase_name == a.phase_name and rec.reused and not rec.artifact_ids:
                            is_reused = True
                            break

            entries.append(
                ArtifactReportEntry(
                    artifact_id=a.artifact_id,
                    identity_key=a.identity_key or a.artifact_id,
                    kind=kind_str,
                    phase_name=a.phase_name,
                    run_id=a.run_id,
                    reused=is_reused,
                )
            )
        return entries

    async def get_run_artifacts(
        self,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Retrieve all report-level artifact entries associated with a run.

        Parameters
        ----------
        run_id : str
            Unique run identifier.
        phase_name : str or None, optional
            Optional phase name filter.
        kind : str or None, optional
            Optional artifact kind filter.

        Returns
        -------
        list of ArtifactReportEntry
            Matching artifact report entries.
        """
        manifest = self._manifest_store.read_manifest(run_id)
        artifacts = await self._get_run_artifacts_raw(run_id)
        return self._collect_run_artifact_entries(
            artifacts, manifest, run_id, phase_name=phase_name, kind=kind
        )

    async def resume_from_run(
        self,
        run_id: str,
        input: PipelineInput,
        from_phase: int | None = None,
    ) -> ExecutionResult:
        """Resume pipeline execution from a prior run within observability context.

        Parameters
        ----------
        run_id : str
            Identifier of the prior run to resume from.
        input : PipelineInput
            Pipeline input holding source documents and metadata.
        from_phase : int or None, optional
            Phase ordinal from which to resume execution, by default 1.

        Returns
        -------
        ExecutionResult
            The execution result containing the run manifest and report.
        """
        target_run_id = f"run-resume-{run_id}"
        with self._run_observability_scope(target_run_id):
            manifest = self._build_manifest(run_id=target_run_id, pipeline_input=input)
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
