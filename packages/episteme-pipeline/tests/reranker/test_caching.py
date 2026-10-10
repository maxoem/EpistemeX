"""Test script to demonstrate the model caching functionality in the reranker."""

from unittest.mock import MagicMock

from episteme_pipeline.phases.phase3_global_relations.rerankers import (
    SentenceTransformerCrossEncoderReranker,
)


def test_model_caching(monkeypatch) -> None:
    """Test that model caching reuses the loaded model instance without redundant calls.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture to intercept external model loading.
    """
    class DummyModel:
        pass

    fake_model = DummyModel()
    mock_load = MagicMock(return_value=fake_model)
    monkeypatch.setattr(SentenceTransformerCrossEncoderReranker, "_load_model", mock_load)

    reranker1 = SentenceTransformerCrossEncoderReranker(
        model_name="test-caching-model",
        cache_model=True,
    )
    assert mock_load.call_count == 1

    reranker2 = SentenceTransformerCrossEncoderReranker(
        model_name="test-caching-model",
        cache_model=True,
    )
    assert mock_load.call_count == 1
    assert reranker1.model is reranker2.model
    assert reranker2.model is fake_model


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
