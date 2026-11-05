"""Composition root factory for pipeline components and workflows (ISSUE-058).

Defines :class:`PipelineFactory` and :class:`ResolvedPipelineComponents`,
isolating Dependency Injection (DI) normalization of LLMs, embedders,
rerankers, :class:`DecisionEngine`, :class:`ModalStrengthResolver`, and
:class:`EpistemicQualityGate` instances from workflow topology and runtime
execution.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.modal_resolver import HybridModalResolver
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.events import EventEmitter, NoOpEventEmitter
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM, default_cache_dir
from episteme_pipeline.llm.structured import ensure_structured_llm
from episteme_pipeline.protocols.decision import DecisionEngine, ensure_decision_engine
from episteme_pipeline.protocols.extractors import (
    CrossEncoder,
    EmbeddingModel,
    GlobalRelationExtractor,
    RelationReranker,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.graph_store import PhaseCheckpointStore
from episteme_pipeline.protocols.modality import (
    ModalStrengthResolver,
    ensure_modal_strength_resolver,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.quality_gate import (
    EpistemicQualityGate,
    ensure_quality_gates,
)
from episteme_pipeline.runtime.quality_gates import build_default_quality_gates
from episteme_pipeline.runtime.workflow_dag import WorkflowDAG

if TYPE_CHECKING:
    from episteme_pipeline.pipeline import Pipeline

#: Tasks ``PipelineFactory`` knows how to build.
SUPPORTED_TASKS: frozenset[str] = frozenset({"knowledge_graph"})


@dataclass(frozen=True)
class ResolvedPipelineComponents:
    """Normalized collaborators wired at the composition root.

    Parameters
    ----------
    llm : Any
        Disk-cached structured LLM adapter.
    embedding_model : EmbeddingModel
        Normalized async embedding model adapter.
    relation_reranker : RelationReranker
        Candidate relation reranker.
    cross_encoder : CrossEncoder or None
        Raw text-pair cross-encoder, if provided.
    decision_engine : DecisionEngine or None
        Observable System 1 decision engine with conformal calibrator, if enabled.
    modal_resolver : ModalStrengthResolver
        Propositional modal strength resolver.
    checkpoint_store : PhaseCheckpointStore
        Within-phase checkpoint store.
    event_emitter : EventEmitter
        Domain event emitter.
    global_extractor : GlobalRelationExtractor
        Global relation extractor strategy.
    quality_gates : tuple of EpistemicQualityGate
        Inter-phase epistemic quality gates.
    """

    llm: Any
    embedding_model: EmbeddingModel
    relation_reranker: RelationReranker
    cross_encoder: CrossEncoder | None
    decision_engine: DecisionEngine | None
    modal_resolver: ModalStrengthResolver
    checkpoint_store: PhaseCheckpointStore
    event_emitter: EventEmitter
    global_extractor: GlobalRelationExtractor
    quality_gates: tuple[EpistemicQualityGate, ...]


class PipelineFactory(Fingerprintable):
    """Composition root factory wiring domain collaborators and workflow topologies.

    Parameters
    ----------
    config : PipelineConfig
        Top-level pipeline configuration.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic representation of the factory configuration.

        Returns
        -------
        dict of str to Any
            JSON-serializable configuration snapshot.
        """
        return {
            "class": self.__class__.__name__,
            "schema_version": self.config.graph_schema.version,
            "quality_gates": self.config.quality_gates.model_dump(mode="json"),
        }

    @classmethod
    def resolve_components(
        cls,
        *,
        config: PipelineConfig,
        llm: Any,
        relation_reranker: RelationReranker | None = None,
        cross_encoder: CrossEncoder | None = None,
        embedding_model: EmbeddingModel | Any = None,
        projection_graph: Any = None,
        checkpoint_store: Any = None,
        event_emitter: EventEmitter | None = None,
        decision_engine: DecisionEngine | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        quality_gates: Iterable[EpistemicQualityGate] | None = None,
    ) -> ResolvedPipelineComponents:
        """Resolve and normalize all pipeline collaborators from ``config``.

        Parameters
        ----------
        config : PipelineConfig
            Pipeline configuration.
        llm : Any
            Generative LLM instance.
        relation_reranker : RelationReranker or None, optional
            Candidate relation reranker.
        cross_encoder : CrossEncoder or None, optional
            Text-pair cross-encoder.
        embedding_model : EmbeddingModel or Any, optional
            Embedding model to normalize via ``ensure_embedding_model``.
        projection_graph : Any, optional
            Target projection graph store.
        checkpoint_store : Any, optional
            Within-phase checkpoint store.
        event_emitter : EventEmitter or None, optional
            Domain event emitter.
        decision_engine : DecisionEngine or None, optional
            System 1 decision engine.
        modal_resolver : ModalStrengthResolver or None, optional
            Propositional modal strength resolver.
        quality_gates : Iterable of EpistemicQualityGate or None, optional
            Explicit quality gates override. If ``None``, built from
            ``config.quality_gates``.

        Returns
        -------
        ResolvedPipelineComponents
            Normalized collaborators ready for phase injection.
        """
        emitter = event_emitter or NoOpEventEmitter()
        normalized_embedding = ensure_embedding_model(embedding_model)

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
            observable_engine = ObservableDecisionEngine(
                inner=decision_engine,
                stochastic_audit_rate=stochastic_rate,
                seed=seed,
            )
            observable_engine.calibrator = calibrator
            decision_engine = observable_engine

        if config.decision_engine is not None:
            config.sync_allocated_risk_budgets()

        resolved_modal_resolver = ensure_modal_strength_resolver(
            modal_resolver
        ) or HybridModalResolver.create(
            config=config.modal_resolver,
            decision_engine=decision_engine,
        )

        if not isinstance(llm, DiskCachedStructuredLLM):
            llm = DiskCachedStructuredLLM(
                cast(Any, ensure_structured_llm(llm, use_cache=False)),
                cache_dir=default_cache_dir(config.execution.runs_dir),
            )

        from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
            DenseRetrievalGlobalRelationExtractor,
        )
        from episteme_pipeline.phases.phase3_global_relations.rerankers import (
            CrossEncoderRelationReranker,
            JevRelationReranker,
        )

        if config.phase3.use_jev_reranker and decision_engine is not None:
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
            normalized_embedding,
            relation_reranker,
            config.phase3,
            decision_engine=decision_engine,
        )

        resolved_gates = (
            ensure_quality_gates(quality_gates)
            if quality_gates is not None
            else build_default_quality_gates(config, decision_engine=decision_engine)
        )

        return ResolvedPipelineComponents(
            llm=llm,
            embedding_model=normalized_embedding,
            relation_reranker=relation_reranker,
            cross_encoder=cross_encoder,
            decision_engine=decision_engine,
            modal_resolver=resolved_modal_resolver,
            checkpoint_store=resolved_checkpoint_store,
            event_emitter=emitter,
            global_extractor=global_extractor,
            quality_gates=resolved_gates,
        )

    @classmethod
    def build_phases(
        cls,
        *,
        task: str = "knowledge_graph",
        config: PipelineConfig,
        components: ResolvedPipelineComponents,
        entity_linker: Any | None = None,
        working_memory_manager: Any | None = None,
        acc_classifier: Any | None = None,
        arc_classifier: Any | None = None,
        ner_extractor: Any | None = None,
        post_processors: list[PhaseRunner[Any]] | None = None,
        extra_phases: list[PhaseRunner[Any]] | None = None,
    ) -> list[PhaseRunner[Any]]:
        """Assemble the ordered list of phase runners for ``task``.

        Parameters
        ----------
        task : str, default "knowledge_graph"
            Workflow task identifier.
        config : PipelineConfig
            Pipeline configuration.
        components : ResolvedPipelineComponents
            Normalized collaborators from :meth:`resolve_components`.
        entity_linker : Any or None, optional
            Custom Phase 2 entity linker.
        working_memory_manager : Any or None, optional
            Custom Phase 2 working memory manager.
        acc_classifier : Any or None, optional
            Custom Phase 4 ACC classifier.
        arc_classifier : Any or None, optional
            Custom Phase 4 ARC classifier.
        ner_extractor : Any or None, optional
            Custom Phase 2 NER extractor.
        post_processors : list of PhaseRunner or None, optional
            Additional post-processing runners.
        extra_phases : list of PhaseRunner or None, optional
            Extra phase runners appended after post-processors.

        Returns
        -------
        list of PhaseRunner
            Instantiated phase runners.
        """
        if task not in SUPPORTED_TASKS:
            raise ValueError(
                f"Unknown task {task!r}. Supported: {sorted(SUPPORTED_TASKS)}."
            )

        from episteme_pipeline.phases.phase1_foundation import Phase1Runner
        from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
        from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
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

        phases: list[PhaseRunner[Any]] = [
            Phase1Runner(
                config.phase1,
                llm=components.llm,
                embedding_model=components.embedding_model,
                graph_store=None,
            ),
            Phase2Runner(
                config.phase2,
                config.graph_schema,
                llm=components.llm,
                embedding_model=components.embedding_model,
                graph_store=components.checkpoint_store,
                cross_encoder=components.cross_encoder,
                working_memory_manager=working_memory_manager,
                decision_engine=components.decision_engine,
                entity_linker=entity_linker,
                ner_extractor=ner_extractor,
            ),
            Phase3Runner(
                config.phase3,
                config.graph_schema,
                llm=components.llm,
                embedding_model=components.embedding_model,
                graph_store=components.checkpoint_store,
                global_extractor=components.global_extractor,
            ),
            Phase3bLatentConsolidationRunner(
                config.phase3b,
                embedding_model=components.embedding_model,
                graph_store=None,
                decision_engine=components.decision_engine,
            ),
            Phase4EntityMaturationRunner(
                config.phase4_maturation,
                llm=components.llm,
                graph_store=None,
                embedding_model=components.embedding_model,
            ),
            Phase4Runner(
                config.phase4,
                config.graph_schema,
                llm=components.llm,
                embedding_model=components.embedding_model,
                graph_store=components.checkpoint_store,
                global_extractor=components.global_extractor,
                acc_classifier=acc_classifier,
                arc_classifier=arc_classifier,
                decision_engine=components.decision_engine,
                modal_resolver=components.modal_resolver,
            ),
            Phase5ArgumentWebRunner(
                config.phase5,
                embedding_model=components.embedding_model,
                graph_store=None,
                decision_engine=components.decision_engine,
            ),
            Phase6Runner(
                cast(Any, config.phase6),
                config.graph_schema,
                graph_store=None,
                decision_engine=components.decision_engine,
                modal_resolver=components.modal_resolver,
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
                    llm=components.llm,
                )
            )

        if post_processors:
            phases.extend(post_processors)

        if extra_phases:
            phases.extend(extra_phases)

        return phases

    @classmethod
    def build_workflow(
        cls,
        *,
        task: str = "knowledge_graph",
        phases: list[PhaseRunner[Any]],
        quality_gates: Iterable[EpistemicQualityGate] | None = None,
    ) -> WorkflowDAG:
        """Build a validated :class:`WorkflowDAG` from phase runners and quality gates.

        Parameters
        ----------
        task : str, default "knowledge_graph"
            Workflow task identifier.
        phases : list of PhaseRunner
            Phase runners forming the workflow.
        quality_gates : Iterable of EpistemicQualityGate or None, optional
            Quality gates to attach.

        Returns
        -------
        WorkflowDAG
            Validated declarative workflow DAG.
        """
        return WorkflowDAG(
            phases=phases,
            quality_gates=quality_gates,
            task=task,
        )

    @classmethod
    def create_for_task(
        cls,
        *,
        pipeline_cls: type[Pipeline],
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
        quality_gates: Iterable[EpistemicQualityGate] | None = None,
    ) -> Pipeline:
        """Create a fully wired :class:`Pipeline` for ``task``.

        Parameters
        ----------
        pipeline_cls : type of Pipeline
            Target Pipeline class to instantiate.
        task : str, default "knowledge_graph"
            Workflow task name.
        llm : Any
            Generative LLM.
        relation_reranker : RelationReranker or None, optional
            Candidate relation reranker.
        cross_encoder : CrossEncoder or None, optional
            Cross-encoder for entity linking or reranking fallback.
        entity_linker : Any or None, optional
            Custom Phase 2 entity linker.
        embedding_model : EmbeddingModel or Any, optional
            Embedding model.
        config : PipelineConfig
            Pipeline configuration.
        graph_reader : Any, optional
            Graph reader instance.
        projection_graph : Any, optional
            Projection graph store.
        checkpoint_store : Any, optional
            Phase checkpoint store.
        event_emitter : EventEmitter or None, optional
            Domain event emitter.
        extra_phases : list of PhaseRunner or None, optional
            Additional phases appended at the end of the workflow.
        post_processors : list of PhaseRunner or None, optional
            Post-processing runners.
        working_memory_manager : Any or None, optional
            Custom working memory manager for Phase 2.
        decision_engine : DecisionEngine or None, optional
            System 1 decision engine.
        acc_classifier : Any or None, optional
            Custom Phase 4 ACC classifier.
        arc_classifier : Any or None, optional
            Custom Phase 4 ARC classifier.
        ner_extractor : Any or None, optional
            Custom Phase 2 NER extractor.
        modal_resolver : ModalStrengthResolver or None, optional
            Propositional modal strength resolver.
        quality_gates : Iterable of EpistemicQualityGate or None, optional
            Explicit inter-phase quality gates.

        Returns
        -------
        Pipeline
            Constructed pipeline orchestrator.
        """
        if task not in SUPPORTED_TASKS:
            raise ValueError(
                f"Unknown task {task!r}. Supported: {sorted(SUPPORTED_TASKS)}."
            )

        components = cls.resolve_components(
            config=config,
            llm=llm,
            relation_reranker=relation_reranker,
            cross_encoder=cross_encoder,
            embedding_model=embedding_model,
            projection_graph=projection_graph,
            checkpoint_store=checkpoint_store,
            event_emitter=event_emitter,
            decision_engine=decision_engine,
            modal_resolver=modal_resolver,
            quality_gates=quality_gates,
        )
        phases = cls.build_phases(
            task=task,
            config=config,
            components=components,
            entity_linker=entity_linker,
            working_memory_manager=working_memory_manager,
            acc_classifier=acc_classifier,
            arc_classifier=arc_classifier,
            ner_extractor=ner_extractor,
            post_processors=post_processors,
            extra_phases=extra_phases,
        )
        workflow = cls.build_workflow(
            task=task,
            phases=phases,
            quality_gates=components.quality_gates,
        )
        return pipeline_cls(
            phases=phases,
            config=config,
            graph_reader=graph_reader,
            projection_graph=projection_graph,
            checkpoint_store=components.checkpoint_store,
            event_emitter=components.event_emitter,
            decision_engine=components.decision_engine,
            modal_resolver=components.modal_resolver,
            quality_gates=components.quality_gates,
            workflow=workflow,
        )
