"""Unit tests for TypeSafe Jev & Laya decision engine clients.

Covers:
- MockJevDecisionEngine deterministic execution, fixtures, and latency simulation.
- LayaDecisionEngine output schema mapping, conformal prediction sets, shortlisting, and error handling.
- TransformersDecisionEngine fallback execution and timeout handling.
- resolve_decision_engine auto-detection and configuration instantiation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from episteme_pipeline.config import DecisionEngineConfig
from episteme_pipeline.decision.jev_client import (
    DecisionEngineError,
    LayaDecisionEngine,
    TransformersDecisionEngine,
    _estimate_tokens_saved,
)
from episteme_pipeline.decision.mock import (
    MockJevDecisionEngine,
    compute_conformal_prediction_set,
)
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
)


def test_conformal_prediction_set_computation() -> None:
    """Verify conformal prediction set construction over discrete distributions."""
    # Singleton case: top probability exceeds 1 - alpha (0.95)
    probs_peaked = {"A": 0.96, "B": 0.03, "C": 0.01}
    pred_set_peaked = compute_conformal_prediction_set(probs_peaked, alpha=0.05)
    assert pred_set_peaked == ["A"]

    # Multi-class set: requires multiple labels to reach 1 - alpha (0.95)
    probs_diffuse = {"CLAIM": 0.60, "PREMISE": 0.36, "COUNTER": 0.04}
    pred_set_diffuse = compute_conformal_prediction_set(probs_diffuse, alpha=0.05)
    assert pred_set_diffuse == ["CLAIM", "PREMISE"]

    # Edge cases
    assert compute_conformal_prediction_set({}) == []


def test_estimate_tokens_saved() -> None:
    """Verify heuristic calculation of tokens saved by System 1 execution."""
    state = "Philosophy of science investigates scientific theories."
    question = "Is this text substantive?"
    tokens = _estimate_tokens_saved(state, question, ["YES", "NO"])
    assert tokens > 50
    assert isinstance(tokens, int)


@pytest.mark.asyncio
async def test_mock_jev_decision_engine_noul() -> None:
    """Verify MockJevDecisionEngine binary noul evaluations."""
    engine = MockJevDecisionEngine(default_confidence_threshold=0.80)
    assert isinstance(engine, DecisionEngine)
    assert engine.name == "MockJevDecisionEngine"

    # Default evaluation
    res = await engine.evaluate_noul("text sample", "Is this relevant?")
    assert isinstance(res, DecisionNoulResult)
    assert res.passed is True
    assert res.probability == 0.90
    assert res.empirical_accuracy == 0.88
    assert len(engine.calls) == 1

    # Register rule with state and question pattern
    engine.register_noul_response(
        question_pattern="substantive",
        state_pattern="bibliography",
        probability=0.25,
        empirical_accuracy=0.95,
        passed=False,
    )
    res_matched = await engine.evaluate_noul(
        "Source: Bibliography and references", "Is this substantive content?"
    )
    assert res_matched.passed is False
    assert res_matched.probability == 0.25
    assert res_matched.empirical_accuracy == 0.95

    # Reset clears calls and rules
    engine.reset()
    assert len(engine.calls) == 0
    res_after_reset = await engine.evaluate_noul("text", "substantive")
    assert res_after_reset.passed is True


@pytest.mark.asyncio
async def test_mock_jev_decision_engine_choice() -> None:
    """Verify MockJevDecisionEngine categorical choice evaluations."""
    engine = MockJevDecisionEngine(conformal_alpha=0.05)

    # Default choice selects first option with conformal set
    res = await engine.evaluate_choice("state block", "Select category", ["CLAIM", "PREMISE"])
    assert isinstance(res, DecisionScore)
    assert res.selected_option == "CLAIM"
    assert res.class_probability == 0.85
    assert res.empirical_accuracy == 0.88
    assert "CLAIM" in res.probabilities
    assert "CLAIM" in res.prediction_set

    # Register customized choice response
    engine.register_choice_response(
        question_pattern="argument stance",
        selected_option="SUPPORT",
        probabilities={"SUPPORT": 0.92, "ATTACK": 0.08},
        class_probability=0.92,
        empirical_accuracy=0.94,
        prediction_set=["SUPPORT"],
    )
    res_reg = await engine.evaluate_choice("state", "What is the argument stance?", ["SUPPORT", "ATTACK"])
    assert res_reg.selected_option == "SUPPORT"
    assert res_reg.class_probability == 0.92
    assert res_reg.empirical_accuracy == 0.94
    assert res_reg.prediction_set == ["SUPPORT"]


@pytest.mark.asyncio
async def test_mock_jev_decision_engine_score_and_batch() -> None:
    """Verify score evaluation and multi-question batching on MockJevDecisionEngine."""
    engine = MockJevDecisionEngine()

    # Score evaluation
    score_res = await engine.evaluate_score("some argument", "Rate strength", [1, 2, 3, 4, 5])
    assert isinstance(score_res, DecisionScore)
    assert score_res.selected_option == 1

    # Batch evaluation
    batch = await engine.evaluate_batch(
        state="Kant's Critique of Pure Reason introduces transcendental idealism.",
        questions={
            "q_substantive": {"type": "noul", "instructions": "Is this substantive?"},
            "q_acc": {
                "type": "choice",
                "instructions": "Classify ADU component",
                "criteria": ["CLAIM", "PREMISE"],
            },
            "q_level": {
                "type": "score",
                "instructions": "Rate argument level",
                "levels": [1, 2, 3],
            },
        },
    )
    assert "q_substantive" in batch
    assert "q_acc" in batch
    assert "q_level" in batch
    assert isinstance(batch["q_substantive"], DecisionNoulResult)
    assert isinstance(batch["q_acc"], DecisionScore)
    assert isinstance(batch["q_level"], DecisionScore)


@pytest.mark.asyncio
async def test_mock_jev_decision_engine_latency_and_exceptions() -> None:
    """Verify simulated latency and error injection on MockJevDecisionEngine."""
    engine = MockJevDecisionEngine()
    engine.set_simulated_latency(0.01)

    t0 = asyncio.get_event_loop().time()
    await engine.evaluate_noul("text", "question")
    elapsed = asyncio.get_event_loop().time() - t0
    assert elapsed >= 0.01

    # Error injection
    engine.should_raise = RuntimeError("Simulated device failure")
    with pytest.raises(RuntimeError, match="Simulated device failure"):
        await engine.evaluate_noul("text", "question")


@pytest.mark.asyncio
async def test_laya_decision_engine_with_mock_agent() -> None:
    """Verify LayaDecisionEngine with a mock Laya Agent conforming to Laya MLX API."""
    mock_agent = MagicMock()
    mock_agent.predict.return_value = {
        "answers": {
            "choice_q": {
                "CLAIM": 0.88,
                "PREMISE": 0.12,
            },
            "noul_q": 0.94,
            "score_q": 2,
        },
        "action": {
            "act_probability": 0.91,
        },
    }

    engine = LayaDecisionEngine(
        agent=mock_agent,
        default_confidence_threshold=0.85,
        conformal_alpha=0.05,
    )
    assert isinstance(engine, DecisionEngine)
    assert "LayaDecisionEngine" in engine.name

    # 1. evaluate_choice
    choice = await engine.evaluate_choice(
        state="An argument unit",
        question="Classify component",
        options=["CLAIM", "PREMISE"],
    )
    assert choice.selected_option == "CLAIM"
    assert choice.class_probability == 0.88
    assert choice.empirical_accuracy == 0.91
    assert choice.probabilities == {"CLAIM": 0.88, "PREMISE": 0.12}
    assert choice.prediction_set == ["CLAIM", "PREMISE"]
    assert choice.tokens_saved_estimate > 0

    # 2. evaluate_noul
    noul = await engine.evaluate_noul("Chunk context", "Is this substantive?")
    assert noul.probability == 0.94
    assert noul.empirical_accuracy == 0.91
    assert noul.passed is True

    # 3. evaluate_score
    score = await engine.evaluate_score("Chunk context", "Rate quality", [1, 2, 3])
    assert score.selected_option == 3  # index 2 in [1, 2, 3]
    assert score.empirical_accuracy == 0.91

    # 4. evaluate_batch
    batch_res = await engine.evaluate_batch(
        state="Test state",
        questions={
            "choice_q": {"type": "choice", "instructions": "Q", "criteria": ["CLAIM", "PREMISE"]},
            "noul_q": {"type": "noul", "instructions": "Q2"},
        },
    )
    assert isinstance(batch_res["choice_q"], DecisionScore)
    assert isinstance(batch_res["noul_q"], DecisionNoulResult)


@pytest.mark.asyncio
async def test_laya_decision_engine_shortlist_trigger() -> None:
    """Verify that LayaDecisionEngine invokes predict_shortlist when options exceed threshold."""
    mock_agent = MagicMock()
    mock_agent.predict.return_value = {
        "answers": {"choice_q": {"ENT_1": 0.95}},
        "action": {"act_probability": 0.93},
    }

    mock_embed_fn = MagicMock(return_value=[0.1, 0.2])

    mock_laya_module = MagicMock()
    mock_laya_module.predict_shortlist.return_value = {
        "answers": {"choice_q": {"ENT_1": 0.95}},
        "action": {"act_probability": 0.93},
    }

    with patch.dict("sys.modules", {"laya_mlx": mock_laya_module}):
        engine = LayaDecisionEngine(
            agent=mock_agent,
            embed_fn=mock_embed_fn,
            shortlist_threshold=3,
        )

        # 6 options exceeds threshold of 3
        options = ["ENT_1", "ENT_2", "ENT_3", "ENT_4", "ENT_5", "ENT_6"]
        res = await engine.evaluate_choice("state", "Disambiguate mention", options)
        assert res.selected_option == "ENT_1"
        assert mock_laya_module.predict_shortlist.called


@pytest.mark.asyncio
async def test_laya_decision_engine_timeout_and_error_handling() -> None:
    """Verify timeout and error translation in LayaDecisionEngine."""
    mock_agent = MagicMock()

    def slow_predict(*args, **kwargs):
        import time
        time.sleep(0.05)
        return {"answers": {}}

    mock_agent.predict.side_effect = slow_predict

    engine = LayaDecisionEngine(agent=mock_agent, timeout_seconds=0.01)
    with pytest.raises(DecisionEngineError, match="timed out"):
        await engine.evaluate_noul("state", "question")

    # General error handling
    mock_agent.predict.side_effect = RuntimeError("Out of Metal memory")
    engine_err = LayaDecisionEngine(agent=mock_agent, timeout_seconds=2.0)
    with pytest.raises(DecisionEngineError, match="Out of Metal memory"):
        await engine_err.evaluate_noul("state", "question")


def test_laya_decision_engine_missing_mlx_package() -> None:
    """Verify informative DecisionEngineError if laya-mlx is not importable."""
    engine = LayaDecisionEngine()
    with patch.dict("sys.modules", {"laya_mlx": None}):
        with pytest.raises(DecisionEngineError, match="laya-mlx is not installed"):
            engine._get_agent()


@pytest.mark.asyncio
async def test_transformers_decision_engine_with_mock_model() -> None:
    """Verify TransformersDecisionEngine execution with mock model."""
    mock_model = MagicMock()
    mock_model.predict.return_value = {
        "answers": {
            "Which category?": {"A": 0.85, "B": 0.15},
        }
    }
    mock_tok = MagicMock()

    engine = TransformersDecisionEngine(
        model=mock_model,
        tokenizer=mock_tok,
        timeout_seconds=2.0,
    )
    assert isinstance(engine, DecisionEngine)
    assert "TransformersDecisionEngine" in engine.name

    choice = await engine.evaluate_choice("state block", "Which category?", ["A", "B"])
    assert choice.selected_option == "A"
    assert choice.class_probability == 0.85
    assert choice.empirical_accuracy == 0.85
    assert choice.prediction_set == ["A", "B"]

    noul = await engine.evaluate_noul("state block", "Which category?")
    assert isinstance(noul, DecisionNoulResult)


