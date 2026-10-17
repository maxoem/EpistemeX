"""
Deterministic unit tests for ISSUE-064 remediation.

Covers:
1. Phase4Runner empty chunks run completes cleanly without UnboundLocalError.
2. TAGARCClassifier queries graph_store directly without _component_as_entity or global_extractor.
3. TheoreticalEnrichmentRunner two-pass parameter projection order invariance.
4. TenabilitySolver edge tenability with zero hardcoded psychology/neuroscience strings.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import TheoreticalEnrichmentArtifact
from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import (
    SubGraph,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase4_argument_mining.arc_classifier import (
    TAGARCClassifier,
)
from episteme_pipeline.post_processing.theoretical_enrichment import (
    EmpiricalCluster,
    TheoreticalEnrichmentRunner,
    TheoryElementDefinition,
    TheoryRegistry,
)
from episteme_pipeline.post_processing.theoretical_enrichment.solvers import (
    TenabilitySolver,
)
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


# ---------------------------------------------------------------------------
# Defect 1: Phase4Runner Empty Chunks UnboundLocalError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase4_empty_chunks_no_unbound_local_error() -> None:
    """Verify Phase4Runner completes without UnboundLocalError when chunks is empty."""
    graph_store = AsyncMock()
    graph_store.get_existing_chunk_ids.return_value = set()
    graph_store.get_unprocessed_chunks.return_value = []
    graph_store.get_chunks.return_value = []
    graph_store.get_theory_atoms.return_value = []

    runner = Phase4Runner(
        config=Phase4Config(batch_size=5),
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=None,
        graph_store=graph_store,
        adu_segmenter=MagicMock(),
        acc_classifier=MagicMock(),
        global_extractor=None,
    )

    empty_view = Phase3ArtifactsView(global_triples=[], relation_type_distribution={}, chunks=[])
    ctx = ArtifactExecutionContext(run_id="run_empty", manifest=None, pipeline_input=None)

    collection = await runner.run(empty_view, ctx)
    assert len(collection.artifacts) == 0


# ---------------------------------------------------------------------------
# Defect 2: TAGARCClassifier Direct Graph Neighborhood & Decoupling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tag_arc_classifier_direct_graph_store_neighborhood() -> None:
    """Verify TAGARCClassifier fetches neighborhoods directly from graph_store."""
    llm = AsyncMock()
    embedding_model = AsyncMock()
    embedding_model.aget_text_embedding_batch.return_value = [[1.0, 0.0], [1.0, 0.0]]

    classifier = TAGARCClassifier(
        llm=llm,
        embedding_model=embedding_model,
        subgraph_depth=1,
        confidence_threshold=0.5,
    )

    atom_a = TheoryAtom(
        id="atom_1",
        text="Premise A",
        component_type="PREMISE",
        source_chunk_id="chk_1",
    )
    atom_b = TheoryAtom(
        id="atom_2",
        text="Claim B",
        component_type="CLAIM",
        source_chunk_id="chk_2",
    )

    graph_store = AsyncMock()
    graph_store.get_neighborhood.side_effect = lambda node_id, depth: SubGraph(
        center_id=node_id, nodes=[], triples=[], depth=depth
    )

    from episteme_pipeline.phases.phase4_argument_mining.models import (
        ARCRelationOutput,
    )

    llm.predict_structured.return_value = ARCRelationOutput(
        relation_type="SUPPORTS_ARG",
        direction="A_to_B",
        confidence=0.88,
        weight=0.88,
    )

    # Classify pair without global_extractor
    rel = await classifier._classify_pair(
        component_a=atom_a,
        component_b=atom_b,
        graph_store=graph_store,
        schema=DEFAULT_SCHEMA,
        global_extractor=None,
    )

    assert rel is not None
    assert rel.source_id == "atom_1"
    assert rel.target_id == "atom_2"
    assert rel.relation_type == "SUPPORTS_ARG"

    # Verify graph_store.get_neighborhood was called directly with atom IDs
    call_ids = [call.args[0] for call in graph_store.get_neighborhood.call_args_list]
    assert "atom_1" in call_ids
    assert "atom_2" in call_ids


# ---------------------------------------------------------------------------
# Defect 3: TheoreticalEnrichmentRunner Two-Pass Cluster Order Invariance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_theoretical_enrichment_cluster_order_invariance() -> None:
    """Verify two-pass execution populates all parameters before edge evaluation, ensuring order invariance."""
    theory = TheoryElementDefinition(
        theory_id="test_theory",
        name="test_theory",
        parameter_names=["coherence_level"],
    )

    registry = TheoryRegistry()
    registry.register(theory)

    # Projector assigns different coherence levels based on cluster id
    projector = AsyncMock()
    projector.aproject.side_effect = lambda cluster, th: (
        {"coherence_level": 0.85}
        if cluster.cluster_id == "cluster-1"
        else {"coherence_level": 0.80}
    )

    solver = TenabilitySolver()

    atom1 = TheoryAtom(id="hyp1", text="Hypothesis 1", component_type="CLAIM", source_chunk_id="c1")
    atom2 = TheoryAtom(id="hyp2", text="Hypothesis 2", component_type="CLAIM", source_chunk_id="c2")

    rel = TheoryRelation(
        source_id="hyp1",
        target_id="hyp2",
        relation_type="CONSTRAINS",
        confidence=0.9,
        scope="global",
    )

    cluster1 = EmpiricalCluster(
        cluster_id="cluster-1",
        observations=[atom1],
        claimant_theory_ids=["test_theory"],
        relations=[rel],
    )
    cluster2 = EmpiricalCluster(
        cluster_id="cluster-2",
        observations=[atom2],
        claimant_theory_ids=["test_theory"],
        relations=[],
    )

    runner = TheoreticalEnrichmentRunner(
        registry=registry,
        projector=projector,
        solver=solver,
        graph_store=None,
    )

    # Run Order A: [cluster1, cluster2]
    with patch.object(runner, "_identify_empirical_clusters", return_value=[cluster1, cluster2]):
        view_a = Phase4ArtifactsView(
            theory_atoms=[atom1, atom2],
            theory_relations=[rel],
        )
        ctx = ArtifactExecutionContext(run_id="run_a", manifest=None, pipeline_input=None)
        res_a = await runner.run(view_a, ctx)
        edge_tenabilities_a = [
            a.payload.edge_tenabilities
            for a in res_a.artifacts
            if isinstance(a.payload, TheoreticalEnrichmentArtifact)
        ]

    # Run Order B: [cluster2, cluster1]
    with patch.object(runner, "_identify_empirical_clusters", return_value=[cluster2, cluster1]):
        view_b = Phase4ArtifactsView(
            theory_atoms=[atom1, atom2],
            theory_relations=[rel],
        )
        ctx = ArtifactExecutionContext(run_id="run_b", manifest=None, pipeline_input=None)
        res_b = await runner.run(view_b, ctx)
        edge_tenabilities_b = [
            a.payload.edge_tenabilities
            for a in res_b.artifacts
            if isinstance(a.payload, TheoreticalEnrichmentArtifact)
        ]

    rel_key = f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"
    score_a = next(scores[rel_key] for scores in edge_tenabilities_a if rel_key in scores)
    score_b = next(scores[rel_key] for scores in edge_tenabilities_b if rel_key in scores)

    # In single-pass execution, score_a had target_params={} (delta_c=0.0 -> ts_edge=1.0)
    # whereas with populated target_params, delta_c = abs(0.85 - 0.80) = 0.05 -> ts_edge = 0.95!
    # Crucially, score_a must equal score_b in two-pass execution.
    assert score_a == score_b
    assert score_a == pytest.approx(0.95, abs=0.01)


# ---------------------------------------------------------------------------
# Defect 4: TenabilitySolver Zero Hardcoded Psychology Strings
# ---------------------------------------------------------------------------


def test_tenability_solver_zero_hardcoded_parameter_strings() -> None:
    """Verify TenabilitySolver contains no hardcoded psychology/neuroscience strings and evaluates generic parameters."""
    solver = TenabilitySolver()
    rel = TheoryRelation(
        source_id="h1",
        target_id="h2",
        relation_type="CONSTRAINS",
        confidence=1.0,
        scope="global",
    )

    # 1. Functional generic test: evaluate two arbitrary domain parameters
    ts_edge, delta_c, anoms = solver.solve_edge_tenability(
        source_params={"UniversalCouplingConstant": 0.82},
        target_params={"ElectroweakSymmetryBlur": 0.78},
        relation=rel,
    )
    assert delta_c == pytest.approx(0.04, abs=0.001)
    assert ts_edge == pytest.approx(0.96, abs=0.001)
    assert len(anoms) == 0

    # 2. Structural assertion: ensure forbidden strings are not present in solver source
    source_code = inspect.getsource(TenabilitySolver)
    forbidden_tokens = ["RepressionMagnitude", "AmygdalaHyperactivity", "DopamineDepletion"]
    for token in forbidden_tokens:
        assert token not in source_code, f"Found forbidden hardcoded token '{token}' in TenabilitySolver source"
