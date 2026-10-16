"""Deterministic tests for DRY primitives and reflection elimination.

Covers:
- `l2_normalize` and `cosine_similarity_matrix` in `episteme_pipeline.utils.similarity`
- `union_find_components` in `episteme_pipeline.utils.graph_algorithms`
- `CandidateEmbeddingCache` in `episteme_pipeline.phases.phase2_entity_discovery.candidate_cache`
- `stable_component_id` and `build_cross_chunk_candidate_pairs` in `pairing.py`
- `Pipeline.resume_from_run` execution within observability context
- Static AST verification of zero `getattr`/`hasattr` in target packages
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from episteme_pipeline.contracts.domain import L1Chunk, L2Entity, TheoryAtom
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.phases.phase2_entity_discovery.candidate_cache import (
    CandidateEmbeddingCache,
)
from episteme_pipeline.phases.phase4_argument_mining.pairing import (
    build_cross_chunk_candidate_pairs,
    stable_component_id,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.utils.graph_algorithms import union_find_components
from episteme_pipeline.utils.similarity import cosine_similarity_matrix, l2_normalize


def test_l2_normalize_clamping_and_zero_vectors() -> None:
    """Verify l2_normalize handles normal, zero, and near-zero vectors without NaN."""
    # 1. Normal 1D vector
    vec1 = np.array([3.0, 4.0])
    norm1 = l2_normalize(vec1)
    assert norm1.shape == (2,)
    assert np.isclose(np.linalg.norm(norm1), 1.0)
    assert np.allclose(norm1, [0.6, 0.8])

    # 2. Zero 1D vector
    zero_vec = np.array([0.0, 0.0, 0.0])
    norm_zero = l2_normalize(zero_vec)
    assert not np.isnan(norm_zero).any()
    assert np.allclose(norm_zero, [0.0, 0.0, 0.0])

    # 3. 2D matrix with mixed zero and non-zero rows
    mat = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.0, 2.0, 2.0],
    ])
    norm_mat = l2_normalize(mat)
    assert norm_mat.shape == (3, 3)
    assert not np.isnan(norm_mat).any()
    assert np.isclose(np.linalg.norm(norm_mat[0]), 1.0)
    assert np.allclose(norm_mat[1], [0.0, 0.0, 0.0])
    assert np.isclose(np.linalg.norm(norm_mat[2]), 1.0)


def test_cosine_similarity_matrix_pairwise_and_asymmetric() -> None:
    """Verify cosine_similarity_matrix handles 1D/2D shapes and zero-norm vectors."""
    # 1. Single matrix: pairwise self-similarity
    mat = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, 1.0],
    ])
    sim = cosine_similarity_matrix(mat)
    assert sim.shape == (3, 3)
    assert np.allclose(np.diag(sim), 1.0)
    assert np.isclose(sim[0, 1], 0.0)
    assert np.isclose(sim[0, 2], 1.0 / np.sqrt(2))

    # 2. Asymmetric a and b
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    b = np.array([[1.0, 0.0], [1.0, 1.0], [0.0, -1.0]])
    sim_ab = cosine_similarity_matrix(a, b)
    assert sim_ab.shape == (2, 3)
    assert np.isclose(sim_ab[0, 0], 1.0)
    assert np.isclose(sim_ab[1, 2], -1.0)

    # 3. 1D inputs return scalar float
    vec_a = np.array([1.0, 0.0])
    vec_b = np.array([0.0, 1.0])
    sim_1d = cosine_similarity_matrix(vec_a, vec_b)
    assert isinstance(sim_1d, float)
    assert np.isclose(sim_1d, 0.0)

    # 4. Zero-norm vector returns 0 similarity and zero NaNs
    zero_mat = np.array([[0.0, 0.0]])
    sim_zero = cosine_similarity_matrix(zero_mat, a)
    assert sim_zero.shape == (1, 2)
    assert not np.isnan(sim_zero).any()
    assert np.allclose(sim_zero, 0.0)


def test_union_find_components_disconnected_and_connected() -> None:
    """Verify union_find_components handles empty edges, chains, cycles, and clusters."""
    # 1. Disconnected nodes
    comps_empty = union_find_components(4, [])
    assert len(comps_empty) == 4
    assert comps_empty == [[0], [1], [2], [3]]

    # 2. Linear chain
    comps_chain = union_find_components(4, [(0, 1), (1, 2), (2, 3)])
    assert len(comps_chain) == 1
    assert sorted(comps_chain[0]) == [0, 1, 2, 3]

    # 3. Disjoint components
    comps_disjoint = union_find_components(6, [(0, 1), (2, 3), (3, 4)])
    assert len(comps_disjoint) == 3
    sorted_comps = sorted(sorted(c) for c in comps_disjoint)
    assert sorted_comps == [[0, 1], [2, 3, 4], [5]]

    # 4. Cycle with redundant edges
    comps_cycle = union_find_components(3, [(0, 1), (1, 2), (2, 0), (0, 2)])
    assert len(comps_cycle) == 1
    assert sorted(comps_cycle[0]) == [0, 1, 2]


@pytest.mark.asyncio
async def test_candidate_embedding_cache() -> None:
    """Verify CandidateEmbeddingCache container operations, population, and batching."""
    mock_embed = MagicMock()
    mock_embed.aget_text_embedding_batch = AsyncMock(
        return_value=[[1.0, 0.0], [0.0, 1.0]]
    )

    cache = CandidateEmbeddingCache(mock_embed)
    assert len(cache) == 0
    assert "e1" not in cache

    entity1 = L2Entity(id="e1", name="Alpha", label="Concept", description="First")
    entity2 = L2Entity(id="e2", name="Beta", label="Concept", description="Second")

    # Populate cache
    await cache.populate([entity1, entity2])
    assert len(cache) == 2
    assert "e1" in cache
    assert "e2" in cache
    assert cache["e1"][0] == "[Concept] Alpha: First"
    assert np.allclose(cache["e1"][1], [1.0, 0.0])
    assert cache.get("nonexistent") is None

    # Get embeddings with warm cache (no additional embed call)
    mock_embed.aget_text_embedding_batch.reset_mock()
    tensor_embs = cache.get_embeddings([entity1, entity2])
    assert tensor_embs.shape == (2, 2)
    assert np.allclose(tensor_embs[0].numpy(), [1.0, 0.0])
    assert np.allclose(tensor_embs[1].numpy(), [0.0, 1.0])
    mock_embed.aget_text_embedding_batch.assert_not_called()

    # Get embeddings with new entity (partial miss)
    entity3 = L2Entity(id="e3", name="Gamma", label="Concept", description="Third")
    mock_embed.aget_text_embedding_batch = AsyncMock(return_value=[[0.5, 0.5]])
    await cache.populate([entity3])
    all_embs = cache.get_embeddings([entity1, entity3])
    assert all_embs.shape == (2, 2)
    assert len(cache) == 3
    assert np.allclose(all_embs[1].numpy(), [0.5, 0.5])
    mock_embed.aget_text_embedding_batch.assert_called_once()


def test_stable_component_id() -> None:
    """Verify stable_component_id produces deterministic ac_ hashes."""
    chunk_id = "chunk_42"
    ac_tag = "claim_1"
    cid = stable_component_id(chunk_id, ac_tag)
    expected_hash = hashlib.sha256(f"{chunk_id}:{ac_tag}".encode("utf-8")).hexdigest()[:14]
    assert cid == f"ac_{expected_hash}"

    # Determinism
    assert stable_component_id(chunk_id, ac_tag) == cid
    # Distinctness
    assert stable_component_id("chunk_43", ac_tag) != cid


def test_build_cross_chunk_candidate_pairs() -> None:
    """Verify build_cross_chunk_candidate_pairs filters same-chunk and respects limits."""
    from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

    # Atoms in chunk A
    a1 = TheoryAtom(id="a1", text="Atom 1", component_type="CLAIM", source_chunk_id="chunk_A")
    a2 = TheoryAtom(id="a2", text="Atom 2", component_type="EVIDENCE", source_chunk_id="chunk_A")

    # Atoms in chunk B
    b1 = TheoryAtom(id="b1", text="Atom 3", component_type="CLAIM", source_chunk_id="chunk_B")
    b2 = TheoryAtom(id="b2", text="Atom 4", component_type="EVIDENCE", source_chunk_id="chunk_B")

    components = [a1, a2, b1, b2]

    pairs = build_cross_chunk_candidate_pairs(
        components,
        schema=DEFAULT_SCHEMA,
        max_candidates_per_component=1,
    )

    # All pairs must span different chunks
    for u, v in pairs:
        assert u.source_chunk_id != v.source_chunk_id

    # Each component has at most 1 candidate partner
    u_counts: dict[str, int] = {}
    for u, _ in pairs:
        u_counts[u.id] = u_counts.get(u.id, 0) + 1
    for count in u_counts.values():
        assert count <= 1


@pytest.mark.asyncio
async def test_pipeline_resume_from_run_observability_context() -> None:
    """Verify Pipeline.resume_from_run executes inside active event emitter and logger contexts."""
    from episteme_pipeline.config import PipelineConfig

    observed_emitter = None

    async def fake_execute(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal observed_emitter
        observed_emitter = get_event_emitter()
        mock_res = MagicMock()
        mock_res.manifest = MagicMock()
        mock_res.report = MagicMock()
        return mock_res

    config = PipelineConfig()
    pipeline = Pipeline(
        phases=[],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
    )
    pipeline._execute = fake_execute  # type: ignore[assignment]
    pipeline._hydrate_previous_collection = AsyncMock(return_value=None)  # type: ignore[assignment]

    p_input = PipelineInput(source_paths=[], documents=[])
    await pipeline.resume_from_run(run_id="run-original-123", input=p_input, from_phase=2)

    # During resume_from_run, get_event_emitter() must have been active and scoped to the target run ID
    assert observed_emitter is not None
    assert observed_emitter.defaults.get("run_id") == "run-resume-run-original-123"


def test_zero_reflection_in_orchestration_and_phases() -> None:
    """Static AST audit asserting zero getattr/hasattr in pipeline orchestration and phases."""
    root_dir = Path(__file__).resolve().parent.parent / "episteme_pipeline"

    target_paths: list[Path] = [
        root_dir / "pipeline.py",
        root_dir / "runtime" / "runner.py",
    ]
    target_paths.extend((root_dir / "phases").rglob("*.py"))
    target_paths.extend((root_dir / "post_processing").rglob("*.py"))

    violations: list[str] = []

    for py_file in target_paths:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"getattr", "hasattr"}:
                    violations.append(f"{py_file.relative_to(root_dir)}:{node.lineno} calls {node.func.id}")

    assert not violations, f"Forbidden reflection anti-patterns detected:\n" + "\n".join(violations)
