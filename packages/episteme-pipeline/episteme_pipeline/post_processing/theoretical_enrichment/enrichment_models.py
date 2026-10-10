"""Theory Element models and registry for Theoretical Enrichment.

Implements structuralist metatheory concepts (Sneed, 1971; Stegmüller, 1976;
Balzer et al., 1987) representing theory-elements T = <K, I>, their non-theoretical
base M_pp, potential models M_p, and core laws M.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation


class InducedTheoryLaw(BaseModel):
    """Pydantic model representing a dynamically induced core law or constraint.

    Attributes
    ----------
    law_id : str
        Unique snake_case identifier for the law.
    description : str
        Human-readable summary of the axiom or functional constraint.
    formula_expression : str
        Normalized mathematical constraint expression (e.g. 'abs(param1 - param2) * 0.5').
    involved_parameters : list[str]
        Theoretical parameters involved in this law.
    """

    law_id: str
    description: str
    formula_expression: str = Field(
        default="",
        description="Normalized mathematical constraint expression over parameters",
    )
    involved_parameters: list[str] = Field(default_factory=list)


class InducedTheoryElement(BaseModel):
    """Pydantic model representing a dynamically induced Theory-Element T = <K>.

    Attributes
    ----------
    theory_id : str
        Unique snake_case identifier for the theory.
    name : str
        Full title of the scientific or philosophical theory.
    description : str
        Summary of the theoretical paradigm and explanatory scope.
    claimant_hypothesis_ids : list[str]
        IDs of TheoreticalHypothesis nodes that belong to this theory.
    required_dimensions : list[str]
        Observable, theory-independent empirical dimensions (M_pp) needed to test this theory.
    parameter_names : list[str]
        Latent theoretical parameters (M_p) postulated by this theory.
    laws : list[InducedTheoryLaw]
        Core relational axioms or constraints governing the parameters (M).
    max_admissible_blur : float
        Upper bound for admissible blurs (A).
    """

    theory_id: str = Field(description="Unique snake_case identifier for the theory")
    name: str = Field(description="Full title of the theory")
    description: str = Field(default="", description="Summary of the theory scope")
    claimant_hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="IDs of TheoreticalHypothesis nodes belonging to this theory",
    )
    required_dimensions: list[str] = Field(
        default_factory=list,
        description="Observable, theory-independent empirical dimensions (M_pp)",
    )
    parameter_names: list[str] = Field(
        default_factory=list,
        description="Latent theoretical parameters (M_p) postulated by this theory",
    )
    laws: list[InducedTheoryLaw] = Field(
        default_factory=list,
        description="Core relational axioms or constraints governing the parameters",
    )
    max_admissible_blur: float = Field(default=1.0, ge=0.0)


class TheoryInductionOutput(BaseModel):
    """Structured LLM output schema for Theory-Element induction."""

    theories: list[InducedTheoryElement] = Field(
        default_factory=list,
        description="List of formal Theory-Elements induced from the text",
    )


class ClusterProjectionOutput(BaseModel):
    """Structured LLM output schema for empirical cluster projection."""

    cluster_id: str = Field(description="Identifier of the empirical cluster")
    theory_id: str = Field(description="Identifier of the claiming theory")
    observed_dimensions: dict[str, float] = Field(
        default_factory=dict,
        description="Extracted or normalized values in [0.0, 1.0] for the theory's required empirical dimensions",
    )
    projected_parameters: dict[str, float] = Field(
        default_factory=dict,
        description="Estimated latent parameter values in [0.0, 1.0] under this theoretical lens",
    )
    fit_rationale: str = Field(default="", description="Justification for the parameter estimation")


@dataclass(slots=True)
class TheoryLaw:
    """Represents a core law or constraint belonging to M.

    Parameters
    ----------
    law_id : str
        Unique identifier for the law.
    description : str
        Human-readable description of the law or axiom.
    evaluator : Callable[[dict[str, Any]], float] | None, optional
        Function taking a dictionary of theoretical parameters and returning
        the deviation or error (>= 0.0) from exact law satisfaction.
    formula_expression : str | None, optional
        Symbolic mathematical constraint expression evaluated safely via AST
        (e.g., 'abs(dopamine - amygdala) * 0.5').
    involved_parameters : list[str], optional
        List of parameter names involved in the law.
    """

    law_id: str
    description: str
    evaluator: Callable[[dict[str, Any]], float] | None = None
    formula_expression: str | None = None
    involved_parameters: list[str] = field(default_factory=list)

    def compute_deviation(self, parameters: dict[str, Any]) -> float:
        """Compute law deviation for a given set of theoretical parameters.

        Parameters
        ----------
        parameters : dict[str, Any]
            Postulated theoretical parameters.

        Returns
        -------
        float
            Non-negative deviation (blur required to satisfy the law).
        """
        if self.evaluator is not None:
            try:
                return float(self.evaluator(parameters))
            except Exception:
                return 1.0

        if self.formula_expression:
            from episteme_pipeline.post_processing.theoretical_enrichment.solvers import (
                evaluate_formula_safely,
            )
            return evaluate_formula_safely(self.formula_expression, parameters)

        return 0.0


@dataclass(slots=True)
class TheoryElementDefinition:
    """Formal definition of a structuralist Theory-Element T = <K, I>.

    Parameters
    ----------
    theory_id : str
        Unique identifier for the theory (e.g. 'neurology', 'psychoanalysis').
    name : str
        Human-readable name of the theory.
    required_dimensions : list[str]
        Empirical measurement dimensions forming the non-theoretical base (M_pp).
    parameter_names : list[str]
        Theoretical parameters in the potential model class (M_p) postulated by T.
    laws : list[TheoryLaw]
        Core laws (M) that valid models must satisfy.
    max_admissible_blur : float, optional
        Upper bound for admissible blurs (A), by default 1.0.
    claimant_hypothesis_ids : list[str], optional
        IDs of TheoreticalHypothesis nodes explicitly associated with this theory.
    """

    theory_id: str
    name: str
    required_dimensions: list[str] = field(default_factory=list)
    parameter_names: list[str] = field(default_factory=list)
    laws: list[TheoryLaw] = field(default_factory=list)
    max_admissible_blur: float = 1.0
    claimant_hypothesis_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EmpiricalCluster:
    """A cluster of empirical observation units forming an Intended Application (I).

    Parameters
    ----------
    cluster_id : str
        Unique identifier for the cluster.
    observations : list[TheoryAtom]
        ObservationUnit and EmpiricalStatement nodes belonging to this cluster.
    claimant_theory_ids : list[str]
        Identified Theory-Elements that claim this cluster as an intended application.
    relations : list[TheoryRelation]
        Internal and outgoing relations connected to the cluster nodes.
    """

    cluster_id: str
    observations: list[TheoryAtom] = field(default_factory=list)
    claimant_theory_ids: list[str] = field(default_factory=list)
    relations: list[TheoryRelation] = field(default_factory=list)

    @property
    def available_dimensions(self) -> set[str]:
        """Return all empirical measurement dimensions present in the cluster.

        Returns
        -------
        set[str]
            Distinct dimension names found across observation nodes.
        """
        dims = set()
        for obs in self.observations:
            for m in obs.measurements:
                dims.add(m.dimension.lower())
        return dims


class TheoryRegistry:
    """Registry holding active Theory-Element definitions.

    Parameters
    ----------
    seed_theories : list[TheoryElementDefinition] | None, optional
        Initial list of theory elements to populate the registry with.
    """

    def __init__(
        self, seed_theories: list[TheoryElementDefinition] | None = None
    ) -> None:
        self._theories: dict[str, TheoryElementDefinition] = {}
        if seed_theories:
            for theory in seed_theories:
                self.register(theory)

    def register(self, theory: TheoryElementDefinition) -> None:
        """Register a new Theory-Element definition.

        Parameters
        ----------
        theory : TheoryElementDefinition
            Theory-element specification to register.
        """
        self._theories[theory.theory_id] = theory

    def register_induced_theories(
        self, induced: list[InducedTheoryElement]
    ) -> list[TheoryElementDefinition]:
        """Convert and register dynamically induced Theory-Elements.

        Parameters
        ----------
        induced : list[InducedTheoryElement]
            List of induced theory elements from LLM induction.

        Returns
        -------
        list[TheoryElementDefinition]
            The instantiated and registered TheoryElementDefinition objects.
        """
        registered: list[TheoryElementDefinition] = []
        for item in induced:
            laws = [
                TheoryLaw(
                    law_id=law.law_id,
                    description=law.description,
                    formula_expression=law.formula_expression,
                    involved_parameters=law.involved_parameters,
                )
                for law in item.laws
            ]
            theory_def = TheoryElementDefinition(
                theory_id=item.theory_id,
                name=item.name,
                required_dimensions=item.required_dimensions,
                parameter_names=item.parameter_names,
                laws=laws,
                max_admissible_blur=item.max_admissible_blur,
                claimant_hypothesis_ids=item.claimant_hypothesis_ids,
            )
            self.register(theory_def)
            registered.append(theory_def)
        return registered

    def get(self, theory_id: str) -> TheoryElementDefinition | None:
        """Retrieve a registered Theory-Element by id.

        Parameters
        ----------
        theory_id : str
            Identifier of the theory.

        Returns
        -------
        TheoryElementDefinition | None
            The registered theory definition, or None if not found.
        """
        return self._theories.get(theory_id)

    def all_theories(self) -> list[TheoryElementDefinition]:
        """Return all registered theory definitions.

        Returns
        -------
        list[TheoryElementDefinition]
            List of registered theory definitions.
        """
        return list(self._theories.values())

    def match_claimants(self, cluster: EmpiricalCluster) -> list[str]:
        """Identify which registered theories claim an empirical cluster.

        A theory claims a cluster if:
        1. Any of the theory's required dimensions are present in the cluster measurements, OR
        2. Any observation unit text mentions the theory keywords or concepts, OR
        3. Any cluster node is registered as a claimant hypothesis ID for the theory.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster.

        Returns
        -------
        list[str]
            List of matching theory_id strings.
        """
        claimants: list[str] = []
        cluster_dims = cluster.available_dimensions
        cluster_texts = " ".join(obs.text.lower() for obs in cluster.observations)
        cluster_node_ids = {obs.id for obs in cluster.observations}

        for tid, theory in self._theories.items():
            req_set = {d.lower() for d in theory.required_dimensions}
            if req_set and not req_set.isdisjoint(cluster_dims):
                claimants.append(tid)
                continue
            if tid in cluster_texts or theory.name.lower() in cluster_texts:
                claimants.append(tid)
                continue
            if set(theory.claimant_hypothesis_ids).intersection(cluster_node_ids):
                claimants.append(tid)
                continue

        return claimants
