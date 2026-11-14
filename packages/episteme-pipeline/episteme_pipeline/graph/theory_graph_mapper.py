"""Hexagonal graph mappers for Stratified Epistemic State Tuple contracts.

Translates canonical Layer 3 domain models (:class:`TheoryAtom` and
:class:`TheoryRelation`) to and from backend property dictionaries so domain
contracts remain decoupled from property-graph serialization details.
"""

from __future__ import annotations

from typing import Any, Literal

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

_STRUCTURAL_EDGE_TYPES: frozenset[str] = frozenset(
    {"CONTAINS", "EXTRACTED_FROM", "SAME_AS", "MENTIONS"}
)
_THEORY_PROPERTY_MARKERS: frozenset[str] = frozenset(
    {
        "inferential_warrant",
        "calibrated_confidence",
        "effective_weight",
        "active_weight",
        "is_admissible",
        "polarity",
        "weight_support",
        "weight_attack",
    }
)


def theory_atom_to_graph_properties(atom: TheoryAtom) -> dict[str, Any]:
    """Serialize a :class:`TheoryAtom` into a canonical graph property map.

    Parameters
    ----------
    atom : TheoryAtom
        Domain theory atom instance.

    Returns
    -------
    dict of str to Any
        Flat property dictionary using canonical Stratified Epistemic State
        Tuple field names. Empty collections and unset optional attributes are
        omitted so Cypher ``SET n += comp.props`` neither triggers ``Map{}``
        errors nor clobbers existing enriched attributes.
    """
    props: dict[str, Any] = {
        "id": atom.id,
        "text": atom.text,
        "component_type": atom.component_type,
        "source_chunk_id": atom.source_chunk_id,
        "modal_prior": atom.modal_prior,
    }
    if atom.local_tenability is not None:
        props["local_tenability"] = atom.local_tenability
    if atom.equilibrium_strength is not None:
        props["equilibrium_strength"] = atom.equilibrium_strength
    if atom.controversy_volatility is not None:
        props["controversy_volatility"] = atom.controversy_volatility
    if atom.confidence is not None:
        props["confidence"] = atom.confidence
    if atom.scope_type is not None:
        props["scope_type"] = atom.scope_type
    if atom.epistemic_status is not None:
        props["epistemic_status"] = atom.epistemic_status
    if atom.resolver_type is not None:
        props["resolver_type"] = atom.resolver_type
    if atom.syntax_bounds is not None:
        props["syntax_bounds"] = list(atom.syntax_bounds)
    if atom.text_anchor is not None:
        props["text_anchor"] = atom.text_anchor.model_dump()
    if atom.entity_ids:
        props["entity_ids"] = list(atom.entity_ids)
    if atom.parameters:
        props["parameters"] = dict(atom.parameters)
    if atom.measurements:
        props["measurements"] = [m.model_dump() for m in atom.measurements]
    if atom.tenability is not None:
        props["tenability"] = atom.tenability.model_dump()
    return props


def theory_relation_to_graph_properties(
    rel: TheoryRelation,
    polarity: int | None = None,
    schema: SchemaConfig | None = None,
) -> dict[str, Any]:
    """Serialize a :class:`TheoryRelation` into a canonical graph edge property map.

    Parameters
    ----------
    rel : TheoryRelation
        Domain theory relation instance.
    polarity : int or None, optional
        Explicit epistemic polarity (``+1``, ``-1``, or ``0``). When ``None``,
        derived from ``schema`` (or ``DEFAULT_SCHEMA``), falling back to the
        sign of ``rel.weight``.
    schema : SchemaConfig or None, optional
        Schema configuration providing relation polarity mappings.

    Returns
    -------
    dict of str to Any
        Edge property dictionary using canonical field names and decoupled
        directional weights.
    """
    effective_schema = schema or DEFAULT_SCHEMA
    eff_w = (
        rel.effective_weight
        if rel.effective_weight is not None
        else (rel.weight if rel.weight is not None else 1.0)
    )
    if polarity is not None:
        resolved_polarity = polarity
    elif rel.weight_support is not None and rel.weight_support > 0:
        resolved_polarity = 1
    elif rel.weight_attack is not None and rel.weight_attack > 0:
        resolved_polarity = -1
    else:
        fallback_pol = 1 if (rel.weight or 0) > 0 else (-1 if (rel.weight or 0) < 0 else 0)
        resolved_polarity = effective_schema.relation_polarities.get(
            rel.relation_type, fallback_pol
        )

    w_supp = (
        rel.weight_support
        if rel.weight_support is not None
        else (eff_w if resolved_polarity > 0 else 0.0)
    )
    w_att = (
        rel.weight_attack
        if rel.weight_attack is not None
        else (eff_w if resolved_polarity < 0 else 0.0)
    )
    cal_conf = (
        rel.calibrated_confidence
        if rel.calibrated_confidence is not None
        else (
            rel.perception_empirical_acc
            if rel.perception_empirical_acc is not None
            else rel.confidence
        )
    )

    props: dict[str, Any] = {
        "inferential_warrant": rel.inferential_warrant,
        "active_weight": rel.active_weight,
        "is_admissible": rel.is_admissible,
        "polarity": resolved_polarity,
        "confidence": rel.confidence,
        "scope": rel.scope,
        "weight": rel.weight if rel.weight is not None else eff_w,
        "effective_weight": eff_w,
        "weight_support": w_supp,
        "weight_attack": w_att,
    }
    if rel.perception_stance_prob is not None:
        props["perception_stance_prob"] = rel.perception_stance_prob
    if rel.perception_empirical_acc is not None:
        props["perception_empirical_acc"] = rel.perception_empirical_acc
    if cal_conf is not None:
        props["calibrated_confidence"] = cal_conf
    if rel.decision_engine_provider is not None:
        props["decision_engine_provider"] = rel.decision_engine_provider
    if rel.edge_tenability is not None:
        props["edge_tenability"] = rel.edge_tenability
    if rel.structural_correspondence is not None:
        props["structural_correspondence"] = rel.structural_correspondence
    return props


def theory_relation_from_graph_properties(
    source_id: str,
    relation_type: str,
    target_id: str,
    properties: dict[str, Any] | None = None,
) -> TheoryRelation:
    """Reconstruct a :class:`TheoryRelation` from serialized graph properties.

    Parameters
    ----------
    source_id : str
        Source atom/component identifier.
    relation_type : str
        Canonical relation type identifier.
    target_id : str
        Target atom/component identifier.
    properties : dict of str to Any or None, optional
        Serialized graph edge property map.

    Returns
    -------
    TheoryRelation
        Validated domain relation instance.
    """
    props = properties or {}
    raw_scope = props.get("scope", "global")
    scope_val: Literal["local", "global"] = "local" if raw_scope == "local" else "global"
    weight_val = (
        float(props["weight"])
        if "weight" in props and props["weight"] is not None
        else None
    )
    eff_weight_val = (
        float(props["effective_weight"])
        if "effective_weight" in props and props["effective_weight"] is not None
        else None
    )
    confidence_raw = props.get("confidence")
    confidence_val = float(confidence_raw if confidence_raw is not None else 1.0)

    kwargs: dict[str, Any] = {
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
        "confidence": confidence_val,
        "scope": scope_val,
        "weight": weight_val,
        "edge_tenability": props.get("edge_tenability"),
        "structural_correspondence": props.get("structural_correspondence"),
        "perception_stance_prob": props.get("perception_stance_prob"),
        "perception_empirical_acc": props.get("perception_empirical_acc"),
        "is_admissible": bool(props.get("is_admissible", True)),
        "effective_weight": eff_weight_val,
        "decision_engine_provider": props.get("decision_engine_provider"),
        "calibrated_confidence": props.get("calibrated_confidence"),
        "weight_support": props.get("weight_support"),
        "weight_attack": props.get("weight_attack"),
    }
    if "inferential_warrant" in props and props["inferential_warrant"] is not None:
        kwargs["inferential_warrant"] = float(props["inferential_warrant"])
    if "active_weight" in props and props["active_weight"] is not None:
        kwargs["active_weight"] = float(props["active_weight"])

    return TheoryRelation(**kwargs)


def is_theory_edge(
    relation_type: str | None = None,
    properties: dict[str, Any] | None = None,
    schema: SchemaConfig | None = None,
    source_is_atom: bool = False,
    target_is_atom: bool = False,
) -> bool:
    """Determine whether candidate graph edge attributes define a :class:`TheoryRelation`.

    Parameters
    ----------
    relation_type : str or None, optional
        Relationship type name.
    properties : dict of str to Any or None, optional
        Edge properties dictionary.
    schema : SchemaConfig or None, optional
        Schema configuration providing dialectical relation definitions.
    source_is_atom : bool, default False
        Whether the source node is known to be a ``TheoryAtom``.
    target_is_atom : bool, default False
        Whether the target node is known to be a ``TheoryAtom``.

    Returns
    -------
    bool
        ``True`` if the edge represents a dialectical ``TheoryRelation``.
    """
    if source_is_atom and target_is_atom:
        return True

    effective_schema = schema or DEFAULT_SCHEMA
    if relation_type and (
        effective_schema.is_dialectical_relation(relation_type)
        or relation_type in effective_schema.argument_relation_types
    ):
        return True

    props = properties or {}
    if any(marker in props for marker in _THEORY_PROPERTY_MARKERS):
        return True

    return bool(
        (source_is_atom or target_is_atom)
        and relation_type is not None
        and relation_type not in _STRUCTURAL_EDGE_TYPES
    )


__all__ = [
    "is_theory_edge",
    "theory_atom_to_graph_properties",
    "theory_relation_from_graph_properties",
    "theory_relation_to_graph_properties",
]
