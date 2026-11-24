"""Hexagonal graph mappers for Stratified Epistemic State Tuple contracts.

Translates canonical Layer 3 domain models (:class:`TheoryAtom` and
:class:`TheoryRelation`) to and from backend property dictionaries so domain
contracts remain decoupled from property-graph serialization details.
"""

from __future__ import annotations

from typing import Any, Literal

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.schema.default_schema import (
    DEFAULT_SCHEMA,
    STRUCTURAL_EDGE_TYPES,
    SchemaConfig,
    StructuralRelationType,
)

_STRUCTURAL_EDGE_TYPES: frozenset[str] = STRUCTURAL_EDGE_TYPES
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
        "intensional_mode": atom.intensional_mode,
    }
    if atom.attributed_to is not None:
        props["attributed_to"] = atom.attributed_to
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
        fallback_pol = (
            1 if (rel.weight or 0) > 0 else (-1 if (rel.weight or 0) < 0 else 0)
        )
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
    if rel.id is not None:
        props["id"] = rel.id
    if rel.premise_ids:
        props["premise_ids"] = list(rel.premise_ids)
    if rel.undercuts_relation_id is not None:
        props["undercuts_relation_id"] = rel.undercuts_relation_id
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


def is_backing_relation_type(relation_type: str | None) -> bool:
    """Return True if ``relation_type`` denotes Toulmin backing or positive support."""
    r_upper = (relation_type or "").strip().upper()
    return r_upper in {"BACKS", "SUPPORTS", "SUPPORTS_ARG", "WARRANTS"}


def theory_inference_node_properties(
    rel: TheoryRelation,
    *,
    schema: SchemaConfig | None = None,
    t_norm: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Serialize a reified :class:`TheoryRelation` into ``:TheoryInference`` node properties.

    Parameters
    ----------
    rel : TheoryRelation
        Reified dialectical inference relation.
    schema : SchemaConfig or None, optional
        Schema configuration for polarity resolution.
    t_norm : str or None, optional
        Conjunctive t-norm operator (``'product'`` or ``'godel'``) used during
        equilibrium evaluation.
    run_id : str or None, optional
        Optional run identifier stamped onto the projected node.

    Returns
    -------
    dict of str to Any
        Graph property dictionary for the ``:TheoryInference`` node.
    """
    props = theory_relation_to_graph_properties(rel, schema=schema)
    props["id"] = rel.relation_id
    props["has_explicit_id"] = rel.id is not None
    if rel.id is not None:
        props["explicit_id"] = rel.id
    props["source_id"] = rel.source_id
    props["relation_type"] = rel.relation_type
    props["target_id"] = rel.target_id
    props["premise_ids"] = list(rel.effective_premise_ids)
    props["has_explicit_premise_ids"] = bool(rel.premise_ids)
    if t_norm is not None:
        props["t_norm"] = t_norm
    if run_id is not None:
        props["run_id"] = run_id
    return props


def build_reified_inference_edges(
    rel: TheoryRelation,
    *,
    is_reified: bool,
    reified_ids: set[str],
    schema: SchemaConfig | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build property-graph edge specs for reified inferences, undercutters, and backings.

    Parameters
    ----------
    rel : TheoryRelation
        Domain relation to translate into hypergraph edges.
    is_reified : bool
        Whether ``rel`` itself has a reified ``:TheoryInference`` node.
    reified_ids : set of str
        Identifiers of all reified ``:TheoryInference`` warrant nodes.
    schema : SchemaConfig or None, optional
        Schema configuration for polarity resolution.
    run_id : str or None, optional
        Optional run identifier stamped on generated edge properties.

    Returns
    -------
    list of dict of str to Any
        Edge dictionaries compatible with ``GraphWriter.upsert_relations``.
    """
    rel_props = theory_relation_to_graph_properties(rel, schema=schema)
    rel_props["relation_type"] = rel.relation_type
    rel_props["target_id"] = rel.target_id
    if run_id is not None:
        rel_props["run_id"] = run_id
    edges: list[dict[str, Any]] = []

    if is_reified:
        w_id = rel.relation_id
        for pid in rel.effective_premise_ids:
            p_props: dict[str, Any] = {"inference_id": w_id}
            if run_id is not None:
                p_props["run_id"] = run_id
            edges.append(
                {
                    "from_id": pid,
                    "relation_type": StructuralRelationType.HAS_PREMISE.value,
                    "to_id": w_id,
                    "properties": p_props,
                }
            )
        target_w = rel.undercuts_relation_id or rel.target_id
        if rel.undercuts_relation_id is not None or (
            rel.relation_type.strip().upper() == "UNDERCUTS" and target_w in reified_ids
        ):
            edges.append(
                {
                    "from_id": w_id,
                    "relation_type": "UNDERCUTS",
                    "to_id": target_w,
                    "properties": {**rel_props, "inference_id": w_id},
                }
            )
        elif target_w in reified_ids and is_backing_relation_type(rel.relation_type):
            edges.append(
                {
                    "from_id": w_id,
                    "relation_type": "BACKS",
                    "to_id": target_w,
                    "properties": {**rel_props, "inference_id": w_id},
                }
            )
        else:
            edges.append(
                {
                    "from_id": w_id,
                    "relation_type": StructuralRelationType.CONCLUDES.value,
                    "to_id": rel.target_id,
                    "properties": {
                        **rel_props,
                        "relation_type": rel.relation_type,
                        "inference_id": w_id,
                    },
                }
            )
        return edges

    target_w = rel.undercuts_relation_id or rel.target_id
    if rel.undercuts_relation_id is not None or (
        rel.relation_type.strip().upper() == "UNDERCUTS" and target_w in reified_ids
    ):
        edges.append(
            {
                "from_id": rel.source_id,
                "relation_type": "UNDERCUTS",
                "to_id": target_w,
                "properties": rel_props,
            }
        )
    elif target_w in reified_ids:
        edge_type = (
            "BACKS"
            if is_backing_relation_type(rel.relation_type)
            else rel.relation_type.strip().upper()
        )
        edges.append(
            {
                "from_id": rel.source_id,
                "relation_type": edge_type,
                "to_id": target_w,
                "properties": rel_props,
            }
        )
    return edges


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
    scope_val: Literal["local", "global"] = (
        "local" if raw_scope == "local" else "global"
    )
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

    resolved_source_id = str(props.get("source_id") or source_id)
    resolved_rel_type = str(props.get("relation_type") or relation_type)
    resolved_target_id = str(props.get("target_id") or target_id)

    if "has_explicit_id" in props:
        resolved_id = (
            (props.get("explicit_id") or props.get("id"))
            if props["has_explicit_id"]
            else None
        )
    else:
        resolved_id = props.get("explicit_id") or props.get("id")

    if "has_explicit_premise_ids" in props:
        resolved_premises = (
            tuple(props.get("premise_ids") or ())
            if props["has_explicit_premise_ids"]
            else ()
        )
    else:
        resolved_premises = tuple(props.get("premise_ids") or ())

    kwargs: dict[str, Any] = {
        "source_id": resolved_source_id,
        "target_id": resolved_target_id,
        "relation_type": resolved_rel_type,
        "confidence": confidence_val,
        "scope": scope_val,
        "id": resolved_id,
        "premise_ids": resolved_premises,
        "undercuts_relation_id": props.get("undercuts_relation_id"),
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
    if relation_type and relation_type in _STRUCTURAL_EDGE_TYPES:
        return False

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
    "build_reified_inference_edges",
    "is_backing_relation_type",
    "is_theory_edge",
    "theory_atom_to_graph_properties",
    "theory_inference_node_properties",
    "theory_relation_from_graph_properties",
    "theory_relation_to_graph_properties",
]
