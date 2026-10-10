"""Tests for DecisionEngine protocol, contract models, prompts, and pipeline wiring."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from episteme_pipeline.config import DecisionEngineConfig, PipelineConfig
from episteme_pipeline.prompts.default_prompts import (
    ACC_DIRECT_PROMPT,
    ARC_DIRECT_PROMPT,
    DECISION_ACC_CRITERIA,
    DECISION_ACC_QUESTION,
    DECISION_ARC_CRITERIA,
    DECISION_ARC_QUESTION,
    DECISION_BOUNDARY_CRITERIA,
    DECISION_BOUNDARY_QUESTION,
    DECISION_EPISTEMIC_RELEVANCE_CRITERIA,
    DECISION_EPISTEMIC_RELEVANCE_QUESTION,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.prompts.providers import (
    DefaultPromptProvider,
    LangfusePromptProvider,
)
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionQuestion,
    DecisionScore,
    ensure_decision_engine,
    ensure_decision_question,
)


class ConformingMockDecisionEngine:
    """Mock engine satisfying the DecisionEngine protocol."""

    @property
    def name(self) -> str:
        """Return engine name."""
        return "ConformingMockDecisionEngine"

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate binary statement."""
        return DecisionNoulResult(
            probability=0.95,
            empirical_accuracy=0.92,
            passed=True,
        )

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate categorical choice."""
        selected = list(options)[0] if isinstance(options, (list, dict)) else "CLAIM"
        return DecisionScore(
            selected_option=selected,
            class_probability=0.88,
            empirical_accuracy=0.85,
            probabilities={selected: 0.88},
            prediction_set=[selected],
            tokens_saved_estimate=120,
        )

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate score levels."""
        return DecisionScore(
            selected_option=levels[0] if levels else 1,
            class_probability=0.75,
            empirical_accuracy=0.80,
            probabilities={},
            prediction_set=None,
        )

    async def evaluate(
        self,
        state: str | dict[str, Any] | list[Any],
        question: DecisionQuestion | dict[str, Any],
    ) -> DecisionScore | DecisionNoulResult:
        """Evaluate a single question."""
        return DecisionNoulResult(probability=0.95, empirical_accuracy=0.92, passed=True)

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, Any],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate batch questions."""
        return {}


class IncompleteMockDecisionEngine:
    """Mock missing evaluate_score method."""

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate binary statement."""
        return DecisionNoulResult(probability=0.5, empirical_accuracy=0.5, passed=True)

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate categorical choice."""
        return DecisionScore(
            selected_option="A",
            class_probability=0.5,
            empirical_accuracy=0.5,
        )


def test_decision_score_model_instantiation_and_validation() -> None:
    """Verify DecisionScore fields and serialization."""
    score = DecisionScore(
        selected_option="CLAIM",
        class_probability=0.92,
        empirical_accuracy=0.89,
        probabilities={"CLAIM": 0.92, "PREMISE": 0.08},
        prediction_set=["CLAIM"],
        tokens_saved_estimate=150,
    )
    assert score.selected_option == "CLAIM"
    assert score.class_probability == 0.92
    assert score.empirical_accuracy == 0.89
    assert score.tokens_saved_estimate == 150

    # Verify JSON round-trip
    dumped = score.model_dump(mode="json")
    assert dumped["selected_option"] == "CLAIM"
    assert json.loads(score.model_dump_json())["class_probability"] == 0.92


def test_decision_noul_result_model() -> None:
    """Verify DecisionNoulResult fields and serialization."""
    result = DecisionNoulResult(
        probability=0.96,
        empirical_accuracy=0.91,
        passed=True,
    )
    assert result.probability == 0.96
    assert result.empirical_accuracy == 0.91
    assert result.passed is True

    dumped = result.model_dump(mode="json")
    assert dumped["probability"] == 0.96
    assert dumped["passed"] is True


def test_decision_engine_protocol_conformance() -> None:
    """Verify runtime checkability of DecisionEngine protocol."""
    engine = ConformingMockDecisionEngine()
    assert isinstance(engine, DecisionEngine)

    incomplete = IncompleteMockDecisionEngine()
    assert not isinstance(incomplete, DecisionEngine)

    assert not isinstance("not_an_engine", DecisionEngine)
    assert not isinstance(123, DecisionEngine)


def test_ensure_decision_engine_normalizer() -> None:
    """Verify ensure_decision_engine normalizer behavior."""
    # None passes through cleanly
    assert ensure_decision_engine(None) is None

    # Conforming engine is passed through
    valid = ConformingMockDecisionEngine()
    assert ensure_decision_engine(valid) is valid

    # Incompatible objects raise TypeError
    with pytest.raises(TypeError, match="does not satisfy the DecisionEngine protocol"):
        ensure_decision_engine("invalid_string_engine")

    with pytest.raises(TypeError, match="does not satisfy the DecisionEngine protocol"):
        ensure_decision_engine(IncompleteMockDecisionEngine())


def test_structured_prompt_bundle_decision_fields() -> None:
    """Verify StructuredPromptBundle supports decision templates and criteria."""
    bundle = StructuredPromptBundle(
        direct_template=DECISION_ACC_QUESTION,
        decision_template=DECISION_ACC_QUESTION,
        decision_criteria=DECISION_ACC_CRITERIA,
        name="test_bundle",
    )
    assert bundle.direct_template == DECISION_ACC_QUESTION
    assert bundle.decision_template == DECISION_ACC_QUESTION
    assert bundle.decision_criteria == DECISION_ACC_CRITERIA

    dumped = bundle.model_dump(mode="json")
    assert dumped["direct_template"] == DECISION_ACC_QUESTION
    assert dumped["decision_template"] == DECISION_ACC_QUESTION
    assert dumped["decision_criteria"] == DECISION_ACC_CRITERIA


def test_default_prompt_provider_decision_bundles() -> None:
    """Verify DefaultPromptProvider serves registered decision prompts and aliases."""
    provider = DefaultPromptProvider()

    # Epistemic relevance (standalone decision prompt: direct_template contains question)
    bundle_relevance = provider.get_bundle("decision_epistemic_relevance")
    assert bundle_relevance.direct_template == DECISION_EPISTEMIC_RELEVANCE_QUESTION
    assert bundle_relevance.decision_criteria == DECISION_EPISTEMIC_RELEVANCE_CRITERIA

    # Alias check
    alias_bundle = provider.get_bundle("epistemic_relevance")
    assert alias_bundle.direct_template == DECISION_EPISTEMIC_RELEVANCE_QUESTION

    # Boundary standalone decision bundle
    bundle_boundary = provider.get_bundle("decision_boundary")
    assert bundle_boundary.direct_template == DECISION_BOUNDARY_QUESTION
    assert bundle_boundary.decision_criteria == DECISION_BOUNDARY_CRITERIA

    # Dual-process classification bundles carry direct LLM prompt + Jev decision question & criteria
    acc_bundle = provider.get_bundle("acc_classification")
    assert acc_bundle.direct_template == ACC_DIRECT_PROMPT
    assert acc_bundle.decision_template == DECISION_ACC_QUESTION
    assert acc_bundle.decision_criteria == DECISION_ACC_CRITERIA

    arc_bundle = provider.get_bundle("arc_classification")
    assert arc_bundle.direct_template == ARC_DIRECT_PROMPT
    assert arc_bundle.decision_template == DECISION_ARC_QUESTION
    assert arc_bundle.decision_criteria == DECISION_ARC_CRITERIA

    # get_template method returns direct_template cleanly
    assert provider.get_template("decision_epistemic_relevance") == DECISION_EPISTEMIC_RELEVANCE_QUESTION
    assert provider.get_template("decision_boundary") == DECISION_BOUNDARY_QUESTION
    assert provider.get_template("acc_classification") == ACC_DIRECT_PROMPT


def test_langfuse_prompt_provider_decision_bundle_fallback() -> None:
    """Verify LangfusePromptProvider handles decision prompts gracefully with fallback."""
    provider = LangfusePromptProvider(client=None)

    bundle = provider.get_bundle("acc_classification")
    assert bundle.decision_template == DECISION_ACC_QUESTION
    assert bundle.decision_criteria == DECISION_ACC_CRITERIA
    assert provider.get_template("acc_classification") == ACC_DIRECT_PROMPT

    # Check sync_defaults_to_langfuse default_names list includes decision prompts
    synced = provider.sync_defaults_to_langfuse()
    assert "decision_epistemic_relevance" in synced
    assert "acc_classification" in synced
    assert "arc_classification" in synced
    assert "decision_boundary" in synced


def test_decision_engine_config_and_pipeline_config() -> None:
    """Verify DecisionEngineConfig fields, defaults, and embedding in PipelineConfig."""
    # Default is None
    cfg = PipelineConfig()
    assert cfg.decision_engine is None

    # Config with DecisionEngineConfig
    dec_cfg = DecisionEngineConfig(
        provider="mock",
        timeout_seconds=3.5,
        default_confidence_threshold=0.90,
        conformal_alpha=0.01,
        stochastic_audit_rate=0.05,
        fallback_to_llm=False,
    )
    cfg2 = PipelineConfig(decision_engine=dec_cfg)
    assert cfg2.decision_engine is not None
    assert cfg2.decision_engine.provider == "mock"
    assert cfg2.decision_engine.timeout_seconds == 3.5
    assert cfg2.decision_engine.default_confidence_threshold == 0.90
    assert cfg2.decision_engine.conformal_alpha == 0.01
    assert cfg2.decision_engine.stochastic_audit_rate == 0.05
    assert cfg2.decision_engine.fallback_to_llm is False

    # Serialization test
    dumped = cfg2.model_dump(mode="json")
    assert dumped["decision_engine"]["provider"] == "mock"
    json_str = cfg2.model_dump_json()
    assert '"provider":"mock"' in json_str


@pytest.mark.asyncio
async def test_conforming_mock_decision_engine_execution() -> None:
    """Verify execution of ConformingMockDecisionEngine methods."""
    engine = ConformingMockDecisionEngine()

    noul = await engine.evaluate_noul("text snippet", "Is this valid?")
    assert noul.passed is True
    assert noul.probability == 0.95
    assert noul.empirical_accuracy == 0.92

    choice = await engine.evaluate_choice("text snippet", "Which type?", ["CLAIM", "PREMISE"])
    assert choice.selected_option == "CLAIM"
    assert choice.class_probability == 0.88
    assert choice.empirical_accuracy == 0.85
    assert choice.prediction_set == ["CLAIM"]

    score = await engine.evaluate_score("text snippet", "Rate confidence", [1, 2, 3, 4, 5])
    assert score.selected_option == 1
    assert score.class_probability == 0.75


def test_pipeline_for_task_decision_engine_injection() -> None:
    """Verify Pipeline.for_task accepts and stores decision_engine."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    from episteme_pipeline.pipeline import Pipeline

    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    mock_reranker = MagicMock()
    mock_embed = MagicMock()
    mock_reader = MagicMock()
    mock_proj = MagicMock()
    mock_ckpt = MagicMock()
    config = PipelineConfig()
    engine = ConformingMockDecisionEngine()

    # Pass conforming engine
    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=mock_reranker,
        cross_encoder=mock_reranker,
        embedding_model=mock_embed,
        config=config,
        graph_reader=mock_reader,
        projection_graph=mock_proj,
        checkpoint_store=mock_ckpt,
        decision_engine=engine,
    )
    from episteme_pipeline.decision.observable import ObservableDecisionEngine
    assert isinstance(pipeline.decision_engine, ObservableDecisionEngine)
    assert pipeline.decision_engine.inner is engine

    # Pass None (default behavior)
    pipeline_none = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=mock_reranker,
        cross_encoder=mock_reranker,
        embedding_model=mock_embed,
        config=config,
        graph_reader=mock_reader,
        projection_graph=mock_proj,
        checkpoint_store=mock_ckpt,
        decision_engine=None,
    )
    assert pipeline_none.decision_engine is None

    # Invalid engine raises TypeError
    with pytest.raises(TypeError, match="does not satisfy the DecisionEngine protocol"):
        Pipeline.for_task(
            llm=mock_llm,
            relation_reranker=mock_reranker,
            cross_encoder=mock_reranker,
            embedding_model=mock_embed,
            config=config,
            graph_reader=mock_reader,
            projection_graph=mock_proj,
            checkpoint_store=mock_ckpt,
            decision_engine="not_an_engine",
        )


def test_decision_question_model_and_normalizer() -> None:
    """Verify DecisionQuestion instantiation, from_bundle, and normalizer."""
    # Direct instantiation
    dq = DecisionQuestion(
        question="Is this claim valid?",
        type="choice",
        criteria=["VALID", "INVALID"],
        alpha=0.05,
    )
    assert dq.question == "Is this claim valid?"
    assert dq.type == "choice"
    assert dq.criteria == ["VALID", "INVALID"]
    assert dq.alpha == 0.05

    # ensure_decision_question idempotent on DecisionQuestion
    assert ensure_decision_question(dq) is dq

    # Normalization from legacy dict with 'instructions' and 'options'
    dict_choice = {"type": "choice", "instructions": "Pick one", "options": ["A", "B"]}
    norm_choice = ensure_decision_question(dict_choice)
    assert isinstance(norm_choice, DecisionQuestion)
    assert norm_choice.question == "Pick one"
    assert norm_choice.criteria == ["A", "B"]

    # Normalization from legacy dict with 'question' and 'levels'
    dict_score = {"type": "score", "question": "Rate level", "levels": [1, 2, 3]}
    norm_score = ensure_decision_question(dict_score)
    assert norm_score.question == "Rate level"
    assert norm_score.type == "score"
    assert norm_score.criteria == [1, 2, 3]

    # Error on invalid type
    with pytest.raises(TypeError, match="Expected DecisionQuestion or dict"):
        ensure_decision_question(12345)  # type: ignore[arg-type]


def test_decision_question_from_bundle() -> None:
    """Verify StructuredPromptBundle conversion to DecisionQuestion."""
    bundle = StructuredPromptBundle(
        direct_template="Extract mentions from: {text}",
        decision_template="Does the passage mention {target}?",
        decision_criteria={"YES": "Explicitly mentions", "NO": "Does not mention"},
    )

    # Conversion via from_bundle classmethod with kwargs formatting
    dq = DecisionQuestion.from_bundle(
        bundle=bundle,
        type="choice",
        format_kwargs={"target": "Kant"},
        alpha=0.01,
    )
    assert dq.question == "Does the passage mention Kant?"
    assert dq.type == "choice"
    assert dq.criteria == {"YES": "Explicitly mentions", "NO": "Does not mention"}
    assert dq.alpha == 0.01

    # Conversion via bundle.to_decision_question() instance method
    dq_method = bundle.to_decision_question(
        type="noul",
        format_kwargs={"target": "Hegel"},
    )
    assert dq_method.question == "Does the passage mention Hegel?"
    assert dq_method.type == "noul"


@pytest.mark.asyncio
async def test_mock_decision_engine_evaluate_batch_with_decision_questions() -> None:
    """Verify MockJevDecisionEngine evaluates typed DecisionQuestion instances."""
    from episteme_pipeline.decision.mock import MockJevDecisionEngine

    engine = MockJevDecisionEngine()
    batch = await engine.evaluate_batch(
        state="Kant claims that pure reason is synthetic a priori.",
        questions={
            "q1": DecisionQuestion(
                question="Is synthetic a priori asserted?",
                type="noul",
            ),
            "q2": DecisionQuestion(
                question="Classify claim status",
                type="choice",
                criteria=["CLAIM", "PREMISE"],
            ),
            "q3": DecisionQuestion(
                question="Rate clarity tier",
                type="score",
                criteria=[1, 2, 3],
            ),
        },
    )

    assert "q1" in batch
    assert "q2" in batch
    assert "q3" in batch
    assert isinstance(batch["q1"], DecisionNoulResult)
    assert isinstance(batch["q2"], DecisionScore)
    assert isinstance(batch["q3"], DecisionScore)


@pytest.mark.asyncio
async def test_decision_engine_evaluate_single_with_strategies() -> None:
    """Verify DecisionEngine.evaluate dispatches polymorphically via question strategies."""
    from episteme_pipeline.decision.mock import MockJevDecisionEngine

    engine = MockJevDecisionEngine()

    # 1. Noul single evaluation
    q_noul = DecisionQuestion(question="Is this claim valid?", type="noul")
    res_noul = await engine.evaluate("Some premise context", q_noul)
    assert isinstance(res_noul, DecisionNoulResult)
    assert res_noul.passed is True

    # 2. Choice single evaluation
    q_choice = DecisionQuestion(
        question="Classify role",
        type="choice",
        criteria=["PREMISE", "CONCLUSION"],
    )
    res_choice = await engine.evaluate("Some premise context", q_choice)
    assert isinstance(res_choice, DecisionScore)
    assert res_choice.selected_option == "PREMISE"

    # 3. Score single evaluation
    q_score = DecisionQuestion(
        question="Rate strength tier",
        type="score",
        criteria=[1, 2, 3],
    )
    res_score = await engine.evaluate("Some premise context", q_score)
    assert isinstance(res_score, DecisionScore)
    assert res_score.selected_option == 1


def test_question_strategy_registry_and_specs() -> None:
    """Verify question strategy registry, laya spec generation, and fallback."""
    from episteme_pipeline.decision.strategies import (
        ChoiceQuestionStrategy,
        NoulQuestionStrategy,
        ScoreQuestionStrategy,
        get_question_strategy,
    )

    noul_strat = get_question_strategy("noul")
    assert isinstance(noul_strat, NoulQuestionStrategy)
    noul_spec = noul_strat.to_laya_spec(DecisionQuestion(question="Is true?", type="noul"))
    assert noul_spec["type"] == "noul"
    assert noul_spec["instructions"] == "Is true?"

    choice_strat = get_question_strategy("choice")
    assert isinstance(choice_strat, ChoiceQuestionStrategy)
    choice_spec = choice_strat.to_laya_spec(
        DecisionQuestion(question="Pick", type="choice", criteria=["A", "B"])
    )
    assert choice_spec["type"] == "choice"
    assert choice_spec["criteria"] == ["A", "B"]

    score_strat = get_question_strategy("score")
    assert isinstance(score_strat, ScoreQuestionStrategy)
    score_spec = score_strat.to_laya_spec(
        DecisionQuestion(question="Rate", type="score", criteria=[1, 2, 3])
    )
    assert score_spec["type"] == "score"
    assert score_spec["criteria"] == ["1", "2", "3"]

    # Unknown modality falls back to ChoiceQuestionStrategy
    unknown_strat = get_question_strategy("custom_unknown")
    assert isinstance(unknown_strat, ChoiceQuestionStrategy)


