"""
Domain models and DTOs for graph algorithms and evaluation.

Provides validated boundary data transfer objects and normalized result
containers for topological graph algorithms (centralities, community detection,
and connectivity components).
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Iterator, Mapping, Optional
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class AlgorithmExecutionMode(str, Enum):
    """Execution mode for graph data science algorithms.

    Attributes
    ----------
    STREAM : str
        Stream computation results directly back as rows.
    MUTATE : str
        Write computation results back into an in-memory graph projection.
    WRITE : str
        Write computation results back into database node/relationship properties.
    STATS : str
        Return statistical summary without mutating or returning all rows.
    """

    STREAM = "stream"
    MUTATE = "mutate"
    WRITE = "write"
    STATS = "stats"


class CentralityResult(BaseModel, Mapping[str, float]):
    """Standardized result container for node centrality calculations.

    Provides a dictionary-like interface mapping node identifiers to their
    continuous centrality scores, alongside metadata regarding algorithm provenance.

    Parameters
    ----------
    scores : dict[str, float]
        Mapping from canonical node IDs to computed centrality scores.
    algorithm : str
        Name of the centrality algorithm (e.g. 'pagerank', 'betweenness').
    backend : str
        Execution backend responsible for computation (e.g. 'neo4j_gds', 'networkx').
    """

    model_config = ConfigDict(frozen=True)

    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Mapping from node domain ID to centrality score.",
    )
    algorithm: str = Field(
        ...,
        description="Name of the computed algorithm.",
    )
    backend: str = Field(
        ...,
        description="Underlying execution backend ('neo4j_gds' or 'networkx').",
    )

    def __getitem__(self, node_id: str) -> float:
        """Retrieve centrality score for a specific node ID."""
        return self.scores[node_id]

    def __iter__(self) -> Iterator[str]:
        """Iterate over all node IDs in the result."""
        return iter(self.scores)

    def __len__(self) -> int:
        """Return total number of scored nodes."""
        return len(self.scores)

    def top_k(self, k: int = 5) -> list[tuple[str, float]]:
        """Return the top-k highest scored nodes in descending order.

        Parameters
        ----------
        k : int, optional
            Number of top nodes to return (default: 5).

        Returns
        -------
        list[tuple[str, float]]
            List of (node_id, score) pairs sorted from highest to lowest.
        """
        sorted_items = sorted(self.scores.items(), key=lambda item: item[1], reverse=True)
        return sorted_items[:k]

    @property
    def max_score(self) -> float:
        """Return maximum centrality score, or 0.0 if empty."""
        return max(self.scores.values()) if self.scores else 0.0

    @property
    def min_score(self) -> float:
        """Return minimum centrality score, or 0.0 if empty."""
        return min(self.scores.values()) if self.scores else 0.0

    @property
    def mean_score(self) -> float:
        """Return arithmetic mean of centrality scores, or 0.0 if empty."""
        if not self.scores:
            return 0.0
        return float(np.mean(list(self.scores.values())))


class PartitionResult(BaseModel):
    """Standardized result container for graph partition and community algorithms.

    Parameters
    ----------
    partitions : list[set[str]]
        List of disjoint node ID sets representing detected communities or components.
    node_to_partition : dict[str, int]
        Mapping from individual node ID to its assigned partition/community index.
    algorithm : str
        Name of the partition algorithm (e.g. 'louvain', 'wcc').
    backend : str
        Execution backend responsible for computation ('neo4j_gds' or 'networkx').
    """

    model_config = ConfigDict(frozen=True)

    partitions: list[set[str]] = Field(
        default_factory=list,
        description="List of component/community node sets.",
    )
    node_to_partition: dict[str, int] = Field(
        default_factory=dict,
        description="Mapping from node domain ID to partition index.",
    )
    algorithm: str = Field(
        ...,
        description="Name of the computed algorithm.",
    )
    backend: str = Field(
        ...,
        description="Underlying execution backend ('neo4j_gds' or 'networkx').",
    )

    @property
    def num_partitions(self) -> int:
        """Return total number of detected partitions."""
        return len(self.partitions)

    def partition_of(self, node_id: str) -> int:
        """Retrieve the partition ID assigned to a node.

        Parameters
        ----------
        node_id : str
            Domain identifier of the node.

        Returns
        -------
        int
            Partition index.

        Raises
        ------
        KeyError
            If node_id is not found in the partition result.
        """
        return self.node_to_partition[node_id]

    def get_partition(self, partition_id: int) -> set[str]:
        """Retrieve the set of nodes belonging to a partition.

        Parameters
        ----------
        partition_id : int
            Index of the partition.

        Returns
        -------
        set[str]
            Set of node IDs.
        """
        return self.partitions[partition_id]

    @property
    def partition_sizes(self) -> list[int]:
        """Return the size of each partition in order."""
        return [len(part) for part in self.partitions]


class NodeType(str, Enum):
    """Ontological and epistemic classification for theory graph nodes.

    Attributes
    ----------
    AXIOM : str
        Foundational law or mathematical axiom (M).
    HYPOTHESIS : str
        Theoretical conjecture or auxiliary hypothesis.
    CLAIM : str
        Argumentative claim or empirical statement.
    CONCEPT : str
        Theoretical or non-theoretical concept / base set.
    PHENOMENON : str
        Observed empirical phenomenon or explanandum.
    EVIDENCE : str
        Empirical observation unit or verification data.
    THEORY_ELEMENT : str
        Bourbaki structural theory element T = <K, I>.
    POTENTIAL_MODEL : str
        Potential model class M_p (conceptual framework & signatures).
    ACTUAL_MODEL : str
        Actual model class M (substantive laws & axioms).
    PARTIAL_POTENTIAL_MODEL : str
        Partial potential model class M_pp (non-theoretical empirical basis).
    CONSTRAINT : str
        Global invariance constraint GC across models.
    PARADIGM : str
        Paradigmatic application or exemplar system I_0.
    """

    AXIOM = "axiom"
    HYPOTHESIS = "hypothesis"
    CLAIM = "claim"
    CONCEPT = "concept"
    PHENOMENON = "phenomenon"
    EVIDENCE = "evidence"
    THEORY_ELEMENT = "theory_element"
    POTENTIAL_MODEL = "potential_model"
    ACTUAL_MODEL = "actual_model"
    PARTIAL_POTENTIAL_MODEL = "partial_potential_model"
    CONSTRAINT = "constraint"
    PARADIGM = "paradigm"

    def __eq__(self, other: object) -> bool:
        """Compare enum instance with another enum or case-insensitive string."""
        if isinstance(other, str):
            return self.value.lower() == other.lower() or self.name.lower() == other.lower()
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return hash matching enum identity."""
        return super().__hash__()

    @classmethod
    def from_str(cls, val: str | NodeType) -> NodeType:
        """Parse a string or enum instance into a canonical NodeType.

        Parameters
        ----------
        val : str or NodeType
            String representation or existing NodeType enum.

        Returns
        -------
        NodeType
            Matched NodeType enum member, falling back to CONCEPT if unknown.
        """
        if isinstance(val, cls):
            return val
        if not isinstance(val, str):
            return cls.CONCEPT

        cleaned = val.strip()
        if ":" in cleaned:
            cleaned = cleaned.split(":")[-1]

        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", cleaned)
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower().replace("-", "_").replace(" ", "_")

        for member in cls:
            if member.value == normalized or member.name.lower() == normalized:
                return member

        alias_map = {
            "theoryelement": cls.THEORY_ELEMENT,
            "potentialmodel": cls.POTENTIAL_MODEL,
            "actualmodel": cls.ACTUAL_MODEL,
            "partialpotentialmodel": cls.PARTIAL_POTENTIAL_MODEL,
            "globalconstraint": cls.CONSTRAINT,
            "global_constraint": cls.CONSTRAINT,
            "paradigmaticapplication": cls.PARADIGM,
            "paradigmatic_application": cls.PARADIGM,
            "observationunit": cls.EVIDENCE,
            "observation_unit": cls.EVIDENCE,
            "empiricalstatement": cls.CLAIM,
            "empirical_statement": cls.CLAIM,
            "theoreticalhypothesis": cls.HYPOTHESIS,
            "theoretical_hypothesis": cls.HYPOTHESIS,
            "coreexpansion": cls.HYPOTHESIS,
            "core_expansion": cls.HYPOTHESIS,
            "coreaxiom": cls.AXIOM,
            "core_axiom": cls.AXIOM,
            "core_theory": cls.AXIOM,
            "foundation": cls.AXIOM,
            "premise": cls.CLAIM,
            "auxiliary": cls.HYPOTHESIS,
            "domain": cls.PARADIGM,
            "intendedapplication": cls.PARADIGM,
            "intended_application": cls.PARADIGM,
        }
        cleaned_simple = cleaned.lower().replace("-", "").replace("_", "").replace(" ", "")
        if cleaned_simple in alias_map:
            return alias_map[cleaned_simple]
        if normalized in alias_map:
            return alias_map[normalized]

        return cls.CONCEPT


class EpistemicStatus(str, Enum):
    """Lakatosian or formal epistemic status of a node in a theory net.

    Attributes
    ----------
    HARD_CORE : str
        Irrefutable foundational core axiom or substantive law.
    PROTECTIVE_BELT : str
        Auxiliary hypothesis or condition absorbing empirical refutations.
    NEUTRAL : str
        Standard uncommitted or unclassified epistemic stance.
    ANOMALOUS : str
        Defeated, refuted, or anomalous empirical finding.
    """

    HARD_CORE = "hard_core"
    PROTECTIVE_BELT = "protective_belt"
    NEUTRAL = "neutral"
    ANOMALOUS = "anomalous"

    def __eq__(self, other: object) -> bool:
        """Compare enum instance with another enum or case-insensitive string."""
        if isinstance(other, str):
            return self.value.lower() == other.lower() or self.name.lower() == other.lower()
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return hash matching enum identity."""
        return super().__hash__()

    @classmethod
    def from_str(cls, val: str | EpistemicStatus) -> EpistemicStatus:
        """Parse a string or enum instance into an EpistemicStatus.

        Parameters
        ----------
        val : str or EpistemicStatus
            String representation or existing EpistemicStatus enum.

        Returns
        -------
        EpistemicStatus
            Matched EpistemicStatus enum member, falling back to NEUTRAL if unknown.
        """
        if isinstance(val, cls):
            return val
        if not isinstance(val, str):
            return cls.NEUTRAL

        cleaned = val.strip()
        if ":" in cleaned:
            cleaned = cleaned.split(":")[-1]

        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", cleaned)
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower().replace("-", "_").replace(" ", "_")

        for member in cls:
            if member.value == normalized or member.name.lower() == normalized:
                return member

        alias_map = {
            "hardcore": cls.HARD_CORE,
            "hard_core": cls.HARD_CORE,
            "core": cls.HARD_CORE,
            "actual_model": cls.HARD_CORE,
            "protectivebelt": cls.PROTECTIVE_BELT,
            "protective_belt": cls.PROTECTIVE_BELT,
            "belt": cls.PROTECTIVE_BELT,
            "auxiliary": cls.PROTECTIVE_BELT,
            "anomaly": cls.ANOMALOUS,
            "anomalous": cls.ANOMALOUS,
        }
        cleaned_simple = cleaned.lower().replace("-", "").replace("_", "").replace(" ", "")
        if cleaned_simple in alias_map:
            return alias_map[cleaned_simple]
        if normalized in alias_map:
            return alias_map[normalized]

        return cls.NEUTRAL


class RelationType(str, Enum):
    """Relational and structural classifications for theory graph edges.

    Attributes
    ----------
    EXPLAINS : str
        Deductive or explanatory relation from explanans to explanandum.
    SUPPORTS : str
        Evidential or inferential positive support relation.
    ATTACKS : str
        Adversarial defeater or undercutting attack relation.
    SPECIALIZES : str
        Specialization link in theory element poset hierarchy.
    REDUCES_TO : str
        Inter-theoretical reduction link.
    CONSTRAINS : str
        Cross-model or invariant parameter constraint.
    PRESUPPOSES : str
        Prerequisite ontological or conceptual presupposition.
    COHERES_WITH : str
        Mutual explanatory coherence association.
    EQUIVALENT_TO : str
        Formal or logical equivalence relation.
    HAS_ACTUAL_MODEL : str
        Model decomposition link: TheoryElement -> ActualModel (M).
    HAS_POTENTIAL_MODEL : str
        Model decomposition link: TheoryElement -> PotentialModel (M_p).
    HAS_PARTIAL_POTENTIAL_MODEL : str
        Model decomposition link: TheoryElement -> PartialPotentialModel (M_pp).
    HAS_CONSTRAINT : str
        Model decomposition link: TheoryElement -> GlobalConstraint (GC).
    HAS_PARADIGM : str
        Model decomposition link: TheoryElement -> Paradigm (I_0).
    HAS_INTENDED_APPLICATION : str
        Model decomposition link: TheoryElement -> Intended Application (I).
    EMPIRICALLY_EQUIVALENT : str
        Empirical equivalence across partial potential models.
    """

    EXPLAINS = "explains"
    SUPPORTS = "supports"
    ATTACKS = "attacks"
    SPECIALIZES = "specializes"
    REDUCES_TO = "reduces_to"
    CONSTRAINS = "constrains"
    PRESUPPOSES = "presupposes"
    COHERES_WITH = "coheres_with"
    EQUIVALENT_TO = "equivalent_to"
    HAS_ACTUAL_MODEL = "has_actual_model"
    HAS_POTENTIAL_MODEL = "has_potential_model"
    HAS_PARTIAL_POTENTIAL_MODEL = "has_partial_potential_model"
    HAS_CONSTRAINT = "has_constraint"
    HAS_PARADIGM = "has_paradigm"
    HAS_INTENDED_APPLICATION = "has_intended_application"
    EMPIRICALLY_EQUIVALENT = "empirically_equivalent"

    def __eq__(self, other: object) -> bool:
        """Compare enum instance with another enum or case-insensitive string."""
        if isinstance(other, str):
            return self.value.lower() == other.lower() or self.name.lower() == other.lower()
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return hash matching enum identity."""
        return super().__hash__()

    @property
    def default_polarity(self) -> int:
        """Return canonical epistemic polarity for this relation type.

        Returns
        -------
        int
            +1 for supportive/entailment relations, -1 for adversarial relations,
            0 for structural/model composition relations.
        """
        if self in {RelationType.ATTACKS}:
            return -1
        if self in {
            RelationType.SPECIALIZES,
            RelationType.CONSTRAINS,
            RelationType.REDUCES_TO,
            RelationType.HAS_ACTUAL_MODEL,
            RelationType.HAS_POTENTIAL_MODEL,
            RelationType.HAS_PARTIAL_POTENTIAL_MODEL,
            RelationType.HAS_CONSTRAINT,
            RelationType.HAS_PARADIGM,
            RelationType.HAS_INTENDED_APPLICATION,
        }:
            return 0
        return 1

    @classmethod
    def from_str(cls, val: str | RelationType) -> RelationType:
        """Parse a string or enum instance into a canonical RelationType.

        Parameters
        ----------
        val : str or RelationType
            String representation or existing RelationType enum.

        Returns
        -------
        RelationType
            Matched RelationType enum member, falling back to EXPLAINS if unknown.
        """
        if isinstance(val, cls):
            return val
        if not isinstance(val, str):
            return cls.EXPLAINS

        cleaned = val.strip()
        if ":" in cleaned:
            cleaned = cleaned.split(":")[-1]

        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", cleaned)
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower().replace("-", "_").replace(" ", "_")

        for member in cls:
            if member.value == normalized or member.name.lower() == normalized:
                return member

        alias_map = {
            "hasactualmodel": cls.HAS_ACTUAL_MODEL,
            "haspotentialmodel": cls.HAS_POTENTIAL_MODEL,
            "haspartialpotentialmodel": cls.HAS_PARTIAL_POTENTIAL_MODEL,
            "hasconstraint": cls.HAS_CONSTRAINT,
            "hasparadigm": cls.HAS_PARADIGM,
            "hasintendedapplication": cls.HAS_INTENDED_APPLICATION,
            "has_intended_application": cls.HAS_INTENDED_APPLICATION,
            "reducesto": cls.REDUCES_TO,
            "cohereswith": cls.COHERES_WITH,
            "equivalentto": cls.EQUIVALENT_TO,
            "empiricallyequivalent": cls.EMPIRICALLY_EQUIVALENT,
            "supportsarg": cls.SUPPORTS,
            "attacksarg": cls.ATTACKS,
            "rebuts": cls.ATTACKS,
            "undercuts": cls.ATTACKS,
            "refutes": cls.ATTACKS,
            "contradicts": cls.ATTACKS,
            "entails": cls.SUPPORTS,
            "deduces": cls.SUPPORTS,
        }
        cleaned_simple = cleaned.lower().replace("-", "").replace("_", "").replace(" ", "")
        if cleaned_simple in alias_map:
            return alias_map[cleaned_simple]
        if normalized in alias_map:
            return alias_map[normalized]

        return cls.EXPLAINS


class TheoryNode(BaseModel):
    """Domain node representation in a TheoryGraph.

    Parameters
    ----------
    id : str
        Canonical unique identifier of the node.
    name : str
        Human-readable name or label.
    node_type : NodeType, optional
        Epistemic or ontological classification (default: NodeType.CONCEPT).
    epistemic_status : EpistemicStatus, optional
        Lakatosian epistemic status (default: EpistemicStatus.NEUTRAL).
    confidence : float, optional
        Extraction or epistemic confidence score (default: 1.0).
    description : str | None, optional
        Textual formulation or proposition statement.
    provenance : list[str], optional
        Originating chunk identifiers or citation references.
    attributes : dict[str, Any], optional
        Domain-specific properties (e.g. formalAxiom, textAnchor).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique node identifier.")
    name: str = Field(..., description="Human-readable node label or name.")
    node_type: NodeType = Field(default=NodeType.CONCEPT, description="Epistemic/ontological node type.")
    epistemic_status: EpistemicStatus = Field(
        default=EpistemicStatus.NEUTRAL, description="Lakatosian or epistemic status."
    )
    confidence: float = Field(default=1.0, description="Extraction or validation confidence.")
    description: Optional[str] = Field(default=None, description="Detailed text or description.")
    provenance: list[str] = Field(default_factory=list, description="Source chunk IDs or citation URIs.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Arbitrary domain attributes.")

    @property
    def type(self) -> NodeType:
        """Alias for node_type for backward and test compatibility.

        Returns
        -------
        NodeType
            The node classification.
        """
        return self.node_type

    def __getitem__(self, key: str) -> Any:
        """Retrieve attribute or model field by key.

        Parameters
        ----------
        key : str
            Attribute or field name.

        Returns
        -------
        Any
            Field value or attribute value.

        Raises
        ------
        KeyError
            If key is not found in model fields or attributes dictionary.
        """
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.attributes:
            return self.attributes[key]
        raise KeyError(f"Attribute or field '{key}' not found on TheoryNode '{self.id}'.")

    def get(self, key: str, default: Any = None) -> Any:
        """Safely retrieve attribute or model field with a default value.

        Parameters
        ----------
        key : str
            Attribute or field name.
        default : Any, optional
            Fallback value if key is not found (default: None).

        Returns
        -------
        Any
            Field value, attribute value, or default.
        """
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return self.attributes.get(key, default)


class TheoryEdge(BaseModel):
    """Domain edge representation in a TheoryGraph.

    Parameters
    ----------
    source : str
        Source node identifier.
    target : str
        Target node identifier.
    relation_type : RelationType, optional
        Relational classification (default: RelationType.EXPLAINS).
    confidence : float, optional
        Confidence score of the relation (default: 1.0).
    weight : float, optional
        Continuous edge weight (default: 1.0).
    polarity : int, optional
        Epistemic polarity: +1 (support), -1 (attack), 0 (structural).
    attributes : dict[str, Any], optional
        Domain-specific properties (e.g. scope, layer).
    """

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="Source node domain identifier.")
    target: str = Field(..., description="Target node domain identifier.")
    relation_type: RelationType = Field(default=RelationType.EXPLAINS, description="Canonical relation type.")
    confidence: float = Field(default=1.0, description="Confidence score.")
    weight: float = Field(default=1.0, description="Edge weight.")
    polarity: int = Field(default=1, description="Epistemic polarity (-1, 0, +1).")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Arbitrary domain attributes.")

    @property
    def type(self) -> RelationType:
        """Alias for relation_type.

        Returns
        -------
        RelationType
            The edge classification.
        """
        return self.relation_type

    def __getitem__(self, key: str) -> Any:
        """Retrieve attribute or model field by key.

        Parameters
        ----------
        key : str
            Attribute or field name.

        Returns
        -------
        Any
            Field value or attribute value.

        Raises
        ------
        KeyError
            If key is not found in model fields or attributes dictionary.
        """
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.attributes:
            return self.attributes[key]
        raise KeyError(f"Attribute or field '{key}' not found on TheoryEdge '{self.source}->{self.target}'.")

    def get(self, key: str, default: Any = None) -> Any:
        """Safely retrieve attribute or model field with a default value.

        Parameters
        ----------
        key : str
            Attribute or field name.
        default : Any, optional
            Fallback value if key is not found (default: None).

        Returns
        -------
        Any
            Field value, attribute value, or default.
        """
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return self.attributes.get(key, default)

