from __future__ import annotations

from episteme_pipeline.artifacts.codecs import (
    ChunkCodec,
    DocumentCodec,
    GlobalRelationCodec,
    LinkedEntityCodec,
    LocalRelationCodec,
    TheoryAtomCodec,
    TheoryRelationCodec,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactProvenance,
    CanonicalizationArtifact,
    ChunkArtifact,
    DocumentArtifact,
    EntityMentionArtifact,
    FusionDecisionArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.runs.fingerprints import stable_fingerprint


def build_document_artifact(document: L1Document, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{document.id}",
        identity_key=f"document::{document.id}",
        kind=ArtifactKind.DOCUMENT,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_path=document.source_path, source_document_id=document.id),
        payload=DocumentCodec.to_payload(document),
        dependency_fingerprint=stable_fingerprint({"document_id": document.id, "source_path": document.source_path}),
    )


def build_chunk_artifact(chunk: L1Chunk, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{chunk.id}",
        identity_key=f"chunk::{chunk.id}",
        kind=ArtifactKind.CHUNK,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_document_id=chunk.source_doc_id, source_chunk_id=chunk.id),
        payload=ChunkCodec.to_payload(chunk),
        dependency_fingerprint=stable_fingerprint({"chunk_id": chunk.id, "document_id": chunk.source_doc_id, "text": chunk.text}),
    )


def build_entity_mention_artifact(entity: L2Entity, chunk_id: str, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    mention_id = f"mention::{entity.id}::{chunk_id}"
    return ArtifactEnvelope(
        artifact_id=f"artifact::{mention_id}",
        identity_key=f"entity_mention::{mention_id}",
        kind=ArtifactKind.ENTITY_MENTION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_chunk_id=chunk_id, upstream_artifact_ids=[f"artifact::{chunk_id}"]),
        payload=EntityMentionArtifact(
            mention_id=mention_id,
            chunk_id=chunk_id,
            surface_form=entity.name,
            entity_type=entity.label,
            entity_id=entity.id,
            textual_envelope=entity.textual_envelope,
            start_char=entity.text_anchor.char_start if entity.text_anchor else None,
            end_char=entity.text_anchor.char_end if entity.text_anchor else None,
            confidence=entity.confidence,
        ),
        dependency_fingerprint=stable_fingerprint({"mention_id": mention_id, "chunk_id": chunk_id}),
    )


def parse_mention_id(mention_id: str) -> tuple[str, str]:
    """Parse a mention ID into its component entity ID and chunk ID."""
    parts = mention_id.split("::")
    if len(parts) == 3 and parts[0] == "mention":
        return parts[1], parts[2]
    # Fallback in case of unexpected format
    return mention_id, ""


def build_linked_entity_artifact(
    entity: L2Entity,
    mention_artifact_ids: list[str],
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
) -> ArtifactEnvelope:
    payload = LinkedEntityCodec.to_payload(entity)
    payload.mention_ids = [artifact_id.removeprefix("artifact::") for artifact_id in mention_artifact_ids]
    resolved_upstream = (
        list(dict.fromkeys(upstream_artifact_ids))
        if upstream_artifact_ids is not None
        else list(mention_artifact_ids)
    )
    return ArtifactEnvelope(
        artifact_id=f"artifact::{entity.id}",
        identity_key=f"linked_entity::{entity.id}",
        kind=ArtifactKind.LINKED_ENTITY,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(
            source_chunk_id=entity.source_chunk_ids[0] if entity.source_chunk_ids else None,
            upstream_artifact_ids=resolved_upstream,
        ),
        payload=payload,
        dependency_fingerprint=stable_fingerprint({"entity_id": entity.id, "canonical_name": entity.name, "entity_type": entity.label}),
    )


def build_local_relation_artifact(triple: L2Triple, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    # A local relation is per-chunk evidence, so the chunk is part of its identity:
    # the same (s, p, o) asserted in two chunks is two pieces of evidence.
    relation_id = f"local-relation::{triple.source_chunk_id}::{triple.subject_id}::{triple.predicate}::{triple.object_id}"
    return ArtifactEnvelope(
        artifact_id=f"artifact::{relation_id}",
        identity_key=f"local_relation::{relation_id}",
        kind=ArtifactKind.LOCAL_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_chunk_id=triple.source_chunk_id, upstream_artifact_ids=[f"artifact::{triple.subject_id}", f"artifact::{triple.object_id}"]),
        payload=LocalRelationArtifact(relation_id=relation_id, subject_entity_id=triple.subject_id, predicate=triple.predicate, object_entity_id=triple.object_id, source_chunk_id=triple.source_chunk_id or "", confidence=triple.confidence),
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "predicate": triple.predicate, "scope": triple.scope}),
    )


def build_global_relation_artifact(triple: L2Triple, relation_dist: dict[str, int], *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    # A global relation spans chunks, so it is identified by the triple alone.
    relation_id = f"global-relation::{triple.subject_id}::{triple.predicate}::{triple.object_id}"
    return ArtifactEnvelope(
        artifact_id=f"artifact::{relation_id}",
        identity_key=f"global_relation::{relation_id}",
        kind=ArtifactKind.GLOBAL_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_chunk_id=triple.source_chunk_id, upstream_artifact_ids=[f"artifact::{triple.subject_id}", f"artifact::{triple.object_id}"]),
        payload=GlobalRelationArtifact(relation_id=relation_id, subject_entity_id=triple.subject_id, predicate=triple.predicate, object_entity_id=triple.object_id, supporting_chunk_ids=[triple.source_chunk_id] if triple.source_chunk_id else [], confidence=triple.confidence, rerank_score=triple.rerank_score),
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "predicate": triple.predicate, "source_chunk_id": triple.source_chunk_id}),
        metadata={"relation_type_distribution": str(relation_dist.get(triple.predicate, 0))},
    )


def build_theory_atom_artifact(component: TheoryAtom, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{component.id}",
        identity_key=f"argument_component::{component.id}",
        kind=ArtifactKind.THEORY_ATOM,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_chunk_id=component.source_chunk_id, upstream_artifact_ids=[f"artifact::{component.source_chunk_id}"]),
        payload=TheoryAtomCodec.to_payload(component),
        dependency_fingerprint=stable_fingerprint({
            "component_id": component.id,
            "component_type": component.component_type,
            "text": component.text,
            "epistemic_status": component.epistemic_status,
            "scope_type": component.scope_type,
        }),
    )


build_argument_component_artifact = build_theory_atom_artifact


def build_theory_relation_artifact(relation: TheoryRelation, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    relation_id = f"argument-relation::{relation.source_id}::{relation.relation_type}::{relation.target_id}"
    return ArtifactEnvelope(
        artifact_id=f"artifact::{relation_id}",
        identity_key=f"argument_relation::{relation_id}",
        kind=ArtifactKind.THEORY_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(upstream_artifact_ids=[f"artifact::{relation.source_id}", f"artifact::{relation.target_id}"]),
        payload=TheoryRelationCodec.to_payload(relation),
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "relation_type": relation.relation_type, "scope": relation.scope}),
    )


build_argument_relation_artifact = build_theory_relation_artifact


def build_canonicalization_artifact(original_id: str, canonical_id: str, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    decision_id = f"canonicalization::{original_id}::{canonical_id}"
    return ArtifactEnvelope(
        artifact_id=f"artifact::{decision_id}",
        identity_key=f"canonicalization::{decision_id}",
        kind=ArtifactKind.CANONICALIZATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(upstream_artifact_ids=[f"artifact::{original_id}", f"artifact::{canonical_id}"]),
        payload=CanonicalizationArtifact(canonical_id=canonical_id, original_artifact_ids=[original_id], canonical_label=canonical_id, canonical_type="entity"),
        dependency_fingerprint=stable_fingerprint({"original_id": original_id, "canonical_id": canonical_id}),
    )


def build_fusion_cluster_artifact(cluster: list[str], theory_fusion_applied: bool, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    # Identity is the membership set, order-independent. A positional index would
    # collide cluster #0 of one run with an unrelated cluster #0 of the next.
    decision_id = f"fusion-cluster::{stable_fingerprint(sorted(cluster))}"
    canonical_id = cluster[0] if cluster else None
    return ArtifactEnvelope(
        artifact_id=f"artifact::{decision_id}",
        identity_key=f"fusion_decision::{decision_id}",
        kind=ArtifactKind.FUSION_DECISION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(upstream_artifact_ids=[f"artifact::{component_id}" for component_id in cluster]),
        payload=FusionDecisionArtifact(
            decision_id=decision_id,
            artifact_ids=cluster,
            decision_type="cluster",
            canonical_artifact_id=canonical_id,
            rationale="semantic argument clustering",
            confidence=None,
        ),
        dependency_fingerprint=stable_fingerprint({"cluster": cluster, "theory_fusion_applied": theory_fusion_applied}),
    )
