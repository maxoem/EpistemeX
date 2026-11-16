"""Artifact-to-graph projection with topological bulk batching."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from itertools import batched
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    BaseArtifactPayload,
    DocumentArtifact,
    TheoreticalEnrichmentArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events import ArtifactProjected, get_event_emitter
from episteme_pipeline.graph.theory_graph_mapper import (
    build_reified_inference_edges,
    theory_inference_node_properties,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.graph_projection import (
    GraphProjectionProtocol,
    ProjectionBatchAccumulator,
)
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.schema.default_schema import SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import ArtifactCollection

logger = logging.getLogger(__name__)


def _resolve_edge_tenability(
    rel: TheoryRelation, edge_tenabilities: dict[str, float]
) -> float | None:
    """Resolve edge tenability for a pairwise or reified relation."""
    if rel.relation_id in edge_tenabilities:
        return edge_tenabilities[rel.relation_id]
    if rel.id is not None and rel.id in edge_tenabilities:
        return edge_tenabilities[rel.id]
    canonical_key = f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"
    return edge_tenabilities.get(canonical_key)


@dataclass(slots=True)
class ProjectionBatch(ProjectionBatchAccumulator):
    """Topological accumulator for bulk artifact-to-graph projection.

    Collects domain and edge items emitted by :class:`BaseArtifactPayload`
    instances and flushes them to a :class:`ProjectionGraph` in topological
    dependency order (**Nodes before Edges**), reifying conjunctive and
    targeted inferences into intermediate ``:TheoryInference`` warrant nodes.
    """

    documents: list[DocumentArtifact] = field(default_factory=list)
    chunks: list[L1Chunk] = field(default_factory=list)
    entities: list[L2Entity] = field(default_factory=list)
    theory_atoms: list[TheoryAtom] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    triples: list[L2Triple] = field(default_factory=list)
    theory_relations: list[TheoryRelation] = field(default_factory=list)
    enrichments: list[TheoreticalEnrichmentArtifact] = field(default_factory=list)
    schema: SchemaConfig | None = None
    t_norm: str | None = None

    def add_document(self, document: DocumentArtifact) -> None:
        """Register a document payload for node projection."""
        self.documents.append(document)

    def add_chunk(self, chunk: L1Chunk) -> None:
        """Register a domain chunk for bulk node projection."""
        self.chunks.append(chunk)

    def add_entity(self, entity: L2Entity) -> None:
        """Register a domain entity for bulk node projection."""
        self.entities.append(entity)

    def add_theory_atom(self, atom: TheoryAtom) -> None:
        """Register a theory atom for bulk node projection."""
        self.theory_atoms.append(atom)

    def add_relation(self, relation: dict[str, Any]) -> None:
        """Register a generic graph relation spec for bulk edge projection."""
        self.relations.append(relation)

    def add_triple(self, triple: L2Triple) -> None:
        """Register an L2 triple for bulk edge projection."""
        self.triples.append(triple)

    def add_theory_relation(self, relation: TheoryRelation) -> None:
        """Register a theory relation for bulk edge projection."""
        self.theory_relations.append(relation)

    def add_enrichment(self, enrichment: TheoreticalEnrichmentArtifact) -> None:
        """Register a theoretical enrichment payload for post-projection edge updates."""
        self.enrichments.append(enrichment)

    async def flush(
        self,
        graph_store: ProjectionGraph,
        batch_size: int = 500,
        *,
        schema: SchemaConfig | None = None,
        t_norm: str | None = None,
    ) -> None:
        """Flush accumulated items to ``graph_store`` in topological order (Nodes before Edges).

        Parameters
        ----------
        graph_store : ProjectionGraph
            Target projection graph store.
        batch_size : int, default 500
            Maximum number of items per bulk ``GraphWriter`` batch call.
        schema : SchemaConfig or None, optional
            Optional schema override for polarity/backing resolution.
        t_norm : str or None, optional
            Optional conjunctive t-norm label stamped onto ``:TheoryInference`` nodes.
        """
        effective_batch = max(1, batch_size)
        eff_schema = schema or self.schema
        eff_t_norm = t_norm if t_norm is not None else self.t_norm
        theory_relations = self.theory_relations

        if self.enrichments and theory_relations:
            edge_tenabilities: dict[str, float] = {}
            for enr in self.enrichments:
                edge_tenabilities.update(enr.edge_tenabilities)
            if edge_tenabilities:
                updated_rels: list[TheoryRelation] = []
                for rel in theory_relations:
                    tenability = _resolve_edge_tenability(rel, edge_tenabilities)
                    updated_rels.append(
                        rel.model_copy(update={"edge_tenability": tenability})
                        if tenability is not None
                        else rel
                    )
                theory_relations = updated_rels

        known_atom_ids: set[str] = {atom.id for atom in self.theory_atoms}
        known_rel_ids: set[str] = set()
        for rel in theory_relations:
            known_rel_ids.add(rel.relation_id)
            if rel.id is not None:
                known_rel_ids.add(rel.id)

        targeted_rel_ids: set[str] = set()
        for rel in theory_relations:
            if rel.undercuts_relation_id is not None:
                targeted_rel_ids.add(rel.undercuts_relation_id)
            elif rel.target_id and rel.target_id not in known_atom_ids:
                is_known_rel = rel.target_id in known_rel_ids
                is_implicit_undercutter = (
                    bool(known_atom_ids)
                    and rel.relation_type.strip().upper() == "UNDERCUTS"
                )
                if is_known_rel or is_implicit_undercutter:
                    targeted_rel_ids.add(rel.target_id)

        reified_indices: set[int] = set()
        reified_rels: list[TheoryRelation] = []
        reified_ids: set[str] = set()
        for idx, rel in enumerate(theory_relations):
            matches_target = rel.relation_id in targeted_rel_ids or (
                rel.id is not None and rel.id in targeted_rel_ids
            )
            if rel.has_conjunctive_premises or matches_target:
                reified_indices.add(idx)
                reified_rels.append(rel)
                reified_ids.add(rel.relation_id)
                if rel.id is not None:
                    reified_ids.add(rel.id)

        all_reified_ids = reified_ids | targeted_rel_ids

        # ------------------------------------------------------------------
        # Pass 1: Nodes (Documents -> Chunks -> Entities -> TheoryAtoms -> TheoryInferences)
        # ------------------------------------------------------------------
        for doc in self.documents:
            await doc.project_to_graph(graph_store)

        for chunk_batch in batched(self.chunks, effective_batch):
            await graph_store.upsert_chunks(list(chunk_batch))

        for entity_batch in batched(self.entities, effective_batch):
            await graph_store.upsert_entities(list(entity_batch))

        for atom_batch in batched(self.theory_atoms, effective_batch):
            await graph_store.upsert_argument_components(list(atom_batch))

        for rel in reified_rels:
            await graph_store.upsert_node(
                "TheoryInference",
                rel.relation_id,
                theory_inference_node_properties(
                    rel,
                    schema=eff_schema,
                    t_norm=eff_t_norm,
                ),
            )

        for stub_id in sorted(targeted_rel_ids - reified_ids):
            await graph_store.upsert_node(
                "TheoryInference",
                stub_id,
                {"id": stub_id},
            )

        # ------------------------------------------------------------------
        # Pass 2: Edges (Mentions/Canonicalizations -> Triples -> Reified Hyperedges -> TheoryRelations)
        # ------------------------------------------------------------------
        for rel_batch in batched(self.relations, effective_batch):
            await graph_store.upsert_relations(list(rel_batch))

        for triple_batch in batched(self.triples, effective_batch):
            await graph_store.upsert_triples(list(triple_batch))

        hypergraph_edges: list[dict[str, Any]] = []
        pairwise_relations: list[TheoryRelation] = []
        for idx, rel in enumerate(theory_relations):
            is_reified = idx in reified_indices
            targets_reified = (
                rel.undercuts_relation_id is not None
                or rel.target_id in all_reified_ids
            )
            if is_reified or targets_reified:
                hypergraph_edges.extend(
                    build_reified_inference_edges(
                        rel,
                        is_reified=is_reified,
                        reified_ids=all_reified_ids,
                        schema=eff_schema,
                    )
                )
            else:
                pairwise_relations.append(rel)

        for hyper_batch in batched(hypergraph_edges, effective_batch):
            await graph_store.upsert_relations(list(hyper_batch))

        for trel_batch in batched(pairwise_relations, effective_batch):
            await graph_store.upsert_theory_relations(list(trel_batch))


class ArtifactGraphProjector(GraphProjectionProtocol):
    """Projects durable run artifacts into a :class:`ProjectionGraph` in topological order.

    Parameters
    ----------
    graph_store : ProjectionGraph
        Target projection graph store.
    schema : SchemaConfig or None, optional
        Domain schema configuration.
    t_norm : str or None, optional
        Conjunctive t-norm operator recorded on reified ``:TheoryInference`` nodes.
    """

    def __init__(
        self,
        graph_store: ProjectionGraph,
        schema: SchemaConfig | None = None,
        t_norm: str | None = None,
    ) -> None:
        self.graph_store = graph_store
        self.schema = schema or SchemaConfig()
        self.t_norm = t_norm

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            Projector class identity, schema state, and t-norm configuration.
        """
        if isinstance(self.schema, Fingerprintable):
            schema_fp: Any = self.schema.fingerprint()
        elif isinstance(self.schema, BaseModel):
            schema_fp = self.schema.model_dump(mode="json")
        else:
            schema_fp = {"class": type(self.schema).__name__}
        return {
            "class": self.__class__.__name__,
            "schema": schema_fp,
            "t_norm": self.t_norm,
        }

    async def project(self, artifact: ArtifactEnvelope) -> None:
        """Project a single :class:`ArtifactEnvelope` into the target graph.

        Parameters
        ----------
        artifact : ArtifactEnvelope
            Artifact envelope to project.
        """
        start = time.perf_counter()
        emitter = get_event_emitter()
        artifact_kind_label = artifact.kind.value
        payload = artifact.payload
        if isinstance(payload, TheoryRelationArtifact):
            try:
                batch = ProjectionBatch(schema=self.schema, t_norm=self.t_norm)
                batch.add_theory_relation(payload.to_domain())
                await batch.flush(
                    self.graph_store,
                    batch_size=1,
                    schema=self.schema,
                    t_norm=self.t_norm,
                )
            except Exception:
                emitter.emit(
                    ArtifactProjected(
                        artifact_type=artifact_kind_label,
                        duration_seconds=time.perf_counter() - start,
                        success=False,
                    )
                )
                raise
            emitter.emit(
                ArtifactProjected(
                    artifact_type=artifact_kind_label,
                    duration_seconds=time.perf_counter() - start,
                    success=True,
                )
            )
            return

        if isinstance(payload, BaseArtifactPayload):
            try:
                await payload.project_to_graph(self.graph_store)
            except Exception:
                emitter.emit(
                    ArtifactProjected(
                        artifact_type=artifact_kind_label,
                        duration_seconds=time.perf_counter() - start,
                        success=False,
                    )
                )
                raise
            emitter.emit(
                ArtifactProjected(
                    artifact_type=artifact_kind_label,
                    duration_seconds=time.perf_counter() - start,
                    success=True,
                )
            )
            return

        logger.warning(
            "No projection rule for payload %s (artifact %s, phase %s) — dropped.",
            type(payload).__name__,
            artifact.artifact_id,
            artifact.phase_name,
        )
        emitter.emit(
            ArtifactProjected(
                artifact_type=artifact_kind_label,
                duration_seconds=time.perf_counter() - start,
                success=False,
            )
        )

    async def project_collection(
        self, collection: ArtifactCollection, batch_size: int = 500
    ) -> None:
        """Bulk-project an :class:`ArtifactCollection` in topological order (Nodes before Edges).

        Parameters
        ----------
        collection : ArtifactCollection
            Artifact collection to project (uses ``latest_by_identity``).
        batch_size : int, default 500
            Maximum number of items per bulk ``GraphWriter`` batch call.
        """
        envelopes = list(collection.latest_by_identity.values())
        if not envelopes:
            return

        start = time.perf_counter()
        emitter = get_event_emitter()
        batch = ProjectionBatch(schema=self.schema, t_norm=self.t_norm)
        for envelope in envelopes:
            payload = envelope.payload
            if isinstance(payload, BaseArtifactPayload):
                payload.collect_for_projection(batch)
            else:
                logger.warning(
                    "No projection rule for payload %s (artifact %s, phase %s) — dropped.",
                    type(payload).__name__,
                    envelope.artifact_id,
                    envelope.phase_name,
                )

        try:
            await batch.flush(
                self.graph_store,
                batch_size=batch_size,
                schema=self.schema,
                t_norm=self.t_norm,
            )
        except Exception:
            emitter.emit(
                ArtifactProjected(
                    artifact_type="ArtifactCollection",
                    duration_seconds=time.perf_counter() - start,
                    success=False,
                )
            )
            raise
        emitter.emit(
            ArtifactProjected(
                artifact_type="ArtifactCollection",
                duration_seconds=time.perf_counter() - start,
                success=True,
            )
        )
