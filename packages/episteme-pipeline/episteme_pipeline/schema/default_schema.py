from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class StructuralRelationType(StrEnum):
    """Schema-owned property-graph structural edge type constants.

    These edges represent provenance, containment, structural alignment,
    community membership, and hyperedge reification plumbing rather than
    domain semantic predicates injected into extraction prompts.
    """

    CONTAINS = "CONTAINS"
    EXTRACTED_FROM = "EXTRACTED_FROM"
    SAME_AS = "SAME_AS"
    MENTIONS = "MENTIONS"
    HAS_PREMISE = "HAS_PREMISE"
    CONCLUDES = "CONCLUDES"
    IN_COMMUNITY = "IN_COMMUNITY"


STRUCTURAL_EDGE_TYPES: frozenset[str] = frozenset(StructuralRelationType)

POLARITY_OVERRIDE_TOKENS: dict[str, int] = {
    "+": 1,
    "+1": 1,
    "1": 1,
    "POS": 1,
    "POSITIVE": 1,
    "SUPPORT": 1,
    "-": -1,
    "-1": -1,
    "NEG": -1,
    "NEGATIVE": -1,
    "ATTACK": -1,
    "0": 0,
    "NEUTRAL": 0,
}

L2_NODE_TYPES: list[str] = ["Concept", "Person", "Work", "Theory", "Institution"]

L2_RELATION_TYPES: list[str] = [
    "RELATED_TO",
    "INSTANCE_OF",
    "PART_OF",
    "SUBCLASS_OF",
    "SUPPORTS",
    "REFUTES",
    "IMPLIES",
    "CONTRADICTS",
]

L2_NODE_DEFINITIONS: dict[str, str] = {
    "Concept": "Abstract idea, category, mental construct, or theoretical term (e.g. 'Justified True Belief', 'Working Memory').",
    "Person": "Individual thinker, scientist, philosopher, author, or historical figure (e.g. 'Edmund Gettier', 'Immanuel Kant').",
    "Work": "Publication, paper, treatise, book, or essay (e.g. 'Is Justified True Belief Knowledge?', 'Critique of Pure Reason').",
    "Theory": "Cohesive conceptual framework, formal model, doctrine, or system (e.g. 'Classical Theory of Knowledge', 'Behaviorism').",
    "Institution": "Academic school, university, research group, movement, or organization (e.g. 'Vienna Circle', 'Harvard University').",
}

L2_RELATION_DEFINITIONS: dict[str, str] = {
    "RELATED_TO": "General associative semantic connection between entities.",
    "INSTANCE_OF": "Entity is a concrete realization or token of a conceptual type.",
    "PART_OF": "Mereological containment or constituent sub-component.",
    "SUBCLASS_OF": "Taxonomic specialization or categorical subsumption.",
    "SUPPORTS": "Entity evidence or premise positively contributes to another.",
    "REFUTES": "Entity evidence or counterargument denies or falsifies another.",
    "IMPLIES": "Logical, causal, or inferential entailment from source to target.",
    "CONTRADICTS": "Direct propositional inconsistency or mutual exclusivity.",
}

L3_COMPONENT_TYPES: list[str] = [
    "ObservationUnit",
    "EmpiricalStatement",
    "TheoreticalHypothesis",
    "CoreExpansion",
]
L3_RELATION_TYPES: list[str] = [
    "ATTACKS",
    "SUPPORTS_ARG",
    "UNDERCUTS",
    "BACKS",
    "SPECIALIZES",
    "CONSTRAINS",
    "REDUCES_TO",
    "ENTAILS",
    "DEDUCES",
    "COHERES_WITH",
    "INHIBITS",
]

L3_COMPONENT_DEFINITIONS: dict[str, str] = {
    "ObservationUnit": "Singular or localized statements containing exclusively observational terms. Act as raw data nodes.",
    "EmpiricalStatement": "Statements containing only logical and empirical concepts.",
    "TheoreticalHypothesis": "Statements containing theoretical concepts or whose quantifiers have theoretical scope. These represent core laws or abstract hypotheses.",
    "CoreExpansion": "Special auxiliary laws and constraints that form a shifting superstructure around the stable theory core.",
}

L3_RELATION_DEFINITIONS: dict[str, str] = {
    "ATTACKS": "Argument component attacks another (critical relationship).",
    "SUPPORTS_ARG": "Argument component provides support for another.",
    "UNDERCUTS": "Argument component undermines the inference of another.",
    "BACKS": "Argument component provides warrant backing for an inference step.",
    "SPECIALIZES": "Directed vertical edges forming a hierarchy where a specialized node inherits and restricts properties from its parent.",
    "CONSTRAINS": "Lateral/horizontal edges crossing overlapping applications to ensure intrinsic properties remain constant.",
    "REDUCES_TO": "Intertheoretical links connecting entirely separate theories, including strict reduction from older to newer theories.",
    "ENTAILS": "Intertheoretical links connecting entirely separate theories, including strict reduction from older to newer theories.",
    "DEDUCES": "Logical entailments between nodes such as Explanation Patterns (Erklärungsschema) and Falsification Patterns (Falsifikationsschema).",
    "COHERES_WITH": "Positive (excitatory) connections between hypotheses that explain evidence, or co-hypotheses that jointly explain a fact.",
    "INHIBITS": "Negative (inhibitory) weights representing incoherence between logically contradictory or competing hypotheses.",
}

RELATION_POLARITIES: dict[str, int] = {
    "RELATED_TO": 0,
    "INSTANCE_OF": 0,
    "PART_OF": 0,
    "SUBCLASS_OF": 0,
    "SUPPORTS": 1,
    "REFUTES": -1,
    "IMPLIES": 1,
    "CONTRADICTS": -1,
    "ATTACKS": -1,
    "SUPPORTS_ARG": 1,
    "UNDERCUTS": -1,
    "BACKS": 1,
    "SPECIALIZES": 0,
    "CONSTRAINS": 0,
    "REDUCES_TO": 1,
    "ENTAILS": 1,
    "DEDUCES": 1,
    "COHERES_WITH": 1,
    "INHIBITS": -1,
}


COMPONENT_PARTITIONS: dict[str, str] = {
    "ObservationUnit": "B",
    "EmpiricalStatement": "B",
    "TheoreticalHypothesis": "A",
    "CoreExpansion": "A",
}

# Explicit aliases for external argument-mining schemas and custom extensions.
COMPONENT_PARTITION_ALIASES: dict[str, str] = {
    "Claim": "A",
    "MajorClaim": "A",
    "Premise": "A",
    "TheoreticalClaim": "A",
    "Hypothesis": "A",
    "Principle": "A",
    "Axiom": "A",
    "Law": "A",
    "Theorem": "A",
    "Observation": "B",
    "EmpiricalEvidence": "B",
    "Datum": "B",
}

SCOPE_TYPES: list[str] = [
    "Essentieller Allsatz",
    "Lokalisierter Allsatz",
    "Lokalisierter Existenzsatz",
    "Statistischer/probabilistischer Allsatz",
    "Existenzsatz",
]

EPISTEMIC_STATUSES: list[str] = [
    "Analytisch",
    "Synthetisch",
]


class SchemaConfig(BaseModel):
    """
    Decoupled schema configuration — all node/edge types the pipeline uses.

    Pass a custom instance to PipelineConfig to override the defaults for a
    different domain. Prompt templates receive these lists as {entity_types}
    and {relation_types} at runtime.
    """

    version: str = "v1"
    node_types: list[str] = Field(default_factory=lambda: list(L2_NODE_TYPES))
    relation_types: list[str] = Field(default_factory=lambda: list(L2_RELATION_TYPES))
    node_definitions: dict[str, str] = Field(
        default_factory=lambda: dict(L2_NODE_DEFINITIONS)
    )
    relation_definitions: dict[str, str] = Field(
        default_factory=lambda: dict(L2_RELATION_DEFINITIONS)
    )
    component_types: list[str] = Field(default_factory=lambda: list(L3_COMPONENT_TYPES))
    argument_relation_types: list[str] = Field(
        default_factory=lambda: list(L3_RELATION_TYPES)
    )
    component_definitions: dict[str, str] = Field(
        default_factory=lambda: dict(L3_COMPONENT_DEFINITIONS)
    )
    argument_relation_definitions: dict[str, str] = Field(
        default_factory=lambda: dict(L3_RELATION_DEFINITIONS)
    )
    relation_polarities: dict[str, int] = Field(
        default_factory=lambda: dict(RELATION_POLARITIES)
    )
    component_partitions: dict[str, str] = Field(
        default_factory=lambda: dict(COMPONENT_PARTITIONS)
    )
    component_partition_aliases: dict[str, str] = Field(
        default_factory=lambda: dict(COMPONENT_PARTITION_ALIASES)
    )
    scope_types: list[str] = Field(default_factory=lambda: list(SCOPE_TYPES))
    epistemic_statuses: list[str] = Field(
        default_factory=lambda: list(EPISTEMIC_STATUSES)
    )

    def node_types_str(self) -> str:
        return ", ".join(self.node_types)

    def relation_types_str(self) -> str:
        return ", ".join(self.relation_types)

    def component_types_str(self) -> str:
        import json

        payload = {
            k: self.component_definitions.get(k, "No description provided.")
            for k in self.component_types
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def argument_relation_types_str(self) -> str:
        import json

        payload = {
            k: self.argument_relation_definitions.get(k, "No description provided.")
            for k in self.argument_relation_types
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def get_relations_with_polarity(self, polarity: int | None = None) -> list[str]:
        """Return relation names filtered by epistemic polarity.

        Parameters
        ----------
        polarity : int or None, default None
            +1 for positive (support/entailment), -1 for negative (attack/undercut),
            0 for neutral/structural. If None, returns all non-zero dialectical relations (+1 and -1).

        Returns
        -------
        list of str
            Relation type names matching the requested polarity.
        """
        if polarity is None:
            return [r for r, p in self.relation_polarities.items() if p != 0]
        return [r for r, p in self.relation_polarities.items() if p == polarity]

    def get_support_relations(self) -> list[str]:
        """Return all relation names with positive support polarity (+1).

        Returns
        -------
        list of str
            Relation types with polarity +1.
        """
        return self.get_relations_with_polarity(1)

    def get_attack_relations(self) -> list[str]:
        """Return all relation names with negative attack polarity (-1).

        Returns
        -------
        list of str
            Relation types with polarity -1.
        """
        return self.get_relations_with_polarity(-1)

    def is_support_relation(self, relation_type: str) -> bool:
        """Check whether a relation type has positive support polarity (+1).

        Parameters
        ----------
        relation_type : str
            Relation type to evaluate.

        Returns
        -------
        bool
            True if relation has polarity +1.
        """
        return (
            self.relation_polarities.get(
                relation_type, self.relation_polarities.get(relation_type.upper(), 0)
            )
            > 0
        )

    def is_attack_relation(self, relation_type: str) -> bool:
        """Check whether a relation type has negative attack polarity (-1).

        Parameters
        ----------
        relation_type : str
            Relation type to evaluate.

        Returns
        -------
        bool
            True if relation has polarity -1.
        """
        return (
            self.relation_polarities.get(
                relation_type, self.relation_polarities.get(relation_type.upper(), 0)
            )
            < 0
        )

    def is_dialectical_relation(self, relation_type: str) -> bool:
        """Check whether a relation type has non-zero dialectical polarity (+1 or -1).

        Parameters
        ----------
        relation_type : str
            Relation type to evaluate.

        Returns
        -------
        bool
            True if relation has non-zero polarity.
        """
        return self.get_relation_polarity(relation_type) != 0

    def get_relation_polarity(self, relation_type: str) -> int:
        """Resolve signed epistemic polarity (``+1``, ``-1``, or ``0``) for a relation.

        Parameters
        ----------
        relation_type : str
            Relation or triple predicate label.

        Returns
        -------
        int
            ``+1`` for support, ``-1`` for attack, or ``0`` for neutral/unknown.
        """
        if not relation_type:
            return 0
        if relation_type in self.relation_polarities:
            return self.relation_polarities[relation_type]
        return self.relation_polarities.get(relation_type.upper(), 0)

    def resolve_edge_polarity(
        self,
        relation_type: str,
        *,
        weight_support: float | None = None,
        weight_attack: float | None = None,
        weight: float | None = None,
    ) -> int:
        """Resolve signed polarity of an edge from directional weights and schema polarity.

        Parameters
        ----------
        relation_type : str
            Relation label.
        weight_support : float or None, optional
            Positive support weight on the edge.
        weight_attack : float or None, optional
            Negative attack weight on the edge.
        weight : float or None, optional
            Signed or magnitude weight fallback.

        Returns
        -------
        int
            ``+1`` for support, ``-1`` for attack, or ``0`` when neutral.
        """
        has_support = weight_support is not None and weight_support > 0.0
        has_attack = weight_attack is not None and weight_attack > 0.0
        if has_support and not has_attack:
            return 1
        if has_attack and not has_support:
            return -1

        schema_pol = self.get_relation_polarity(relation_type)
        if schema_pol != 0:
            return schema_pol

        if weight is not None:
            if weight > 0.0:
                return 1
            if weight < 0.0:
                return -1
        return 0

    def resolve_component_partition(
        self,
        component_type: str,
        *,
        atom_type: str | None = None,
    ) -> Literal["A", "B"] | None:
        """Resolve epistemic partition (``"A"`` theoretical or ``"B"`` empirical).

        Resolves strictly via canonical ``component_partitions``, declared
        ``component_partition_aliases`` (case-insensitive), and optional
        ``atom_type`` (``"law"`` -> ``"A"``, ``"fact"`` -> ``"B"``).

        Parameters
        ----------
        component_type : str
            Component type label on an atom or extracted argument unit.
        atom_type : str or None, optional
            Logical form role (e.g., ``"law"`` or ``"fact"``).

        Returns
        -------
        {"A", "B"} or None
            Resolved partition identifier, or ``None`` if unknown.
        """
        if component_type:
            direct = self.component_partitions.get(component_type)
            if direct in {"A", "B"}:
                return direct  # type: ignore[return-value]
            lowered = component_type.strip().lower()
            for table in (self.component_partitions, self.component_partition_aliases):
                for key, part in table.items():
                    if key.lower() == lowered and part in {"A", "B"}:
                        return part  # type: ignore[return-value]
        if atom_type == "law":
            return "A"
        if atom_type == "fact":
            return "B"
        return None

    def get_partition_components(self, partition: Literal["A", "B"]) -> list[str]:
        """Return canonical schema component types assigned to a partition.

        Parameters
        ----------
        partition : {"A", "B"}
            Target Schurz/Lakatos epistemic partition.

        Returns
        -------
        list of str
            Ordered list of configured ``component_types`` belonging to ``partition``.
        """
        return [
            comp
            for comp in self.component_types
            if self.component_partitions.get(comp) == partition
        ]

    def default_observation_component_type(self) -> str:
        """Return the primary empirical observation component type from this schema.

        Returns
        -------
        str
            Canonical empirical component type name.
        """
        b_types = self.get_partition_components("B")
        if b_types:
            return b_types[0]
        for key, part in self.component_partitions.items():
            if part == "B":
                return key
        return self.component_types[0] if self.component_types else "ObservationUnit"

    def default_hypothesis_component_type(self) -> str:
        """Return the primary theoretical hypothesis component type from this schema.

        Returns
        -------
        str
            Canonical theoretical component type name.
        """
        a_types = self.get_partition_components("A")
        if a_types:
            return a_types[0]
        for key, part in self.component_partitions.items():
            if part == "A":
                return key
        return (
            self.component_types[-1]
            if self.component_types
            else "TheoreticalHypothesis"
        )

    def default_support_relation(self) -> str:
        """Return the canonical dialectical support relation label for this schema.

        Returns
        -------
        str
            Schema-registered positive-polarity argument relation type.
        """
        for rel in self.argument_relation_types:
            if self.get_relation_polarity(rel) > 0 and rel == "SUPPORTS_ARG":
                return rel
        for rel in self.argument_relation_types:
            if self.get_relation_polarity(rel) > 0:
                return rel
        return (
            self.argument_relation_types[0]
            if self.argument_relation_types
            else "SUPPORTS_ARG"
        )

    def default_attack_relation(self) -> str:
        """Return the canonical dialectical attack relation label for this schema.

        Returns
        -------
        str
            Schema-registered negative-polarity argument relation type.
        """
        for rel in self.argument_relation_types:
            if self.get_relation_polarity(rel) < 0 and rel == "ATTACKS":
                return rel
        for rel in self.argument_relation_types:
            if self.get_relation_polarity(rel) < 0:
                return rel
        return (
            self.argument_relation_types[0]
            if self.argument_relation_types
            else "ATTACKS"
        )

    def resolve_relation_type(self, candidate: str) -> str | None:
        """Resolve a candidate relation name or dialectical stance to a configured argument relation.

        Matches candidate names directly against argument_relation_types or dynamically
        maps positive/negative stance labels (e.g. 'SUPPORTS' -> 'SUPPORTS_ARG') based
        on identical polarity alignment.

        Parameters
        ----------
        candidate : str
            Candidate relation or stance identifier.

        Returns
        -------
        str or None
            Matching canonical relation type, or None if unmapped.
        """
        if not candidate:
            return None
        cand_upper = candidate.upper()
        if candidate in self.argument_relation_types:
            return candidate
        if cand_upper in self.argument_relation_types:
            return cand_upper

        cand_pol = self.get_relation_polarity(cand_upper)
        if cand_pol != 0:
            for r in self.argument_relation_types:
                if self.relation_polarities.get(r) == cand_pol:
                    return r
        return None

    def parse_polarity_override(self, polarity: str | None) -> int | None:
        """Parse an optional curation polarity override into a signed polarity.

        Checks the configured ``relation_polarities`` mapping before falling
        back to shorthand stance tokens in ``POLARITY_OVERRIDE_TOKENS``.

        Parameters
        ----------
        polarity : str or None
            Raw polarity override string (e.g. ``"+"``, ``"-"``, ``"NEUTRAL"``,
            or a schema-registered relation label).

        Returns
        -------
        int or None
            ``1`` for positive support, ``-1`` for negative attack, ``0`` for
            neutral, or ``None`` when ``polarity`` is unset, blank, or unknown.
        """
        if polarity is None:
            return None
        raw = polarity.strip()
        if not raw:
            return None
        upper = raw.upper()

        schema_pol: int | None = None
        if raw in self.relation_polarities:
            schema_pol = self.relation_polarities[raw]
        elif upper in self.relation_polarities:
            schema_pol = self.relation_polarities[upper]
        else:
            for rel_key, rel_pol in self.relation_polarities.items():
                if rel_key.upper() == upper:
                    schema_pol = rel_pol
                    break
        if schema_pol is not None:
            if schema_pol > 0:
                return 1
            if schema_pol < 0:
                return -1
            return 0

        return POLARITY_OVERRIDE_TOKENS.get(upper)

    def default_l2_relation_for_polarity(self, polarity: int) -> str:
        """Return the canonical L2 relation label matching ``polarity``.

        Parameters
        ----------
        polarity : int
            Signed epistemic polarity (``> 0`` support, ``< 0`` refute/attack,
            or ``0`` neutral).

        Returns
        -------
        str
            Schema-registered L2 predicate label for the requested polarity.
        """
        if polarity > 0:
            if (
                "SUPPORTS" in self.relation_types
                and self.get_relation_polarity("SUPPORTS") > 0
            ):
                return "SUPPORTS"
            for rel in self.relation_types:
                if self.get_relation_polarity(rel) > 0:
                    return rel
            return self.default_support_relation()
        if polarity < 0:
            if (
                "REFUTES" in self.relation_types
                and self.get_relation_polarity("REFUTES") < 0
            ):
                return "REFUTES"
            for rel in self.relation_types:
                if self.get_relation_polarity(rel) < 0:
                    return rel
            return self.default_attack_relation()
        for rel in self.relation_types:
            if self.get_relation_polarity(rel) == 0:
                return rel
        return self.relation_types[0] if self.relation_types else "RELATED_TO"

    def resolve_relation_override(
        self,
        relation_type: str,
        polarity: str | None = None,
        *,
        layer: Literal["l2", "l3"] = "l3",
    ) -> tuple[str, int | None]:
        """Resolve an effective relation label and signed polarity under this schema.

        Parameters
        ----------
        relation_type : str
            Base curated relation type or ``"REJECTED"``.
        polarity : str or None, optional
            Optional explicit polarity override string.
        layer : {"l2", "l3"}, default "l3"
            Target graph layer used when resolving a fallback relation label
            from a shorthand polarity token.

        Returns
        -------
        tuple of (str, int or None)
            ``(effective_relation_type, resolved_polarity_sign)``.
        """
        if relation_type.strip().upper() == "REJECTED":
            return "REJECTED", None
        sign = self.parse_polarity_override(polarity)
        if sign is None or sign == 0:
            return relation_type, sign

        base_type = relation_type.strip()
        if base_type and self.get_relation_polarity(base_type) == sign:
            return relation_type, sign

        if polarity is not None:
            pol_upper = polarity.strip().upper()
            if self.get_relation_polarity(pol_upper) == sign:
                return pol_upper, sign

        if layer == "l2":
            return self.default_l2_relation_for_polarity(sign), sign
        default_l3 = (
            self.default_support_relation()
            if sign > 0
            else self.default_attack_relation()
        )
        return default_l3, sign


DEFAULT_SCHEMA = SchemaConfig()


def get_support_relations(schema: SchemaConfig | None = None) -> list[str]:
    """Retrieve all relations with positive support polarity (+1).

    Parameters
    ----------
    schema : SchemaConfig or None, default None
        Schema configuration instance. If None, uses DEFAULT_SCHEMA.

    Returns
    -------
    list of str
        Relation names with polarity +1.
    """
    s = schema or DEFAULT_SCHEMA
    return s.get_support_relations()


def get_attack_relations(schema: SchemaConfig | None = None) -> list[str]:
    """Retrieve all relations with negative attack polarity (-1).

    Parameters
    ----------
    schema : SchemaConfig or None, default None
        Schema configuration instance. If None, uses DEFAULT_SCHEMA.

    Returns
    -------
    list of str
        Relation names with polarity -1.
    """
    s = schema or DEFAULT_SCHEMA
    return s.get_attack_relations()


def get_dialectical_relations(schema: SchemaConfig | None = None) -> list[str]:
    """Retrieve all relations with dialectical (non-zero) polarity.

    Parameters
    ----------
    schema : SchemaConfig or None, default None
        Schema configuration instance. If None, uses DEFAULT_SCHEMA.

    Returns
    -------
    list of str
        Relation names with non-zero polarity (+1 or -1).
    """
    s = schema or DEFAULT_SCHEMA
    return s.get_relations_with_polarity()
