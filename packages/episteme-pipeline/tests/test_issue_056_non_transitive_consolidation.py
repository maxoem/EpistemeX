"""Tests for ISSUE-056: Non-transitive consolidation and compositional conformal risk control.

Verifies:
1. Phase 3b (LatentGraphConsolidation) and Phase 5 (EmbeddingArgumentClustering) enforce diameter
   and minimum-internal-similarity constraints (clique_constrained_components) during cluster formation
   to prevent single-linkage bridge chaining (A ~ B ~ C where A !~ C).
2. DecisionEngineConfig and ConformalCalibrator support per-phase / per-task alpha_m allocation
   derived from a global pipeline risk budget alpha_global via weighted union bounds.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from episteme_pipeline.config import DecisionEngineConfig
from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.phases.phase3b_consolidation.consolidation import (
    LatentGraphConsolidation,
)
from episteme_pipeline.phases.phase5_fusion.argument_clustering import (
    EmbeddingArgumentClustering,
)
from episteme_pipeline.utils.graph_algorithms import (
    clique_constrained_components,
    union_find_components,
)

# ---------------------------------------------------------------------------
# Criterion 1: Prevention of Single-Linkage Chaining via Clique Constraints
# ---------------------------------------------------------------------------


def test_clique_constrained_components_blocks_bridge_chaining():
    """Verify clique_constrained_components prevents bridge chaining A ~ B ~ C when A !~ C."""
    # 3 nodes: 0, 1, 2
    # Pair similarities: (0, 1) = 0.90, (1, 2) = 0.88, (0, 2) = 0.30
    sim_matrix = np.array([
        [1.00, 0.90, 0.30],
        [0.90, 1.00, 0.88],
        [0.30, 0.88, 1.00],
    ])
    edges = [(0, 1), (1, 2)]

    # Unconstrained Union-Find merges all 3 into a single giant component [0, 1, 2]
    uf_clusters = union_find_components(3, edges)
    assert len(uf_clusters) == 1
    assert sorted(uf_clusters[0]) == [0, 1, 2]

    # Clique-constrained components with min_internal_similarity=0.70 prevents merging (1, 2) into {0, 1}
    # because min(sim(0, 2)) = 0.30 < 0.70
    clique_clusters = clique_constrained_components(
        3, edges, sim_matrix, min_internal_similarity=0.70
    )
    assert len(clique_clusters) == 2
    cluster_sets = [set(c) for c in clique_clusters]
    # Cluster {0, 1} formed first by greedy descending weight 0.90, leaving {2} alone
    assert {0, 1} in cluster_sets
    assert {2} in cluster_sets


@pytest.mark.asyncio
async def test_phase3b_consolidation_enforces_clique_constraints():
    """Verify LatentGraphConsolidation does not collapse non-similar entities through a polysemous bridge."""
    # Entities: e0 (Kant), e1 (Bridge), e2 (Hume)
    # e0 ~ e1 (0.90), e1 ~ e2 (0.89), but e0 !~ e2 (0.20)
    e0 = L2Entity(id="e0", name="Kant", label="Person", source_chunk_ids=["c1"])
    e1 = L2Entity(id="e1", name="Bridge Thinker", label="Person", source_chunk_ids=["c1"])
    e2 = L2Entity(id="e2", name="Hume", label="Person", source_chunk_ids=["c1"])

    store = AsyncMock()
    store.get_entities.return_value = [e0, e1, e2]

    neighborhood = MagicMock()
    neighborhood.nodes = []
    neighborhood.triples = []
    store.get_neighborhood.return_value = neighborhood

    embedding_model = AsyncMock()
    # Mock embeddings such that sim(0, 1) = 0.90, sim(1, 2) = 0.89, sim(0, 2) = 0.20
    # Provide explicit custom 3-vector embedding batch:
    embedding_model.aget_text_embedding_batch.return_value = [
        [1.0, 0.0, 0.0],
        [0.86, 0.51, 0.0],  # dot(v0, v1) = 0.86
        [0.30, 0.85, 0.43],  # dot(v0, v2) = 0.30, dot(v1, v2) ~ 0.86*0.3 + 0.51*0.85 = 0.258 + 0.4335 = 0.69
    ]

    consolidation = LatentGraphConsolidation(
        embedding_model=embedding_model,
        dense_similarity_threshold=0.85,
        relation_overlap_threshold=0.0,
        min_internal_similarity=0.75,
        use_csls=False,
    )

    fused_map = await consolidation.fuse(store)

    # e0 and e2 must NEVER be mapped to the same canonical entity
    canon_e0 = fused_map.get("e0", "e0")
    canon_e2 = fused_map.get("e2", "e2")
    assert canon_e0 != canon_e2


@pytest.mark.asyncio
async def test_phase5_argument_clustering_enforces_clique_constraints():
    """Verify EmbeddingArgumentClustering enforces min_internal_similarity during cluster formation."""
    # 3 TheoryAtoms: a0, a1, a2
    a0 = TheoryAtom(id="a0", text="Claim A", component_type="CLAIM", source_chunk_id="c1")
    a1 = TheoryAtom(id="a1", text="Claim B", component_type="CLAIM", source_chunk_id="c2")
    a2 = TheoryAtom(id="a2", text="Claim C", component_type="CLAIM", source_chunk_id="c3")

    store = AsyncMock()
    store.get_theory_atoms.return_value = [a0, a1, a2]

    # Craft pairwise similarities: sim(0, 1) = 0.90, sim(1, 2) = 0.88, sim(0, 2) = 0.20
    # Vector embeddings:
    embedding_model = AsyncMock()
    # Normalize:
    v0 = [1.0, 0.0, 0.0]
    v1 = [0.9, 0.43588989, 0.0]  # dot with v0 = 0.90
    # Let's provide vectors with known cosines:
    v2 = [0.2, 0.7, 0.68556]  # dot with v0 = 0.20, dot with v1 = 0.9*0.2 + 0.43588989*0.7 = 0.18 + 0.305 = 0.485
    embedding_model.aget_text_embedding_batch.return_value = [v0, v1, v2]

    clustering = EmbeddingArgumentClustering(
        embedding_model=embedding_model,
        similarity_threshold=0.85,
        min_internal_similarity=0.75,
    )

    clusters = await clustering.cluster(store)

    # Only a0 and a1 should be clustered together; a2 must not be merged
    assert len(clusters) == 1
    assert set(clusters[0]) == {"a0", "a1"}
    assert "a2" not in clusters[0]


# ---------------------------------------------------------------------------
# Criterion 2: Compositional Conformal Risk Control & Alpha Allocation
# ---------------------------------------------------------------------------


def test_decision_engine_config_global_alpha_budget_allocation():
    """Verify DecisionEngineConfig allocates per-phase alpha_m derived from global_alpha."""
    config = DecisionEngineConfig(
        global_alpha=0.05,
        risk_budget_weights={
            "phase2_linking": 0.20,
            "phase3_relations": 0.20,
            "phase3b_consolidation": 0.10,  # Irreversible structural phase gets tighter budget
            "phase4_argument_mining": 0.30,
            "phase5_fusion": 0.20,
        },
    )

    alphas = config.allocate_phase_alphas()

    # Sum of allocated alphas must be <= global_alpha (union bound guarantee)
    total_alpha = sum(alphas.values())
    assert np.isclose(total_alpha, 0.05, atol=1e-6)

    # Phase 3b consolidation gets tighter budget (0.10 * 0.05 = 0.005)
    assert np.isclose(alphas["phase3b_consolidation"], 0.005)
    # Phase 4 argument mining gets larger share (0.30 * 0.05 = 0.015)
    assert np.isclose(alphas["phase4_argument_mining"], 0.015)

    assert np.isclose(config.get_allocated_alpha("phase3b_consolidation"), 0.005)
    # Unweighted phase falls back to default conformal_alpha
    assert np.isclose(config.get_allocated_alpha("unknown_phase"), config.conformal_alpha)


def test_conformal_calibrator_allocate_risk_budget():
    """Verify ConformalCalibrator.allocate_risk_budget computes exact weighted risk allocations."""
    weights = {
        "p2": 1.0,
        "p3b": 0.5,
        "p4": 1.5,
        "p5": 1.0,
    }
    # Total weight = 4.0, global_alpha = 0.08
    allocated = ConformalCalibrator.allocate_risk_budget(global_alpha=0.08, weights=weights)

    assert np.isclose(sum(allocated.values()), 0.08)
    assert np.isclose(allocated["p2"], 0.08 * (1.0 / 4.0))  # 0.02
    assert np.isclose(allocated["p3b"], 0.08 * (0.5 / 4.0))  # 0.01 (tightest)
    assert np.isclose(allocated["p4"], 0.08 * (1.5 / 4.0))  # 0.03

    # Error handling on invalid weights
    with pytest.raises(ValueError, match="strictly positive"):
        ConformalCalibrator.allocate_risk_budget(global_alpha=0.05, weights={"p1": 0.0, "p2": -1.0})


def test_conformal_calibrator_instance_allocated_alpha_lookup():
    """Verify ConformalCalibrator instance get_allocated_alpha integrates with global risk budget."""
    calibrator = ConformalCalibrator(
        alpha=0.05,
        global_alpha=0.04,
        risk_budget_weights={"phase3b": 0.25, "phase4": 0.75},
    )

    assert np.isclose(calibrator.get_allocated_alpha("phase3b"), 0.01)
    assert np.isclose(calibrator.get_allocated_alpha("phase4"), 0.03)
    assert np.isclose(calibrator.get_allocated_alpha("unlisted_phase"), 0.05)

    # Fingerprint includes global_alpha
    fp = calibrator.fingerprint()
    assert fp["global_alpha"] == 0.04
