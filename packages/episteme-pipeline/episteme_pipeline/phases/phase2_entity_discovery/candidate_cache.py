"""Candidate entity embedding cache for Phase 2 Entity Linkers.

Pre-fetches, caches, and provides vector embeddings for canonical entities in the
knowledge graph during bi-encoder candidate retrieval.
"""

from __future__ import annotations

import torch

from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.protocols.extractors import EmbeddingModel, as_tensor


class CandidateEmbeddingCache:
    """In-memory cache for canonical entity text representations and embeddings.

    Parameters
    ----------
    embedding_model : EmbeddingModel
        Underlying embedding model used to batch-compute dense vectors.
    """

    def __init__(self, embedding_model: EmbeddingModel) -> None:
        self.embedding_model = embedding_model
        self._cache: dict[str, tuple[str, list[float]]] = {}

    @staticmethod
    def canonical_entity_string(candidate: L2Entity) -> str:
        """Format candidate entity for bi-encoder embedding with explicit type grounding.

        Parameters
        ----------
        candidate : L2Entity
            The candidate entity to format.

        Returns
        -------
        str
            Formatted textual representation.
        """
        return f"[{candidate.label}] {candidate.name}: {candidate.description or ''}"

    async def populate(self, candidates: list[L2Entity]) -> None:
        """Pre-fetch embeddings for new or stale candidate entities.

        Parameters
        ----------
        candidates : list of L2Entity
            List of candidate entities to synchronize with the vector cache.
        """
        stale_candidates: list[L2Entity] = []
        stale_basic_texts: list[str] = []
        for c in candidates:
            basic_text = self.canonical_entity_string(c)
            cached = self._cache.get(c.id)
            if not cached or cached[0] != basic_text:
                stale_candidates.append(c)
                stale_basic_texts.append(basic_text)

        if not stale_candidates:
            return

        fresh_vectors = await self.embedding_model.aget_text_embedding_batch(stale_basic_texts)
        for c, b_text, vec in zip(stale_candidates, stale_basic_texts, fresh_vectors):
            self._cache[c.id] = (b_text, vec)

    def get_embeddings(self, candidates: list[L2Entity]) -> torch.Tensor:
        """Return cached embeddings as a torch Tensor.

        Parameters
        ----------
        candidates : list of L2Entity
            Candidate entities whose vectors should be retrieved.

        Returns
        -------
        torch.Tensor
            2D float tensor of candidate embeddings.
        """
        embs = [self._cache[c.id][1] for c in candidates]
        return as_tensor(embs)

    def __contains__(self, entity_id: str) -> bool:
        """Check if an entity ID is present in the cache.

        Parameters
        ----------
        entity_id : str
            Unique entity identifier.

        Returns
        -------
        bool
            True if entity is cached, False otherwise.
        """
        return entity_id in self._cache

    def __len__(self) -> int:
        """Return the number of cached entities.

        Returns
        -------
        int
            Count of cached entities.
        """
        return len(self._cache)

    def __getitem__(self, entity_id: str) -> tuple[str, list[float]]:
        """Retrieve cached text and vector tuple for an entity ID.

        Parameters
        ----------
        entity_id : str
            Unique entity identifier.

        Returns
        -------
        tuple of (str, list of float)
            Cached text and embedding vector.

        Raises
        -------
        KeyError
            If entity_id is not present in cache.
        """
        return self._cache[entity_id]

    def get(self, entity_id: str) -> tuple[str, list[float]] | None:
        """Retrieve cached text and vector tuple for an entity ID, if present.

        Parameters
        ----------
        entity_id : str
            Unique entity identifier.

        Returns
        -------
        tuple of (str, list of float) or None
            Cached text and embedding vector, or None if not cached.
        """
        return self._cache.get(entity_id)

