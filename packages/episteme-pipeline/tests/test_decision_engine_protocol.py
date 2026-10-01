"""Tests for DecisionEngine protocol, contract models, prompts, and pipeline wiring."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
import pytest
from pydantic import SecretStr

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
from episteme_pipeline.prompts.providers import DefaultPromptProvider, LangfusePromptProvider
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
    ensure_decision_engine,
)


class ConformingMockDecisionEngine:
    """Mock engine satisfying the DecisionEngine protocol."""

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
    from episteme_pipeline.pipeline import Pipeline
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM

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
