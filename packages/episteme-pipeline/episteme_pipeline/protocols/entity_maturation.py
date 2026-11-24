"""Entity Maturation & Conception Stratification Protocols.

Defines hexagonal port interfaces for multi-modal polysemy detection and
conception clustering used by Phase 4 Entity Maturation runners.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class ConceptionClustererProtocol(Protocol):
    """Protocol for spherical polysemy measurement and conception stratification."""

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for lineage tracking.

        Returns
        -------
        dict of str to Any
            Structured parameter mapping for lineage hashing.
        """
        ...

    def compute_spherical_variance(self, embeddings: np.ndarray) -> float:
        """Compute directional spherical variance across envelope vectors.

        Parameters
        ----------
        embeddings : numpy.ndarray
            Matrix of shape ``(N, D)`` containing envelope embeddings.

        Returns
        -------
        float
            Spherical variance in ``[0.0, 1.0]``.
        """
        ...

    def stratify(
        self,
        envelopes: list[str],
        embeddings: np.ndarray,
        *,
        envelope_chunk_ids: list[str] | None = None,
        envelope_perspectives: list[str] | None = None,
    ) -> tuple[float, list[Any]]:
        """Assess envelope dispersion and partition multi-modal contexts into clusters.

        Parameters
        ----------
        envelopes : list of str
            Textual mention envelopes for a single canonical entity.
        embeddings : numpy.ndarray
            Matrix of shape ``(N, D)`` matching ``envelopes``.
        envelope_chunk_ids : list of str or None, optional
            Parallel source chunk IDs aligned with ``envelopes``.
        envelope_perspectives : list of str or None, optional
            Parallel document or perspective labels aligned with ``envelopes``.

        Returns
        -------
        tuple of (float, list of Any)
            Pair of ``(spherical_variance, clusters)`` where each cluster provides
            ``perspective``, ``envelopes``, ``chunk_ids``, and ``confidence`` metadata.
        """
        ...
