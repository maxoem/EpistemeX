"""Unit tests for Phase 4 Argument Mining classifiers and resolution factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
    CascadingACCClassifier,
    CascadingARCClassifier,
    JevACCClassifier,
    JevARCClassifier,
    _extract_adu_text,
)
from episteme_pipeline.protocols.argument_mining import ACCClassifier, ARCClassifier
from episteme_pipeline.protocols.decision import DecisionNoulResult, DecisionScore
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


def test_extract_adu_text() -> None:
    """Verify ADU text span extraction from tagged text."""
    tagged = "Here is intro. <AC1>Kant argued for synthetic a priori judgments.</AC1> Followed by text."
    assert _extract_adu_text(tagged, "AC1") == "Kant argued for synthetic a priori judgments."
    assert _extract_adu_text(tagged, "AC2") == "[AC2]"


@pytest.mark.asyncio
async def test_jev_acc_classifier() -> None:
    """Verify JevACCClassifier evaluates choice and extracts valid TheoryAtoms."""
    mock_engine = MagicMock()
    mock_engine.evaluate_choice = AsyncMock(
        return_value=DecisionScore(
            selected_option="TheoreticalHypothesis",
            class_probability=0.92,
            empirical_accuracy=0.90,
        )
    )

    classifier = JevACCClassifier(mock_engine)
    tagged = "<AC1>The mind constructs reality.</AC1>"
    atoms, rels = await classifier.classify(
        chunk_id="chunk_1",
        tagged_text=tagged,
        adu_ids=["AC1"],
        schema=DEFAULT_SCHEMA,
    )

    assert len(atoms) == 1
    assert atoms[0].text == "The mind constructs reality."
    assert atoms[0].component_type == "TheoreticalHypothesis"
    assert atoms[0].confidence == 0.92
    assert atoms[0].plausibility == 0.90
    assert rels == []


@pytest.mark.asyncio
async def test_cascading_acc_classifier_escalation() -> None:
    """Verify CascadingACCClassifier escalates to LLM when confidence is below threshold."""
    fast_acc = MagicMock(spec=ACCClassifier)
    # Return low confidence atom
    fast_acc.classify = AsyncMock(
        return_value=(
            [
                TheoryAtom(
                    id="ac_1",
                    text="Some claim",
                    component_type="CLAIM",
                    source_chunk_id="chunk_1",
                    confidence=0.50,  # below 0.85 threshold
                )
            ],
            [],
        )
    )

    llm_acc = MagicMock(spec=ACCClassifier)
    llm_acc.classify = AsyncMock(
        return_value=(
            [
                TheoryAtom(
                    id="ac_1",
                    text="Some claim",
                    component_type="MAJOR_CLAIM",
                    source_chunk_id="chunk_1",
                    confidence=0.95,
                )
            ],
            [
                TheoryRelation(
                    source_id="ac_1",
                    target_id="ac_2",
                    relation_type="SUPPORTS",
                    confidence=0.90,
                    scope="local",
                )
            ],
        )
    )

    config = Phase4Config(triage_confidence_threshold=0.85, stochastic_audit_rate=0.0)
    cascade = CascadingACCClassifier(fast_acc, llm_acc, config)

    atoms, rels = await cascade.classify(
        chunk_id="chunk_1",
        tagged_text="<AC1>Some claim</AC1>",
        adu_ids=["AC1"],
        schema=DEFAULT_SCHEMA,
    )

    # Should have escalated to LLM
    assert llm_acc.classify.called
    assert atoms[0].component_type == "MAJOR_CLAIM"
    assert len(rels) == 1


@pytest.mark.asyncio
async def test_jev_arc_classifier_classify_global() -> None:
    """Verify JevARCClassifier implements classify_global and returns relations."""
    mock_engine = MagicMock()
    mock_engine.evaluate_choice = AsyncMock(
        return_value=DecisionScore(
            selected_option="SUPPORTS_ARG",
            class_probability=0.88,
            empirical_accuracy=0.85,
        )
    )

    classifier = JevARCClassifier(mock_engine, confidence_threshold=0.60)
    atom_a = TheoryAtom(
        id="ac_a",
        text="Premise A",
        component_type="PREMISE",
        source_chunk_id="chunk_1",
    )
    atom_b = TheoryAtom(
        id="ac_b",
        text="Claim B",
        component_type="CLAIM",
        source_chunk_id="chunk_2",
    )

    rels = await classifier.classify_global(
        local_components=[atom_a, atom_b],
        local_relations=[],
        graph_store=MagicMock(),
        global_extractor=MagicMock(),
        schema=DEFAULT_SCHEMA,
    )

    assert len(rels) == 1
    assert rels[0].source_id == "ac_a"
    assert rels[0].target_id == "ac_b"
    assert rels[0].relation_type == "SUPPORTS_ARG"
    assert rels[0].confidence == 0.88


@pytest.mark.asyncio
async def test_cascading_arc_classifier() -> None:
    """Verify CascadingARCClassifier falls back to LLM when fast classifier predicts no relations."""
    fast_arc = MagicMock(spec=ARCClassifier)
    fast_arc.classify_global = AsyncMock(return_value=[])

    llm_arc = MagicMock(spec=ARCClassifier)
    llm_rel = TheoryRelation(
        source_id="ac_a", target_id="ac_b", relation_type="ATTACKS", confidence=0.85, scope="global"
    )
    llm_arc.classify_global = AsyncMock(return_value=[llm_rel])

    config = Phase4Config(stochastic_audit_rate=0.0)
    cascade = CascadingARCClassifier(fast_arc, llm_arc, config)

    result = await cascade.classify_global(
        local_components=[],
        local_relations=[],
        graph_store=MagicMock(),
        global_extractor=MagicMock(),
        schema=DEFAULT_SCHEMA,
    )

    assert len(result) == 1
    assert result[0].relation_type == "ATTACKS"
    assert llm_arc.classify_global.called




def test_jev_acc_classifier_prompt_handling() -> None:
    """Verify JevACCClassifier prompt resolution and validation."""
    from episteme_pipeline.prompts.default_prompts import DECISION_ACC_QUESTION
    from episteme_pipeline.prompts.models import StructuredPromptBundle

    mock_engine = MagicMock()
    # 1. Default prompt
    acc = JevACCClassifier(mock_engine)
    assert acc.decision_template == DECISION_ACC_QUESTION.strip()

    # 2. Custom prompt bundle
    bundle = StructuredPromptBundle(
        direct_template="Direct",
        decision_template="Custom ACC question?",
    )
    acc_custom = JevACCClassifier(mock_engine, prompts=bundle)
    assert acc_custom.decision_template == "Custom ACC question?"

    # 3. Missing/empty prompt raises ValueError
    empty_bundle = StructuredPromptBundle(direct_template="Direct", decision_template="")
    with pytest.raises(ValueError, match="No decision prompt configured for JevACCClassifier"):
        JevACCClassifier(mock_engine, prompts=empty_bundle)


def test_jev_arc_classifier_prompt_handling() -> None:
    """Verify JevARCClassifier prompt resolution and validation."""
    from episteme_pipeline.prompts.default_prompts import DECISION_ARC_QUESTION
    from episteme_pipeline.prompts.models import StructuredPromptBundle

    mock_engine = MagicMock()
    # 1. Default prompt
    arc = JevARCClassifier(mock_engine)
    assert arc.decision_template == DECISION_ARC_QUESTION.strip()

    # 2. Custom prompt bundle
    bundle = StructuredPromptBundle(
        direct_template="Direct",
        decision_template="Custom ARC question?",
    )
    arc_custom = JevARCClassifier(mock_engine, prompts=bundle)
    assert arc_custom.decision_template == "Custom ARC question?"

    # 3. Missing/empty prompt raises ValueError
    empty_bundle = StructuredPromptBundle(direct_template="Direct", decision_template="")
    with pytest.raises(ValueError, match="No decision prompt configured for JevARCClassifier"):
        JevARCClassifier(mock_engine, prompts=empty_bundle)




def test_phase4_runner_respects_user_overrides() -> None:
    """Verify Phase4Runner respects user-injected classifiers over decision_engine."""
    from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner

    mock_engine = MagicMock()
    custom_acc = MagicMock(spec=ACCClassifier)
    custom_arc = MagicMock(spec=ARCClassifier)

    config = Phase4Config(acc_mode="cascading", arc_mode="cascading")
    runner = Phase4Runner(
        config=config,
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
        graph_store=MagicMock(),
        acc_classifier=custom_acc,
        arc_classifier=custom_arc,
        decision_engine=mock_engine,
    )

    assert runner._acc_classifier_override is custom_acc
    assert runner.arc_classifier is custom_arc


@pytest.mark.asyncio
async def test_jev_arc_dynamic_schema() -> None:
    """Verify JevARCClassifier dynamically draws choice options and definitions from SchemaConfig."""
    from episteme_pipeline.schema.default_schema import SchemaConfig

    custom_schema = SchemaConfig(
        argument_relation_types=["ENTAILS", "CONTRADICTS_ARG"],
        argument_relation_definitions={
            "ENTAILS": "Source logically entails target",
            "CONTRADICTS_ARG": "Source contradicts target argument",
        },
    )

    mock_engine = MagicMock()
    captured_options = {}

    async def fake_evaluate_choice(state, question, options):
        nonlocal captured_options
        captured_options = options
        return DecisionScore(
            selected_option="ENTAILS",
            class_probability=0.95,
            empirical_accuracy=0.90,
        )

    mock_engine.evaluate_choice = AsyncMock(side_effect=fake_evaluate_choice)

    classifier = JevARCClassifier(mock_engine, confidence_threshold=0.7)
    atom_a = TheoryAtom(id="a", text="Premise", component_type="CLAIM", source_chunk_id="c1")
    atom_b = TheoryAtom(id="b", text="Conclusion", component_type="CLAIM", source_chunk_id="c2")

    rels = await classifier.classify_pair(atom_a, atom_b, custom_schema)

    assert "ENTAILS" in captured_options
    assert captured_options["ENTAILS"] == "Source logically entails target"
    assert "CONTRADICTS_ARG" in captured_options
    assert captured_options["CONTRADICTS_ARG"] == "Source contradicts target argument"
    assert "NEUTRAL" in captured_options
    # Should not have hardcoded relations that aren't in this schema
    assert "SUPPORTS" not in captured_options
    assert "ATTACKS" not in captured_options

    assert len(rels) == 1
    assert rels[0].relation_type == "ENTAILS"
    assert rels[0].confidence == 0.95


@pytest.mark.asyncio
async def test_jev_arc_multiplex_dynamic_schema() -> None:
    """Verify JevARCClassifier multiplex mode dynamically evaluates all schema relation types."""
    from episteme_pipeline.schema.default_schema import SchemaConfig

    custom_schema = SchemaConfig(
        argument_relation_types=["REDUCES_TO", "COHERES_WITH"],
        argument_relation_definitions={
            "REDUCES_TO": "Intertheoretical reduction",
            "COHERES_WITH": "Excitatory coherence",
        },
    )

    evaluated_questions = []

    async def fake_evaluate_noul(state, question):
        evaluated_questions.append(question)
        return DecisionNoulResult(passed=True, probability=0.90, empirical_accuracy=0.88)

    mock_engine = MagicMock()
    mock_engine.evaluate_noul = AsyncMock(side_effect=fake_evaluate_noul)

    classifier = JevARCClassifier(mock_engine, arc_mode="multiplex", confidence_threshold=0.7)
    atom_a = TheoryAtom(id="a", text="Theory A", component_type="TheoreticalHypothesis", source_chunk_id="c1")
    atom_b = TheoryAtom(id="b", text="Theory B", component_type="TheoreticalHypothesis", source_chunk_id="c2")

    rels = await classifier.classify_pair(atom_a, atom_b, custom_schema)

    assert len(evaluated_questions) == 2
    assert any("REDUCES_TO" in q for q in evaluated_questions)
    assert any("COHERES_WITH" in q for q in evaluated_questions)
    assert len(rels) == 2
    assert {r.relation_type for r in rels} == {"REDUCES_TO", "COHERES_WITH"}


def test_cascading_classifiers_direct_instantiation() -> None:
    """Verify CascadingACCClassifier and CascadingARCClassifier can be instantiated without Phase4Config."""
    fast_acc = MagicMock(spec=ACCClassifier)
    llm_acc = MagicMock(spec=ACCClassifier)
    cascade_acc = CascadingACCClassifier(
        fast_acc, llm_acc, triage_confidence_threshold=0.90, stochastic_audit_rate=0.05
    )
    assert cascade_acc.triage_confidence_threshold == 0.90
    assert cascade_acc.stochastic_audit_rate == 0.05

    fast_arc = MagicMock(spec=ARCClassifier)
    llm_arc = MagicMock(spec=ARCClassifier)
    cascade_arc = CascadingARCClassifier(fast_arc, llm_arc, stochastic_audit_rate=0.03)
    assert cascade_arc.stochastic_audit_rate == 0.03


