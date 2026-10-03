"""Schema adapter mapping pipeline SchemaConfig to studio domain conventions."""

from __future__ import annotations

from typing import Any, Literal
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig


class SchemaMapper:
    """Resolves ontology metadata, polarity, and partitions against a SchemaConfig.

    Parameters
    ----------
    schema : SchemaConfig or None, optional
        The active schema configuration. If None, DEFAULT_SCHEMA is used.
    predicate_aliases : dict of str to Any or None, optional
        Custom mappings/aliases for open-vocabulary predicates (e.g. {"WIDERSPRICHT": {"polarity": -1}}).
    """

    def __init__(
        self,
        schema: SchemaConfig | None = None,
        predicate_aliases: dict[str, Any] | None = None,
    ) -> None:
        self.schema: SchemaConfig = schema or DEFAULT_SCHEMA
        self.predicate_aliases: dict[str, Any] = predicate_aliases or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the schema to a dictionary for API delivery.

        Returns
        -------
        dict of str to Any
            Full schema representation including definitions, polarities, and partitions.
        """
        payload = self.schema.model_dump()
        if self.predicate_aliases:
            payload["predicate_aliases"] = self.predicate_aliases

        payload["property_definitions"] = {
            "empirical_accuracy": {
                "type": "float",
                "label": "Empirical Accuracy P(correct)",
                "description": "Calibrated extraction accuracy frequency from System 1 decision engine",
                "domain": [0.0, 1.0],
            },
            "modal_strength": {
                "type": "float",
                "label": "Modal Strength M(φ)",
                "description": "Authorial propositional modal certainty (necessity □ vs possibility ◊)",
                "domain": [0.0, 1.0],
            },
            "inferential_force": {
                "type": "float",
                "label": "Inferential Warrant Force I_(j->i)",
                "description": "Toulminian conditional warrant validity across dialectical schemes",
                "domain": [0.0, 1.0],
            },
            "qbaf_tau": {
                "type": "float",
                "label": "QBAF Equilibrium Standing τ*",
                "description": "Asymptotic justification standing evaluated by continuous Quadratic Energy semantics",
                "domain": [0.0, 1.0],
            },
            "total_weight_of_evidence": {
                "type": "float",
                "label": "Gross Evidentiary Volume E_total",
                "description": "Gross weight of evidence across all supporting and attacking warrants (Keynes/Gärdenfors)",
                "domain": [0.0, None],
            },
            "volatility_index": {
                "type": "float",
                "label": "Epistemic Controversy V",
                "description": "Controversy tension index quantifying evenly contested evidence",
                "domain": [0.0, 1.0],
            },
            "decision_tier": {
                "type": "string",
                "label": "Decision Tier",
                "description": "Execution origin: System 1 fast-exit vs System 2 generative synthesis",
                "enum": ["system_1", "system_2", "legacy"],
            },
        }
        return payload

    def resolve_polarity(self, relation_type: str) -> int | None:
        """Resolve edge polarity (+1, -1, 0) or None if unmapped.

        Per D-15, missing entries resolve to None (null on wire), NEVER to 0.
        0 denotes explicitly neutral argumentative charge, whereas None
        denotes an unmapped or open-vocabulary predicate.

        Parameters
        ----------
        relation_type : str
            The raw predicate or relation string.

        Returns
        -------
        int or None
            1 for support, -1 for attack, 0 for neutral, or None if unmapped.
        """
        polarities = self.schema.relation_polarities or {}
        if relation_type in polarities:
            return polarities[relation_type]

        # Check configured custom predicate aliases/mappings
        if relation_type in self.predicate_aliases:
            entry = self.predicate_aliases[relation_type]
            if isinstance(entry, dict) and "polarity" in entry:
                return entry["polarity"]
            if isinstance(entry, int) and entry in (-1, 0, 1):
                return entry
            if isinstance(entry, str) and entry in polarities:
                return polarities[entry]

        return None

    def resolve_partition(self, component_type: str) -> Literal["B", "A"] | None:
        """Resolve L3 TheoryNet partition ('B' for empirical base, 'A' for theoretical antecedent).

        Parameters
        ----------
        component_type : str
            Argument component type name.

        Returns
        -------
        Literal['B', 'A'] or None
            Partition code 'B' or 'A', or None if unmapped.
        """
        partitions = self.schema.component_partitions or {}
        val = partitions.get(component_type)
        if val in ("B", "A"):
            return val
        return None

    def resolve_node_descriptor(self, node_type: str, layer: int) -> dict[str, Any]:
        """Resolve presentation metadata for a node type.

        Per D-13, unknown types degrade gracefully to neutral styling without raising errors.

        Parameters
        ----------
        node_type : str
            Semantic node type name.
        layer : int
            Graph layer (1, 2, or 3).

        Returns
        -------
        dict of str to Any
            Descriptor with 'known', 'definition', and 'partition'.
        """
        known = False
        definition = None
        partition = None

        if layer == 2:
            known = node_type in self.schema.node_types
            definition = self.schema.node_definitions.get(node_type)
        elif layer == 3:
            known = node_type in self.schema.component_types
            definition = self.schema.component_definitions.get(node_type)
            partition = self.resolve_partition(node_type)

        return {
            "type": node_type,
            "layer": layer,
            "known": known,
            "definition": definition,
            "partition": partition,
        }

    def resolve_edge_descriptor(
        self,
        relation_type: str,
        layer: int | None = None,
    ) -> dict[str, Any]:
        """Resolve presentation and ontological metadata for an edge relation predicate.

        Parameters
        ----------
        relation_type : str
            The relation predicate string.
        layer : int or None, optional
            Explicit graph layer (2 or 3) if known.

        Returns
        -------
        dict of str to Any
            Descriptor containing 'type', 'layer', 'known', 'polarity', 'definition', and 'alias_of'.
        """
        known = (
            relation_type in self.schema.relation_types
            or relation_type in self.schema.argument_relation_types
        )
        definition = (
            self.schema.relation_definitions.get(relation_type)
            or self.schema.argument_relation_definitions.get(relation_type)
        )
        polarity = self.resolve_polarity(relation_type)
        alias_of = None

        if relation_type in self.predicate_aliases:
            alias_entry = self.predicate_aliases[relation_type]
            if isinstance(alias_entry, dict):
                alias_of = alias_entry.get("canonical") or alias_entry.get("target")
                if not definition:
                    definition = alias_entry.get("definition")
            elif isinstance(alias_entry, str):
                alias_of = alias_entry

        inferred_layer = layer
        if inferred_layer is None:
            if relation_type in self.schema.argument_relation_types:
                inferred_layer = 3
            elif relation_type in self.schema.relation_types:
                inferred_layer = 2

        return {
            "type": relation_type,
            "layer": inferred_layer,
            "known": known or (alias_of is not None),
            "polarity": polarity,
            "definition": definition,
            "alias_of": alias_of,
        }
