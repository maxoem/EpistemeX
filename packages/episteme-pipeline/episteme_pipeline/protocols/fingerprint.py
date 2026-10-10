"""Protocols and utilities for component fingerprinting and discovery.

Grounding & Architecture:
- Adheres to the Composite Pattern and Structural Subtyping (typing.Protocol).
- Inspired by PyTorch's ``nn.Module`` sub-object discovery, recursively traversing
  injected components (engines, resolvers, extractors, classifiers, and models)
  without requiring manual registration dictionaries in phase runners.
- Eliminates invalidation blindspots by guaranteeing that dynamic/environmental
  component state is deterministically captured for run invalidation and phase reuse.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable
from unittest.mock import NonCallableMock

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_PRIMITIVE_TYPES = (int, float, str, bool, bytes, type(None), type)

_CORE_COMPONENT_NAMES = frozenset({
    "llm",
    "embedding_model",
    "global_extractor",
    "decision_engine",
    "modal_resolver",
    "entity_linker",
    "ner_extractor",
    "cross_encoder",
    "reranker",
    "acc_classifier",
    "arc_classifier",
    "adu_segmenter",
    "stopping_oracle",
    "working_memory_manager",
    "instance_fusion",
    "argument_clustering",
    "theory_fusion",
    "cluster_verifier",
    "projector",
})


@runtime_checkable
class Fingerprintable(Protocol):
    """Protocol for components that expose deterministic state for cache invalidation.

    Any computational unit, model adapter, decision engine, or extractor whose
    behavior affects pipeline outputs should satisfy this protocol by returning
    a JSON-serializable dictionary, list, or string representing its configuration,
    weights revision, or hyperparameters.
    """

    def fingerprint(self) -> Any:
        """Return a deterministic JSON-serializable representation of component state.

        Returns
        -------
        Any
            JSON-serializable dictionary, list, string, or primitive representing
            the component's identity, hyperparameters, and internal state.
        """
        ...


def is_component(val: Any, attr_name: str | None = None) -> bool:
    """Check if an object qualifies as a computational component for fingerprinting.

    Parameters
    ----------
    val : Any
        Candidate object to evaluate.
    attr_name : str or None, optional
        Attribute name under which the object is bound on its parent.

    Returns
    -------
    bool
        True if the object is an eligible component, False otherwise.
    """
    if val is None or isinstance(val, _PRIMITIVE_TYPES):
        return False

    # Explicit protocol conformance (structural typing)
    if isinstance(val, Fingerprintable) and callable(getattr(val, "fingerprint", None)):
        return True

    # Pydantic models (configs, schemas, data contracts) are fingerprinted separately
    if isinstance(val, BaseModel):
        return False

    # Core runner component attributes (backwards compatibility for test doubles)
    return attr_name in _CORE_COMPONENT_NAMES


def find_components(
    root: Any,
    prefix: str = "",
    visited: set[int] | None = None,
) -> dict[str, Any]:
    """Recursively discover all computational components in an object graph.

    Traverses object attributes, lists, and dictionaries using Depth-First Search
    (DFS) to build hierarchical dotted paths (e.g. ``global_extractor.reranker``),
    similar to PyTorch's ``named_modules()``.

    Parameters
    ----------
    root : Any
        Root object to introspect (e.g., a PhaseRunner instance or extractor).
    prefix : str, default ""
        Current path prefix for hierarchical component keys.
    visited : set of int or None, default None
        Set of visited object memory IDs to avoid reference cycles.

    Returns
    -------
    dict of str to Any
        Mapping from dotted component path to the discovered component instance.
    """
    if visited is None:
        visited = set()

    if root is None or id(root) in visited:
        return {}

    if isinstance(root, (_PRIMITIVE_TYPES, list, tuple, set, dict, NonCallableMock)):
        return {}

    visited.add(id(root))
    discovered: dict[str, Any] = {}

    # Extract instance attributes
    raw_dict = getattr(root, "__dict__", None)
    if not isinstance(raw_dict, dict):
        return {}

    attrs = {k: v for k, v in raw_dict.items() if isinstance(k, str) and not k.startswith("_")}

    for name, value in attrs.items():
        if value is None:
            continue

        full_path = f"{prefix}.{name}" if prefix else name

        if is_component(value, attr_name=name):
            discovered[full_path] = value

        if not isinstance(value, (list, tuple, dict)):
            discovered.update(find_components(value, prefix=full_path, visited=visited))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                sub_path = f"{full_path}[{i}]"
                if is_component(item):
                    discovered[sub_path] = item
                discovered.update(find_components(item, prefix=sub_path, visited=visited))
        elif isinstance(value, dict):
            for k, item in value.items():
                if isinstance(k, str) and not k.startswith("_"):
                    sub_path = f"{full_path}.{k}"
                    if is_component(item):
                        discovered[sub_path] = item
                    discovered.update(find_components(item, prefix=sub_path, visited=visited))

    return discovered
