"""Tests for Engine Settings Service, persistent storage, and schema mapping."""

from __future__ import annotations

from pathlib import Path

import pytest
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_studio.adapters.engine_storage import FileEngineSettingsStorage
from episteme_studio.adapters.schema_mapper import SchemaMapper
from episteme_studio.app import create_app
from episteme_studio.domain.engine import EngineSettings, PredicateMapping
from episteme_studio.services.engine_settings_service import EngineSettingsService
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


def test_schema_mapper_l2_definitions_and_edge_descriptors() -> None:
    """SchemaMapper must return node definitions for L2 and resolve edge descriptors."""
    mapper = SchemaMapper()

    # Verify L2 node definition is present (resolving the previous bug)
    concept_desc = mapper.resolve_node_descriptor("Concept", layer=2)
    assert concept_desc["known"] is True
    assert concept_desc["definition"] is not None
    assert "Abstract idea" in concept_desc["definition"]

    # Verify L3 node definition
    obs_desc = mapper.resolve_node_descriptor("ObservationUnit", layer=3)
    assert obs_desc["known"] is True
    assert obs_desc["partition"] == "B"
    assert obs_desc["definition"] is not None

    # Verify edge descriptors
    supports_arg = mapper.resolve_edge_descriptor("SUPPORTS_ARG")
    assert supports_arg["known"] is True
    assert supports_arg["polarity"] == 1
    assert supports_arg["layer"] == 3
    assert supports_arg["definition"] is not None

    refutes = mapper.resolve_edge_descriptor("REFUTES")
    assert refutes["known"] is True
    assert refutes["polarity"] == -1
    assert refutes["layer"] == 2

    unknown = mapper.resolve_edge_descriptor("UNMAPPED_REL")
    assert unknown["known"] is False
    assert unknown["polarity"] is None


def test_schema_mapper_with_predicate_aliases() -> None:
    """SchemaMapper respects custom open-vocabulary predicate aliases."""
    aliases = {
        "WIDERSPRICHT": {"polarity": -1, "canonical": "ATTACKS", "definition": "German attack relation"},
        "BELEGT": {"polarity": 1, "canonical": "SUPPORTS_ARG"},
    }
    mapper = SchemaMapper(predicate_aliases=aliases)

    assert mapper.resolve_polarity("WIDERSPRICHT") == -1
    assert mapper.resolve_polarity("BELEGT") == 1
    assert mapper.resolve_polarity("OTHER") is None

    w_desc = mapper.resolve_edge_descriptor("WIDERSPRICHT")
    assert w_desc["known"] is True
    assert w_desc["polarity"] == -1
    assert w_desc["alias_of"] == "ATTACKS"
    assert w_desc["definition"] == "German attack relation"


@pytest.mark.asyncio
async def test_file_engine_settings_storage_roundtrip(tmp_path: Path) -> None:
    """FileEngineSettingsStorage safely writes and reads engine settings."""
    storage_file = tmp_path / "test_engine_settings.json"
    storage = FileEngineSettingsStorage(storage_path=storage_file)

    # Initial load on missing file returns default
    initial = await storage.load()
    assert initial.schema_config == {}

    # Mutate and save
    custom_schema = SchemaConfig(
        node_types=["Concept", "CustomEntity"],
        relation_types=["RELATED_TO", "CUSTOM_REL"],
    )
    settings = EngineSettings(
        schema_config=custom_schema.model_dump(),
        predicate_aliases={"CUSTOM_PRED": {"polarity": 1}},
    )
    await storage.save(settings)
    assert storage_file.is_file()

    # Reload from disk
    loaded = await storage.load()
    assert loaded.schema_config["node_types"] == ["Concept", "CustomEntity"]
    assert "CUSTOM_PRED" in loaded.predicate_aliases

    # Reset
    reset_settings = await storage.reset()
    assert reset_settings.schema_config == {}
    assert not storage_file.is_file()


@pytest.mark.asyncio
async def test_engine_settings_service_and_api(tmp_path: Path) -> None:
    """EngineSettingsService and API endpoints support querying, patching, mapping and reset."""
    storage_file = tmp_path / "api_engine_settings.json"
    storage = FileEngineSettingsStorage(storage_path=storage_file)
    service = EngineSettingsService(storage=storage)

    # Test direct service map_predicate
    await service.map_predicate(
        PredicateMapping(
            predicate="KRITISIERT",
            polarity=-1,
            canonical="ATTACKS",
            definition="German criticism predicate",
        )
    )
    s = await service.get_settings()
    assert "KRITISIERT" in s.predicate_aliases
    assert s.predicate_aliases["KRITISIERT"]["polarity"] == -1

    # Test via FastAPI endpoints
    app = create_app(StudioSettings())
    app.state.engine_settings_service = service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET /api/engine/settings
        res = await client.get("/api/engine/settings")
        assert res.status_code == 200
        data = res.json()
        assert "schema_config" in data
        assert "predicate_aliases" in data
        assert "KRITISIERT" in data["predicate_aliases"]

        # GET /api/schema reflects the mapped predicate alias
        schema_res = await client.get("/api/schema")
        assert schema_res.status_code == 200
        schema_data = schema_res.json()
        assert "predicate_aliases" in schema_data
        assert "KRITISIERT" in schema_data["predicate_aliases"]

        # POST /api/engine/map-predicate
        map_res = await client.post(
            "/api/engine/map-predicate",
            json={
                "predicate": "STUETZT",
                "polarity": 1,
                "canonical": "SUPPORTS",
                "definition": "German support predicate",
            },
        )
        assert map_res.status_code == 200
        map_data = map_res.json()
        assert "STUETZT" in map_data["predicate_aliases"]
        assert map_data["predicate_aliases"]["STUETZT"]["polarity"] == 1

        # PUT /api/engine/settings
        patch_res = await client.put(
            "/api/engine/settings",
            json={
                "predicate_aliases": {
                    "STUETZT": {"polarity": 1},
                    "WIDERLEGT": {"polarity": -1},
                }
            },
        )
        assert patch_res.status_code == 200
        patch_data = patch_res.json()
        assert "WIDERLEGT" in patch_data["predicate_aliases"]

        # POST /api/engine/settings/reset
        reset_res = await client.post("/api/engine/settings/reset")
        assert reset_res.status_code == 200
        reset_data = reset_res.json()
        assert reset_data["predicate_aliases"] == {}


@pytest.mark.asyncio
async def test_decision_engine_playground_and_protocol_contract() -> None:
    """Verify POST /api/engine/decision/test accepts both playground and protocol payloads."""
    app = create_app(StudioSettings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Playground modal payload (using input_text, candidate_labels)
        pg_res = await client.post(
            "/api/engine/decision/test",
            json={
                "primitive": "choice",
                "input_text": "Der Satz vom Widerspruch ist das sicherste aller Prinzipien.",
                "candidate_labels": ["Axiom", "Definition", "Lemma", "Theorem"],
            },
        )
        assert pg_res.status_code == 200, f"Expected 200, got {pg_res.status_code}: {pg_res.text}"
        pg_data = pg_res.json()
        assert pg_data["primitive"] == "choice"
        assert "prediction" in pg_data
        assert "confidence" in pg_data
        assert "conformal_set" in pg_data
        assert "tier" in pg_data
        assert "tokens_saved" in pg_data
        assert "latency_ms" in pg_data

        # 2. Protocol payload (using state, question, options)
        proto_res = await client.post(
            "/api/engine/decision/test",
            json={
                "primitive": "choice",
                "state": "Sample premise text",
                "question": "What is the classification?",
                "options": ["A", "B", "C"],
            },
        )
        assert proto_res.status_code == 200
        proto_data = proto_res.json()
        assert proto_data["primitive"] == "choice"
        assert proto_data["selected_option"] is not None

        # 3. Noul primitive playground payload (hypothesis_text)
        noul_res = await client.post(
            "/api/engine/decision/test",
            json={
                "primitive": "noul",
                "input_text": "Premise stating validity.",
                "hypothesis_text": "Is this logically valid?",
            },
        )
        assert noul_res.status_code == 200
        noul_data = noul_res.json()
        assert noul_data["primitive"] == "noul"
        assert "prediction" in noul_data

        # 4. Playground request passing selected options from config panel
        override_res = await client.post(
            "/api/engine/decision/test",
            json={
                "primitive": "choice",
                "input_text": "Philosophy of science studies structural representations.",
                "candidate_labels": ["Axiom", "Theorem"],
                "provider": "laya",
                "model_checkpoint": "aac6fef/laya-mlx",
                "fast_exit_threshold": 0.95,
            },
        )
        assert override_res.status_code == 200
        override_data = override_res.json()
        assert override_data["primitive"] == "choice"
        assert override_data["prediction"] is not None


@pytest.mark.asyncio
async def test_decision_engine_playground_read_only_docker_immunity() -> None:
    """Verify that in read-only mode, the playground runs safely via simulation stub without failing."""
    app = create_app(StudioSettings(read_only=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/engine/decision/test",
            json={
                "primitive": "choice",
                "input_text": "Epistemic reasoning under uncertainty.",
                "candidate_labels": ["Hypothesis", "Evidence"],
                "provider": "laya",
                "model_checkpoint": "aac6fef/laya-mlx",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_mock"] is True
        assert data["prediction"] is not None


