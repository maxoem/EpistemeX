"""Deterministic identifier and canonical key helpers for Episteme.

Centralizes stable ID construction, order-preserving deduplication, and
canonical hyperedge lookup keys shared across extraction and refinement phases.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence


def stable_entity_id(label: str, name: str) -> str:
    """Compute a deterministic L2 entity identifier from label and normalized name.

    Same normalized name and label across chunks map to the same canonical ID.

    Parameters
    ----------
    label : str
        Schema entity label (e.g., ``"Concept"``).
    name : str
        Entity surface or canonical name.

    Returns
    -------
    str
        Deterministic entity identifier prefixed with ``"entity_"``.
    """
    key = f"{label.upper()}::{name.strip().lower()}"
    return f"entity_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:14]}"


def dedup_preserve_order(items: Iterable[str]) -> list[str]:
    """Return unique non-empty string identifiers in their first-seen order.

    Parameters
    ----------
    items : Iterable of str
        Input identifier sequence.

    Returns
    -------
    list of str
        Deduplicated non-empty string identifiers preserving order.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def canonical_relation_key(
    premise_ids: Sequence[str],
    target_id: str,
    relation_type: str,
) -> tuple[tuple[str, ...], str, str]:
    """Compute a canonical structural key for a directional argument hyperedge.

    Parameters
    ----------
    premise_ids : Sequence of str
        Effective premise atom identifiers.
    target_id : str
        Target conclusion atom identifier.
    relation_type : str
        Dialectical or structural relation label.

    Returns
    -------
    tuple of (tuple of str, str, str)
        Sorted premise tuple paired with ``(target_id, relation_type)``.
    """
    return (tuple(sorted(premise_ids)), target_id, relation_type)
