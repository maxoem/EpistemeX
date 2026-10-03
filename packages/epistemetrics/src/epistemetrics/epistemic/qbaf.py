"""Quantitative Bipolar Argumentation Framework (QBAF) Gradual Semantics Solvers.

Operationalizes dialectical equilibrium convergence over argument graphs
with decoupled calibrated weights:

.. math::
    w = M(\\text{modal\\_strength}) \\times P(\\text{stance})

Supports multiple gradual semantics update functions, empirical accuracy admissibility gating, and
comparative evaluation between uncalibrated binary weights vs. calibrated modal weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Literal, Mapping, Sequence
import networkx as nx
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.integrate import solve_ivp

from epistemetrics.core.models import RelationType, TheoryEdge, TheoryNode
from epistemetrics.graph.theory_graph import TheoryGraph


@dataclass(slots=True, frozen=True)
class _AdmissibleEdge:
    """Internal normalized representation for dialectical edges after admissibility gating."""

    source: str
    target: str
    polarity: int
    weight: float


class GradualSemanticsModel(str, Enum):
    """Gradual semantics convergence update model formulation.

    Attributes
    ----------
    QUADRATIC : str
        Bounded quadratic energy attenuation model balancing support and attack.
    EULER : str
        Sigmoidal exponential energy model.
    CATEGORIZER : str
        H-categorizer gradual semantics model.
    LINEAR : str
        Linear bounded difference aggregation model.
    """

    QUADRATIC = "quadratic"
    EULER = "euler"
    CATEGORIZER = "categorizer"
    LINEAR = "linear"


class WeightNormalizationMode(str, Enum):
    """Weight normalization mode for QBAF iterative solving.

    Attributes
    ----------
    CALIBRATED_MODAL : str
        Continuous edge weights decoupled by modal strength and empirical accuracy:
        :math:`w = M(\\text{modal\\_strength}) \\times P(\\text{stance})`.
    UNWEIGHTED_BINARY : str
        Standard uncalibrated binary edge weights (:math:`w = 1.0` for all active edges).
    """

    CALIBRATED_MODAL = "calibrated_modal"
    UNWEIGHTED_BINARY = "unweighted_binary"


class QBAFSolverResult(BaseModel, Mapping[str, float]):
    """Equilibrium justification degrees and convergence telemetry for a QBAF.

    Provides a dictionary-like interface mapping node identifiers to their
    converged justification degrees :math:`\\tau(a) \\in [0, 1]`.

    Parameters
    ----------
    degrees : dict[str, float]
        Mapping from node identifier to equilibrium justification degree.
    iterations : int
        Number of iterations executed until convergence or termination cap.
    converged : bool
        Whether the iterative process reached delta < tolerance.
    final_delta : float
        Maximum absolute change across all nodes in the final iteration.
    normalization_mode : WeightNormalizationMode
        Active edge weighting normalization mode.
    semantics_model : GradualSemanticsModel
        Gradual semantics update model used.
    support_sums : dict[str, float]
        Total weighted incoming support aggregated per node.
    attack_sums : dict[str, float]
        Total weighted incoming attack aggregated per node.
    total_weight_of_evidence : dict[str, float]
        Gross epistemic weight of evidence aggregated per node (E_total = E_supp + E_att).
    volatility_index : dict[str, float]
        Keynes-Gärdenfors epistemic volatility index per node.
    admissibility_pruned_count : int, default 0
        Number of edges pruned due to falling below the admissibility threshold.
    """

    model_config = ConfigDict(frozen=True)

    degrees: dict[str, float] = Field(
        default_factory=dict,
        description="Converged justification degrees tau(a) per node.",
    )
    iterations: int = Field(
        ...,
        description="Total iteration count executed.",
    )
    converged: bool = Field(
        ...,
        description="Whether solver reached numerical convergence tolerance.",
    )
    final_delta: float = Field(
        ...,
        description="Maximum absolute degree shift in final iteration.",
    )
    normalization_mode: WeightNormalizationMode = Field(
        ...,
        description="Applied weight normalization mode.",
    )
    semantics_model: GradualSemanticsModel = Field(
        ...,
        description="Underlying gradual semantics mathematical formulation.",
    )
    support_sums: dict[str, float] = Field(
        default_factory=dict,
        description="Final aggregated incoming support energy per node.",
    )
    attack_sums: dict[str, float] = Field(
        default_factory=dict,
        description="Final aggregated incoming attack energy per node.",
    )
    total_weight_of_evidence: dict[str, float] = Field(
        default_factory=dict,
        description="Orthogonal gross epistemic weight E_total = E_supp + E_att per node.",
    )
    volatility_index: dict[str, float] = Field(
        default_factory=dict,
        description="Keynes-Gärdenfors epistemic volatility index V per node.",
    )
    admissibility_pruned_count: int = Field(
        default=0,
        description="Count of edges pruned by the empirical accuracy admissibility gate.",
    )

    @property
    def volatility(self) -> dict[str, float]:
        """Return volatility index mapping."""
        return self.volatility_index

    def __getitem__(self, node_id: str) -> float:
        """Retrieve justification degree for a specific node ID."""
        return self.degrees[node_id]

    def __iter__(self) -> Any:
        """Iterate over all node IDs."""
        return iter(self.degrees)

    def __len__(self) -> int:
        """Return total number of evaluated nodes."""
        return len(self.degrees)

    @property
    def mean_degree(self) -> float:
        """Return average justification degree across all nodes."""
        if not self.degrees:
            return 0.0
        return float(np.mean(list(self.degrees.values())))

    @property
    def max_degree(self) -> float:
        """Return maximum justification degree."""
        if not self.degrees:
            return 0.0
        return max(self.degrees.values())

    @property
    def min_degree(self) -> float:
        """Return minimum justification degree."""
        if not self.degrees:
            return 0.0
        return min(self.degrees.values())


class QBAFComparisonResult(BaseModel):
    """Comparative analysis contrasting calibrated modal vs unweighted binary QBAF equilibria.

    Quantifies the mathematical distortion and epistemic drift introduced by
    uncalibrated unit edge weights compared to calibrated System 1 priors.

    Parameters
    ----------
    calibrated_result : QBAFSolverResult
        QBAF result computed under CALIBRATED_MODAL weighting.
    unweighted_result : QBAFSolverResult
        QBAF result computed under UNWEIGHTED_BINARY weighting.
    delta_justifications : dict[str, float]
        Difference tau_calibrated(a) - tau_unweighted(a) for each node.
    mean_absolute_drift : float
        Mean absolute shift across all evaluated arguments.
    max_drift : float
        Maximum absolute drift observed for any individual argument.
    max_drift_node : str | None
        Identifier of the argument undergoing the largest justification drift.
    rank_reversals : int
        Number of argument pairs whose relative priority reversed between modes.
    summary : dict[str, Any]
        Statistical and qualitative summary metrics.
    """

    model_config = ConfigDict(frozen=True)

    calibrated_result: QBAFSolverResult
    unweighted_result: QBAFSolverResult
    delta_justifications: dict[str, float] = Field(default_factory=dict)
    mean_absolute_drift: float = 0.0
    max_drift: float = 0.0
    max_drift_node: str | None = None
    rank_reversals: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class WeightedQuadraticEnergySolver:
    """Adaptive continuous dynamical solver for Quantitative Bipolar Argumentation Frameworks.

    Provides unified Quadratic Energy semantics across all graph topologies:
    - Acyclic graphs (DAGs): Closed-form evaluation in O(|V| + |E|) along topological sort (Proposition 5).
    - Cyclic graphs: Continuous adaptive ODE integration (RK45 / Radau fallback) with early stationary termination.

    Parameters
    ----------
    rtol : float, default 1e-4
        Relative tolerance for adaptive ODE step size control.
    atol : float, default 1e-6
        Absolute tolerance for convergence and root-finding stationary termination.
    t_max : float, default 50.0
        Maximum simulation horizon for continuous ODE relaxation.
    max_step : float, default 0.5
        Maximum allowable integration step size.
    """

    def __init__(
        self,
        rtol: float = 1e-4,
        atol: float = 1e-6,
        t_max: float = 50.0,
        max_step: float = 0.5,
    ) -> None:
        self.rtol = rtol
        self.atol = atol
        self.t_max = t_max
        self.max_step = max_step

    @staticmethod
    def _impact(x: np.ndarray | float) -> np.ndarray | float:
        """Quadratic impact attenuation function h(x) = (max(x, 0)^2) / (1 + max(x, 0)^2)."""
        pos = np.maximum(x, 0.0)
        pos_sq = pos ** 2
        return pos_sq / (1.0 + pos_sq)

    def _derivatives(
        self,
        t: float,
        s: np.ndarray,
        w: np.ndarray,
        g_supp_t: np.ndarray,
        g_att_t: np.ndarray,
    ) -> np.ndarray:
        """Compute ODE time derivative vector s_dot under Quadratic Energy formulation."""
        e = (g_supp_t @ s) - (g_att_t @ s)
        h_pos = self._impact(e)
        h_neg = self._impact(-e)
        return w - s + (1.0 - w) * h_pos - w * h_neg

    def _solve_dag_closed_form(
        self,
        base_scores: np.ndarray,
        g_supp_t: np.ndarray,
        g_att_t: np.ndarray,
        topo_order: list[int],
    ) -> np.ndarray:
        """Evaluate exact equilibrium in closed form along topological order (Proposition 5)."""
        s = base_scores.copy()
        for i in topo_order:
            e_i = float(np.dot(g_supp_t[i], s) - np.dot(g_att_t[i], s))
            h_pos = float(self._impact(e_i))
            h_neg = float(self._impact(-e_i))
            w_i = float(base_scores[i])
            s[i] = w_i + (1.0 - w_i) * h_pos - w_i * h_neg
        return np.clip(s, 0.0, 1.0)

    def solve(
        self,
        base_scores: np.ndarray,
        g_supp: np.ndarray,
        g_att: np.ndarray,
    ) -> tuple[np.ndarray, bool, dict[str, np.ndarray]]:
        """Solve for dialectical equilibrium state over argument network.

        Parameters
        ----------
        base_scores : np.ndarray
            Vector of prior base plausibilities w in [0, 1]^N.
        g_supp : np.ndarray
            N x N adjacency matrix of support relation weights (j -> i at g_supp[j, i]).
        g_att : np.ndarray
            N x N adjacency matrix of attack relation weights (j -> i at g_att[j, i]).

        Returns
        -------
        s_final : np.ndarray
            Converged justification degrees tau* in [0, 1]^N.
        converged : bool
            Whether numerical equilibrium tolerance was attained.
        telemetry : dict[str, np.ndarray]
            Diagnostic matrices: support_energy, attack_energy, total_weight_of_evidence, volatility_index.
        """
        n = len(base_scores)
        if n == 0:
            empty = np.array([], dtype=np.float64)
            return empty, True, {
                "support_energy": empty,
                "attack_energy": empty,
                "total_weight_of_evidence": empty,
                "volatility_index": empty,
            }

        w = np.clip(base_scores, 0.0, 1.0)
        g_supp_t = g_supp.T
        g_att_t = g_att.T

        # Check for directed acyclic graph topology
        adj = (g_supp + g_att) > 0
        g_nx = nx.DiGraph(adj)

        if nx.is_directed_acyclic_graph(g_nx):
            # Fast-path: O(|V| + |E|) closed-form topological evaluation (Proposition 5)
            topo_order = list(nx.topological_sort(g_nx))
            s_final = self._solve_dag_closed_form(w, g_supp_t, g_att_t, topo_order)
            converged = True
        else:
            # Cyclic topology: Adaptive continuous ODE integration
            s0 = w.copy()
            ds0 = self._derivatives(0.0, s0, w, g_supp_t, g_att_t)

            if np.max(np.abs(ds0)) < self.atol:
                s_final = s0
                converged = True
            else:
                event_tol = max(self.atol, 1e-4)

                def stationary_event(
                    t: float,
                    s: np.ndarray,
                    w_arr: np.ndarray,
                    supp_t: np.ndarray,
                    att_t: np.ndarray,
                ) -> float:
                    ds = self._derivatives(t, s, w_arr, supp_t, att_t)
                    return float(np.max(np.abs(ds)) - event_tol)

                stationary_event.terminal = True
                stationary_event.direction = -1

                ode_rtol = min(self.rtol, 1e-5)
                ode_atol = min(self.atol, 1e-7)

                sol = solve_ivp(
                    fun=self._derivatives,
                    t_span=(0.0, self.t_max),
                    y0=s0,
                    args=(w, g_supp_t, g_att_t),
                    method="RK45",
                    rtol=ode_rtol,
                    atol=ode_atol,
                    max_step=self.max_step,
                    events=stationary_event,
                )

                # Fallback to implicit Radau if stiffness or divergence is encountered
                if not sol.success or sol.status < 0:
                    sol = solve_ivp(
                        fun=self._derivatives,
                        t_span=(0.0, self.t_max),
                        y0=s0,
                        args=(w, g_supp_t, g_att_t),
                        method="Radau",
                        rtol=ode_rtol,
                        atol=ode_atol,
                        events=stationary_event,
                    )

                s_final = np.clip(sol.y[:, -1], 0.0, 1.0)
                converged = bool(sol.status >= 0)

        # Compute orthogonal telemetry: Weight of Evidence E_total and Volatility V
        e_supp = g_supp_t @ s_final
        e_att = g_att_t @ s_final
        e_total = e_supp + e_att
        denom = 1.0 + e_total
        safe_denom = np.where(denom > 0, denom, 1.0)
        volatility = (e_total / safe_denom) * (1.0 - 2.0 * np.abs(s_final - 0.5))

        telemetry = {
            "support_energy": e_supp,
            "attack_energy": e_att,
            "total_weight_of_evidence": e_total,
            "volatility_index": volatility,
        }
        return s_final, converged, telemetry


class QBAFGradualSemanticsSolver:
    """Iterative numerical solver for Quantitative Bipolar Argumentation Frameworks.

    Solves for equilibrium justification degrees :math:`\\tau(a)` over arbitrary
    (potentially cyclic and dense) dialectical graphs.

    Parameters
    ----------
    semantics_model : GradualSemanticsModel or str, default GradualSemanticsModel.QUADRATIC
        Gradual semantics aggregation model.
    max_iterations : int, default 50
        Iteration cap preventing infinite loops on oscillating cyclic graphs.
    tolerance : float, default 1e-4
        Convergence delta threshold.
    admissibility_threshold : float, default 0.0
        Calibrated empirical accuracy admissibility gate threshold :math:`\\tau_{\\text{admissibility}}`.
    prune_inadmissible : bool, default True
        Whether edges below the admissibility threshold are pruned entirely.
    admissibility_mode : Literal["hard", "soft"], default "hard"
        Gating strategy: Mode 1 hard pruning vs. Mode 2 continuous sigmoidal relaxation.
    tau_p : float, default 0.0
        Perception stance probability threshold.
    tau_c : float, default 0.0
        Perception calibration confidence threshold.
    use_continuous : bool, default False
        Whether to route solve() to the unified continuous WeightedQuadraticEnergySolver.
    """

    def __init__(
        self,
        semantics_model: GradualSemanticsModel | str = GradualSemanticsModel.QUADRATIC,
        max_iterations: int = 50,
        tolerance: float = 1e-4,
        admissibility_threshold: float = 0.0,
        prune_inadmissible: bool = True,
        admissibility_mode: Literal["hard", "soft"] = "hard",
        tau_p: float = 0.0,
        tau_c: float = 0.0,
        use_continuous: bool = False,
    ) -> None:
        if isinstance(semantics_model, str):
            semantics_model = GradualSemanticsModel(semantics_model.lower())
        self.semantics_model = semantics_model
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.admissibility_threshold = admissibility_threshold
        self.prune_inadmissible = prune_inadmissible
        self.admissibility_mode = admissibility_mode
        self.tau_p = tau_p
        self.tau_c = tau_c
        self.use_continuous = use_continuous

    def solve(
        self,
        nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
        edges: Sequence[Any] | None = None,
        normalization_mode: WeightNormalizationMode
        | str = WeightNormalizationMode.CALIBRATED_MODAL,
        admissibility_mode: Literal["hard", "soft"] | None = None,
        tau_p: float | None = None,
        tau_c: float | None = None,
        continuous: bool | None = None,
    ) -> QBAFSolverResult:
        """Compute equilibrium justification degrees over an argumentation network.

        Parameters
        ----------
        nodes : TheoryGraph or Mapping of str to float or Sequence of TheoryNode/dict/tuple
            Argument nodes with initial prior plausibilities or complete TheoryGraph container.
        edges : Sequence of TheoryEdge, dict, or tuple, optional
            Dialectical edges connecting nodes. Inferred from TheoryGraph if omitted.
        normalization_mode : WeightNormalizationMode or str, default CALIBRATED_MODAL
            Weight calculation mode ('calibrated_modal' or 'unweighted_binary').
        admissibility_mode : Literal["hard", "soft"], optional
            Gating mode ('hard' pruning vs. 'soft' sigmoidal relaxation). Defaults to instance mode.
        tau_p : float, optional
            Stance probability threshold override.
        tau_c : float, optional
            Model confidence threshold override.
        continuous : bool, optional
            Whether to solve using continuous WeightedQuadraticEnergySolver. Defaults to instance setting.

        Returns
        -------
        QBAFSolverResult
            Equilibrium justification states and convergence statistics.
        """
        if continuous is True or (continuous is None and self.use_continuous):
            return self.solve_continuous(
                nodes=nodes,
                edges=edges,
                normalization_mode=normalization_mode,
                admissibility_mode=admissibility_mode,
                tau_p=tau_p,
                tau_c=tau_c,
            )

        if isinstance(normalization_mode, str):
            normalization_mode = WeightNormalizationMode(normalization_mode.lower())

        active_adm_mode = admissibility_mode or self.admissibility_mode
        active_tau_p = tau_p if tau_p is not None else self.tau_p
        active_tau_c = tau_c if tau_c is not None else self.tau_c

        base_tau, admissible_edges, admissibility_pruned = self._prepare_graph_data(
            nodes=nodes,
            edges=edges,
            normalization_mode=normalization_mode,
            active_adm_mode=active_adm_mode,
            active_tau_p=active_tau_p,
            active_tau_c=active_tau_c,
        )

        incoming_edges: dict[str, list[_AdmissibleEdge]] = {nid: [] for nid in base_tau}
        for edge in admissible_edges:
            incoming_edges[edge.target].append(edge)

        # Iterative Gradual Semantics Convergence Loop
        tau_current: dict[str, float] = dict(base_tau)
        final_delta = 0.0
        converged = False
        iteration_count = 0

        support_energy: dict[str, float] = {nid: 0.0 for nid in base_tau}
        attack_energy: dict[str, float] = {nid: 0.0 for nid in base_tau}

        for it in range(self.max_iterations):
            iteration_count = it + 1
            max_delta = 0.0
            tau_next: dict[str, float] = {}

            for nid in base_tau:
                tau_0 = base_tau[nid]
                s_sum = 0.0
                a_sum = 0.0

                for inc in incoming_edges.get(nid, []):
                    src_val = tau_current[inc.source]
                    w = inc.weight
                    pol = inc.polarity

                    if pol > 0:
                        s_sum += src_val * w
                    elif pol < 0:
                        a_sum += src_val * w

                support_energy[nid] = s_sum
                attack_energy[nid] = a_sum

                # Apply gradual semantics update function
                updated_val = self._compute_update(
                    tau_0=tau_0,
                    support=s_sum,
                    attack=a_sum,
                    model=self.semantics_model,
                )

                delta = abs(updated_val - tau_current[nid])
                if delta > max_delta:
                    max_delta = delta

                tau_next[nid] = updated_val

            tau_current = tau_next
            final_delta = max_delta

            if max_delta < self.tolerance:
                converged = True
                break

        # Compute orthogonal telemetry: Weight of Evidence E_total and Volatility V
        total_evidence: dict[str, float] = {}
        volatility: dict[str, float] = {}
        for nid in base_tau:
            e_tot = support_energy[nid] + attack_energy[nid]
            deg = tau_current[nid]
            vol = (e_tot / (1.0 + e_tot)) * (1.0 - 2.0 * abs(deg - 0.5)) if e_tot > 0 else 0.0
            total_evidence[nid] = round(e_tot, 6)
            volatility[nid] = round(vol, 6)

        return QBAFSolverResult(
            degrees={k: round(v, 6) for k, v in tau_current.items()},
            iterations=iteration_count,
            converged=converged,
            final_delta=round(final_delta, 8),
            normalization_mode=normalization_mode,
            semantics_model=self.semantics_model,
            support_sums={k: round(v, 6) for k, v in support_energy.items()},
            attack_sums={k: round(v, 6) for k, v in attack_energy.items()},
            total_weight_of_evidence=total_evidence,
            volatility_index=volatility,
            admissibility_pruned_count=admissibility_pruned,
        )

    def solve_continuous(
        self,
        nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
        edges: Sequence[Any] | None = None,
        normalization_mode: WeightNormalizationMode
        | str = WeightNormalizationMode.CALIBRATED_MODAL,
        admissibility_mode: Literal["hard", "soft"] | None = None,
        tau_p: float | None = None,
        tau_c: float | None = None,
    ) -> QBAFSolverResult:
        """Solve QBAF equilibrium using the unified continuous WeightedQuadraticEnergySolver.

        Evaluates DAG topologies in closed form along a topological sort in O(|V| + |E|)
        (Proposition 5), and cyclic topologies via adaptive ODE integration (RK45 with
        Radau fallback) and root-finding early stationary termination.

        Parameters
        ----------
        nodes : TheoryGraph or Mapping or Sequence
            Argument nodes or TheoryGraph container with base plausibilities.
        edges : Sequence or None, optional
            Argument relations. Inferred from TheoryGraph if omitted.
        normalization_mode : WeightNormalizationMode or str, default CALIBRATED_MODAL
            Weight calculation mode.
        admissibility_mode : Literal["hard", "soft"], optional
            Gating mode override.
        tau_p : float, optional
            Stance probability threshold override.
        tau_c : float, optional
            Model confidence threshold override.

        Returns
        -------
        QBAFSolverResult
            Equilibrium justifications, energy totals, and volatility telemetry.
        """
        if isinstance(normalization_mode, str):
            normalization_mode = WeightNormalizationMode(normalization_mode.lower())

        active_adm_mode = admissibility_mode or self.admissibility_mode
        active_tau_p = tau_p if tau_p is not None else self.tau_p
        active_tau_c = tau_c if tau_c is not None else self.tau_c

        base_tau, admissible_edges, admissibility_pruned = self._prepare_graph_data(
            nodes=nodes,
            edges=edges,
            normalization_mode=normalization_mode,
            active_adm_mode=active_adm_mode,
            active_tau_p=active_tau_p,
            active_tau_c=active_tau_c,
        )

        node_list = list(base_tau.keys())
        node_to_idx = {nid: i for i, nid in enumerate(node_list)}
        n = len(node_list)

        base_scores = np.array([base_tau[nid] for nid in node_list], dtype=np.float64)
        g_supp = np.zeros((n, n), dtype=np.float64)
        g_att = np.zeros((n, n), dtype=np.float64)

        for edge in admissible_edges:
            u = node_to_idx[edge.source]
            v = node_to_idx[edge.target]
            if edge.polarity > 0:
                g_supp[u, v] += edge.weight
            elif edge.polarity < 0:
                g_att[u, v] += edge.weight

        ode_solver = WeightedQuadraticEnergySolver(
            rtol=self.tolerance,
            atol=max(self.tolerance * 0.01, 1e-6),
        )
        s_final, converged, telemetry = ode_solver.solve(base_scores, g_supp, g_att)

        degrees = {nid: round(float(s_final[i]), 6) for i, nid in enumerate(node_list)}
        support_sums = {nid: round(float(telemetry["support_energy"][i]), 6) for i, nid in enumerate(node_list)}
        attack_sums = {nid: round(float(telemetry["attack_energy"][i]), 6) for i, nid in enumerate(node_list)}
        total_evidence = {nid: round(float(telemetry["total_weight_of_evidence"][i]), 6) for i, nid in enumerate(node_list)}
        volatility = {nid: round(float(telemetry["volatility_index"][i]), 6) for i, nid in enumerate(node_list)}

        return QBAFSolverResult(
            degrees=degrees,
            iterations=1,
            converged=converged,
            final_delta=0.0,
            normalization_mode=normalization_mode,
            semantics_model=GradualSemanticsModel.QUADRATIC,
            support_sums=support_sums,
            attack_sums=attack_sums,
            total_weight_of_evidence=total_evidence,
            volatility_index=volatility,
            admissibility_pruned_count=admissibility_pruned,
        )

    def compare_weight_modes(
        self,
        nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
        edges: Sequence[Any] | None = None,
    ) -> QBAFComparisonResult:
        """Evaluate dialectical equilibrium under both calibrated modal and unweighted binary modes.

        Parameters
        ----------
        nodes : Mapping or Sequence
            Nodes with base plausibility priors.
        edges : Sequence
            Graph relations with confidence, accuracy, and modality attributes.

        Returns
        -------
        QBAFComparisonResult
            Paired results, absolute drift measurements, and rank reversal statistics.
        """
        cal_res = self.solve(
            nodes=nodes,
            edges=edges,
            normalization_mode=WeightNormalizationMode.CALIBRATED_MODAL,
        )
        unw_res = self.solve(
            nodes=nodes,
            edges=edges,
            normalization_mode=WeightNormalizationMode.UNWEIGHTED_BINARY,
        )

        all_nodes = list(cal_res.degrees.keys())
        deltas: dict[str, float] = {}
        abs_drifts: list[float] = []

        max_drift = 0.0
        max_drift_node: str | None = None

        for nid in all_nodes:
            c_val = cal_res.degrees[nid]
            u_val = unw_res.degrees[nid]
            d = round(c_val - u_val, 6)
            deltas[nid] = d
            abs_d = abs(d)
            abs_drifts.append(abs_d)

            if abs_d > max_drift:
                max_drift = abs_d
                max_drift_node = nid

        mean_drift = float(np.mean(abs_drifts)) if abs_drifts else 0.0

        # Compute rank reversals across pairs
        rank_reversals = 0
        n = len(all_nodes)
        for i in range(n):
            for j in range(i + 1, n):
                u = all_nodes[i]
                v = all_nodes[j]
                c_diff = cal_res.degrees[u] - cal_res.degrees[v]
                u_diff = unw_res.degrees[u] - unw_res.degrees[v]
                # Reversal if relative order strictly changes sign
                if (c_diff > 1e-4 and u_diff < -1e-4) or (c_diff < -1e-4 and u_diff > 1e-4):
                    rank_reversals += 1

        summary = {
            "total_nodes": n,
            "mean_absolute_drift": round(mean_drift, 6),
            "max_drift": round(max_drift, 6),
            "max_drift_node": max_drift_node,
            "rank_reversals": rank_reversals,
            "calibrated_iterations": cal_res.iterations,
            "unweighted_iterations": unw_res.iterations,
            "admissibility_pruned_count": cal_res.admissibility_pruned_count,
        }

        return QBAFComparisonResult(
            calibrated_result=cal_res,
            unweighted_result=unw_res,
            delta_justifications=deltas,
            mean_absolute_drift=round(mean_drift, 6),
            max_drift=round(max_drift, 6),
            max_drift_node=max_drift_node,
            rank_reversals=rank_reversals,
            summary=summary,
        )

    def _compute_update(
        self,
        tau_0: float,
        support: float,
        attack: float,
        model: GradualSemanticsModel,
    ) -> float:
        """Compute the updated single-node justification degree."""
        if model == GradualSemanticsModel.LINEAR:
            val = tau_0 + support - attack
            return max(0.0, min(1.0, val))

        elif model == GradualSemanticsModel.CATEGORIZER:
            # h-categorizer formulation: tau_0 / (1 + attack) * (1 + support / (1 + support))
            denom = 1.0 + attack
            supp_factor = 1.0 + (support / (1.0 + support))
            val = (tau_0 / max(denom, 1e-9)) * supp_factor
            return max(0.0, min(1.0, val))

        elif model == GradualSemanticsModel.EULER:
            # Eulerian energy formulation: 1 - (1 - tau_0^2) / (1 + tau_0 * exp(support - attack))
            energy = support - attack
            clamped_energy = max(-50.0, min(50.0, energy))
            denom = 1.0 + tau_0 * math.exp(clamped_energy)
            val = 1.0 - (1.0 - tau_0**2) / max(denom, 1e-9)
            return max(0.0, min(1.0, val))

        else:
            # Quadratic Energy formulation (default)
            # Monotone, smoothly bounded in [0, 1] without numerical oscillation
            supp_term = (1.0 - tau_0) * (support / (1.0 + support))
            att_term = tau_0 * (attack / (1.0 + attack))
            val = tau_0 + supp_term - att_term
            return max(0.0, min(1.0, val))

    def _prepare_graph_data(
        self,
        nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
        edges: Sequence[Any] | None,
        normalization_mode: WeightNormalizationMode,
        active_adm_mode: Literal["hard", "soft"],
        active_tau_p: float,
        active_tau_c: float,
    ) -> tuple[dict[str, float], list[_AdmissibleEdge], int]:
        """Normalize node base plausibilities and filter dialectical edges with admissibility gating.

        Parameters
        ----------
        nodes : TheoryGraph or Mapping or Sequence
            Argument nodes or complete TheoryGraph container.
        edges : Sequence or None
            Dialectical relations between nodes (inferred from TheoryGraph if omitted).
        normalization_mode : WeightNormalizationMode
            Weight calculation mode.
        active_adm_mode : Literal["hard", "soft"]
            Gating mode ('hard' pruning vs. 'soft' sigmoidal relaxation).
        active_tau_p : float
            Stance probability threshold.
        active_tau_c : float
            Model confidence threshold.

        Returns
        -------
        tuple of (dict[str, float], list[_AdmissibleEdge], int)
            Normalized node base priors, filtered admissible edges, and pruned edge count.
        """
        if isinstance(nodes, TheoryGraph):
            raw_nodes: Mapping[str, Any] | Sequence[Any] = nodes.nodes
            raw_edges: Sequence[Any] = edges if edges is not None else nodes.edges
        else:
            raw_nodes = nodes
            raw_edges = edges if edges is not None else ()

        base_tau: dict[str, float] = {}
        if isinstance(raw_nodes, Mapping):
            for nid, val in raw_nodes.items():
                if isinstance(val, (int, float)):
                    base_tau[str(nid)] = max(0.0, min(1.0, float(val)))
                else:
                    _, extracted_tau = self._extract_node_plausibility(val)
                    base_tau[str(nid)] = max(0.0, min(1.0, extracted_tau))
        else:
            for item in raw_nodes:
                nid, val = self._extract_node_plausibility(item)
                base_tau[nid] = max(0.0, min(1.0, val))

        admissible_edges: list[_AdmissibleEdge] = []
        admissibility_pruned = 0

        for edge_item in raw_edges:
            parsed = self._parse_edge(edge_item)
            if not parsed:
                continue

            src, tgt, pol, eff_w, acc, p_stance, model_conf = parsed

            # Ensure both endpoints exist in node index
            if src not in base_tau:
                base_tau[src] = 0.5
            if tgt not in base_tau:
                base_tau[tgt] = 0.5

            # Enforce admissibility gating based on mode
            if active_adm_mode == "hard":
                is_inadmissible = False
                if self.admissibility_threshold > 0.0 and acc is not None and acc < self.admissibility_threshold:
                    is_inadmissible = True
                if active_tau_p > 0.0 and p_stance is not None and p_stance < active_tau_p:
                    is_inadmissible = True
                if active_tau_c > 0.0 and model_conf is not None and model_conf < active_tau_c:
                    is_inadmissible = True

                if is_inadmissible:
                    admissibility_pruned += 1
                    if self.prune_inadmissible:
                        continue
                    else:
                        eff_w = 0.0

                if normalization_mode == WeightNormalizationMode.UNWEIGHTED_BINARY:
                    final_w = 1.0 if not is_inadmissible else 0.0
                else:
                    final_w = eff_w
            else:
                # Mode 2: Soft Margin continuous sigmoidal relaxation
                gate_p = (
                    1.0 / (1.0 + math.exp(-20.0 * (p_stance - active_tau_p)))
                    if (p_stance is not None and active_tau_p > 0.0)
                    else 1.0
                )
                gate_c = (
                    1.0 / (1.0 + math.exp(-20.0 * (model_conf - active_tau_c)))
                    if (model_conf is not None and active_tau_c > 0.0)
                    else 1.0
                )
                f_soft = gate_p * gate_c
                if normalization_mode == WeightNormalizationMode.UNWEIGHTED_BINARY:
                    final_w = 1.0 * f_soft
                else:
                    final_w = eff_w * f_soft

            admissible_edges.append(
                _AdmissibleEdge(
                    source=src,
                    target=tgt,
                    polarity=pol,
                    weight=final_w,
                )
            )

        return base_tau, admissible_edges, admissibility_pruned

    def _extract_node_plausibility(self, node: Any) -> tuple[str, float]:
        """Extract canonical ID and prior plausibility from diverse node representations.

        Parameters
        ----------
        node : Any
            Node representation (TheoryNode, dict, tuple, or identifier).

        Returns
        -------
        tuple of (str, float)
            Tuple of canonical node ID and prior plausibility tau_0 in [0, 1].
        """
        if isinstance(node, TheoryNode):
            if "base_score" in node.model_fields_set:
                tau = node.base_score
            elif "confidence" in node.model_fields_set:
                tau = node.confidence
            else:
                tau = node.base_score
            return node.id, float(tau)

        if isinstance(node, dict):
            nid = str(node.get("id") or node.get("node_id") or "unknown")
            tau = node.get("base_score") or node.get("plausibility") or node.get("confidence") or 0.5
            return nid, float(tau)

        if isinstance(node, (tuple, list)) and len(node) >= 2:
            return str(node[0]), float(node[1])

        if hasattr(node, "id"):
            nid = str(node.id)
            tau = 0.5
            if hasattr(node, "base_score") and node.base_score is not None:
                tau = node.base_score
            elif hasattr(node, "plausibility") and node.plausibility is not None:
                tau = node.plausibility
            elif hasattr(node, "confidence") and node.confidence is not None:
                tau = node.confidence
            return nid, float(tau)

        return str(node), 0.5

    def _parse_edge(
        self, edge: Any
    ) -> tuple[str, str, int, float, float | None, float | None, float | None] | None:
        """Parse source, target, polarity, effective weight, accuracy, stance probability, and model confidence.

        Parameters
        ----------
        edge : Any
            Edge representation (TheoryEdge, dict, or tuple).

        Returns
        -------
        tuple of (str, str, int, float, float | None, float | None, float | None) or None
            Parsed relational attributes (src, tgt, polarity, weight, accuracy, stance_prob, confidence).
        """
        # 1. First-class TheoryEdge domain object
        if isinstance(edge, TheoryEdge):
            pol = edge.polarity
            if pol == 0:
                pol = edge.relation_type.default_polarity if isinstance(edge.relation_type, RelationType) else 1
            eff_w, acc, p_stance, model_conf = self._extract_edge_weights_from_model(edge)
            return edge.source, edge.target, pol, eff_w, acc, p_stance, model_conf

        # 2. Dictionary representation
        if isinstance(edge, dict):
            src = str(edge.get("source") or edge.get("source_id") or edge.get("from_id", ""))
            tgt = str(edge.get("target") or edge.get("target_id") or edge.get("to_id", ""))
            if not src or not tgt:
                return None
            props = edge.get("properties") if isinstance(edge.get("properties"), dict) else edge
            pol = self._resolve_polarity(
                props.get("polarity"),
                edge.get("relation_type") or props.get("relation_type") or props.get("type"),
            )
            eff_w, acc, p_stance, model_conf = self._extract_edge_weights_from_dict(props)
            return src, tgt, pol, eff_w, acc, p_stance, model_conf

        # 3. Tuple (src, tgt, weight, polarity)
        if isinstance(edge, (tuple, list)) and len(edge) >= 2:
            src = str(edge[0])
            tgt = str(edge[1])
            w = float(edge[2]) if len(edge) >= 3 else 1.0
            pol = int(edge[3]) if len(edge) >= 4 else 1
            return src, tgt, pol, w, None, None, None

        # 4. Fallback for foreign domain object with source/target or source_id/target_id
        if hasattr(edge, "source_id") and hasattr(edge, "target_id"):
            src = str(edge.source_id)
            tgt = str(edge.target_id)
            rel_type = edge.relation_type if hasattr(edge, "relation_type") else None
            pol = self._resolve_polarity(None, rel_type)
            eff_w, acc, p_stance, model_conf = self._extract_edge_weights_from_foreign(edge)
            return src, tgt, pol, eff_w, acc, p_stance, model_conf

        if hasattr(edge, "source") and hasattr(edge, "target"):
            src = str(edge.source)
            tgt = str(edge.target)
            explicit_pol = edge.polarity if hasattr(edge, "polarity") else None
            rel_type = edge.relation_type if hasattr(edge, "relation_type") else None
            pol = self._resolve_polarity(explicit_pol, rel_type)
            eff_w, acc, p_stance, model_conf = self._extract_edge_weights_from_foreign(edge)
            return src, tgt, pol, eff_w, acc, p_stance, model_conf

        return None

    def _resolve_polarity(self, polarity: int | None, relation_type: Any) -> int:
        """Resolve epistemic polarity (+1 support, -1 attack, 0 neutral).

        Parameters
        ----------
        polarity : int or None
            Explicit polarity integer if provided.
        relation_type : Any
            RelationType enum or string taxonomic classification.

        Returns
        -------
        int
            Canonical polarity (+1 for support, -1 for attack).
        """
        if polarity is not None and isinstance(polarity, int) and polarity != 0:
            return 1 if polarity > 0 else -1

        if isinstance(relation_type, RelationType):
            pol = relation_type.default_polarity
            return pol if pol != 0 else 1

        if relation_type is not None:
            r_str = str(relation_type).upper()
            if r_str in {
                "SUPPORTS",
                "SUPPORTS_ARG",
                "ENTAILS",
                "IMPLIES",
                "DEDUCES",
                "COHERES_WITH",
            }:
                return 1
            if r_str in {
                "ATTACKS",
                "REFUTES",
                "CONTRADICTS",
                "UNDERCUTS",
                "INHIBITS",
            }:
                return -1

        return 1

    def _extract_edge_weights_from_model(
        self, edge: TheoryEdge
    ) -> tuple[float, float | None, float | None, float | None]:
        """Extract decoupled mathematical weights from TheoryEdge domain model.

        Parameters
        ----------
        edge : TheoryEdge
            Strongly typed theory edge model.

        Returns
        -------
        tuple of (float, float | None, float | None, float | None)
            Resolved weight magnitude, empirical accuracy, stance probability, and model confidence.
        """
        p_stance = edge.stance_probability if edge.stance_probability is not None else edge.class_probability
        model_conf = edge.model_confidence
        acc = edge.empirical_accuracy
        inferential = edge.inferential_force
        modal = edge.modal_strength

        if edge.effective_weight is not None:
            w = float(edge.effective_weight)
        elif "active_weight" in edge.model_fields_set and edge.active_weight is not None:
            w = float(edge.active_weight)
        elif p_stance is not None:
            force = inferential if inferential is not None else modal
            w = float(force * float(p_stance))
        elif inferential is not None:
            w = float(inferential)
        elif edge.weight is not None:
            w = float(edge.weight)
        else:
            w = 1.0

        c_val = float(model_conf) if model_conf is not None else (float(acc) if acc is not None else None)
        return max(0.0, w), acc, p_stance, c_val

    def _extract_edge_weights_from_dict(
        self, obj: Mapping[str, Any]
    ) -> tuple[float, float | None, float | None, float | None]:
        """Extract decoupled mathematical weights from dictionary representation.

        Parameters
        ----------
        obj : Mapping of str to Any
            Relational property dictionary.

        Returns
        -------
        tuple of (float, float | None, float | None, float | None)
            Resolved weight magnitude, empirical accuracy, stance probability, and model confidence.
        """
        inferential = obj.get("inferential_force")
        modal = float(obj.get("modal_strength", 1.0) or 1.0)
        p_stance = obj.get("stance_probability") or obj.get("class_probability")
        model_conf = obj.get("model_confidence")
        acc = obj.get("empirical_accuracy")
        explicit_active = obj.get("active_weight")
        explicit_eff = obj.get("effective_weight")
        explicit_w = obj.get("weight") or obj.get("confidence")

        if explicit_active is not None:
            w = float(explicit_active)
        elif explicit_eff is not None:
            w = float(explicit_eff)
        elif inferential is not None and p_stance is None:
            w = float(inferential)
        elif p_stance is not None:
            force = inferential if inferential is not None else modal
            w = float(force * float(p_stance))
        elif inferential is not None:
            w = float(inferential)
        elif explicit_w is not None:
            w = float(explicit_w)
        else:
            w = 1.0

        p_val = float(p_stance) if p_stance is not None else None
        c_val = float(model_conf) if model_conf is not None else (float(acc) if acc is not None else None)
        acc_val = float(acc) if acc is not None else None
        return max(0.0, w), acc_val, p_val, c_val

    def _extract_edge_weights_from_foreign(
        self, obj: Any
    ) -> tuple[float, float | None, float | None, float | None]:
        """Extract decoupled mathematical weights from foreign domain object without getattr reflection.

        Parameters
        ----------
        obj : Any
            Foreign object instance.

        Returns
        -------
        tuple of (float, float | None, float | None, float | None)
            Resolved weight magnitude, empirical accuracy, stance probability, and model confidence.
        """
        inferential = obj.inferential_force if hasattr(obj, "inferential_force") else None
        modal = float(obj.modal_strength if hasattr(obj, "modal_strength") and obj.modal_strength is not None else 1.0)
        p_stance = (
            obj.stance_probability
            if hasattr(obj, "stance_probability") and obj.stance_probability is not None
            else (obj.class_probability if hasattr(obj, "class_probability") else None)
        )
        model_conf = obj.model_confidence if hasattr(obj, "model_confidence") else None
        acc = obj.empirical_accuracy if hasattr(obj, "empirical_accuracy") else None
        explicit_active = obj.active_weight if hasattr(obj, "active_weight") else None
        explicit_eff = obj.effective_weight if hasattr(obj, "effective_weight") else None
        explicit_w = (
            obj.weight
            if hasattr(obj, "weight") and obj.weight is not None
            else (obj.confidence if hasattr(obj, "confidence") else None)
        )

        if explicit_active is not None:
            w = float(explicit_active)
        elif explicit_eff is not None:
            w = float(explicit_eff)
        elif inferential is not None and p_stance is None:
            w = float(inferential)
        elif p_stance is not None:
            force = inferential if inferential is not None else modal
            w = float(force * float(p_stance))
        elif inferential is not None:
            w = float(inferential)
        elif explicit_w is not None:
            w = float(explicit_w)
        else:
            w = 1.0

        p_val = float(p_stance) if p_stance is not None else None
        c_val = float(model_conf) if model_conf is not None else (float(acc) if acc is not None else None)
        acc_val = float(acc) if acc is not None else None
        return max(0.0, w), acc_val, p_val, c_val


def solve_qbaf_gradual_semantics(
    nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    semantics_model: GradualSemanticsModel | str = GradualSemanticsModel.QUADRATIC,
    normalization_mode: WeightNormalizationMode
    | str = WeightNormalizationMode.CALIBRATED_MODAL,
    admissibility_threshold: float = 0.0,
    admissibility_mode: Literal["hard", "soft"] = "hard",
    tau_p: float = 0.0,
    tau_c: float = 0.0,
    max_iterations: int = 50,
    tolerance: float = 1e-4,
    continuous: bool = False,
) -> QBAFSolverResult:
    """Convenience functional interface for solving QBAF gradual semantics.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Target argument nodes or complete TheoryGraph container.
    edges : Sequence or None, optional
        Dialectical relations. Inferred from TheoryGraph if omitted.
    semantics_model : GradualSemanticsModel or str, default QUADRATIC
        Convergence update formulation.
    normalization_mode : WeightNormalizationMode or str, default CALIBRATED_MODAL
        Edge weighting mode.
    admissibility_threshold : float, default 0.0
        Empirical accuracy admissibility gate.
    admissibility_mode : Literal["hard", "soft"], default "hard"
        Gating strategy (Mode 1 hard pruning vs. Mode 2 continuous sigmoidal relaxation).
    tau_p : float, default 0.0
        Stance probability threshold.
    tau_c : float, default 0.0
        Model confidence threshold.
    max_iterations : int, default 50
        Maximum iteration limit.
    tolerance : float, default 1e-4
        Numerical convergence threshold.
    continuous : bool, default False
        Whether to solve via unified continuous WeightedQuadraticEnergySolver.

    Returns
    -------
    QBAFSolverResult
        Equilibrium justification results.
    """
    solver = QBAFGradualSemanticsSolver(
        semantics_model=semantics_model,
        max_iterations=max_iterations,
        tolerance=tolerance,
        admissibility_threshold=admissibility_threshold,
        admissibility_mode=admissibility_mode,
        tau_p=tau_p,
        tau_c=tau_c,
        use_continuous=continuous,
    )
    return solver.solve(
        nodes=nodes,
        edges=edges,
        normalization_mode=normalization_mode,
        admissibility_mode=admissibility_mode,
        tau_p=tau_p,
        tau_c=tau_c,
        continuous=continuous,
    )


def solve_continuous_qbaf(
    nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    normalization_mode: WeightNormalizationMode
    | str = WeightNormalizationMode.CALIBRATED_MODAL,
    admissibility_mode: Literal["hard", "soft"] = "hard",
    tau_p: float = 0.0,
    tau_c: float = 0.0,
    tolerance: float = 1e-4,
) -> QBAFSolverResult:
    """Convenience functional interface for continuous Quadratic Energy QBAF solving.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Target argument nodes or TheoryGraph container.
    edges : Sequence or None, optional
        Dialectical relations. Inferred from TheoryGraph if omitted.
    normalization_mode : WeightNormalizationMode or str, default CALIBRATED_MODAL
        Edge weighting mode.
    admissibility_mode : Literal["hard", "soft"], default "hard"
        Gating strategy (Mode 1 hard pruning vs. Mode 2 continuous sigmoidal relaxation).
    tau_p : float, default 0.0
        Stance probability threshold.
    tau_c : float, default 0.0
        Model confidence threshold.
    tolerance : float, default 1e-4
        Numerical convergence threshold.

    Returns
    -------
    QBAFSolverResult
        Equilibrium justification results.
    """
    solver = QBAFGradualSemanticsSolver(
        semantics_model=GradualSemanticsModel.QUADRATIC,
        tolerance=tolerance,
        admissibility_mode=admissibility_mode,
        tau_p=tau_p,
        tau_c=tau_c,
    )
    return solver.solve_continuous(nodes=nodes, edges=edges, normalization_mode=normalization_mode)


def compare_qbaf_weight_modes(
    nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    semantics_model: GradualSemanticsModel | str = GradualSemanticsModel.QUADRATIC,
    admissibility_threshold: float = 0.0,
    max_iterations: int = 50,
    tolerance: float = 1e-4,
) -> QBAFComparisonResult:
    """Convenience functional interface for comparing calibrated modal vs unweighted binary QBAF.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Target argument nodes or TheoryGraph container.
    edges : Sequence or None, optional
        Dialectical relations. Inferred from TheoryGraph if omitted.
    semantics_model : GradualSemanticsModel or str, default QUADRATIC
        Convergence update formulation.
    admissibility_threshold : float, default 0.0
        Empirical accuracy admissibility gate.
    max_iterations : int, default 50
        Maximum iteration cap.
    tolerance : float, default 1e-4
        Numerical convergence threshold.

    Returns
    -------
    QBAFComparisonResult
        Comparative analysis with drift and rank reversal measurements.
    """
    solver = QBAFGradualSemanticsSolver(
        semantics_model=semantics_model,
        max_iterations=max_iterations,
        tolerance=tolerance,
        admissibility_threshold=admissibility_threshold,
    )
    return solver.compare_weight_modes(nodes=nodes, edges=edges)
