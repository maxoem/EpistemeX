"""Phase 6: TheoryNet Materialization and Projection.

Constructs the formal Bourbaki and QBAF theory net from mined argument
components and relations, applying calibrated edge weights and projecting
them to the long-term Neo4j graph store.
"""

from __future__ import annotations

from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner

__all__ = ["Phase6Runner"]
