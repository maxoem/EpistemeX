"""Comprehensive deterministic tests for ISSUE-046 and ISSUE-047 architectural remediations.

Covers:
1. ISSUE-046:
   - Zero direct PhaseRunner writes to projection_graph; all target graph mutations
     flow exclusively through ArtifactGraphProjector.
   - ArtifactSubgraphReader implements GraphReader over ArtifactCollection, allowing
     Phase3, Phase3b, Phase4, and Phase5 to execute 100% offline without Neo4j.
   - ArtifactGraphProjector.project_collection() batches projections by ArtifactKind
     in topological dependency order (Nodes before Edges).
   - Two concurrent or alternating runs with different LLM configurations execute
     and resume via lineage-scoped FileSystemCheckpointStore without overwriting
     each other's checkpoints or entity states.
2. ISSUE-047:
   - ArtifactCollection.of_kind(*kinds, latest_only=True) deduplicates artifacts by
     identity_key using last-write-wins ordering while preserving full history.
   - Phase2ArtifactsView and Phase3ArtifactsView apply CanonicalizationArtifact alias
     mappings to both entities and local/global L2Triple endpoints (dropping self-loops).
   - Phase4EntityMaturationRunner reads entity textual envelopes from Phase3ArtifactsView
     without querying Neo4j, and its matured LinkedEntityArtifact updates overwrite
     Phase 2's raw entities in downstream views without DAG self-loop cycles.
   - Phase5ArgumentWebRunner cluster merges are reflected in Phase6Runner and
     TheoreticalEnrichmentRunner via canonicalized TheoryAtom and TheoryRelation views.
   - RunPhaseRecord.input_artifact_ids records the exact artifact IDs consumed by each
     phase's input_view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_canonicalization_artifact,
    build_chunk_artifact,
    build_document_artifact,
    build_entity_mention_artifact,
    build_fusion_cluster_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
    Phase5ArtifactsView,
)
from episteme_pipeline.artifacts.invalidate import ArtifactDependencyGraph
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.config import (
    ExecutionConfig,
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
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
from episteme_pipeline.phases.phase3b_consolidation import (
    Phase3bLatentConsolidationRunner,
)
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase4_entity_maturation import (
    EntitySynthesisOutput,
    Phase4EntityMaturationRunner,
)
from episteme_pipeline.phases.phase5_fusion.argument_web import Phase5ArgumentWebRunner
from episteme_pipeline.phases.phase6_theorynet import Phase6Runner
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.post_processing.theoretical_enrichment import (
    TheoreticalEnrichmentRunner,
)
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    InducedTheoryElement,
    InducedTheoryLaw,
    TheoryRegistry,
)
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
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
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig


# ---------------------------------------------------------------------------
# Deterministic Fakes & Recording Spies
# ---------------------------------------------------------------------------


class DeterministicEmbeddingModel(EmbeddingModel):
    """Deterministic embedding model that maps text prefixes to controlled unit vectors."""

    async def aget_text_embedding(self, text: str) -> list[float]:
        low = text.lower()
        if "kant" in low:
            return [1.0, 0.0, 0.0, 0.0]
        if "space" in low or "raum" in low:
            return [0.0, 1.0, 0.0, 0.0]
        if "experience" in low or "empirical" in low:
            return [0.0, 0.0, 1.0, 0.0]
        return [0.0, 0.0, 0.0, 1.0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.aget_text_embedding(t) for t in texts]


class DeterministicReranker(RelationReranker):
    """Deterministic relation reranker for offline tests."""

    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: Any,
        entity_b: L2Entity,
        env_b: Any,
    ) -> float:
        return 0.95

    async def score_pairs(
        self, pairs: list[tuple[str, str]], **kwargs: Any
    ) -> list[float]:
        return [0.95 for _ in pairs]


class DeterministicMaturationLLM:
    """Deterministic structured LLM stub for entity maturation and enrichment."""

    def __init__(self, tag: str = "v1") -> None:
        self.tag = tag
        self.synthesized_entities: list[str] = []
        self.envelopes_seen: dict[str, str] = {}

    def fingerprint(self) -> dict[str, Any]:
        return {"model": f"deterministic-llm-{self.tag}"}

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        if output_cls is EntitySynthesisOutput:
            entity_name = prompt_args.get("entity_name", "Unknown")
            envelopes = prompt_args.get("envelopes", "")
            self.synthesized_entities.append(entity_name)
            self.envelopes_seen[entity_name] = envelopes
            return EntitySynthesisOutput(
                description=f"[{self.tag}] Synthesized mature description for {entity_name}"
            )
        return output_cls.model_construct()

    async def predict_text(
        self,
        prompt: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> str:
        return f"[{self.tag}] reasoning"


class OfflineNERExtractor(NERExtractor):
    """Deterministic NER extractor emitting duplicate entity aliases across chunks."""

    def __init__(self, tag: str = "v1") -> None:
        self.tag = tag
        self.calls: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"extractor": "OfflineNERExtractor", "tag": self.tag}

    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: dict[str, Any] | None = None,
        anchor: Any = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict[str, Any] | None, bool, str | None]:
        self.calls.append(chunk_id)
        if "chunk_1" in chunk_id or chunk_text.startswith("# Section 1"):
            e_kant = L2Entity(
                id="e_kant_canonical",
                label="Person",
                name="Immanuel Kant",
                description=f"Raw Kant ({self.tag})",
                textual_envelope="Immanuel Kant argued that space is an a priori intuition.",
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

        # Second chunk uses alias "I. Kant" with a different entity ID to test Phase 3b merge
        e_kant_alias = L2Entity(
            id="e_kant_dup",
            label="Person",
            name="I. Kant",
            description=f"Duplicate Kant ({self.tag})",
            textual_envelope="I. Kant further linked space to synthetic a priori judgments.",
            source_chunk_ids=[chunk_id],
            confidence=0.88,
        )
        e_space_2 = L2Entity(
            id="e_space",
            label="Concept",
            name="Space",
            description=f"Raw Space ({self.tag})",
            textual_envelope="Space grounds geometric cognition in sensibility.",
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
        return [e_kant_alias, e_space_2], [triple_dup], None, False, None


class NoOpEntityLinker(EntityLinker):
    """Leaves extracted entity IDs unmerged in Phase 2 so Phase 3b can consolidate them."""

    async def link(
        self, mention: L2Entity, graph_store: Any, top_k: int = 10, threshold: float = 0.85
    ) -> L2Entity | None:
        # Verify graph_store passed to linker is an ArtifactSubgraphReader
        assert isinstance(graph_store, ArtifactSubgraphReader)
        return None


class OfflineGlobalExtractor(GlobalRelationExtractor):
    """Deterministic global relation extractor verifying ArtifactSubgraphReader usage."""

    def __init__(self, fail_on_second_pair_once: bool = False) -> None:
        self.fail_on_second_pair_once = fail_on_second_pair_once
        self._failed_once = False
        self.evaluated_pairs: list[str] = []
        self.reader_types: list[type[Any]] = []

    async def extract_pair(
        self, pair: CandidatePair, graph_store: Any, schema: SchemaConfig
    ) -> L2Triple | None:
        self.reader_types.append(type(graph_store))
        self.evaluated_pairs.append(pair.key)
        # Verify neighborhood lookup works on the in-memory reader
        sub = await graph_store.get_neighborhood(pair.entity_a.id, depth=1)
        assert sub.center_id == pair.entity_a.id
        if self.fail_on_second_pair_once and len(self.evaluated_pairs) == 2 and not self._failed_once:
            self._failed_once = True
            raise RuntimeError("Simulated crash after batch 1")
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


class OfflineADUSegmenter(ADUSegmenter):
    """Deterministic ADU segmenter."""

    async def segment(self, chunk_id: str, chunk_text: str) -> tuple[str, list[str]]:
        return f"<AC1>{chunk_text}</AC1>", ["AC1"]


class OfflineACCClassifier(ACCClassifier):
    """Deterministic ACC classifier recording chunk_entities passed from Phase 4."""

    def __init__(self) -> None:
        self.seen_chunk_entities: list[L2Entity] = []
        self._counter = 0

    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: SchemaConfig,
        chunk_entities: list[L2Entity] | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        if chunk_entities:
            self.seen_chunk_entities.extend(chunk_entities)
        self._counter += 1
        if self._counter == 1:
            a1 = TheoryAtom(
                id="atom_claim_1",
                text="All knowledge begins with experience.",
                component_type="TheoreticalHypothesis",
                source_chunk_id=chunk_id,
                entity_ids=[e.id for e in (chunk_entities or [])],
                confidence=0.92,
                modal_strength=0.85,
                base_score=0.85,
            )
            a2 = TheoryAtom(
                id="atom_obs_1",
                text="Empirical observation of spatial geometry.",
                component_type="ObservationUnit",
                source_chunk_id=chunk_id,
                entity_ids=[e.id for e in (chunk_entities or [])],
                confidence=0.90,
                modal_strength=0.80,
                base_score=0.80,
            )
            rel = TheoryRelation(
                source_id="atom_obs_1",
                target_id="atom_claim_1",
                relation_type="SUPPORTS",
                confidence=0.88,
                scope="local",
            )
            return [a1, a2], [rel]
        else:
            # Second chunk produces a duplicate claim that Phase 5 will cluster with atom_claim_1
            a_dup = TheoryAtom(
                id="atom_claim_dup",
                text="All knowledge begins with empirical experience.",
                component_type="TheoreticalHypothesis",
                source_chunk_id=chunk_id,
                entity_ids=[e.id for e in (chunk_entities or [])],
                confidence=0.89,
                modal_strength=0.82,
                base_score=0.82,
            )
            a_obs_2 = TheoryAtom(
                id="atom_obs_2",
                text="Second observation supporting the duplicate claim.",
                component_type="ObservationUnit",
                source_chunk_id=chunk_id,
                entity_ids=[e.id for e in (chunk_entities or [])],
                confidence=0.91,
                modal_strength=0.84,
                base_score=0.84,
            )
            rel_dup = TheoryRelation(
                source_id="atom_obs_2",
                target_id="atom_claim_dup",
                relation_type="SUPPORTS",
                confidence=0.90,
                scope="local",
            )
            return [a_dup, a_obs_2], [rel_dup]


class OfflineARCClassifier(ARCClassifier):
    """Deterministic ARC classifier."""

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: Any,
        global_extractor: Any = None,
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]:
        assert isinstance(graph_store, ArtifactSubgraphReader)
        return []


class RecordingProjectionGraph(ProjectionGraph):
    """Records every call in order to verify topological bulk projection."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def upsert_node(
        self,
        label: str,
        node_id: str,
        properties: dict[str, Any],
        *,
        extra_labels: tuple[str, ...] = (),
        create_only_properties: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(("upsert_node", (label, node_id)))

    async def prune_document_children(
        self,
        document_id: str,
        *,
        keep_chunk_ids: list[str],
        keep_chapter_ids: list[str],
    ) -> dict[str, int]:
        self.calls.append(("prune_document_children", document_id))
        return {"chunks": 0, "chapters": 0}

    async def upsert_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(("upsert_relation", (from_id, relation_type, to_id)))

    async def upsert_relations(self, relations: list[dict[str, Any]]) -> None:
        self.calls.append(("upsert_relations", len(relations)))

    async def upsert_chunk(self, chunk: L1Chunk) -> None:
        self.calls.append(("upsert_chunk", chunk.id))

    async def upsert_chunks(self, chunks: list[L1Chunk]) -> None:
        self.calls.append(("upsert_chunks", [c.id for c in chunks]))

    async def upsert_entity(self, entity: L2Entity) -> None:
        self.calls.append(("upsert_entity", entity.id))

    async def upsert_entities(self, entities: list[L2Entity]) -> None:
        self.calls.append(("upsert_entities", [e.id for e in entities]))

    async def upsert_triple(self, triple: L2Triple) -> None:
        self.calls.append(("upsert_triple", triple.predicate))

    async def upsert_triples(self, triples: list[L2Triple]) -> None:
        self.calls.append(("upsert_triples", len(triples)))

    async def upsert_theory_atom(self, component: TheoryAtom) -> None:
        self.calls.append(("upsert_theory_atom", component.id))

    async def upsert_argument_component(self, component: TheoryAtom) -> None:
        self.calls.append(("upsert_argument_component", component.id))

    async def upsert_argument_components(self, components: list[TheoryAtom]) -> None:
        self.calls.append(("upsert_argument_components", [c.id for c in components]))

    async def upsert_theory_relation(self, relation: TheoryRelation) -> None:
        self.calls.append(("upsert_theory_relation", relation.relation_type))

    async def upsert_theory_relations(self, relations: list[TheoryRelation]) -> None:
        self.calls.append(("upsert_theory_relations", len(relations)))

    async def upsert_community(
        self, community_id: str, level: int, entity_ids: list[str]
    ) -> None:
        self.calls.append(("upsert_community", community_id))

    async def upsert_communities(self, communities: list[dict[str, Any]]) -> None:
        self.calls.append(("upsert_communities", len(communities)))

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# ISSUE-047 Tests: ArtifactCollection, Canonicalization, Maturation, L3 Fusion
# ---------------------------------------------------------------------------


def test_artifact_collection_of_kind_deduplicates_by_identity_key_last_write_wins() -> None:
    """ArtifactCollection.of_kind(*kinds, latest_only=True) deduplicates by identity_key."""
    raw_entity = L2Entity(
        id="ent_kant",
        label="Person",
        name="Immanuel Kant",
        description="Raw first-mention description",
        is_mature=False,
        source_chunk_ids=["c1"],
    )
    matured_entity = L2Entity(
        id="ent_kant",
        label="Person",
        name="Immanuel Kant",
        description="Matured synthesized description across all chunks",
        is_mature=True,
        source_chunk_ids=["c1", "c2"],
    )

    art_p2 = build_linked_entity_artifact(
        raw_entity,
        ["artifact::mention::ent_kant::c1"],
        run_id="run-1",
        phase_name="Phase 2: Entity & Local Relation Discovery",
        method="phase2.entity_discovery",
    )
    art_p4_mat = build_linked_entity_artifact(
        matured_entity,
        ["artifact::mention::ent_kant::c1", "artifact::mention::ent_kant::c2"],
        run_id="run-1",
        phase_name="Phase 4: Entity Maturation (Batch Epistemic Synthesis)",
        method="Phase4EntityMaturationRunner",
        upstream_artifact_ids=[art_p2.artifact_id],
    )

    collection = ArtifactCollection([art_p2, art_p4_mat])

    # Full history is preserved
    assert len(collection.history) == 2
    assert len(collection.of_kind(ArtifactKind.LINKED_ENTITY, latest_only=False)) == 2

    # latest_only=True (default) returns only the matured entity envelope
    latest = collection.of_kind(ArtifactKind.LINKED_ENTITY)
    assert len(latest) == 1
    assert latest[0].payload.is_mature is True
    assert latest[0].payload.description == "Matured synthesized description across all chunks"

    # Also verify ArtifactDependencyGraph does not create a self-loop cycle when two
    # envelopes share the same identity_key
    dag = ArtifactDependencyGraph.from_artifacts(collection.history)
    assert dag.upstream.get("linked_entity::ent_kant", set()) == set()
    assert dag.topsort() == ["linked_entity::ent_kant"]


def test_phase2_and_phase3_views_apply_canonicalization_to_entities_and_triples() -> None:
    """Phase2ArtifactsView and Phase3ArtifactsView canonicalize entities and triples."""
    e_canon = L2Entity(
        id="e_kant",
        label="Person",
        name="Immanuel Kant",
        description="Canonical Kant",
        source_chunk_ids=["c1"],
    )
    e_dup = L2Entity(
        id="e_kant_alias",
        label="Person",
        name="I. Kant",
        description="Alias Kant",
        source_chunk_ids=["c2"],
    )
    e_space = L2Entity(
        id="e_space",
        label="Concept",
        name="Space",
        source_chunk_ids=["c1", "c2"],
    )

    m1 = build_entity_mention_artifact(
        e_canon.model_copy(update={"textual_envelope": "Env 1"}),
        "c1",
        run_id="r1",
        phase_name="P2",
        method="m",
    )
    m2 = build_entity_mention_artifact(
        e_dup.model_copy(update={"textual_envelope": "Env 2"}),
        "c2",
        run_id="r1",
        phase_name="P2",
        method="m",
    )
    le1 = build_linked_entity_artifact(e_canon, [m1.artifact_id], run_id="r1", phase_name="P2", method="m")
    le2 = build_linked_entity_artifact(e_dup, [m2.artifact_id], run_id="r1", phase_name="P2", method="m")
    le3 = build_linked_entity_artifact(e_space, [], run_id="r1", phase_name="P2", method="m")

    # Local triple using duplicate ID + self-loop triple between e_kant_alias and e_kant
    local_t1 = build_local_relation_artifact(
        L2Triple(
            subject_id="e_kant_alias",
            predicate="DEFINES",
            object_id="e_space",
            confidence=0.9,
            scope="local",
            source_chunk_id="c2",
        ),
        run_id="r1",
        phase_name="P2",
        method="m",
    )
    local_self_loop = build_local_relation_artifact(
        L2Triple(
            subject_id="e_kant_alias",
            predicate="SAME_AS",
            object_id="e_kant",
            confidence=0.95,
            scope="local",
            source_chunk_id="c2",
        ),
        run_id="r1",
        phase_name="P2",
        method="m",
    )
    global_t1 = build_global_relation_artifact(
        L2Triple(
            subject_id="e_space",
            predicate="ATTRIBUTED_TO",
            object_id="e_kant_alias",
            confidence=0.88,
            scope="global",
        ),
        {"ATTRIBUTED_TO": 1},
        run_id="r1",
        phase_name="P3",
        method="m",
    )
    canon_art = build_canonicalization_artifact(
        original_id="e_kant_alias",
        canonical_id="e_kant",
        run_id="r1",
        phase_name="P3b",
        method="m",
    )

    collection = ArtifactCollection(
        [m1, m2, le1, le2, le3, local_t1, local_self_loop, global_t1, canon_art]
    )

    p2_view = Phase2ArtifactsView.from_collection(collection)
    p3_view = Phase3ArtifactsView.from_collection(collection)

    # Duplicate entity is merged into canonical entity
    entity_ids = [e.id for e in p3_view.entities]
    assert entity_ids == ["e_kant", "e_space"]
    kant_entity = next(e for e in p3_view.entities if e.id == "e_kant")
    assert set(kant_entity.source_chunk_ids) == {"c1", "c2"}

    # Envelopes from both canonical and duplicate mentions are combined under canonical ID
    assert p3_view.entity_envelopes_by_id["e_kant"] == ["Env 1", "Env 2"]

    # Local and global triples have endpoints rewritten to e_kant, and self-loop is dropped
    assert len(p2_view.local_triples) == 1
    assert p2_view.local_triples[0].subject_id == "e_kant"
    assert p2_view.local_triples[0].object_id == "e_space"

    assert len(p3_view.global_triples) == 1
    assert p3_view.global_triples[0].subject_id == "e_space"
    assert p3_view.global_triples[0].object_id == "e_kant"


@pytest.mark.asyncio
async def test_phase4_maturation_reads_envelopes_from_view_offline_and_updates_downstream(
    tmp_path: Path,
) -> None:
    """Phase4EntityMaturationRunner runs 100% offline from Phase3ArtifactsView and overwrites raw entities."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM

    e_canon = L2Entity(
        id="e_kant",
        label="Person",
        name="Immanuel Kant",
        description="Initial raw description",
        is_mature=False,
        source_chunk_ids=["c1", "c2"],
    )
    e_dup = L2Entity(
        id="e_kant_dup",
        label="Person",
        name="I. Kant",
        description="Duplicate raw description",
        is_mature=False,
        source_chunk_ids=["c2"],
    )

    m1 = build_entity_mention_artifact(
        e_canon.model_copy(update={"textual_envelope": "Envelope from chunk 1"}),
        "c1",
        run_id="r1",
        phase_name="P2",
        method="m",
    )
    m2 = build_entity_mention_artifact(
        e_dup.model_copy(update={"textual_envelope": "Envelope from chunk 2"}),
        "c2",
        run_id="r1",
        phase_name="P2",
        method="m",
    )
    le1 = build_linked_entity_artifact(e_canon, [m1.artifact_id], run_id="r1", phase_name="P2", method="m")
    le2 = build_linked_entity_artifact(e_dup, [m2.artifact_id], run_id="r1", phase_name="P2", method="m")
    canon = build_canonicalization_artifact("e_kant_dup", "e_kant", run_id="r1", phase_name="P3b", method="m")

    upstream_collection = ArtifactCollection([m1, m2, le1, le2, canon])
    p3_view = Phase3ArtifactsView.from_collection(upstream_collection)

    llm_spy = DeterministicMaturationLLM(tag="maturation")
    cached_llm = DiskCachedStructuredLLM(llm_spy, cache_dir=tmp_path / "llm_cache")
    runner = Phase4EntityMaturationRunner(
        config=Phase4EntityMaturationConfig(maturation_top_k=5),
        llm=cached_llm,
        graph_store=None,  # Zero Neo4j / GraphStore connection
        embedding_model=DeterministicEmbeddingModel(),
    )
    ctx = ArtifactExecutionContext(
        run_id="r1",
        manifest=RunManifest(run_id="r1"),
        pipeline_input=PipelineInput(source_paths=[]),
        previous=upstream_collection,
    )

    maturation_out = await runner.run(p3_view, ctx)
    # Only the canonical entity was matured (duplicate was already consolidated)
    assert llm_spy.synthesized_entities == ["Immanuel Kant"]
    assert "Envelope from chunk 1" in llm_spy.envelopes_seen["Immanuel Kant"]
    assert "Envelope from chunk 2" in llm_spy.envelopes_seen["Immanuel Kant"]

    # Downstream Phase3ArtifactsView (consumed by Phase 4 Argument Mining) sees the matured entity
    combined = ArtifactCollection(upstream_collection.artifacts + maturation_out.artifacts)
    downstream_view = Phase3ArtifactsView.from_collection(combined)
    assert len(downstream_view.entities) == 1
    assert downstream_view.entities[0].id == "e_kant"
    assert downstream_view.entities[0].is_mature is True
    assert "[maturation] Synthesized mature description" in (downstream_view.entities[0].description or "")


@pytest.mark.asyncio
async def test_phase5_cluster_merges_propagate_to_phase6_and_theoretical_enrichment() -> None:
    """Phase 5 FusionDecisionArtifact cluster merges propagate into Phase 6 and TheoreticalEnrichment."""
    a1 = TheoryAtom(
        id="atom_canon",
        text="Kant's thesis on space",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        confidence=0.90,
        modal_strength=0.85,
        base_score=0.85,
    )
    a2 = TheoryAtom(
        id="atom_merged",
        text="Kant's equivalent thesis on spatial intuition",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        confidence=0.88,
        modal_strength=0.80,
        base_score=0.80,
    )
    obs = TheoryAtom(
        id="atom_obs",
        text="Geometric demonstration in Euclidean space",
        component_type="ObservationUnit",
        source_chunk_id="c2",
        confidence=0.95,
        modal_strength=0.90,
        base_score=0.90,
    )
    # Relation originally targets the duplicate atom_merged
    rel = TheoryRelation(
        source_id="atom_obs",
        target_id="atom_merged",
        relation_type="SUPPORTS",
        confidence=0.92,
        scope="local",
    )

    art_a1 = build_argument_component_artifact(a1, run_id="r1", phase_name="P4", method="m")
    art_a2 = build_argument_component_artifact(a2, run_id="r1", phase_name="P4", method="m")
    art_obs = build_argument_component_artifact(obs, run_id="r1", phase_name="P4", method="m")
    art_rel = build_argument_relation_artifact(rel, run_id="r1", phase_name="P4", method="m")
    art_fusion = build_fusion_cluster_artifact(
        ["atom_canon", "atom_merged"],
        theory_fusion_applied=True,
        run_id="r1",
        phase_name="P5",
        method="m",
    )

    collection = ArtifactCollection([art_a1, art_a2, art_obs, art_rel, art_fusion])
    p5_view = Phase5ArtifactsView.from_collection(collection)

    # Canonical atoms have atom_merged collapsed into atom_canon, and relation target rewritten
    assert [a.id for a in p5_view.canonical_theory_atoms] == ["atom_canon", "atom_obs"]
    assert len(p5_view.canonical_theory_relations) == 1
    assert p5_view.canonical_theory_relations[0].source_id == "atom_obs"
    assert p5_view.canonical_theory_relations[0].target_id == "atom_canon"

    ctx = ArtifactExecutionContext(
        run_id="r1",
        manifest=RunManifest(run_id="r1"),
        pipeline_input=PipelineInput(source_paths=[]),
        previous=collection,
    )

    # Phase 6 runs without graph_store and emits TheoryAtomArtifact / TheoryRelationArtifact over canonical L3
    p6_runner = Phase6Runner(config=Phase6Config(), schema=DEFAULT_SCHEMA, graph_store=None)
    p6_out = await p6_runner.run(p5_view, ctx)
    p6_atoms = [a.payload for a in p6_out.of_kind(ArtifactKind.THEORY_ATOM)]
    p6_rels = [a.payload for a in p6_out.of_kind(ArtifactKind.THEORY_RELATION)]
    assert {a.component_id for a in p6_atoms} == {"atom_canon", "atom_obs"}
    assert len(p6_rels) == 1
    assert p6_rels[0].target_component_id == "atom_canon"

    # TheoreticalEnrichmentRunner also evaluates over canonical L3 without graph_store
    registry = TheoryRegistry()
    registry.register(
        InducedTheoryElement(
            theory_id="kantian_space",
            name="Kantian Transcendental Aesthetic",
            claimant_hypothesis_ids=["atom_canon"],
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
    enrichment_runner = TheoreticalEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(enabled=True, induce_theories=False),
        schema=DEFAULT_SCHEMA,
        graph_store=None,
        registry=registry,
    )
    enrichment_out = await enrichment_runner.run(p5_view, ctx)
    enrichment_items = enrichment_out.of_kind(ArtifactKind.THEORETICAL_ENRICHMENT)
    assert len(enrichment_items) >= 1


# ---------------------------------------------------------------------------
# ISSUE-046 Tests: Offline Execution, Topological Bulk Projection, Run Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_graph_projector_batches_in_topological_order() -> None:
    """ArtifactGraphProjector.project_collection() projects Nodes before Edges in batches."""
    doc = L1Document(id="doc_1", title="Critique", source_path="critique.md", chapter_count=1, chunk_count=1)
    chunk = L1Chunk(
        id="chunk_1",
        text="Kant discussed space.",
        source_doc_id="doc_1",
        chapter_id="chap_1",
        sequence_index=0,
        token_count=4,
    )
    e1 = L2Entity(id="e_kant", label="Person", name="Immanuel Kant", source_chunk_ids=["chunk_1"])
    e2 = L2Entity(id="e_space", label="Concept", name="Space", source_chunk_ids=["chunk_1"])
    t_local = L2Triple(
        subject_id="e_kant",
        predicate="DEFINES",
        object_id="e_space",
        confidence=0.9,
        scope="local",
        source_chunk_id="chunk_1",
    )
    atom = TheoryAtom(
        id="atom_1",
        text="Space is a priori.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_1",
        entity_ids=["e_kant", "e_space"],
    )
    t_rel = TheoryRelation(
        source_id="atom_1",
        target_id="atom_1",
        relation_type="SUPPORTS",
        confidence=0.9,
        scope="local",
    )

    # Intentionally scramble artifact order: edges before nodes!
    scrambled_artifacts = [
        build_argument_relation_artifact(t_rel, run_id="r1", phase_name="P4", method="m"),
        build_local_relation_artifact(t_local, run_id="r1", phase_name="P2", method="m"),
        build_entity_mention_artifact(e1, "chunk_1", run_id="r1", phase_name="P2", method="m"),
        build_argument_component_artifact(atom, run_id="r1", phase_name="P4", method="m"),
        build_linked_entity_artifact(e1, [], run_id="r1", phase_name="P2", method="m"),
        build_linked_entity_artifact(e2, [], run_id="r1", phase_name="P2", method="m"),
        build_chunk_artifact(chunk, run_id="r1", phase_name="P1", method="m"),
        build_document_artifact(doc, run_id="r1", phase_name="P1", method="m"),
    ]

    spy_graph = RecordingProjectionGraph()
    projector = ArtifactGraphProjector(spy_graph)
    await projector.project_collection(ArtifactCollection(scrambled_artifacts), batch_size=500)

    call_names = [name for name, _ in spy_graph.calls]
    # Node upserts (upsert_node, upsert_chunks, upsert_entities, upsert_argument_components)
    # MUST all occur before edge upserts (upsert_relations, upsert_triples, upsert_theory_relations)
    last_node_idx = max(
        idx
        for idx, name in enumerate(call_names)
        if name in {"upsert_node", "upsert_chunks", "upsert_entities", "upsert_argument_components"}
    )
    first_edge_idx = min(
        idx
        for idx, name in enumerate(call_names)
        if name in {"upsert_relations", "upsert_triples", "upsert_theory_relations"}
    )
    assert last_node_idx < first_edge_idx


@pytest.mark.asyncio
async def test_phase3_crash_resume_recovers_committed_triples_from_checkpoint_store(
    tmp_path: Path,
) -> None:
    """Phase3Runner recovers previously committed triples from FileSystemCheckpointStore on resume."""
    ckpt_store = FileSystemCheckpointStore(tmp_path / "_checkpoints")
    entities = [
        L2Entity(id="e1", label="Person", name="Kant", source_chunk_ids=["c1"]),
        L2Entity(id="e2", label="Concept", name="Space", source_chunk_ids=["c1"]),
        L2Entity(id="e3", label="Concept", name="Time", source_chunk_ids=["c1"]),
    ]
    chunk = L1Chunk(id="c1", text="Kant on space and time.", source_doc_id="d1", sequence_index=0, token_count=5)
    col = ArtifactCollection(
        [
            build_chunk_artifact(chunk, run_id="r1", phase_name="P1", method="m"),
            *[build_linked_entity_artifact(e, [], run_id="r1", phase_name="P2", method="m") for e in entities],
        ]
    )
    view = Phase2ArtifactsView.from_collection(col)

    extractor = OfflineGlobalExtractor(fail_on_second_pair_once=True)
    runner = Phase3Runner(
        config=Phase3Config(batch_size=1),
        schema=DEFAULT_SCHEMA,
        llm=None,
        embedding_model=DeterministicEmbeddingModel(),
        graph_store=ckpt_store,
        global_extractor=extractor,
    )
    ctx = ArtifactExecutionContext(
        run_id="r1",
        manifest=RunManifest(run_id="r1"),
        pipeline_input=PipelineInput(source_paths=[]),
        previous=col,
        lineage_fingerprint="fp_run_1",
    )

    # First run processes batch 1 (commits 1 triple), quarantine-fails pair 2, and commits batch 3
    out1 = await runner.run(view, ctx)
    triples_1 = [a.payload for a in out1.of_kind(ArtifactKind.GLOBAL_RELATION)]
    assert len(triples_1) == 2

    # Second run with same lineage_fingerprint resumes: all pairs are already checkpointed,
    # and the committed triples from run 1 are recovered into the returned ArtifactCollection!
    out2 = await runner.run(view, ctx)
    triples_2 = [a.payload for a in out2.of_kind(ArtifactKind.GLOBAL_RELATION)]
    assert len(triples_2) == 2


@pytest.mark.asyncio
async def test_full_pipeline_executes_offline_and_isolates_alternating_runs(
    tmp_path: Path,
) -> None:
    """Full Pipeline executes 100% offline, tracks exact input_artifact_ids, and isolates alternating runs."""
    doc_path = tmp_path / "kant_intuition.md"
    doc_path.write_text(
        "# Section 1\nImmanuel Kant argued that space is an a priori intuition.\n\n"
        "# Section 2\nI. Kant further linked space to synthetic a priori judgments.\n",
        encoding="utf-8",
    )

    runs_dir = tmp_path / "runs"
    artifacts_dir = tmp_path / "artifacts"

    def build_test_pipeline(tag: str, projection_graph: RecordingProjectionGraph | None = None) -> tuple[Pipeline, OfflineNERExtractor, DeterministicMaturationLLM, OfflineACCClassifier]:
        cfg = PipelineConfig(
            phase1=Phase1Config(chunk_size=12, chunk_overlap=0),
            phase2=Phase2Config(batch_size=1),
            phase3=Phase3Config(batch_size=2),
            phase3b=Phase3bConfig(
                enabled=True,
                dense_similarity_threshold=0.80,
                relation_overlap_threshold=0.50,
            ),
            phase4_maturation=Phase4EntityMaturationConfig(maturation_top_k=3),
            phase4=Phase4Config(batch_size=1),
            phase5=Phase5Config(
                argument_clustering_enabled=True,
                theory_fusion_enabled=False,
                fusion_similarity_threshold=0.80,
            ),
            phase6=Phase6Config(),
            theoretical_enrichment=TheoreticalEnrichmentConfig(enabled=False),
            execution=ExecutionConfig(
                runs_dir=str(runs_dir),
                artifacts_dir=str(artifacts_dir),
                project_artifacts_to_graph=projection_graph is not None,
            ),
        )
        ner_ext = OfflineNERExtractor(tag=tag)
        llm_stub = DeterministicMaturationLLM(tag=tag)
        acc_clf = OfflineACCClassifier()

        pipe = Pipeline.for_task(
            llm=llm_stub,
            relation_reranker=DeterministicReranker(),
            embedding_model=DeterministicEmbeddingModel(),
            config=cfg,
            graph_reader=None,
            projection_graph=projection_graph,
            checkpoint_store=None,
            ner_extractor=ner_ext,
            entity_linker=NoOpEntityLinker(),
            acc_classifier=acc_clf,
            arc_classifier=OfflineARCClassifier(),
        )
        # Inject OfflineADUSegmenter into Phase 4
        for phase in pipe.phases:
            if isinstance(phase, Phase4Runner):
                phase.adu_segmenter = OfflineADUSegmenter()
            if isinstance(phase, Phase3Runner):
                phase.global_extractor = OfflineGlobalExtractor()
        return pipe, ner_ext, llm_stub, acc_clf

    # Run A (tag="runA") with RecordingProjectionGraph enabled
    spy_projection = RecordingProjectionGraph()
    pipe_a, ner_a, llm_a, acc_a = build_test_pipeline("runA", projection_graph=spy_projection)

    # Verify zero phase runner holds a reference to spy_projection
    for phase in pipe_a.phases:
        assert phase.graph_store is not spy_projection

    res_a = await pipe_a.run(PipelineInput(source_paths=[str(doc_path)]), run_id="run-A")
    assert res_a.manifest.status.value == "completed"

    # 1. Phase 3b consolidated e_kant_dup into e_kant_canonical, so Phase 4 Maturation
    #    only synthesized 2 canonical entities (Immanuel Kant & Space), NOT 3!
    assert len(llm_a.synthesized_entities) == 2

    # 2. Phase 4 ACCClassifier received the matured canonical entities from ArtifactSubgraphReader
    assert any(e.is_mature for e in acc_a.seen_chunk_entities)
    seen_ids = {e.id for e in acc_a.seen_chunk_entities}
    assert len(seen_ids) == 2
    assert not ({"e_kant_canonical", "e_kant_dup"}.issubset(seen_ids))

    # 3. RunPhaseRecord.input_artifact_ids records the exact artifact IDs consumed by each phase's input_view
    records_by_name = {r.phase_name: r for r in res_a.manifest.phase_records}
    p1_record = records_by_name["Phase 1: Data Foundation"]
    p2_record = records_by_name["Phase 2: Entity & Local Relation Discovery"]
    p4_record = records_by_name["Phase 4: Argument Mining"]
    assert p1_record.input_artifact_ids == []
    assert set(p2_record.input_artifact_ids) == set(p1_record.output_artifact_ids)
    # Phase 4 Argument Mining consumes Phase 1 chunks + Phase 2/4-maturation entities + Phase 3 relations + Phase 3b canonicalizations
    assert set(p1_record.output_artifact_ids).issubset(set(p4_record.input_artifact_ids))
    assert len(p4_record.input_artifact_ids) > len(p1_record.output_artifact_ids)

    # 4. Run B (tag="runB") with different LLM/extractor configuration executes without
    #    colliding with Run A's checkpoints or entity states
    pipe_b, ner_b, llm_b, acc_b = build_test_pipeline("runB", projection_graph=None)
    res_b = await pipe_b.run(PipelineInput(source_paths=[str(doc_path)]), run_id="run-B")
    assert res_b.manifest.status.value == "completed"
    assert len(ner_b.calls) >= 2  # Run B did not falsely skip chunks due to Run A's checkpoints
    assert any("[runB]" in (e.description or "") for e in acc_b.seen_chunk_entities)
    assert all("[runA]" not in (e.description or "") for e in acc_b.seen_chunk_entities)
