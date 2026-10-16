"""Pairing and content-addressable ID primitives for Phase 4 Argument Mining.

Centralizes deterministic hashing for argument components and priority-ranked
cross-chunk candidate pairing logic shared across ACC and ARC classifiers.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib

from episteme_pipeline.contracts.domain import TheoryAtom
from episteme_pipeline.schema.default_schema import SchemaConfig


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
