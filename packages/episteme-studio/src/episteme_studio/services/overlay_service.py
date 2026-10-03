"""Overlay service coordinating metric computations, plugin dispatch, and caching."""

from __future__ import annotations

import json
from typing import Any, Callable
from episteme_studio.adapters.metrics_adapter import (
    compute_component,
    compute_degree,
    compute_gradual_strength,
    compute_internal_correlation,
    compute_leiden,
    compute_modal_strength,
    compute_pagerank,
    compute_tenability,
)
from episteme_studio.domain.errors import OverlayNotImplementedError
from episteme_studio.domain.graph import GraphView
from episteme_studio.domain.overlays import Overlay, OverlayKind

OverlayComputeFn = Callable[[GraphView, dict[str, Any] | None], Overlay]


class OverlayService:
    """Service managing graph overlay algorithms, caching, and plugin dispatch.

    Attributes
    ----------
    _plugins : dict of OverlayKind to OverlayComputeFn
        Plugin dispatch table for supported overlay kinds.
    _reserved_kinds : set of OverlayKind
        Reserved overlay kinds that must return 501 Not Implemented.
    _cache : dict of tuple to Overlay
        In-memory cache keyed by (graph_version, kind_value, params_json).
    """

    def __init__(self) -> None:
        self._plugins: dict[OverlayKind, OverlayComputeFn] = {
            OverlayKind.GRADUAL_STRENGTH: compute_gradual_strength,
            OverlayKind.MODAL_STRENGTH: compute_modal_strength,
            OverlayKind.INTERNAL_CORRELATION: compute_internal_correlation,
            OverlayKind.DEGREE: compute_degree,
            OverlayKind.COMPONENT: compute_component,
            OverlayKind.PAGERANK: compute_pagerank,
            OverlayKind.LEIDEN: compute_leiden,
            OverlayKind.TENABILITY: compute_tenability,
        }
        self._reserved_kinds: set[OverlayKind] = {
            OverlayKind.B_CONSISTENCY,
            OverlayKind.STABLE_EXTENSION,
        }
        self._cache: dict[tuple[str, str, str], Overlay] = {}

    def compute_overlay(
        self,
        graph: GraphView,
        kind: OverlayKind | str,
        params: dict[str, Any] | None = None,
    ) -> Overlay:
        """Compute or retrieve a cached graph overlay for a specific graph version.

        Parameters
        ----------
        graph : GraphView
            The graph snapshot to calculate the overlay across.
        kind : OverlayKind or str
            The identifier of the overlay algorithm to execute.
        params : dict of str to Any, optional
            Optional algorithmic parameters.

        Returns
        -------
        Overlay
            The computed or cached overlay.

        Raises
        ------
        OverlayNotImplementedError
            If the requested overlay kind is reserved (e.g. b_consistency, stable_extension)
            or not registered in the plugin table.
        """
        try:
            overlay_kind = OverlayKind(kind)
        except ValueError:
            raise OverlayNotImplementedError(
                f"Overlay kind '{kind}' is unknown and not implemented."
            )

        if overlay_kind in self._reserved_kinds:
            raise OverlayNotImplementedError(
                f"Overlay kind '{overlay_kind.value}' is reserved and not implemented yet (D-12)."
            )

        handler = self._plugins.get(overlay_kind)
        if handler is None:
            raise OverlayNotImplementedError(
                f"No plugin registered for overlay kind '{overlay_kind.value}'."
            )

        param_dict = params or {}
        params_key = json.dumps(param_dict, sort_keys=True)
        cache_key = (graph.graph_version, overlay_kind.value, params_key)

        if cache_key in self._cache:
            return self._cache[cache_key]

        overlay = handler(graph, param_dict)
        self._cache[cache_key] = overlay
        return overlay

    def list_overlays(self, graph_version: str | None = None) -> list[Overlay]:
        """List cached overlays, optionally filtered by graph version.

        Parameters
        ----------
        graph_version : str or None, optional
            Filter for overlays computed against this specific graph version fingerprint.

        Returns
        -------
        list of Overlay
            List of cached overlays matching the filter criteria.
        """
        if graph_version is None:
            return list(self._cache.values())
        return [
            overlay
            for (gv, _, _), overlay in self._cache.items()
            if gv == graph_version
        ]

    def clear_cache(self) -> None:
        """Clear all entries from the overlay cache."""
        self._cache.clear()
