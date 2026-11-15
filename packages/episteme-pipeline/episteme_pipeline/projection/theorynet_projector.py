"""TheoryNet projection — constructs the core epistemological formalism from artifacts.

Projects Phase 4 artifact outputs into the unified Theory Graph (TheoryNet) formalism
and executes iterative Quantitative Bipolar Argumentation Framework (QBAF) gradual semantics
with decoupled calibrated weights.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Literal

from epistemetrics.core.models import RelationType, TheoryEdge, TheoryNode
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
  'MATCH (n:TheoryAtom) RETURN id(n) AS id, n.modal_prior AS base_score',
  'MATCH (s:TheoryAtom)-[r:THEORY_RELATION]->(t:TheoryAtom)
   WHERE r.perception_stance_prob >= {p_val} AND r.calibrated_confidence >= {c_val}
   RETURN id(s) AS source, id(t) AS target,
          r.inferential_warrant AS weight,
          type(r) AS relation_type'
)"""
    return f"""CALL gds.graph.project.cypher(
  '{graph_name}',
  'MATCH (n:TheoryAtom) RETURN id(n) AS id, n.modal_prior AS base_score',
  'MATCH (s:TheoryAtom)-[r:THEORY_RELATION]->(t:TheoryAtom)
   RETURN id(s) AS source, id(t) AS target,
          r.inferential_warrant AS inferential_warrant,
          r.perception_stance_prob AS perception_stance_prob,
          r.calibrated_confidence AS calibrated_confidence,
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
    use_continuous : bool, default True
        Whether to use the continuous WeightedQuadraticEnergySolver (closed-form DAG
        and adaptive RK45/Radau ODE integration) when semantics_model is 'quadratic'.
    perspective : str or None, optional
        Optional epistemic perspective filter ('author', agent name, or None).
    isolate_suppositional : bool, default True
        Whether suppositional/Reductio nodes are isolated from contributing positive prior.
    isolate_attributed : bool, default True
        Whether attributed opponent summaries are isolated from directly inflating
        asserted authorial claims.
    t_norm : Literal["product", "godel"], default "product"
        Conjunctive t-norm operator applied across multi-premise inferences in QBAF
        solvers (``"product"`` or ``"godel"``).
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
        use_continuous: bool = True,
        perspective: str | None = None,
        isolate_suppositional: bool = True,
        isolate_attributed: bool = True,
        t_norm: Literal["product", "godel"] = "product",
    ) -> None:
        self.schema = schema or SchemaConfig()
        self.modal_resolver = modal_resolver or StructuralistModalResolver()
        self.admissibility_threshold = admissibility_threshold
        self.admissibility_mode = admissibility_mode
        self.tau_p = tau_p if tau_p > 0.0 else (max(0.0, admissibility_threshold))
        self.tau_c = tau_c if tau_c > 0.0 else (max(0.0, admissibility_threshold))
        self.prune_inadmissible = prune_inadmissible
        self.iterations = iterations
        self.tolerance = tolerance
        self.semantics_model = (
            semantics_model.value
            if isinstance(semantics_model, GradualSemanticsModel)
            else str(semantics_model)
        )
        self.use_continuous = bool(
            use_continuous
            and self.semantics_model == GradualSemanticsModel.QUADRATIC.value
        )
        self.perspective = perspective
        self.isolate_suppositional = isolate_suppositional
        self.isolate_attributed = isolate_attributed
        self.t_norm: Literal["product", "godel"] = t_norm
        self.solver = solver or QBAFGradualSemanticsSolver(
            semantics_model=self.semantics_model,
            max_iterations=iterations,
            tolerance=tolerance,
            admissibility_threshold=admissibility_threshold,
            prune_inadmissible=prune_inadmissible,
            use_continuous=self.use_continuous,
            perspective=perspective,
            isolate_suppositional=isolate_suppositional,
            isolate_attributed=isolate_attributed,
            t_norm=self.t_norm,
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for run cache invalidation.

        Returns
        -------
        dict of str to Any
            Projector configuration and dependency fingerprints.
        """
        from episteme_pipeline.protocols.fingerprint import Fingerprintable

        return {
            "class": self.__class__.__name__,
            "admissibility_threshold": self.admissibility_threshold,
            "admissibility_mode": self.admissibility_mode,
            "tau_p": self.tau_p,
            "tau_c": self.tau_c,
            "prune_inadmissible": self.prune_inadmissible,
            "iterations": self.iterations,
            "tolerance": self.tolerance,
            "semantics_model": self.semantics_model,
            "use_continuous": self.use_continuous,
            "perspective": self.perspective,
            "isolate_suppositional": self.isolate_suppositional,
            "isolate_attributed": self.isolate_attributed,
            "t_norm": self.t_norm,
            "modal_resolver": (
                self.modal_resolver.fingerprint()
                if isinstance(self.modal_resolver, Fingerprintable)
                else {"class": self.modal_resolver.__class__.__name__}
            ),
        }

    def project(
        self,
        view: Phase4ArtifactsView,
        perspective: str | None = None,
    ) -> TheoryNet:
        """Constructs the full TheoryNet formal model from pipeline artifacts.

        Parameters
        ----------
        view : Phase4ArtifactsView
            Extracted theory atoms and dialectical relations from Phase 4.
        perspective : str or None, optional
            Optional perspective filter overriding ``self.perspective`` for
            perspective-scoped QBAF projection.

        Returns
        -------
        TheoryNet
            Materialized TheoryNet with equilibrium justification plausibilities.
        """
        active_perspective = perspective if perspective is not None else self.perspective
        # Retrieve and filter all theory relations with decoupled weights
        source_relations = (
            view.canonical_theory_relations
            if view.canonical_theory_relations
            else view.theory_relations
        )
        relations: list[TheoryRelation] = []
        for r in source_relations:
            rel = r.model_copy()

            # Apply upstream heuristic warrant mapping if not explicitly defined
            if "inferential_warrant" not in rel.model_fields_set:
                rel.inferential_warrant = derive_relation_warrant(rel)

            p_val = (
                rel.perception_stance_prob
                if rel.perception_stance_prob is not None
                else (rel.confidence if rel.confidence is not None else 1.0)
            )
            c_val = (
                rel.perception_empirical_acc
                if rel.perception_empirical_acc is not None
                else (
                    rel.calibrated_confidence
                    if rel.calibrated_confidence is not None
                    else (rel.confidence if rel.confidence is not None else 1.0)
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
                        rel.edge_tenability = 0.0
                else:
                    rel.active_weight = rel.inferential_warrant
            else:
                # Mode 2: Continuous sigmoidal relaxation with k1 = k2 = 20
                rel.is_admissible = bool(p_val >= self.tau_p and c_val >= self.tau_c)
                diff_p = p_val - self.tau_p
                diff_c = c_val - self.tau_c
                # Prevent overflow in exp
                exp_p = math.exp(-20.0 * max(-30.0, min(30.0, diff_p)))
                exp_c = math.exp(-20.0 * max(-30.0, min(30.0, diff_c)))
                f_soft = (1.0 / (1.0 + exp_p)) * (1.0 / (1.0 + exp_c))
                rel.active_weight = float(rel.inferential_warrant * f_soft)

            rel.weight = self.compute_relation_weight(rel)
            relations.append(rel)

        # Retrieve all theory atoms (empirical base and theoretical antecedents)
        source_atoms = (
            view.canonical_theory_atoms
            if view.canonical_theory_atoms
            else view.theory_atoms
        )
        atoms: list[TheoryAtom] = []
        for c in source_atoms:
            atom = c.model_copy()
            if "modal_prior" not in atom.model_fields_set and atom.resolver_type is None:
                atom.modal_prior = self.modal_resolver.resolve_modality_sync(atom)
            atoms.append(atom)

        # Execute Gradual Semantics Convergence via sovereign epistemetrics solver
        # Single source of truth: solver handles intensional supposition discharge & perspective scoping
        if atoms:
            theory_edges = self._to_theory_edges(relations)
            solver_nodes = self._to_solver_nodes(atoms)
            solver_res = self.solver.solve(
                nodes=solver_nodes,
                edges=theory_edges,
                normalization_mode=WeightNormalizationMode.CALIBRATED_MODAL,
                perspective=active_perspective,
                isolate_suppositional=self.isolate_suppositional,
                isolate_attributed=self.isolate_attributed,
            )
            for atom in atoms:
                if atom.id in solver_res.degrees:
                    atom.equilibrium_strength = solver_res.degrees[atom.id]
                else:
                    atom.equilibrium_strength = self.compute_weight(
                        atom, perspective=active_perspective
                    )
                if solver_res.volatility_index and atom.id in solver_res.volatility_index:
                    atom.controversy_volatility = solver_res.volatility_index[atom.id]

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
            ts_edge = (
                float(rel.edge_tenability)
                if rel.edge_tenability is not None
                else 1.0
            )
            if not rel.is_admissible:
                solver_eff_weight = 0.0
            elif self.admissibility_mode == "soft":
                solver_eff_weight = float(rel.active_weight * ts_edge)
            else:
                p_factor = (
                    float(rel.perception_stance_prob)
                    if rel.perception_stance_prob is not None
                    else 1.0
                )
                unscaled_base = float(rel.inferential_warrant * p_factor)
                solver_eff_weight = float(unscaled_base * ts_edge)
            theory_edges.append(
                TheoryEdge(
                    source=rel.source_id,
                    target=rel.target_id,
                    relation_type=RelationType.from_str(rel.relation_type),
                    confidence=rel.confidence if rel.confidence is not None else 1.0,
                    weight=rel.weight if rel.weight is not None else 1.0,
                    polarity=pol,
                    id=rel.relation_id,
                    premise_ids=rel.premise_ids,
                    undercuts_relation_id=rel.undercuts_relation_id,
                    inferential_force=rel.inferential_warrant,
                    stance_probability=rel.perception_stance_prob,
                    model_confidence=rel.calibrated_confidence,
                    empirical_accuracy=rel.perception_empirical_acc,
                    active_weight=solver_eff_weight,
                    effective_weight=solver_eff_weight,
                )
            )
        return theory_edges

    def _to_solver_nodes(
        self,
        atoms: list[TheoryAtom],
    ) -> list[TheoryNode]:
        """Convert theoretical atoms into strongly-typed :class:`TheoryNode` inputs.

        Preserves each atom's intrinsic tenability-modulated prior
        (:math:`M(\\phi) \\cdot TS_{\\text{local}}(\\phi)`) alongside ``intensional_mode``
        and ``attributed_to`` so :class:`QBAFGradualSemanticsSolver` remains the
        single source of truth for perspective and supposition (*Reductio*) scoping.

        Parameters
        ----------
        atoms : list of TheoryAtom
            Theoretical atoms with base scores, local tenability, and intensional scope.

        Returns
        -------
        list of TheoryNode
            Typed solver nodes carrying intrinsic ``base_score``, ``intensional_mode``,
            and ``attributed_to``.
        """
        return [
            TheoryNode(
                id=atom.id,
                name=atom.id,
                base_score=atom.effective_base_prior(
                    include_suppositional=True,
                    perspective="all",
                ),
                modal_strength=atom.modal_prior if atom.modal_prior is not None else 0.6,
                intensional_mode=atom.intensional_mode,
                attributed_to=atom.attributed_to,
                description=atom.text,
                provenance=[atom.source_chunk_id] if atom.source_chunk_id else [],
            )
            for atom in atoms
        ]

    def _to_node_priors(self, atoms: list[TheoryAtom]) -> dict[str, float]:
        """Extract tenability-modulated node prior plausibility mappings from theoretical atoms.

        Parameters
        ----------
        atoms : list of TheoryAtom
            Theoretical atoms with base scores and optional local tenability.

        Returns
        -------
        dict of str to float
            Mapping from atom identifier to tenability-modulated prior :math:`\\tilde{\\tau}_0(a)`.
        """
        return {
            atom.id: self.compute_weight(atom)
            for atom in atoms
        }

    def compute_weight(
        self,
        atom: TheoryAtom,
        perspective: str | None = None,
    ) -> float:
        """Derive tenability-modulated prior plausibility weight :math:`\\tilde{\\tau}_0(a)` for a theoretical atom.

        .. math::
            \\tilde{\\tau}_0(a) = \\tau_0(a) \\cdot TS_{\\text{local}}(a)

        Applies intensional scoping so suppositional (*Reductio*) and off-perspective
        atoms return ``0.0`` when isolated.

        Parameters
        ----------
        atom : TheoryAtom
            Target atom.
        perspective : str or None, optional
            Optional perspective override; falls back to ``self.perspective``.

        Returns
        -------
        float
            Assigned prior plausibility in ``[0.0, 1.0]``.
        """
        active_perspective = perspective if perspective is not None else self.perspective
        return atom.effective_base_prior(
            include_suppositional=not self.isolate_suppositional,
            perspective=active_perspective,
        )

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
        elif rel.perception_stance_prob is not None:
            base = rel.inferential_warrant * rel.perception_stance_prob
        elif rel.weight is not None:
            base = abs(rel.weight)
        else:
            base = rel.inferential_warrant

        polarity = self.schema.relation_polarities.get(rel.relation_type, 0)
        return float(base * polarity)
