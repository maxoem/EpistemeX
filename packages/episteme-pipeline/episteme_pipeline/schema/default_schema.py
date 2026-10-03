from __future__ import annotations

from pydantic import BaseModel, Field


L2_NODE_TYPES: list[str] = [
    "Concept",
    "Person",
    "Work",
    "Theory",
    "Institution"
]

L2_RELATION_TYPES: list[str] = [
    "RELATED_TO",
    "INSTANCE_OF",
    "PART_OF",
    "SUBCLASS_OF",
    "SUPPORTS",
    "REFUTES",
    "IMPLIES",
    "CONTRADICTS"
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
    "CoreExpansion"
]
L3_RELATION_TYPES: list[str] = [
    "ATTACKS",
    "SUPPORTS_ARG",
    "UNDERCUTS",
    "SPECIALIZES",
    "CONSTRAINS",
    "REDUCES_TO",
    "ENTAILS",
    "DEDUCES",
    "COHERES_WITH",
    "INHIBITS"
]

L3_COMPONENT_DEFINITIONS: dict[str, str] = {
    "ObservationUnit": "Singular or localized statements containing exclusively observational terms. Act as raw data nodes.",
    "EmpiricalStatement": "Statements containing only logical and empirical concepts.",
    "TheoreticalHypothesis": "Statements containing theoretical concepts or whose quantifiers have theoretical scope. These represent core laws or abstract hypotheses.",
    "CoreExpansion": "Special auxiliary laws and constraints that form a shifting superstructure around the stable theory core."
}

L3_RELATION_DEFINITIONS: dict[str, str] = {
    "ATTACKS": "Argument component attacks another (critical relationship).",
    "SUPPORTS_ARG": "Argument component provides support for another.",
    "UNDERCUTS": "Argument component undermines the inference of another.",
    "SPECIALIZES": "Directed vertical edges forming a hierarchy where a specialized node inherits and restricts properties from its parent.",
    "CONSTRAINS": "Lateral/horizontal edges crossing overlapping applications to ensure intrinsic properties remain constant.",
    "REDUCES_TO": "Intertheoretical links connecting entirely separate theories, including strict reduction from older to newer theories.",
    "ENTAILS": "Intertheoretical links connecting entirely separate theories, including strict reduction from older to newer theories.",
    "DEDUCES": "Logical entailments between nodes such as Explanation Patterns (Erklärungsschema) and Falsification Patterns (Falsifikationsschema).",
    "COHERES_WITH": "Positive (excitatory) connections between hypotheses that explain evidence, or co-hypotheses that jointly explain a fact.",
    "INHIBITS": "Negative (inhibitory) weights representing incoherence between logically contradictory or competing hypotheses."
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
    "SPECIALIZES": 0,
    "CONSTRAINS": 0,
    "REDUCES_TO": 1,
    "ENTAILS": 1,
    "DEDUCES": 1,
    "COHERES_WITH": 1,
    "INHIBITS": -1
}


COMPONENT_PARTITIONS: dict[str, str] = {
    "ObservationUnit": "B",
    "EmpiricalStatement": "B",
    "TheoreticalHypothesis": "A",
    "CoreExpansion": "A"
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
    node_definitions: dict[str, str] = Field(default_factory=lambda: dict(L2_NODE_DEFINITIONS))
    relation_definitions: dict[str, str] = Field(default_factory=lambda: dict(L2_RELATION_DEFINITIONS))
    component_types: list[str] = Field(default_factory=lambda: list(L3_COMPONENT_TYPES))
    argument_relation_types: list[str] = Field(default_factory=lambda: list(L3_RELATION_TYPES))
    component_definitions: dict[str, str] = Field(default_factory=lambda: dict(L3_COMPONENT_DEFINITIONS))
    argument_relation_definitions: dict[str, str] = Field(default_factory=lambda: dict(L3_RELATION_DEFINITIONS))
    relation_polarities: dict[str, int] = Field(default_factory=lambda: dict(RELATION_POLARITIES))
    component_partitions: dict[str, str] = Field(default_factory=lambda: dict(COMPONENT_PARTITIONS))
    scope_types: list[str] = Field(default_factory=lambda: list(SCOPE_TYPES))
    epistemic_statuses: list[str] = Field(default_factory=lambda: list(EPISTEMIC_STATUSES))

    def node_types_str(self) -> str:
        return ", ".join(self.node_types)

    def relation_types_str(self) -> str:
        return ", ".join(self.relation_types)

    def component_types_str(self) -> str:
        import json
        payload = {k: self.component_definitions.get(k, "No description provided.") for k in self.component_types}
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def argument_relation_types_str(self) -> str:
        import json
        payload = {k: self.argument_relation_definitions.get(k, "No description provided.") for k in self.argument_relation_types}
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
        return self.relation_polarities.get(relation_type, self.relation_polarities.get(relation_type.upper(), 0)) > 0

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
        return self.relation_polarities.get(relation_type, self.relation_polarities.get(relation_type.upper(), 0)) < 0

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

        cand_pol = self.relation_polarities.get(cand_upper, self.relation_polarities.get(candidate, 0))
        if cand_pol != 0:
            for r in self.argument_relation_types:
                if self.relation_polarities.get(r) == cand_pol:
                    return r
        return None


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
