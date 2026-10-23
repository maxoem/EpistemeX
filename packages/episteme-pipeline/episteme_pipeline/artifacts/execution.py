"""Artifact collection, cumulative epistemic state views, and phase execution context.

Implements:
- Identity-keyed versioning (last-write-wins per ``identity_key``) in
  :class:`ArtifactCollection` while preserving full append-only ``history``.
- Canonical L2 entity and triple resolution from :class:`CanonicalizationArtifact`
  envelopes emitted by Phase 3b.
- Canonical L3 theory atom and relation resolution from :class:`FusionDecisionArtifact`
  envelopes emitted by Phase 5.
- Cumulative :class:`EpistemicStateView` hierarchy (:class:`Phase1ArtifactsView`
  through :class:`Phase4ArtifactsView`) with explicit ``consumed_artifact_ids``
  lineage tracking and :meth:`~EpistemicStateView.to_graph_reader` factory.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from episteme_pipeline.artifacts.builders import parse_mention_id
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactPayload,
    CanonicalizationArtifact,
    ChunkArtifact,
    DocumentArtifact,
    EntityMentionArtifact,
    FusionDecisionArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
    TheoreticalEnrichmentArtifact,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.runs.models import RunManifest


def _strip_artifact_prefix(raw_id: str) -> str:
    """Strip ``artifact::...::`` or ``artifact::`` prefixes from an ID string.

    Parameters
    ----------
    raw_id : str
        Artifact or domain identifier.

    Returns
    -------
    str
        Normalized domain identifier.
    """
    for prefix in (
        "artifact::theory-atom::",
        "artifact::argument_component::",
        "artifact::linked_entity::",
        "artifact::",
    ):
        if raw_id.startswith(prefix):
            return raw_id[len(prefix) :]
    return raw_id


def _resolve_alias_chain(node_id: str, alias_map: dict[str, str]) -> str:
    """Follow transitive canonicalization mappings with cycle protection.

    Parameters
    ----------
    node_id : str
        Starting entity or atom identifier.
    alias_map : dict of str to str
        Mapping from merged alias ID to canonical target ID.

    Returns
    -------
    str
        Resolved canonical identifier.
    """
    visited: set[str] = set()
    curr = node_id
    while curr in alias_map and curr not in visited:
        visited.add(curr)
        curr = alias_map[curr]
    return curr


class ArtifactCollection:
    """Collection of artifact envelopes maintaining history and identity-keyed lookup.

    Parameters
    ----------
    artifacts : Iterable of ArtifactEnvelope, optional
        Initial sequence of artifact envelopes.
    """

    __slots__ = ("history", "latest_by_identity")

    def __init__(
        self, artifacts: Iterable[ArtifactEnvelope[ArtifactPayload]] = ()
    ) -> None:
        self.history: list[ArtifactEnvelope[ArtifactPayload]] = list(artifacts)
        self.latest_by_identity: dict[str, ArtifactEnvelope[ArtifactPayload]] = {}
        for artifact in self.history:
            key = artifact.identity_key or artifact.artifact_id
            self.latest_by_identity[key] = artifact

    @property
    def artifacts(self) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """Return the append-only history of artifact envelopes.

        Returns
        -------
        list of ArtifactEnvelope
            All envelopes added to this collection in emission order.
        """
        return self.history

    @artifacts.setter
    def artifacts(
        self, value: Iterable[ArtifactEnvelope[ArtifactPayload]]
    ) -> None:
        self.history = list(value)
        self.latest_by_identity = {
            (a.identity_key or a.artifact_id): a for a in self.history
        }

    def __len__(self) -> int:
        """Return the number of artifact envelopes in ``history``.

        Returns
        -------
        int
            Count of envelopes in history.
        """
        return len(self.history)

    def __iter__(self) -> Iterator[ArtifactEnvelope[ArtifactPayload]]:
        """Iterate over the artifact envelopes in ``history``.

        Returns
        -------
        Iterator of ArtifactEnvelope
            Iterator over envelopes.
        """
        return iter(self.history)

    def __getitem__(self, index: int) -> ArtifactEnvelope[ArtifactPayload]:
        """Index into the artifact collection history.

        Parameters
        ----------
        index : int
            Position index.

        Returns
        -------
        ArtifactEnvelope
            Artifact envelope at ``index``.
        """
        return self.history[index]

    def of_kind(
        self, *kinds: ArtifactKind, latest_only: bool = True
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """Return artifact envelopes matching ``kinds``.

        Parameters
        ----------
        *kinds : ArtifactKind
            Target artifact kinds to filter by.
        latest_only : bool, default True
            When ``True`` (default), returns only the most recently emitted
            envelope per ``identity_key`` (last-write-wins). When ``False``,
            returns all matching envelopes from ``history``.

        Returns
        -------
        list of ArtifactEnvelope
            Filtered artifact envelopes.
        """
        allowed = set(kinds)
        source: Iterable[ArtifactEnvelope[ArtifactPayload]] = (
            self.latest_by_identity.values() if latest_only else self.history
        )
        return [artifact for artifact in source if artifact.kind in allowed]


def _extract_l1_state(
    collection: ArtifactCollection,
) -> tuple[list[L1Document], list[L1Chunk], list[str]]:
    """Hydrate Phase 1 documents and chunks along with consumed artifact IDs."""
    documents: list[L1Document] = []
    chunks: list[L1Chunk] = []
    consumed_ids: list[str] = []

    for artifact in collection.of_kind(
        ArtifactKind.DOCUMENT, ArtifactKind.CHUNK, latest_only=True
    ):
        consumed_ids.append(artifact.artifact_id)
        payload = artifact.payload
        if artifact.kind == ArtifactKind.DOCUMENT and isinstance(
            payload, DocumentArtifact
        ):
            documents.append(payload.to_domain())
        elif artifact.kind == ArtifactKind.CHUNK and isinstance(
            payload, ChunkArtifact
        ):
            chunks.append(payload.to_domain())
    return documents, chunks, consumed_ids


def _extract_l2_state(
    collection: ArtifactCollection,
) -> tuple[
    list[L2Entity],
    list[L2Triple],
    dict[str, int],
    dict[str, list[str]],
    dict[str, list[dict[str, str]]],
    dict[str, str],
    list[str],
]:
    """Hydrate and canonicalize Phase 2 / 3b / 4-maturation L2 state."""
    consumed_ids: list[str] = []
    alias_map: dict[str, str] = {}

    for canon_art in collection.of_kind(
        ArtifactKind.CANONICALIZATION, latest_only=True
    ):
        consumed_ids.append(canon_art.artifact_id)
        payload = canon_art.payload
        if isinstance(payload, CanonicalizationArtifact):
            canon_id = _strip_artifact_prefix(payload.canonical_entity_id)
            for orig_id in payload.merged_entity_ids:
                clean_orig = _strip_artifact_prefix(orig_id)
                if clean_orig and clean_orig != canon_id:
                    alias_map[clean_orig] = canon_id

    mention_chunk_ids_by_entity: dict[str, list[str]] = {}
    entity_envelopes_by_id: dict[str, list[str]] = {}
    entity_mentions_by_id: dict[str, list[dict[str, str]]] = {}

    l2_envelopes = collection.of_kind(
        ArtifactKind.ENTITY_MENTION,
        ArtifactKind.LINKED_ENTITY,
        ArtifactKind.LOCAL_RELATION,
        latest_only=True,
    )

    for artifact in l2_envelopes:
        if artifact.kind == ArtifactKind.ENTITY_MENTION and isinstance(
            artifact.payload, EntityMentionArtifact
        ):
            consumed_ids.append(artifact.artifact_id)
            payload = artifact.payload
            raw_eid, parsed_cid = parse_mention_id(payload.mention_id)
            eid = payload.entity_id or raw_eid
            cid = payload.chunk_id or parsed_cid
            canon_eid = _resolve_alias_chain(eid, alias_map)

            if cid:
                cids = mention_chunk_ids_by_entity.setdefault(canon_eid, [])
                if cid not in cids:
                    cids.append(cid)
            if payload.textual_envelope:
                envs = entity_envelopes_by_id.setdefault(canon_eid, [])
                if payload.textual_envelope not in envs:
                    envs.append(payload.textual_envelope)
            recs = entity_mentions_by_id.setdefault(canon_eid, [])
            mention_rec = {
                "mention_id": f"mention::{canon_eid}::{cid}" if cid else payload.mention_id,
                "chunk_id": cid,
            }
            if mention_rec not in recs:
                recs.append(mention_rec)

    raw_entities: list[L2Entity] = []
    raw_local_triples: list[L2Triple] = []

    for artifact in l2_envelopes:
        payload = artifact.payload
        if artifact.kind == ArtifactKind.LINKED_ENTITY and isinstance(
            payload, LinkedEntityArtifact
        ):
            consumed_ids.append(artifact.artifact_id)
            raw_entities.append(payload.to_domain())
        elif artifact.kind == ArtifactKind.LOCAL_RELATION and isinstance(
            payload, LocalRelationArtifact
        ):
            consumed_ids.append(artifact.artifact_id)
            raw_local_triples.append(payload.to_domain())

    # Group and canonicalize entities via alias_map
    grouped_entities: dict[str, list[L2Entity]] = {}
    for entity in raw_entities:
        canon_id = _resolve_alias_chain(entity.id, alias_map)
        grouped_entities.setdefault(canon_id, []).append(entity)

    canonical_entities: list[L2Entity] = []
    entity_count_by_type: dict[str, int] = {}

    for canon_id, group in grouped_entities.items():
        # Prefer the representative whose ID already equals canon_id
        rep = next((e for e in group if e.id == canon_id), group[0])
        merged_chunks: list[str] = []
        for member in group:
            for cid in member.source_chunk_ids:
                if cid not in merged_chunks:
                    merged_chunks.append(cid)
            if member.textual_envelope:
                envs = entity_envelopes_by_id.setdefault(canon_id, [])
                if member.textual_envelope not in envs:
                    envs.append(member.textual_envelope)
        for cid in mention_chunk_ids_by_entity.get(canon_id, []):
            if cid not in merged_chunks:
                merged_chunks.append(cid)

        description = rep.description or next(
            (m.description for m in group if m.description), None
        )
        textual_envelope = rep.textual_envelope or next(
            (m.textual_envelope for m in group if m.textual_envelope), None
        )
        if not textual_envelope and entity_envelopes_by_id.get(canon_id):
            textual_envelope = entity_envelopes_by_id[canon_id][0]

        is_mature = any(m.is_mature for m in group)
        conf_vals = [m.confidence for m in group if m.confidence is not None]
        max_conf = max(conf_vals) if conf_vals else rep.confidence

        canon_entity = rep.model_copy(
            update={
                "id": canon_id,
                "source_chunk_ids": merged_chunks,
                "description": description,
                "textual_envelope": textual_envelope,
                "is_mature": is_mature,
                "confidence": max_conf,
            }
        )
        canonical_entities.append(canon_entity)
        entity_count_by_type[canon_entity.label] = (
            entity_count_by_type.get(canon_entity.label, 0) + 1
        )

    canonical_local_triples = _canonicalize_triples(raw_local_triples, alias_map)
    return (
        canonical_entities,
        canonical_local_triples,
        entity_count_by_type,
        entity_envelopes_by_id,
        entity_mentions_by_id,
        alias_map,
        consumed_ids,
    )


def _canonicalize_triples(
    triples: list[L2Triple], alias_map: dict[str, str]
) -> list[L2Triple]:
    """Rewrite triple endpoints via ``alias_map`` and deduplicate parallel edges."""
    if not alias_map:
        return list(triples)

    deduped: dict[tuple[str, str, str, str, str | None], L2Triple] = {}
    for triple in triples:
        new_subj = _resolve_alias_chain(triple.subject_id, alias_map)
        new_obj = _resolve_alias_chain(triple.object_id, alias_map)
        # Drop self-loops induced by merging two distinct alias entities
        if triple.subject_id != triple.object_id and new_subj == new_obj:
            continue
        rewritten = (
            triple.model_copy(
                update={"subject_id": new_subj, "object_id": new_obj}
            )
            if (new_subj != triple.subject_id or new_obj != triple.object_id)
            else triple
        )
        key = (
            rewritten.subject_id,
            rewritten.predicate,
            rewritten.object_id,
            rewritten.scope,
            rewritten.source_chunk_id if rewritten.scope == "local" else None,
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = rewritten
        else:
            t_confs = [
                c
                for c in (existing.confidence, rewritten.confidence)
                if c is not None
            ]
            best_conf = max(t_confs) if t_confs else existing.confidence
            reranks = [
                r
                for r in (existing.rerank_score, rewritten.rerank_score)
                if r is not None
            ]
            best_rerank = max(reranks) if reranks else None
            deduped[key] = existing.model_copy(
                update={"confidence": best_conf, "rerank_score": best_rerank}
            )
    return list(deduped.values())


def _resolve_l3_atoms_and_relations(
    theory_atoms: list[TheoryAtom],
    theory_relations: list[TheoryRelation],
    fusion_decisions: list[FusionDecisionArtifact],
) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
    """Apply Phase 5 ``FusionDecisionArtifact`` decisions to produce canonical L3 graph.

    Parameters
    ----------
    theory_atoms : list of TheoryAtom
        Raw theory atoms from Phase 4 / 6.
    theory_relations : list of TheoryRelation
        Raw theory relations from Phase 4 / 6.
    fusion_decisions : list of FusionDecisionArtifact
        Cluster and merge decisions from Phase 5.

    Returns
    -------
    tuple of (list of TheoryAtom, list of TheoryRelation)
        Canonicalized theory atoms and theory relations.
    """
    if not fusion_decisions:
        return list(theory_atoms), list(theory_relations)

    atom_alias_map: dict[str, str] = {}
    for decision in fusion_decisions:
        if decision.decision_type not in ("cluster", "merge"):
            continue
        clean_ids = [
            _strip_artifact_prefix(aid)
            for aid in decision.artifact_ids
            if _strip_artifact_prefix(aid)
        ]
        if len(clean_ids) < 2:
            continue
        canon_id = (
            _strip_artifact_prefix(decision.canonical_artifact_id)
            if decision.canonical_artifact_id
            else clean_ids[0]
        )
        for member_id in clean_ids:
            if member_id != canon_id:
                atom_alias_map[member_id] = canon_id

    if not atom_alias_map:
        return list(theory_atoms), list(theory_relations)

    grouped_atoms: dict[str, list[TheoryAtom]] = {}
    for atom in theory_atoms:
        canon_id = _resolve_alias_chain(atom.id, atom_alias_map)
        grouped_atoms.setdefault(canon_id, []).append(atom)

    canonical_atoms: list[TheoryAtom] = []
    for canon_id, group in grouped_atoms.items():
        rep = next((a for a in group if a.id == canon_id), group[0])
        if len(group) == 1 and rep.id == canon_id:
            canonical_atoms.append(rep)
            continue

        merged_entity_ids: list[str] = []
        merged_measurements = list(rep.measurements)
        merged_parameters: dict[str, Any] = dict(rep.parameters)
        for member in group:
            for eid in member.entity_ids:
                if eid not in merged_entity_ids:
                    merged_entity_ids.append(eid)
            for meas in member.measurements:
                if meas not in merged_measurements:
                    merged_measurements.append(meas)
            for pk, pv in member.parameters.items():
                merged_parameters.setdefault(pk, pv)

        conf_vals = [m.confidence for m in group if m.confidence is not None]
        max_conf = max(conf_vals) if conf_vals else rep.confidence
        plaus_vals = [m.plausibility for m in group if m.plausibility is not None]
        max_plaus = max(plaus_vals) if plaus_vals else rep.plausibility
        modal_vals = [m.modal_strength for m in group if m.modal_strength is not None]
        max_modal = max(modal_vals) if modal_vals else rep.modal_strength
        base_scores = [m.base_score for m in group if m.base_score is not None]
        best_base = max(base_scores) if base_scores else rep.base_score
        tenability = rep.tenability or next(
            (m.tenability for m in group if m.tenability is not None), None
        )

        canonical_atoms.append(
            rep.model_copy(
                update={
                    "id": canon_id,
                    "entity_ids": merged_entity_ids,
                    "measurements": merged_measurements,
                    "parameters": merged_parameters,
                    "confidence": max_conf,
                    "plausibility": max_plaus,
                    "modal_strength": max_modal,
                    "base_score": best_base,
                    "tenability": tenability,
                }
            )
        )

    deduped_relations: dict[tuple[str, str, str], TheoryRelation] = {}
    for rel in theory_relations:
        new_src = _resolve_alias_chain(rel.source_id, atom_alias_map)
        new_tgt = _resolve_alias_chain(rel.target_id, atom_alias_map)
        if rel.source_id != rel.target_id and new_src == new_tgt:
            continue
        rewritten = (
            rel.model_copy(update={"source_id": new_src, "target_id": new_tgt})
            if (new_src != rel.source_id or new_tgt != rel.target_id)
            else rel
        )
        rkey = (rewritten.source_id, rewritten.relation_type, rewritten.target_id)
        existing = deduped_relations.get(rkey)
        if existing is None:
            deduped_relations[rkey] = rewritten
        else:
            if (rewritten.confidence or 0.0) > (existing.confidence or 0.0):
                deduped_relations[rkey] = rewritten

    return canonical_atoms, list(deduped_relations.values())


@dataclass(slots=True)
class EpistemicStateView:
    """Base contract for cumulative inter-phase artifact views."""

    documents: list[L1Document] = field(default_factory=list)
    chunks: list[L1Chunk] = field(default_factory=list)
    entities: list[L2Entity] = field(default_factory=list)
    local_triples: list[L2Triple] = field(default_factory=list)
    entity_count_by_type: dict[str, int] = field(default_factory=dict)
    global_triples: list[L2Triple] = field(default_factory=list)
    relation_type_distribution: dict[str, int] = field(default_factory=dict)
    theory_atoms: list[TheoryAtom] = field(default_factory=list)
    theory_relations: list[TheoryRelation] = field(default_factory=list)
    fusion_decisions: list[FusionDecisionArtifact] = field(default_factory=list)
    canonical_theory_atoms: list[TheoryAtom] = field(default_factory=list)
    canonical_theory_relations: list[TheoryRelation] = field(default_factory=list)
    entity_envelopes_by_id: dict[str, list[str]] = field(default_factory=dict)
    entity_mentions_by_id: dict[str, list[dict[str, str]]] = field(
        default_factory=dict
    )
    consumed_artifact_ids: list[str] = field(default_factory=list)

    def to_graph_reader(self) -> ArtifactSubgraphReader:
        """Build an in-memory :class:`ArtifactSubgraphReader` from this view.

        Returns
        -------
        ArtifactSubgraphReader
            Deterministic in-memory graph reader over this view's state.
        """
        return ArtifactSubgraphReader.from_view(self)


@dataclass(slots=True)
class Phase1ArtifactsView(EpistemicStateView):
    """Cumulative view of Phase 1 foundation artifacts."""

    _allowed_kinds = (ArtifactKind.DOCUMENT, ArtifactKind.CHUNK)

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> Phase1ArtifactsView:
        """Hydrate a :class:`Phase1ArtifactsView` from an :class:`ArtifactCollection`."""
        documents, chunks, consumed_ids = _extract_l1_state(collection)
        return cls(
            documents=documents,
            chunks=chunks,
            consumed_artifact_ids=consumed_ids,
        )


@dataclass(slots=True)
class Phase2ArtifactsView(EpistemicStateView):
    """Cumulative view of Phase 1 + Phase 2 / 3b / 4-maturation artifacts."""

    _allowed_kinds = (
        ArtifactKind.DOCUMENT,
        ArtifactKind.CHUNK,
        ArtifactKind.ENTITY_MENTION,
        ArtifactKind.LINKED_ENTITY,
        ArtifactKind.LOCAL_RELATION,
        ArtifactKind.CANONICALIZATION,
    )

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> Phase2ArtifactsView:
        """Hydrate a canonicalized :class:`Phase2ArtifactsView` from ``collection``."""
        documents, chunks, l1_ids = _extract_l1_state(collection)
        (
            entities,
            local_triples,
            entity_count_by_type,
            entity_envelopes_by_id,
            entity_mentions_by_id,
            _alias_map,
            l2_ids,
        ) = _extract_l2_state(collection)
        return cls(
            entities=entities,
            local_triples=local_triples,
            entity_count_by_type=entity_count_by_type,
            documents=documents,
            chunks=chunks,
            entity_envelopes_by_id=entity_envelopes_by_id,
            entity_mentions_by_id=entity_mentions_by_id,
            consumed_artifact_ids=[*l1_ids, *l2_ids],
        )


@dataclass(slots=True)
class Phase3ArtifactsView(EpistemicStateView):
    """Cumulative view of Phase 1 + Phase 2/3b/4-maturation + Phase 3 artifacts."""

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> Phase3ArtifactsView:
        """Hydrate a cumulative :class:`Phase3ArtifactsView` from ``collection``."""
        documents, chunks, l1_ids = _extract_l1_state(collection)
        (
            entities,
            local_triples,
            entity_count_by_type,
            entity_envelopes_by_id,
            entity_mentions_by_id,
            alias_map,
            l2_ids,
        ) = _extract_l2_state(collection)

        raw_global_triples: list[L2Triple] = []
        l3_ids: list[str] = []
        for artifact in collection.of_kind(
            ArtifactKind.GLOBAL_RELATION, latest_only=True
        ):
            payload = artifact.payload
            if isinstance(payload, GlobalRelationArtifact):
                l3_ids.append(artifact.artifact_id)
                raw_global_triples.append(payload.to_domain())

        global_triples = _canonicalize_triples(raw_global_triples, alias_map)
        distribution: dict[str, int] = {}
        for triple in global_triples:
            distribution[triple.predicate] = (
                distribution.get(triple.predicate, 0) + 1
            )

        return cls(
            global_triples=global_triples,
            relation_type_distribution=distribution,
            chunks=chunks,
            documents=documents,
            entities=entities,
            local_triples=local_triples,
            entity_count_by_type=entity_count_by_type,
            entity_envelopes_by_id=entity_envelopes_by_id,
            entity_mentions_by_id=entity_mentions_by_id,
            consumed_artifact_ids=[*l1_ids, *l2_ids, *l3_ids],
        )


@dataclass(slots=True)
class Phase4ArtifactsView(EpistemicStateView):
    """Cumulative view of Phase 1–5 artifacts including canonical L3 fusion."""

    def __post_init__(self) -> None:
        if not self.canonical_theory_atoms and self.theory_atoms:
            canon_atoms, canon_rels = _resolve_l3_atoms_and_relations(
                self.theory_atoms, self.theory_relations, self.fusion_decisions
            )
            self.canonical_theory_atoms = canon_atoms
            if not self.canonical_theory_relations:
                self.canonical_theory_relations = canon_rels
        elif not self.canonical_theory_relations and self.theory_relations:
            _, canon_rels = _resolve_l3_atoms_and_relations(
                self.theory_atoms, self.theory_relations, self.fusion_decisions
            )
            self.canonical_theory_relations = canon_rels

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> Phase4ArtifactsView:
        """Hydrate a cumulative :class:`Phase4ArtifactsView` from ``collection``."""
        p3 = Phase3ArtifactsView.from_collection(collection)

        components: list[TheoryAtom] = []
        relations: list[TheoryRelation] = []
        fusion_decisions: list[FusionDecisionArtifact] = []
        enrichments: list[TheoreticalEnrichmentArtifact] = []
        p4_ids: list[str] = []

        for artifact in collection.of_kind(
            ArtifactKind.THEORY_ATOM,
            ArtifactKind.THEORY_RELATION,
            ArtifactKind.FUSION_DECISION,
            ArtifactKind.THEORETICAL_ENRICHMENT,
            latest_only=True,
        ):
            p4_ids.append(artifact.artifact_id)
            payload = artifact.payload
            if artifact.kind == ArtifactKind.THEORY_ATOM and isinstance(
                payload, TheoryAtomArtifact
            ):
                components.append(payload.to_domain())
            elif artifact.kind == ArtifactKind.THEORY_RELATION and isinstance(
                payload, TheoryRelationArtifact
            ):
                relations.append(payload.to_domain())
            elif artifact.kind == ArtifactKind.FUSION_DECISION and isinstance(
                payload, FusionDecisionArtifact
            ):
                fusion_decisions.append(payload)
            elif artifact.kind == ArtifactKind.THEORETICAL_ENRICHMENT and isinstance(
                payload, TheoreticalEnrichmentArtifact
            ):
                enrichments.append(payload)

        if enrichments:
            edge_tenability_map: dict[str, float] = {}
            for enr in enrichments:
                edge_tenability_map.update(enr.edge_tenabilities)
            if edge_tenability_map:
                updated_rels: list[TheoryRelation] = []
                for rel in relations:
                    rkey = f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"
                    if rkey in edge_tenability_map:
                        updated_rels.append(
                            rel.model_copy(
                                update={"tenability": edge_tenability_map[rkey]}
                            )
                        )
                    else:
                        updated_rels.append(rel)
                relations = updated_rels

        canon_atoms, canon_rels = _resolve_l3_atoms_and_relations(
            components, relations, fusion_decisions
        )

        return cls(
            theory_atoms=components,
            theory_relations=relations,
            fusion_decisions=fusion_decisions,
            canonical_theory_atoms=canon_atoms,
            canonical_theory_relations=canon_rels,
            documents=p3.documents,
            chunks=p3.chunks,
            entities=p3.entities,
            local_triples=p3.local_triples,
            entity_count_by_type=p3.entity_count_by_type,
            global_triples=p3.global_triples,
            relation_type_distribution=p3.relation_type_distribution,
            entity_envelopes_by_id=p3.entity_envelopes_by_id,
            entity_mentions_by_id=p3.entity_mentions_by_id,
            consumed_artifact_ids=[*p3.consumed_artifact_ids, *p4_ids],
        )


Phase5ArtifactsView = Phase4ArtifactsView


@dataclass(slots=True)
class TheoreticalEnrichmentArtifactsView:
    """Artifact view for theoretical enrichment and tenability evaluation results.

    Parameters
    ----------
    enrichments : list of TheoreticalEnrichmentArtifact
        Enrichment and tenability score artifacts.
    """

    _allowed_kinds = (ArtifactKind.THEORETICAL_ENRICHMENT,)

    enrichments: list[TheoreticalEnrichmentArtifact] = field(default_factory=list)
    consumed_artifact_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_collection(
        cls, collection: ArtifactCollection
    ) -> TheoreticalEnrichmentArtifactsView:
        """Construct the view from an artifact collection."""
        enrichments: list[TheoreticalEnrichmentArtifact] = []
        consumed_ids: list[str] = []
        for artifact in collection.of_kind(*cls._allowed_kinds, latest_only=True):
            payload = artifact.payload
            if isinstance(payload, TheoreticalEnrichmentArtifact):
                consumed_ids.append(artifact.artifact_id)
                enrichments.append(payload)
        return cls(enrichments=enrichments, consumed_artifact_ids=consumed_ids)


@dataclass(slots=True)
class ArtifactExecutionContext:
    """Per-phase execution context carrying run metadata and upstream artifacts.

    Parameters
    ----------
    run_id : str
        Unique run identifier.
    manifest : RunManifest
        Run manifest.
    pipeline_input : PipelineInput
        Initial pipeline input contract.
    previous : ArtifactCollection or None, optional
        Cumulative artifact collection from completed upstream phases.
    lineage_fingerprint : str or None, optional
        Deterministic lineage fingerprint for the currently executing phase.
    prior_artifacts : ArtifactCollection or None, optional
        Cumulative artifact collection hydrated from historical parent run lineage.
    prior_manifest : RunManifest or None, optional
        RunManifest of the immediate parent or resume run.
    """

    run_id: str
    manifest: RunManifest
    pipeline_input: PipelineInput
    previous: ArtifactCollection | None = None
    lineage_fingerprint: str | None = None
    prior_artifacts: ArtifactCollection | None = None
    prior_manifest: RunManifest | None = None
