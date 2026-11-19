"""Refinement delta materialization, split retirement, overlay, and subgraph slicing.

Centralizes artifact envelope construction for closed-loop hermeneutic
refinement (ISSUE-053) so :class:`~episteme_pipeline.refinement.coordinator.ClosedLoopRefinementCoordinator`
stays focused on loop orchestration and convergence policy.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from collections.abc import Sequence

from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_entity_mention_artifact,
    build_epistemic_deficit_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
    parse_mention_id,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactPayload,
    EntityMentionArtifact,
    LinkedEntityArtifact,
)
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    L2Entity,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.utils.identifiers import (
    canonical_relation_key,
    dedup_preserve_order,
)


def float_differs(
    lhs: float | None,
    rhs: float | None,
    *,
    tol: float = 1e-6,
) -> bool:
    """Return True when two optional floats differ beyond ``tol``.

    Parameters
    ----------
    lhs : float or None
        First float value.
    rhs : float or None
        Second float value.
    tol : float, default 1e-6
        Absolute difference tolerance.

    Returns
    -------
    bool
        True if nullity differs or ``|lhs - rhs| > tol``.
    """
    if lhs is None or rhs is None:
        return lhs is not rhs
    return not math.isclose(lhs, rhs, abs_tol=tol, rel_tol=0.0)


def theory_atom_changed(prior: TheoryAtom | None, current: TheoryAtom) -> bool:
    """Return True if a refined or re-projected ``TheoryAtom`` meaningfully changed.

    Parameters
    ----------
    prior : TheoryAtom or None
        Previous version of the atom in the working collection, if any.
    current : TheoryAtom
        Candidate updated atom.

    Returns
    -------
    bool
        True when ``prior`` is absent or persisted domain scores/metadata changed.
    """
    if prior is None:
        return True
    if (
        prior.text != current.text
        or prior.component_type != current.component_type
        or prior.scope_type != current.scope_type
        or prior.epistemic_status != current.epistemic_status
        or prior.intensional_mode != current.intensional_mode
        or prior.entity_ids != current.entity_ids
        or prior.parameters != current.parameters
        or prior.measurements != current.measurements
    ):
        return True
    if (
        float_differs(prior.modal_prior, current.modal_prior)
        or float_differs(prior.equilibrium_strength, current.equilibrium_strength)
        or float_differs(prior.controversy_volatility, current.controversy_volatility)
        or float_differs(prior.confidence, current.confidence)
        or float_differs(prior.local_tenability, current.local_tenability)
    ):
        return True
    if (prior.tenability is None) != (current.tenability is None):
        return True
    if prior.tenability is not None and current.tenability is not None:
        if (
            float_differs(
                prior.tenability.aggregated_score,
                current.tenability.aggregated_score,
            )
            or prior.tenability.is_tenable != current.tenability.is_tenable
        ):
            return True
    return False


def theory_relation_changed(
    prior: TheoryRelation | None,
    current: TheoryRelation,
) -> bool:
    """Return True if a refined or re-projected ``TheoryRelation`` meaningfully changed.

    Parameters
    ----------
    prior : TheoryRelation or None
        Previous relation state, if any.
    current : TheoryRelation
        Candidate updated relation.

    Returns
    -------
    bool
        True when ``prior`` is absent or admissible weights/tenability changed.
    """
    if prior is None:
        return True
    return (
        prior.relation_id != current.relation_id
        or prior.is_admissible != current.is_admissible
        or prior.undercuts_relation_id != current.undercuts_relation_id
        or float_differs(prior.active_weight, current.active_weight)
        or float_differs(prior.effective_weight, current.effective_weight)
        or float_differs(prior.edge_tenability, current.edge_tenability)
        or float_differs(prior.inferential_warrant, current.inferential_warrant)
        or float_differs(prior.confidence, current.confidence)
    )


def resolve_latest_artifact_id(
    collection: ArtifactCollection,
    identity_key: str,
    fallback_raw_id: str,
) -> str:
    """Resolve latest ``artifact_id`` from ``collection`` or synthesize a canonical fallback.

    Parameters
    ----------
    collection : ArtifactCollection
        Active artifact collection.
    identity_key : str
        Canonical ``ArtifactEnvelope.identity_key``.
    fallback_raw_id : str
        Raw domain identifier used if ``identity_key`` is absent.

    Returns
    -------
    str
        Resolved artifact identifier.
    """
    existing = collection.latest_by_identity.get(identity_key)
    if existing is not None:
        return existing.artifact_id
    return f"artifact::{fallback_raw_id}"


def build_deficit_envelope(
    deficit: EpistemicDeficit,
    collection: ArtifactCollection,
    *,
    run_id: str,
    phase_name: str,
    detector_method: str,
    pass_idx: int,
) -> tuple[ArtifactEnvelope[ArtifactPayload], bool]:
    """Build or look up the :class:`EpistemicDeficitArtifact` envelope for ``deficit``.

    Parameters
    ----------
    deficit : EpistemicDeficit
        Detected epistemic deficit signal.
    collection : ArtifactCollection
        Current working collection used to resolve upstream artifact IDs.
    run_id : str
        Active run identifier.
    phase_name : str
        Emitting phase name.
    detector_method : str
        Detector method or class identifier.
    pass_idx : int
        One-based refinement pass executing next (deficit originates at ``pass_idx - 1``).

    Returns
    -------
    tuple of (ArtifactEnvelope, bool)
        Constructed (or existing) envelope and a boolean indicating whether it
        is newly emitted.
    """
    upstream_ids: list[str] = []
    for cid in deficit.target_chunk_ids:
        upstream_ids.append(
            resolve_latest_artifact_id(collection, f"chunk::{cid}", cid)
        )
    for eid in deficit.target_entity_ids:
        upstream_ids.append(
            resolve_latest_artifact_id(collection, f"linked_entity::{eid}", eid)
        )
    for aid in deficit.target_atom_ids:
        upstream_ids.append(
            resolve_latest_artifact_id(collection, f"argument_component::{aid}", aid)
        )
    for rid in deficit.target_relation_ids:
        upstream_ids.append(
            resolve_latest_artifact_id(collection, f"argument_relation::{rid}", rid)
        )

    envelope = build_epistemic_deficit_artifact(
        deficit,
        run_id=run_id,
        phase_name=phase_name,
        method=detector_method,
        upstream_artifact_ids=dedup_preserve_order(upstream_ids),
        refinement_pass=max(0, pass_idx - 1),
    )
    existing = collection.latest_by_identity.get(
        envelope.identity_key or envelope.artifact_id
    )
    if existing is not None and existing.artifact_id == envelope.artifact_id:
        return existing, False
    return envelope, True


def build_delta_envelopes(
    delta: RefinementDelta,
    *,
    deficit: EpistemicDeficit,
    deficit_artifact_id: str,
    collection: ArtifactCollection,
    run_id: str,
    phase_name: str,
    method_name: str,
    pass_idx: int,
) -> list[ArtifactEnvelope[ArtifactPayload]]:
    """Wrap ``RefinementDelta`` updates and entity/mention retirements as envelopes.

    Parameters
    ----------
    delta : RefinementDelta
        Structured delta returned by a refinement handler.
    deficit : EpistemicDeficit
        Deficit addressed by ``delta``.
    deficit_artifact_id : str
        Artifact identifier of the persisted triggering deficit envelope.
    collection : ArtifactCollection
        Working artifact collection before applying ``delta``.
    run_id : str
        Active run identifier.
    phase_name : str
        Emitting phase name.
    method_name : str
        Refinement handler identifier stamped onto emitted provenance.
    pass_idx : int
        Current refinement cycle number (``>= 1``).

    Returns
    -------
    list of ArtifactEnvelope
        Ordered envelopes representing chunks, updated/split/retired mentions
        and entities, triples, theory atoms, and theory relations.
    """
    envelopes: list[ArtifactEnvelope[ArtifactPayload]] = []
    entity_art_ids: dict[str, str] = {}
    atom_art_ids: dict[str, str] = {}
    chunk_art_ids: dict[str, str] = {}
    emitted_mention_keys: set[str] = set()

    for chunk in delta.chunks:
        upstreams = [deficit_artifact_id]
        doc_key = f"document::{chunk.source_doc_id}"
        if doc_key in collection.latest_by_identity:
            upstreams.append(collection.latest_by_identity[doc_key].artifact_id)
        env = build_chunk_artifact(
            chunk,
            run_id=run_id,
            phase_name=phase_name,
            method=method_name,
            upstream_artifact_ids=dedup_preserve_order(upstreams),
            refinement_pass=pass_idx,
            deficit_id=deficit.deficit_id,
        )
        chunk_art_ids[chunk.id] = env.artifact_id
        envelopes.append(env)

    def _chunk_artifact_id(cid: str) -> str | None:
        """Resolve latest chunk artifact ID for ``cid`` if present."""
        if cid in chunk_art_ids:
            return chunk_art_ids[cid]
        chunk_env = collection.latest_by_identity.get(f"chunk::{cid}")
        return chunk_env.artifact_id if chunk_env is not None else None

    for entity in delta.entities:
        mention_art_ids: list[str] = []
        parent_id = delta.split_entity_parents.get(entity.id)
        upstreams = [deficit_artifact_id]

        for cid in entity.source_chunk_ids:
            c_art = _chunk_artifact_id(cid)
            if c_art is not None:
                upstreams.append(c_art)

            # Supersede stale parent mention in reassigned chunk if splitting.
            if parent_id is not None:
                old_m_key = f"entity_mention::mention::{parent_id}::{cid}"
                if (
                    old_m_key in collection.latest_by_identity
                    and old_m_key not in emitted_mention_keys
                ):
                    old_env = collection.latest_by_identity[old_m_key]
                    old_payload = old_env.payload
                    if isinstance(old_payload, EntityMentionArtifact):
                        retired_mention = build_entity_mention_artifact(
                            L2Entity(
                                id=old_payload.entity_id or parent_id,
                                label=old_payload.entity_type,
                                name=old_payload.surface_form,
                                source_chunk_ids=[cid],
                                textual_envelope=old_payload.textual_envelope,
                                confidence=old_payload.confidence,
                            ),
                            cid,
                            run_id=run_id,
                            phase_name=phase_name,
                            method=method_name,
                            upstream_artifact_ids=[deficit_artifact_id],
                            refinement_pass=pass_idx,
                            deficit_id=deficit.deficit_id,
                            is_retired=True,
                        )
                        emitted_mention_keys.add(old_m_key)
                        envelopes.append(retired_mention)

            m_key = f"entity_mention::mention::{entity.id}::{cid}"
            existing_mention = collection.latest_by_identity.get(m_key)
            if (
                existing_mention is None or parent_id is not None
            ) and m_key not in emitted_mention_keys:
                m_ups = [deficit_artifact_id]
                if c_art is not None:
                    m_ups.append(c_art)
                else:
                    m_ups.append(f"artifact::{cid}")
                mention_env = build_entity_mention_artifact(
                    entity,
                    cid,
                    run_id=run_id,
                    phase_name=phase_name,
                    method=method_name,
                    upstream_artifact_ids=m_ups,
                    refinement_pass=pass_idx,
                    deficit_id=deficit.deficit_id,
                )
                emitted_mention_keys.add(m_key)
                envelopes.append(mention_env)
                mention_art_ids.append(mention_env.artifact_id)
            else:
                mention_art_ids.append(
                    existing_mention.artifact_id
                    if existing_mention is not None
                    else f"artifact::mention::{entity.id}::{cid}"
                )

        if parent_id is not None:
            parent_env = collection.latest_by_identity.get(f"linked_entity::{parent_id}")
            if parent_env is not None:
                upstreams.append(parent_env.artifact_id)

        env = build_linked_entity_artifact(
            entity,
            mention_art_ids,
            run_id=run_id,
            phase_name=phase_name,
            method=method_name,
            upstream_artifact_ids=dedup_preserve_order(upstreams),
            refinement_pass=pass_idx,
            deficit_id=deficit.deficit_id,
        )
        entity_art_ids[entity.id] = env.artifact_id
        envelopes.append(env)

    # Retire completely split parent entities and any remaining mentions targeting them.
    retired_set = {eid for eid in delta.retired_entity_ids if eid}
    for retired_id in sorted(retired_set):
        if retired_id in entity_art_ids:
            continue
        prior_ent_env = collection.latest_by_identity.get(f"linked_entity::{retired_id}")
        if prior_ent_env is not None and isinstance(
            prior_ent_env.payload, LinkedEntityArtifact
        ):
            retired_domain = prior_ent_env.payload.to_domain().model_copy(
                update={"source_chunk_ids": []}
            )
            envelopes.append(
                build_linked_entity_artifact(
                    retired_domain,
                    [],
                    run_id=run_id,
                    phase_name=phase_name,
                    method=method_name,
                    upstream_artifact_ids=[deficit_artifact_id],
                    refinement_pass=pass_idx,
                    deficit_id=deficit.deficit_id,
                    is_retired=True,
                )
            )
        for m_env in collection.of_kind(ArtifactKind.ENTITY_MENTION, latest_only=True):
            m_key = m_env.identity_key or m_env.artifact_id
            if m_key in emitted_mention_keys:
                continue
            m_payload = m_env.payload
            if not isinstance(m_payload, EntityMentionArtifact) or m_payload.is_retired:
                continue
            raw_eid, parsed_cid = parse_mention_id(m_payload.mention_id)
            eid = m_payload.entity_id or raw_eid
            cid = m_payload.chunk_id or parsed_cid
            if eid == retired_id and cid:
                retired_m = build_entity_mention_artifact(
                    L2Entity(
                        id=eid,
                        label=m_payload.entity_type,
                        name=m_payload.surface_form,
                        source_chunk_ids=[cid],
                        textual_envelope=m_payload.textual_envelope,
                        confidence=m_payload.confidence,
                    ),
                    cid,
                    run_id=run_id,
                    phase_name=phase_name,
                    method=method_name,
                    upstream_artifact_ids=[deficit_artifact_id],
                    refinement_pass=pass_idx,
                    deficit_id=deficit.deficit_id,
                    is_retired=True,
                )
                emitted_mention_keys.add(m_key)
                envelopes.append(retired_m)

    def _entity_up(eid: str) -> str:
        """Resolve latest linked-entity artifact ID for ``eid``."""
        if eid in entity_art_ids:
            return entity_art_ids[eid]
        return resolve_latest_artifact_id(collection, f"linked_entity::{eid}", eid)

    for triple in delta.local_triples:
        upstreams = [
            deficit_artifact_id,
            _entity_up(triple.subject_id),
            _entity_up(triple.object_id),
        ]
        if triple.source_chunk_id:
            c_art = _chunk_artifact_id(triple.source_chunk_id)
            if c_art is not None:
                upstreams.append(c_art)
        envelopes.append(
            build_local_relation_artifact(
                triple,
                run_id=run_id,
                phase_name=phase_name,
                method=method_name,
                upstream_artifact_ids=dedup_preserve_order(upstreams),
                refinement_pass=pass_idx,
                deficit_id=deficit.deficit_id,
            )
        )

    if delta.global_triples:
        rel_dist = dict(Counter(t.predicate for t in delta.global_triples))
        for triple in delta.global_triples:
            upstreams = [
                deficit_artifact_id,
                _entity_up(triple.subject_id),
                _entity_up(triple.object_id),
            ]
            envelopes.append(
                build_global_relation_artifact(
                    triple,
                    rel_dist,
                    run_id=run_id,
                    phase_name=phase_name,
                    method=method_name,
                    upstream_artifact_ids=dedup_preserve_order(upstreams),
                    refinement_pass=pass_idx,
                    deficit_id=deficit.deficit_id,
                )
            )

    for atom in delta.theory_atoms:
        upstreams = [deficit_artifact_id]
        if atom.source_chunk_id:
            c_art = _chunk_artifact_id(atom.source_chunk_id)
            if c_art is not None:
                upstreams.append(c_art)
        for eid in atom.entity_ids:
            upstreams.append(_entity_up(eid))
        env = build_theory_atom_artifact(
            atom,
            run_id=run_id,
            phase_name=phase_name,
            method=method_name,
            upstream_artifact_ids=dedup_preserve_order(upstreams),
            refinement_pass=pass_idx,
            deficit_id=deficit.deficit_id,
        )
        atom_art_ids[atom.id] = env.artifact_id
        envelopes.append(env)

    def _atom_up(aid: str) -> str:
        """Resolve latest argument-component artifact ID for ``aid``."""
        if aid in atom_art_ids:
            return atom_art_ids[aid]
        return resolve_latest_artifact_id(collection, f"argument_component::{aid}", aid)

    for rel in delta.theory_relations:
        upstreams = [deficit_artifact_id]
        for pid in rel.effective_premise_ids:
            upstreams.append(_atom_up(pid))
        target_ref = rel.undercuts_relation_id or rel.target_id
        if rel.undercuts_relation_id is not None:
            upstreams.append(
                resolve_latest_artifact_id(
                    collection, f"argument_relation::{target_ref}", target_ref
                )
            )
        else:
            upstreams.append(_atom_up(target_ref))
        envelopes.append(
            build_theory_relation_artifact(
                rel,
                run_id=run_id,
                phase_name=phase_name,
                method=method_name,
                upstream_artifact_ids=dedup_preserve_order(upstreams),
                refinement_pass=pass_idx,
                deficit_id=deficit.deficit_id,
            )
        )

    return envelopes


def merge_pass_envelopes(
    pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]],
    new_envelopes: Sequence[ArtifactEnvelope[ArtifactPayload]],
) -> None:
    """Insert or update envelopes generated within the active refinement pass.

    Parameters
    ----------
    pass_envelopes_by_id : dict of str to ArtifactEnvelope
        Pass accumulator keyed by ``artifact_id``.
    new_envelopes : Sequence of ArtifactEnvelope
        Newly constructed envelopes to upsert.
    """
    for env in new_envelopes:
        pass_envelopes_by_id[env.artifact_id] = env


def overlay_collection(
    base_collection: ArtifactCollection,
    pass_envelopes_by_id: dict[str, ArtifactEnvelope[ArtifactPayload]],
) -> ArtifactCollection:
    """Overlay pass envelopes onto ``base_collection`` while preserving full history.

    Parameters
    ----------
    base_collection : ArtifactCollection
        Starting artifact collection.
    pass_envelopes_by_id : dict of str to ArtifactEnvelope
        New or updated envelopes keyed by ``artifact_id``.

    Returns
    -------
    ArtifactCollection
        New immutable collection containing merged history and latest identity index.
    """
    if not pass_envelopes_by_id:
        return base_collection
    merged_history = list(base_collection.history)
    index_by_artifact_id = {
        env.artifact_id: idx for idx, env in enumerate(merged_history)
    }
    for env in pass_envelopes_by_id.values():
        existing_idx = index_by_artifact_id.get(env.artifact_id)
        if existing_idx is not None:
            merged_history[existing_idx] = env
        else:
            index_by_artifact_id[env.artifact_id] = len(merged_history)
            merged_history.append(env)
    return ArtifactCollection(merged_history)


def slice_phase4_component_view(
    view: Phase4ArtifactsView,
    seed_atom_ids: set[str],
) -> Phase4ArtifactsView:
    """Slice ``view`` to the weakly connected TheoryNet component(s) containing ``seed_atom_ids``.

    Ensures D-QBAF gradual equilibrium projection computes exact fixed-point
    plausibilities on affected dialectical components without re-evaluating
    disconnected corpus subgraphs.

    Parameters
    ----------
    view : Phase4ArtifactsView
        Full cumulative Phase 4 artifact view.
    seed_atom_ids : set of str
        Modified or newly introduced atom identifiers defining the refinement locus.

    Returns
    -------
    Phase4ArtifactsView
        Scoped Phase 4 view containing only atoms and relations in connected
        component(s) reachable from ``seed_atom_ids``.
    """
    source_atoms = (
        view.canonical_theory_atoms if view.canonical_theory_atoms else view.theory_atoms
    )
    source_rels = (
        view.canonical_theory_relations
        if view.canonical_theory_relations
        else view.theory_relations
    )
    if not seed_atom_ids or not source_atoms:
        return Phase4ArtifactsView(
            documents=view.documents,
            chunks=view.chunks,
            entities=view.entities,
            local_triples=view.local_triples,
            entity_count_by_type=view.entity_count_by_type,
            global_triples=view.global_triples,
            relation_type_distribution=view.relation_type_distribution,
            theory_atoms=[],
            theory_relations=[],
            fusion_decisions=view.fusion_decisions,
            canonical_theory_atoms=[],
            canonical_theory_relations=[],
            entity_envelopes_by_id=view.entity_envelopes_by_id,
            entity_mentions_by_id=view.entity_mentions_by_id,
            theoretical_enrichments=view.theoretical_enrichments,
            consumed_artifact_ids=view.consumed_artifact_ids,
        )

    adj: dict[str, set[str]] = {}
    rels_by_id: dict[str, TheoryRelation] = {
        r.relation_id: r for r in source_rels if r.relation_id
    }
    undercut_links: dict[str, list[TheoryRelation]] = {}

    for rel in source_rels:
        endpoints = [*rel.effective_premise_ids, rel.target_id]
        for u in endpoints:
            adj.setdefault(u, set()).update(v for v in endpoints if v != u)
        if rel.undercuts_relation_id:
            undercut_links.setdefault(rel.undercuts_relation_id, []).append(rel)

    # Couple undercutting premises/targets with the target relation's endpoints.
    for target_rel_id, cutters in undercut_links.items():
        target_rel = rels_by_id.get(target_rel_id)
        if target_rel is None:
            continue
        target_nodes = {*target_rel.effective_premise_ids, target_rel.target_id}
        for cutter in cutters:
            cutter_nodes = {*cutter.effective_premise_ids, cutter.target_id}
            for cn in cutter_nodes:
                adj.setdefault(cn, set()).update(target_nodes)
            for tn in target_nodes:
                adj.setdefault(tn, set()).update(cutter_nodes)

    component_atoms: set[str] = {aid for aid in seed_atom_ids if aid}
    queue: deque[str] = deque(sorted(component_atoms))
    while queue:
        curr = queue.popleft()
        for nbr in sorted(adj.get(curr, ())):
            if nbr not in component_atoms:
                component_atoms.add(nbr)
                queue.append(nbr)

    scoped_atoms = [a for a in source_atoms if a.id in component_atoms]
    scoped_rels = [
        r
        for r in source_rels
        if ({*r.effective_premise_ids, r.target_id} & component_atoms)
        or (
            r.undercuts_relation_id is not None
            and r.undercuts_relation_id in rels_by_id
            and (
                {*rels_by_id[r.undercuts_relation_id].effective_premise_ids,
                 rels_by_id[r.undercuts_relation_id].target_id}
                & component_atoms
            )
        )
    ]

    return Phase4ArtifactsView(
        documents=view.documents,
        chunks=view.chunks,
        entities=view.entities,
        local_triples=view.local_triples,
        entity_count_by_type=view.entity_count_by_type,
        global_triples=view.global_triples,
        relation_type_distribution=view.relation_type_distribution,
        theory_atoms=scoped_atoms,
        theory_relations=scoped_rels,
        fusion_decisions=view.fusion_decisions,
        canonical_theory_atoms=scoped_atoms,
        canonical_theory_relations=scoped_rels,
        entity_envelopes_by_id=view.entity_envelopes_by_id,
        entity_mentions_by_id=view.entity_mentions_by_id,
        theoretical_enrichments=view.theoretical_enrichments,
        consumed_artifact_ids=view.consumed_artifact_ids,
    )


__all__ = [
    "build_deficit_envelope",
    "build_delta_envelopes",
    "canonical_relation_key",
    "float_differs",
    "merge_pass_envelopes",
    "overlay_collection",
    "resolve_latest_artifact_id",
    "slice_phase4_component_view",
    "theory_atom_changed",
    "theory_relation_changed",
]
