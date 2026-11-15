"""Phase 4 — Entity Maturation & Theory-Laden Conception Stratification.

This phase matures canonical ``L2Entity`` nodes after entity linking and resolution
(ADR-0003, ADR-0023). Rather than relying on naive first-mention-wins descriptions or
forcing divergent theoretical usages into a single flat centroid average:

1. Retrieves all ``EXTRACTED_FROM`` textual envelopes and associated chunk/document
   provenance for each immature canonical entity.
2. Computes L2-normalized envelope embeddings and measures spherical polysemy variance
   (``1 - ||mean(normed)||_2``) via :class:`ConceptionClusterer`.
3. When dispersion exceeds ``polysemy_variance_threshold`` and coherent perspective or
   latent clusters emerge, stratifies the entity into perspective-specific
   :class:`EntityConception` facets attached to the shared Referential Topic
   :class:`L2Entity` and emits :class:`EntityConceptionStratified`.
4. Otherwise (uni-modal usage), selects the Top-K envelopes closest to the centroid and
   synthesizes a single canonical description.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import batched
from typing import Any

import numpy as np
import torch
from pydantic import BaseModel

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase3ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import Phase4EntityMaturationConfig
from episteme_pipeline.contracts.domain import (
    EntityConception,
    L2Entity,
    PhaseItemRecord,
)
from episteme_pipeline.events.models import (
    EntityConceptionStratified,
    EntityMaturationSynthesized,
)
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.protocols.extractors import EmbeddingModel, as_tensor
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.graph_store import (
    GraphReader,
    GraphWriter,
    PhaseCheckpointStore,
    ProcessingGraph,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runtime.batch_executor import CheckpointedBatchExecutor
from episteme_pipeline.utils.similarity import cosine_similarity_matrix, l2_normalize

logger = logging.getLogger(__name__)


class EntitySynthesisOutput(BaseModel):
    """Structured LLM output for synthesized entity or conception descriptions.

    Attributes
    ----------
    description : str
        Synthesized canonical or perspective-scoped description.
    """

    description: str


@dataclass(slots=True)
class ConceptionCluster:
    """Cluster of semantically coherent mention envelopes for one conception facet.

    Attributes
    ----------
    perspective : str
        Document/theory perspective label or latent cluster identifier.
    envelopes : list of str
        Top-K representative mention envelopes closest to this cluster's centroid.
    chunk_ids : list of str
        Deduplicated source chunk identifiers grounding this cluster.
    centroid_dispersion : float
        Intra-cluster spherical dispersion ``1 - ||mean(normed)||_2`` in ``[0, 1]``.
    confidence : float
        Cluster coherence confidence ``1 - centroid_dispersion`` in ``[0, 1]``.
    """

    perspective: str
    envelopes: list[str]
    chunk_ids: list[str]
    centroid_dispersion: float
    confidence: float


class ConceptionClusterer(Fingerprintable):
    """Detects multi-modal polysemy across envelopes and stratifies conceptions.

    Measures directional dispersion on the unit hypersphere and partitions divergent
    contextual envelopes by explicit perspective boundaries (when aligned with
    semantic separation) or deterministic spherical k-means scored with cosine
    silhouette coherence (Kuhn, 1962; Quine, 1951).

    Parameters
    ----------
    polysemy_variance_threshold : float, default 0.15
        Minimum spherical variance ``1 - R`` required to trigger stratification.
    min_silhouette_score : float, default 0.15
        Minimum cosine silhouette score required when stratifying unsupervised.
    max_conceptions : int, default 4
        Maximum number of distinct conceptions retained per entity.
    min_envelopes : int, default 2
        Minimum envelope count required to attempt stratification.
    top_k_per_conception : int, default 5
        Maximum representative envelopes selected per stratified conception.
    """

    def __init__(
        self,
        *,
        polysemy_variance_threshold: float = 0.15,
        min_silhouette_score: float = 0.15,
        max_conceptions: int = 4,
        min_envelopes: int = 2,
        top_k_per_conception: int = 5,
    ) -> None:
        self.polysemy_variance_threshold = polysemy_variance_threshold
        self.min_silhouette_score = min_silhouette_score
        self.max_conceptions = max_conceptions
        self.min_envelopes = min_envelopes
        self.top_k_per_conception = top_k_per_conception

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for lineage tracking.

        Returns
        -------
        dict of str to Any
            Structured parameter mapping for lineage hashing.
        """
        return {
            "component": "ConceptionClusterer",
            "polysemy_variance_threshold": self.polysemy_variance_threshold,
            "min_silhouette_score": self.min_silhouette_score,
            "max_conceptions": self.max_conceptions,
            "min_envelopes": self.min_envelopes,
            "top_k_per_conception": self.top_k_per_conception,
        }

    def compute_spherical_variance(self, embeddings: np.ndarray) -> float:
        """Compute directional spherical variance ``1 - R`` across envelope vectors.

        Parameters
        ----------
        embeddings : numpy.ndarray
            Matrix of shape ``(N, D)`` containing envelope embeddings.

        Returns
        -------
        float
            Spherical variance in ``[0.0, 1.0]``. Returns ``0.0`` if ``N < 2`` or if all
            vectors are zero-norm.
        """
        if embeddings.ndim != 2 or embeddings.shape[0] < 2:
            return 0.0
        normed = l2_normalize(embeddings.astype(np.float32))
        if np.allclose(normed, 0.0):
            return 0.0
        mean_vec = np.mean(normed, axis=0)
        resultant_len = float(np.linalg.norm(mean_vec))
        return max(0.0, min(1.0, 1.0 - resultant_len))

    def _build_cluster(
        self,
        perspective: str,
        indices: list[int],
        envelopes: list[str],
        normed: np.ndarray,
        chunk_ids: list[str],
    ) -> ConceptionCluster:
        """Build a ranked :class:`ConceptionCluster` for a group of envelope indices."""
        sub = normed[indices]
        mean_vec = np.mean(sub, axis=0)
        resultant_len = float(np.linalg.norm(mean_vec))
        dispersion = max(0.0, min(1.0, 1.0 - resultant_len))
        confidence = max(0.0, min(1.0, 1.0 - dispersion))

        if resultant_len > 1e-12:
            centroid = (mean_vec / resultant_len).reshape(1, -1)
            sims = (sub @ centroid.T).reshape(-1)
        else:
            sims = np.zeros(len(indices), dtype=np.float32)

        ranked = [
            indices[pos]
            for pos in sorted(
                range(len(indices)),
                key=lambda pos: (-float(sims[pos]), indices[pos]),
            )
        ]
        rep_envelopes = [envelopes[i] for i in ranked[: self.top_k_per_conception]]
        cids = list(dict.fromkeys(chunk_ids[i] for i in indices if chunk_ids[i]))
        return ConceptionCluster(
            perspective=perspective,
            envelopes=rep_envelopes,
            chunk_ids=cids,
            centroid_dispersion=round(dispersion, 6),
            confidence=round(confidence, 6),
        )

    @staticmethod
    def _spherical_kmeans(
        normed: np.ndarray,
        sim_mat: np.ndarray,
        k: int,
    ) -> np.ndarray | None:
        """Partition L2-normalized vectors into ``k`` clusters deterministically.

        Uses farthest-first seed initialization followed by spherical k-means updates.
        Returns ``None`` if fewer than ``k`` distinct unit directions exist.
        """
        n = normed.shape[0]
        seeds: list[int] = [0]
        dist_mat = np.clip(1.0 - sim_mat, 0.0, 2.0)

        for _ in range(1, k):
            min_dists = np.min(dist_mat[:, seeds], axis=1)
            for s in seeds:
                min_dists[s] = -1.0
            next_seed = int(np.argmax(min_dists))
            if min_dists[next_seed] <= 1e-9:
                return None
            seeds.append(next_seed)

        centroids = normed[seeds].copy()
        labels = np.zeros(n, dtype=np.int64)

        for _ in range(25):
            scores = normed @ centroids.T
            new_labels = np.argmax(scores, axis=1)

            # Reassign furthest outlier if any cluster becomes empty.
            for c in range(k):
                if not np.any(new_labels == c):
                    own_sims = scores[np.arange(n), new_labels]
                    candidate = int(np.argmin(own_sims))
                    new_labels[candidate] = c

            updated: list[np.ndarray] = []
            for c in range(k):
                mask = new_labels == c
                if np.any(mask):
                    updated.append(l2_normalize(np.mean(normed[mask], axis=0, keepdims=True))[0])
                else:
                    updated.append(centroids[c])
            centroids = np.vstack(updated)

            if np.array_equal(new_labels, labels):
                break
            labels = new_labels

        if len(set(labels.tolist())) < 2:
            return None
        return labels

    @staticmethod
    def _mean_cosine_silhouette(
        labels: np.ndarray,
        dist_mat: np.ndarray,
    ) -> float:
        """Compute mean cosine silhouette coefficient (singletons receive ``0.0``)."""
        n = dist_mat.shape[0]
        unique_labels = sorted(set(labels.tolist()))
        if len(unique_labels) < 2:
            return -1.0

        scores: list[float] = []
        for i in range(n):
            own = int(labels[i])
            own_members = [j for j in range(n) if int(labels[j]) == own and j != i]
            if not own_members:
                scores.append(0.0)
                continue
            a_i = float(np.mean(dist_mat[i, own_members]))
            b_i = min(
                float(np.mean(dist_mat[i, labels == other]))
                for other in unique_labels
                if other != own
            )
            denom = max(a_i, b_i)
            scores.append((b_i - a_i) / denom if denom > 1e-12 else 0.0)
        return float(np.mean(scores))

    def stratify(
        self,
        envelopes: list[str],
        embeddings: np.ndarray,
        *,
        envelope_chunk_ids: list[str] | None = None,
        envelope_perspectives: list[str] | None = None,
    ) -> tuple[float, list[ConceptionCluster]]:
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
            Parallel document or theoretical perspective labels aligned with ``envelopes``.

        Returns
        -------
        tuple of (float, list of ConceptionCluster)
            Pair of ``(spherical_variance, clusters)``. Returns an empty list for
            ``clusters`` when the entity is uni-modal or lacks coherent separation.
        """
        variance = self.compute_spherical_variance(embeddings)
        n = len(envelopes)
        if n < self.min_envelopes or variance <= self.polysemy_variance_threshold:
            return variance, []

        normed = l2_normalize(embeddings.astype(np.float32))
        chunk_ids = (
            list(envelope_chunk_ids)
            if envelope_chunk_ids and len(envelope_chunk_ids) == n
            else [""] * n
        )

        # Prefer explicit perspective groups when at least two exist and centroids diverge.
        if envelope_perspectives and len(envelope_perspectives) == n:
            groups: dict[str, list[int]] = {}
            for idx, raw_persp in enumerate(envelope_perspectives):
                persp = raw_persp.strip() if raw_persp else ""
                if persp:
                    groups.setdefault(persp, []).append(idx)

            if len(groups) >= 2:
                ordered = sorted(
                    groups.items(),
                    key=lambda item: (-len(item[1]), item[0]),
                )[: self.max_conceptions]
                centroids = np.vstack(
                    [
                        l2_normalize(np.mean(normed[idxs], axis=0, keepdims=True))
                        for _, idxs in ordered
                    ]
                )
                inter_sim = cosine_similarity_matrix(centroids)
                upper_tri = np.triu_indices(len(ordered), k=1)
                inter_separation = 1.0 - float(np.mean(inter_sim[upper_tri]))
                if inter_separation > self.polysemy_variance_threshold:
                    clusters = [
                        self._build_cluster(persp, idxs, envelopes, normed, chunk_ids)
                        for persp, idxs in ordered
                    ]
                    return variance, clusters

        # Unsupervised geometric stratification fallback.
        if n == 2:
            return variance, [
                self._build_cluster("concept_cluster_1", [0], envelopes, normed, chunk_ids),
                self._build_cluster("concept_cluster_2", [1], envelopes, normed, chunk_ids),
            ]

        max_k = min(self.max_conceptions, n - 1)
        if max_k < 2:
            return variance, []

        sim_mat = cosine_similarity_matrix(normed)
        dist_mat = np.clip(1.0 - sim_mat, 0.0, 2.0)

        best_score = -1.0
        best_labels: np.ndarray | None = None
        for k in range(2, max_k + 1):
            labels = self._spherical_kmeans(normed, sim_mat, k)
            if labels is None:
                continue
            score = self._mean_cosine_silhouette(labels, dist_mat)
            if score > best_score:
                best_score = score
                best_labels = labels

        if best_labels is None or best_score < self.min_silhouette_score:
            return variance, []

        label_groups: dict[int, list[int]] = {}
        for idx, lbl in enumerate(best_labels.tolist()):
            label_groups.setdefault(lbl, []).append(idx)

        ordered_groups = sorted(
            label_groups.values(),
            key=lambda idxs: (-len(idxs), min(idxs)),
        )
        clusters = [
            self._build_cluster(
                f"concept_cluster_{rank}",
                idxs,
                envelopes,
                normed,
                chunk_ids,
            )
            for rank, idxs in enumerate(ordered_groups, start=1)
        ]
        return variance, clusters


def _default_embedding_model() -> EmbeddingModel:
    """Last-resort local encoder, imported lazily to keep ``transformers`` optional."""
    from episteme_pipeline.protocols.extractors import HuggingFaceEmbeddingModel

    logger.warning(
        "Phase 4 maturation received no embedding model and none is configured; "
        "falling back to a default HuggingFaceEmbeddingModel."
    )
    return HuggingFaceEmbeddingModel()


class Phase4EntityMaturationRunner(PhaseRunner[Phase3ArtifactsView]):
    """Runner for Phase 4: Entity Maturation & Conception Stratification.

    Synthesizes canonical descriptions for immature :class:`L2Entity` nodes using
    contextual mention envelopes while preserving theory-laden / perspective-specific
    :class:`EntityConception` facets whenever envelope dispersion reveals genuine
    polysemy across documents or semantic clusters.

    Parameters
    ----------
    config : Phase4EntityMaturationConfig
        Configuration options for maturation and conception stratification.
    llm : Any
        LLM backend used for structured description synthesis.
    graph_store : ProcessingGraph | GraphReader | None, optional
        Optional graph database client fallback.
    embedding_model : EmbeddingModel | None, optional
        Bi-encoder used to embed mention envelopes for dispersion and clustering.
    """

    name = "Phase 4: Entity Maturation (Batch Epistemic Synthesis)"
    phase_key = "phase4_maturation"
    input_view = Phase3ArtifactsView
    reads_kinds = frozenset(
        {
            ArtifactKind.LINKED_ENTITY,
            ArtifactKind.CANONICALIZATION,
            ArtifactKind.GLOBAL_RELATION,
        }
    )
    writes_kinds = frozenset({ArtifactKind.LINKED_ENTITY})

    def __init__(
        self,
        config: Phase4EntityMaturationConfig,
        *,
        llm: Any,
        graph_store: ProcessingGraph | GraphReader | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.config = config
        self.llm = ensure_structured_llm(llm)
        self.graph_store = graph_store
        self.embedding_model: EmbeddingModel = (
            embedding_model or _default_embedding_model()
        )
        self.conception_clusterer = ConceptionClusterer(
            polysemy_variance_threshold=config.polysemy_variance_threshold,
            min_silhouette_score=config.min_silhouette_score,
            max_conceptions=config.max_conceptions_per_entity,
            min_envelopes=config.min_envelopes_for_stratification,
            top_k_per_conception=config.maturation_top_k,
        )

    async def run(
        self, input: Phase3ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Mature immature canonical entities and emit updated entity artifacts.

        Parameters
        ----------
        input : Phase3ArtifactsView
            Upstream Phase 3 view supplying entities, envelopes, mentions, and chunks.
        context : ArtifactExecutionContext
            Runtime context identifying the active run and lineage fingerprint.

        Returns
        -------
        ArtifactCollection
            Collection of matured :class:`LinkedEntityArtifact` envelopes.
        """
        logger.info("Starting Entity Maturation batch synthesis...")
        from episteme_pipeline.artifacts.builders import build_linked_entity_artifact

        if input.entities:
            all_entities = list(input.entities)
        elif isinstance(self.graph_store, GraphReader):
            all_entities = await self.graph_store.get_entities()
        else:
            all_entities = []

        immature_entities = [e for e in all_entities if not e.is_mature]

        logger.info(
            f"Found {len(immature_entities)} immature entities out of {len(all_entities)} total."
        )

        matured_artifacts = []
        chunk_to_doc = {c.id: c.source_doc_id for c in input.chunks}

        progress_task = f"Phase 4 Maturation: {len(immature_entities)} entities"
        batch_size = self.config.batch_size
        checkpoint_store = (
            self.graph_store
            if isinstance(self.graph_store, PhaseCheckpointStore)
            else None
        )
        effective_phase = (
            f"{self.phase_key}:{context.lineage_fingerprint}"
            if context and context.lineage_fingerprint
            else self.phase_key
        )

        async def _maturation_item(entity: L2Entity) -> L2Entity | None:
            return await self._process_entity(
                entity,
                context.run_id,
                input_envelopes=input.entity_envelopes_by_id.get(entity.id),
                mention_records=input.entity_mentions_by_id.get(entity.id),
                chunk_to_doc=chunk_to_doc,
            )

        async def _on_maturation_batch(
            batch_entities: list[L2Entity],
            records: list[PhaseItemRecord],
        ) -> None:
            for matured_entity in batch_entities:
                mention_ids = [
                    f"artifact::mention::{matured_entity.id}::{cid}"
                    for cid in matured_entity.source_chunk_ids
                ]
                matured_artifacts.append(
                    build_linked_entity_artifact(
                        matured_entity,
                        mention_ids,
                        run_id=context.run_id,
                        phase_name=self.name,
                        method="Phase4EntityMaturationRunner",
                        upstream_artifact_ids=[
                            f"artifact::{matured_entity.id}",
                            *mention_ids,
                        ],
                    )
                )

            if batch_entities and isinstance(self.graph_store, GraphWriter):
                for sub_batch in batched(batch_entities, 500):
                    await self.graph_store.upsert_entities(list(sub_batch))

        with self.progress_scope(
            progress_task,
            total_items=len(immature_entities),
            description="Entity Maturation",
        ) as advance:
            executor = CheckpointedBatchExecutor[L2Entity, L2Entity](
                checkpoint_store=checkpoint_store,
                phase_tag=effective_phase,
                batch_size=batch_size,
                item_key_fn=lambda e: f"maturation::{e.id}",
                process_item_fn=_maturation_item,
                on_batch_complete=_on_maturation_batch,
                guard_systematic_failure=False,
            )
            await executor.execute(immature_entities, on_batch_advance=advance)

        if matured_artifacts:
            return ArtifactCollection(matured_artifacts)
        return ArtifactCollection([])

    @staticmethod
    def _align_envelopes(
        envelopes: list[str],
        mention_records: list[dict[str, str]] | None,
        chunk_to_doc: dict[str, str] | None,
    ) -> tuple[list[str], list[str]]:
        """Align chunk IDs and document/perspective labels with ``envelopes``."""
        n = len(envelopes)
        if not mention_records:
            return [""] * n, [""] * n

        env_meta: dict[str, tuple[str, str]] = {}
        has_env_text = False
        for rec in mention_records:
            cid = rec.get("chunk_id", "")
            persp = rec.get("perspective") or (
                chunk_to_doc.get(cid, "") if chunk_to_doc and cid else ""
            )
            env_text = rec.get("textual_envelope", "")
            if env_text:
                has_env_text = True
                if env_text not in env_meta:
                    env_meta[env_text] = (cid, persp)

        if has_env_text:
            aligned_cids = [env_meta.get(env, ("", ""))[0] for env in envelopes]
            aligned_persps = [env_meta.get(env, ("", ""))[1] for env in envelopes]
            return aligned_cids, aligned_persps

        if len(mention_records) == n:
            aligned_cids = [rec.get("chunk_id", "") for rec in mention_records]
            aligned_persps = [
                rec.get("perspective")
                or (
                    chunk_to_doc.get(rec.get("chunk_id", ""), "")
                    if chunk_to_doc and rec.get("chunk_id")
                    else ""
                )
                for rec in mention_records
            ]
            return aligned_cids, aligned_persps

        return [""] * n, [""] * n

    async def _synthesize_description(
        self,
        entity_name: str,
        envelopes: list[str],
    ) -> str | None:
        """Synthesize a canonical or perspective-scoped description via the LLM.

        Parameters
        ----------
        entity_name : str
            Target entity display name (optionally qualified by perspective).
        envelopes : list of str
            Representative textual envelopes passed to the structured prompt.

        Returns
        -------
        str or None
            Synthesized description string, or ``None`` on synthesis error.
        """
        formatted_envelopes = "\n---\n".join(envelopes)
        try:
            raw: EntitySynthesisOutput = await self.llm.predict_structured(
                EntitySynthesisOutput,
                self.config.entity_synthesis_prompts,
                strategy=self.config.entity_synthesis_decoding_strategy,
                entity_name=entity_name,
                envelopes=formatted_envelopes,
            )
            return raw.description
        except Exception as exc:  # noqa: BLE001 - isolate per-entity LLM backend errors so batch maturation proceeds
            logger.warning(f"Synthesis failed for {entity_name}: {exc}")
            return None

    async def _process_entity(
        self,
        entity: L2Entity,
        run_id: str,
        input_envelopes: list[str] | None = None,
        mention_records: list[dict[str, str]] | None = None,
        chunk_to_doc: dict[str, str] | None = None,
    ) -> L2Entity | None:
        """Synthesize a matured description (and optional conceptions) for one entity.

        Parameters
        ----------
        entity : L2Entity
            Immature canonical entity to synthesize.
        run_id : str
            Active pipeline run identifier for event emission.
        input_envelopes : list of str or None, optional
            Envelopes pre-collected from Phase 3 mention artifacts.
        mention_records : list of dict or None, optional
            Mention provenance dicts carrying ``chunk_id`` and optional ``textual_envelope``.
        chunk_to_doc : dict of str to str or None, optional
            Mapping from chunk identifier to source document / perspective identifier.

        Returns
        -------
        L2Entity or None
            Updated mature entity, or ``None`` if structured synthesis fails.
        """
        if input_envelopes:
            envelopes = list(input_envelopes)
        elif mention_records and any(rec.get("textual_envelope") for rec in mention_records):
            envelopes = [
                rec["textual_envelope"]
                for rec in mention_records
                if rec.get("textual_envelope")
            ]
        elif isinstance(self.graph_store, GraphReader):
            envelopes = await self.graph_store.get_entity_envelopes(entity.id)
        elif entity.textual_envelope:
            envelopes = [entity.textual_envelope]
        else:
            envelopes = []

        if not envelopes:
            logger.debug(
                f"Entity {entity.name} has no valid textual envelopes to synthesize."
            )
            return entity.model_copy(update={"is_mature": True})

        embeddings = as_tensor(
            await self.embedding_model.aget_text_embedding_batch(envelopes)
        )  # Shape: [N, hidden_size]
        embeddings_np = embeddings.detach().cpu().numpy()

        chunk_ids, perspectives = self._align_envelopes(
            envelopes, mention_records, chunk_to_doc
        )

        if self.config.enable_conception_stratification:
            polysemy_variance, clusters = self.conception_clusterer.stratify(
                envelopes,
                embeddings_np,
                envelope_chunk_ids=chunk_ids,
                envelope_perspectives=perspectives,
            )
        else:
            polysemy_variance = self.conception_clusterer.compute_spherical_variance(
                embeddings_np
            )
            clusters = []

        if len(clusters) >= 2:
            conceptions: list[EntityConception] = []
            for cluster in clusters:
                scoped_entity_name = f"{entity.name} [{cluster.perspective}]"
                cluster_desc = await self._synthesize_description(
                    scoped_entity_name, cluster.envelopes
                )
                if cluster_desc is None:
                    return None

                conceptions.append(
                    EntityConception(
                        id=f"{entity.id}::conception::{cluster.perspective}",
                        entity_id=entity.id,
                        perspective=cluster.perspective,
                        description=cluster_desc,
                        representative_envelopes=cluster.envelopes,
                        source_chunk_ids=cluster.chunk_ids,
                        centroid_dispersion=cluster.centroid_dispersion,
                        confidence=cluster.confidence,
                    )
                )

            combined_desc = " | ".join(
                f"[{c.perspective}] {c.description}" for c in conceptions
            )
            rounded_variance = round(polysemy_variance, 6)
            matured_entity = entity.model_copy(
                update={
                    "description": combined_desc,
                    "is_mature": True,
                    "conceptions": conceptions,
                    "polysemy_variance": rounded_variance,
                }
            )
            logger.info(
                f"Stratified entity {entity.name} into {len(conceptions)} conceptions "
                f"(polysemy_variance={rounded_variance:.4f})."
            )
            self.event_emitter.emit(
                EntityConceptionStratified(
                    run_id=run_id,
                    phase=self.name,
                    entity_id=entity.id,
                    entity_name=entity.name,
                    conception_count=len(conceptions),
                    polysemy_variance=rounded_variance,
                    perspectives=[c.perspective for c in conceptions],
                )
            )
            self.event_emitter.emit(
                EntityMaturationSynthesized(
                    run_id=run_id,
                    phase=self.name,
                    entity_id=entity.id,
                    entity_name=entity.name,
                    envelope_count=len(envelopes),
                    top_k_used=sum(
                        len(c.representative_envelopes) for c in conceptions
                    ),
                    synthesized_description=combined_desc,
                )
            )
            return matured_entity

        if len(envelopes) <= self.config.maturation_top_k:
            top_k_envelopes = envelopes
        else:
            centroid = torch.mean(embeddings, dim=0, keepdim=True)
            similarities = torch.nn.functional.cosine_similarity(embeddings, centroid)
            top_k_indices = torch.topk(
                similarities, self.config.maturation_top_k
            ).indices.tolist()
            top_k_envelopes = [envelopes[i] for i in top_k_indices]

        logger.debug(
            f"Synthesizing description for {entity.name} using "
            f"{len(top_k_envelopes)} representative contexts."
        )

        synthesized_desc = await self._synthesize_description(
            entity.name, top_k_envelopes
        )
        if synthesized_desc is None:
            return None

        matured_entity = entity.model_copy(
            update={
                "description": synthesized_desc,
                "is_mature": True,
                "polysemy_variance": round(polysemy_variance, 6),
            }
        )

        logger.info(f"Successfully matured entity {entity.name}.")

        self.event_emitter.emit(
            EntityMaturationSynthesized(
                run_id=run_id,
                phase=self.name,
                entity_id=entity.id,
                entity_name=entity.name,
                envelope_count=len(envelopes),
                top_k_used=len(top_k_envelopes),
                synthesized_description=synthesized_desc,
            )
        )
        return matured_entity
