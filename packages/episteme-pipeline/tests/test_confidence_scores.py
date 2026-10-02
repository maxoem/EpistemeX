from __future__ import annotations

import pytest

from episteme_pipeline.config import Phase2Config, Phase3Config, Phase4Config
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, TheoryAtom, TheoryRelation
from episteme_pipeline.artifacts.models import TheoryAtomArtifact, EntityMentionArtifact, LinkedEntityArtifact
from episteme_pipeline.artifacts.builders import build_argument_component_artifact
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner


def test_domain_models_confidence_attributes():
    # Test L2Entity with and without confidence
    entity1 = L2Entity(id="e1", label="CONCEPT", name="Thermodynamics")
    assert entity1.confidence is None

    entity2 = L2Entity(id="e2", label="CONCEPT", name="Entropy", confidence=0.92)
    assert entity2.confidence == 0.92

    # Test TheoryAtom with and without confidence
    comp1 = TheoryAtom(id="ac1", text="Premise text", component_type="EMPIRICAL_OBSERVATION", source_chunk_id="c1")
    assert comp1.confidence is None

    comp2 = TheoryAtom(id="ac2", text="Claim text", component_type="ANTECEDENT", source_chunk_id="c1", confidence=0.88)
    assert comp2.confidence == 0.88


def test_artifact_models_and_builders_confidence():
    comp = TheoryAtom(id="ac1", text="Premise text", component_type="EMPIRICAL_OBSERVATION", source_chunk_id="c1", confidence=0.95)
    artifact = build_argument_component_artifact(
        comp, run_id="run-1", phase_name="phase4", method="test"
    )
    assert isinstance(artifact.payload, TheoryAtomArtifact)
    assert artifact.payload.confidence == 0.95


def test_phase_configs_confidence_threshold_defaults():
    # Phase2Config thresholds
    p2_cfg = Phase2Config()
    assert p2_cfg.ner_confidence_threshold == 0.0
    assert p2_cfg.local_relation_confidence_threshold == 0.0
    assert p2_cfg.linking_confidence_threshold == 0.85

    p2_custom = Phase2Config(linking_confidence_threshold=0.9, ner_confidence_threshold=0.8)
    assert p2_custom.linking_confidence_threshold == 0.9
    assert p2_custom.ner_confidence_threshold == 0.8

    # Phase3Config thresholds
    p3_cfg = Phase3Config()
    assert p3_cfg.global_relation_confidence_threshold == 0.7

    p3_custom = Phase3Config(global_relation_confidence_threshold=0.85)
    assert p3_custom.global_relation_confidence_threshold == 0.85

    # Phase4Config thresholds
    p4_cfg = Phase4Config()
    assert p4_cfg.adu_confidence_threshold == 0.0
    assert p4_cfg.acc_confidence_threshold == 0.0
    assert p4_cfg.arc_confidence_threshold == 0.65

    p4_custom = Phase4Config(acc_confidence_threshold=0.75, adu_confidence_threshold=0.8)
    assert p4_custom.acc_confidence_threshold == 0.75
    assert p4_custom.adu_confidence_threshold == 0.8


@pytest.mark.asyncio
async def test_phase2_runner_confidence_filtering():
    from unittest.mock import AsyncMock, MagicMock
    from episteme_pipeline.contracts.domain import L1Chunk
    from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

    graph_store = AsyncMock()
    graph_store.find_entities_by_name.return_value = []
    
    mock_extractor = AsyncMock()
    e1 = L2Entity(id="e1", label="CONCEPT", name="Entity Low", confidence=0.4)
    e2 = L2Entity(id="e2", label="CONCEPT", name="Entity High", confidence=0.9)
    t1 = L2Triple(subject_id="e1", predicate="RELATES", object_id="e2", confidence=0.3, scope="local")
    t2 = L2Triple(subject_id="e2", predicate="RELATES", object_id="e1", confidence=0.85, scope="local")

    mock_extractor.extract.return_value = ([e1, e2], [t1, t2], None, False, None)

    cfg = Phase2Config(
        ner_confidence_threshold=0.5,
        local_relation_confidence_threshold=0.5
    )
    runner = Phase2Runner(
        config=cfg,
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
        graph_store=graph_store,
        ner_extractor=mock_extractor,
    )

    chunk = L1Chunk(id="c1", text="Sample text", source_doc_id="d1", sequence_index=0, token_count=10)
    
    # Run _process_chunk
    res_entities, triples, _ = await runner._process_chunk(chunk)
    entities = [e for e, _ in res_entities]

    # Low confidence entity (0.4) and low confidence triple (0.3) should be filtered out
    assert len(entities) == 1
    assert entities[0].id == e2.id
    assert len(triples) == 1
    assert triples[0].confidence == 0.85


@pytest.mark.asyncio
async def test_phase4_runner_acc_confidence_filtering():
    from unittest.mock import AsyncMock, MagicMock
    from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

    graph_store = AsyncMock()
    
    cfg = Phase4Config(acc_confidence_threshold=0.7)
    runner = Phase4Runner(
        config=cfg,
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
        graph_store=graph_store,
    )

    c1 = TheoryAtom(id="ac1", text="Low confidence claim", component_type="ANTECEDENT", source_chunk_id="chk1", confidence=0.5)
    c2 = TheoryAtom(id="ac2", text="High confidence premise", component_type="EMPIRICAL_OBSERVATION", source_chunk_id="chk1", confidence=0.9)
    
    mock_segmenter = AsyncMock()
    mock_segmenter.segment.return_value = ("<AC1>text</AC1>", ["ac1", "ac2"])
    runner._adu_segmenter_override = mock_segmenter

    mock_classifier = AsyncMock()
    mock_classifier.classify.return_value = ([c1, c2], [])
    runner._acc_classifier_override = mock_classifier

    components, _, _ = await runner._process_chunk("chk1", "Sample text")

    # c1 (0.5 < 0.7) should be filtered out, leaving only c2 (0.9 >= 0.7)
    assert len(components) == 1
    assert components[0].id == "ac2"
