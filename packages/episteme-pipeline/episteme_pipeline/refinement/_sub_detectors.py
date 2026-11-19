"""Focused deficit sub-detectors for closed-loop hermeneutic refinement.

Decomposes epistemic deficit detection into three single-responsibility
components:

- :class:`EnthymemeGapSubDetector`: unwarranted or :math:`Z_1`-disconnected
  theoretical claims participating in argument structure.
- :class:`PolysemyCollisionSubDetector`: bridging entities or argument atoms
  exposing incompatible cluster/stance/conception bridges.
- :class:`UngroundedAxiomSubDetector`: empirical/local tenability failures,
  missing :math:`M_{pp}` observation dimensions, or missing observational base.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from episteme_pipeline.artifacts.execution import EpistemicStateView
from episteme_pipeline.artifacts.models import TheoreticalEnrichmentArtifact
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.refinement._detector_analysis import (
    METADATA_PARAM_KEYS,
    DetectorStateAnalysis,
    collect_target_chunks,
    dedup_relations,
    extract_required_dimensions,
    lookup_edge_tenability,
)
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils.identifiers import dedup_preserve_order


class EnthymemeGapSubDetector:
    """Detect unwarranted or :math:`Z_1`-disconnected theoretical argument components."""

    def detect(
        self,
        analysis: DetectorStateAnalysis,
        *,
        cfg: HermeneuticRefinementConfig,
        phase_label: str,
        refinement_pass: int,
    ) -> list[EpistemicDeficit]:
        """Identify ``ENTHYMEME_GAP`` deficits over theoretical partition-A atoms.

        Purely isolated theoretical postulates with zero incident argument edges
        and zero local empirical partition-B atoms (whose primary deficit is an
        ungrounded empirical base rather than a missing bridging premise) are
        left to :class:`UngroundedAxiomSubDetector` so the two detectors do not
        double-fire on the same isolated atom.

        Parameters
        ----------
        analysis : DetectorStateAnalysis
            Precomputed graph, partition, and enrichment state snapshot.
        cfg : HermeneuticRefinementConfig
            Threshold configuration.
        phase_label : str
            Originating phase label recorded on emitted deficits.
        refinement_pass : int
            Active refinement pass counter.

        Returns
        -------
        list of EpistemicDeficit
            Detected enthymeme gap signals.
        """
        max_pr = max((analysis.pr_scores.get(aid, 0.0) for aid in analysis.a_atoms), default=0.0)
        max_btw = max((analysis.btw_scores.get(aid, 0.0) for aid in analysis.a_atoms), default=0.0)
        core_claims = [
            analysis.atoms_by_id[aid].text
            for aid in sorted(
                analysis.a_atoms,
                key=lambda x: (-analysis.pr_scores.get(x, 0.0), -analysis.btw_scores.get(x, 0.0), x),
            )[:5]
        ]
        macro_dims = sorted(
            {dim for dims in analysis.cluster_dimensions.values() for dim in dims}
        )

        deficits: list[EpistemicDeficit] = []
        for atom in sorted(analysis.atoms, key=lambda a: a.id):
            if atom.id not in analysis.a_atoms or atom.intensional_mode == "suppositional":
                continue

            centrality = float(analysis.pr_scores.get(atom.id, 0.0))
            btw = float(analysis.btw_scores.get(atom.id, 0.0))
            if centrality < cfg.enthymeme_min_centrality:
                continue

            in_sup = analysis.in_support_degree.get(atom.id, 0)
            is_z1 = atom.id in analysis.z1_grounded
            if in_sup > 0 and is_z1:
                continue

            # Disambiguate from UNGROUNDED_AXIOM: isolated theoretical postulates
            # without any edges and without local B-atoms lack empirical base first.
            has_local_b = analysis.cluster_b_counts.get(atom.source_chunk_id, 0) > 0
            degree = analysis.incident_degree.get(atom.id, 0)
            if degree == 0 and not has_local_b:
                continue

            base_sev = (
                0.70 if (in_sup == 0 and not is_z1) else (0.60 if in_sup == 0 else 0.50)
            )
            norm_pr = (centrality / max_pr) if max_pr > 0.0 else 0.0
            norm_btw = (btw / max_btw) if max_btw > 0.0 else 0.0
            severity = min(
                1.0,
                max(0.0, round(base_sev + 0.25 * norm_pr + 0.05 * norm_btw, 4)),
            )

            enrs = analysis.atom_to_enrichments.get(atom.id, [])
            primary_theory_id = enrs[0].theory_id if enrs else None
            if primary_theory_id is None and isinstance(
                atom.parameters.get("theory_id"), str
            ):
                primary_theory_id = str(atom.parameters["theory_id"])

            projected_params: dict[str, Any] = {}
            for enr in enrs:
                projected_params.update(enr.projected_parameters)
            projected_params.update(atom.parameters)

            param_names = sorted(
                k for k in projected_params if k not in METADATA_PARAM_KEYS
            )
            target_chunks = collect_target_chunks(
                [atom.source_chunk_id], analysis.chunk_neighbors
            )
            local_dims = sorted(
                {
                    dim
                    for cid in target_chunks
                    for dim in analysis.cluster_dimensions.get(cid, set())
                }
            )
            required_dims = dedup_preserve_order(
                [
                    *extract_required_dimensions(atom, enrs[0] if enrs else None),
                    *local_dims,
                    *macro_dims,
                ]
            )
            entity_names = [
                analysis.entities_by_id[eid].name
                for eid in atom.entity_ids
                if eid in analysis.entities_by_id
            ]
            theory_lens: dict[str, Any] = {
                "theory_ids": dedup_preserve_order(
                    [e.theory_id for e in enrs if e.theory_id]
                ),
                "parameter_names": param_names,
                "required_dimensions": required_dims,
                "projected_parameters": {
                    k: v
                    for k, v in projected_params.items()
                    if k not in METADATA_PARAM_KEYS
                },
                "core_claims": [c for c in core_claims if c != atom.text],
                "atom_text": atom.text,
                "component_type": atom.component_type,
                "entity_names": entity_names,
            }

            tau_star = (
                float(atom.equilibrium_strength)
                if atom.equilibrium_strength is not None
                else analysis.equilibrium_map.get(atom.id, atom.effective_base_prior())
            )

            if in_sup == 0 and not is_z1:
                gap_reason = (
                    "has zero incoming support edges and no empirical B-base"
                    if not analysis.b_atoms
                    else "has zero incoming support edges and no Z1 path to empirical base B"
                )
            elif in_sup == 0:
                gap_reason = "has zero incoming support edges"
            else:
                gap_reason = "lacks a Z1 grounding path to empirical base B"

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"enthymeme_gap::{atom.id}",
                    deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=list(atom.entity_ids),
                    target_atom_ids=[atom.id],
                    target_relation_ids=[],
                    theory_id=primary_theory_id,
                    theory_lens=theory_lens,
                    rationale=(
                        f"{atom.component_type} '{atom.id}' (centrality={centrality:.4f}) "
                        f"{gap_reason}."
                    ),
                    metrics={
                        "centrality": round(centrality, 6),
                        "betweenness_centrality": round(btw, 6),
                        "in_support_degree": float(in_sup),
                        "tau_star": round(float(tau_star), 6),
                        "z1_grounded": 1.0 if is_z1 else 0.0,
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
        return deficits


class PolysemyCollisionSubDetector:
    """Detect entity or atom polysemy and cross-cluster incompatibility bridges."""

    def __init__(self, schema: SchemaConfig) -> None:
        """Initialize the detector with canonical ``schema`` polarity rules.

        Parameters
        ----------
        schema : SchemaConfig
            Single source of truth for relation polarities.
        """
        self.schema = schema

    def detect(
        self,
        state: EpistemicStateView,
        analysis: DetectorStateAnalysis,
        *,
        cfg: HermeneuticRefinementConfig,
        phase_label: str,
        refinement_pass: int,
        curation_ledger: EpistemicCurationLedger | None,
    ) -> list[EpistemicDeficit]:
        """Identify ``POLYSEMY_COLLISION`` deficits across entity and atom hubs.

        Parameters
        ----------
        state : EpistemicStateView
            Cumulative epistemic state providing entities and triples.
        analysis : DetectorStateAnalysis
            Precomputed state analysis snapshot.
        cfg : HermeneuticRefinementConfig
            Threshold configuration.
        phase_label : str
            Originating phase label.
        refinement_pass : int
            Active refinement pass counter.
        curation_ledger : EpistemicCurationLedger or None
            Active curation constraints preventing redundant re-splitting.

        Returns
        -------
        list of EpistemicDeficit
            Detected polysemy collision signals.
        """
        deficits: list[EpistemicDeficit] = []
        covered_atoms: set[str] = set()
        covered_relations: set[str] = set()

        split_parent_ids: set[str] = {
            e.id.split("__sense_", 1)[0]
            for e in state.entities
            if "__sense_" in e.id
        }
        cannot_link_ids: set[str] = set()
        if curation_ledger is not None:
            for eid_a, eid_b in curation_ledger.cannot_link_entities:
                cannot_link_ids.add(eid_a)
                cannot_link_ids.add(eid_b)

        triples = [*state.local_triples, *state.global_triples]
        triples_by_entity: dict[str, list[L2Triple]] = {}
        for triple in triples:
            triples_by_entity.setdefault(triple.subject_id, []).append(triple)
            if triple.object_id != triple.subject_id:
                triples_by_entity.setdefault(triple.object_id, []).append(triple)

        rels_by_atom: dict[str, list[TheoryRelation]] = {}
        for rel in analysis.relations:
            if not rel.is_admissible or rel.undercuts_relation_id is not None:
                continue
            involved = set(rel.effective_premise_ids)
            if rel.target_id in analysis.atoms_by_id:
                involved.add(rel.target_id)
            for aid in involved:
                if aid in analysis.atoms_by_id:
                    rels_by_atom.setdefault(aid, []).append(rel)

        # 1. Entity-centric polysemy collisions
        for ent in sorted(state.entities, key=lambda e: e.id):
            if ent.id in split_parent_ids:
                continue
            linked_atoms = [a for a in analysis.atoms if ent.id in a.entity_ids]
            if (
                not linked_atoms
                and ent.id not in cannot_link_ids
                and (len(ent.conceptions) >= 2 or (ent.polysemy_variance or 0.0) > 0.0)
                and ent.source_chunk_ids
            ):
                ent_chunks = set(ent.source_chunk_ids)
                linked_atoms = [a for a in analysis.atoms if a.source_chunk_id in ent_chunks]

            linked_ids = {a.id for a in linked_atoms}
            touching_rels = dedup_relations(
                [rel for aid in linked_ids for rel in rels_by_atom.get(aid, [])]
            )
            ent_triples = triples_by_entity.get(ent.id, [])

            incompatible, conflict_reasons, implicated_rels, has_ambiguity = (
                self._assess_incompatibility(
                    atom_ids=linked_ids,
                    touching_rels=touching_rels,
                    entity=ent,
                    ent_triples=ent_triples,
                    analysis=analysis,
                    cfg=cfg,
                )
            )
            if not incompatible:
                continue
            if (
                len(ent.conceptions) < 2
                and len(set(ent.source_chunk_ids)) <= 1
                and implicated_rels
                and all(
                    self._is_relation_disambiguated_by_split(
                        rel, analysis.atoms_by_id, curation_ledger
                    )
                    for rel in implicated_rels
                )
            ):
                continue

            implicated_atom_ids: set[str] = set(linked_ids)
            for rel in implicated_rels:
                for pid in rel.effective_premise_ids:
                    if pid in analysis.atoms_by_id:
                        implicated_atom_ids.add(pid)
                if rel.target_id in analysis.atoms_by_id:
                    implicated_atom_ids.add(rel.target_id)

            max_vol = max(
                (
                    float(analysis.atoms_by_id[aid].controversy_volatility)
                    for aid in implicated_atom_ids
                    if analysis.atoms_by_id[aid].controversy_volatility is not None
                ),
                default=0.0,
            )
            ts_values = [
                ts
                for rel in (implicated_rels or touching_rels)
                if (ts := lookup_edge_tenability(rel, analysis.edge_tenability_map)) is not None
            ]
            min_ts_edge = min(ts_values) if ts_values else 1.0
            polysemy_var = float(ent.polysemy_variance) if ent.polysemy_variance is not None else 0.0

            if not (
                max_vol >= cfg.polysemy_volatility_threshold
                or min_ts_edge < cfg.polysemy_edge_tenability_threshold
            ):
                continue

            severity = self._polysemy_severity(
                max_vol=max_vol,
                min_ts_edge=min_ts_edge,
                polysemy_var=polysemy_var,
                cfg=cfg,
            )
            target_atoms = sorted(implicated_atom_ids)
            target_rels = [r.relation_id for r in implicated_rels]
            seed_chunks = [
                *ent.source_chunk_ids,
                *(analysis.atoms_by_id[aid].source_chunk_id for aid in target_atoms),
            ]
            target_chunks = collect_target_chunks(seed_chunks, analysis.chunk_neighbors)
            enrs = [
                enr
                for aid in target_atoms
                for enr in analysis.atom_to_enrichments.get(aid, [])
            ]
            theory_ids = dedup_preserve_order([e.theory_id for e in enrs if e.theory_id])

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"polysemy_collision::entity::{ent.id}",
                    deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=[ent.id],
                    target_atom_ids=target_atoms,
                    target_relation_ids=target_rels,
                    theory_id=theory_ids[0] if len(theory_ids) == 1 else None,
                    theory_lens={
                        "entity_name": ent.name,
                        "entity_label": ent.label,
                        "conception_perspectives": [c.perspective for c in ent.conceptions],
                        "conflicting_theories": theory_ids,
                        "conflicting_clusters": dedup_preserve_order(
                            [e.cluster_id for e in enrs]
                        ),
                        "conflict_signals": conflict_reasons,
                        "has_conceptual_ambiguity": has_ambiguity,
                    },
                    rationale=(
                        f"Entity '{ent.name}' ({ent.id}) bridges incompatible "
                        f"clusters/stances ({', '.join(conflict_reasons)}) with "
                        f"V={max_vol:.3f}, TS_edge={min_ts_edge:.3f}."
                    ),
                    metrics={
                        "controversy_volatility": round(max_vol, 6),
                        "ts_edge": round(min_ts_edge, 6),
                        "polysemy_variance": round(polysemy_var, 6),
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
            covered_atoms.update(target_atoms)
            covered_relations.update(target_rels)

        # 2. Atom-centric polysemy collisions (uncovered by entity-level)
        for atom in sorted(analysis.atoms, key=lambda a: a.id):
            if atom.id in covered_atoms:
                continue
            touching_rels = dedup_relations(rels_by_atom.get(atom.id, []))
            if not touching_rels:
                continue

            vol = (
                float(atom.controversy_volatility)
                if atom.controversy_volatility is not None
                else 0.0
            )
            ts_values = [
                ts
                for rel in touching_rels
                if (ts := lookup_edge_tenability(rel, analysis.edge_tenability_map)) is not None
            ]
            min_ts_edge = min(ts_values) if ts_values else 1.0
            if not (
                vol >= cfg.polysemy_volatility_threshold
                or min_ts_edge < cfg.polysemy_edge_tenability_threshold
            ):
                continue

            incompatible, conflict_reasons, implicated_rels, has_ambiguity = (
                self._assess_incompatibility(
                    atom_ids={atom.id},
                    touching_rels=touching_rels,
                    entity=None,
                    ent_triples=(),
                    analysis=analysis,
                    cfg=cfg,
                )
            )
            if not incompatible:
                continue
            if implicated_rels and all(
                self._is_relation_disambiguated_by_split(
                    rel, analysis.atoms_by_id, curation_ledger
                )
                for rel in implicated_rels
            ):
                continue

            implicated_rel_ids = [r.relation_id for r in implicated_rels]
            if implicated_rel_ids and all(
                rid in covered_relations for rid in implicated_rel_ids
            ):
                continue

            neighbor_atom_ids: set[str] = {atom.id}
            for rel in implicated_rels:
                for pid in rel.effective_premise_ids:
                    if pid in analysis.atoms_by_id:
                        neighbor_atom_ids.add(pid)
                if rel.target_id in analysis.atoms_by_id:
                    neighbor_atom_ids.add(rel.target_id)

            target_atoms = sorted(neighbor_atom_ids)
            target_entities = dedup_preserve_order(
                [
                    eid
                    for aid in target_atoms
                    for eid in analysis.atoms_by_id[aid].entity_ids
                ]
            )
            target_chunks = collect_target_chunks(
                [analysis.atoms_by_id[aid].source_chunk_id for aid in target_atoms],
                analysis.chunk_neighbors,
            )
            enrs = [
                enr
                for aid in target_atoms
                for enr in analysis.atom_to_enrichments.get(aid, [])
            ]
            theory_ids = dedup_preserve_order([e.theory_id for e in enrs if e.theory_id])

            severity = self._polysemy_severity(
                max_vol=vol,
                min_ts_edge=min_ts_edge,
                polysemy_var=0.0,
                cfg=cfg,
            )
            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"polysemy_collision::atom::{atom.id}",
                    deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=target_entities,
                    target_atom_ids=target_atoms,
                    target_relation_ids=implicated_rel_ids,
                    theory_id=theory_ids[0] if len(theory_ids) == 1 else None,
                    theory_lens={
                        "atom_text": atom.text,
                        "conflicting_theories": theory_ids,
                        "conflicting_clusters": dedup_preserve_order(
                            [e.cluster_id for e in enrs]
                        ),
                        "conflict_signals": conflict_reasons,
                        "has_conceptual_ambiguity": has_ambiguity,
                    },
                    rationale=(
                        f"Atom '{atom.id}' exhibits bridging polysemy/incompatibility "
                        f"({', '.join(conflict_reasons)}) with V={vol:.3f}, TS_edge={min_ts_edge:.3f}."
                    ),
                    metrics={
                        "controversy_volatility": round(vol, 6),
                        "ts_edge": round(min_ts_edge, 6),
                        "polysemy_variance": 0.0,
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
            covered_atoms.update(target_atoms)
            covered_relations.update(implicated_rel_ids)

        return deficits

    @staticmethod
    def _is_relation_disambiguated_by_split(
        rel: TheoryRelation,
        atoms_by_id: dict[str, TheoryAtom],
        curation_ledger: EpistemicCurationLedger | None,
    ) -> bool:
        """Return whether ``rel`` spans distinct split or cannot-link entities."""
        endpoint_ids = [pid for pid in rel.effective_premise_ids if pid in atoms_by_id]
        if rel.target_id in atoms_by_id:
            endpoint_ids.append(rel.target_id)
        if len(endpoint_ids) < 2:
            return False

        entity_sets = [
            set(atoms_by_id[aid].entity_ids)
            for aid in endpoint_ids
            if atoms_by_id[aid].entity_ids
        ]
        if len(entity_sets) < 2:
            return False

        for idx, eids_a in enumerate(entity_sets):
            for eids_b in entity_sets[idx + 1 :]:
                if eids_a & eids_b:
                    continue
                for ea in eids_a:
                    for eb in eids_b:
                        if ea == eb:
                            continue
                        if curation_ledger is not None and curation_ledger.is_cannot_link(ea, eb):
                            return True
                        if (
                            "__sense_" in ea
                            and "__sense_" in eb
                            and ea.split("__sense_", 1)[0] == eb.split("__sense_", 1)[0]
                        ):
                            return True
        return False

    def _assess_incompatibility(
        self,
        *,
        atom_ids: set[str],
        touching_rels: Sequence[TheoryRelation],
        entity: L2Entity | None,
        ent_triples: Sequence[L2Triple],
        analysis: DetectorStateAnalysis,
        cfg: HermeneuticRefinementConfig,
    ) -> tuple[bool, list[str], list[TheoryRelation], bool]:
        """Assess structural incompatibility and explicit ambiguity cues."""
        reasons: list[str] = []
        implicated: list[TheoryRelation] = []
        rel_polarities: set[int] = set()
        has_ambiguity = False

        for rel in touching_rels:
            pol = self.schema.resolve_edge_polarity(
                rel.relation_type,
                weight_support=rel.weight_support,
                weight_attack=rel.weight_attack,
                weight=rel.weight,
            )
            if pol != 0:
                rel_polarities.add(pol)

            endpoints = {
                pid for pid in rel.effective_premise_ids if pid in analysis.atoms_by_id
            }
            if rel.target_id in analysis.atoms_by_id:
                endpoints.add(rel.target_id)

            ts_edge = lookup_edge_tenability(rel, analysis.edge_tenability_map)
            low_ts = (
                ts_edge is not None and ts_edge < cfg.polysemy_edge_tenability_threshold
            )

            ep_clusters = {
                e.cluster_id
                for aid in endpoints
                for e in analysis.atom_to_enrichments.get(aid, [])
            }
            ep_theories = {
                e.theory_id
                for aid in endpoints
                for e in analysis.atom_to_enrichments.get(aid, [])
                if e.theory_id
            }
            ep_comms = {
                analysis.atom_to_community[aid]
                for aid in endpoints
                if aid in analysis.atom_to_community
            }
            ep_perspectives = {
                analysis.atoms_by_id[aid].attributed_to.strip().lower()
                for aid in endpoints
                if analysis.atoms_by_id[aid].attributed_to
            }
            cross_cluster = (
                len(ep_clusters) > 1
                or len(ep_theories) > 1
                or len(ep_comms) > 1
                or len(ep_perspectives) > 1
            )
            if low_ts and cross_cluster:
                reasons.append("low_ts_edge_cross_cluster")
                implicated.append(rel)
                has_ambiguity = True
            elif low_ts and pol < 0:
                reasons.append("low_ts_edge_attack")
                implicated.append(rel)
            elif cross_cluster:
                reasons.append("cross_cluster_bridge")
                implicated.append(rel)
                has_ambiguity = True

        triple_polarities = {
            self.schema.get_relation_polarity(t.predicate) for t in ent_triples
        } - {0}
        combined_polarities = rel_polarities | triple_polarities
        if 1 in combined_polarities and -1 in combined_polarities:
            reasons.append("conflicting_support_attack")
            implicated.extend(
                r
                for r in touching_rels
                if self.schema.resolve_edge_polarity(
                    r.relation_type,
                    weight_support=r.weight_support,
                    weight_attack=r.weight_attack,
                    weight=r.weight,
                )
                != 0
            )
        elif entity is not None and len(atom_ids) >= 2 and -1 in combined_polarities:
            reasons.append("conflicting_internal_attack")
            implicated.extend(
                r
                for r in touching_rels
                if self.schema.resolve_edge_polarity(
                    r.relation_type,
                    weight_support=r.weight_support,
                    weight_attack=r.weight_attack,
                    weight=r.weight,
                )
                < 0
            )

        all_clusters = {
            e.cluster_id
            for aid in atom_ids
            for e in analysis.atom_to_enrichments.get(aid, [])
        }
        all_theories = {
            e.theory_id
            for aid in atom_ids
            for e in analysis.atom_to_enrichments.get(aid, [])
            if e.theory_id
        }
        all_comms = {
            analysis.atom_to_community[aid]
            for aid in atom_ids
            if aid in analysis.atom_to_community
        }
        if len(all_clusters) > 1 or len(all_theories) > 1 or len(all_comms) > 1:
            reasons.append("distinct_clusters")
            has_ambiguity = True

        if entity is not None and (
            len(entity.conceptions) >= 2
            or (entity.polysemy_variance is not None and entity.polysemy_variance > 0.0)
        ):
            reasons.append("conception_stratification")
            has_ambiguity = True

        deduped_reasons = dedup_preserve_order(reasons)
        deduped_rels = dedup_relations(implicated)
        return bool(deduped_reasons), deduped_reasons, deduped_rels, has_ambiguity

    @staticmethod
    def _polysemy_severity(
        *,
        max_vol: float,
        min_ts_edge: float,
        polysemy_var: float,
        cfg: HermeneuticRefinementConfig,
    ) -> float:
        """Compute normalized ``[0.0, 1.0]`` severity for ``POLYSEMY_COLLISION``."""
        vol_part = 0.0
        if max_vol >= cfg.polysemy_volatility_threshold:
            denom = max(1.0 - cfg.polysemy_volatility_threshold, 1e-6)
            excess = max(0.0, max_vol - cfg.polysemy_volatility_threshold) / denom
            vol_part = 0.55 + 0.40 * min(1.0, excess)

        edge_part = 0.0
        if min_ts_edge < cfg.polysemy_edge_tenability_threshold:
            denom = max(cfg.polysemy_edge_tenability_threshold, 1e-6)
            deficit_ratio = (cfg.polysemy_edge_tenability_threshold - min_ts_edge) / denom
            edge_part = 0.55 + 0.40 * min(1.0, max(0.0, deficit_ratio))

        bonus = 0.05 if (vol_part > 0.0 and edge_part > 0.0) or polysemy_var > 0.0 else 0.0
        return min(1.0, round(max(vol_part, edge_part) + bonus, 4))


class UngroundedAxiomSubDetector:
    """Detect empirical tenability failures and observationally ungrounded axioms."""

    def detect(
        self,
        enrichments: Sequence[TheoreticalEnrichmentArtifact],
        analysis: DetectorStateAnalysis,
        *,
        cfg: HermeneuticRefinementConfig,
        phase_label: str,
        refinement_pass: int,
    ) -> list[EpistemicDeficit]:
        """Identify ``UNGROUNDED_AXIOM`` deficits across enrichments and atoms.

        Parameters
        ----------
        enrichments : Sequence of TheoreticalEnrichmentArtifact
            Cluster enrichment artifacts emitted during theoretical enrichment.
        analysis : DetectorStateAnalysis
            Precomputed state analysis snapshot.
        cfg : HermeneuticRefinementConfig
            Threshold configuration.
        phase_label : str
            Originating phase label.
        refinement_pass : int
            Active refinement pass counter.

        Returns
        -------
        list of EpistemicDeficit
            Detected ungrounded axiom deficits.
        """
        deficits: list[EpistemicDeficit] = []
        covered_by_enrichment: set[str] = set()

        # 1. Enrichment-cluster level checks
        for enr in sorted(
            enrichments, key=lambda e: (e.theory_id, e.cluster_id, e.enrichment_id)
        ):
            chunk_hint = enr.cluster_id.removeprefix("cluster-")
            claimant_ids = dedup_preserve_order(enr.claimant_atom_ids)
            if not claimant_ids:
                claimant_ids = [
                    a.id
                    for a in analysis.atoms
                    if a.id in analysis.a_atoms and a.source_chunk_id == chunk_hint
                ]

            claimant_atoms = [
                analysis.atoms_by_id[aid]
                for aid in claimant_ids
                if aid in analysis.atoms_by_id
            ]
            req_dims = dedup_preserve_order(
                [
                    *extract_required_dimensions(None, enr),
                    *(
                        dim
                        for ca in claimant_atoms
                        for dim in extract_required_dimensions(ca, None)
                    ),
                ]
            )
            observed_dims = set(analysis.cluster_dimensions.get(chunk_hint, set()))
            observed_dims.update(analysis.cluster_dimensions.get(enr.cluster_id, set()))
            missing_dims = [d for d in req_dims if d.lower() not in observed_dims]

            low_local = enr.local_tenability < cfg.ungrounded_local_tenability_threshold
            untenable = not enr.is_tenable
            local_anomalies = [
                a for a in enr.anomalies if not a.startswith("Constraint edge ")
            ]
            no_obs_in_cluster = (
                analysis.cluster_b_counts.get(chunk_hint, 0) == 0
                and analysis.cluster_b_counts.get(enr.cluster_id, 0) == 0
                and bool(claimant_ids)
            )
            missing_z1 = bool(claimant_ids) and not any(
                cid in analysis.z1_grounded for cid in claimant_ids
            )
            if not (
                low_local
                or untenable
                or local_anomalies
                or missing_dims
                or (no_obs_in_cluster and missing_z1)
            ):
                continue

            ts_local = float(enr.local_tenability)
            gap = max(0.0, cfg.ungrounded_local_tenability_threshold - ts_local) / max(
                cfg.ungrounded_local_tenability_threshold, 1e-6
            )
            severity = min(
                1.0,
                max(0.55 if not (low_local or untenable) else 0.60, round(0.60 + 0.35 * gap, 4)),
            )

            param_names = sorted(
                k for k in enr.projected_parameters if k not in METADATA_PARAM_KEYS
            )
            min_tau_star = min(
                (
                    enr.equilibrium_strengths.get(
                        ca.id,
                        ca.equilibrium_strength
                        if ca.equilibrium_strength is not None
                        else ca.effective_base_prior(),
                    )
                    for ca in claimant_atoms
                ),
                default=0.0,
            )
            seed_chunks = [
                *(ca.source_chunk_id for ca in claimant_atoms),
                chunk_hint,
            ]
            target_chunks = collect_target_chunks(seed_chunks, analysis.chunk_neighbors)

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"ungrounded_axiom::{enr.theory_id}::{enr.cluster_id}",
                    deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=dedup_preserve_order(
                        [eid for ca in claimant_atoms for eid in ca.entity_ids]
                    ),
                    target_atom_ids=claimant_ids,
                    target_relation_ids=[],
                    theory_id=enr.theory_id or None,
                    theory_lens={
                        "required_dimensions": req_dims,
                        "parameter_names": param_names,
                        "claimant_atom_ids": claimant_ids,
                        "missing_dimensions": missing_dims,
                        "cluster_id": enr.cluster_id,
                        "anomalies": list(enr.anomalies),
                        "projected_parameters": dict(enr.projected_parameters),
                    },
                    rationale=(
                        f"Cluster '{enr.cluster_id}' under theory '{enr.theory_id}' "
                        f"failed empirical grounding (TS_local={enr.local_tenability:.3f}, "
                        f"is_tenable={enr.is_tenable})."
                    ),
                    metrics={
                        "ts_local": round(ts_local, 6),
                        "aggregated_tenability": round(float(enr.aggregated_tenability), 6),
                        "tau_star": round(min_tau_star, 6),
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
            covered_by_enrichment.update(claimant_ids)

        # 2. Atom-level checks (for atoms not covered by failing enrichment)
        for atom in sorted(analysis.atoms, key=lambda a: a.id):
            if atom.id not in analysis.a_atoms or atom.id in covered_by_enrichment:
                continue
            if atom.intensional_mode == "suppositional":
                continue

            ts_local = (
                float(atom.local_tenability)
                if atom.local_tenability is not None
                else (
                    float(atom.tenability.local_score)
                    if atom.tenability is not None
                    else None
                )
            )
            agg_ts = (
                float(atom.tenability.aggregated_score)
                if atom.tenability is not None
                else ts_local
            )
            low_ts = (
                ts_local is not None
                and ts_local < cfg.ungrounded_local_tenability_threshold
            )
            untenable = atom.tenability is not None and not atom.tenability.is_tenable
            no_obs_in_cluster = analysis.cluster_b_counts.get(atom.source_chunk_id, 0) == 0
            # Trigger missing-B-base UNGROUNDED_AXIOM when atom is empirically isolated
            # (0 incident argument edges) or explicitly requires dimensions.
            enrs = analysis.atom_to_enrichments.get(atom.id, [])
            req_dims = extract_required_dimensions(atom, enrs[0] if enrs else None)
            observed_dims = analysis.cluster_dimensions.get(atom.source_chunk_id, set())
            missing_dims = [d for d in req_dims if d.lower() not in observed_dims]

            isolated_no_obs = (
                atom.id not in analysis.z1_grounded
                and no_obs_in_cluster
                and (analysis.incident_degree.get(atom.id, 0) == 0 or bool(req_dims))
            )

            if not (low_ts or untenable or isolated_no_obs or missing_dims):
                continue

            eff_ts_local = float(ts_local) if ts_local is not None else 0.0
            eff_agg = float(agg_ts) if agg_ts is not None else eff_ts_local
            tau_star = (
                float(atom.equilibrium_strength)
                if atom.equilibrium_strength is not None
                else analysis.equilibrium_map.get(atom.id, atom.effective_base_prior())
            )

            if low_ts or untenable:
                gap = max(0.0, cfg.ungrounded_local_tenability_threshold - eff_ts_local) / max(
                    cfg.ungrounded_local_tenability_threshold, 1e-6
                )
                severity = min(1.0, max(0.55, round(0.55 + 0.45 * gap, 4)))
            elif isolated_no_obs:
                prior = atom.modal_prior if atom.modal_prior is not None else 0.6
                severity = min(1.0, round(0.55 + 0.25 * float(prior), 4))
            else:
                severity = 0.65

            theory_id: str | None = enrs[0].theory_id if enrs else None
            if theory_id is None and isinstance(atom.parameters.get("theory_id"), str):
                theory_id = str(atom.parameters["theory_id"])

            param_names = sorted(
                k for k in atom.parameters if k not in METADATA_PARAM_KEYS
            )
            target_chunks = collect_target_chunks(
                [atom.source_chunk_id], analysis.chunk_neighbors
            )

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"ungrounded_axiom::atom::{atom.id}",
                    deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=list(atom.entity_ids),
                    target_atom_ids=[atom.id],
                    target_relation_ids=[],
                    theory_id=theory_id,
                    theory_lens={
                        "required_dimensions": req_dims,
                        "parameter_names": param_names,
                        "claimant_atom_ids": [atom.id],
                        "missing_dimensions": missing_dims,
                        "atom_text": atom.text,
                        "component_type": atom.component_type,
                    },
                    rationale=(
                        f"{atom.component_type} '{atom.id}' lacks empirical grounding "
                        f"(TS_local={eff_ts_local:.3f}, missing_dims={missing_dims}, "
                        f"obs_in_cluster={analysis.cluster_b_counts.get(atom.source_chunk_id, 0)})."
                    ),
                    metrics={
                        "ts_local": round(eff_ts_local, 6),
                        "aggregated_tenability": round(eff_agg, 6),
                        "tau_star": round(float(tau_star), 6),
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
        return deficits
