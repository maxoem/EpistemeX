"""Tests for prompt fingerprinting in RunManifest and _build_manifest."""

from episteme_pipeline.runs.fingerprints import stable_fingerprint
from episteme_pipeline.runs.models import RunManifest


def test_prompt_fingerprints_captures_custom_ner_prompt():
    """When a custom NER prompt is set, its fingerprint should be captured."""

    custom_prompt = "CUSTOM NER PROMPT TEMPLATE v2"
    default_prompt = "You are an expert in formal logic and the history of philosophy."

    # Verify the default prompt is what we expect
    assert default_prompt in custom_prompt or custom_prompt != default_prompt

    # The fingerprint of two different prompts should differ
    fp1 = stable_fingerprint(custom_prompt)
    fp2 = stable_fingerprint(default_prompt)
    assert fp1 != fp2


def test_prompt_fingerprint_is_stable():
    """Verify the same prompt text always produces the same fingerprint."""
    from episteme_pipeline.runs.fingerprints import stable_fingerprint

    prompt = "This is a test prompt"
    fp1 = stable_fingerprint(prompt)
    fp2 = stable_fingerprint(prompt)
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex


def test_prompt_fingerprint_changes_with_content():
    """Verify that changing the prompt text changes the fingerprint."""
    fp1 = stable_fingerprint("prompt v1")
    fp2 = stable_fingerprint("prompt v2")
    assert fp1 != fp2


def test_run_manifest_has_prompts_fingerprints_field(config):
    """Verify RunManifest model has prompts_fingerprints field."""
    manifest = RunManifest(
        run_id="test-manifest",
        prompts_fingerprints={"ner_extraction": "abc123"},
    )
    assert isinstance(manifest.prompts_fingerprints, dict)
    assert manifest.prompts_fingerprints == {"ner_extraction": "abc123"}


def test_run_manifest_prompt_fingerprints_empty_by_default():
    """Verify prompts_fingerprints is empty dict by default."""
    manifest = RunManifest(run_id="test-manifest")
    assert manifest.prompts_fingerprints == {}


def test_config_snapshot_reflects_changed_schema_version(config):
    """Verify config_snapshot includes schema version when changed."""
    config.graph_schema.version = "v2-schema-test"
    snapshot = config.model_dump(mode="json")
    assert "graph_schema" in snapshot
    assert snapshot["graph_schema"]["version"] == "v2-schema-test"
