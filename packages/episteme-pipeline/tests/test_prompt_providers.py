"""Unit tests for PromptProvider implementations and prompt management."""

import json
from unittest.mock import MagicMock

import pytest

from episteme_pipeline.config import PipelineConfig, StructuredPromptBundle
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.prompts.providers import (
    DefaultPromptProvider,
    LangfusePromptProvider,
    FilePromptProvider,
    _mustache_to_python_format,
)
from episteme_pipeline.protocols.prompts import PromptProvider


def test_mustache_to_python_format_conversion():
    """Verify Mustache variable tags are converted while preserving JSON escapes."""
    template = "Extract from {{chunk_text}} with schema {{\n  \"key\": \"val\"\n}} and {{entity_types}}."
    converted = _mustache_to_python_format(template)
    assert "{chunk_text}" in converted
    assert "{entity_types}" in converted
    assert '{{\n  "key": "val"\n}}' in converted


def test_default_prompt_provider_protocol_compliance():
    """Verify DefaultPromptProvider implements PromptProvider protocol."""
    provider = DefaultPromptProvider()
    assert isinstance(provider, PromptProvider)


def test_default_prompt_provider_bundles():
    """Verify DefaultPromptProvider returns bundles for all canonical names."""
    provider = DefaultPromptProvider()
    names = [
        "ner_extraction",
        "entity_linking",
        "global_relation",
        "entity_synthesis",
        "adu_segmentation",
        "acc_classification",
        "arc_classification",
    ]
    for name in names:
        bundle = provider.get_bundle(name)
        assert isinstance(bundle, StructuredPromptBundle)
        assert bundle.direct_template
        assert bundle.name == name
        assert bundle.provider == "default"

        direct_str = provider.get_template(name)
        assert isinstance(direct_str, str)
        assert len(direct_str) > 0


def test_default_prompt_provider_aliases():
    """Verify aliases resolve correctly to canonical bundles."""
    provider = DefaultPromptProvider()
    assert provider.get_bundle("ner").name == "ner_extraction"
    assert provider.get_bundle("linking").name == "entity_linking"
    assert provider.get_bundle("maturation").name == "entity_synthesis"
    assert provider.get_bundle("adu").name == "adu_segmentation"
    assert provider.get_bundle("acc").name == "acc_classification"
    assert provider.get_bundle("arc").name == "arc_classification"


def test_default_prompt_provider_populate_config():
    """Verify populate_config sets all prompt bundles on PipelineConfig."""
    provider = DefaultPromptProvider()
    config = PipelineConfig()
    populated = provider.populate_config(config, label_or_version="staging")

    assert populated.phase2.ner_prompts.name == "ner_extraction"
    assert populated.phase2.entity_linking_prompts.name == "entity_linking"
    assert populated.phase3.global_relation_prompts.name == "global_relation"
    assert populated.phase4_maturation.entity_synthesis_prompts.name == "entity_synthesis"
    assert populated.phase4.adu_segmentation_prompts.name == "adu_segmentation"
    assert populated.phase4.acc_prompts.name == "acc_classification"
    assert populated.phase4.arc_prompts.name == "arc_classification"


def test_langfuse_prompt_provider_fallback_when_unconfigured():
    """Verify LangfusePromptProvider falls back to DefaultPromptProvider when client is None."""
    provider = LangfusePromptProvider(client=None)
    bundle = provider.get_bundle("ner_extraction")
    assert isinstance(bundle, StructuredPromptBundle)
    assert bundle.name == "ner_extraction"
    assert bundle.provider == "default"


def test_langfuse_prompt_provider_with_mock_client():
    """Verify LangfusePromptProvider resolves prompts and metadata from mock Langfuse client."""
    mock_client = MagicMock()
    mock_prompt = MagicMock()
    mock_prompt.name = "ner_extraction"
    mock_prompt.version = 5
    mock_prompt.labels = ["production"]
    mock_prompt.config = {"temperature": 0.1, "model": "gpt-4o"}
    mock_prompt.prompt = "Extract entities from {{chunk_text}} matching {{entity_types}}."

    mock_client.get_prompt.return_value = mock_prompt

    provider = LangfusePromptProvider(client=mock_client)
    bundle = provider.get_bundle("ner_extraction", label_or_version="production")

    mock_client.get_prompt.assert_any_call(name="ner_extraction", label="production")

    assert bundle.name == "ner_extraction"
    assert bundle.version == 5
    assert bundle.label == "production"
    assert bundle.provider == "langfuse"
    assert bundle.metadata == {"temperature": 0.1, "model": "gpt-4o"}
    assert "{chunk_text}" in bundle.direct_template
    assert "{entity_types}" in bundle.direct_template


def test_file_prompt_provider(tmp_path):
    """Verify FilePromptProvider loads JSON prompt definitions from disk."""
    prompt_file = tmp_path / "ner_extraction.json"
    prompt_file.write_text(
        json.dumps({
            "direct_template": "Custom file prompt: {chunk_text}",
            "reasoning_template": "Custom reasoning: {chunk_text}",
            "version": "1.0.0",
        }),
        encoding="utf-8",
    )

    provider = FilePromptProvider(prompts_dir=tmp_path)
    bundle = provider.get_bundle("ner_extraction")

    assert bundle.direct_template == "Custom file prompt: {chunk_text}"
    assert bundle.reasoning_template == "Custom reasoning: {chunk_text}"
    assert bundle.version == "1.0.0"
    assert bundle.provider == "file"


@pytest.mark.asyncio
async def test_prompt_version_changes_fingerprint(tmp_path, graph_store):
    """Verify that updating a prompt version changes the phase prompt fingerprint."""
    config1 = PipelineConfig()
    config1.phase2.ner_prompts.version = 1
    pipeline1 = Pipeline(
        phases=[],
        config=config1,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )
    fps1 = pipeline1._prompt_fingerprints()

    config2 = PipelineConfig()
    config2.phase2.ner_prompts.version = 2
    pipeline2 = Pipeline(
        phases=[],
        config=config2,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )
    fps2 = pipeline2._prompt_fingerprints()

    assert fps1["phase2"]["ner_extraction"] != fps2["phase2"]["ner_extraction"]
    assert fps1["phase3"]["global_relation"] == fps2["phase3"]["global_relation"]


def test_langfuse_prompt_provider_unreachable_passes_with_warning():
    """Verify provider passes with a warning when Langfuse cannot be reached.

    If Langfuse raises a connection or authentication error, the provider must
    issue a warning, fall back gracefully to the default prompt bundle, and
    return a valid StructuredPromptBundle without failing.
    """
    mock_failing_client = MagicMock()
    mock_failing_client.get_prompt.side_effect = ConnectionError("Langfuse server connection refused at localhost:3000")

    provider = LangfusePromptProvider(client=mock_failing_client)

    # Calling get_bundle should issue a UserWarning and return a valid fallback bundle
    with pytest.warns(UserWarning, match=r"Failed to fetch prompt.*connection refused"):
        bundle = provider.get_bundle("ner_extraction", label_or_version="production")

    assert isinstance(bundle, StructuredPromptBundle)
    assert bundle.name == "ner_extraction"
    assert bundle.direct_template
    assert len(bundle.direct_template) > 0


@pytest.mark.parametrize("client_scenario", ["working", "unreachable", "unconfigured"])
def test_langfuse_provider_scenario_always_returns_valid_bundle(client_scenario):
    """Verify provider always returns a valid bundle, emitting a warning if unreachable."""
    if client_scenario == "working":
        client = MagicMock()
        mock_prompt = MagicMock()
        mock_prompt.name = "global_relation"
        mock_prompt.version = 2
        mock_prompt.labels = ["production"]
        mock_prompt.config = {}
        mock_prompt.prompt = "Relation prompt: {{relation_types}}"
        client.get_prompt.return_value = mock_prompt
        provider = LangfusePromptProvider(client=client)

        bundle = provider.get_bundle("global_relation")
        assert isinstance(bundle, StructuredPromptBundle)
        assert bundle.provider == "langfuse"
        assert bundle.version == 2

    elif client_scenario == "unreachable":
        client = MagicMock()
        client.get_prompt.side_effect = TimeoutError("Langfuse request timed out")
        client.create_prompt.side_effect = TimeoutError("Langfuse request timed out")
        provider = LangfusePromptProvider(client=client)

        with pytest.warns(UserWarning, match=r"Failed to (fetch|create) prompt.*timed out"):
            bundle = provider.get_bundle("global_relation")
        assert isinstance(bundle, StructuredPromptBundle)
        assert bundle.direct_template
        assert bundle.provider == "default"

    elif client_scenario == "unconfigured":
        provider = LangfusePromptProvider(client=None)

        with pytest.warns(UserWarning, match=r"(Failed to fetch prompt|Langfuse client is not initialized)"):
            bundle = provider.get_bundle("global_relation")
        assert isinstance(bundle, StructuredPromptBundle)
        assert bundle.direct_template
        assert bundle.provider == "default"


def test_langfuse_prompt_provider_create_prompt():
    """Verify create_prompt correctly calls Langfuse client.create_prompt."""
    mock_client = MagicMock()
    mock_created = MagicMock()
    mock_created.name = "custom_test_prompt"
    mock_created.version = 1
    mock_client.create_prompt.return_value = mock_created

    provider = LangfusePromptProvider(client=mock_client)
    res = provider.create_prompt(
        name="custom_test_prompt",
        template="Test prompt {var}",
        labels=["staging"],
        tags=["unit-test"],
        config={"temp": 0.5},
        commit_message="Test commit",
    )

    mock_client.create_prompt.assert_called_once_with(
        name="custom_test_prompt",
        prompt="Test prompt {var}",
        labels=["staging"],
        tags=["unit-test"],
        type="text",
        config={"temp": 0.5},
        commit_message="Test commit",
    )
    assert res == mock_created


def test_langfuse_prompt_provider_create_bundle():
    """Verify create_bundle creates direct, reasoning, format, and gleaning templates."""
    mock_client = MagicMock()
    mock_direct = MagicMock()
    mock_direct.version = 3
    mock_client.create_prompt.return_value = mock_direct

    provider = LangfusePromptProvider(client=mock_client)
    bundle = StructuredPromptBundle(
        direct_template="Direct prompt",
        reasoning_template="Reasoning prompt",
        format_template="Format prompt",
        gleaning_template="Gleaning prompt",
        name="ner_extraction",
    )

    created_bundle = provider.create_bundle(
        name="ner_extraction",
        bundle=bundle,
        label="production",
        tags=["default-prompt"],
    )

    # 4 calls to create_prompt: direct, reasoning, format, gleaning
    assert mock_client.create_prompt.call_count == 4
    created_names = [call.kwargs["name"] for call in mock_client.create_prompt.call_args_list]
    assert "ner_extraction" in created_names
    assert "ner_extraction_reasoning" in created_names
    assert "ner_extraction_format" in created_names
    assert "ner_extraction_gleaning" in created_names

    assert created_bundle.version == 3
    assert created_bundle.provider == "langfuse"
    assert created_bundle.label == "production"


def test_langfuse_prompt_provider_sync_defaults():
    """Verify sync_defaults_to_langfuse uploads all default structured bundles."""
    mock_client = MagicMock()
    # First time get_prompt is called, simulate prompt not existing
    mock_client.get_prompt.side_effect = Exception("Prompt not found")
    mock_created = MagicMock()
    mock_created.version = 1
    mock_client.create_prompt.return_value = mock_created

    provider = LangfusePromptProvider(client=mock_client)
    synced = provider.sync_defaults_to_langfuse(label="production")

    assert "ner_extraction" in synced
    assert "entity_linking" in synced
    assert "global_relation" in synced
    assert "entity_synthesis" in synced
    assert "adu_segmentation" in synced
    assert "acc_classification" in synced
    assert "arc_classification" in synced

    # Verified create_prompt was invoked across all templates
    assert mock_client.create_prompt.call_count >= 7
    all_created_names = {call.kwargs["name"] for call in mock_client.create_prompt.call_args_list}
    assert "ner_extraction" in all_created_names
    assert "ner_extraction_reasoning" in all_created_names
    assert "global_relation" in all_created_names
    assert "acc_classification" in all_created_names
    assert "arc_classification" in all_created_names


def test_langfuse_prompt_provider_populate_config_triggers_sync():
    """Verify populate_config syncs default prompt bundles into Langfuse if missing."""
    mock_client = MagicMock()
    mock_client.get_prompt.side_effect = Exception("404 Not Found")
    mock_created = MagicMock()
    mock_created.version = 1
    mock_created.prompt = "Default template"
    mock_client.create_prompt.return_value = mock_created

    provider = LangfusePromptProvider(client=mock_client)
    config = PipelineConfig()
    populated = provider.populate_config(config, label_or_version="production", sync_defaults=True)

    assert mock_client.create_prompt.call_count >= 7
    assert populated.phase2.ner_prompts.version == 1
    assert populated.phase3.global_relation_prompts.version == 1
    assert populated.phase4.acc_prompts.version == 1


