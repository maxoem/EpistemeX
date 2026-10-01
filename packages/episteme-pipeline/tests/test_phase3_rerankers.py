from __future__ import annotations

from typing import Any

import pytest

from episteme_pipeline.contracts.domain import L2Entity, SubGraph
from episteme_pipeline.phases.phase3_global_relations.rerankers import (
    SentenceTransformerCrossEncoderReranker,
)


class FakeCrossEncoder:
    """Minimal cross-encoder test double.

    Attributes
    ----------
    calls
        Recorded calls made to ``predict``.
    """

    def __init__(self) -> None:
        """Initialize the fake model."""
        self.calls = []

    def predict(
        self,
        pairs: list[tuple[str, str]],
        activation_fn: Any,
        **kwargs: Any,
    ) -> list[float]:
        """Record the predict call and return a stable score.

        Parameters
        ----------
        pairs
            Query/document pairs passed by the reranker.
        activation_fn
            Activation function forwarded by the reranker.

        Returns
        -------
        list[float]
            Single deterministic reranker score.
        """
        self.calls.append((pairs, activation_fn))
        return [0.73]


@pytest.mark.asyncio
async def test_cross_encoder_reranker_scores_entity_pair() -> None:
    """Reranker formats entity envelopes and delegates scoring to the model."""
    model = FakeCrossEncoder()
    activation_fn = object()
    reranker = SentenceTransformerCrossEncoderReranker(
        model=model,
        activation_fn=activation_fn,
    )

    entity_a = L2Entity(
        id="a",
        label="Concept",
        name="Explanatory Power",
        description="",
    )
    entity_b = L2Entity(
        id="b",
        label="Concept",
        name="Empirical Adequacy",
        description="",
    )

    score = await reranker.score_relation(
        entity_a,
        SubGraph(center_id="a", nodes=[entity_a], triples=[], depth=1),
        entity_b,
        SubGraph(center_id="b", nodes=[entity_b], triples=[], depth=1),
    )

    assert score == 0.73
    assert model.calls[0][1] is activation_fn

    pair = model.calls[0][0][0]
    assert "Entity: Explanatory Power" in pair[0]
    assert "Entity: Empirical Adequacy" in pair[1]


def test_cross_encoder_reranker_uses_injected_model_without_loading() -> None:
    """Injected models bypass default model loading."""
    model = FakeCrossEncoder()

    class NoLoadReranker(SentenceTransformerCrossEncoderReranker):
        @staticmethod
        def _load_model(**kwargs: Any) -> Any:
            """Raise if the default loader is invoked.

            Parameters
            ----------
            **kwargs
                Loader arguments from the parent constructor.

            Returns
            -------
            Any
                This method always raises.
            """
            raise AssertionError("model loading should not be called")

    reranker = NoLoadReranker(model=model)

    assert reranker.model is model


def test_cross_encoder_reranker_forwards_max_length_to_loader() -> None:
    """Configured max length is passed to the sentence-transformers loader."""
    captured: dict[str, Any] = {}

    class CaptureLoadReranker(SentenceTransformerCrossEncoderReranker):
        @staticmethod
        def _load_model(**kwargs: Any) -> Any:
            """Capture loader kwargs and return a fake model."""
            captured.update(kwargs)
            return FakeCrossEncoder()

    CaptureLoadReranker(max_length=384)

    assert captured["max_length"] == 384


def test_cross_encoder_reranker_describes_input_sizes() -> None:
    """Reranker exposes lightweight size metadata for observability."""
    reranker = SentenceTransformerCrossEncoderReranker(model=FakeCrossEncoder())
    entity_a = L2Entity(id="a", label="Concept", name="Theory", description="Dense")
    entity_b = L2Entity(id="b", label="Concept", name="Observation", description="Wide")

    metadata = reranker.describe_relation_input(
        entity_a,
        SubGraph(center_id="a", nodes=[entity_a], triples=[], depth=2),
        entity_b,
        SubGraph(center_id="b", nodes=[entity_b], triples=[], depth=2),
    )

    assert metadata["query_char_count"] > 0
    assert metadata["document_char_count"] > 0
    assert metadata["pair_byte_count"] >= metadata["pair_char_count"]
    assert metadata["max_length"] == 1024


def test_cross_encoder_reranker_forwards_huggingface_configs_to_loader() -> None:
    """Device, trust_remote_code, and kwarg dicts are passed down to the loader."""
    captured: dict[str, Any] = {}

    class CaptureLoadReranker(SentenceTransformerCrossEncoderReranker):
        @staticmethod
        def _load_model(**kwargs: Any) -> Any:
            """Capture loader kwargs and return a fake model."""
            captured.update(kwargs)
            return FakeCrossEncoder()

    CaptureLoadReranker(
        device="cuda",
        trust_remote_code=True,
        model_kwargs={"torch_dtype": "auto", "attn_implementation": "flash_attention_2"},
        tokenizer_args={"use_fast": True},
        config_args={"output_hidden_states": True},
    )

    assert captured["device"] == "cuda"
    assert captured["trust_remote_code"] is True
    assert captured["automodel_args"] == {"torch_dtype": "auto", "attn_implementation": "flash_attention_2"}
    assert captured["tokenizer_args"] == {"use_fast": True}
    assert captured["config_args"] == {"output_hidden_states": True}


def test_cross_encoder_reranker_cache_key_differentiates_hf_configs() -> None:
    """Cache key varies when Hugging Face configuration arguments differ."""
    from episteme_pipeline.phases.phase3_global_relations.rerankers import _model_cache_key

    key1 = _model_cache_key(
        model_name="test-model",
        prompts={"classification": "test"},
        default_prompt_name="classification",
        max_length=1024,
        device="cpu",
        trust_remote_code=False,
        model_kwargs=None,
    )
    key2 = _model_cache_key(
        model_name="test-model",
        prompts={"classification": "test"},
        default_prompt_name="classification",
        max_length=1024,
        device="cuda",
        trust_remote_code=True,
        model_kwargs={"torch_dtype": "auto"},
    )

    assert key1 != key2


@pytest.mark.asyncio
async def test_jev_relation_reranker_default_prompt() -> None:
    """Verify JevRelationReranker uses PAIR_GATING_DECISION_PROMPT by default."""
    from unittest.mock import AsyncMock, MagicMock
    from episteme_pipeline.phases.phase3_global_relations.rerankers import JevRelationReranker
    from episteme_pipeline.prompts.default_prompts import PAIR_GATING_DECISION_PROMPT
    from episteme_pipeline.protocols.decision import DecisionNoulResult

    mock_engine = MagicMock()
    mock_engine.evaluate_noul = AsyncMock(
        return_value=DecisionNoulResult(probability=0.85, passed=True, empirical_accuracy=0.80)
    )

    reranker = JevRelationReranker(mock_engine)
    assert reranker.decision_template == PAIR_GATING_DECISION_PROMPT

    entity_a = L2Entity(id="a", label="Concept", name="Entity A")
    entity_b = L2Entity(id="b", label="Concept", name="Entity B")
    env = SubGraph(center_id="x", nodes=[], triples=[], depth=0)

    score = await reranker.score_relation(entity_a, env, entity_b, env)
    assert score == 0.85
    mock_engine.evaluate_noul.assert_called_once()
    assert (
        mock_engine.evaluate_noul.call_args.kwargs["question"]
        == "Is there a direct theoretical or semantic relationship between Entity A and Entity B?"
    )


@pytest.mark.asyncio
async def test_jev_relation_reranker_custom_prompt() -> None:
    """Verify JevRelationReranker respects custom decision_template in prompt bundle."""
    from unittest.mock import AsyncMock, MagicMock
    from episteme_pipeline.phases.phase3_global_relations.rerankers import JevRelationReranker
    from episteme_pipeline.prompts.models import StructuredPromptBundle
    from episteme_pipeline.protocols.decision import DecisionNoulResult

    mock_engine = MagicMock()
    mock_engine.evaluate_noul = AsyncMock(
        return_value=DecisionNoulResult(probability=0.90, passed=True, empirical_accuracy=0.88)
    )

    bundle = StructuredPromptBundle(
        direct_template="Direct",
        decision_template="Are {entity_a} and {entity_b} connected?",
    )
    reranker = JevRelationReranker(mock_engine, prompts=bundle)
    assert reranker.decision_template == "Are {entity_a} and {entity_b} connected?"

    entity_a = L2Entity(id="a", label="Concept", name="Kant")
    entity_b = L2Entity(id="b", label="Concept", name="Hume")
    env = SubGraph(center_id="x", nodes=[], triples=[], depth=0)

    await reranker.score_relation(entity_a, env, entity_b, env)
    assert mock_engine.evaluate_noul.call_args.kwargs["question"] == "Are Kant and Hume connected?"


def test_jev_relation_reranker_missing_prompt_fails() -> None:
    """Verify JevRelationReranker raises ValueError if decision template is empty."""
    from unittest.mock import MagicMock
    import pytest
    from episteme_pipeline.phases.phase3_global_relations.rerankers import JevRelationReranker
    from episteme_pipeline.prompts.models import StructuredPromptBundle

    bundle = StructuredPromptBundle(direct_template="Direct", decision_template="")
    with pytest.raises(ValueError, match="No decision prompt configured for JevRelationReranker"):
        JevRelationReranker(MagicMock(), prompts=bundle)


