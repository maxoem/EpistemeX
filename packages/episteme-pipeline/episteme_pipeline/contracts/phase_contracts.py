from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Sequence

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from episteme_pipeline.runs.models import RunManifest, RunReport
    from episteme_pipeline.schema.default_schema import SchemaConfig

from episteme_pipeline.contracts.domain import (
    CandidatePair,
    GlobalStructuralAnchor,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    PhaseItemRecord,
    SearchResult,
    SubGraph,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)


class RelationOverride(BaseModel):
    """
    Human-in-the-loop relation or polarity curation override.

    Attributes
    ----------
    source_id : str
        Subject or source atom/entity identifier.
    target_id : str
        Object or target atom/entity identifier.
    relation_type : str
        Curated relation type or decision, e.g. 'SUPPORTS', 'ATTACKS', or 'REJECTED'.
    polarity : str | None, optional
        Optional explicit polarity ('+' / '-' or 'SUPPORTS' / 'ATTACKS'), by default None.
    confidence : float, optional
        Axiomatic human confidence score in [0.0, 1.0], by default 1.0.
    """

    source_id: str
    target_id: str
    relation_type: str
    polarity: str | None = None
    confidence: float = 1.0

    def _resolve_schema(self, schema: SchemaConfig | None) -> SchemaConfig:
        """Return ``schema`` when provided or fall back to ``DEFAULT_SCHEMA``."""
        if schema is not None:
            return schema
        from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

        return DEFAULT_SCHEMA

    def resolved_polarity_sign(
        self, schema: SchemaConfig | None = None
    ) -> int | None:
        """Parse optional ``polarity`` override via the configured ``SchemaConfig``.

        Parameters
        ----------
        schema : SchemaConfig or None, optional
            Schema defining valid relation polarities (defaults to ``DEFAULT_SCHEMA``).

        Returns
        -------
        int or None
            ``1`` for positive support, ``-1`` for negative attack, ``0`` for
            neutral, or ``None`` when ``polarity`` is unset or blank.
        """
        return self._resolve_schema(schema).parse_polarity_override(self.polarity)

    def resolved_relation_type(
        self,
        schema: SchemaConfig | None = None,
        *,
        layer: Literal["l2", "l3"] = "l3",
    ) -> str:
        """Resolve effective relation label via the configured ``SchemaConfig``.

        Parameters
        ----------
        schema : SchemaConfig or None, optional
            Schema defining L2/L3 relation types and polarities (defaults to ``DEFAULT_SCHEMA``).
        layer : {"l2", "l3"}, default "l3"
            Target graph layer used when resolving a fallback relation label.

        Returns
        -------
        str
            Effective relation predicate or dialectical relation type.
        """
        rel_type, _ = self._resolve_schema(schema).resolve_relation_override(
            self.relation_type, self.polarity, layer=layer
        )
        return rel_type


class EpistemicCurationLedger(BaseModel):
    """
    Persistent Human-in-the-Loop (HITL) curation and constraint ledger.

    Carries expert adjudications across runs to prevent machine errors from recurring
    during incremental corpus evolution.

    Attributes
    ----------
    must_link_entities : set[tuple[str, str]]
        Pairs of entity identifiers (or names) that MUST be linked or merged.
    cannot_link_entities : set[tuple[str, str]]
        Pairs of entity identifiers (or names) that CANNOT be linked or merged.
    relation_overrides : dict[str, RelationOverride]
        Overridden relation or polarity decisions, keyed by pair key (e.g., 'source::target').
    modality_overrides : dict[str, float]
        Locked human-adjudicated modal strength priors tau_0(a) for TheoryAtoms,
        keyed by atom identifier.
    """

    must_link_entities: set[tuple[str, str]] = Field(default_factory=set)
    cannot_link_entities: set[tuple[str, str]] = Field(default_factory=set)
    relation_overrides: dict[str, RelationOverride] = Field(default_factory=dict)
    modality_overrides: dict[str, float] = Field(default_factory=dict)

    def is_must_link(
        self,
        id_a: str,
        id_b: str,
        name_a: str | None = None,
        name_b: str | None = None,
    ) -> bool:
        """
        Check if two entities have an axiomatic must-link constraint.

        Parameters
        ----------
        id_a : str
            Identifier of entity A.
        id_b : str
            Identifier of entity B.
        name_a : str | None, optional
            Optional name or surface form of entity A, by default None.
        name_b : str | None, optional
            Optional name or surface form of entity B, by default None.

        Returns
        -------
        bool
            True if the entities must be linked or merged.
        """
        candidates = {(id_a, id_b), (id_b, id_a)}
        if name_a and name_b:
            candidates.update({(name_a, name_b), (name_b, name_a)})
        return bool(candidates & self.must_link_entities)

    def is_cannot_link(
        self,
        id_a: str,
        id_b: str,
        name_a: str | None = None,
        name_b: str | None = None,
    ) -> bool:
        """
        Check if two entities have an axiomatic cannot-link constraint.

        Parameters
        ----------
        id_a : str
            Identifier of entity A.
        id_b : str
            Identifier of entity B.
        name_a : str | None, optional
            Optional name or surface form of entity A, by default None.
        name_b : str | None, optional
            Optional name or surface form of entity B, by default None.

        Returns
        -------
        bool
            True if the entities cannot be linked or merged.
        """
        candidates = {(id_a, id_b), (id_b, id_a)}
        if name_a and name_b:
            candidates.update({(name_a, name_b), (name_b, name_a)})
        return bool(candidates & self.cannot_link_entities)

    def get_relation_override(
        self, source_id: str, target_id: str
    ) -> RelationOverride | None:
        """
        Retrieve any relation override specified for a directed pair.

        Parameters
        ----------
        source_id : str
            Identifier of source node or entity.
        target_id : str
            Identifier of target node or entity.

        Returns
        -------
        RelationOverride | None
            Matching override record, or None if no override is defined.
        """
        for key in (
            f"{source_id}::{target_id}",
            f"{source_id}:{target_id}",
        ):
            if key in self.relation_overrides:
                return self.relation_overrides[key]
        for key in (
            f"{target_id}::{source_id}",
            f"{target_id}:{source_id}",
        ):
            if key in self.relation_overrides:
                candidate = self.relation_overrides[key]
                if candidate.relation_type == "REJECTED" or (
                    candidate.source_id == source_id
                    and candidate.target_id == target_id
                ):
                    return candidate
        for candidate in self.relation_overrides.values():
            if candidate.source_id == source_id and candidate.target_id == target_id:
                return candidate
        return None

    def get_modality_override(self, atom_id: str) -> float | None:
        """
        Retrieve any locked modal certainty override for a TheoryAtom.

        Parameters
        ----------
        atom_id : str
            Identifier of target TheoryAtom.

        Returns
        -------
        float | None
            Locked modal strength prior tau_0(a), or None if not overridden.
        """
        return self.modality_overrides.get(atom_id)

    @staticmethod
    def _polarity_weight_kwargs(
        pol_sign: int | None, confidence: float
    ) -> dict[str, float]:
        """Build directional support/attack weights from an explicit polarity sign."""
        if pol_sign is None:
            return {}
        if pol_sign > 0:
            return {"weight_support": abs(confidence), "weight_attack": 0.0}
        if pol_sign < 0:
            return {"weight_support": 0.0, "weight_attack": abs(confidence)}
        return {"weight_support": 0.0, "weight_attack": 0.0}

    def apply_to_triples(
        self,
        triples: Sequence[L2Triple],
        valid_entity_ids: set[str] | None = None,
        scope: Literal["local", "global"] = "global",
        schema: SchemaConfig | None = None,
    ) -> list[L2Triple]:
        """
        Filter rejected triples, apply predicate/confidence overrides, and inject curated edges.

        Parameters
        ----------
        triples : Sequence[L2Triple]
            Input stream of triples.
        valid_entity_ids : set[str] | None, optional
            Set of valid entity identifiers for injected triples. If provided, injected triples
            must connect nodes within this set, by default None.
        scope : {"local", "global"}, default "global"
            Scope assigned to newly injected triples, by default "global".
        schema : SchemaConfig | None, optional
            Schema configuration governing L2 relation types and polarities, by default None.

        Returns
        -------
        list[L2Triple]
            Filtered, overridden, and injected triples.
        """
        if not self.relation_overrides:
            return list(triples)

        filtered: list[L2Triple] = []
        handled_pairs: set[tuple[str, str]] = set()

        for t in triples:
            pair = (t.subject_id, t.object_id)
            override = self.get_relation_override(t.subject_id, t.object_id)
            if override is not None:
                effective_predicate = override.resolved_relation_type(
                    schema=schema, layer="l2"
                )
                if effective_predicate == "REJECTED" or pair in handled_pairs:
                    continue
                updated = t.model_copy(
                    update={"predicate": effective_predicate, "confidence": override.confidence}
                )
                filtered.append(updated)
                handled_pairs.add(pair)
            else:
                filtered.append(t)

        existing_pairs = {(t.subject_id, t.object_id) for t in filtered}
        for override in self.relation_overrides.values():
            pair = (override.source_id, override.target_id)
            effective_predicate = override.resolved_relation_type(
                schema=schema, layer="l2"
            )
            if (
                effective_predicate != "REJECTED"
                and pair not in existing_pairs
                and (
                    valid_entity_ids is None
                    or (override.source_id in valid_entity_ids and override.target_id in valid_entity_ids)
                )
            ):
                filtered.append(
                    L2Triple(
                        subject_id=override.source_id,
                        predicate=effective_predicate,
                        object_id=override.target_id,
                        confidence=override.confidence,
                        scope=scope,
                    )
                )
                existing_pairs.add(pair)

        return filtered

    def apply_to_theory_relations(
        self,
        relations: Sequence[TheoryRelation],
        valid_atom_ids: set[str] | None = None,
        scope: Literal["local", "global"] = "local",
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]:
        """
        Filter rejected relations, apply type and confidence overrides, and inject curated edges.

        Parameters
        ----------
        relations : Sequence[TheoryRelation]
            Input sequence of theory relations.
        valid_atom_ids : set[str] | None, optional
            Set of valid atom identifiers for injected relations. If provided, injected relations
            must connect atoms within this set, by default None.
        scope : {"local", "global"}, default "local"
            Scope assigned to newly injected theory relations, by default "local".
        schema : SchemaConfig | None, optional
            Schema configuration governing L3 relation types and polarities, by default None.

        Returns
        -------
        list[TheoryRelation]
            Filtered, overridden, and injected theory relations.
        """
        if not self.relation_overrides:
            return list(relations)

        filtered: list[TheoryRelation] = []
        handled_pairs: set[tuple[str, str]] = set()

        for rel in relations:
            pair = (rel.source_id, rel.target_id)
            override = self.get_relation_override(rel.source_id, rel.target_id)
            if override is not None:
                effective_rel_type = override.resolved_relation_type(
                    schema=schema, layer="l3"
                )
                if effective_rel_type == "REJECTED" or pair in handled_pairs:
                    continue
                pol_sign = override.resolved_polarity_sign(schema=schema)
                # Fresh initialization triggers @model_validator(mode="after")
                # to recompute effective_weight, active_weight, and clear stale polarity caches.
                # Only preserve inferential_warrant if explicitly set and neither relation_type nor polarity changed,
                # so downstream TheoryNetProjector can derive the warrant for a changed relation_type.
                extra_kwargs: dict[str, Any] = self._polarity_weight_kwargs(
                    pol_sign, override.confidence
                )
                if (
                    "inferential_warrant" in rel.model_fields_set
                    and effective_rel_type == rel.relation_type
                    and pol_sign is None
                ):
                    extra_kwargs["inferential_warrant"] = rel.inferential_warrant
                updated = TheoryRelation(
                    id=rel.id,
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    premise_ids=rel.premise_ids,
                    undercuts_relation_id=rel.undercuts_relation_id,
                    relation_type=effective_rel_type,
                    confidence=override.confidence,
                    scope=rel.scope,
                    weight=override.confidence,
                    effective_weight=override.confidence,
                    active_weight=abs(override.confidence),
                    calibrated_confidence=override.confidence,
                    edge_tenability=rel.edge_tenability,
                    perception_empirical_acc=rel.perception_empirical_acc,
                    decision_engine_provider=rel.decision_engine_provider,
                    **extra_kwargs,
                )
                filtered.append(updated)
                handled_pairs.add(pair)
            else:
                filtered.append(rel)

        existing_pairs = {(r.source_id, r.target_id) for r in filtered}
        for override in self.relation_overrides.values():
            pair = (override.source_id, override.target_id)
            effective_rel_type = override.resolved_relation_type(
                schema=schema, layer="l3"
            )
            if (
                effective_rel_type != "REJECTED"
                and pair not in existing_pairs
                and (
                    valid_atom_ids is None
                    or (override.source_id in valid_atom_ids and override.target_id in valid_atom_ids)
                )
            ):
                pol_sign = override.resolved_polarity_sign(schema=schema)
                extra_inj = self._polarity_weight_kwargs(pol_sign, override.confidence)
                injected = TheoryRelation(
                    source_id=override.source_id,
                    target_id=override.target_id,
                    relation_type=effective_rel_type,
                    confidence=override.confidence,
                    scope=scope,
                    weight=override.confidence,
                    effective_weight=override.confidence,
                    active_weight=abs(override.confidence),
                    calibrated_confidence=override.confidence,
                    **extra_inj,
                )
                filtered.append(injected)
                existing_pairs.add(pair)

        return filtered

    @classmethod
    def load_from_path(cls, path: str | Path) -> EpistemicCurationLedger:
        """
        Load an EpistemicCurationLedger from a JSON file.

        Parameters
        ----------
        path : str | Path
            Filesystem path to JSON ledger file.

        Returns
        -------
        EpistemicCurationLedger
            Deserialized ledger instance.
        """
        p = Path(path)
        content = p.read_text(encoding="utf-8")
        return cls.model_validate_json(content)


class PipelineInput(BaseModel):
    """
    Entry point for the full pipeline.

    Parameters
    ----------
    source_paths : list[str]
        File paths to the source documents to ingest and process.
    bib_paths : list[str | Path], optional
        Optional file paths to bibliography references (.bib), by default empty list.
    metadata : dict[str, str], optional
        Arbitrary execution metadata strings, by default empty dict.
    structural_anchor : GlobalStructuralAnchor | None, optional
        Global structural anchor coordinate system (ToC outline, document summary, and/or
        global thesis) for the target document or pipeline run, by default None.
    curation_ledger : EpistemicCurationLedger | None, optional
        Persistent Human-in-the-Loop constraint ledger, by default None.
    curation_ledger_path : str | Path | None, optional
        File path to load an EpistemicCurationLedger from disk, by default None.
    """

    source_paths: list[str]
    bib_paths: list[str | Path] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    structural_anchor: GlobalStructuralAnchor | None = None
    curation_ledger: EpistemicCurationLedger | None = None
    curation_ledger_path: str | Path | None = None

    def resolved_curation_ledger(self) -> EpistemicCurationLedger | None:
        """
        Resolve the active EpistemicCurationLedger instance.

        Returns
        -------
        EpistemicCurationLedger | None
            Ledger passed directly or loaded from curation_ledger_path.
        """
        if self.curation_ledger is not None:
            return self.curation_ledger
        if self.curation_ledger_path is not None:
            p = Path(self.curation_ledger_path)
            if p.exists():
                return EpistemicCurationLedger.load_from_path(p)
        return None


class Phase1Output(BaseModel):
    documents: list[L1Document] = Field(default_factory=list)
    chunks: list[L1Chunk] = Field(default_factory=list)


class Phase2Output(BaseModel):
    entities: list[L2Entity] = Field(default_factory=list)
    local_triples: list[L2Triple] = Field(default_factory=list)


class Phase3Output(BaseModel):
    global_triples: list[L2Triple] = Field(default_factory=list)


class Phase4Output(BaseModel):
    theory_atoms: list[TheoryAtom] = Field(default_factory=list)
    theory_relations: list[TheoryRelation] = Field(default_factory=list)
    argument_relations: list[TheoryRelation] | None = None
    theory_net: TheoryNet | None = None
    qbaf: Any = None

    def model_post_init(self, context: Any, /) -> None:
        if self.argument_relations and not self.theory_relations:
            object.__setattr__(self, "theory_relations", self.argument_relations)
        elif self.theory_relations and not self.argument_relations:
            object.__setattr__(self, "argument_relations", self.theory_relations)


class Phase5Output(BaseModel):
    pass


class PipelineResult(BaseModel):
    """Result envelope for running (part of) the pipeline."""

    # Use explicit models to ensure required fields (e.g., run_id) exist.
    manifest: RunManifest | None = None
    artifacts: list[object] = Field(default_factory=list)
    report: RunReport | None = None


__all__ = [
    "CandidatePair",
    "EpistemicCurationLedger",
    "GlobalStructuralAnchor",
    "L1Chunk",
    "L1Document",
    "L2Entity",
    "L2Triple",
    "Phase1Output",
    "Phase2Output",
    "Phase3Output",
    "Phase4Output",
    "Phase5Output",
    "PhaseItemRecord",
    "PipelineInput",
    "PipelineResult",
    "RelationOverride",
    "SearchResult",
    "SubGraph",
    "TheoryAtom",
    "TheoryNet",
    "TheoryRelation",
]
