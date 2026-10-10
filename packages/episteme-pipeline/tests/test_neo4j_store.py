"""Regression tests for Neo4j graph store Cypher generation."""

from __future__ import annotations

import pytest

from episteme_pipeline.graph.neo4j_store import _Neo4jWriteMixin


class _RecordingTransaction:
    def __init__(self, session: _RecordingSession) -> None:
        self.session = session

    async def __aenter__(self) -> "_RecordingTransaction":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def run(self, query: str, **params) -> None:
        await self.session.run(query, **params)

    async def commit(self) -> None:
        pass


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self) -> "_RecordingSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def run(self, query: str, **params) -> None:
        self.calls.append((query, params))

    async def begin_transaction(self) -> _RecordingTransaction:
        return _RecordingTransaction(self)


class _RecordingWriter(_Neo4jWriteMixin):
    def __init__(self) -> None:
        self.session = _RecordingSession()

    def _session(self) -> _RecordingSession:
        return self.session


@pytest.mark.asyncio
async def test_upsert_relation_uses_separate_match_clauses() -> None:
    """Relation writes should avoid Neo4j disconnected-pattern warnings."""
    writer = _RecordingWriter()

    await writer.upsert_relation("doc", "CONTAINS", "chapter", {"rank": 1})

    assert len(writer.session.calls) == 1
    query, params = writer.session.calls[0]
    assert "MATCH (a {id: rel.from_id})" in query
    assert "MATCH (b {id: rel.to_id})" in query
    assert "MERGE (a)-[r:`CONTAINS`]->(b)" in query
    assert "SET r += rel.props" in query
    assert params == {
        "batch": [{"from_id": "doc", "to_id": "chapter", "props": {"rank": 1}}]
    }


@pytest.mark.asyncio
async def test_upsert_argument_components_default_omits_empty_maps() -> None:
    """Default TheoryAtom nodes should omit empty dicts and collections.

    Ensures that empty defaults (e.g. parameters={}, measurements=[]) do not
    pass through into Cypher as Map{}, preventing CypherTypeError.
    """
    from episteme_pipeline.contracts.domain import TheoryAtom

    writer = _RecordingWriter()
    atom = TheoryAtom(
        id="atom_default",
        text="A test premise text.",
        component_type="EMPIRICAL_OBSERVATION",
        source_chunk_id="chk_1",
        confidence=0.9,
        plausibility=0.85,
        entity_ids=["e1", "e2"],
    )

    await writer.upsert_argument_components([atom])

    assert len(writer.session.calls) == 1
    query, params = writer.session.calls[0]
    assert "UNWIND $batch AS comp" in query
    batch = params["batch"]
    assert len(batch) == 1
    props = batch[0]["props"]

    # parameters, measurements, and tenability should NOT be present
    assert "parameters" not in props
    assert "measurements" not in props
    assert "tenability" not in props

    # Primitives and list of primitives should remain intact
    assert props["text"] == "A test premise text."
    assert props["component_type"] == "EMPIRICAL_OBSERVATION"
    assert props["source_chunk_id"] == "chk_1"
    assert props["confidence"] == 0.9
    assert props["plausibility"] == 0.85
    assert props["entity_ids"] == ["e1", "e2"]


@pytest.mark.asyncio
async def test_upsert_argument_components_serializes_complex_fields() -> None:
    """Populated complex fields on TheoryAtom should serialize to JSON strings.

    Ensures that parameters, measurements, and tenability are safely written
    as JSON strings so they persist in Neo4j without violating property type rules.
    """
    import json
    from episteme_pipeline.contracts.domain import Measurement, TenabilityResult, TheoryAtom

    writer = _RecordingWriter()
    atom = TheoryAtom(
        id="atom_enriched",
        text="Enriched observation unit.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chk_2",
        confidence=0.95,
        plausibility=0.9,
        entity_ids=["e1"],
        parameters={"DopamineDepletion": 0.8, "scale": 1.2},
        measurements=[Measurement(dimension="dopamine", value=0.7, unit="ratio")],
        tenability=TenabilityResult(
            local_score=0.9,
            edge_scores={"edge_1": 0.85},
            aggregated_score=0.88,
            is_tenable=True,
            tightest_blur=0.05,
            anomalies=["minor_deviation"],
        ),
    )

    await writer.upsert_argument_components([atom])

    assert len(writer.session.calls) == 1
    _, params = writer.session.calls[0]
    props = params["batch"][0]["props"]

    assert isinstance(props["parameters"], str)
    assert json.loads(props["parameters"]) == {"DopamineDepletion": 0.8, "scale": 1.2}

    assert isinstance(props["measurements"], str)
    meas_data = json.loads(props["measurements"])
    assert len(meas_data) == 1
    assert meas_data[0]["dimension"] == "dopamine"
    assert meas_data[0]["value"] == 0.7

    assert isinstance(props["tenability"], str)
    tenab_data = json.loads(props["tenability"])
    assert tenab_data["local_score"] == 0.9
    assert tenab_data["is_tenable"] is True


def test_writable_props_sanitization() -> None:
    """Direct verification of _writable_props with various property types."""
    import json
    from episteme_pipeline.graph.neo4j_store import _writable_props

    raw = {
        "text": "valid string",
        "count": 42,
        "ratio": 3.14,
        "flag": True,
        "none_val": None,
        "empty_dict": {},
        "filled_dict": {"k": "v"},
        "primitive_list": ["a", "b"],
        "empty_list": [],
        "complex_list": [{"inner": 1}],
    }

    cleaned = _writable_props(raw)

    assert cleaned["text"] == "valid string"
    assert cleaned["count"] == 42
    assert cleaned["ratio"] == 3.14
    assert cleaned["flag"] is True
    assert "none_val" not in cleaned
    assert "empty_dict" not in cleaned
    assert cleaned["filled_dict"] == json.dumps({"k": "v"})
    assert cleaned["primitive_list"] == ["a", "b"]
    assert cleaned["empty_list"] == []
    assert cleaned["complex_list"] == json.dumps([{"inner": 1}])


@pytest.mark.asyncio
async def test_get_theory_atoms_deserialization() -> None:
    """Verify that get_theory_atoms reconstructs complex objects from JSON."""
    import json
    from episteme_pipeline.graph.neo4j_store import _Neo4jReadMixin

    class _MockResult:
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        async def data(self) -> list[dict]:
            return self._data

    class _MockReadSession:
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        async def __aenter__(self) -> "_MockReadSession":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def run(self, query: str, **params) -> _MockResult:
            return _MockResult(self._data)

    class _MockReader(_Neo4jReadMixin):
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        def _session(self) -> _MockReadSession:
            return _MockReadSession(self._data)

    mock_row = {
        "id": "atom_read_1",
        "text": "Read premise text",
        "component_type": "TheoreticalHypothesis",
        "source_chunk_id": "chk_10",
        "confidence": 0.88,
        "plausibility": 0.82,
        "epistemic_status": "Synthetisch",
        "scope_type": "Essentieller Allsatz",
        "entity_ids": ["ent_1", "ent_2"],
        "parameters": json.dumps({"Dopamine": 0.5}),
        "measurements": json.dumps([{"dimension": "flow", "value": 1.2, "unit": "ml/s"}]),
        "tenability": json.dumps({
            "local_score": 0.95,
            "edge_scores": {},
            "aggregated_score": 0.95,
            "is_tenable": True,
            "tightest_blur": 0.02,
            "anomalies": [],
        }),
    }

    reader = _MockReader([mock_row])
    atoms = await reader.get_theory_atoms()

    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.id == "atom_read_1"
    assert atom.entity_ids == ["ent_1", "ent_2"]
    assert atom.parameters == {"Dopamine": 0.5}
    assert len(atom.measurements) == 1
    assert atom.measurements[0].dimension == "flow"
    assert atom.measurements[0].value == 1.2
    assert atom.measurements[0].unit == "ml/s"
    assert atom.tenability is not None
    assert atom.tenability.is_tenable is True
    assert atom.tenability.local_score == 0.95


def test_heterogeneous_lists_are_serialized_to_json() -> None:
    """Heterogeneous lists must serialize to JSON to prevent Neo4j array type errors."""
    import json
    from episteme_pipeline.graph.neo4j_store import _serialize_prop_value

    # Mixed primitive types
    assert _serialize_prop_value([1, "text"]) == json.dumps([1, "text"])
    assert _serialize_prop_value([True, 1]) == json.dumps([True, 1])
    assert _serialize_prop_value([1.5, "str"]) == json.dumps([1.5, "str"])

    # Homogeneous primitive types remain lists
    assert _serialize_prop_value(["a", "b"]) == ["a", "b"]
    assert _serialize_prop_value([1, 2, 3]) == [1, 2, 3]
    assert _serialize_prop_value([1.0, 2.5]) == [1.0, 2.5]
    assert _serialize_prop_value([True, False]) == [True, False]


@pytest.mark.asyncio
async def test_upsert_argument_components_omits_empty_entity_ids() -> None:
    """Empty entity_ids list should be omitted so it does not overwrite existing links."""
    from episteme_pipeline.contracts.domain import TheoryAtom

    writer = _RecordingWriter()
    atom = TheoryAtom(
        id="atom_no_entities",
        text="Premise without entities",
        component_type="CLAIM",
        source_chunk_id="chk_x",
        entity_ids=[],
    )
    await writer.upsert_argument_components([atom])
    props = writer.session.calls[0][1]["batch"][0]["props"]
    assert "entity_ids" not in props


@pytest.mark.asyncio
async def test_get_theory_atoms_resilient_deserialization() -> None:
    """Verify that get_theory_atoms gracefully handles non-string and malformed inputs."""
    from episteme_pipeline.contracts.domain import Measurement
    from episteme_pipeline.graph.neo4j_store import _Neo4jReadMixin

    class _MockResult:
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        async def data(self) -> list[dict]:
            return self._data

    class _MockReadSession:
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        async def __aenter__(self) -> "_MockReadSession":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def run(self, query: str, **params) -> _MockResult:
            return _MockResult(self._data)

    class _MockReader(_Neo4jReadMixin):
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        def _session(self) -> _MockReadSession:
            return _MockReadSession(self._data)

    row = {
        "id": "atom_resilient",
        "text": "Resilient premise",
        "component_type": "HYPOTHESIS",
        "source_chunk_id": "chk_r",
        "entity_ids": None,
        "parameters": "not a json string {",
        "measurements": [Measurement(dimension="d", value=1.0, unit="u")],
        "tenability": {
            "local_score": 0.8,
            "edge_scores": {},
            "aggregated_score": 0.8,
            "is_tenable": True,
            "tightest_blur": 0.01,
            "anomalies": [],
        },
    }

    reader = _MockReader([row])
    atoms = await reader.get_theory_atoms()
    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.parameters == {}
    assert len(atom.measurements) == 1
    assert atom.measurements[0].dimension == "d"
    assert atom.tenability is not None
    assert atom.tenability.local_score == 0.8


@pytest.mark.asyncio
async def test_get_all_theory_relations_includes_tenability() -> None:
    """Verify get_all_theory_relations captures the tenability property."""
    from episteme_pipeline.graph.neo4j_store import _Neo4jReadMixin

    class _MockResult:
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        async def data(self) -> list[dict]:
            return self._data

    class _MockReadSession:
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        async def __aenter__(self) -> "_MockReadSession":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def run(self, query: str, **params) -> _MockResult:
            assert "r.tenability as tenability" in query
            return _MockResult(self._data)

    class _MockReader(_Neo4jReadMixin):
        def __init__(self, data: list[dict]) -> None:
            self._data = data

        def _session(self) -> _MockReadSession:
            return _MockReadSession(self._data)

    row = {
        "source_id": "a1",
        "target_id": "a2",
        "relation_type": "SUPPORTS",
        "confidence": 0.9,
        "scope": "local",
        "weight": 0.7,
        "tenability": 0.85,
    }
    reader = _MockReader([row])
    rels = await reader.get_all_theory_relations()
    assert len(rels) == 1
    assert rels[0].tenability == 0.85


@pytest.mark.asyncio
async def test_mark_chunks_processed_sanitizes_phase_identifier() -> None:
    """Ensure mark_chunks_processed rejects invalid Cypher identifiers."""
    import pytest
    from episteme_pipeline.graph.neo4j_store import _Neo4jCheckpointMixin

    class _MockCheckpointStore(_Neo4jCheckpointMixin):
        def _session(self):
            return None

    store = _MockCheckpointStore()
    with pytest.raises(ValueError, match="Unsafe Cypher property name"):
        await store.mark_chunks_processed(["chk_1"], "phase; DROP TABLE chunks--")


@pytest.mark.asyncio
async def test_item_checkpoints_sanitize_phase_identifier() -> None:
    """Ensure filter_unprocessed_items, commit_phase_batch, clear_phase_checkpoints reject unsafe phase names."""
    from episteme_pipeline.graph.neo4j_store import _Neo4jCheckpointMixin
    from episteme_pipeline.contracts.domain import PhaseItemRecord

    class _MockCheckpointStore(_Neo4jCheckpointMixin):
        def _session(self):
            return None

    store = _MockCheckpointStore()
    unsafe = "phase; DROP TABLE chunks--"
    with pytest.raises(ValueError, match="Unsafe Cypher phase identifier"):
        await store.filter_unprocessed_items(["k1"], unsafe)

    with pytest.raises(ValueError, match="Unsafe Cypher phase identifier"):
        await store.commit_phase_batch(
            unsafe, triples=[], items=[PhaseItemRecord(key="k1", status="completed")]
        )

    with pytest.raises(ValueError, match="Unsafe Cypher phase identifier"):
        await store.clear_phase_checkpoints(unsafe)

