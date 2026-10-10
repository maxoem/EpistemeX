"""Tests for the declarative ``ModelConfig`` block on ``PipelineConfig``.

``ModelConfig`` exists so that model selection is *declared* in one place and
recorded by name in every run manifest. These tests pin the three properties the
Studio and the example scripts rely on: environment resolution, override
precedence, and the fact that adding the block did not disturb phase
fingerprints (model identity is already covered by ``fingerprint_method``).
"""

from __future__ import annotations

import pytest
from episteme_pipeline.config import ModelConfig, PipelineConfig
from episteme_pipeline.runs.fingerprints import fingerprint_phase_config


@pytest.fixture
def clean_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_MODEL", "EMBED_MODEL", "RERANKER_MODEL", "LITELLM_API_BASE", "LLM_THINKING_LEVEL", "THINKING_LEVEL"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_stable(clean_model_env: None) -> None:
    """Defaults must not drift — three call sites use them as fallbacks."""
    models = ModelConfig()
    assert models.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert models.reranker_model == "Alibaba-NLP/gte-reranker-modernbert-base"
    assert models.temperature == 0.0
    assert models.seed is None
    assert models.thinking_level == "off"


def test_from_env_reads_known_variables(
    clean_model_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MODEL", "openai/deepseek-v4-flash-sovereign")
    monkeypatch.setenv("EMBED_MODEL", "openai/qwen-3-vl-embedding-2b-sovereign")
    monkeypatch.setenv("RERANKER_MODEL", "Alibaba-NLP/gte-reranker-modernbert-base")
    monkeypatch.setenv("LITELLM_API_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_THINKING_LEVEL", "medium")

    models = ModelConfig.from_env()

    assert models.llm_model == "openai/deepseek-v4-flash-sovereign"
    assert models.embedding_model == "openai/qwen-3-vl-embedding-2b-sovereign"
    assert models.llm_api_base == "https://example.invalid/v1"
    assert models.thinking_level == "medium"


def test_blank_env_falls_back_to_defaults(
    clean_model_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exported-but-empty variable must not blank out the model name."""
    monkeypatch.setenv("LLM_MODEL", "   ")

    assert ModelConfig.from_env().llm_model == ModelConfig().llm_model


def test_explicit_overrides_beat_the_environment(
    clean_model_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MODEL", "from-env")

    assert ModelConfig.from_env(llm_model="pinned").llm_model == "pinned"


def test_pipeline_config_from_env_resolves_models(
    clean_model_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MODEL", "openai/some-model")

    config = PipelineConfig.from_env()

    assert config.models.llm_model == "openai/some-model"


def test_model_names_are_recorded_in_the_config_snapshot(clean_model_env: None) -> None:
    """The manifest's ``config_snapshot`` is ``config.model_dump()`` — models must survive it."""
    snapshot = PipelineConfig(
        models=ModelConfig(llm_model="openai/recorded-model")
    ).model_dump(mode="json")

    assert snapshot["models"]["llm_model"] == "openai/recorded-model"


def test_deprecated_aliases_still_read(clean_model_env: None) -> None:
    """Three in-tree call sites still read the old attribute names."""
    config = PipelineConfig(models=ModelConfig(embedding_model="e", reranker_model="r"))

    assert config.default_embedding_model == "e"
    assert config.default_reranker_model == "r"


def test_model_choice_does_not_alter_phase_fingerprints(clean_model_env: None) -> None:
    """Guards the deliberate decision to keep ``models`` out of phase fingerprints.

    Model identity reaches invalidation via ``fingerprint_method`` on the live
    model objects. Folding it in here as well would re-fingerprint every phase
    and invalidate all prior runs for no added coverage.
    """
    baseline = PipelineConfig(models=ModelConfig(llm_model="model-a"))
    swapped = PipelineConfig(models=ModelConfig(llm_model="model-b"))

    for phase_key in ("phase1", "phase2", "phase3", "phase4", "phase5", "phase6"):
        assert fingerprint_phase_config(
            getattr(baseline, phase_key)
        ) == fingerprint_phase_config(getattr(swapped, phase_key))
