"""
Main pipeline orchestration module.

This module defines the core Pipeline class and high-level construction functions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List
from typing import cast, Any

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
    use_event_emitter,
)

from episteme_pipeline.observability.logging import run_folder_logger


from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.protocols.extractors import (
    CrossEncoder,
    EmbeddingModel,
    RelationReranker,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.fingerprints import (
    fingerprint_existing_sources,
    fingerprint_phase_config,
    fingerprint_structural_anchor,
    fingerprint_method,
    stable_fingerprint,
)
from episteme_pipeline.runs.models import (
    ExecutionResult,
    InvalidationDecision,
    ResumePoint,
    RunManifest,
    RunPhaseRecord,
    RunReport,
    RunStatus,
    ArtifactReportEntry,
)
from episteme_pipeline.runs.persistence import JsonRunManifestStore

logger = logging.getLogger(__name__)





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

    def __init__(
        self,
        *,
        phases: List[PhaseRunner],
        config: PipelineConfig,
        graph_reader: Any,
        projection_graph: Any,
        checkpoint_store: Any,
        event_emitter: EventEmitter | None = None,
        decision_engine: Any | None = None,
    ) -> None:
        self.phases = phases
        self.config = config
        self.graph_reader = graph_reader
        self.projection_graph = projection_graph
        self.checkpoint_store = checkpoint_store
        self.event_emitter = event_emitter or NoOpEventEmitter()
        self.decision_engine = decision_engine
        # Stores
        self._manifest_store = JsonRunManifestStore(self.config.execution.runs_dir)
        self._artifact_store = JsonArtifactStore(self.config.execution.artifacts_dir)
        from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
        self._projector = ArtifactGraphProjector(projection_graph)

        # Build internal phase entries (1-based ordinals). Validate the dispatch
        # contract here so a runner with a missing or misspelled `phase_key`
        # fails at composition time instead of quietly falling through to the
        # wrong config block.
        entries: list[_PhaseEntry] = []
        for i, runner in enumerate(self.phases, start=1):
            phase_key = getattr(runner, "phase_key", None)
            if not phase_key:
                name_str = str(getattr(runner, "name", ""))
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
                    phase_key = f"phase{i}" if hasattr(config, f"phase{i}") else "phase1"
            if not hasattr(config, phase_key):
                phase_key = "phase1"
            entries.append(
                _PhaseEntry(
                    index=i,
                    runner=runner,
                    phase_key=phase_key,
                    input_view=getattr(runner, "input_view", getattr(runner, "input_view_type", None)),
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
        embedding_model: EmbeddingModel | Any = None,
        config: PipelineConfig,
        graph_reader: Any,
        projection_graph: Any,
        checkpoint_store: Any,
        event_emitter: EventEmitter | None = None,
        extra_phases: list[PhaseRunner] | None = None,
        post_processors: list[PhaseRunner] | None = None,
        working_memory_manager: Any | None = None,
        decision_engine: Any | None = None,
    ) -> "Pipeline":
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
            or Laya adapter). Normalised once here via ``ensure_decision_engine``.
            When None (the default), pipeline phases execute baseline generative
            LLM or CrossEncoder routines without modification.
        """
        if task not in _SUPPORTED_TASKS:
            raise ValueError(
                f"Unknown task {task!r}. Supported: {sorted(_SUPPORTED_TASKS)}."
            )

        from episteme_pipeline.phases.phase1_foundation import Phase1Runner
        from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
        from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
        from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
        from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
        from episteme_pipeline.phases.phase4_entity_maturation import Phase4EntityMaturationRunner
        from episteme_pipeline.phases.phase5_fusion.argument_web import Phase5ArgumentWebRunner
        from episteme_pipeline.phases.phase6_theorynet import Phase6Runner

        from episteme_pipeline.phases.phase3_global_relations.rerankers import (
            CrossEncoderRelationReranker,
        )

        emitter = event_emitter or NoOpEventEmitter()
        embedding_model = ensure_embedding_model(embedding_model)

        from episteme_pipeline.protocols.decision import ensure_decision_engine

        decision_engine = ensure_decision_engine(decision_engine)

        # Wrap the LLM once, here, so the disk cache lands under the configured
        # runs_dir instead of the hardcoded repo-root default (F-10). Every
        # extractor calls ensure_structured_llm on whatever it is given, and
        # that returns an already-wrapped DiskCachedStructuredLLM unchanged — so
        # this is the single place the cache location is decided.
        from episteme_pipeline.llm.cache import DiskCachedStructuredLLM, default_cache_dir
        from episteme_pipeline.llm.structured import ensure_structured_llm

        if not isinstance(llm, DiskCachedStructuredLLM):
            llm = DiskCachedStructuredLLM(
                cast(Any, ensure_structured_llm(
                    llm, use_cache=False
                )),
                cache_dir=default_cache_dir(config.execution.runs_dir),
            )

        if relation_reranker is None and cross_encoder is not None:
            relation_reranker = CrossEncoderRelationReranker(cross_encoder)
        if relation_reranker is None:
            raise ValueError(
                "A relation_reranker or cross_encoder must be supplied. "
                "The previous DummyReranker fallback has been removed (issue D-05) "
                "because scoring every pair 1.0 leads to catastrophic O(n^2) LLM calls."
            )

        global_extractor = DenseRetrievalGlobalRelationExtractor(
            llm, embedding_model, relation_reranker, config.phase3
        )
        phases: list[Any] = [
            Phase1Runner(
                config.phase1,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=projection_graph,
            ),
            Phase2Runner(
                config.phase2,
                config.graph_schema,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=checkpoint_store,
                cross_encoder=cross_encoder,
                working_memory_manager=working_memory_manager,
            ),

            Phase3Runner(
                config.phase3,
                config.graph_schema,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=checkpoint_store,
                global_extractor=global_extractor,
            ),
            Phase3bLatentConsolidationRunner(
                config.phase3b,
                embedding_model=embedding_model,
                graph_store=graph_reader,
            ),
            Phase4EntityMaturationRunner(
                config.phase4_maturation,
                llm=llm,
                graph_store=checkpoint_store,
                embedding_model=embedding_model,
            ),
            Phase4Runner(
                config.phase4,
                config.graph_schema,
                llm=llm,
                embedding_model=embedding_model,
                graph_store=checkpoint_store,
                # F-02: ARC (cross-chunk SUPPORTS/ATTACKS) is only constructed
                # when the extractor is present. Phase 3 and Phase 4 share the
                # same instance so retrieval caches and the reranker are reused.
                global_extractor=global_extractor,
            ),
            Phase5ArgumentWebRunner(
                config.phase5,
                embedding_model=embedding_model,
                graph_store=graph_reader,
            ),
            Phase6Runner(
                cast(Any, config.phase6),
                config.graph_schema,
                graph_store=projection_graph,
            ),
        ]

        if (
            getattr(config, "theoretical_enrichment", None)
            and config.theoretical_enrichment.enabled
        ):
            from episteme_pipeline.post_processing.theoretical_enrichment import (
                TheoreticalEnrichmentRunner,
            )

            phases.append(
                TheoreticalEnrichmentRunner(
                    config=config.theoretical_enrichment,
                    schema=config.graph_schema,
                    graph_store=projection_graph,
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
            checkpoint_store=checkpoint_store,
            event_emitter=emitter,
            decision_engine=decision_engine,
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
        contextual_emitter = ContextualEventEmitter(self.event_emitter, defaults={"run_id": run_id})
        with use_event_emitter(contextual_emitter):
            with run_folder_logger(self.config.execution.runs_dir, run_id):
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
        contextual_emitter = ContextualEventEmitter(self.event_emitter, defaults={"run_id": run_id})
        with use_event_emitter(contextual_emitter):
            with run_folder_logger(self.config.execution.runs_dir, run_id):
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
        """``{phase_key: {prompt_name: fingerprint}}``.

        Grouped by the phase that actually *uses* the prompt. Attaching
        all prompts to every phase meant that editing, say, the ADU segmentation
        prompt invalidated Phase 1 and forced a full re-ingest — including
        re-embedding every chunk.
        """
        def _fp_item(item: Any) -> str:
            if hasattr(item, "model_dump"):
                return stable_fingerprint(item.model_dump(mode="json"))
            return stable_fingerprint(str(item))

        prompts_by_phase: dict[str, dict[str, Any]] = {
            "phase2": {
                "ner_extraction": self.config.phase2.ner_prompts,
                "entity_linking": getattr(self.config.phase2, "entity_linking_prompts", self.config.phase2.entity_linking_prompt_template),
            },
            "phase3": {
                "global_relation": self.config.phase3.global_relation_prompts,
            },
            "phase4_maturation": {
                "entity_synthesis": self.config.phase4_maturation.entity_synthesis_prompts,
            },
            "phase4": {
                "adu_segmentation": getattr(self.config.phase4, "adu_segmentation_prompts", self.config.phase4.adu_segmentation_prompt_template),
                "acc_classification": self.config.phase4.acc_prompts,
                "arc_classification": self.config.phase4.arc_prompts,
            },
        }
        return {
            phase_key: {name: _fp_item(bundle_or_text) for name, bundle_or_text in prompts.items()}
            for phase_key, prompts in prompts_by_phase.items()
        }

    def _method_fingerprints(self) -> dict[str, str]:
        fps: dict[str, str] = {}
        prompt_fps = self._prompt_fingerprints()
        for entry in self._phase_entries:
            runner = entry.runner
            prefix = getattr(runner, "name", None)
            if prefix is None or not isinstance(prefix, str):
                prefix = getattr(entry, "name", "phase")
            if not isinstance(prefix, str):
                prefix = "phase"
            # Try common attributes on runners
            for attr, suffix in (("llm", "llm"), ("embedding_model", "embedding_model"), ("global_extractor", "global_extractor")):
                obj = getattr(runner, attr, None)
                fp = fingerprint_method(obj)
                if fp:
                    fps[f"{prefix}.{suffix}"] = fp
            phase_key = getattr(entry, "phase_key", getattr(runner, "phase_key", ""))
            for pname, pfp in prompt_fps.get(phase_key, {}).items():
                fps[f"{prefix}.prompt.{pname}"] = pfp
        return fps


    def _phase_config(self, entry: _PhaseEntry):
        """The config block this phase runs on, resolved from ``phase_key``."""
        return getattr(self.config, entry.phase_key)

    def _phase_config_fingerprints(self) -> dict[int, str]:
        return {
            entry.index: fingerprint_phase_config(self._phase_config(entry))
            for entry in self._phase_entries
        }

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

        # Otherwise find the first phase whose config, method or prompt moved.
        if earliest_invalid is None:
            for entry in self._phase_entries:
                key = f"phase_{entry.index}"
                if prior.phase_config_fingerprints.get(key) != current.phase_config_fingerprints.get(key):
                    earliest_invalid = entry.index
                    reason = f"config-changed:{entry.name}"
                    break
                method_keys = [
                    k for k in current.method_fingerprints if k.startswith(f"{entry.name}.")
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
        from datetime import datetime, timezone

        # Persist initial manifest
        if self.config.execution.persist_run_manifests:
            self._manifest_store.write_manifest(manifest)

        report = RunReport(
            manifest=manifest,
            run_id=manifest.run_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            phase_records=manifest.phase_records,
            reused_phase_ordinals=list(invalidation_decision.reused_phase_ordinals),
            invalidated_phase_ordinals=list(invalidation_decision.invalidated_phase_ordinals),
            invalidation_reason=invalidation_decision.reason,
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

        # Populate reused artifacts in report
        reused_entries = await self._reused_artifact_entries(invalidation_decision)
        report.artifact_entries.extend(reused_entries)
        for entry in reused_entries:
            self._increment_count(report.artifact_counts_by_kind, entry.kind)
            self._increment_count(report.artifact_counts_by_phase, entry.phase_name)
            self._increment_count(report.reused_artifact_counts_by_kind, entry.kind)
            self._increment_count(report.reused_artifact_counts_by_phase, entry.phase_name)

        previous = initial_previous_collection
        # Ids produced by the phase that ran immediately before the current one,
        # recorded as the current phase's input.
        upstream_artifact_ids: list[str] = (
            [a.artifact_id for a in initial_previous_collection.artifacts]
            if initial_previous_collection is not None
            else []
        )
        records_by_ordinal = {rec.phase_ordinal: rec for rec in manifest.phase_records}

        # Execute phases starting from start_index (1-based). If start_index > len, nothing to run.
        for ordinal in range(start_index, len(self._phase_entries) + 1):
            entry = self._phase_entries[ordinal - 1]
            phase_name = entry.name
            phase_input = self._build_phase_input(
                entry=entry,
                pipeline_input=pipeline_input,
                previous=previous,
            )

            context = ArtifactExecutionContext(
                run_id=run_id, manifest=manifest, pipeline_input=pipeline_input, previous=previous
            )

            if ordinal in invalidation_decision.invalidated_phase_ordinals:
                if not (invalidation_decision.reason and invalidation_decision.reason.startswith("prior-phase-incomplete")):
                    store = getattr(entry.runner, "graph_store", None)
                    if store is not None and hasattr(store, "clear_phase_checkpoints"):
                        await store.clear_phase_checkpoints(entry.phase_key)

            record = records_by_ordinal.get(ordinal)
            if record is not None:
                record.status = RunStatus.RUNNING
                record.started_at = datetime.now(timezone.utc)
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
                    collection: ArtifactCollection = await entry.runner.run(phase_input, context)
            except Exception as exc:
                logger.exception("Phase %s failed: %s", phase_name, exc)
                if record is not None:
                    record.status = RunStatus.FAILED
                    record.completed_at = datetime.now(timezone.utc)
                    record.notes["error"] = f"{type(exc).__name__}: {exc}"
                manifest.status = RunStatus.FAILED
                manifest.completed_at = datetime.now(timezone.utc)
                report.status = RunStatus.FAILED
                report.completed_at = manifest.completed_at
                if self.config.execution.persist_run_manifests:
                    self._manifest_store.write_manifest(manifest)
                raise

            if getattr(
                self.config.execution, f"persist_{entry.phase_key}_artifacts", True
            ):
                for art in collection.artifacts:
                    await self._artifact_store.write_artifact(art)

            if self.config.execution.project_artifacts_to_graph:
                for art in collection.artifacts:
                    await self._projector.project(art)

            produced_ids = [a.artifact_id for a in collection.artifacts]
            if record is not None:
                record.status = RunStatus.COMPLETED
                record.completed_at = datetime.now(timezone.utc)
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
        manifest.completed_at = datetime.now(timezone.utc)
        report.status = RunStatus.COMPLETED
        report.completed_at = manifest.completed_at

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
                kind=artifact.kind.value if hasattr(artifact.kind, "value") else str(artifact.kind),
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
        entries: list[ArtifactReportEntry] = []

        reused_phase_ordinals = [
            rec.phase_ordinal for rec in manifest.phase_records if rec.reused
        ]
        invalidated_phase_ordinals = [
            rec.phase_ordinal for rec in manifest.phase_records if not rec.reused
        ]

        for a in artifacts:
            is_reused = False
            if a.run_id != run_id:
                is_reused = True
            else:
                for rec in manifest.phase_records:
                    if rec.reused and a.artifact_id in rec.artifact_ids:
                        is_reused = True
                        break
                else:
                    for rec in manifest.phase_records:
                        if rec.phase_name == a.phase_name and rec.reused and not rec.artifact_ids:
                            is_reused = True
                            break

            kind_val = a.kind.value if hasattr(a.kind, "value") else str(a.kind)
            
            self._increment_count(by_kind, kind_val)
            self._increment_count(by_phase, a.phase_name)

            if is_reused:
                self._increment_count(reused_by_kind, kind_val)
                self._increment_count(reused_by_phase, a.phase_name)
            else:
                self._increment_count(new_by_kind, kind_val)
                self._increment_count(new_by_phase, a.phase_name)

            entries.append(
                ArtifactReportEntry(
                    artifact_id=a.artifact_id,
                    identity_key=a.identity_key or a.artifact_id,
                    kind=kind_val,
                    phase_name=a.phase_name,
                    run_id=a.run_id,
                    reused=is_reused,
                )
            )

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
            invalidation_reason=getattr(manifest, "invalidation_reason", None),
            artifact_entries=entries,
        )

    async def get_run_artifacts(self, run_id: str, *, phase_name: str | None = None, kind: str | None = None) -> list[ArtifactReportEntry]:
        manifest = self._manifest_store.read_manifest(run_id)
        artifacts = await self._get_run_artifacts_raw(run_id)
        result: list[ArtifactReportEntry] = []
        for a in artifacts:
            if phase_name and a.phase_name != phase_name:
                continue
            if kind and a.kind.value != kind:
                continue

            # Determine if reused
            is_reused = False
            if a.run_id != run_id:
                is_reused = True
            elif manifest:
                for rec in manifest.phase_records:
                    if rec.reused and a.artifact_id in rec.artifact_ids:
                        is_reused = True
                        break
                else:
                    for rec in manifest.phase_records:
                        if rec.phase_name == a.phase_name and rec.reused and not rec.artifact_ids:
                            is_reused = True
                            break

            result.append(
                ArtifactReportEntry(
                    artifact_id=a.artifact_id,
                    identity_key=a.identity_key or a.artifact_id,
                    kind=a.kind.value if hasattr(a.kind, "value") else str(a.kind),
                    phase_name=a.phase_name,
                    run_id=a.run_id,
                    reused=is_reused,
                )
            )
        return result

    async def resume_from_run(self, run_id: str, input: PipelineInput, from_phase: int | None = None) -> ExecutionResult:
        # Simple resume: reuse phases before from_phase, invalidate from from_phase onward
        manifest = self._build_manifest(run_id=f"run-resume-{run_id}", pipeline_input=input)
        if from_phase is None:
            from_phase = 1
        decision = InvalidationDecision(
            resume_point=ResumePoint(run_id=run_id),
            reused_phase_ordinals=[i for i in range(1, from_phase)],
            invalidated_phase_ordinals=[i for i in range(from_phase, len(self._phase_entries) + 1)],
            reason="explicit-resume-boundary",
        )
        if decision.reused_phase_ordinals:
            manifest.parent_run_id = run_id
        previous_collection = await self._hydrate_previous_collection(from_phase, source_run_id=run_id)
        return await self._execute(
            run_id=manifest.run_id,
            manifest=manifest,
            start_index=from_phase,
            pipeline_input=input,
            initial_previous_collection=previous_collection,
            invalidation_decision=decision,
        )
