"""TheoryNet projection — constructs the core epistemological formalism from artifacts.

Projects Phase 4 artifact outputs into the unified Theory Graph (TheoryNet) formalism
and executes iterative Quantitative Bipolar Argumentation Framework (QBAF) gradual semantics
with decoupled calibrated weights.
"""

from __future__ import annotations

import logging
import math
from typing import Literal

from epistemetrics.core.models import RelationType, TheoryEdge
from epistemetrics.epistemic.qbaf import (
    GradualSemanticsModel,
    QBAFGradualSemanticsSolver,
    WeightNormalizationMode,
)
from episteme_pipeline.artifacts.execution import Phase4ArtifactsView
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryNet, TheoryRelation
from episteme_pipeline.decision.modal_resolver import StructuralistModalResolver
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


def derive_atom_modality(atom: TheoryAtom) -> float:
    """Derive deterministic authorial propositional modal strength from atom classifications.

    Grounding:
    - Toulmin (1958): Modal Qualifier Q on scientific propositions.
    - Schurz (2014): Structuralist Scope Types (Allsatz, Existenzsatz) and Epistemic Status.

    Parameters
    ----------
    atom : TheoryAtom
        Target theoretical atom.

    Returns
    -------
    float
        Deterministic modality score M(phi) in [0.0, 1.0].
    """
    return StructuralistModalResolver().resolve_modality_sync(atom)


def derive_relation_warrant(rel: TheoryRelation) -> float:
    """Derive deterministic Toulminian inferential warrant validity from relation types.

    Parameters
    ----------
    rel : TheoryRelation
        Target dialectical relation.

    Returns
    -------
    float
        Inferential warrant force I_(j->i) in [0.0, 1.0].
    """
    rel_type = (rel.relation_type or "").upper().replace(" ", "_").replace("-", "_")

    if any(k in rel_type for k in ("ENTAIL", "DEDUCE", "IMPLY")):
        return 1.00
    if any(k in rel_type for k in ("CONTRADICT", "REFUTE", "REBUT")):
        return 1.00
    if any(k in rel_type for k in ("SUPPORT", "COHERE")):
        return 0.75
    if any(k in rel_type for k in ("ATTACK", "UNDERMINE")):
        return 0.75
    if any(k in rel_type for k in ("UNDERCUT", "CRITICIZE")):
        return 0.60
    if any(k in rel_type for k in ("ANALOGY", "EXEMPLIF")):
        return 0.40
    return 0.75


def get_cypher_projection_query(
    graph_name: str,
    admissibility_mode: Literal["hard", "soft"] = "hard",
    tau_p: float | str = "$tau_p",
    tau_c: float | str = "$tau_c",
) -> str:
    """Generate Cypher projection query template for Neo4j GDS based on admissibility mode.

    Parameters
    ----------
    graph_name : str
        In-memory GDS projection catalog name.
    admissibility_mode : Literal["hard", "soft"], default "hard"
        Bivariate gating mode (hard pruning vs candidate attribute passthrough).
    tau_p : float | str, default "$tau_p"
        Perception stance probability threshold or Cypher parameter.
    tau_c : float | str, default "$tau_c"
        Perception calibration confidence threshold or Cypher parameter.

    Returns
    -------
    str
        Cypher GDS projection statement.
    """
    p_val = str(tau_p)
    c_val = str(tau_c)
    if admissibility_mode == "hard":
        return f"""CALL gds.graph.project.cypher(
  '{graph_name}',
  'MATCH (n:TheoryAtom) RETURN id(n) AS id, n.modal_strength AS base_score',
  'MATCH (s:TheoryAtom)-[r:THEORY_RELATION]->(t:TheoryAtom)
   WHERE r.stance_probability >= {p_val} AND r.model_confidence >= {c_val}
   RETURN id(s) AS source, id(t) AS target,
          r.inferential_force AS weight,
          type(r) AS relation_type'
)"""
    return f"""CALL gds.graph.project.cypher(
  '{graph_name}',
  'MATCH (n:TheoryAtom) RETURN id(n) AS id, n.modal_strength AS base_score',
  'MATCH (s:TheoryAtom)-[r:THEORY_RELATION]->(t:TheoryAtom)
   RETURN id(s) AS source, id(t) AS target,
          r.inferential_force AS inferential_force,
          r.stance_probability AS stance_probability,
          r.model_confidence AS model_confidence,
          type(r) AS relation_type'
)"""


class TheoryNetProjector:
    """Project Phase 4 artifacts into a formal TheoryNet structure.

    Evaluates decoupled mathematical weights W_ji = I_(j->i) * F(r),
    enforces bivariate admissibility gating (hard pruning or continuous sigmoidal relaxation),
    and executes gradual semantics equilibrium convergence via QBAFGradualSemanticsSolver.

    Parameters
    ----------
    schema : SchemaConfig | None, optional
        Pipeline schema defining relation polarities and component partitions.
    solver : QBAFGradualSemanticsSolver | None, optional
        Injected gradual semantics solver instance. If None, initialized from parameters.
    admissibility_threshold : float, default 0.0
        Legacy calibrated empirical accuracy threshold.
    admissibility_mode : Literal["hard", "soft"], default "hard"
        Gating strategy (Mode 1 hard database pruning vs. Mode 2 continuous sigmoidal relaxation).
    tau_p : float, default 0.0
        Perception stance probability threshold.
    tau_c : float, default 0.0
        Perception calibration confidence threshold.
    prune_inadmissible : bool, default False
        Whether to drop inadmissible relations completely instead of assigning zero active weight.
    iterations : int, default 20
        Maximum iteration cap for gradual semantics convergence.
    tolerance : float, default 1e-4
        Numerical convergence threshold for equilibrium justification degrees.
    semantics_model : GradualSemanticsModel | str, default "quadratic"
        Gradual semantics formulation ('quadratic', 'euler', 'categorizer', or 'linear').
    modal_resolver : ModalStrengthResolver | None, optional
        Injected authorial modal strength resolver. If None, defaults to StructuralistModalResolver.
    """

    def __init__(
        self,
        schema: SchemaConfig | None = None,
        solver: QBAFGradualSemanticsSolver | None = None,
        admissibility_threshold: float = 0.0,
        admissibility_mode: Literal["hard", "soft"] = "hard",
        tau_p: float = 0.0,
        tau_c: float = 0.0,
        prune_inadmissible: bool = False,
        iterations: int = 20,
        tolerance: float = 1e-4,
        semantics_model: GradualSemanticsModel | str = GradualSemanticsModel.QUADRATIC,
        modal_resolver: ModalStrengthResolver | None = None,
    ) -> None:
        self.schema = schema or SchemaConfig()
        self.modal_resolver = modal_resolver or StructuralistModalResolver()
        self.admissibility_threshold = admissibility_threshold
        self.admissibility_mode = admissibility_mode
        self.tau_p = tau_p if tau_p > 0.0 else (admissibility_threshold if admissibility_threshold > 0.0 else 0.0)
        self.tau_c = tau_c if tau_c > 0.0 else (admissibility_threshold if admissibility_threshold > 0.0 else 0.0)
        self.prune_inadmissible = prune_inadmissible
        self.iterations = iterations
        self.tolerance = tolerance
        self.semantics_model = (
            semantics_model.value
            if isinstance(semantics_model, GradualSemanticsModel)
            else str(semantics_model)
        )
        self.solver = solver or QBAFGradualSemanticsSolver(
            semantics_model=self.semantics_model,
            max_iterations=iterations,
            tolerance=tolerance,
            admissibility_threshold=admissibility_threshold,
            prune_inadmissible=prune_inadmissible,
        )

    def project(
        self,
        view: Phase4ArtifactsView,
    ) -> TheoryNet:
        """Constructs the full TheoryNet formal model from pipeline artifacts.

        Parameters
        ----------
        view : Phase4ArtifactsView
            Extracted theory atoms and dialectical relations from Phase 4.

        Returns
        -------
        TheoryNet
            Materialized TheoryNet with equilibrium justification plausibilities.
        """
        # Retrieve and filter all theory relations with decoupled weights
        relations: list[TheoryRelation] = []
        for r in view.theory_relations:
            rel = r.model_copy()

            # Apply upstream heuristic warrant mapping if not explicitly defined
            if "inferential_force" not in rel.model_fields_set and "modal_strength" not in rel.model_fields_set:
                rel.inferential_force = derive_relation_warrant(rel)

            p_val = (
                rel.stance_probability
                if rel.stance_probability is not None
                else (
                    rel.class_probability
                    if rel.class_probability is not None
                    else (rel.confidence if rel.confidence is not None else 1.0)
                )
            )
            c_val = (
                rel.model_confidence
                if rel.model_confidence is not None
                else (
                    rel.calibrated_confidence
                    if rel.calibrated_confidence is not None
                    else (
                        rel.empirical_accuracy
                        if rel.empirical_accuracy is not None
                        else (rel.confidence if rel.confidence is not None else 1.0)
                    )
                )
            )

            # Apply bivariate admissibility gating
            if self.admissibility_mode == "hard":
                is_admissible = (self.tau_p <= 0.0 or p_val >= self.tau_p) and (
                    self.tau_c <= 0.0 or c_val >= self.tau_c
                )
                rel.is_admissible = is_admissible
                if not is_admissible:
                    if self.prune_inadmissible:
                        logger.debug(
                            "Pruned relation %s->%s: (P=%.3f < %.3f or C=%.3f < %.3f)",
                            rel.source_id,
                            rel.target_id,
                            p_val,
                            self.tau_p,
                            c_val,
                            self.tau_c,
                        )
                        continue
                    else:
                        rel.active_weight = 0.0
                        rel.tenability = 0.0
                else:
                    rel.active_weight = rel.inferential_force
            else:
                # Mode 2: Continuous sigmoidal relaxation with k1 = k2 = 20
                rel.is_admissible = bool(p_val >= self.tau_p and c_val >= self.tau_c)
                diff_p = p_val - self.tau_p
                diff_c = c_val - self.tau_c
                # Prevent overflow in exp
                exp_p = math.exp(-20.0 * max(-30.0, min(30.0, diff_p)))
                exp_c = math.exp(-20.0 * max(-30.0, min(30.0, diff_c)))
                f_soft = (1.0 / (1.0 + exp_p)) * (1.0 / (1.0 + exp_c))
                rel.active_weight = float(rel.inferential_force * f_soft)

            rel.weight = self.compute_relation_weight(rel)
            relations.append(rel)

        # Retrieve all theory atoms (empirical base and theoretical antecedents)
        atoms: list[TheoryAtom] = []
        for c in view.theory_atoms:
            atom = c.model_copy()
            if "modal_strength" not in atom.model_fields_set and "base_score" not in atom.model_fields_set:
                atom.modal_strength = self.modal_resolver.resolve_modality_sync(atom)
                atom.base_score = atom.modal_strength
            atom.plausibility = self.compute_weight(atom)
            atoms.append(atom)

        # Execute Gradual Semantics Convergence via sovereign epistemetrics solver
        if atoms and relations:
            theory_edges = self._to_theory_edges(relations)
            node_priors = self._to_node_priors(atoms)
            solver_res = self.solver.solve(
                nodes=node_priors,
                edges=theory_edges,
                normalization_mode=WeightNormalizationMode.CALIBRATED_MODAL,
            )
            for atom in atoms:
                if atom.id in solver_res.degrees:
                    atom.plausibility = solver_res.degrees[atom.id]

        return TheoryNet(
            atoms=atoms,
            relations=relations,
        )

    def _to_theory_edges(self, relations: list[TheoryRelation]) -> list[TheoryEdge]:
        """Convert pipeline TheoryRelation models to epistemetrics TheoryEdge models.

        Parameters
        ----------
        relations : list of TheoryRelation
            Pipeline relations to convert.

        Returns
        -------
        list of TheoryEdge
            Strongly-typed epistemetrics edge models with resolved polarities and weights.
        """
        theory_edges: list[TheoryEdge] = []
        for rel in relations:
            pol = self.schema.relation_polarities.get(rel.relation_type, 0)
            if pol == 0:
                pol = (
                    -1
                    if any(
                        k in (rel.relation_type or "").upper()
                        for k in ("ATTACK", "REFUTE", "CONTRADICT", "UNDERCUT", "INHIBIT", "REBUT")
                    )
                    else 1
                )
            theory_edges.append(
                TheoryEdge(
                    source=rel.source_id,
                    target=rel.target_id,
                    relation_type=RelationType.from_str(rel.relation_type),
                    confidence=rel.confidence if rel.confidence is not None else 1.0,
                    weight=rel.weight if rel.weight is not None else 1.0,
                    polarity=pol,
                    inferential_force=rel.inferential_force,
                    stance_probability=rel.stance_probability,
                    model_confidence=rel.model_confidence,
                    empirical_accuracy=rel.empirical_accuracy,
                    active_weight=rel.active_weight,
                    effective_weight=rel.effective_weight,
                )
            )
        return theory_edges

    def _to_node_priors(self, atoms: list[TheoryAtom]) -> dict[str, float]:
        """Extract node prior plausibility mappings from theoretical atoms.

        Parameters
        ----------
        atoms : list of TheoryAtom
            Theoretical atoms with base scores or computed plausibility.

        Returns
        -------
        dict of str to float
            Mapping from atom identifier to prior plausibility score.
        """
        return {
            atom.id: atom.plausibility if atom.plausibility is not None else atom.base_score
            for atom in atoms
        }

    def compute_weight(self, atom: TheoryAtom) -> float:
        """Derive prior plausibility weight for a theoretical atom.

        Parameters
        ----------
        atom : TheoryAtom
            Target atom.

        Returns
        -------
        float
            Assigned prior plausibility.
        """
        if atom.base_score is not None:
            return atom.base_score
        if atom.modal_strength is not None:
            return atom.modal_strength
        if atom.plausibility is not None:
            return atom.plausibility
        return atom.confidence if atom.confidence is not None else 0.60

    def compute_relation_weight(self, rel: TheoryRelation) -> float:
        """Compute signed directional relation weight.

        Multiplies the active mathematical magnitude by the relational polarity
        (+1 for support, -1 for attack, 0 for neutral).

        Parameters
        ----------
        rel : TheoryRelation
            Target dialectical relation.

        Returns
        -------
        float
            Signed relation weight.
        """
        if "active_weight" in rel.model_fields_set and rel.active_weight is not None:
            base = rel.active_weight
        elif rel.effective_weight is not None:
            base = rel.effective_weight
        elif rel.class_probability is not None:
            base = rel.modal_strength * rel.class_probability
        elif rel.weight is not None:
            base = abs(rel.weight)
        else:
            base = rel.inferential_force

        polarity = self.schema.relation_polarities.get(rel.relation_type, 0)
        return float(base * polarity)
