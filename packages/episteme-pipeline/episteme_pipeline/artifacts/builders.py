from __future__ import annotations

import re

from episteme_pipeline.artifacts.codecs import (
    ChunkCodec,
    DocumentCodec,
    EpistemicDeficitCodec,
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
    EntityMentionArtifact,
    FusionDecisionArtifact,
    GlobalRelationArtifact,
    LocalRelationArtifact,
    MentionId,
)
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.runs.fingerprints import stable_fingerprint


def _scoped_artifact_id(
    base_id: str,
    refinement_pass: int = 0,
    *,
    phase_tag: str | None = None,
) -> str:
    """Build a phase- and pass-scoped artifact identifier preserving history on disk.

    Parameters
    ----------
    base_id : str
        Canonical domain or identity key segment.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index (``0`` for initial forward pass).
    phase_tag : str or None, optional
        Optional semantic producer phase tag (e.g. ``"phase4_maturation"``,
        ``"phase6"``, ``"theoretical_enrichment"``) disambiguating forward-pass
        updates on disk without altering semantic ``identity_key``.

    Returns
    -------
    str
        Deterministic artifact identifier string.
    """
    parts = ["artifact", base_id]
    if phase_tag is not None:
        cleaned_tag = re.sub(r"[^a-zA-Z0-9._-]+", "_", phase_tag.strip()).strip("_")
        if cleaned_tag:
            parts.append(cleaned_tag)
    if refinement_pass > 0:
        parts.append(f"pass{refinement_pass}")
    return "::".join(parts)


def _build_provenance(
    *,
    source_path: str | None = None,
    source_document_id: str | None = None,
    source_chunk_id: str | None = None,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactProvenance:
    """Construct an :class:`ArtifactProvenance` with optional refinement lineage.

    Parameters
    ----------
    source_path : str or None, optional
        Source document path, by default None.
    source_document_id : str or None, optional
        Source document identifier, by default None.
    source_chunk_id : str or None, optional
        Source chunk identifier, by default None.
    upstream_artifact_ids : list of str or None, optional
        Upstream artifact IDs consumed to build this artifact.
    refinement_pass : int, default 0
        Hermeneutic refinement pass index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if produced during refinement.

    Returns
    -------
    ArtifactProvenance
        Populated provenance metadata model.
    """
    return ArtifactProvenance(
        source_path=source_path,
        source_document_id=source_document_id,
        source_chunk_id=source_chunk_id,
        upstream_artifact_ids=list(dict.fromkeys(upstream_artifact_ids or [])),
        refinement_pass=refinement_pass,
        deficit_id=deficit_id,
    )


def build_document_artifact(
    document: L1Document,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`DocumentArtifact`.

    Parameters
    ----------
    document : L1Document
        Source document domain contract.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.

    Returns
    -------
    ArtifactEnvelope
        Constructed document artifact envelope.
    """
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(document.id, refinement_pass),
        identity_key=f"document::{document.id}",
        kind=ArtifactKind.DOCUMENT,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_path=document.source_path,
            source_document_id=document.id,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=DocumentCodec.to_payload(document),
        dependency_fingerprint=stable_fingerprint({"document_id": document.id, "source_path": document.source_path}),
    )


def build_chunk_artifact(
    chunk: L1Chunk,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`ChunkArtifact`.

    Parameters
    ----------
    chunk : L1Chunk
        Source chunk domain contract.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs for provenance lineage.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.

    Returns
    -------
    ArtifactEnvelope
        Constructed chunk artifact envelope.
    """
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(chunk.id, refinement_pass),
        identity_key=f"chunk::{chunk.id}",
        kind=ArtifactKind.CHUNK,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_document_id=chunk.source_doc_id,
            source_chunk_id=chunk.id,
            upstream_artifact_ids=upstream_artifact_ids,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=ChunkCodec.to_payload(chunk),
        dependency_fingerprint=stable_fingerprint({"chunk_id": chunk.id, "document_id": chunk.source_doc_id, "text": chunk.text}),
    )


def build_entity_mention_artifact(
    entity: L2Entity,
    chunk_id: str,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
    is_retired: bool = False,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping an :class:`EntityMentionArtifact`.

    Parameters
    ----------
    entity : L2Entity
        Extracted entity mention contract.
    chunk_id : str
        Originating chunk identifier.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs for provenance lineage.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.
    is_retired : bool, default False
        When True, marks a superseded mention after entity splitting.

    Returns
    -------
    ArtifactEnvelope
        Constructed entity mention artifact envelope.
    """
    mention_id = MentionId.format(entity.id, chunk_id)
    resolved_upstream = (
        list(dict.fromkeys(upstream_artifact_ids))
        if upstream_artifact_ids is not None
        else [f"artifact::{chunk_id}"]
    )
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(mention_id, refinement_pass),
        identity_key=f"entity_mention::{mention_id}",
        kind=ArtifactKind.ENTITY_MENTION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_chunk_id=chunk_id,
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
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
            is_retired=is_retired,
        ),
        dependency_fingerprint=stable_fingerprint(
            {"mention_id": mention_id, "chunk_id": chunk_id, "is_retired": is_retired}
        ),
    )


def parse_mention_id(mention_id: str) -> tuple[str, str]:
    """Parse a mention ID into its component entity ID and chunk ID."""
    entity_id, chunk_id = MentionId.parse(mention_id)
    return entity_id, chunk_id or ""


def build_linked_entity_artifact(
    entity: L2Entity,
    mention_artifact_ids: list[str],
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
    is_retired: bool = False,
    phase_tag: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`LinkedEntityArtifact`.

    Parameters
    ----------
    entity : L2Entity
        Linked entity domain contract.
    mention_artifact_ids : list of str
        Associated entity mention artifact identifiers.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs for provenance lineage.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.
    is_retired : bool, default False
        When True, marks a superseded entity after full concept splitting.
    phase_tag : str or None, optional
        Optional semantic producer phase tag disambiguating forward updates.

    Returns
    -------
    ArtifactEnvelope
        Constructed linked entity artifact envelope.
    """
    payload = LinkedEntityCodec.to_payload(entity)
    payload.mention_ids = [artifact_id.removeprefix("artifact::") for artifact_id in mention_artifact_ids]
    payload.is_retired = is_retired
    artifact_id = _scoped_artifact_id(
        entity.id, refinement_pass, phase_tag=phase_tag
    )
    resolved_upstream = (
        list(dict.fromkeys(upstream_artifact_ids))
        if upstream_artifact_ids is not None
        else list(mention_artifact_ids)
    )
    resolved_upstream = [uid for uid in resolved_upstream if uid != artifact_id]
    return ArtifactEnvelope(
        artifact_id=artifact_id,
        identity_key=f"linked_entity::{entity.id}",
        kind=ArtifactKind.LINKED_ENTITY,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_chunk_id=entity.source_chunk_ids[0] if entity.source_chunk_ids else None,
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=payload,
        dependency_fingerprint=stable_fingerprint(
            {
                "entity_id": entity.id,
                "canonical_name": entity.name,
                "entity_type": entity.label,
                "is_retired": is_retired,
            }
        ),
    )


def build_local_relation_artifact(
    triple: L2Triple,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`LocalRelationArtifact`.

    Parameters
    ----------
    triple : L2Triple
        Local relation triple domain contract.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs overriding endpoint entity references.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.

    Returns
    -------
    ArtifactEnvelope
        Constructed local relation artifact envelope.
    """
    # A local relation is per-chunk evidence, so the chunk is part of its identity:
    # the same (s, p, o) asserted in two chunks is two pieces of evidence.
    payload = LocalRelationCodec.to_payload(triple)
    relation_id = payload.relation_id
    resolved_upstream = (
        upstream_artifact_ids
        if upstream_artifact_ids is not None
        else [f"artifact::{triple.subject_id}", f"artifact::{triple.object_id}"]
    )
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(relation_id, refinement_pass),
        identity_key=f"local_relation::{relation_id}",
        kind=ArtifactKind.LOCAL_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_chunk_id=triple.source_chunk_id,
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=payload,
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "predicate": triple.predicate, "scope": triple.scope}),
    )


def build_global_relation_artifact(
    triple: L2Triple,
    relation_dist: dict[str, int],
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`GlobalRelationArtifact`.

    Parameters
    ----------
    triple : L2Triple
        Global relation triple domain contract.
    relation_dist : dict of str to int
        Frequency distribution over relation predicates.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs overriding endpoint entity references.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.

    Returns
    -------
    ArtifactEnvelope
        Constructed global relation artifact envelope.
    """
    # A global relation spans chunks, so it is identified by the triple alone.
    relation_id = f"global-relation::{triple.subject_id}::{triple.predicate}::{triple.object_id}"
    resolved_upstream = (
        upstream_artifact_ids
        if upstream_artifact_ids is not None
        else [f"artifact::{triple.subject_id}", f"artifact::{triple.object_id}"]
    )
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(relation_id, refinement_pass),
        identity_key=f"global_relation::{relation_id}",
        kind=ArtifactKind.GLOBAL_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_chunk_id=triple.source_chunk_id,
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=GlobalRelationArtifact(relation_id=relation_id, subject_entity_id=triple.subject_id, predicate=triple.predicate, object_entity_id=triple.object_id, supporting_chunk_ids=[triple.source_chunk_id] if triple.source_chunk_id else [], confidence=triple.confidence, rerank_score=triple.rerank_score),
        dependency_fingerprint=stable_fingerprint({"relation_id": relation_id, "predicate": triple.predicate, "source_chunk_id": triple.source_chunk_id}),
        metadata={"relation_type_distribution": str(relation_dist.get(triple.predicate, 0))},
    )


def build_theory_atom_artifact(
    component: TheoryAtom,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
    phase_tag: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`TheoryAtomArtifact`.

    Parameters
    ----------
    component : TheoryAtom
        Theory atom domain contract.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs overriding source chunk reference.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.
    phase_tag : str or None, optional
        Optional semantic producer phase tag disambiguating forward updates.

    Returns
    -------
    ArtifactEnvelope
        Constructed theory atom artifact envelope.
    """
    artifact_id = _scoped_artifact_id(
        component.id, refinement_pass, phase_tag=phase_tag
    )
    resolved_upstream = (
        upstream_artifact_ids
        if upstream_artifact_ids is not None
        else [f"artifact::{component.source_chunk_id}"]
    )
    resolved_upstream = [uid for uid in resolved_upstream if uid != artifact_id]
    return ArtifactEnvelope(
        artifact_id=artifact_id,
        identity_key=f"argument_component::{component.id}",
        kind=ArtifactKind.THEORY_ATOM,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_chunk_id=component.source_chunk_id,
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=TheoryAtomCodec.to_payload(component),
        dependency_fingerprint=stable_fingerprint({
            "component_id": component.id,
            "component_type": component.component_type,
            "text": component.text,
            "epistemic_status": component.epistemic_status,
            "scope_type": component.scope_type,
            "intensional_mode": component.intensional_mode,
            "attributed_to": component.attributed_to,
        }),
    )


build_argument_component_artifact = build_theory_atom_artifact


def build_theory_relation_artifact(
    relation: TheoryRelation,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
    phase_tag: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`TheoryRelationArtifact`.

    Parameters
    ----------
    relation : TheoryRelation
        Theory relation domain contract.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs overriding endpoint atom references.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.
    phase_tag : str or None, optional
        Optional semantic producer phase tag disambiguating forward updates.

    Returns
    -------
    ArtifactEnvelope
        Constructed theory relation artifact envelope.
    """
    relation_id = relation.relation_id
    artifact_id = _scoped_artifact_id(
        relation_id, refinement_pass, phase_tag=phase_tag
    )
    default_upstream = [f"artifact::{pid}" for pid in relation.effective_premise_ids]
    target_ref = relation.undercuts_relation_id or relation.target_id
    default_upstream.append(f"artifact::{target_ref}")
    resolved_upstream = (
        upstream_artifact_ids if upstream_artifact_ids is not None else default_upstream
    )
    resolved_upstream = [uid for uid in resolved_upstream if uid != artifact_id]
    return ArtifactEnvelope(
        artifact_id=artifact_id,
        identity_key=f"argument_relation::{relation_id}",
        kind=ArtifactKind.THEORY_RELATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=TheoryRelationCodec.to_payload(relation),
        dependency_fingerprint=stable_fingerprint({
            "relation_id": relation_id,
            "relation_type": relation.relation_type,
            "scope": relation.scope,
            "premise_ids": list(relation.effective_premise_ids),
            "undercuts_relation_id": relation.undercuts_relation_id,
        }),
    )


build_argument_relation_artifact = build_theory_relation_artifact


def build_canonicalization_artifact(
    original_id: str,
    canonical_id: str,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`CanonicalizationArtifact`.

    Parameters
    ----------
    original_id : str
        Alias entity identifier mapped to ``canonical_id``.
    canonical_id : str
        Target canonical entity identifier.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.

    Returns
    -------
    ArtifactEnvelope
        Constructed canonicalization artifact envelope.
    """
    decision_id = f"canonicalization::{original_id}::{canonical_id}"
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(decision_id, refinement_pass),
        identity_key=f"canonicalization::{decision_id}",
        kind=ArtifactKind.CANONICALIZATION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            upstream_artifact_ids=[f"artifact::{original_id}", f"artifact::{canonical_id}"],
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
        payload=CanonicalizationArtifact(canonical_id=canonical_id, original_artifact_ids=[original_id], canonical_label=canonical_id, canonical_type="entity"),
        dependency_fingerprint=stable_fingerprint({"original_id": original_id, "canonical_id": canonical_id}),
    )


def build_fusion_cluster_artifact(
    cluster: list[str],
    theory_fusion_applied: bool,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    refinement_pass: int = 0,
    deficit_id: str | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping a :class:`FusionDecisionArtifact`.

    Parameters
    ----------
    cluster : list of str
        Member component identifiers in the equivalence cluster.
    theory_fusion_applied : bool
        Whether calibrated theory fusion gating was applied.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the emitting phase.
    method : str
        Method or strategy identifier.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration index.
    deficit_id : str or None, optional
        Triggering epistemic deficit identifier, if any.

    Returns
    -------
    ArtifactEnvelope
        Constructed fusion decision artifact envelope.
    """
    # Identity is the membership set, order-independent. A positional index would
    # collide cluster #0 of one run with an unrelated cluster #0 of the next.
    decision_id = f"fusion-cluster::{stable_fingerprint(sorted(cluster))}"
    canonical_id = cluster[0] if cluster else None
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(decision_id, refinement_pass),
        identity_key=f"fusion_decision::{decision_id}",
        kind=ArtifactKind.FUSION_DECISION,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            upstream_artifact_ids=[f"artifact::{component_id}" for component_id in cluster],
            refinement_pass=refinement_pass,
            deficit_id=deficit_id,
        ),
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


def build_epistemic_deficit_artifact(
    deficit: EpistemicDeficit,
    *,
    run_id: str,
    phase_name: str,
    method: str,
    upstream_artifact_ids: list[str] | None = None,
    refinement_pass: int | None = None,
) -> ArtifactEnvelope:
    """Build an :class:`ArtifactEnvelope` wrapping an :class:`EpistemicDeficitArtifact`.

    Parameters
    ----------
    deficit : EpistemicDeficit
        Detected top-down epistemic deficit domain contract.
    run_id : str
        Active run identifier.
    phase_name : str
        Name of the detecting or coordinating phase.
    method : str
        Detector or strategy identifier.
    upstream_artifact_ids : list of str or None, optional
        Explicit upstream artifact IDs; if omitted, derived deterministically
        from ``deficit.target_chunk_ids``, ``target_entity_ids``,
        ``target_atom_ids``, and ``target_relation_ids``.
    refinement_pass : int or None, optional
        Optional refinement pass override stamped onto both provenance and payload.
        Defaults to ``deficit.refinement_pass``.

    Returns
    -------
    ArtifactEnvelope
        Constructed epistemic deficit artifact envelope.
    """
    effective_pass = (
        deficit.refinement_pass if refinement_pass is None else refinement_pass
    )
    payload = EpistemicDeficitCodec.to_payload(deficit)
    if payload.refinement_pass != effective_pass:
        payload = payload.model_copy(update={"refinement_pass": effective_pass})

    default_upstream = [
        f"artifact::{target_id}"
        for target_id in (
            *deficit.target_chunk_ids,
            *deficit.target_entity_ids,
            *deficit.target_atom_ids,
            *deficit.target_relation_ids,
        )
    ]
    resolved_upstream = (
        upstream_artifact_ids if upstream_artifact_ids is not None else default_upstream
    )
    identity_key = f"epistemic_deficit::{deficit.deficit_id}"
    return ArtifactEnvelope(
        artifact_id=_scoped_artifact_id(identity_key, effective_pass),
        identity_key=identity_key,
        kind=ArtifactKind.EPISTEMIC_DEFICIT,
        run_id=run_id,
        phase_name=phase_name,
        method=method,
        provenance=_build_provenance(
            source_chunk_id=(
                deficit.target_chunk_ids[0] if deficit.target_chunk_ids else None
            ),
            upstream_artifact_ids=resolved_upstream,
            refinement_pass=effective_pass,
            deficit_id=deficit.deficit_id,
        ),
        payload=payload,
        dependency_fingerprint=stable_fingerprint(
            {
                "deficit_id": deficit.deficit_id,
                "deficit_kind": deficit.deficit_kind.value,
                "target_chunk_ids": deficit.target_chunk_ids,
                "target_entity_ids": deficit.target_entity_ids,
                "target_atom_ids": deficit.target_atom_ids,
                "target_relation_ids": deficit.target_relation_ids,
                "theory_id": deficit.theory_id,
                "refinement_pass": effective_pass,
            }
        ),
    )
