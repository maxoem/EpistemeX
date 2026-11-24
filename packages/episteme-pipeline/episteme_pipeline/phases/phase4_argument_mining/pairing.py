"""Pairing and content-addressable ID primitives for Phase 4 Argument Mining.

Centralizes deterministic hashing for argument components and priority-ranked
cross-chunk candidate pairing logic shared across ACC and ARC classifiers.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
from typing import Any

import numpy as np

from episteme_pipeline.contracts.domain import TheoryAtom
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils.similarity import (
    cosine_similarity_matrix,
    csls_similarity_matrix,
    dynamic_k_effective,
    z_score_normalize,
)


def stable_component_id(chunk_id: str, ac_tag: str) -> str:
    """Generate a deterministic, content-addressable ID for an argument component.

    Parameters
    ----------
    chunk_id : str
        The unique ID of the source chunk.
    ac_tag : str
        The local tag identifier (e.g. "AC1").

    Returns
    -------
    str
        Stable component ID in the format ``ac_<hex14>``.
    """
    key = f"{chunk_id}:{ac_tag}"
    return f"ac_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:14]}"


def build_cross_chunk_candidate_pairs(
    components: list[TheoryAtom],
    schema: SchemaConfig,
    max_candidates_per_component: int = 10,
) -> list[tuple[TheoryAtom, TheoryAtom]]:
    """Generate candidate argument pairs across distinct source chunks based on priority ranking.

    Sorts argument components by their epistemic priority hierarchy defined in the
    schema, and creates pairs between components originating from different chunks,
    respecting per-component maximum candidate limits.

    Parameters
    ----------
    components : list of TheoryAtom
        The pool of argument components to pair.
    schema : SchemaConfig
        Schema providing the component type hierarchy order.
    max_candidates_per_component : int, default 10
        Maximum number of candidate pairings allowed for any single component.

    Returns
    -------
    list of tuple of (TheoryAtom, TheoryAtom)
        Selected cross-chunk candidate pairs.
    """
    partner_count: dict[str, int] = defaultdict(int)
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[TheoryAtom, TheoryAtom]] = []

    priority_rank = {ctype: idx for idx, ctype in enumerate(schema.component_types)}
    sorted_components = sorted(
        components, key=lambda c: priority_rank.get(c.component_type, 99)
    )

    for i, a in enumerate(sorted_components):
        for b in sorted_components[i + 1 :]:
            if a.source_chunk_id == b.source_chunk_id:
                continue
            key = (min(a.id, b.id), max(a.id, b.id))
            if key in seen:
                continue
            if (
                partner_count[a.id] >= max_candidates_per_component
                or partner_count[b.id] >= max_candidates_per_component
            ):
                continue
            seen.add(key)
            pairs.append((a, b))
            partner_count[a.id] += 1
            partner_count[b.id] += 1

    return pairs


async def build_cross_chunk_embedding_pairs(
    components: list[TheoryAtom],
    embedding_model: Any,
    *,
    max_candidates_per_component: int = 10,
    use_csls: bool = True,
    csls_k_nearest: int = 10,
    use_adaptive_k: bool = True,
    adaptive_k_gamma: float = 2.0,
    adaptive_k_min: int = 2,
    z_score_threshold: float | None = None,
) -> list[tuple[TheoryAtom, TheoryAtom]]:
    """Generate cross-chunk candidate pairs ranked by CSLS / cosine similarity with adaptive K_eff.

    Parameters
    ----------
    components : list of TheoryAtom
        The pool of argument components to pair.
    embedding_model : Any
        Embedding model exposing ``aget_text_embedding_batch``.
    max_candidates_per_component : int, default 10
        Maximum candidate degree cap.
    use_csls : bool, default True
        Whether to apply Cross-Domain Similarity Local Scaling (CSLS).
    csls_k_nearest : int, default 10
        Neighborhood size for CSLS scaling.
    use_adaptive_k : bool, default True
        Whether to bound candidate degree dynamically via ``dynamic_k_effective``.
    adaptive_k_gamma : float, default 2.0
        Scaling multiplier for adaptive K_eff.
    adaptive_k_min : int, default 2
        Minimum candidate degree floor for adaptive K_eff.
    z_score_threshold : float or None, optional
        Optional standardized z-score cutoff for candidate pairs.

    Returns
    -------
    list of tuple of (TheoryAtom, TheoryAtom)
        Selected cross-chunk candidate pairs ordered by descending similarity.
    """
    if len(components) < 2:
        return []

    partner_count: dict[str, int] = defaultdict(int)
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[TheoryAtom, TheoryAtom]] = []

    texts = [c.text for c in components]
    embeddings = await embedding_model.aget_text_embedding_batch(texts)

    vectors = np.array(embeddings)
    if use_csls:
        sim_matrix = csls_similarity_matrix(vectors, k_nearest=csls_k_nearest)
    else:
        sim_matrix = cosine_similarity_matrix(vectors)

    num_comp = len(components)
    if use_adaptive_k:
        k_eff = dynamic_k_effective(
            n=num_comp,
            k_min=adaptive_k_min,
            k_max=max_candidates_per_component,
            gamma=adaptive_k_gamma,
        )
    else:
        k_eff = max_candidates_per_component

    z_scores = (
        z_score_normalize(sim_matrix, symmetric=True)
        if z_score_threshold is not None
        else None
    )

    i_indices, j_indices = np.triu_indices(num_comp, k=1)
    similarities = sim_matrix[i_indices, j_indices]
    sorted_idx = np.argsort(similarities)[::-1]

    for idx in sorted_idx:
        i = i_indices[idx]
        j = j_indices[idx]
        a = components[i]
        b = components[j]

        if a.source_chunk_id == b.source_chunk_id:
            continue

        if z_score_threshold is not None and z_scores is not None:
            if z_scores[i, j] < z_score_threshold:
                continue

        key = (min(a.id, b.id), max(a.id, b.id))
        if key in seen:
            continue

        if partner_count[a.id] >= k_eff or partner_count[b.id] >= k_eff:
            continue

        seen.add(key)
        pairs.append((a, b))
        partner_count[a.id] += 1
        partner_count[b.id] += 1

    return pairs
