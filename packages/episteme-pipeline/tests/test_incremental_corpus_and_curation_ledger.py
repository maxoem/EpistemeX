"""Deterministic unit and integration tests for ISSUE-057.

Verifies:
1. RunManifest tracks per-document SHA-256 fingerprints (document_fingerprints).
2. Incremental corpus evolution: Phase 1, Phase 2, and local Phase 4 artifacts
   for unchanged documents are hydrated without redundant re-processing when ΔD
   is added to PipelineInput.
3. EpistemicCurationLedger contracts, serialization, and disk persistence.
4. EpistemicCurationLedger hard constraints in Phase 2 linking and Phase 3b consolidation
   (must-link and cannot-link).
5. EpistemicCurationLedger relation and polarity overrides in Phase 3, Phase 4, and Phase 6.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from unittest.mock import AsyncMock

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_chunk_artifact,
    build_document_artifact,
    build_entity_mention_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import (
    Phase1Config,
    Phase2Config,
    Phase3Config,
    Phase3bConfig,
    Phase4Config,
    Phase6Config,
    PipelineConfig,
)
from episteme_pipeline.contracts.domain import (
    CandidatePair,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    PhaseItemRecord,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import (
    EpistemicCurationLedger,
    PipelineInput,
    RelationOverride,
)
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase1_foundation.provenance import doc_id
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
from episteme_pipeline.phases.phase3b_consolidation.consolidation import LatentGraphConsolidation
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    EntityLinker,
    GlobalRelationExtractor,
    NERExtractor,
)
from episteme_pipeline.protocols.graph_store import FusionGraph
from episteme_pipeline.runs.fingerprints import (
    compute_document_fingerprints,
    fingerprint_curation_ledger,
    is_phase_unchanged,
)
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig


# ---------------------------------------------------------------------------
# Test Mocks & Stubs
# ---------------------------------------------------------------------------

class StubNERExtractor(NERExtractor):
    """Stub NER extractor recording invocations."""

    def __init__(self) -> None:
        self.extracted_chunk_ids: list[str] = []

    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: Any = None,
        anchor: Any = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict[str, Any] | None, bool, str | None]:
        self.extracted_chunk_ids.append(chunk_id)
        ent = L2Entity(
            id=f"e_{chunk_id}",
            label="Concept",
            name=f"ConceptFrom_{chunk_id}",
            textual_envelope=chunk_text,
            source_chunk_ids=[chunk_id],
        )
        triple = L2Triple(
            subject_id=f"e_{chunk_id}",
            predicate="RELATES_TO",
            object_id="e_universal",
            source_chunk_id=chunk_id,
            confidence=0.9,
            scope="local",
        )
        return [ent], [triple], None, False, None

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubNERExtractor"}


class StubEntityLinker(EntityLinker):
    """Stub EntityLinker supporting candidate returns."""

    def __init__(self, target_entity: L2Entity | None = None) -> None:
        self.target_entity = target_entity

    async def link(
        self,
        entity: L2Entity,
        graph_store: Any,
        top_k: int = 5,
        threshold: float = 0.85,
    ) -> L2Entity | None:
        return self.target_entity

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubEntityLinker"}


class StubEmbeddingModel(EmbeddingModel):
    """Deterministic embedding model returning unit vectors."""

    def __init__(self) -> None:
        pass

    async def aget_text_embedding(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubEmbeddingModel"}


class StubADUSegmenter:
    """Stub ADU Segmenter."""

    def __init__(self) -> None:
        self.segmented_chunk_ids: list[str] = []

    async def segment(self, chunk_id: str, chunk_text: str) -> tuple[str, list[str]]:
        self.segmented_chunk_ids.append(chunk_id)
        return f"<AC0>{chunk_text}</AC0>", [f"{chunk_id}_adu0"]

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubADUSegmenter"}


class StubACCClassifier:
    """Stub ACC Classifier."""

    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: Any = None,
        chunk_entities: list[L2Entity] | None = None,
        active_reader: Any = None,
        **kwargs: Any,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        atoms = [
            TheoryAtom(
                id=f"atom_{chunk_id}",
                text="Argument text",
                component_type="CLAIM",
                source_chunk_id=chunk_id,
                base_score=0.7,
                modal_strength=0.7,
            )
        ]
        relations = [
            TheoryRelation(
                source_id=f"atom_{chunk_id}",
                target_id="atom_target",
                relation_type="SUPPORTS",
                confidence=0.85,
                scope="local",
            )
        ]
        return atoms, relations

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubACCClassifier"}


class StubARCClassifier:
    """Stub ARC Classifier."""

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: Any,
        global_extractor: Any,
        schema: Any,
    ) -> list[TheoryRelation]:
        if len(local_components) >= 2:
            return [
                TheoryRelation(
                    source_id=local_components[0].id,
                    target_id=local_components[1].id,
                    relation_type="ATTACKS",
                    confidence=0.8,
                    scope="global",
                )
            ]
        return []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubARCClassifier"}


class StubGlobalRelationExtractor(GlobalRelationExtractor):
    """Stub GlobalRelationExtractor."""

    async def candidate_pairs(self, entities: list[L2Entity]) -> list[CandidatePair]:
        if len(entities) >= 2:
            return [
                CandidatePair(
                    entity_a=entities[0],
                    entity_b=entities[1],
                )
            ]
        return []

    async def extract_pairs(
        self, candidate_pairs: list[CandidatePair], graph_store: Any, schema: SchemaConfig
    ) -> tuple[list[L2Triple], list[PhaseItemRecord]]:
        triples = [
            L2Triple(
                subject_id=candidate_pairs[0].entity_a.id,
                predicate="INTERACTS_WITH",
                object_id=candidate_pairs[0].entity_b.id,
                confidence=0.88,
                scope="global",
            )
        ]
        records = [
            PhaseItemRecord(key=f"{c.entity_a.id}:{c.entity_b.id}", status="completed")
            for c in candidate_pairs
        ]
        return triples, records

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "StubGlobalRelationExtractor"}


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

def test_document_fingerprints_computation(tmp_path: Path) -> None:
    """Test compute_document_fingerprints produces stable SHA-256 hashes per document."""
    doc1 = tmp_path / "paper1.md"
    doc2 = tmp_path / "paper2.md"
    doc1.write_text("Foundational theory 1", encoding="utf-8")
    doc2.write_text("Foundational theory 2", encoding="utf-8")

    fps = compute_document_fingerprints([str(doc1), str(doc2)])
    d_id1 = doc_id(doc1)
    d_id2 = doc_id(doc2)

    assert d_id1 in fps
    assert d_id2 in fps
    assert len(fps[d_id1]) == 64  # SHA-256 hexadecimal string
    assert fps[d_id1] != fps[d_id2]
    # Check lookup by string path is also supported
    assert fps[str(doc1)] == fps[d_id1]


def test_epistemic_curation_ledger_contract_and_serialization(tmp_path: Path) -> None:
    """Test EpistemicCurationLedger Pydantic model serialization and file persistence."""
    ledger = EpistemicCurationLedger(
        must_link_entities={("e1", "e2"), ("Kant", "Immanuel Kant")},
        cannot_link_entities={("e1", "e3"), ("space", "time")},
        relation_overrides={
            "atom1::atom2": RelationOverride(
                source_id="atom1",
                target_id="atom2",
                relation_type="SUPPORTS",
                confidence=0.95,
            ),
            "atom3::atom4": RelationOverride(
                source_id="atom3",
                target_id="atom4",
                relation_type="REJECTED",
            ),
        },
        modality_overrides={"atom_thesis": 0.99},
    )

    # Verification of helper methods
    assert ledger.is_must_link("e1", "e2")
    assert ledger.is_must_link("e2", "e1")  # Symmetric
    assert ledger.is_must_link("other_id", "another_id", "Kant", "Immanuel Kant")
    assert not ledger.is_must_link("e1", "e3")

    assert ledger.is_cannot_link("e1", "e3")
    assert ledger.is_cannot_link("e3", "e1")  # Symmetric
    assert ledger.is_cannot_link("x", "y", "space", "time")
    assert not ledger.is_cannot_link("e1", "e2")

    override = ledger.get_relation_override("atom1", "atom2")
    assert override is not None
    assert override.relation_type == "SUPPORTS"
    assert override.confidence == 0.95

    rej_override = ledger.get_relation_override("atom3", "atom4")
    assert rej_override is not None
    assert rej_override.relation_type == "REJECTED"

    assert ledger.get_modality_override("atom_thesis") == 0.99
    assert ledger.get_modality_override("nonexistent") is None

    # Disk serialization and load_from_path
    ledger_path = tmp_path / "curation_ledger.json"
    ledger_path.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")

    loaded = EpistemicCurationLedger.load_from_path(ledger_path)
    assert loaded.is_must_link("e1", "e2")
    assert loaded.is_cannot_link("space", "time", "space", "time")
    assert loaded.get_modality_override("atom_thesis") == 0.99

    # PipelineInput resolved_curation_ledger resolution
    p_input = PipelineInput(source_paths=["p.md"], curation_ledger_path=ledger_path)
    resolved = p_input.resolved_curation_ledger()
    assert resolved is not None
    assert resolved.is_must_link("e1", "e2")


@pytest.mark.asyncio
async def test_phase1_incremental_corpus_hydration(tmp_path: Path) -> None:
    """Verify Phase 1 hydrates unchanged documents and only processes delta documents."""
    doc1 = tmp_path / "foundation.md"
    doc2 = tmp_path / "new_paper.md"
    doc1.write_text("# Chapter 1\nFoundational philosophy.", encoding="utf-8")
    doc2.write_text("# Chapter 1\nNewly added philosophy.", encoding="utf-8")

    d_id1 = doc_id(doc1)
    doc_fps = compute_document_fingerprints([str(doc1)])

    # Construct prior artifacts for doc1
    prior_doc = L1Document(id=d_id1, title="Foundation", source_path=str(doc1), chapter_count=1, chunk_count=1)
    prior_chunk = L1Chunk(id=f"chk_{d_id1}_0", text="Foundational philosophy.", source_doc_id=d_id1, sequence_index=0, token_count=3)
    prior_collection = ArtifactCollection([
        build_document_artifact(prior_doc, run_id="run-prior", phase_name="Phase 1: Data Foundation", method="m"),
        build_chunk_artifact(prior_chunk, run_id="run-prior", phase_name="Phase 1: Data Foundation", method="m"),
    ])

    prior_manifest = RunManifest(
        run_id="run-prior",
        status=RunStatus.COMPLETED,
        document_fingerprints=doc_fps,
        phase_config_fingerprints={"phase_1": "cfg_same"},
        method_fingerprints={},
    )

    current_manifest = RunManifest(
        run_id="run-current",
        document_fingerprints=compute_document_fingerprints([str(doc1), str(doc2)]),
        phase_config_fingerprints={"phase_1": "cfg_same"},
        method_fingerprints={},
    )

    ctx = ArtifactExecutionContext(
        run_id="run-current",
        manifest=current_manifest,
        pipeline_input=PipelineInput(source_paths=[str(doc1), str(doc2)]),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )

    runner = Phase1Runner(config=Phase1Config(chunk_size=100))
    # Execute Phase 1 on the combined corpus (D_t ∪ ΔD)
    output = await runner.run(ctx.pipeline_input, ctx)

    docs = [a.payload for a in output.of_kind(ArtifactKind.DOCUMENT)]
    chunks = [a.payload for a in output.of_kind(ArtifactKind.CHUNK)]

    # Both documents are in the output collection
    assert len(docs) == 2
    assert len(chunks) == 2
    # The artifact for doc1 was hydrated and tagged with current run_id
    doc1_art = next(a for a in output.of_kind(ArtifactKind.DOCUMENT) if a.payload.document_id == d_id1)
    assert doc1_art.run_id == "run-current"


@pytest.mark.asyncio
async def test_phase2_incremental_hydration_and_curation_constraints() -> None:
    """Verify Phase 2 hydrates unchanged chunk mentions and enforces cannot-link / must-link constraints."""
    # Chunk 1 (unchanged doc) and Chunk 2 (new document)
    chunk1 = L1Chunk(id="c1", text="Kant on space", source_doc_id="doc_unchanged", sequence_index=0, token_count=3)
    chunk2 = L1Chunk(id="c2", text="Leibniz on monads", source_doc_id="doc_new", sequence_index=1, token_count=3)

    prior_ent = L2Entity(id="e_kant", label="Concept", name="Kant", source_chunk_ids=["c1"])
    prior_collection = ArtifactCollection([
        build_entity_mention_artifact(prior_ent, "c1", run_id="run-prior", phase_name="Phase 2: Entity & Local Relation Discovery", method="m"),
        build_linked_entity_artifact(prior_ent, ["artifact::mention::e_kant::c1"], run_id="run-prior", phase_name="Phase 2: Entity & Local Relation Discovery", method="m"),
        build_local_relation_artifact(
            L2Triple(
                subject_id="e_kant",
                predicate="FOUNDED",
                object_id="e_idealism",
                source_chunk_id="c1",
                confidence=0.9,
                scope="local",
            ),
            run_id="run-prior",
            phase_name="Phase 2: Entity & Local Relation Discovery",
            method="m",
        ),
    ])

    prior_manifest = RunManifest(
        run_id="run-prior",
        status=RunStatus.COMPLETED,
        document_fingerprints={"doc_unchanged": "hash_same"},
        phase_config_fingerprints={"phase_2": "same"},
        method_fingerprints={},
    )
    current_manifest = RunManifest(
        run_id="run-current",
        document_fingerprints={"doc_unchanged": "hash_same", "doc_new": "hash_new"},
        phase_config_fingerprints={"phase_2": "same"},
        method_fingerprints={},
    )

    stub_ner = StubNERExtractor()
    stub_linker = StubEntityLinker(target_entity=prior_ent)

    # 1. Test cannot-link constraint prevents linking to prior_ent
    ledger_cannot = EpistemicCurationLedger(cannot_link_entities={("e_c2", "e_kant")})
    ctx = ArtifactExecutionContext(
        run_id="run-current",
        manifest=current_manifest,
        pipeline_input=PipelineInput(
            source_paths=["foundation.md", "new.md"],
            curation_ledger=ledger_cannot,
        ),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )

    view = Phase1ArtifactsView(chunks=[chunk1, chunk2], documents=[])
    runner = Phase2Runner(
        config=Phase2Config(),
        schema=DEFAULT_SCHEMA,
        llm=None,
        ner_extractor=stub_ner,
        entity_linker=stub_linker,
    )

    output = await runner.run(view, ctx)

    # c1 was hydrated, so stub_ner was called ONLY on c2!
    assert stub_ner.extracted_chunk_ids == ["c2"]

    entities = [a.payload.to_domain() for a in output.of_kind(ArtifactKind.LINKED_ENTITY)]
    # Due to cannot-link constraint, e_c2 was NOT merged into e_kant
    entity_ids = {e.id for e in entities}
    assert "e_kant" in entity_ids
    assert "e_c2" in entity_ids

    # 2. Test must-link constraint merges e_c2 into e_kant
    stub_ner.extracted_chunk_ids.clear()
    ledger_must = EpistemicCurationLedger(must_link_entities={("e_c2", "e_kant")})
    ctx_must = ArtifactExecutionContext(
        run_id="run-current-2",
        manifest=current_manifest,
        pipeline_input=PipelineInput(
            source_paths=["foundation.md", "new.md"],
            curation_ledger=ledger_must,
        ),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )
    output_must = await runner.run(view, ctx_must)
    entities_must = [a.payload.to_domain() for a in output_must.of_kind(ArtifactKind.LINKED_ENTITY)]
    assert len(entities_must) == 1
    assert entities_must[0].id == "e_kant"
    assert set(entities_must[0].source_chunk_ids) == {"c1", "c2"}


@pytest.mark.asyncio
async def test_phase3b_latent_consolidation_curation_constraints() -> None:
    """Verify Phase 3b Latent Graph Consolidation respects cannot-link and must-link constraints."""
    e1 = L2Entity(id="e_kant1", label="Concept", name="Kant", textual_envelope="Kant's philosophy")
    e2 = L2Entity(id="e_kant2", label="Concept", name="Immanuel Kant", textual_envelope="Kant's philosophy")

    from episteme_pipeline.contracts.domain import SubGraph
    reader = AsyncMock()
    reader.get_entities = AsyncMock(return_value=[e1, e2])
    reader.get_neighborhood = AsyncMock(return_value=SubGraph(center_id="e_kant1", depth=1, nodes=[], triples=[]))

    consolidation = LatentGraphConsolidation(
        embedding_model=StubEmbeddingModel(),
        dense_similarity_threshold=0.50,  # Vectors are identical [1,0,0], so normally merged
        relation_overlap_threshold=0.0,
    )

    # 1. Normal execution merges e_kant2 into e_kant1 (or canonical)
    normal_map = await consolidation.fuse(reader)
    assert len(normal_map) == 1

    # 2. Cannot-link constraint blocks the merge
    ledger_cannot = EpistemicCurationLedger(cannot_link_entities={("e_kant1", "e_kant2")})
    cannot_map = await consolidation.fuse(reader, curation_ledger=ledger_cannot)
    assert cannot_map == {}

    # 3. Must-link constraint forces merge even if similarity threshold is 0.99
    strict_consolidation = LatentGraphConsolidation(
        embedding_model=StubEmbeddingModel(),
        dense_similarity_threshold=0.99,
        relation_overlap_threshold=1.0,  # High threshold
    )
    ledger_must = EpistemicCurationLedger(must_link_entities={("e_kant1", "e_kant2")})
    must_map = await strict_consolidation.fuse(reader, curation_ledger=ledger_must)
    assert len(must_map) == 1


@pytest.mark.asyncio
async def test_phase3_and_phase4_relation_overrides() -> None:
    """Verify Phase 3 and Phase 4 enforce relation overrides and suppress rejected relations."""
    e1 = L2Entity(id="e1", label="Concept", name="Premise Concept", source_chunk_ids=["c1"])
    e2 = L2Entity(id="e2", label="Concept", name="Conclusion Concept", source_chunk_ids=["c1"])

    # Phase 3 with REJECTED override
    ledger_p3 = EpistemicCurationLedger(
        relation_overrides={
            "e1::e2": RelationOverride(
                source_id="e1",
                target_id="e2",
                relation_type="REJECTED",
            )
        }
    )
    p3_ctx = ArtifactExecutionContext(
        run_id="run-p3",
        manifest=RunManifest(run_id="run-p3"),
        pipeline_input=PipelineInput(source_paths=["p.md"], curation_ledger=ledger_p3),
    )
    p3_runner = Phase3Runner(
        config=Phase3Config(),
        schema=DEFAULT_SCHEMA,
        llm=None,
        embedding_model=StubEmbeddingModel(),
        global_extractor=StubGlobalRelationExtractor(),
    )
    p3_view = Phase2ArtifactsView(entities=[e1, e2], local_triples=[])
    p3_out = await p3_runner.run(p3_view, p3_ctx)
    p3_triples = p3_out.of_kind(ArtifactKind.GLOBAL_RELATION)
    # The candidate pair was extracted as INTERACTS_WITH, but suppressed by REJECTED override
    assert len(p3_triples) == 0

    # Phase 4 with polarity flip from ATTACKS to SUPPORTS
    ledger_p4 = EpistemicCurationLedger(
        relation_overrides={
            "atom_c1::atom_c2": RelationOverride(
                source_id="atom_c1",
                target_id="atom_c2",
                relation_type="SUPPORTS",
                confidence=0.99,
            )
        }
    )
    p4_ctx = ArtifactExecutionContext(
        run_id="run-p4",
        manifest=RunManifest(run_id="run-p4"),
        pipeline_input=PipelineInput(source_paths=["p.md"], curation_ledger=ledger_p4),
    )
    p4_runner = Phase4Runner(
        config=Phase4Config(),
        schema=DEFAULT_SCHEMA,
        llm=None,
        embedding_model=StubEmbeddingModel(),
        adu_segmenter=StubADUSegmenter(),
        acc_classifier=StubACCClassifier(),
        arc_classifier=StubARCClassifier(),  # Returns ATTACKS between atom_c1 and atom_c2
    )
    p4_view = Phase3ArtifactsView(
        chunks=[
            L1Chunk(id="c1", text="Text 1", source_doc_id="d1", sequence_index=0, token_count=2),
            L1Chunk(id="c2", text="Text 2", source_doc_id="d1", sequence_index=1, token_count=2),
        ],
        documents=[],
    )
    p4_out = await p4_runner.run(p4_view, p4_ctx)
    p4_rels = [a.payload.to_domain() for a in p4_out.of_kind(ArtifactKind.THEORY_RELATION)]
    rel_c1_c2 = next(r for r in p4_rels if r.from_id == "atom_c1" and r.to_id == "atom_c2")
    assert rel_c1_c2.relation_type == "SUPPORTS"
    assert rel_c1_c2.confidence == 0.99


@pytest.mark.asyncio
async def test_phase6_modality_overrides() -> None:
    """Verify Phase 6 locks human-adjudicated tau_0(a) priors via modality_overrides."""
    atom = TheoryAtom(
        id="atom_synthetic_apriori",
        text="Synthetic a priori knowledge is possible.",
        component_type="CLAIM",
        source_chunk_id="c1",
        base_score=0.40,
        modal_strength=0.40,
    )
    rel = TheoryRelation(
        source_id="atom_synthetic_apriori",
        target_id="atom_conclusion",
        relation_type="SUPPORTS",
        confidence=0.9,
        scope="local",
    )

    ledger = EpistemicCurationLedger(modality_overrides={"atom_synthetic_apriori": 0.95})
    ctx = ArtifactExecutionContext(
        run_id="run-p6",
        manifest=RunManifest(run_id="run-p6"),
        pipeline_input=PipelineInput(source_paths=["kant.md"], curation_ledger=ledger),
    )

    collection = ArtifactCollection([
        build_argument_component_artifact(atom, run_id="run-p6", phase_name="P4", method="m"),
        build_argument_relation_artifact(rel, run_id="run-p6", phase_name="P4", method="m"),
    ])
    p4_view = Phase4ArtifactsView.from_collection(collection)

    p6_runner = Phase6Runner(config=Phase6Config(), schema=DEFAULT_SCHEMA, graph_store=None)
    output = await p6_runner.run(p4_view, ctx)

    projected_atoms = [a.payload for a in output.of_kind(ArtifactKind.THEORY_ATOM)]
    projected_target = next(a for a in projected_atoms if a.component_id == "atom_synthetic_apriori")
    assert projected_target.modal_strength == 0.95
    assert projected_target.base_score == 0.95


@pytest.mark.asyncio
async def test_phase3_and_phase4_incremental_delta_hydration() -> None:
    """Verify Phase 3 delta-frontier filtering and Phase 4 unchanged-chunk hydration."""
    from episteme_pipeline.artifacts.builders import build_global_relation_artifact

    c1 = L1Chunk(id="c1", text="Doc 1 text", source_doc_id="doc_unchanged", sequence_index=0, token_count=3)
    c2 = L1Chunk(id="c2", text="Doc 2 text", source_doc_id="doc_new", sequence_index=0, token_count=3)

    e1 = L2Entity(id="e1", label="Concept", name="E1", source_chunk_ids=["c1"])
    e2 = L2Entity(id="e2", label="Concept", name="E2", source_chunk_ids=["c1"])
    e3 = L2Entity(id="e3", label="Concept", name="E3", source_chunk_ids=["c2"])

    prior_global_triple = L2Triple(
        subject_id="e1",
        predicate="PRIOR_REL",
        object_id="e2",
        confidence=0.91,
        scope="global",
    )
    prior_atom = TheoryAtom(
        id="atom_c1",
        text="Prior argument",
        component_type="CLAIM",
        source_chunk_id="c1",
        base_score=0.7,
        modal_strength=0.7,
    )
    prior_collection = ArtifactCollection([
        build_global_relation_artifact(
            prior_global_triple,
            {"PRIOR_REL": 1},
            run_id="run-prior",
            phase_name="Phase 3: Global Relation Extraction",
            method="m",
        ),
        build_argument_component_artifact(
            prior_atom,
            run_id="run-prior",
            phase_name="Phase 4: Argument Mining",
            method="m",
        ),
    ])

    prior_manifest = RunManifest(
        run_id="run-prior",
        status=RunStatus.COMPLETED,
        document_fingerprints={"doc_unchanged": "hash_same"},
        phase_config_fingerprints={"phase_3": "same", "phase_4": "same"},
        method_fingerprints={},
    )
    current_manifest = RunManifest(
        run_id="run-current",
        document_fingerprints={"doc_unchanged": "hash_same", "doc_new": "hash_new"},
        phase_config_fingerprints={"phase_3": "same", "phase_4": "same"},
        method_fingerprints={},
    )
    ctx = ArtifactExecutionContext(
        run_id="run-current",
        manifest=current_manifest,
        pipeline_input=PipelineInput(source_paths=["d1.md", "d2.md"]),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )

    class AllPairsGlobalExtractor(GlobalRelationExtractor):
        def __init__(self) -> None:
            self.extracted_pairs: list[tuple[str, str]] = []

        async def candidate_pairs(self, entities: list[L2Entity]) -> list[CandidatePair]:
            pairs: list[CandidatePair] = []
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    pairs.append(CandidatePair(entity_a=entities[i], entity_b=entities[j]))
            return pairs

        async def extract_pairs(
            self, candidate_pairs: list[CandidatePair], graph_store: Any, schema: SchemaConfig
        ) -> tuple[list[L2Triple], list[PhaseItemRecord]]:
            self.extracted_pairs.extend((c.entity_a.id, c.entity_b.id) for c in candidate_pairs)
            triples = [
                L2Triple(
                    subject_id=c.entity_a.id,
                    predicate="DELTA_REL",
                    object_id=c.entity_b.id,
                    confidence=0.85,
                    scope="global",
                )
                for c in candidate_pairs
            ]
            records = [PhaseItemRecord(key=c.key, status="completed") for c in candidate_pairs]
            return triples, records

        def fingerprint(self) -> dict[str, Any]:
            return {"class": "AllPairsGlobalExtractor"}

    extractor = AllPairsGlobalExtractor()
    p3_runner = Phase3Runner(
        config=Phase3Config(),
        schema=DEFAULT_SCHEMA,
        llm=None,
        embedding_model=StubEmbeddingModel(),
        global_extractor=extractor,
    )
    p2_view = Phase2ArtifactsView(chunks=[c1, c2], entities=[e1, e2, e3], local_triples=[])
    p3_out = await p3_runner.run(p2_view, ctx)

    # (e1, e2) is in E_prior x E_prior so it was NOT re-evaluated; only pairs involving e3 were evaluated!
    assert ("e1", "e2") not in extractor.extracted_pairs
    assert set(extractor.extracted_pairs) == {("e1", "e3"), ("e2", "e3")}
    global_triples = [a.payload.to_domain() for a in p3_out.of_kind(ArtifactKind.GLOBAL_RELATION)]
    assert any(t.subject_id == "e1" and t.object_id == "e2" and t.predicate == "PRIOR_REL" for t in global_triples)

    # Phase 4 incremental chunk hydration: c1 is skipped by ADUSegmenter, only c2 is segmented
    stub_segmenter = StubADUSegmenter()
    p4_runner = Phase4Runner(
        config=Phase4Config(),
        schema=DEFAULT_SCHEMA,
        llm=None,
        embedding_model=StubEmbeddingModel(),
        adu_segmenter=stub_segmenter,
        acc_classifier=StubACCClassifier(),
        arc_classifier=StubARCClassifier(),
    )
    p3_view = Phase3ArtifactsView(chunks=[c1, c2], documents=[])
    p4_out = await p4_runner.run(p3_view, ctx)
    assert stub_segmenter.segmented_chunk_ids == ["c2"]
    atoms = [a.payload.to_domain() for a in p4_out.of_kind(ArtifactKind.THEORY_ATOM)]
    assert {a.id for a in atoms} == {"atom_c1", "atom_c2"}


@pytest.mark.asyncio
async def test_phase3_multi_chunk_lost_evidence_invalidation() -> None:
    """Verify that an entity losing evidence from a modified chunk is not marked prior-only in Phase 3."""
    chunk_a = L1Chunk(id="chunk_a", text="Doc A text", source_doc_id="doc_unchanged", sequence_index=0, token_count=3)
    chunk_b_v2 = L1Chunk(id="chunk_b_v2", text="Doc B v2 text", source_doc_id="doc_modified", sequence_index=0, token_count=3)

    # Prior entity e1 was supported by both chunk_a (unchanged) and chunk_b_v1 (modified)
    prior_e1 = L2Entity(id="e1", label="Concept", name="E1", source_chunk_ids=["chunk_a", "chunk_b_v1"])
    # Prior entity e2 was supported exclusively by chunk_a
    prior_e2 = L2Entity(id="e2", label="Concept", name="E2", source_chunk_ids=["chunk_a"])

    prior_triple = L2Triple(
        subject_id="e1",
        predicate="PRIOR_REL",
        object_id="e2",
        confidence=0.90,
        scope="global",
    )

    prior_collection = ArtifactCollection([
        build_linked_entity_artifact(prior_e1, [], run_id="run-prior", phase_name="P2", method="m"),
        build_linked_entity_artifact(prior_e2, [], run_id="run-prior", phase_name="P2", method="m"),
        build_global_relation_artifact(
            prior_triple,
            {"PRIOR_REL": 1},
            run_id="run-prior",
            phase_name="Phase 3: Global Relation Extraction",
            method="m",
        ),
    ])

    prior_manifest = RunManifest(
        run_id="run-prior",
        status=RunStatus.COMPLETED,
        document_fingerprints={"doc_unchanged": "hash_same", "doc_modified": "hash_v1"},
        phase_config_fingerprints={"phase_3": "same"},
        method_fingerprints={},
    )
    current_manifest = RunManifest(
        run_id="run-current",
        document_fingerprints={"doc_unchanged": "hash_same", "doc_modified": "hash_v2"},
        phase_config_fingerprints={"phase_3": "same"},
        method_fingerprints={},
    )
    ctx = ArtifactExecutionContext(
        run_id="run-current",
        manifest=current_manifest,
        pipeline_input=PipelineInput(source_paths=["a.md", "b.md"]),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )

    # In current run, e1 lost mentions in modified Doc B, so it only has chunk_a
    current_e1 = L2Entity(id="e1", label="Concept", name="E1", source_chunk_ids=["chunk_a"])
    current_e2 = L2Entity(id="e2", label="Concept", name="E2", source_chunk_ids=["chunk_a"])

    class RecordingGlobalExtractor(GlobalRelationExtractor):
        def __init__(self) -> None:
            self.extracted_pairs: list[tuple[str, str]] = []

        async def candidate_pairs(self, entities: list[L2Entity]) -> list[CandidatePair]:
            return [CandidatePair(entity_a=entities[0], entity_b=entities[1])]

        async def extract_pairs(
            self, candidate_pairs: list[CandidatePair], graph_store: Any, schema: SchemaConfig
        ) -> tuple[list[L2Triple], list[PhaseItemRecord]]:
            self.extracted_pairs.extend((c.entity_a.id, c.entity_b.id) for c in candidate_pairs)
            triples = [
                L2Triple(
                    subject_id=c.entity_a.id,
                    predicate="NEW_REL",
                    object_id=c.entity_b.id,
                    confidence=0.95,
                    scope="global",
                )
                for c in candidate_pairs
            ]
            records = [PhaseItemRecord(key=c.key, status="completed") for c in candidate_pairs]
            return triples, records

        def fingerprint(self) -> dict[str, Any]:
            return {"class": "RecordingGlobalExtractor"}

    extractor = RecordingGlobalExtractor()
    p3_runner = Phase3Runner(
        config=Phase3Config(),
        schema=DEFAULT_SCHEMA,
        llm=None,
        embedding_model=StubEmbeddingModel(),
        global_extractor=extractor,
    )
    p2_view = Phase2ArtifactsView(chunks=[chunk_a, chunk_b_v2], entities=[current_e1, current_e2], local_triples=[])
    await p3_runner.run(p2_view, ctx)

    # Because e1 lost chunk_b_v1, e1 is NOT prior-only. (e1, e2) MUST be re-extracted!
    assert ("e1", "e2") in extractor.extracted_pairs


def test_curation_ledger_multi_predicate_override_collision() -> None:
    """Verify that multiple predicate edges between the same pair collapse to a single overridden triple."""
    t1 = L2Triple(subject_id="E1", predicate="RELATES_TO", object_id="E2", confidence=0.8, scope="global")
    t2 = L2Triple(subject_id="E1", predicate="MENTIONS", object_id="E2", confidence=0.7, scope="global")
    t3 = L2Triple(subject_id="E2", predicate="PART_OF", object_id="E3", confidence=0.9, scope="global")

    ledger = EpistemicCurationLedger(
        relation_overrides={
            "E1::E2": RelationOverride(
                source_id="E1",
                target_id="E2",
                relation_type="SUPPORTS",
                confidence=0.99,
            )
        }
    )

    filtered = ledger.apply_to_triples([t1, t2, t3], valid_entity_ids={"E1", "E2", "E3"})

    assert len(filtered) == 2
    e1_e2_triples = [t for t in filtered if t.subject_id == "E1" and t.object_id == "E2"]
    assert len(e1_e2_triples) == 1
    assert e1_e2_triples[0].predicate == "SUPPORTS"
    assert e1_e2_triples[0].confidence == 0.99

    e2_e3_triples = [t for t in filtered if t.subject_id == "E2" and t.object_id == "E3"]
    assert len(e2_e3_triples) == 1
    assert e2_e3_triples[0].predicate == "PART_OF"
    assert e2_e3_triples[0].confidence == 0.9


def test_curation_ledger_theory_relation_revalidation() -> None:
    """Verify that overriding TheoryRelation revalidates effective_weight and epistemic polarity."""
    rel = TheoryRelation(
        source_id="A1",
        target_id="A2",
        relation_type="SUPPORTS",
        confidence=0.85,
        scope="local",
        weight=0.85,
        weight_support=0.85,
    )
    assert rel.polarity == 1

    ledger = EpistemicCurationLedger(
        relation_overrides={
            "A1::A2": RelationOverride(
                source_id="A1",
                target_id="A2",
                relation_type="ATTACKS",
                confidence=0.95,
            )
        }
    )

    updated_rels = ledger.apply_to_theory_relations([rel], valid_atom_ids={"A1", "A2"})
    assert len(updated_rels) == 1
    updated = updated_rels[0]

    assert updated.relation_type == "ATTACKS"
    assert updated.confidence == 0.95
    assert updated.effective_weight == 0.95
    assert updated.active_weight == 0.95
    assert updated.polarity == -1
    assert updated.weight_support is None
    assert updated.weight_attack is None
    assert "inferential_force" not in updated.model_fields_set


