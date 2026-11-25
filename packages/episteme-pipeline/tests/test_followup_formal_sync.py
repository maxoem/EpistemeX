"""Tests verifying formal-model follow-up synchronization in episteme-pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from episteme_pipeline.artifacts.builders import build_theory_atom_artifact
from episteme_pipeline.artifacts.codecs import TheoryAtomCodec
from episteme_pipeline.artifacts.execution import Phase4ArtifactsView
from episteme_pipeline.contracts.domain import (
    SemanticSentenceType,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.graph.theory_graph_mapper import theory_atom_to_graph_properties
from episteme_pipeline.phases.phase5_fusion.leiden_clustering import (
    LeidenTheoryClustering,
)
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


def test_default_schema_entails_distinct_and_asipc_triad_and_alternative_reading() -> None:
    """C-04 & C-05: ENTAILS has its own definition, ASPIC+ triad & ALTERNATIVE_READING_OF exist."""
    defs = DEFAULT_SCHEMA.argument_relation_definitions
    assert defs["ENTAILS"] != defs["REDUCES_TO"]
    assert "deductive" in defs["ENTAILS"].lower() or "follows" in defs["ENTAILS"].lower()

    for rel in ("REBUTS", "UNDERCUTS", "UNDERMINES", "ALTERNATIVE_READING_OF"):
        assert rel in DEFAULT_SCHEMA.argument_relation_types
        assert rel in defs

    assert DEFAULT_SCHEMA.relation_polarities["ALTERNATIVE_READING_OF"] == 0
    assert DEFAULT_SCHEMA.relation_polarities["REBUTS"] == -1
    assert DEFAULT_SCHEMA.relation_polarities["UNDERMINES"] == -1
    assert DEFAULT_SCHEMA.relation_polarities["UNDERCUTS"] == -1

    # Non-factive L2 REFUTES phrasing
    assert (
        "non-factive" in DEFAULT_SCHEMA.relation_definitions["REFUTES"].lower()
        or "challenges" in DEFAULT_SCHEMA.relation_definitions["REFUTES"].lower()
    )


def test_theory_atom_reading_id_and_semantic_sentence_type_roundtrip() -> None:
    """C-04 & C-05: reading_id and semantic_sentence_type round-trip through codecs, builders, mappers."""
    atom = TheoryAtom(
        id="atom_map_1",
        text="Force equals mass times acceleration as measured on calibrated balances.",
        component_type="Claim",
        source_chunk_id="chunk_1",
        document_id="doc_1",
        reading_id="reading_newton_strict",
        semantic_sentence_type=SemanticSentenceType.MIXED,
        modal_prior=0.9,
        local_tenability=0.8,
    )

    payload = TheoryAtomCodec.to_payload(atom)
    assert payload.reading_id == "reading_newton_strict"
    assert payload.semantic_sentence_type == SemanticSentenceType.MIXED

    hydrated = TheoryAtomCodec.to_domain(payload)
    assert hydrated.reading_id == "reading_newton_strict"
    assert hydrated.semantic_sentence_type == SemanticSentenceType.MIXED

    envelope = build_theory_atom_artifact(
        atom,
        run_id="run_test",
        phase_name="phase4",
        method="test_method",
    )
    assert envelope.payload.reading_id == "reading_newton_strict"
    assert envelope.payload.semantic_sentence_type == SemanticSentenceType.MIXED

    props = theory_atom_to_graph_properties(atom)
    assert props["reading_id"] == "reading_newton_strict"
    assert props["semantic_sentence_type"] == "MIXED"


def test_theory_atom_effective_base_prior_policies() -> None:
    """C-03: effective_base_prior respects descriptive, uniform, and Data-Priority modes."""
    obs = TheoryAtom(
        id="obs_1",
        text="Measured perihelion shift is 43 arcseconds per century.",
        component_type="ObservationUnit",
        source_chunk_id="chunk_1",
        document_id="doc_1",
        modal_prior=0.3,
        local_tenability=1.0,
    )
    claim = TheoryAtom(
        id="claim_1",
        text="Spacetime curvature causes perihelion precession.",
        component_type="Claim",
        source_chunk_id="chunk_1",
        document_id="doc_1",
        modal_prior=0.95,
        local_tenability=1.0,
    )

    assert obs.effective_base_prior(base_prior_policy="descriptive_authorial") == pytest.approx(0.3)
    assert claim.effective_base_prior(base_prior_policy="descriptive_authorial") == pytest.approx(0.95)

    assert obs.effective_base_prior(base_prior_policy="normative_uniform") == pytest.approx(0.5)
    assert claim.effective_base_prior(base_prior_policy="normative_uniform") == pytest.approx(0.5)

    assert obs.effective_base_prior(
        base_prior_policy="normative_data_priority",
        normative_data_prior=0.85,
        normative_hypothesis_prior=0.5,
    ) == pytest.approx(0.85)
    assert claim.effective_base_prior(
        base_prior_policy="normative_data_priority",
        normative_data_prior=0.85,
        normative_hypothesis_prior=0.5,
    ) == pytest.approx(0.5)


def test_theorynet_projector_normative_policy_and_skips_alternative_reading() -> None:
    """C-03 & C-04: Projector applies normative base_prior_policy and excludes ALTERNATIVE_READING_OF."""
    atoms = [
        TheoryAtom(
            id="obs",
            text="Empirical observation.",
            component_type="ObservationUnit",
            source_chunk_id="c1",
            document_id="d1",
            modal_prior=0.3,
        ),
        TheoryAtom(
            id="hedged_supported",
            text="Cautiously phrased supported thesis.",
            component_type="Claim",
            source_chunk_id="c1",
            document_id="d1",
            modal_prior=0.35,
            reading_id="r1",
        ),
        TheoryAtom(
            id="bold_ungrounded",
            text="Dogmatically phrased unsupported thesis.",
            component_type="Claim",
            source_chunk_id="c1",
            document_id="d1",
            modal_prior=0.95,
            reading_id="r2",
        ),
    ]
    relations = [
        TheoryRelation(
            id="rel_supp",
            source_id="obs",
            target_id="hedged_supported",
            relation_type="SUPPORTS",
            confidence=0.95,
            scope="local",
        ),
        TheoryRelation(
            id="rel_alt",
            source_id="bold_ungrounded",
            target_id="hedged_supported",
            relation_type="ALTERNATIVE_READING_OF",
            confidence=1.0,
            scope="local",
        ),
    ]
    view = Phase4ArtifactsView(
        theory_atoms=atoms,
        theory_relations=relations,
    )

    proj_desc = TheoryNetProjector(base_prior_policy="descriptive_authorial")
    net_desc = proj_desc.project(view)

    proj_norm = TheoryNetProjector(base_prior_policy="normative_data_priority")
    net_norm = proj_norm.project(view)

    desc_by_id = {a.id: a for a in net_desc.atoms}
    norm_by_id = {a.id: a for a in net_norm.atoms}

    # Under descriptive priors, bold_ungrounded outranks hedged_supported
    assert (desc_by_id["bold_ungrounded"].equilibrium_strength or 0.0) > (
        desc_by_id["hedged_supported"].equilibrium_strength or 0.0
    )
    # Under normative Data-Priority priors, evidence-backed thesis outranks ungrounded bold thesis
    assert (norm_by_id["hedged_supported"].equilibrium_strength or 0.0) > (
        norm_by_id["bold_ungrounded"].equilibrium_strength or 0.0
    )
    # ALTERNATIVE_READING_OF must be excluded from dialectical edges
    projected_edges = proj_norm._to_theory_edges(relations)
    assert len(projected_edges) == 1
    assert projected_edges[0].target == "hedged_supported"
    assert projected_edges[0].polarity == 1


@pytest.mark.asyncio
async def test_leiden_clustering_support_only_excludes_adversarial_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-06: support_only Leiden separates rival clusters linked only by ATTACKS and stores q_c."""
    import sys
    import types
    from dataclasses import dataclass

    import networkx as nx

    @dataclass
    class _FakeCluster:
        level: int
        cluster: int
        node: str

    def _fake_hierarchical_leiden(g: nx.Graph, max_cluster_size: int = 100, resolution: float = 1.0):
        # Verify negative-polarity ATTACKS/REBUTS edges were excluded from cluster_g
        for u, v in g.edges():
            assert u[0] == v[0], f"Adversarial cross-camp edge leaked into support_only graph: {(u, v)}"
        comms = nx.community.louvain_communities(g, weight="weight", resolution=resolution, seed=42)
        out = []
        for cid, members in enumerate(comms):
            for node in members:
                out.append(_FakeCluster(level=0, cluster=cid, node=str(node)))
        return out

    fake_grasp = types.ModuleType("graspologic")
    fake_part = types.ModuleType("graspologic.partition")
    fake_part.hierarchical_leiden = _fake_hierarchical_leiden  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "graspologic", fake_grasp)
    monkeypatch.setitem(sys.modules, "graspologic.partition", fake_part)

    atoms = [
        TheoryAtom(
            id=f"a{i}",
            text=f"Camp A claim {i}",
            component_type="Claim",
            source_chunk_id="c1",
            document_id="d1",
        )
        for i in range(3)
    ] + [
        TheoryAtom(
            id=f"b{i}",
            text=f"Camp B claim {i}",
            component_type="Claim",
            source_chunk_id="c1",
            document_id="d1",
        )
        for i in range(3)
    ]
    relations = [
        TheoryRelation(id="sa1", source_id="a0", target_id="a1", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        TheoryRelation(id="sa2", source_id="a1", target_id="a2", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        TheoryRelation(id="sa3", source_id="a2", target_id="a0", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        TheoryRelation(id="sb1", source_id="b0", target_id="b1", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        TheoryRelation(id="sb2", source_id="b1", target_id="b2", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        TheoryRelation(id="sb3", source_id="b2", target_id="b0", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        # Strong attacks between A and B must NOT merge them under support_only
        TheoryRelation(id="att1", source_id="a0", target_id="b0", relation_type="ATTACKS", confidence=1.0, scope="local"),
        TheoryRelation(id="att2", source_id="a1", target_id="b1", relation_type="REBUTS", confidence=1.0, scope="local"),
        TheoryRelation(id="att3", source_id="a2", target_id="b2", relation_type="ATTACKS", confidence=1.0, scope="local"),
    ]

    graph_store = MagicMock()
    graph_store.get_theory_atoms = AsyncMock(return_value=atoms)
    graph_store.get_all_theory_relations = AsyncMock(return_value=relations)
    graph_store.upsert_communities = AsyncMock(return_value=None)

    leiden = LeidenTheoryClustering(
        max_cluster_size=10,
        cluster_layer="theory_atoms",
        edge_projection="support_only",
        resolution=1.0,
    )
    await leiden.fuse(graph_store)

    assert graph_store.upsert_communities.await_count >= 1
    batches = [
        item
        for call in graph_store.upsert_communities.await_args_list
        for item in call.args[0]
    ]
    member_sets = [set(item["entity_ids"]) for item in batches]
    for item in batches:
        assert item["edge_projection"] == "support_only"
        assert "modularity_contribution" in item
    assert {"a0", "a1", "a2"} in member_sets
    assert {"b0", "b1", "b2"} in member_sets
