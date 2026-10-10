from __future__ import annotations

import json

from episteme_pipeline.contracts.domain import L2Entity, L2Triple, SubGraph
from episteme_pipeline.prompts.input_formatters import (
    InputFormatStrategy,
    format_subgraph_envelope,
)


def test_format_subgraph_envelope_json() -> None:
    env_a = SubGraph(
        center_id="e1",
        nodes=[L2Entity(id="e1", label="CONCEPT", name="Dog", description="A good boy")],
        triples=[],
        depth=1,
    )
    env_b = SubGraph(
        center_id="e2",
        nodes=[L2Entity(id="e2", label="CONCEPT", name="Cat", description="A bad boy")],
        triples=[
            L2Triple(
                subject_id="e1",
                predicate="CHASES",
                object_id="e2",
                confidence=1.0,
                scope="local",
            )
        ],
        depth=1,
    )

    out = format_subgraph_envelope(env_a, env_b, strategy=InputFormatStrategy.JSON)
    data = json.loads(out)
    
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    
    node_names = [n["name"] for n in data["nodes"]]
    assert "Dog" in node_names
    assert "Cat" in node_names
    
    edge = data["edges"][0]
    assert edge["subject"] == "e1"
    assert edge["predicate"] == "CHASES"
    assert edge["object"] == "e2"


def test_format_subgraph_envelope_text() -> None:
    env_a = SubGraph(
        center_id="e1",
        nodes=[L2Entity(id="e1", label="CONCEPT", name="Dog")],
        triples=[],
        depth=1,
    )
    env_b = SubGraph(
        center_id="e2",
        nodes=[],
        triples=[],
        depth=1,
    )

    out = format_subgraph_envelope(
        env_a, env_b, strategy=InputFormatStrategy.TEXT, include_description=False
    )
    assert "[CONCEPT] Dog" in out


def test_format_empty_envelope_json() -> None:
    env = SubGraph(center_id="e1", nodes=[], triples=[], depth=1)
    out = format_subgraph_envelope(env, env, strategy=InputFormatStrategy.JSON)
    
    data = json.loads(out)
    assert data.get("message") == "No graph context available."
