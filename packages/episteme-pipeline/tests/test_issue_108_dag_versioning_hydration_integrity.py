"""Comprehensive regression tests for ISSUE-108.

Covers:
1. ``TheoreticalEnrichmentRunner`` DAG wiring to Phase 5 & Phase 6,
   ``Phase4Runner.reads_kinds`` canonicalization dependency, and
   ``TheoreticalEnrichmentArtifactsView.allowed_kinds`` exposure.
2. Forward-pass phase-scoped ``artifact_id`` versioning on disk, acyclic
   provenance without self-references, and lossless partial upstream reuse.
3. Deterministic ``PYTHONHASHSEED``-independent curation ledger fingerprinting,
   ``ArtifactHydrator`` ledger invalidation, strict ``allow_phase_reuse`` /
   ``allow_artifact_hydration`` enforcement, ``RelationOverride.polarity``, and
   ``Phase2Runner._deduplicate_entities`` must-link rewriting.
4. Retired split entity and mention pruning in ``ProjectionGraph``,
   standalone refinement ``premise_recoverer`` wiring (with and without LLM),
   and orchestrated refinement reuse/invalidation.
5. Lossless ``DocumentCodec`` metadata types and ``LocalRelationCodec``
   ``None`` ``source_chunk_id`` preservation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_chunk_artifact,
    build_document_artifact,
    build_entity_mention_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.codecs import (
    DocumentCodec,
    LocalRelationCodec,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicStateView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
    TheoreticalEnrichmentArtifactsView,
)
from episteme_pipeline.artifacts.invalidate import ArtifactDependencyGraph
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    DocumentArtifact,
    EntityMentionArtifact,
    LinkedEntityArtifact,
    TheoryAtomArtifact,
)
from episteme_pipeline.config import (
    ExecutionConfig,
    HermeneuticRefinementConfig,
    Phase1Config,
    Phase2Config,
    Phase3bConfig,
    Phase3Config,
    Phase4Config,
    Phase4EntityMaturationConfig,
    Phase5Config,
    Phase6Config,
    PipelineConfig,
    TheoreticalEnrichmentConfig,
)
from episteme_pipeline.contracts.domain import (
    CandidatePair,
    EntityConception,
    EpistemicDeficitKind,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    Measurement,
    RefinementDelta,
    TenabilityResult,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import (
    EpistemicCurationLedger,
    PipelineInput,
    RelationOverride,
)
from episteme_pipeline.events import MetricsObserver, PhaseReused, SimpleEventEmitter
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase4_entity_maturation import (
    EntitySynthesisOutput,
    Phase4EntityMaturationRunner,
)
from episteme_pipeline.phases.phase5_fusion.argument_web import Phase5ArgumentWebRunner
from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.post_processing.theoretical_enrichment import (
    TheoreticalEnrichmentRunner,
)
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    InducedTheoryElement,
    InducedTheoryLaw,
    TheoryRegistry,
)
from episteme_pipeline.protocols.argument_mining import (
    ACCClassifier,
    ADUSegmenter,
    ARCClassifier,
)
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    EntityLinker,
    GlobalRelationExtractor,
    NERExtractor,
    RelationReranker,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.refinement import (
    ClosedLoopRefinementCoordinator,
    LLMTheoryGuidedPremiseRecoverer,
    TheoryNetDeficitDetector,
)
from episteme_pipeline.refinement.axiom_grounder import (
    AxiomGroundingOutput,
    RecoveredGroundingEntity,
    RecoveredMeasurement,
    RecoveredObservationAtom,
)
from episteme_pipeline.runs.fingerprints import fingerprint_curation_ledger
from episteme_pipeline.runs.models import RunStatus
from episteme_pipeline.runtime.pipeline_factory import PipelineFactory
from episteme_pipeline.runtime.workflow_dag import WorkflowDAG
from episteme_pipeline.schema.default_schema import (
    DEFAULT_SCHEMA,
    STRUCTURAL_EDGE_TYPES,
    SchemaConfig,
    StructuralRelationType,
)


class _OrthogonalEmbeddingModel(EmbeddingModel):
    """Deterministic embedding model aligning duplicate claims cleanly."""

    async def aget_text_embedding(self, text: str) -> list[float]:
        """Return an orthogonal unit vector keyed off semantic markers."""
        low = text.lower()
        if "a priori" in low or "knowledge begins with" in low:
            return [1.0, 0.0, 0.0, 0.0]
        if "spatial geometry" in low:
            return [0.0, 1.0, 0.0, 0.0]
        if "empirical geometry" in low:
            return [0.0, 0.0, 1.0, 0.0]
        if "kant" in low:
            return [0.9, 0.43589, 0.0, 0.0]
        if "space" in low:
            return [0.0, 0.8, 0.6, 0.0]
        return [0.0, 0.0, 0.0, 1.0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        """Return batched deterministic embeddings."""
        return [await self.aget_text_embedding(t) for t in texts]


class _StubReranker(RelationReranker):
    """Deterministic relation reranker returning uniform high scores."""

    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: Any,
        entity_b: L2Entity,
        env_b: Any,
    ) -> float:
        """Return a fixed relation score."""
        return 0.95

    async def score_pairs(
        self, pairs: list[tuple[str, str]], **kwargs: Any
    ) -> list[float]:
        """Return fixed scores for candidate pairs."""
        return [0.95 for _ in pairs]


class _StubStructuredLLM:
    """Offline structured LLM stub supporting maturation and axiom grounding."""

    def __init__(self, tag: str = "v1") -> None:
        self.tag = tag
        self.synthesized_entities: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic stub fingerprint."""
        return {"class": "_StubStructuredLLM", "tag": self.tag}

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        """Return deterministic Pydantic payloads for structured extraction calls."""
        if output_cls is EntitySynthesisOutput:
            entity_name = prompt_args.get("entity_name", "Unknown")
            self.synthesized_entities.append(str(entity_name))
            return EntitySynthesisOutput(
                description=f"[{self.tag}] Synthesized description for {entity_name}"
            )
        if output_cls is AxiomGroundingOutput:
            return AxiomGroundingOutput(
                observations=[
                    RecoveredObservationAtom(
                        local_id="OBS_REC",
                        text="Trial recorded N=42 confirming empirical grounding.",
                        component_type="ObservationUnit",
                        source_chunk_id="chunk_ax_1",
                        target_atom_id="ax_ungrounded",
                        relation_type="SUPPORTS",
                        confidence=0.92,
                        measurements=[
                            RecoveredMeasurement(
                                dimension="sample_size", value="42", unit="trials"
                            )
                        ],
                    )
                ],
                entities=[
                    RecoveredGroundingEntity(
                        name="Empirical Trial",
                        label="Method",
                        description="Controlled empirical trial.",
                        source_chunk_id="chunk_ax_1",
                    )
                ],
            )
        return output_cls.model_construct()

    async def predict_text(
        self,
        prompt: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> str:
        """Return deterministic free-text reasoning."""
        return f"[{self.tag}] reasoning"


class _TwoChunkNERExtractor(NERExtractor):
    """Deterministic NER extractor producing distinct alias entities across two chunks."""

    def __init__(self, tag: str = "v1") -> None:
        self.tag = tag
        self.calls: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic extractor fingerprint."""
        return {"extractor": "_TwoChunkNERExtractor", "tag": self.tag}

    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: dict[str, Any] | None = None,
        anchor: Any = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict[str, Any] | None, bool, str | None]:
        """Extract deterministic entities and local triples keyed by chunk text."""
        self.calls.append(chunk_id)
        if "Immanuel Kant" in chunk_text:
            e_kant = L2Entity(
                id="e_kant_canonical",
                label="Person",
                name="Immanuel Kant",
                description=f"Raw Kant ({self.tag})",
                textual_envelope="Immanuel Kant argued that space is a priori.",
                source_chunk_ids=[chunk_id],
                confidence=0.95,
            )
            e_space = L2Entity(
                id="e_space",
                label="Concept",
                name="Space",
                description=f"Raw Space ({self.tag})",
                textual_envelope="Space is an a priori form of outer sensibility.",
                source_chunk_ids=[chunk_id],
                confidence=0.92,
            )
            triple = L2Triple(
                subject_id="e_kant_canonical",
                predicate="DEFINES",
                object_id="e_space",
                confidence=0.91,
                scope="local",
                source_chunk_id=chunk_id,
            )
            return [e_kant, e_space], [triple], None, False, None

        e_kant_dup = L2Entity(
            id="e_kant_dup",
            label="Person",
            name="I. Kant",
            description=f"Duplicate Kant ({self.tag})",
            textual_envelope="Immanuel Kant argued that space is a priori in geometry.",
            source_chunk_ids=[chunk_id],
            confidence=0.88,
        )
        e_space_2 = L2Entity(
            id="e_space",
            label="Concept",
            name="Space",
            description=f"Raw Space ({self.tag})",
            textual_envelope="Space is an a priori form of sensibility in experience.",
            source_chunk_ids=[chunk_id],
            confidence=0.90,
        )
        triple_dup = L2Triple(
            subject_id="e_kant_dup",
            predicate="DEFINES",
            object_id="e_space",
            confidence=0.89,
            scope="local",
            source_chunk_id=chunk_id,
        )
        return [e_kant_dup, e_space_2], [triple_dup], None, False, None


class _NoOpEntityLinker(EntityLinker):
    """EntityLinker returning None so raw extracted entities pass through."""

    async def link(
        self,
        mention: L2Entity,
        graph_store: Any,
        top_k: int = 10,
        threshold: float = 0.85,
    ) -> L2Entity | None:
        """Keep extracted entities unmerged during Phase 2."""
        return None


class _OfflineGlobalExtractor(GlobalRelationExtractor):
    """Deterministic GlobalRelationExtractor producing schema-valid triples."""

    async def extract_pair(
        self, pair: CandidatePair, graph_store: Any, schema: SchemaConfig
    ) -> L2Triple | None:
        """Return a fixed global IMPLIES triple for any candidate pair."""
        return L2Triple(
            subject_id=pair.entity_a.id,
            predicate="IMPLIES",
            object_id=pair.entity_b.id,
            confidence=0.87,
            scope="global",
            source_chunk_id=pair.entity_a.source_chunk_ids[0]
            if pair.entity_a.source_chunk_ids
            else None,
        )


class _OfflineADUSegmenter(ADUSegmenter):
    """Deterministic ADU segmenter tagging the full chunk text."""

    async def segment(self, chunk_id: str, chunk_text: str) -> tuple[str, list[str]]:
        """Wrap chunk text as a single argumentative discourse unit."""
        return f"<AC1>{chunk_text}</AC1>", ["AC1"]


class _DuplicateClaimACCClassifier(ACCClassifier):
    """Deterministic ACC classifier emitting fusable claims and empirical measurements."""

    def __init__(self) -> None:
        self._counter = 0

    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: SchemaConfig,
        chunk_entities: list[L2Entity] | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        """Emit equivalent claim atoms across two chunks so Phase 5 fuses them."""
        self._counter += 1
        ent_ids = [e.id for e in (chunk_entities or [])]
        if self._counter == 1:
            a1 = TheoryAtom(
                id="atom_claim_1",
                text="All knowledge begins with experience.",
                component_type="TheoreticalHypothesis",
                source_chunk_id=chunk_id,
                entity_ids=ent_ids,
                confidence=0.92,
                modal_prior=0.85,
            )
            a_obs = TheoryAtom(
                id="atom_obs_1",
                text="Spatial geometry observation.",
                component_type="ObservationUnit",
                source_chunk_id=chunk_id,
                entity_ids=ent_ids,
                measurements=[
                    Measurement(dimension="apriori_validity", value=0.95, unit="score")
                ],
                confidence=0.90,
                modal_prior=0.80,
            )
            rel = TheoryRelation(
                source_id="atom_obs_1",
                target_id="atom_claim_1",
                relation_type="SUPPORTS",
                confidence=0.88,
                scope="local",
            )
            return [a1, a_obs], [rel]

        a_dup = TheoryAtom(
            id="atom_claim_dup",
            text="All knowledge begins with empirical experience.",
            component_type="TheoreticalHypothesis",
            source_chunk_id=chunk_id,
            entity_ids=[*ent_ids, "extra_dup_entity"],
            confidence=0.89,
            modal_prior=0.82,
        )
        a_obs_2 = TheoryAtom(
            id="atom_obs_2",
            text="Empirical geometry confirmation.",
            component_type="ObservationUnit",
            source_chunk_id=chunk_id,
            entity_ids=ent_ids,
            measurements=[
                Measurement(dimension="apriori_validity", value=0.90, unit="score")
            ],
            confidence=0.91,
            modal_prior=0.84,
        )
        rel_dup = TheoryRelation(
            source_id="atom_obs_2",
            target_id="atom_claim_dup",
            relation_type="SUPPORTS",
            confidence=0.90,
            scope="local",
        )
        return [a_dup, a_obs_2], [rel_dup]


class _NoOpARCClassifier(ARCClassifier):
    """Deterministic ARC classifier returning no extra cross-chunk relations."""

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: Any,
        global_extractor: Any = None,
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]:
        """Return empty cross-chunk relation list."""
        return []


class _RecordingEnrichmentRunner(TheoreticalEnrichmentRunner):
    """Subclass capturing the exact ``Phase4ArtifactsView`` delivered to enrichment."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recorded_views: list[Phase4ArtifactsView] = []
        self.recorded_contexts: list[ArtifactExecutionContext] = []

    async def run(
        self, input: Phase4ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Record inputs and delegate to ``TheoreticalEnrichmentRunner.run``."""
        self.recorded_views.append(input)
        self.recorded_contexts.append(context)
        return await super().run(input, context)


class _RecordingMaturationRunner(Phase4EntityMaturationRunner):
    """Subclass capturing entities delivered to ``Phase4EntityMaturationRunner``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.seen_entity_ids: list[list[str]] = []

    async def run(
        self, input: Phase3ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Record upstream entity identifiers and run maturation."""
        self.seen_entity_ids.append([e.id for e in input.entities])
        return await super().run(input, context)


class _StaticPhaseRunner(PhaseRunner[Any]):
    """Lightweight deterministic phase runner backed by a builder callable."""

    def __init__(
        self,
        *,
        name: str,
        phase_key: str,
        input_view: type[Any] | None,
        reads_kinds: frozenset[ArtifactKind],
        writes_kinds: frozenset[ArtifactKind],
        dependencies: tuple[str, ...] | None,
        builder: Any,
    ) -> None:
        self.name = name
        self.phase_key = phase_key
        self.input_view = input_view
        self.reads_kinds = reads_kinds
        self.writes_kinds = writes_kinds
        self.dependencies = dependencies
        self._builder = builder
        self.calls: int = 0
        self.seen_contexts: list[ArtifactExecutionContext] = []

    async def run(
        self, input: Any, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Invoke the configured builder and record invocation context."""
        self.calls += 1
        self.seen_contexts.append(context)
        return ArtifactCollection(self._builder(input, context))


def _seed_kant_registry() -> TheoryRegistry:
    """Create a TheoryRegistry matching ``atom_claim_1`` for enrichment updates."""
    registry = TheoryRegistry()
    registry.register(
        InducedTheoryElement(
            theory_id="kantian_space",
            name="Kantian Transcendental Aesthetic",
            claimant_hypothesis_ids=["atom_claim_1"],
            parameter_names=["apriori_validity"],
            laws=[
                InducedTheoryLaw(
                    law_id="law_1",
                    description="Space is a priori",
                    formula_expression="0.0",
                    involved_parameters=["apriori_validity"],
                )
            ],
        ).to_definition()
    )
    return registry


def _build_full_test_pipeline(
    tmp_path: Path,
    *,
    tag: str = "v1",
    projection_graph: Any = None,
    enrichment_runner: TheoreticalEnrichmentRunner | None = None,
    maturation_top_k: int = 3,
    tenability_threshold: float = 0.5,
) -> Pipeline:
    """Assemble an offline full Phases 1..6 + Enrichment pipeline for tests."""
    cfg = PipelineConfig(
        phase1=Phase1Config(chunk_size=64, chunk_overlap=0),
        phase2=Phase2Config(batch_size=5),
        phase3=Phase3Config(batch_size=5),
        phase3b=Phase3bConfig(
            enabled=True,
            dense_similarity_threshold=0.80,
            relation_overlap_threshold=0.50,
        ),
        phase4_maturation=Phase4EntityMaturationConfig(maturation_top_k=maturation_top_k),
        phase4=Phase4Config(batch_size=5),
        phase5=Phase5Config(
            argument_clustering_enabled=True,
            theory_fusion_enabled=False,
            fusion_similarity_threshold=0.85,
            min_internal_similarity=0.80,
        ),
        phase6=Phase6Config(),
        theoretical_enrichment=TheoreticalEnrichmentConfig(
            enabled=True,
            induce_theories=False,
            tenability_threshold=tenability_threshold,
        ),
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
            project_artifacts_to_graph=projection_graph is not None,
        ),
    )
    llm_stub = _StubStructuredLLM(tag=tag)
    embedder = _OrthogonalEmbeddingModel()
    enrichment = enrichment_runner or _RecordingEnrichmentRunner(
        config=cfg.theoretical_enrichment,
        schema=DEFAULT_SCHEMA,
        registry=_seed_kant_registry(),
    )
    pipe = Pipeline.for_task(
        llm=llm_stub,
        relation_reranker=_StubReranker(),
        embedding_model=embedder,
        config=cfg,
        projection_graph=projection_graph,
        ner_extractor=_TwoChunkNERExtractor(tag=tag),
        entity_linker=_NoOpEntityLinker(),
        acc_classifier=_DuplicateClaimACCClassifier(),
        arc_classifier=_NoOpARCClassifier(),
    )
    for idx, phase in enumerate(pipe.phases):
        if isinstance(phase, Phase4Runner):
            phase.adu_segmenter = _OfflineADUSegmenter()
        elif isinstance(phase, Phase3Runner):
            phase.global_extractor = _OfflineGlobalExtractor()
        elif isinstance(phase, Phase4EntityMaturationRunner):
            pipe.phases[idx] = _RecordingMaturationRunner(
                config=phase.config,
                llm=llm_stub,
                embedding_model=phase.embedding_model,
                conception_clusterer=phase.conception_clusterer,
            )
        elif isinstance(phase, TheoreticalEnrichmentRunner):
            pipe.phases[idx] = enrichment
    pipe = Pipeline(
        phases=pipe.phases,
        config=cfg,
        projection_graph=projection_graph,
        checkpoint_store=pipe.checkpoint_store,
        event_emitter=pipe.event_emitter,
    )
    return pipe


# ---------------------------------------------------------------------------
# Area 1: TheoreticalEnrichmentRunner DAG Coupling & View Contracts
# ---------------------------------------------------------------------------


def test_theoretical_enrichment_dag_wiring_and_view_contracts() -> None:
    """Verify DAG inference for Phase 4 canonicalization and Enrichment -> Phase 5/6."""
    assert ArtifactKind.CANONICALIZATION in Phase4Runner.reads_kinds
    assert (
        TheoreticalEnrichmentArtifactsView.allowed_kinds
        == (ArtifactKind.THEORETICAL_ENRICHMENT,)
    )
    assert TheoreticalEnrichmentRunner.dependencies is None
    assert ArtifactKind.FUSION_DECISION in TheoreticalEnrichmentRunner.reads_kinds

    llm_stub = _StubStructuredLLM()
    embedder = _OrthogonalEmbeddingModel()
    cfg = PipelineConfig()
    p1 = Phase1Runner(cfg.phase1, embedding_model=embedder)
    p2 = Phase2Runner(
        cfg.phase2,
        DEFAULT_SCHEMA,
        llm=llm_stub,
        embedding_model=embedder,
        ner_extractor=_TwoChunkNERExtractor(),
        entity_linker=_NoOpEntityLinker(),
    )
    p3 = Phase3Runner(
        cfg.phase3,
        DEFAULT_SCHEMA,
        llm=llm_stub,
        embedding_model=embedder,
        global_extractor=_OfflineGlobalExtractor(),
    )
    p3b = Phase3bLatentConsolidationRunner(cfg.phase3b, embedding_model=embedder)
    p4 = Phase4Runner(
        cfg.phase4,
        DEFAULT_SCHEMA,
        llm=llm_stub,
        embedding_model=embedder,
        adu_segmenter=_OfflineADUSegmenter(),
        acc_classifier=_DuplicateClaimACCClassifier(),
        arc_classifier=_NoOpARCClassifier(),
    )
    p5 = Phase5ArgumentWebRunner(cfg.phase5, embedding_model=embedder)
    p6 = Phase6Runner(cfg.phase6, schema=DEFAULT_SCHEMA)
    te = TheoreticalEnrichmentRunner(cfg.theoretical_enrichment, schema=DEFAULT_SCHEMA)

    dag_no_maturation = WorkflowDAG(phases=[p1, p2, p3, p3b, p4])
    assert "phase3b" in dag_no_maturation.dependencies()["phase4"]

    full_dag = WorkflowDAG(phases=[p1, p2, p3, p3b, p4, p5, p6, te])
    te_deps = full_dag.dependencies()["theoretical_enrichment"]
    te_trans = full_dag.transitive_dependencies()["theoretical_enrichment"]
    assert "phase5" in te_deps
    assert "phase6" in te_deps
    assert {"phase4", "phase5", "phase6"}.issubset(te_trans)


@pytest.mark.asyncio
async def test_orchestrated_pipeline_delivers_phase5_fusions_and_phase6_curated_qbaf_to_enrichment(
    tmp_path: Path,
) -> None:
    """Verify Enrichment receives Phase 5 fusions and Phase 6 curated QBAF state via Pipeline.run()."""
    doc_path = tmp_path / "kant_space.md"
    doc_path.write_text(
        "# Section 1\nImmanuel Kant argued that space is an a priori intuition.\n\n"
        "# Section 2\nI. Kant linked space and experience to synthetic a priori judgments.\n",
        encoding="utf-8",
    )

    mem_graph = InMemoryGraphStore()
    enrichment_spy = _RecordingEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(enabled=True, induce_theories=False),
        schema=DEFAULT_SCHEMA,
        registry=_seed_kant_registry(),
    )
    pipe = _build_full_test_pipeline(
        tmp_path,
        projection_graph=mem_graph,
        enrichment_runner=enrichment_spy,
    )

    ledger = EpistemicCurationLedger(modality_overrides={"atom_claim_1": 0.2})
    res = await pipe.run(
        PipelineInput(source_paths=[str(doc_path)], curation_ledger=ledger),
        run_id="run-area1-coupling",
    )
    assert res.manifest.status == RunStatus.COMPLETED
    assert len(enrichment_spy.recorded_views) == 1

    view = enrichment_spy.recorded_views[0]
    assert len(view.fusion_decisions) >= 1
    canon_ids = {a.id for a in view.canonical_theory_atoms}
    assert "atom_claim_1" in canon_ids
    assert "atom_claim_dup" not in canon_ids

    canon_atom = next(a for a in view.canonical_theory_atoms if a.id == "atom_claim_1")
    assert canon_atom.modal_prior == pytest.approx(0.2)
    assert canon_atom.resolver_type == "curation_ledger_override"
    assert canon_atom.equilibrium_strength is not None

    persisted = await pipe.artifact_store.list_run_artifacts("run-area1-coupling")
    final_col = ArtifactCollection(persisted)
    final_view = Phase4ArtifactsView.from_collection(final_col)
    assert "atom_claim_dup" not in {a.id for a in final_view.canonical_theory_atoms}

    latest_atom_env = final_col.latest_by_identity["argument_component::atom_claim_1"]
    assert isinstance(latest_atom_env.payload, TheoryAtomArtifact)
    assert latest_atom_env.payload.modal_prior == pytest.approx(0.2)
    assert latest_atom_env.payload.resolver_type == "curation_ledger_override"
    assert latest_atom_env.payload.equilibrium_strength is not None
    assert "extra_dup_entity" in latest_atom_env.payload.entity_ids

    projected_atom = mem_graph._theory_atoms["atom_claim_1"]
    assert projected_atom.modal_prior == pytest.approx(0.2)
    assert projected_atom.resolver_type == "curation_ledger_override"
    assert projected_atom.equilibrium_strength is not None
    assert "extra_dup_entity" in projected_atom.entity_ids


# ---------------------------------------------------------------------------
# Area 2: Forward-Pass Disk Versioning & Partial Upstream Reuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forward_pass_disk_versioning_provenance_dag_and_partial_reuse(
    tmp_path: Path,
) -> None:
    """Verify disk history preservation, non-self-referential provenance, and partial reuse."""
    doc_path = tmp_path / "versioned_doc.md"
    doc_path.write_text(
        "# Section 1\nImmanuel Kant argued that space is an a priori intuition.\n\n"
        "# Section 2\nI. Kant linked space and experience to synthetic a priori judgments.\n",
        encoding="utf-8",
    )

    enrichment1 = _RecordingEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(enabled=True, induce_theories=False),
        schema=DEFAULT_SCHEMA,
        registry=_seed_kant_registry(),
    )
    pipe1 = _build_full_test_pipeline(
        tmp_path, tag="run1", enrichment_runner=enrichment1, maturation_top_k=3
    )
    res1 = await pipe1.run(
        PipelineInput(source_paths=[str(doc_path)]),
        run_id="run-version-1",
    )
    assert res1.manifest.status == RunStatus.COMPLETED

    run1_files = {
        p.name for p in (tmp_path / "artifacts" / "run-version-1").glob("*.json")
    }
    assert "artifact::e_kant_canonical.json" in run1_files
    assert "artifact::e_kant_canonical::phase4_maturation.json" in run1_files
    assert "artifact::atom_claim_1.json" in run1_files
    assert "artifact::atom_claim_1::phase6.json" in run1_files
    assert "artifact::atom_claim_1::theoretical_enrichment.json" in run1_files

    raw_p2_env = json.loads(
        (tmp_path / "artifacts" / "run-version-1" / "artifact::e_kant_canonical.json").read_text()
    )
    raw_mat_env = json.loads(
        (
            tmp_path
            / "artifacts"
            / "run-version-1"
            / "artifact::e_kant_canonical::phase4_maturation.json"
        ).read_text()
    )
    assert raw_p2_env["payload"]["is_mature"] is False
    assert raw_mat_env["payload"]["is_mature"] is True

    persisted = await pipe1.artifact_store.list_run_artifacts("run-version-1")
    for env in persisted:
        assert env.artifact_id not in env.provenance.upstream_artifact_ids

    dep_forward = ArtifactDependencyGraph.from_artifacts(persisted)
    dep_reversed = ArtifactDependencyGraph.from_artifacts(list(reversed(persisted)))
    assert len(dep_forward.topsort()) > 0
    assert len(dep_reversed.topsort()) > 0
    assert (
        dep_reversed.nodes["linked_entity::e_kant_canonical"].artifact_id
        == "artifact::e_kant_canonical::phase4_maturation"
    )
    assert (
        dep_reversed.nodes["argument_component::atom_claim_1"].artifact_id
        == "artifact::atom_claim_1::theoretical_enrichment"
    )

    # Partial reuse #1: change phase4_maturation config -> reuse phases 1..3b without losing Phase 2 entities
    pipe2 = _build_full_test_pipeline(
        tmp_path, tag="run1", maturation_top_k=5
    )
    res2 = await pipe2.run(
        PipelineInput(source_paths=[str(doc_path)]),
        run_id="run-version-2",
        parent_run_id="run-version-1",
    )
    assert res2.manifest.status == RunStatus.COMPLETED
    recs2 = {r.phase_key: r for r in res2.manifest.phase_records}
    for key in ("phase1", "phase2", "phase3", "phase3b"):
        assert recs2[key].reused is True
    assert recs2["phase4_maturation"].reused is False

    mat_runner2 = next(
        p for p in pipe2.phases if isinstance(p, _RecordingMaturationRunner)
    )
    assert mat_runner2.seen_entity_ids
    assert {"e_kant_canonical", "e_space"}.issubset(set(mat_runner2.seen_entity_ids[0]))

    # Partial reuse #2: change only theoretical_enrichment config -> reuse phases 1..6 cleanly
    enrichment3 = _RecordingEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(
            enabled=True, induce_theories=False, tenability_threshold=0.65
        ),
        schema=DEFAULT_SCHEMA,
        registry=_seed_kant_registry(),
    )
    pipe3 = _build_full_test_pipeline(
        tmp_path,
        tag="run1",
        maturation_top_k=5,
        enrichment_runner=enrichment3,
        tenability_threshold=0.65,
    )
    res3 = await pipe3.run(
        PipelineInput(source_paths=[str(doc_path)]),
        run_id="run-version-3",
        parent_run_id="run-version-2",
    )
    assert res3.manifest.status == RunStatus.COMPLETED
    recs3 = {r.phase_key: r for r in res3.manifest.phase_records}
    for key in ("phase1", "phase2", "phase3", "phase3b", "phase4_maturation", "phase4", "phase5", "phase6"):
        assert recs3[key].reused is True
    assert recs3["theoretical_enrichment"].reused is False
    assert len(enrichment3.recorded_views) == 1
    assert enrichment3.recorded_views[0].fusion_decisions
    assert any(
        a.equilibrium_strength is not None
        for a in enrichment3.recorded_views[0].canonical_theory_atoms
    )


# ---------------------------------------------------------------------------
# Area 3: Ledger Hashing, Hydration Invalidation, Reuse Flags, Polarity & Must-Link
# ---------------------------------------------------------------------------


def test_fingerprint_curation_ledger_deterministic_across_pythonhashseed() -> None:
    """Verify ``fingerprint_curation_ledger`` ignores ``PYTHONHASHSEED`` and pair order."""
    code = (
        "import sys; "
        "from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger; "
        "from episteme_pipeline.runs.fingerprints import fingerprint_curation_ledger; "
        "flip = sys.argv[1] == 'flip'; "
        "must = {('b', 'a'), ('d', 'c')} if flip else {('a', 'b'), ('c', 'd')}; "
        "cannot = {('y', 'x'), ('z', 'w')} if flip else {('x', 'y'), ('w', 'z')}; "
        "ledger = EpistemicCurationLedger(must_link_entities=must, cannot_link_entities=cannot, modality_overrides={'m1': 0.3}); "
        "print(fingerprint_curation_ledger(ledger))"
    )
    digests: set[str] = set()
    for seed in ("1", "42", "999"):
        for mode in ("norm", "flip"):
            proc = subprocess.run(
                [sys.executable, "-c", code, mode],
                env={**os.environ, "PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
                check=True,
            )
            digests.add(proc.stdout.strip())
    assert len(digests) == 1


class _CountingDocNERExtractor(NERExtractor):
    """NER extractor tracking chunk texts processed to verify incremental hydration."""

    def __init__(self) -> None:
        self.called_chunk_texts: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        """Return stable extractor fingerprint."""
        return {"extractor": "_CountingDocNERExtractor"}

    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: Any = None,
        anchor: Any = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]:
        """Extract deterministic entities and triples keyed off document content."""
        self.called_chunk_texts.append(chunk_text)
        if "Alpha proposition" in chunk_text:
            e1 = L2Entity(
                id="e_alpha_1",
                label="Concept",
                name="Alpha",
                source_chunk_ids=[chunk_id],
            )
            e2 = L2Entity(
                id="e_alpha_2",
                label="Concept",
                name="Beta",
                source_chunk_ids=[chunk_id],
            )
            triple = L2Triple(
                subject_id="e_alpha_1",
                predicate="SUPPORTS",
                object_id="e_alpha_2",
                confidence=0.9,
                scope="local",
                source_chunk_id=chunk_id,
            )
            return [e1, e2], [triple], None, False, None
        e3 = L2Entity(
            id="e_gamma_2",
            label="Concept",
            name="Gamma",
            source_chunk_ids=[chunk_id],
        )
        return [e3], [], None, False, None


@pytest.mark.asyncio
async def test_orchestrated_incremental_corpus_and_curation_ledger_edit_invalidation(
    tmp_path: Path,
) -> None:
    """Verify ΔD hydrates unchanged docs while curation ledger edits invalidate hydration."""
    doc1 = tmp_path / "doc1.md"
    doc2 = tmp_path / "doc2.md"
    doc1.write_text("# Doc 1\nAlpha proposition on foundational axioms.\n", encoding="utf-8")
    doc2.write_text("# Doc 2\nGamma proposition on observational tests.\n", encoding="utf-8")

    cfg = PipelineConfig(
        phase1=Phase1Config(chunk_size=128, chunk_overlap=0),
        phase2=Phase2Config(batch_size=5),
        phase3=Phase3Config(batch_size=5),
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
        ),
    )
    embedder = _OrthogonalEmbeddingModel()
    llm_stub = _StubStructuredLLM()

    class _MergingAlphaLinker(EntityLinker):
        """Entity linker that merges ``e_alpha_2`` into ``e_alpha_1`` unless blocked."""

        async def link(
            self,
            mention: L2Entity,
            graph_store: Any,
            top_k: int = 10,
            threshold: float = 0.85,
        ) -> L2Entity | None:
            """Return ``e_alpha_1`` when linking ``e_alpha_2`` to test ``cannot_link``."""
            if mention.id == "e_alpha_2" and graph_store is not None:
                existing = [e for e in await graph_store.get_entities() if e.id == "e_alpha_1"]
                if existing:
                    return existing[0]
            return None

    class _PairCountingGlobalExtractor(GlobalRelationExtractor):
        """Global extractor recording evaluated unordered entity pairs."""

        def __init__(self) -> None:
            self.extracted_pairs: list[tuple[str, str]] = []

        def fingerprint(self) -> dict[str, Any]:
            """Return deterministic extractor fingerprint."""
            return {"class": "_PairCountingGlobalExtractor"}

        async def extract_pair(
            self, pair: CandidatePair, graph_store: Any, schema: SchemaConfig
        ) -> L2Triple | None:
            """Record candidate pair and emit an IMPLIES global triple."""
            ids = tuple(sorted((pair.entity_a.id, pair.entity_b.id)))
            self.extracted_pairs.append(ids)
            return L2Triple(
                subject_id=pair.entity_a.id,
                predicate="IMPLIES",
                object_id=pair.entity_b.id,
                confidence=0.9,
                scope="global",
                source_chunk_id=pair.entity_a.source_chunk_ids[0]
                if pair.entity_a.source_chunk_ids
                else None,
            )

    def _make_pipe(
        ner: _CountingDocNERExtractor, global_ext: _PairCountingGlobalExtractor
    ) -> Pipeline:
        p1 = Phase1Runner(cfg.phase1, embedding_model=embedder)
        p2 = Phase2Runner(
            cfg.phase2,
            DEFAULT_SCHEMA,
            llm=llm_stub,
            embedding_model=embedder,
            ner_extractor=ner,
            entity_linker=_MergingAlphaLinker(),
        )
        p3 = Phase3Runner(
            cfg.phase3,
            DEFAULT_SCHEMA,
            llm=llm_stub,
            embedding_model=embedder,
            global_extractor=global_ext,
        )
        return Pipeline(phases=[p1, p2, p3], config=cfg)

    ledger1 = EpistemicCurationLedger(
        modality_overrides={"atom_x": 0.7},
        cannot_link_entities={("e_alpha_1", "e_alpha_2")},
    )
    ner1 = _CountingDocNERExtractor()
    gext1 = _PairCountingGlobalExtractor()
    pipe1 = _make_pipe(ner1, gext1)
    res1 = await pipe1.run(
        PipelineInput(source_paths=[str(doc1)], curation_ledger=ledger1),
        run_id="run-inc-1",
    )
    assert res1.manifest.status == RunStatus.COMPLETED
    assert len(ner1.called_chunk_texts) == 1
    assert "Alpha proposition" in ner1.called_chunk_texts[0]
    assert ("e_alpha_1", "e_alpha_2") in gext1.extracted_pairs

    # Run 2: add doc2 with identical curation ledger -> doc1 hydrated in Phase 1/2/3
    ner2 = _CountingDocNERExtractor()
    gext2 = _PairCountingGlobalExtractor()
    pipe2 = _make_pipe(ner2, gext2)
    res2 = await pipe2.run(
        PipelineInput(source_paths=[str(doc1), str(doc2)], curation_ledger=ledger1),
        run_id="run-inc-2",
        parent_run_id="run-inc-1",
    )
    assert res2.manifest.status == RunStatus.COMPLETED
    assert len(ner2.called_chunk_texts) == 1
    assert "Gamma proposition" in ner2.called_chunk_texts[0]
    assert ("e_alpha_1", "e_alpha_2") not in gext2.extracted_pairs
    run2_col = ArtifactCollection(await pipe2.artifact_store.list_run_artifacts("run-inc-2"))
    run2_ent_ids = {
        e.payload.entity_id
        for e in run2_col.of_kind(ArtifactKind.LINKED_ENTITY, latest_only=True)
        if isinstance(e.payload, LinkedEntityArtifact)
    }
    assert {"e_alpha_1", "e_alpha_2", "e_gamma_2"}.issubset(run2_ent_ids)

    # Run 3: edit curation ledger (REJECT relation + extra cannot_link) -> hydration invalidated!
    ledger2 = EpistemicCurationLedger(
        modality_overrides={"atom_x": 0.7},
        cannot_link_entities={("e_alpha_1", "e_alpha_2"), ("e_alpha_1", "e_gamma_2")},
        relation_overrides={
            "e_alpha_1::e_alpha_2": RelationOverride(
                source_id="e_alpha_1",
                target_id="e_alpha_2",
                relation_type="REJECTED",
            )
        },
    )
    ner3 = _CountingDocNERExtractor()
    gext3 = _PairCountingGlobalExtractor()
    pipe3 = _make_pipe(ner3, gext3)
    inp3 = PipelineInput(source_paths=[str(doc1), str(doc2)], curation_ledger=ledger2)
    manifest3 = pipe3.engine.build_manifest(run_id="run-inc-3", pipeline_input=inp3)
    manifest3.parent_run_id = "run-inc-2"
    decision3 = await pipe3.engine.choose_reuse_source(manifest3)
    assert decision3.reason == "curation-ledger-changed"

    hydrator_check_ctx = ArtifactExecutionContext(
        run_id="run-inc-3",
        manifest=manifest3,
        pipeline_input=inp3,
        prior_manifest=res2.manifest,
        prior_artifacts=run2_col,
    )
    assert hydrator_check_ctx.hydrator("phase2", "Phase 2: Entity & Local Relation Discovery").can_hydrate is False
    assert hydrator_check_ctx.hydrator("phase3", "Phase 3: Global Relation Extraction").can_hydrate is False

    res3 = await pipe3.run(
        inp3,
        run_id="run-inc-3",
        parent_run_id="run-inc-2",
    )
    assert res3.manifest.status == RunStatus.COMPLETED
    assert len(ner3.called_chunk_texts) == 2
    assert ("e_alpha_1", "e_alpha_2") in gext3.extracted_pairs
    run3_col = ArtifactCollection(await pipe3.artifact_store.list_run_artifacts("run-inc-3"))
    global_pairs_run3 = {
        tuple(sorted((r.payload.subject_entity_id, r.payload.object_entity_id)))
        for r in run3_col.of_kind(ArtifactKind.GLOBAL_RELATION, latest_only=True)
    }
    assert ("e_alpha_1", "e_alpha_2") not in global_pairs_run3


@pytest.mark.asyncio
async def test_allow_phase_reuse_false_and_allow_artifact_hydration_false_disable_prior_loading(
    tmp_path: Path,
) -> None:
    """Verify reuse/hydration flags strictly block prior manifest/artifact loading."""
    cfg1 = PipelineConfig(
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
        )
    )
    runner1 = _StaticPhaseRunner(
        name="Phase 1: Data Foundation",
        phase_key="phase1",
        input_view=None,
        reads_kinds=frozenset(),
        writes_kinds=frozenset({ArtifactKind.DOCUMENT}),
        dependencies=(),
        builder=lambda _inp, ctx: [
            build_document_artifact(
                L1Document(id="d1", title="D1", source_path="d1.md", chapter_count=1, chunk_count=1),
                run_id=ctx.run_id,
                phase_name="Phase 1: Data Foundation",
                method="stub",
            )
        ],
    )
    pipe1 = Pipeline(phases=[runner1], config=cfg1)
    res1 = await pipe1.run(PipelineInput(source_paths=[]), run_id="run-flag-1")
    assert res1.manifest.status == RunStatus.COMPLETED

    # allow_phase_reuse=False clears resume_point.run_id and skips prior loading
    cfg2 = PipelineConfig(
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
            allow_phase_reuse=False,
            allow_artifact_hydration=True,
        )
    )
    runner2 = _StaticPhaseRunner(
        name="Phase 1: Data Foundation",
        phase_key="phase1",
        input_view=None,
        reads_kinds=frozenset(),
        writes_kinds=frozenset({ArtifactKind.DOCUMENT}),
        dependencies=(),
        builder=runner1._builder,
    )
    pipe2 = Pipeline(phases=[runner2], config=cfg2)
    m2 = pipe2.engine.build_manifest(run_id="run-flag-2", pipeline_input=PipelineInput(source_paths=[]))
    dec2 = await pipe2.engine.choose_reuse_source(m2)
    assert dec2.resume_point.run_id is None
    assert dec2.reused_phase_ordinals == []

    res2 = await pipe2.run(
        PipelineInput(source_paths=[]), run_id="run-flag-2", parent_run_id="run-flag-1"
    )
    assert res2.report.reused_phase_ordinals == []
    assert runner2.seen_contexts[0].prior_manifest is None
    assert runner2.seen_contexts[0].prior_artifacts is None

    # allow_artifact_hydration=False suppresses prior loading even when allow_phase_reuse=True
    cfg3 = PipelineConfig(
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
            allow_phase_reuse=True,
            allow_artifact_hydration=False,
        )
    )
    runner3 = _StaticPhaseRunner(
        name="Phase 1: Data Foundation",
        phase_key="phase1",
        input_view=None,
        reads_kinds=frozenset(),
        writes_kinds=frozenset({ArtifactKind.DOCUMENT}),
        dependencies=(),
        builder=runner1._builder,
    )
    runner3_p2 = _StaticPhaseRunner(
        name="Phase 2: Entities",
        phase_key="phase2",
        input_view=EpistemicStateView,
        reads_kinds=frozenset({ArtifactKind.DOCUMENT}),
        writes_kinds=frozenset(),
        dependencies=("phase1",),
        builder=lambda _inp, _ctx: [],
    )
    pipe3 = Pipeline(phases=[runner3, runner3_p2], config=cfg3)
    res3 = await pipe3.run(
        PipelineInput(source_paths=[]), run_id="run-flag-3", parent_run_id="run-flag-2"
    )
    assert res3.manifest.status == RunStatus.COMPLETED
    assert len(runner3_p2.seen_contexts) == 1
    assert runner3_p2.seen_contexts[0].prior_manifest is None
    assert runner3_p2.seen_contexts[0].prior_artifacts is None

    res4 = await pipe3.run(
        PipelineInput(source_paths=["changed.md"]),
        run_id="run-flag-4",
        parent_run_id="run-flag-3",
    )
    assert res4.manifest.status == RunStatus.COMPLETED
    assert len(runner3.seen_contexts) == 1
    assert runner3.seen_contexts[0].prior_manifest is None
    assert runner3.seen_contexts[0].prior_artifacts is None


def test_relation_override_polarity_honored_in_triples_and_theory_relations() -> None:
    """Verify ``RelationOverride.polarity`` drives triple predicates and TheoryRelation weights."""
    triples = [
        L2Triple(
            subject_id="e1",
            predicate="RELATES_TO",
            object_id="e2",
            confidence=0.6,
            scope="local",
        )
    ]
    ledger_triples = EpistemicCurationLedger(
        relation_overrides={
            "e1::e2": RelationOverride(
                source_id="e1",
                target_id="e2",
                relation_type="RELATES_TO",
                polarity="-",
                confidence=0.9,
            ),
            "e3::e4": RelationOverride(
                source_id="e3",
                target_id="e4",
                relation_type="LINKS_TO",
                polarity="+",
                confidence=0.85,
            ),
        }
    )
    out_triples = ledger_triples.apply_to_triples(triples, {"e1", "e2", "e3", "e4"})
    by_pair = {(t.subject_id, t.object_id): t for t in out_triples}
    assert by_pair[("e1", "e2")].predicate == "REFUTES"
    assert by_pair[("e3", "e4")].predicate == "SUPPORTS"

    rels = [
        TheoryRelation(
            source_id="a1",
            target_id="a2",
            relation_type="SUPPORTS",
            confidence=0.7,
            scope="local",
        ),
        TheoryRelation(
            source_id="a3",
            target_id="a4",
            relation_type="SUPPORTS",
            confidence=0.75,
            scope="global",
        ),
    ]
    ledger_rels = EpistemicCurationLedger(
        relation_overrides={
            "a1::a2": RelationOverride(
                source_id="a1",
                target_id="a2",
                relation_type="SUPPORTS",
                polarity="-",
                confidence=0.88,
            ),
            "a3::a4": RelationOverride(
                source_id="a3",
                target_id="a4",
                relation_type="ATTACKS",
                polarity=None,
                confidence=0.80,
            ),
            "a5::a6": RelationOverride(
                source_id="a5",
                target_id="a6",
                relation_type="RELATES",
                polarity="NEUTRAL",
                confidence=0.5,
            ),
            "a7::a8": RelationOverride(
                source_id="a7",
                target_id="a8",
                relation_type="ATTACKS",
                polarity="SUPPORTS",
                confidence=0.92,
            ),
            "a9::a10": RelationOverride(
                source_id="a9",
                target_id="a10",
                relation_type="CONSTRAINS",
                polarity="+",
                confidence=0.86,
            ),
        }
    )
    out_rels = ledger_rels.apply_to_theory_relations(
        rels, {"a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10"}
    )
    rel_map = {(r.source_id, r.target_id): r for r in out_rels}

    assert rel_map[("a1", "a2")].relation_type == "ATTACKS"
    assert rel_map[("a1", "a2")].weight_support == 0.0
    assert rel_map[("a1", "a2")].weight_attack == pytest.approx(0.88)

    assert rel_map[("a3", "a4")].relation_type == "ATTACKS"
    assert rel_map[("a3", "a4")].weight_support is None
    assert rel_map[("a3", "a4")].weight_attack is None

    assert rel_map[("a5", "a6")].relation_type == "RELATES"
    assert rel_map[("a5", "a6")].weight_support == 0.0
    assert rel_map[("a5", "a6")].weight_attack == 0.0

    assert rel_map[("a7", "a8")].relation_type == "SUPPORTS"
    assert rel_map[("a7", "a8")].weight_support == pytest.approx(0.92)
    assert rel_map[("a7", "a8")].weight_attack == 0.0

    assert rel_map[("a9", "a10")].relation_type == "SUPPORTS_ARG"
    assert rel_map[("a9", "a10")].weight_support == pytest.approx(0.86)
    assert rel_map[("a9", "a10")].weight_attack == 0.0

    # Custom SchemaConfig resolves L2 and L3 overrides strictly from injected schema
    custom_schema = SchemaConfig(
        relation_types=["BOLSTERS", "DISPROVES"],
        argument_relation_types=["BACKS_CLAIM", "REBUTS_CLAIM"],
        relation_polarities={
            "BOLSTERS": 1,
            "DISPROVES": -1,
            "BACKS_CLAIM": 1,
            "REBUTS_CLAIM": -1,
        },
    )
    custom_triples = ledger_triples.apply_to_triples(
        triples, {"e1", "e2", "e3", "e4"}, schema=custom_schema
    )
    custom_by_pair = {(t.subject_id, t.object_id): t for t in custom_triples}
    assert custom_by_pair[("e1", "e2")].predicate == "DISPROVES"
    assert custom_by_pair[("e3", "e4")].predicate == "BOLSTERS"

    custom_rels_ledger = EpistemicCurationLedger(
        relation_overrides={
            "a1::a2": RelationOverride(
                source_id="a1",
                target_id="a2",
                relation_type="UNKNOWN_REL",
                polarity="-",
                confidence=0.91,
            ),
            "a3::a4": RelationOverride(
                source_id="a3",
                target_id="a4",
                relation_type="UNKNOWN_REL",
                polarity="+",
                confidence=0.84,
            ),
        }
    )
    custom_out_rels = custom_rels_ledger.apply_to_theory_relations(
        rels[:1], {"a1", "a2", "a3", "a4"}, schema=custom_schema
    )
    custom_rel_map = {(r.source_id, r.target_id): r for r in custom_out_rels}
    assert custom_rel_map[("a1", "a2")].relation_type == "REBUTS_CLAIM"
    assert custom_rel_map[("a1", "a2")].weight_attack == pytest.approx(0.91)
    assert custom_rel_map[("a3", "a4")].relation_type == "BACKS_CLAIM"
    assert custom_rel_map[("a3", "a4")].weight_support == pytest.approx(0.84)

    assert StructuralRelationType.EXTRACTED_FROM == "EXTRACTED_FROM"
    assert StructuralRelationType.EXTRACTED_FROM in STRUCTURAL_EDGE_TYPES


@pytest.mark.asyncio
async def test_phase2_must_link_rewrites_triples_and_mention_envelopes_without_dangling_ids() -> None:
    """Verify ``Phase2Runner._deduplicate_entities`` and ``run()`` leave zero dangling IDs."""
    e1 = L2Entity(
        id="e1",
        label="Concept",
        name="Freedom",
        source_chunk_ids=["c1"],
        confidence=0.9,
    )
    e2 = L2Entity(
        id="e2",
        label="Concept",
        name="Autonomy",
        source_chunk_ids=["c1"],
        confidence=0.85,
    )
    e3 = L2Entity(
        id="e3",
        label="Concept",
        name="Will",
        source_chunk_ids=["c2"],
        confidence=0.8,
    )
    triples = [
        L2Triple(
            subject_id="e2",
            predicate="SUPPORTS",
            object_id="e3",
            source_chunk_id="c1",
            confidence=0.88,
            scope="local",
        ),
        L2Triple(
            subject_id="e1",
            predicate="LINKS",
            object_id="e2",
            source_chunk_id="c1",
            confidence=0.7,
            scope="local",
        ),
    ]
    envelopes = {("e1", "c1"): "env1", ("e2", "c1"): "env2"}
    ledger = EpistemicCurationLedger(must_link_entities={("e1", "e2")})

    dedup_ents, dedup_triples, dedup_envs = Phase2Runner._deduplicate_entities(
        [e1, e2, e3],
        curation_ledger=ledger,
        triples=triples,
        mention_envelopes=envelopes,
    )
    assert [e.id for e in dedup_ents] == ["e1", "e3"]
    assert len(dedup_triples) == 1
    assert dedup_triples[0].subject_id == "e1"
    assert dedup_triples[0].object_id == "e3"
    assert ("e2", "c1") not in dedup_envs
    assert ("e1", "c1") in dedup_envs

    class _MustLinkNER(NERExtractor):
        async def extract(
            self,
            chunk_id: str,
            chunk_text: str,
            schema: SchemaConfig,
            memory: Any = None,
            anchor: Any = None,
        ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]:
            return (
                [e1.model_copy(), e2.model_copy(), e3.model_copy(update={"source_chunk_ids": [chunk_id]})],
                [
                    L2Triple(
                        subject_id="e2",
                        predicate="SUPPORTS",
                        object_id="e3",
                        source_chunk_id=chunk_id,
                        confidence=0.9,
                        scope="local",
                    )
                ],
                None,
                False,
                None,
            )

    p2 = Phase2Runner(
        Phase2Config(batch_size=5),
        DEFAULT_SCHEMA,
        llm=_StubStructuredLLM(),
        embedding_model=_OrthogonalEmbeddingModel(),
        ner_extractor=_MustLinkNER(),
        entity_linker=_NoOpEntityLinker(),
    )
    chunk = L1Chunk(
        id="c1",
        source_doc_id="d1",
        sequence_index=0,
        token_count=4,
        text="Freedom and Autonomy.",
    )
    col_in = ArtifactCollection(
        [
            build_chunk_artifact(
                chunk, run_id="r-ml", phase_name="Phase 1", method="stub"
            )
        ]
    )
    ctx = ArtifactExecutionContext(
        run_id="r-ml",
        manifest=__import__("episteme_pipeline.runs.models", fromlist=["RunManifest"]).RunManifest(run_id="r-ml"),
        pipeline_input=PipelineInput(source_paths=[], curation_ledger=ledger),
        previous=col_in,
    )
    out = await p2.run(
        __import__("episteme_pipeline.artifacts.execution", fromlist=["Phase1ArtifactsView"]).Phase1ArtifactsView.from_collection(col_in),
        ctx,
    )
    for rel_env in out.of_kind(ArtifactKind.LOCAL_RELATION):
        assert rel_env.payload.subject_entity_id != "e2"
        assert rel_env.payload.object_entity_id != "e2"
        assert rel_env.payload.subject_entity_id == "e1"
    for mention_env in out.of_kind(ArtifactKind.ENTITY_MENTION):
        assert mention_env.payload.entity_id != "e2"


# ---------------------------------------------------------------------------
# Area 4: Retirement Pruning, Standalone Refinement Wiring & Refinement Reuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retired_split_entities_and_mentions_pruned_from_projection_graph(
    tmp_path: Path,
) -> None:
    """Verify retired split entities and mentions are pruned and never re-upserted."""
    mem_direct = InMemoryGraphStore()
    ent_parent = L2Entity(
        id="ent_direct",
        label="Concept",
        name="DirectHub",
        source_chunk_ids=["c_d1"],
    )
    await mem_direct.upsert_entity(ent_parent)
    await mem_direct.upsert_relation("ent_direct", "EXTRACTED_FROM", "c_d1", {})

    retired_ent_payload = LinkedEntityArtifact(
        entity_id="ent_direct",
        canonical_name="DirectHub",
        entity_type="Concept",
        source_chunk_ids=[],
        is_retired=True,
    )
    retired_mention_payload = EntityMentionArtifact(
        mention_id="mention::ent_direct::c_d1",
        entity_id="ent_direct",
        chunk_id="c_d1",
        surface_form="DirectHub",
        entity_type="Concept",
        textual_envelope="stale",
        is_retired=True,
    )
    await retired_mention_payload.project_to_graph(mem_direct)
    await retired_ent_payload.project_to_graph(mem_direct)
    assert "ent_direct" not in mem_direct._entities
    assert not any(
        r["from_id"] == "ent_direct" and r["relation_type"] == "EXTRACTED_FROM"
        for r in mem_direct._generic_relations
    )

    # Full orchestrated Pipeline.run() with POLYSEMY_COLLISION split and ProjectionGraph
    mem_graph = InMemoryGraphStore()
    cfg = PipelineConfig(
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
            project_artifacts_to_graph=True,
        ),
        refinement=HermeneuticRefinementConfig(max_refinement_cycles=1),
    )

    c1 = L1Chunk(
        id="chunk_a1",
        source_doc_id="doc_a",
        sequence_index=0,
        token_count=6,
        text="Action triggers physical kinematic arcs.",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    c2 = L1Chunk(
        id="chunk_a2",
        source_doc_id="doc_a",
        sequence_index=1,
        token_count=6,
        text="Action requires moral deliberative endorsement.",
        embedding=[0.0, 1.0, 0.0, 0.0],
    )
    ent_action = L2Entity(
        id="ent_action",
        label="Concept",
        name="Action",
        description="Ambiguous causal vs normative hub.",
        source_chunk_ids=["chunk_a1", "chunk_a2"],
        polysemy_variance=0.45,
        conceptions=[
            EntityConception(
                id="ent_action::phys",
                entity_id="ent_action",
                perspective="Physicist",
                description="Bodily causal movement trigger",
                source_chunk_ids=["chunk_a1"],
                confidence=0.9,
            ),
            EntityConception(
                id="ent_action::eth",
                entity_id="ent_action",
                perspective="Ethicist",
                description="Normative moral agency commitment",
                source_chunk_ids=["chunk_a2"],
                confidence=0.9,
            ),
        ],
    )
    a_causal = TheoryAtom(
        id="ac_causal",
        text="Action reduces to kinematics.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_a1",
        entity_ids=["ent_action"],
        local_tenability=0.9,
        controversy_volatility=0.45,
        equilibrium_strength=0.8,
    )
    a_deontic = TheoryAtom(
        id="ac_deontic",
        text="Action resists reduction.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_a2",
        entity_ids=["ent_action"],
        local_tenability=0.9,
        equilibrium_strength=0.8,
    )
    rel_conflict = TheoryRelation(
        source_id="ac_deontic",
        target_id="ac_causal",
        relation_type="ATTACKS",
        confidence=0.9,
        scope="global",
        edge_tenability=0.3,
    )

    p1 = _StaticPhaseRunner(
        name="Phase 1: Ingestion",
        phase_key="phase1",
        input_view=None,
        reads_kinds=frozenset(),
        writes_kinds=frozenset({ArtifactKind.DOCUMENT, ArtifactKind.CHUNK}),
        dependencies=(),
        builder=lambda _inp, ctx: [
            build_document_artifact(
                L1Document(id="doc_a", title="Doc A", source_path="doc_a.md", chapter_count=1, chunk_count=2),
                run_id=ctx.run_id,
                phase_name="Phase 1: Ingestion",
                method="stub",
            ),
            build_chunk_artifact(c1, run_id=ctx.run_id, phase_name="Phase 1: Ingestion", method="stub"),
            build_chunk_artifact(c2, run_id=ctx.run_id, phase_name="Phase 1: Ingestion", method="stub"),
        ],
    )
    p2 = _StaticPhaseRunner(
        name="Phase 2: Entities",
        phase_key="phase2",
        input_view=EpistemicStateView,
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.LINKED_ENTITY, ArtifactKind.ENTITY_MENTION}),
        dependencies=("phase1",),
        builder=lambda _inp, ctx: [
            build_entity_mention_artifact(
                ent_action, "chunk_a1", run_id=ctx.run_id, phase_name="Phase 2: Entities", method="stub"
            ),
            build_entity_mention_artifact(
                ent_action, "chunk_a2", run_id=ctx.run_id, phase_name="Phase 2: Entities", method="stub"
            ),
            build_linked_entity_artifact(
                ent_action,
                ["artifact::mention::ent_action::chunk_a1", "artifact::mention::ent_action::chunk_a2"],
                run_id=ctx.run_id,
                phase_name="Phase 2: Entities",
                method="stub",
            ),
        ],
    )
    p6 = _StaticPhaseRunner(
        name="Phase 6: TheoryNet",
        phase_key="phase6",
        input_view=EpistemicStateView,
        reads_kinds=frozenset({ArtifactKind.CHUNK, ArtifactKind.LINKED_ENTITY}),
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
        dependencies=("phase2",),
        builder=lambda _inp, ctx: [
            build_theory_atom_artifact(a_causal, run_id=ctx.run_id, phase_name="Phase 6: TheoryNet", method="stub"),
            build_theory_atom_artifact(a_deontic, run_id=ctx.run_id, phase_name="Phase 6: TheoryNet", method="stub"),
            build_theory_relation_artifact(rel_conflict, run_id=ctx.run_id, phase_name="Phase 6: TheoryNet", method="stub"),
        ],
    )

    pipe = Pipeline(phases=[p1, p2, p6], config=cfg, projection_graph=mem_graph)
    res = await pipe.run(PipelineInput(source_paths=[]), run_id="run-split-prune")
    assert res.manifest.status == RunStatus.COMPLETED
    assert res.manifest.refinement_pass == 1

    assert "ent_action" not in mem_graph._entities
    assert not any(
        r["from_id"] == "ent_action" and r["relation_type"] == "EXTRACTED_FROM"
        for r in mem_graph._generic_relations
    )
    split_ids = [eid for eid in mem_graph._entities if eid.startswith("ent_action__sense_")]
    assert len(split_ids) == 2
    for sid in split_ids:
        assert any(
            r["from_id"] == sid and r["relation_type"] == "EXTRACTED_FROM"
            for r in mem_graph._generic_relations
        )


@pytest.mark.asyncio
async def test_standalone_refinement_wires_premise_recoverer_and_handles_missing_llm(
    tmp_path: Path,
) -> None:
    """Verify standalone refinement wires ``premise_recoverer`` and handles no-LLM gracefully."""
    cfg = PipelineConfig(
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
        ),
        refinement=HermeneuticRefinementConfig(max_refinement_cycles=1),
    )
    llm_stub = _StubStructuredLLM()

    det_llm, coord_llm = PipelineFactory.build_standalone_refinement(
        config=cfg, llm=llm_stub
    )
    assert isinstance(det_llm, TheoryNetDeficitDetector)
    assert isinstance(coord_llm.premise_recoverer, LLMTheoryGuidedPremiseRecoverer)
    assert coord_llm.premise_recoverer.llm is not None
    assert coord_llm._is_handler_enabled(EpistemicDeficitKind.ENTHYMEME_GAP, cfg.refinement) is True

    # Auto-discovery from Pipeline phases without getattr/hasattr
    p_llm = Phase3Runner(
        cfg.phase3,
        DEFAULT_SCHEMA,
        llm=llm_stub,
        embedding_model=_OrthogonalEmbeddingModel(),
        global_extractor=_OfflineGlobalExtractor(),
    )
    standalone_pipe = Pipeline(phases=[p_llm], config=cfg)
    assert isinstance(standalone_pipe.refinement_coordinator, ClosedLoopRefinementCoordinator)
    assert isinstance(
        standalone_pipe.refinement_coordinator.premise_recoverer,
        LLMTheoryGuidedPremiseRecoverer,
    )
    assert standalone_pipe.refinement_coordinator.premise_recoverer.llm is not None

    # No-LLM standalone wiring skips ENTHYMEME_GAP cleanly without raising ValueError
    _det_no_llm, coord_no_llm = PipelineFactory.build_standalone_refinement(config=cfg)
    assert isinstance(coord_no_llm.premise_recoverer, LLMTheoryGuidedPremiseRecoverer)
    assert coord_no_llm.premise_recoverer.llm is None
    assert (
        coord_no_llm._is_handler_enabled(EpistemicDeficitKind.ENTHYMEME_GAP, cfg.refinement)
        is False
    )

    col = ArtifactCollection(
        [
            build_theory_atom_artifact(
                TheoryAtom(
                    id="c_gap",
                    text="Unjustified theoretical claim",
                    component_type="TheoreticalHypothesis",
                    source_chunk_id="ck1",
                    local_tenability=0.9,
                ),
                run_id="r-no-llm",
                phase_name="Phase 6",
                method="stub",
            ),
            build_theory_atom_artifact(
                TheoryAtom(
                    id="c_down",
                    text="Downstream conclusion",
                    component_type="CoreExpansion",
                    source_chunk_id="ck1",
                    local_tenability=0.9,
                ),
                run_id="r-no-llm",
                phase_name="Phase 6",
                method="stub",
            ),
            build_theory_relation_artifact(
                TheoryRelation(
                    source_id="c_gap",
                    target_id="c_down",
                    relation_type="ENTAILS",
                    confidence=0.9,
                    scope="local",
                ),
                run_id="r-no-llm",
                phase_name="Phase 6",
                method="stub",
            ),
        ]
    )
    ctx = ArtifactExecutionContext(
        run_id="r-no-llm",
        manifest=__import__("episteme_pipeline.runs.models", fromlist=["RunManifest"]).RunManifest(run_id="r-no-llm"),
        pipeline_input=PipelineInput(source_paths=[]),
    )
    out = await coord_no_llm.refine(col, ctx)
    assert len(out.history) == len(col.history)


class _CountingCoordinator(ClosedLoopRefinementCoordinator):
    """Refinement coordinator subclass counting actual ``refine()`` executions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.refine_calls: int = 0

    async def refine(
        self,
        collection: ArtifactCollection,
        context: ArtifactExecutionContext,
        *,
        config: HermeneuticRefinementConfig | None = None,
    ) -> ArtifactCollection:
        """Count invocation and run closed-loop refinement."""
        self.refine_calls += 1
        return await super().refine(collection, context, config=config)


@pytest.mark.asyncio
async def test_orchestrated_refinement_reuse_on_identical_run_and_invalidation_on_config_change(
    tmp_path: Path,
) -> None:
    """Verify identical runs reuse refinement artifacts/events and config edits invalidate."""
    chunk = L1Chunk(
        id="chunk_ax_1",
        source_doc_id="doc_ax",
        sequence_index=0,
        token_count=8,
        text="Trial recorded N=42 confirming empirical grounding.",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    ungrounded = TheoryAtom(
        id="ax_ungrounded",
        text="Deliberative axioms match empirical trial observations.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_ax_1",
        parameters={"required_dimensions": ["sample_size"]},
        confidence=0.85,
        modal_prior=0.80,
        local_tenability=0.25,
        equilibrium_strength=0.25,
        tenability=TenabilityResult(
            local_score=0.25,
            edge_scores={},
            aggregated_score=0.25,
            is_tenable=False,
            tightest_blur=0.75,
            anomalies=["Missing sample_size measurement"],
        ),
    )

    def _make_phases() -> list[PhaseRunner[Any]]:
        return [
            _StaticPhaseRunner(
                name="Phase 1: Ingestion",
                phase_key="phase1",
                input_view=None,
                reads_kinds=frozenset(),
                writes_kinds=frozenset({ArtifactKind.CHUNK}),
                dependencies=(),
                builder=lambda _i, ctx: [
                    build_chunk_artifact(chunk, run_id=ctx.run_id, phase_name="Phase 1: Ingestion", method="stub")
                ],
            ),
            _StaticPhaseRunner(
                name="Phase 6: TheoryNet",
                phase_key="phase6",
                input_view=EpistemicStateView,
                reads_kinds=frozenset({ArtifactKind.CHUNK}),
                writes_kinds=frozenset({ArtifactKind.THEORY_ATOM}),
                dependencies=("phase1",),
                builder=lambda _i, ctx: [
                    build_theory_atom_artifact(
                        ungrounded, run_id=ctx.run_id, phase_name="Phase 6: TheoryNet", method="stub"
                    )
                ],
            ),
        ]

    from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
        GenericTheoryProjector,
    )
    from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
    from episteme_pipeline.refinement.axiom_grounder import TheoryGuidedAxiomGrounder

    llm_stub = _StubStructuredLLM()
    embedder = _OrthogonalEmbeddingModel()

    class _SimpleNER(NERExtractor):
        """Minimal NER extractor returning a single trial entity per chunk."""

        def fingerprint(self) -> dict[str, Any]:
            """Return deterministic extractor fingerprint."""
            return {"class": "_SimpleNER"}

        async def extract(self, chunk_id, chunk_text, schema, memory=None, anchor=None):
            """Return fixed trial entity for grounding."""
            return (
                [
                    L2Entity(
                        id="ent_trial",
                        label="Method",
                        name="Empirical Trial",
                        source_chunk_ids=[chunk_id],
                    )
                ],
                [],
                None,
                False,
                None,
            )

    def _build_pipe(
        *,
        vol_threshold: float,
        emitter: SimpleEventEmitter | None = None,
    ) -> tuple[Pipeline, _CountingCoordinator]:
        cfg = PipelineConfig(
            execution=ExecutionConfig(
                runs_dir=str(tmp_path / "runs"),
                artifacts_dir=str(tmp_path / "artifacts"),
            ),
            refinement=HermeneuticRefinementConfig(
                max_refinement_cycles=1,
                polysemy_volatility_threshold=vol_threshold,
            ),
        )
        coord = _CountingCoordinator(
            detector=TheoryNetDeficitDetector(config=cfg.refinement, schema=DEFAULT_SCHEMA),
            axiom_grounder=TheoryGuidedAxiomGrounder(
                ner_extractor=_SimpleNER(),
                llm=llm_stub,
                theory_projector=GenericTheoryProjector(),
                embedding_model=embedder,
                schema=DEFAULT_SCHEMA,
                vector_top_k=1,
            ),
            theorynet_projector=TheoryNetProjector(schema=DEFAULT_SCHEMA),
            config=cfg.refinement,
            schema=DEFAULT_SCHEMA,
        )
        pipe = Pipeline(
            phases=_make_phases(),
            config=cfg,
            event_emitter=emitter or SimpleEventEmitter(),
            refinement_coordinator=coord,
        )
        return pipe, coord

    # Run 1: fresh execution runs refinement Pass 1
    pipe1, coord1 = _build_pipe(vol_threshold=0.25)
    res1 = await pipe1.run(PipelineInput(source_paths=[]), run_id="run-ref-1")
    assert res1.manifest.status == RunStatus.COMPLETED
    assert coord1.refine_calls == 1
    assert res1.manifest.refinement_pass == 1
    assert res1.manifest.refinement_lineage_fingerprint is not None

    # Run 2: identical inputs & config -> refinement skipped and reused
    events2: list[Any] = []
    emitter2 = SimpleEventEmitter()
    metrics2 = MetricsObserver()
    emitter2.register_observer(metrics2)

    class _CaptureObserver:
        """Minimal observer capturing emitted domain events."""

        def on_event(self, event: Any) -> None:
            """Append received domain event to ``events2``."""
            events2.append(event)

    emitter2.register_observer(_CaptureObserver())
    pipe2, coord2 = _build_pipe(vol_threshold=0.25, emitter=emitter2)
    res2 = await pipe2.run(
        PipelineInput(source_paths=[]),
        run_id="run-ref-2",
        parent_run_id="run-ref-1",
    )
    assert res2.manifest.status == RunStatus.COMPLETED
    assert coord2.refine_calls == 0
    assert res2.manifest.refinement_pass == 1
    ref_recs2 = [r for r in res2.manifest.phase_records if r.phase_key == "refinement"]
    assert ref_recs2 and all(r.reused is True for r in ref_recs2)
    assert any(
        isinstance(ev, PhaseReused) and ev.phase_name == ref_recs2[0].phase_name
        for ev in events2
    )
    report2 = await pipe2.get_run_report("run-ref-2")
    raw2 = await pipe2.engine.get_run_artifacts_raw("run-ref-2")
    assert any(r.phase_key == "refinement" and r.reused for r in report2.phase_records)
    assert any(a.provenance.refinement_pass == 1 for a in raw2)

    # Run 3: edit refinement config threshold -> invalidates and re-runs refine()
    pipe3, coord3 = _build_pipe(vol_threshold=0.35)
    res3 = await pipe3.run(
        PipelineInput(source_paths=[]),
        run_id="run-ref-3",
        parent_run_id="run-ref-2",
    )
    assert res3.manifest.status == RunStatus.COMPLETED
    assert coord3.refine_calls == 1
    ref_recs3 = [r for r in res3.manifest.phase_records if r.phase_key == "refinement"]
    assert ref_recs3 and all(r.reused is False for r in ref_recs3)


# ---------------------------------------------------------------------------
# Area 5: Lossless Document & LocalRelation Codecs
# ---------------------------------------------------------------------------


def test_document_codec_preserves_metadata_types_and_local_relation_codec_preserves_none_chunk() -> None:
    """Verify exact metadata type preservation in DocumentCodec and None chunk in LocalRelationCodec."""
    doc = L1Document(
        id="doc-meta",
        title="Critique",
        source_path="/corpus/critique.md",
        chapter_count=4,
        chunk_count=19,
        metadata={
            "year": 1781,
            "score": 0.95,
            "peer_reviewed": True,
            "tags": ["kant", "epistemology"],
            "nested": {"edition": 2},
            "optional": None,
        },
    )
    doc_payload = DocumentCodec.to_payload(doc)
    roundtripped_payload = DocumentArtifact.model_validate_json(
        doc_payload.model_dump_json()
    )
    hydrated_doc = DocumentCodec.to_domain(roundtripped_payload)
    assert hydrated_doc.chapter_count == 4
    assert hydrated_doc.chunk_count == 19
    assert hydrated_doc.metadata == doc.metadata
    assert isinstance(hydrated_doc.metadata["year"], int)
    assert isinstance(hydrated_doc.metadata["score"], float)
    assert isinstance(hydrated_doc.metadata["peer_reviewed"], bool)
    assert isinstance(hydrated_doc.metadata["tags"], list)
    assert isinstance(hydrated_doc.metadata["nested"], dict)
    assert hydrated_doc.metadata["optional"] is None

    # Legacy JSON fallback when top-level counts are absent
    legacy_payload = DocumentArtifact.model_validate(
        {
            "document_id": "doc-leg",
            "title": "Legacy",
            "source_path": "leg.md",
            "metadata": {"chapter_count": "3", "chunk_count": "7", "tag": "hist"},
        }
    )
    legacy_doc = DocumentCodec.to_domain(legacy_payload)
    assert legacy_doc.chapter_count == 3
    assert legacy_doc.chunk_count == 7
    assert legacy_doc.metadata == {"tag": "hist"}

    triple_none_chunk = L2Triple(
        subject_id="s1",
        predicate="SUPPORTS",
        object_id="o1",
        source_chunk_id=None,
        confidence=0.88,
        scope="local",
    )
    rel_payload = LocalRelationCodec.to_payload(triple_none_chunk)
    assert rel_payload.source_chunk_id is None
    assert LocalRelationCodec.to_domain(rel_payload).source_chunk_id is None

    rel_env = build_local_relation_artifact(
        triple_none_chunk,
        run_id="r-codec",
        phase_name="Phase 2",
        method="stub",
    )
    rehydrated_env = ArtifactEnvelope.model_validate_json(rel_env.model_dump_json())
    assert rehydrated_env.payload.source_chunk_id is None
    assert rehydrated_env.payload.to_domain().source_chunk_id is None
