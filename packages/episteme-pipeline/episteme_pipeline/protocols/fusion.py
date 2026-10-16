from abc import ABC, abstractmethod

from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.graph_store import FusionGraph


class InstanceFusion(Fingerprintable, ABC):
    """
    Phase 5 — Graph-based Instance-Level Fusion.

    Resolves cross-chunk entity aliases and fragmented references that the
    LLM could not resolve locally in Phase 2. This is the modern replacement
    for traditional standalone coreference resolution.

    Default implementation: zero-shot LLM disambiguation (EntGPT / LLM-Align
    style) — compares entity pairs via their graph neighborhoods before merging.

    Pluggable future implementation: TAG + GNN clustering for O(N log N)
    efficiency at scale (swap in via PipelineConfig.phase5.instance_fusion).
    """

    @abstractmethod
    async def fuse(
        self,
        graph_store: FusionGraph,
    ) -> dict[str, str]:
        """
        Returns a map of {original_entity_id -> canonical_entity_id} for all
        merged entities. Entities that are not merged map to themselves.
        Graph store is updated in place (MERGE semantics).
        """
        ...


class ArgumentClustering(Fingerprintable, ABC):
    """
    Phase 5 — Global Argument Resolution via clustering (Key Point Analysis).

    Groups semantically equivalent argument components across chunks/documents
    into clusters. Each cluster collapses to a single canonical proxy node in
    the graph, preserving the originating EXTRACTED_FROM links.

    This is Phase 5b's primary step — it operates on the L3 argument graph
    after Phase 4 has populated it.
    """

    @abstractmethod
    async def cluster(
        self,
        graph_store: FusionGraph,
    ) -> list[list[str]]:
        """
        Returns groups of argument component IDs that are semantically
        equivalent and should be treated as one canonical argument.
        """
        ...


class TheoryFusion(Fingerprintable, ABC):
    """
    Phase 5 — Theory-Level Fusion.

    Fuses theory-level structures: argument clusters, axioms, observation
    statements, and assignment laws into a coherent theory network on L3.

    Interface only in V1. This is not conceptually blocked on TheoryNet; TheoryNet is
    treated as one optional downstream projection rather than the mandatory
    backbone of theory-layer construction.
    """

    @abstractmethod
    async def fuse(
        self,
        graph_store: FusionGraph,
    ) -> None: ...
