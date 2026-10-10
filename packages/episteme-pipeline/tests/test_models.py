"""Tests for LLM output model validation (pure Pydantic, no I/O)."""

import pytest
from episteme_pipeline.phases.phase2_entity_discovery.models import (
    ExtractedEntity,
    ExtractedTriple,
    NERExtractionOutput,
)
from episteme_pipeline.phases.phase4_argument_mining.models import (
    ACCOutput,
    ARCRelationOutput,
    ExtractedComponent,
    ExtractedTheoryRelation,
)

# ---------------------------------------------------------------------------
# NERExtractionOutput
# ---------------------------------------------------------------------------


class TestNERExtractionOutput:
    def test_validate_references_keeps_valid_triples(self):
        entities = [
            ExtractedEntity(id="e1", label="PERSON", name="Kant", mention_quote="Kant"),
            ExtractedEntity(id="e2", label="KONZEPT", name="space", mention_quote="space"),
        ]
        triples = [ExtractedTriple(subject_id="e1", predicate="IMPLIZIERT", object_id="e2")]
        output = NERExtractionOutput(entities=entities, triples=triples)
        validated = output.validate_references()
        assert len(validated.triples) == 1

    def test_validate_references_drops_orphan_triples(self):
        entities = [ExtractedEntity(id="e1", label="PERSON", name="Kant", mention_quote="Kant")]
        triples = [
            ExtractedTriple(subject_id="e1", predicate="IMPLIZIERT", object_id="e99"),  # e99 missing
        ]
        output = NERExtractionOutput(entities=entities, triples=triples)
        validated = output.validate_references()
        assert len(validated.triples) == 0

    def test_validate_references_drops_triple_with_missing_subject(self):
        entities = [ExtractedEntity(id="e2", label="KONZEPT", name="space", mention_quote="space")]
        triples = [ExtractedTriple(subject_id="e99", predicate="IMPLIZIERT", object_id="e2")]
        output = NERExtractionOutput(entities=entities, triples=triples)
        validated = output.validate_references()
        assert len(validated.triples) == 0

    def test_validate_references_empty_output(self):
        output = NERExtractionOutput(entities=[], triples=[])
        validated = output.validate_references()
        assert validated.entities == []
        assert validated.triples == []

    def test_confidence_clamped_below_zero(self):
        t = ExtractedTriple(subject_id="e1", predicate="X", object_id="e2", confidence=-1.0)
        assert t.confidence == 0.0

    def test_confidence_clamped_above_one(self):
        t = ExtractedTriple(subject_id="e1", predicate="X", object_id="e2", confidence=5.0)
        assert t.confidence == 1.0

    def test_entity_name_stripped(self):
        e = ExtractedEntity(id="e1", label="PERSON", name="  Kant  ", mention_quote="Kant")
        assert e.name == "Kant"

    def test_entity_empty_name_raises(self):
        with pytest.raises(Exception):
            ExtractedEntity(id="e1", label="PERSON", name="   ", mention_quote="Kant")


# ---------------------------------------------------------------------------
# ACCOutput
# ---------------------------------------------------------------------------


class TestACCOutput:
    def test_validate_references_keeps_valid_relations(self):
        components = [
            ExtractedComponent(id="AC1", component_type="ANTECEDENT", text="Space is a priori."),
            ExtractedComponent(id="AC2", component_type="EMPIRICAL_OBSERVATION", text="Kant said so."),
        ]
        relations = [ExtractedTheoryRelation(source_id="AC2", relation="SUPPORTS", target_id="AC1")]
        output = ACCOutput(components=components, relations=relations)
        validated = output.validate_references()
        assert len(validated.relations) == 1

    def test_validate_references_drops_orphan_relations(self):
        components = [ExtractedComponent(id="AC1", component_type="ANTECEDENT", text="Claim.")]
        relations = [ExtractedTheoryRelation(source_id="AC1", relation="SUPPORTS", target_id="AC99")]
        output = ACCOutput(components=components, relations=relations)
        validated = output.validate_references()
        assert len(validated.relations) == 0

    def test_empty_acc_output(self):
        output = ACCOutput()
        validated = output.validate_references()
        assert validated.components == []
        assert validated.relations == []

    def test_extracted_component_text_stripped(self):
        c = ExtractedComponent(id="AC1", component_type="ANTECEDENT", text="  hello  ")
        assert c.text == "hello"

    def test_extracted_component_empty_text_raises(self):
        with pytest.raises(Exception):
            ExtractedComponent(id="AC1", component_type="ANTECEDENT", text="  ")

    def test_extracted_argument_relation_accepts_any_string(self):
        # After the schema-decoupling fix, relation is str — no Literal constraint
        r = ExtractedTheoryRelation(source_id="AC1", relation="CUSTOM_REL", target_id="AC2")
        assert r.relation == "CUSTOM_REL"

    def test_arc_relation_output_accepts_any_string(self):
        r = ARCRelationOutput(relation_type="MY_CUSTOM_TYPE", confidence=0.8)
        assert r.relation_type == "MY_CUSTOM_TYPE"

    def test_arc_relation_output_none_relation(self):
        r = ARCRelationOutput()
        assert r.relation_type is None
