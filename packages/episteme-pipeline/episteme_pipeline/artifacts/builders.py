from __future__ import annotations

from episteme_pipeline.artifacts.models import (
    TheoryAtomArtifact,
    TheoryRelationArtifact,
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
)
from episteme_pipeline.contracts.domain import L1Chunk, L1Document, L2Entity, L2Triple, TheoryAtom, TheoryRelation
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
        payload=DocumentArtifact(
            document_id=document.id,
            title=document.title,
            source_path=document.source_path,
            structural_anchor=document.structural_anchor,
            metadata={
                "chapter_count": str(document.chapter_count),
                "chunk_count": str(document.chunk_count),
            },
            ingested_at=document.ingested_at,
        ),
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
        payload=ChunkArtifact(
            chunk_id=chunk.id,
            document_id=chunk.source_doc_id,
            text=chunk.text,
            sequence_index=chunk.sequence_index,
            chapter_id=chunk.chapter_id,
            token_count=chunk.token_count,
        ),
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
        payload=EntityMentionArtifact(mention_id=mention_id, chunk_id=chunk_id, surface_form=entity.name, entity_type=entity.label),
        dependency_fingerprint=stable_fingerprint({"mention_id": mention_id, "chunk_id": chunk_id}),
    )


def parse_mention_id(mention_id: str) -> tuple[str, str]:
    """Parse a mention ID into its component entity ID and chunk ID."""
    parts = mention_id.split("::")
    if len(parts) == 3 and parts[0] == "mention":
        return parts[1], parts[2]
    # Fallback in case of unexpected format
    return mention_id, ""


def build_linked_entity_artifact(entity: L2Entity, mention_artifact_ids: list[str], *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{entity.id}",
        identity_key=f"linked_entity::{entity.id}",
        kind=ArtifactKind.LINKED_ENTITY,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_chunk_id=entity.source_chunk_ids[0] if entity.source_chunk_ids else None, upstream_artifact_ids=mention_artifact_ids),
        payload=LinkedEntityArtifact(
            entity_id=entity.id,
            canonical_name=entity.name,
            entity_type=entity.label,
            mention_ids=[artifact_id.removeprefix("artifact::") for artifact_id in mention_artifact_ids],
            description=entity.description,
            textual_envelope=entity.textual_envelope,
            is_mature=entity.is_mature,
            confidence=entity.confidence,
        ),
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
        payload=LocalRelationArtifact(relation_id=relation_id, subject_entity_id=triple.subject_id, predicate=triple.predicate, object_entity_id=triple.object_id, source_chunk_id=triple.source_chunk_id, confidence=triple.confidence),
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
        payload=GlobalRelationArtifact(relation_id=relation_id, subject_entity_id=triple.subject_id, predicate=triple.predicate, object_entity_id=triple.object_id, supporting_chunk_ids=[triple.source_chunk_id], confidence=triple.confidence, rerank_score=triple.rerank_score),
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "predicate": triple.predicate, "source_chunk_id": triple.source_chunk_id}),
        metadata={"relation_type_distribution": str(relation_dist.get(triple.predicate, 0))},
    )


def build_argument_component_artifact(component: TheoryAtom, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{component.id}",
        identity_key=f"argument_component::{component.id}",
        kind=ArtifactKind.THEORY_ATOM,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(source_chunk_id=component.source_chunk_id, upstream_artifact_ids=[f"artifact::{component.source_chunk_id}"]),
        payload=TheoryAtomArtifact(
            component_id=component.id,
            chunk_id=component.source_chunk_id,
            text=component.text,
            component_type=component.component_type,
            confidence=component.confidence,
            plausibility=component.plausibility,
            epistemic_status=component.epistemic_status,
            scope_type=component.scope_type,
        ),
        dependency_fingerprint=stable_fingerprint({
            "component_id": component.id,
            "component_type": component.component_type,
            "text": component.text,
            "epistemic_status": component.epistemic_status,
            "scope_type": component.scope_type,
        }),
    )


def build_argument_relation_artifact(relation: TheoryRelation, *, run_id: str, phase_name: str, method: str) -> ArtifactEnvelope:
    relation_id = f"argument-relation::{relation.source_id}::{relation.relation_type}::{relation.target_id}"
    return ArtifactEnvelope(
        artifact_id=f"artifact::{relation_id}",
        identity_key=f"argument_relation::{relation_id}",
        kind=ArtifactKind.THEORY_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(upstream_artifact_ids=[f"artifact::{relation.source_id}", f"artifact::{relation.target_id}"]),
        payload=TheoryRelationArtifact(
            relation_id=relation_id,
            source_component_id=relation.source_id,
            target_component_id=relation.target_id,
            relation_type=relation.relation_type,
            scope=relation.scope,
            confidence=relation.confidence,
            weight=relation.weight,
            class_probability=relation.class_probability,
            empirical_accuracy=relation.empirical_accuracy,
            modal_strength=relation.modal_strength,
            effective_weight=relation.effective_weight,
            decision_engine_provider=relation.decision_engine_provider,
            tenability=relation.tenability,
            calibrated_confidence=relation.calibrated_confidence,
            weight_support=relation.weight_support,
            weight_attack=relation.weight_attack,
        ),
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "relation_type": relation.relation_type, "scope": relation.scope}),
    )


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
    return ArtifactEnvelope(
        artifact_id=f"artifact::{decision_id}",
        identity_key=f"fusion_decision::{decision_id}",
        kind=ArtifactKind.FUSION_DECISION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=ArtifactProvenance(upstream_artifact_ids=[f"artifact::{component_id}" for component_id in cluster]),
        payload=FusionDecisionArtifact(decision_id=decision_id, artifact_ids=cluster, decision_type="cluster", rationale="semantic argument clustering", confidence=None),
        dependency_fingerprint=stable_fingerprint({"cluster": cluster, "theory_fusion_applied": theory_fusion_applied}),
    )
