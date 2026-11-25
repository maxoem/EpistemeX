"""Quantitative Bipolar Argumentation Framework (QBAF) Gradual Semantics Solvers.

Operationalizes dialectical equilibrium convergence over argument graphs with
decoupled weights separating node propositional modality/prior :math:`\\tau_0(a)`
from relational inferential warrant :math:`W_{ji}` and admissibility gating,
while supporting optional intensional supposition (*Reductio* refutation
discharge) and epistemic perspective scoping.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import networkx as nx
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.integrate import solve_ivp

from epistemetrics.core.models import NodeType, RelationType, TheoryEdge, TheoryNode
from epistemetrics.graph.theory_graph import TheoryGraph

_VALID_T_NORMS = frozenset({"product", "godel"})


def _validate_t_norm(t_norm: str) -> Literal["product", "godel"]:
    """Validate and normalize conjunctive t-norm selector."""
    norm = t_norm.strip().lower()
    if norm == "product":
        return "product"
    if norm == "godel":
        return "godel"
    raise ValueError(
        f"Unsupported conjunctive t-norm '{t_norm}'. Expected 'product' or 'godel'."
    )


def _conjunctive_t_norm(
    values: Sequence[float], t_norm: Literal["product", "godel"]
) -> float:
    """Aggregate conjunctive premise activations using the configured t-norm."""
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    if t_norm == "godel":
        return float(min(values))
    return float(math.prod(values))


@dataclass(slots=True, frozen=True)
class HyperedgeSpec:
    """Compiled bipartite hyperedge / warrant specification for QBAF solvers.

    Attributes
    ----------
    warrant_id : str
        Canonical identifier of the reified ``:TheoryInference`` warrant node.
    premise_indices : tuple of int
        Index tuple of conjunctive premise atoms in the solver's node vector.
    target_idx : int
        Index of the conclusion target atom in the solver's node vector.
    polarity : int
        Epistemic polarity toward the conclusion (``+1`` support, ``-1`` attack).
    base_warrant : float
        Intrinsic Toulminian warrant plausibility prior :math:`w_0 \\in [0, 1]`.
    gate_factor : float, default 1.0
        Multiplicative perception/tenability gating factor decoupling
        :math:`s(w_k)` from extrinsic gate thresholds.
    backing_edges : tuple of (tuple of int, float), optional
        Positive backing modifiers ``(premise_indices, weight)`` targeting this warrant.
    undercut_edges : tuple of (tuple of int, float), optional
        Negative undercutting modifiers ``(premise_indices, weight)`` targeting this warrant.
    target_warrant_idx : int or None, optional
        Optional target warrant index in ``hyperedges`` when this specification
        represents a modulated higher-order modifier acting on another warrant
        (in which case ``target_idx`` is ``-1``).
    """

    warrant_id: str
    premise_indices: tuple[int, ...]
    target_idx: int
    polarity: int
    base_warrant: float = 0.75
    gate_factor: float = 1.0
    backing_edges: tuple[tuple[tuple[int, ...], float], ...] = ()
    undercut_edges: tuple[tuple[tuple[int, ...], float], ...] = ()
    target_warrant_idx: int | None = None


@dataclass(slots=True, frozen=True)
class _AdmissibleEdge:
    """Internal normalized representation for dialectical edges after admissibility gating."""

    source: str
    target: str
    polarity: int
    weight: float
    id: str | None = None
    premise_ids: tuple[str, ...] = ()
    undercuts_relation_id: str | None = None
    base_warrant: float = 0.75


@dataclass(slots=True, frozen=True)
class _ParsedEdge:
    """Internal parsed representation for candidate dialectical edges before scoping and gating."""

    source: str
    target: str
    polarity: int
    eff_w: float
    acc: float | None
    p_stance: float | None
    model_conf: float | None
    id: str | None = None
    premise_ids: tuple[str, ...] = ()
    undercuts_relation_id: str | None = None
    base_warrant: float = 0.75


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
    """Weight normalization mode for QBAF solving.

    Attributes
    ----------
    CALIBRATED_MODAL : str
        Continuous edge weights modulated by inferential warrant, admissibility
        gating, and edge tenability.
    UNWEIGHTED_BINARY : str
        Unit binary edge weights (:math:`w = 1.0` for all active edges).
    """

    CALIBRATED_MODAL = "calibrated_modal"
    UNWEIGHTED_BINARY = "unweighted_binary"


class BasePriorPolicy(str, Enum):
    """Policy deriving atom base prior :math:`\\beta(a) \\in [0, 1]` before propagation.

    Decouples descriptive authorial commitment :math:`M_{\\text{mod}}(\\phi_a)`
    from normative epistemic priors so evaluative acceptability does not track
    rhetorical hedging conventions.

    Attributes
    ----------
    DESCRIPTIVE_AUTHORIAL : str
        Sets :math:`\\beta(a) = M_{\\text{mod}}(\\phi_a)` (or node ``base_score``)
        to reconstruct authorial commitment weights within a text.
    NORMATIVE_UNIFORM : str
        Assigns a uniform neutral prior (default ``0.5``) to all active atoms.
    NORMATIVE_DATA_PRIORITY : str
        Assigns a defeasible Data-Priority prior (default ``0.8``) to evidential
        base atoms (:math:`B`) and a neutral prior (default ``0.5``) to
        theoretical hypotheses (:math:`H`).
    """

    DESCRIPTIVE_AUTHORIAL = "descriptive_authorial"
    NORMATIVE_UNIFORM = "normative_uniform"
    NORMATIVE_DATA_PRIORITY = "normative_data_priority"


_EVIDENTIAL_NODE_TYPES: frozenset[str] = frozenset(
    {
        "evidence",
        "observationunit",
        "observation_unit",
        "empiricalstatement",
        "empirical_statement",
        "observation",
        "empiricalevidence",
        "empirical_evidence",
        "datum",
    }
)


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
    perspective: str | None = Field(
        default=None,
        description="Evaluated epistemic perspective filter ('author', agent name, or None).",
    )
    suppositional_isolated_count: int = Field(
        default=0,
        description="Number of suppositional/Reductio nodes isolated from contributing unconditioned positive prior.",
    )
    perspective_filtered_count: int = Field(
        default=0,
        description="Number of cross-perspective or off-perspective nodes isolated during evaluation.",
    )
    warrant_states: dict[str, float] = Field(
        default_factory=dict,
        description="Converged validity degrees s_W(xi_k) for reified inference warrants.",
    )
    base_prior_policy: BasePriorPolicy = Field(
        default=BasePriorPolicy.DESCRIPTIVE_AUTHORIAL,
        description="Base prior policy applied before dialectical propagation.",
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
    t_norm : Literal["product", "godel"], default "product"
        Conjunctive t-norm operator applied across multi-premise inference sets
        (``"product"`` multiplicative t-norm or ``"godel"`` minimum t-norm).
    """

    def __init__(
        self,
        rtol: float = 1e-4,
        atol: float = 1e-6,
        t_max: float = 50.0,
        max_step: float = 0.5,
        t_norm: Literal["product", "godel"] = "product",
    ) -> None:
        self.rtol = rtol
        self.atol = atol
        self.t_max = t_max
        self.max_step = max_step
        self.t_norm = _validate_t_norm(t_norm)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            Solver class identity and continuous/t-norm hyperparameters.
        """
        return {
            "class": self.__class__.__name__,
            "rtol": self.rtol,
            "atol": self.atol,
            "t_max": self.t_max,
            "max_step": self.max_step,
            "t_norm": self.t_norm,
        }

    @staticmethod
    def _impact(x: np.ndarray | float) -> np.ndarray | float:
        """Quadratic impact attenuation function h(x) = (max(x, 0)^2) / (1 + max(x, 0)^2)."""
        pos = np.maximum(x, 0.0)
        pos_sq = pos**2
        return pos_sq / (1.0 + pos_sq)

    def _conjunctive_activation(
        self,
        s: np.ndarray,
        premise_indices: tuple[int, ...],
    ) -> float:
        """Evaluate conjunctive premise activation under the configured t-norm."""
        if not premise_indices:
            return 0.0
        if len(premise_indices) == 1:
            return float(s[premise_indices[0]])
        vals = [float(s[idx]) for idx in premise_indices]
        return _conjunctive_t_norm(vals, self.t_norm)

    @staticmethod
    def _group_warrant_modifiers(
        hyperedges: Sequence[HyperedgeSpec],
    ) -> dict[int, list[tuple[int, HyperedgeSpec]]]:
        """Index higher-order modifier hyperedges by their target warrant index."""
        mods: dict[int, list[tuple[int, HyperedgeSpec]]] = {}
        for mod_k, spec in enumerate(hyperedges):
            if spec.target_warrant_idx is not None:
                mods.setdefault(spec.target_warrant_idx, []).append((mod_k, spec))
        return mods

    def _evaluate_warrant_energy(
        self,
        s_atoms: np.ndarray,
        spec: HyperedgeSpec,
        s_w: np.ndarray | None = None,
        warrant_mods: Sequence[tuple[int, HyperedgeSpec]] = (),
    ) -> float:
        """Compute net Toulmin warrant energy ``E_back - E_undercut`` for ``spec``."""
        e_back = sum(
            w_b * self._conjunctive_activation(s_atoms, b_idxs)
            for b_idxs, w_b in spec.backing_edges
        )
        e_und = sum(
            w_u * self._conjunctive_activation(s_atoms, u_idxs)
            for u_idxs, w_u in spec.undercut_edges
        )
        for mod_k, mod_spec in warrant_mods:
            sw_mod = (
                float(s_w[mod_k])
                if s_w is not None
                else float(np.clip(mod_spec.base_warrant, 0.0, 1.0))
            )
            mod_contrib = (
                sw_mod
                * mod_spec.gate_factor
                * self._conjunctive_activation(s_atoms, mod_spec.premise_indices)
            )
            if mod_spec.polarity > 0:
                e_back += mod_contrib
            elif mod_spec.polarity < 0:
                e_und += mod_contrib
        return float(e_back - e_und)

    def _compute_warrant_states(
        self,
        s_atoms: np.ndarray,
        hyperedges: Sequence[HyperedgeSpec],
    ) -> np.ndarray:
        """Evaluate exact Quadratic Energy steady-state warrant degrees given atom states."""
        m = len(hyperedges)
        if m == 0:
            return np.array([], dtype=np.float64)
        warrant_mods = self._group_warrant_modifiers(hyperedges)
        s_w = np.array(
            [np.clip(spec.base_warrant, 0.0, 1.0) for spec in hyperedges],
            dtype=np.float64,
        )
        max_sweeps = 1 if not warrant_mods else 256
        tol = min(self.atol, 1e-9)
        for _ in range(max_sweeps):
            s_w_next = np.empty(m, dtype=np.float64)
            for k, spec in enumerate(hyperedges):
                e_w = self._evaluate_warrant_energy(
                    s_atoms,
                    spec,
                    s_w=s_w,
                    warrant_mods=warrant_mods.get(k, ()),
                )
                w0 = float(np.clip(spec.base_warrant, 0.0, 1.0))
                val = (
                    w0
                    + (1.0 - w0) * float(self._impact(e_w))
                    - w0 * float(self._impact(-e_w))
                )
                s_w_next[k] = float(np.clip(val, 0.0, 1.0))
            max_delta = float(np.max(np.abs(s_w_next - s_w)))
            s_w = s_w_next
            if max_delta < tol:
                break
        return s_w

    def _derivatives(
        self,
        t: float,
        s: np.ndarray,
        w: np.ndarray,
        g_supp_t: np.ndarray,
        g_att_t: np.ndarray,
        hyperedges: Sequence[HyperedgeSpec] = (),
    ) -> np.ndarray:
        """Compute ODE time derivative vector s_dot under Quadratic Energy formulation."""
        if not hyperedges:
            e = (g_supp_t @ s) - (g_att_t @ s)
            h_pos = self._impact(e)
            h_neg = self._impact(-e)
            return w - s + (1.0 - w) * h_pos - w * h_neg

        n = len(w)
        m = len(hyperedges)
        s_atoms = s[:n]
        has_warrant_state = len(s) >= n + m
        s_warrants = (
            s[n : n + m]
            if has_warrant_state
            else self._compute_warrant_states(s_atoms, hyperedges)
        )

        e_supp = np.array(g_supp_t @ s_atoms, dtype=np.float64)
        e_att = np.array(g_att_t @ s_atoms, dtype=np.float64)
        ds_warrants = np.zeros(m, dtype=np.float64)
        warrant_mods = self._group_warrant_modifiers(hyperedges)

        for k, spec in enumerate(hyperedges):
            e_w = self._evaluate_warrant_energy(
                s_atoms,
                spec,
                s_w=s_warrants,
                warrant_mods=warrant_mods.get(k, ()),
            )
            w0 = float(np.clip(spec.base_warrant, 0.0, 1.0))
            sw_k = float(s_warrants[k])
            ds_warrants[k] = (
                w0
                - sw_k
                + (1.0 - w0) * float(self._impact(e_w))
                - w0 * float(self._impact(-e_w))
            )
            if spec.target_warrant_idx is not None or spec.target_idx < 0:
                continue
            contrib = (
                sw_k
                * spec.gate_factor
                * self._conjunctive_activation(s_atoms, spec.premise_indices)
            )
            if spec.polarity > 0:
                e_supp[spec.target_idx] += contrib
            elif spec.polarity < 0:
                e_att[spec.target_idx] += contrib

        e_atoms = e_supp - e_att
        ds_atoms = (
            w - s_atoms + (1.0 - w) * self._impact(e_atoms) - w * self._impact(-e_atoms)
        )
        if has_warrant_state:
            return np.concatenate([ds_atoms, ds_warrants])
        return ds_atoms

    def _solve_dag_closed_form(
        self,
        base_scores: np.ndarray,
        g_supp_t: np.ndarray,
        g_att_t: np.ndarray,
        topo_order: list[int],
        hyperedges: Sequence[HyperedgeSpec] = (),
    ) -> np.ndarray:
        """Evaluate exact equilibrium in closed form along topological order (Proposition 5)."""
        s = base_scores.copy()
        if not hyperedges:
            for i in topo_order:
                e_i = float(np.dot(g_supp_t[i], s) - np.dot(g_att_t[i], s))
                h_pos = float(self._impact(e_i))
                h_neg = float(self._impact(-e_i))
                w_i = float(base_scores[i])
                s[i] = w_i + (1.0 - w_i) * h_pos - w_i * h_neg
            return np.clip(s, 0.0, 1.0)

        n = len(base_scores)
        m = len(hyperedges)
        s_w = np.array(
            [np.clip(h.base_warrant, 0.0, 1.0) for h in hyperedges], dtype=np.float64
        )
        warrant_done = [False] * m
        warrant_mods = self._group_warrant_modifiers(hyperedges)
        incoming_hyper: dict[int, list[int]] = {}
        for k, spec in enumerate(hyperedges):
            if spec.target_warrant_idx is None and 0 <= spec.target_idx < n:
                incoming_hyper.setdefault(spec.target_idx, []).append(k)

        def _eval_warrant(k_idx: int) -> None:
            if warrant_done[k_idx]:
                return
            for mod_k, _ in warrant_mods.get(k_idx, ()):
                if not warrant_done[mod_k]:
                    _eval_warrant(mod_k)
            spec = hyperedges[k_idx]
            e_w = self._evaluate_warrant_energy(
                s,
                spec,
                s_w=s_w,
                warrant_mods=warrant_mods.get(k_idx, ()),
            )
            w0 = float(np.clip(spec.base_warrant, 0.0, 1.0))
            val = (
                w0
                + (1.0 - w0) * float(self._impact(e_w))
                - w0 * float(self._impact(-e_w))
            )
            s_w[k_idx] = float(np.clip(val, 0.0, 1.0))
            warrant_done[k_idx] = True

        for node_idx in topo_order:
            if node_idx >= n:
                _eval_warrant(node_idx - n)
                continue

            i = node_idx
            e_i = float(np.dot(g_supp_t[i], s) - np.dot(g_att_t[i], s))
            for k in incoming_hyper.get(i, []):
                if not warrant_done[k]:
                    _eval_warrant(k)
                spec = hyperedges[k]
                contrib = (
                    float(s_w[k])
                    * spec.gate_factor
                    * self._conjunctive_activation(s, spec.premise_indices)
                )
                if spec.polarity > 0:
                    e_i += contrib
                elif spec.polarity < 0:
                    e_i -= contrib
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
        hyperedges: Sequence[HyperedgeSpec] | None = None,
    ) -> tuple[np.ndarray, bool, dict[str, np.ndarray]]:
        """Solve for dialectical equilibrium state over argument network or bipartite hypergraph.

        Parameters
        ----------
        base_scores : np.ndarray
            Vector of prior base plausibilities w in [0, 1]^N.
        g_supp : np.ndarray
            N x N adjacency matrix of support relation weights (j -> i at g_supp[j, i]).
        g_att : np.ndarray
            N x N adjacency matrix of attack relation weights (j -> i at g_att[j, i]).
        hyperedges : Sequence of HyperedgeSpec or None, optional
            Reified conjunctive and warrant-modulated inference specifications.

        Returns
        -------
        s_final : np.ndarray
            Converged justification degrees tau* in [0, 1]^N.
        converged : bool
            Whether numerical equilibrium tolerance was attained.
        telemetry : dict[str, np.ndarray]
            Diagnostic arrays: support_energy, attack_energy, total_weight_of_evidence,
            volatility_index, and warrant_states.
        """
        n = len(base_scores)
        hyper_list: tuple[HyperedgeSpec, ...] = tuple(hyperedges) if hyperedges else ()
        if n == 0:
            empty = np.array([], dtype=np.float64)
            return (
                empty,
                True,
                {
                    "support_energy": empty,
                    "attack_energy": empty,
                    "total_weight_of_evidence": empty,
                    "volatility_index": empty,
                    "warrant_states": empty,
                    "final_residual": np.array([0.0], dtype=np.float64),
                },
            )

        w = np.clip(base_scores, 0.0, 1.0)
        g_supp_t = g_supp.T
        g_att_t = g_att.T
        m = len(hyper_list)

        # Build unified bipartite graph (0..n-1 = atoms, n..n+m-1 = warrants)
        adj = (g_supp + g_att) > 0
        g_nx = nx.DiGraph(adj)
        if m > 0:
            for k, spec in enumerate(hyper_list):
                w_node = n + k
                g_nx.add_node(w_node)
                for p_idx in spec.premise_indices:
                    g_nx.add_edge(p_idx, w_node)
                for b_idxs, _ in spec.backing_edges:
                    for b_idx in b_idxs:
                        g_nx.add_edge(b_idx, w_node)
                for u_idxs, _ in spec.undercut_edges:
                    for u_idx in u_idxs:
                        g_nx.add_edge(u_idx, w_node)
                if spec.target_warrant_idx is not None:
                    g_nx.add_edge(w_node, n + spec.target_warrant_idx)
                elif 0 <= spec.target_idx < n:
                    g_nx.add_edge(w_node, spec.target_idx)

        final_residual = 0.0
        if nx.is_directed_acyclic_graph(g_nx):
            # Exact closed-form evaluation along topological order in O(|A| + |W| + |E|)
            topo_order = list(nx.topological_sort(g_nx))
            s_final = self._solve_dag_closed_form(
                w, g_supp_t, g_att_t, topo_order, hyperedges=hyper_list
            )
            s_w = self._compute_warrant_states(s_final, hyper_list)
            converged = True
        else:
            # Cyclic topology: adaptive continuous ODE integration over [atoms, warrants]
            w_warrants = (
                np.array(
                    [np.clip(h.base_warrant, 0.0, 1.0) for h in hyper_list],
                    dtype=np.float64,
                )
                if m > 0
                else np.array([], dtype=np.float64)
            )
            s0 = np.concatenate([w, w_warrants]) if m > 0 else w.copy()
            ds0 = self._derivatives(0.0, s0, w, g_supp_t, g_att_t, hyper_list)
            init_residual = float(np.max(np.abs(ds0)))

            if init_residual < self.atol:
                s_final = np.clip(s0[:n], 0.0, 1.0)
                s_w = np.clip(s0[n:], 0.0, 1.0)
                final_residual = init_residual
                converged = True
            else:
                event_tol = max(self.atol, 1e-4)

                def stationary_event(
                    t: float,
                    s: np.ndarray,
                    w_arr: np.ndarray,
                    supp_t: np.ndarray,
                    att_t: np.ndarray,
                    hyper_seq: tuple[HyperedgeSpec, ...],
                ) -> float:
                    ds = self._derivatives(t, s, w_arr, supp_t, att_t, hyper_seq)
                    return float(np.max(np.abs(ds)) - event_tol)

                stationary_event.terminal = True
                stationary_event.direction = -1

                ode_rtol = min(self.rtol, 1e-5)
                ode_atol = min(self.atol, 1e-7)

                sol = solve_ivp(
                    fun=self._derivatives,
                    t_span=(0.0, self.t_max),
                    y0=s0,
                    args=(w, g_supp_t, g_att_t, hyper_list),
                    method="RK45",
                    rtol=ode_rtol,
                    atol=ode_atol,
                    max_step=self.max_step,
                    events=stationary_event,
                )

                # Fallback to implicit Radau if stiffness or integration failure occurs
                if not sol.success or sol.status < 0:
                    sol = solve_ivp(
                        fun=self._derivatives,
                        t_span=(0.0, self.t_max),
                        y0=s0,
                        args=(w, g_supp_t, g_att_t, hyper_list),
                        method="Radau",
                        rtol=ode_rtol,
                        atol=ode_atol,
                        events=stationary_event,
                    )

                y_end = sol.y[:, -1]
                ds_end = self._derivatives(
                    float(sol.t[-1]), y_end, w, g_supp_t, g_att_t, hyper_list
                )
                final_residual = float(np.max(np.abs(ds_end)))
                s_final = np.clip(y_end[:n], 0.0, 1.0)
                s_w = (
                    np.clip(y_end[n : n + m], 0.0, 1.0)
                    if m > 0
                    else np.array([], dtype=np.float64)
                )
                converged = bool(
                    sol.success
                    and (sol.status == 1 or final_residual <= max(event_tol * 2.0, 1e-3))
                )

        # Compute evidentiary weight Wt and support/attack controversy volatility V
        e_supp = np.array(g_supp_t @ s_final, dtype=np.float64)
        e_att = np.array(g_att_t @ s_final, dtype=np.float64)
        for k, spec in enumerate(hyper_list):
            if spec.target_warrant_idx is not None or spec.target_idx < 0:
                continue
            contrib = (
                float(s_w[k])
                * spec.gate_factor
                * self._conjunctive_activation(s_final, spec.premise_indices)
            )
            if spec.polarity > 0:
                e_supp[spec.target_idx] += contrib
            elif spec.polarity < 0:
                e_att[spec.target_idx] += contrib

        e_total = e_supp + e_att
        safe_total = np.where(e_total > 0.0, e_total, 1.0)
        weight_of_evidence = np.where(e_total > 0.0, e_total / (1.0 + e_total), 0.0)
        controversy = np.where(
            e_total > 0.0,
            1.0 - np.abs(e_supp - e_att) / safe_total,
            0.0,
        )
        volatility = weight_of_evidence * controversy

        telemetry = {
            "support_energy": e_supp,
            "attack_energy": e_att,
            "total_weight_of_evidence": e_total,
            "volatility_index": volatility,
            "warrant_states": s_w,
            "final_residual": np.array([final_residual], dtype=np.float64),
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
    perspective : str or None, optional
        Optional epistemic perspective filter (e.g., ``"author"``, ``"asserted"``,
        or an attributed agent/school identifier).
    isolate_suppositional : bool, default True
        Whether nodes with ``intensional_mode == "suppositional"`` (e.g., *Reductio*
        assumptions) have their base prior zeroed and outgoing cross-scope edges isolated.
    isolate_attributed : bool, default True
        Whether ``attributed`` / ``historical`` nodes are isolated from directly
        inflating or deflating ``asserted`` authorial claims when evaluating the
        author's theory base.
    t_norm : Literal["product", "godel"], default "product"
        Conjunctive t-norm operator applied across multi-premise inference sets
        (``"product"`` multiplicative t-norm or ``"godel"`` minimum t-norm).
    continuous_solver : WeightedQuadraticEnergySolver or None, optional
        Optional continuous Quadratic Energy solver injected for ``solve_continuous()``.
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
        perspective: str | None = None,
        isolate_suppositional: bool = True,
        isolate_attributed: bool = True,
        t_norm: Literal["product", "godel"] = "product",
        base_prior_policy: BasePriorPolicy | str = BasePriorPolicy.DESCRIPTIVE_AUTHORIAL,
        normative_hypothesis_prior: float = 0.5,
        normative_data_prior: float = 0.8,
        continuous_solver: WeightedQuadraticEnergySolver | None = None,
    ) -> None:
        if isinstance(semantics_model, str):
            semantics_model = GradualSemanticsModel(semantics_model.lower())
        if isinstance(base_prior_policy, str):
            base_prior_policy = BasePriorPolicy(base_prior_policy.strip().lower())
        self.semantics_model = semantics_model
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.admissibility_threshold = admissibility_threshold
        self.prune_inadmissible = prune_inadmissible
        self.admissibility_mode = admissibility_mode
        self.tau_p = tau_p
        self.tau_c = tau_c
        self.use_continuous = use_continuous
        self.perspective = perspective
        self.isolate_suppositional = isolate_suppositional
        self.isolate_attributed = isolate_attributed
        self.t_norm = _validate_t_norm(t_norm)
        self.base_prior_policy = base_prior_policy
        self.normative_hypothesis_prior = float(
            max(0.0, min(1.0, normative_hypothesis_prior))
        )
        self.normative_data_prior = float(max(0.0, min(1.0, normative_data_prior)))
        self.continuous_solver = continuous_solver or WeightedQuadraticEnergySolver(
            rtol=self.tolerance,
            atol=max(self.tolerance * 0.01, 1e-6),
            t_norm=self.t_norm,
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            Solver class identity and hypergraph/gradual-semantics hyperparameters.
        """
        return {
            "class": self.__class__.__name__,
            "semantics_model": self.semantics_model.value,
            "max_iterations": self.max_iterations,
            "tolerance": self.tolerance,
            "admissibility_threshold": self.admissibility_threshold,
            "prune_inadmissible": self.prune_inadmissible,
            "admissibility_mode": self.admissibility_mode,
            "tau_p": self.tau_p,
            "tau_c": self.tau_c,
            "use_continuous": self.use_continuous,
            "perspective": self.perspective,
            "isolate_suppositional": self.isolate_suppositional,
            "isolate_attributed": self.isolate_attributed,
            "t_norm": self.t_norm,
            "base_prior_policy": self.base_prior_policy.value,
            "normative_hypothesis_prior": self.normative_hypothesis_prior,
            "normative_data_prior": self.normative_data_prior,
            "continuous_solver": self.continuous_solver.fingerprint(),
        }

    @staticmethod
    def _partition_pairwise_and_hyperedges(
        admissible_edges: Sequence[_AdmissibleEdge],
        node_to_idx: Mapping[str, int],
        normalization_mode: WeightNormalizationMode = WeightNormalizationMode.CALIBRATED_MODAL,
    ) -> tuple[list[_AdmissibleEdge], list[HyperedgeSpec]]:
        """Partition admissible edges into pairwise edges and reified hyperedges."""
        explicit_edge_ids = {e.id for e in admissible_edges if e.id}
        explicit_warrant_ids = explicit_edge_ids | {
            e.undercuts_relation_id for e in admissible_edges if e.undercuts_relation_id
        }

        modifiers_by_target: dict[str, list[_AdmissibleEdge]] = {}
        primary_edges: list[_AdmissibleEdge] = []
        for edge in admissible_edges:
            if edge.undercuts_relation_id is not None or (
                edge.target in explicit_warrant_ids and edge.target not in node_to_idx
            ):
                target_w = edge.undercuts_relation_id or edge.target
                modifiers_by_target.setdefault(target_w, []).append(edge)
            else:
                primary_edges.append(edge)

        def _warrant_prior_and_gate(edge: _AdmissibleEdge) -> tuple[float, float]:
            if normalization_mode == WeightNormalizationMode.UNWEIGHTED_BINARY:
                return 1.0, float(edge.weight)
            w0 = float(np.clip(edge.base_warrant, 0.0, 1.0))
            gate_factor = (edge.weight / w0) if w0 > 1e-12 else 1.0
            return w0, gate_factor

        targeted_warrant_ids = set(modifiers_by_target.keys())
        pairwise: list[_AdmissibleEdge] = []
        hyperedges: list[HyperedgeSpec] = []
        warrant_idx_by_id: dict[str, int] = {}
        expansion_queue: list[tuple[int, str]] = []

        for idx, edge in enumerate(primary_edges):
            raw_premises = (
                edge.premise_ids
                if edge.premise_ids
                else ((edge.source,) if edge.source else ())
            )
            is_conjunctive = len(raw_premises) > 1
            is_targeted = edge.id is not None and edge.id in targeted_warrant_ids

            if not (is_conjunctive or is_targeted):
                pairwise.append(edge)
                continue

            target_idx = node_to_idx.get(edge.target)
            if target_idx is None:
                continue
            premise_indices = tuple(
                node_to_idx[p] for p in raw_premises if p in node_to_idx
            )
            if len(premise_indices) != len(raw_premises) or not premise_indices:
                continue

            w0, gate_factor = _warrant_prior_and_gate(edge)
            warrant_id = edge.id or (
                f"inf::{'&'.join(raw_premises)}->{edge.target}#{idx}"
            )

            backing_list: list[tuple[tuple[int, ...], float]] = []
            undercut_list: list[tuple[tuple[int, ...], float]] = []
            has_child_targeted = False
            for mod in modifiers_by_target.get(warrant_id, ()):
                mod_raw_prems = (
                    mod.premise_ids
                    if mod.premise_ids
                    else ((mod.source,) if mod.source else ())
                )
                mod_idxs = tuple(
                    node_to_idx[p] for p in mod_raw_prems if p in node_to_idx
                )
                if len(mod_idxs) != len(mod_raw_prems) or not mod_idxs:
                    continue
                if (
                    mod.id is not None
                    and mod.id in targeted_warrant_ids
                    and mod.id != warrant_id
                ):
                    has_child_targeted = True
                elif mod.polarity > 0:
                    backing_list.append((mod_idxs, mod.weight))
                elif mod.polarity < 0:
                    undercut_list.append((mod_idxs, mod.weight))

            parent_idx = len(hyperedges)
            warrant_idx_by_id[warrant_id] = parent_idx
            hyperedges.append(
                HyperedgeSpec(
                    warrant_id=warrant_id,
                    premise_indices=premise_indices,
                    target_idx=target_idx,
                    polarity=edge.polarity,
                    base_warrant=w0,
                    gate_factor=gate_factor,
                    backing_edges=tuple(backing_list),
                    undercut_edges=tuple(undercut_list),
                )
            )
            if has_child_targeted:
                expansion_queue.append((parent_idx, warrant_id))

        q_pos = 0
        while q_pos < len(expansion_queue):
            parent_idx, parent_wid = expansion_queue[q_pos]
            q_pos += 1
            for mod in modifiers_by_target.get(parent_wid, ()):
                if mod.id is None or mod.id not in targeted_warrant_ids:
                    continue
                if mod.id in warrant_idx_by_id:
                    continue
                mod_raw_prems = (
                    mod.premise_ids
                    if mod.premise_ids
                    else ((mod.source,) if mod.source else ())
                )
                mod_idxs = tuple(
                    node_to_idx[p] for p in mod_raw_prems if p in node_to_idx
                )
                if len(mod_idxs) != len(mod_raw_prems) or not mod_idxs:
                    continue

                mod_w0, mod_gate = _warrant_prior_and_gate(mod)
                sub_back: list[tuple[tuple[int, ...], float]] = []
                sub_und: list[tuple[tuple[int, ...], float]] = []
                has_sub_targeted = False
                for sub_mod in modifiers_by_target.get(mod.id, ()):
                    sub_raw_prems = (
                        sub_mod.premise_ids
                        if sub_mod.premise_ids
                        else ((sub_mod.source,) if sub_mod.source else ())
                    )
                    sub_idxs = tuple(
                        node_to_idx[p] for p in sub_raw_prems if p in node_to_idx
                    )
                    if len(sub_idxs) != len(sub_raw_prems) or not sub_idxs:
                        continue
                    if (
                        sub_mod.id is not None
                        and sub_mod.id in targeted_warrant_ids
                        and sub_mod.id != mod.id
                    ):
                        has_sub_targeted = True
                    elif sub_mod.polarity > 0:
                        sub_back.append((sub_idxs, sub_mod.weight))
                    elif sub_mod.polarity < 0:
                        sub_und.append((sub_idxs, sub_mod.weight))

                mod_idx = len(hyperedges)
                warrant_idx_by_id[mod.id] = mod_idx
                hyperedges.append(
                    HyperedgeSpec(
                        warrant_id=mod.id,
                        premise_indices=mod_idxs,
                        target_idx=-1,
                        polarity=mod.polarity,
                        base_warrant=mod_w0,
                        gate_factor=mod_gate,
                        backing_edges=tuple(sub_back),
                        undercut_edges=tuple(sub_und),
                        target_warrant_idx=parent_idx,
                    )
                )
                if has_sub_targeted:
                    expansion_queue.append((mod_idx, mod.id))

        return pairwise, hyperedges

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
        perspective: str | None = None,
        isolate_suppositional: bool | None = None,
        isolate_attributed: bool | None = None,
        base_prior_policy: BasePriorPolicy | str | None = None,
    ) -> QBAFSolverResult:
        """Compute equilibrium justification degrees over an argumentation network."""
        if continuous is True or (continuous is None and self.use_continuous):
            return self.solve_continuous(
                nodes=nodes,
                edges=edges,
                normalization_mode=normalization_mode,
                admissibility_mode=admissibility_mode,
                tau_p=tau_p,
                tau_c=tau_c,
                perspective=perspective,
                isolate_suppositional=isolate_suppositional,
                isolate_attributed=isolate_attributed,
                base_prior_policy=base_prior_policy,
            )

        if isinstance(normalization_mode, str):
            normalization_mode = WeightNormalizationMode(normalization_mode.lower())

        eff_policy = (
            BasePriorPolicy(base_prior_policy.strip().lower())
            if isinstance(base_prior_policy, str)
            else (base_prior_policy or self.base_prior_policy)
        )
        active_adm_mode = admissibility_mode or self.admissibility_mode
        active_tau_p = tau_p if tau_p is not None else self.tau_p
        active_tau_c = tau_c if tau_c is not None else self.tau_c
        active_perspective = (
            perspective if perspective is not None else self.perspective
        )

        (
            base_tau,
            admissible_edges,
            admissibility_pruned,
            suppositional_isolated,
            perspective_filtered,
        ) = self._prepare_graph_data(
            nodes=nodes,
            edges=edges,
            normalization_mode=normalization_mode,
            active_adm_mode=active_adm_mode,
            active_tau_p=active_tau_p,
            active_tau_c=active_tau_c,
            perspective=perspective,
            isolate_suppositional=isolate_suppositional,
            isolate_attributed=isolate_attributed,
            base_prior_policy=eff_policy,
        )

        node_list = list(base_tau.keys())
        node_to_idx = {nid: i for i, nid in enumerate(node_list)}
        pairwise_edges, hyperedges = self._partition_pairwise_and_hyperedges(
            admissible_edges,
            node_to_idx,
            normalization_mode=normalization_mode,
        )
        hyper_mods_by_target: dict[int, list[tuple[int, HyperedgeSpec]]] = {}
        for mod_k, h_spec in enumerate(hyperedges):
            if h_spec.target_warrant_idx is not None:
                hyper_mods_by_target.setdefault(h_spec.target_warrant_idx, []).append(
                    (mod_k, h_spec)
                )

        incoming_edges: dict[str, list[_AdmissibleEdge]] = {nid: [] for nid in base_tau}
        for edge in pairwise_edges:
            if edge.target in incoming_edges:
                incoming_edges[edge.target].append(edge)

        # Iterative Gradual Semantics Convergence Loop
        tau_current: dict[str, float] = dict(base_tau)
        warrant_states: dict[str, float] = {
            spec.warrant_id: spec.base_warrant for spec in hyperedges
        }
        final_delta = 0.0
        converged = False
        iteration_count = 0

        support_energy: dict[str, float] = {nid: 0.0 for nid in base_tau}
        attack_energy: dict[str, float] = {nid: 0.0 for nid in base_tau}

        for it in range(self.max_iterations):
            iteration_count = it + 1
            max_delta = 0.0
            tau_next: dict[str, float] = {}
            s_vec = [tau_current[nid] for nid in node_list]

            hyper_supp: dict[str, float] = {nid: 0.0 for nid in base_tau}
            hyper_att: dict[str, float] = {nid: 0.0 for nid in base_tau}
            s_w_prev = [warrant_states[spec.warrant_id] for spec in hyperedges]
            for k_idx, spec in enumerate(hyperedges):
                e_back = sum(
                    w_b * _conjunctive_t_norm([s_vec[i] for i in b_idxs], self.t_norm)
                    for b_idxs, w_b in spec.backing_edges
                )
                e_und = sum(
                    w_u * _conjunctive_t_norm([s_vec[i] for i in u_idxs], self.t_norm)
                    for u_idxs, w_u in spec.undercut_edges
                )
                for mod_k, mod_spec in hyper_mods_by_target.get(k_idx, ()):
                    mod_contrib = (
                        s_w_prev[mod_k]
                        * mod_spec.gate_factor
                        * _conjunctive_t_norm(
                            [s_vec[i] for i in mod_spec.premise_indices], self.t_norm
                        )
                    )
                    if mod_spec.polarity > 0:
                        e_back += mod_contrib
                    elif mod_spec.polarity < 0:
                        e_und += mod_contrib
                w_new = self._compute_update(
                    tau_0=spec.base_warrant,
                    support=e_back,
                    attack=e_und,
                    model=self.semantics_model,
                )
                max_delta = max(max_delta, abs(w_new - s_w_prev[k_idx]))
                warrant_states[spec.warrant_id] = w_new

                if spec.target_warrant_idx is not None or spec.target_idx < 0:
                    continue
                conj_act = _conjunctive_t_norm(
                    [s_vec[i] for i in spec.premise_indices], self.t_norm
                )
                contrib = w_new * spec.gate_factor * conj_act
                tgt_nid = node_list[spec.target_idx]
                if spec.polarity > 0:
                    hyper_supp[tgt_nid] += contrib
                elif spec.polarity < 0:
                    hyper_att[tgt_nid] += contrib

            for nid in base_tau:
                tau_0 = base_tau[nid]
                s_sum = hyper_supp[nid]
                a_sum = hyper_att[nid]

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
                max_delta = max(max_delta, delta)

                tau_next[nid] = updated_val

            tau_current = tau_next
            final_delta = max_delta

            if max_delta < self.tolerance:
                converged = True
                break

        # Compute evidentiary weight Wt and support/attack controversy volatility V
        total_evidence: dict[str, float] = {}
        volatility: dict[str, float] = {}
        for nid in base_tau:
            e_supp = support_energy[nid]
            e_att = attack_energy[nid]
            e_tot = e_supp + e_att
            vol = (
                (e_tot / (1.0 + e_tot)) * (1.0 - abs(e_supp - e_att) / e_tot)
                if e_tot > 0.0
                else 0.0
            )
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
            perspective=active_perspective,
            suppositional_isolated_count=suppositional_isolated,
            perspective_filtered_count=perspective_filtered,
            warrant_states={k: round(v, 6) for k, v in warrant_states.items()},
            base_prior_policy=eff_policy,
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
        perspective: str | None = None,
        isolate_suppositional: bool | None = None,
        isolate_attributed: bool | None = None,
        base_prior_policy: BasePriorPolicy | str | None = None,
    ) -> QBAFSolverResult:
        """Solve QBAF equilibrium using the unified continuous WeightedQuadraticEnergySolver."""
        if isinstance(normalization_mode, str):
            normalization_mode = WeightNormalizationMode(normalization_mode.lower())

        eff_policy = (
            BasePriorPolicy(base_prior_policy.strip().lower())
            if isinstance(base_prior_policy, str)
            else (base_prior_policy or self.base_prior_policy)
        )
        active_adm_mode = admissibility_mode or self.admissibility_mode
        active_tau_p = tau_p if tau_p is not None else self.tau_p
        active_tau_c = tau_c if tau_c is not None else self.tau_c
        active_perspective = (
            perspective if perspective is not None else self.perspective
        )

        (
            base_tau,
            admissible_edges,
            admissibility_pruned,
            suppositional_isolated,
            perspective_filtered,
        ) = self._prepare_graph_data(
            nodes=nodes,
            edges=edges,
            normalization_mode=normalization_mode,
            active_adm_mode=active_adm_mode,
            active_tau_p=active_tau_p,
            active_tau_c=active_tau_c,
            perspective=perspective,
            isolate_suppositional=isolate_suppositional,
            isolate_attributed=isolate_attributed,
            base_prior_policy=eff_policy,
        )

        node_list = list(base_tau.keys())
        node_to_idx = {nid: i for i, nid in enumerate(node_list)}
        n = len(node_list)

        base_scores = np.array([base_tau[nid] for nid in node_list], dtype=np.float64)
        g_supp = np.zeros((n, n), dtype=np.float64)
        g_att = np.zeros((n, n), dtype=np.float64)

        pairwise_edges, hyperedges = self._partition_pairwise_and_hyperedges(
            admissible_edges,
            node_to_idx,
            normalization_mode=normalization_mode,
        )
        for edge in pairwise_edges:
            u = node_to_idx[edge.source]
            v = node_to_idx[edge.target]
            if edge.polarity > 0:
                g_supp[u, v] += edge.weight
            elif edge.polarity < 0:
                g_att[u, v] += edge.weight

        ode_solver = (
            self.continuous_solver
            if self.continuous_solver.t_norm == self.t_norm
            else WeightedQuadraticEnergySolver(
                rtol=self.continuous_solver.rtol,
                atol=self.continuous_solver.atol,
                t_max=self.continuous_solver.t_max,
                max_step=self.continuous_solver.max_step,
                t_norm=self.t_norm,
            )
        )
        s_final, converged, telemetry = ode_solver.solve(
            base_scores,
            g_supp,
            g_att,
            hyperedges=hyperedges,
        )

        degrees = {nid: round(float(s_final[i]), 6) for i, nid in enumerate(node_list)}
        support_sums = {
            nid: round(float(telemetry["support_energy"][i]), 6)
            for i, nid in enumerate(node_list)
        }
        attack_sums = {
            nid: round(float(telemetry["attack_energy"][i]), 6)
            for i, nid in enumerate(node_list)
        }
        total_evidence = {
            nid: round(float(telemetry["total_weight_of_evidence"][i]), 6)
            for i, nid in enumerate(node_list)
        }
        volatility = {
            nid: round(float(telemetry["volatility_index"][i]), 6)
            for i, nid in enumerate(node_list)
        }
        warrant_states_arr = telemetry.get("warrant_states")
        warrant_states = (
            {
                spec.warrant_id: round(float(warrant_states_arr[k]), 6)
                for k, spec in enumerate(hyperedges)
            }
            if warrant_states_arr is not None
            and len(warrant_states_arr) == len(hyperedges)
            else {}
        )

        final_res_arr = telemetry.get("final_residual")
        final_delta_val = (
            round(float(final_res_arr[0]), 8)
            if final_res_arr is not None and len(final_res_arr) > 0
            else 0.0
        )

        return QBAFSolverResult(
            degrees=degrees,
            iterations=1,
            converged=converged,
            final_delta=final_delta_val,
            normalization_mode=normalization_mode,
            semantics_model=GradualSemanticsModel.QUADRATIC,
            support_sums=support_sums,
            attack_sums=attack_sums,
            total_weight_of_evidence=total_evidence,
            volatility_index=volatility,
            admissibility_pruned_count=admissibility_pruned,
            perspective=active_perspective,
            suppositional_isolated_count=suppositional_isolated,
            perspective_filtered_count=perspective_filtered,
            warrant_states=warrant_states,
            base_prior_policy=eff_policy,
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
                if (c_diff > 1e-4 and u_diff < -1e-4) or (
                    c_diff < -1e-4 and u_diff > 1e-4
                ):
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

    def _evaluate_admissibility_gate(
        self,
        eff_w: float,
        acc: float | None,
        p_stance: float | None,
        model_conf: float | None,
        normalization_mode: WeightNormalizationMode,
        active_adm_mode: Literal["hard", "soft"],
        active_tau_p: float,
        active_tau_c: float,
    ) -> tuple[bool, float, bool]:
        """Apply hard or soft empirical admissibility gating to a single parsed edge.

        Returns
        -------
        tuple of (bool, float, bool)
            ``(keep_edge, resolved_weight, was_pruned)``.
        """
        if active_adm_mode == "hard":
            is_inadmissible = False
            if (
                self.admissibility_threshold > 0.0
                and acc is not None
                and acc < self.admissibility_threshold
            ):
                is_inadmissible = True
            if active_tau_p > 0.0 and p_stance is not None and p_stance < active_tau_p:
                is_inadmissible = True
            if (
                active_tau_c > 0.0
                and model_conf is not None
                and model_conf < active_tau_c
            ):
                is_inadmissible = True

            if is_inadmissible:
                if self.prune_inadmissible:
                    return False, 0.0, True
                return True, 0.0, True

            final_w = (
                1.0
                if normalization_mode == WeightNormalizationMode.UNWEIGHTED_BINARY
                else eff_w
            )
            return True, final_w, False

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
        final_w = (
            1.0 * f_soft
            if normalization_mode == WeightNormalizationMode.UNWEIGHTED_BINARY
            else eff_w * f_soft
        )
        return True, final_w, False

    def _resolve_reductio_discharge(
        self,
        sup_nodes: set[str],
        active_refuters: set[str],
        in_persp_non_sup: set[str],
        raw_base_tau: dict[str, float],
        sup_candidate_edges: list[_AdmissibleEdge],
    ) -> tuple[set[str], list[_AdmissibleEdge]]:
        """Resolve refuted *Reductio ad absurdum* chains and discharge refutation energy.

        Unrefuted suppositional subgraphs retain ``0.0`` base priors and emit no
        cross-scope edges. When an active non-suppositional proposition attacks a
        suppositional consequence :math:`Q` (or directly attacks assumption :math:`S`),
        refutation propagates backward along ``SUPPORTS`` derivations via *modus
        tollens* and discharges the drop :math:`\\Delta_{\\text{ref}}(S) = \\tau_0(S) - \\tau^*(S)`
        onto linked asserted theses without polluting unrefuted claims.
        """

        def _edge_premises(edge: _AdmissibleEdge) -> tuple[str, ...]:
            return (
                edge.premise_ids
                if edge.premise_ids
                else ((edge.source,) if edge.source else ())
            )

        direct_refutations = [
            e
            for e in sup_candidate_edges
            if e.polarity < 0
            and e.weight > 0.0
            and _edge_premises(e)
            and all(p in active_refuters for p in _edge_premises(e))
            and e.target in sup_nodes
        ]
        if not direct_refutations:
            return set(), []

        # Reverse adjacency along suppositional (and mixed conjunctive) --SUPPORTS--> suppositional edges
        rev_supp: dict[str, list[tuple[str, float]]] = {nid: [] for nid in sup_nodes}
        for e in sup_candidate_edges:
            if e.target not in sup_nodes or e.polarity <= 0 or e.weight <= 0.0:
                continue
            premises = _edge_premises(e)
            sup_prems = [p for p in premises if p in sup_nodes]
            if not sup_prems:
                continue
            non_sup_prems = [p for p in premises if p not in sup_nodes]
            if any(raw_base_tau.get(p, 0.0) <= 0.0 for p in non_sup_prems):
                continue
            non_sup_scale = (
                _conjunctive_t_norm(
                    [raw_base_tau[p] for p in non_sup_prems], self.t_norm
                )
                if non_sup_prems
                else 1.0
            )
            eff_sup_w = e.weight * non_sup_scale
            for sp in sup_prems:
                rev_supp[e.target].append((sp, eff_sup_w))

        # Track (refuter -> sup_node) maximal contrapositive attack weight along simple paths
        refuted_sup_nodes: set[str] = set()
        direct_attack_pairs: set[tuple[str, str]] = set()
        mt_weight_map: dict[tuple[str, str], float] = {}
        refuter_contrib: dict[str, dict[str, float]] = {}

        for e in direct_refutations:
            prems = _edge_premises(e)
            refuted_sup_nodes.add(e.target)
            refuter_contrib.setdefault(e.target, {})
            if len(prems) == 1:
                step_contribs = [(e.source, e.weight)]
            else:
                ref_act = _conjunctive_t_norm(
                    [raw_base_tau[p] for p in prems], self.t_norm
                )
                step_contribs = [
                    (
                        r_id,
                        (e.weight * ref_act)
                        / (len(prems) * max(raw_base_tau.get(r_id, 0.0), 1e-12)),
                    )
                    for r_id in prems
                ]

            for r_id, base_w in step_contribs:
                direct_attack_pairs.add((r_id, e.target))
                refuter_contrib[e.target][r_id] = (
                    refuter_contrib[e.target].get(r_id, 0.0) + base_w
                )

                # BFS/DFS backward along SUPPORTS to propagate modus tollens refutation
                stack: list[tuple[str, float, frozenset[str]]] = [
                    (e.target, base_w, frozenset({e.target}))
                ]
                while stack:
                    curr, path_w, visited = stack.pop()
                    for prev_sup, edge_w in rev_supp.get(curr, ()):
                        if prev_sup in visited:
                            continue
                        prop_w = min(1.0, path_w * edge_w)
                        if prop_w <= 0.0:
                            continue
                        refuted_sup_nodes.add(prev_sup)
                        pair_key = (r_id, prev_sup)
                        if prop_w > mt_weight_map.get(pair_key, 0.0):
                            mt_weight_map[pair_key] = prop_w
                        refuter_contrib.setdefault(prev_sup, {})
                        if prop_w > refuter_contrib[prev_sup].get(r_id, 0.0):
                            refuter_contrib[prev_sup][r_id] = prop_w
                        stack.append((prev_sup, prop_w, visited | {prev_sup}))

        internal_sup_edges = [
            e
            for e in sup_candidate_edges
            if e.target in refuted_sup_nodes
            and any(p in sup_nodes for p in _edge_premises(e))
            and all(
                (p in refuted_sup_nodes) or (p not in sup_nodes)
                for p in _edge_premises(e)
            )
        ]
        mt_edges = [
            _AdmissibleEdge(source=r_id, target=s_id, polarity=-1, weight=w_mt)
            for (r_id, s_id), w_mt in mt_weight_map.items()
            if (r_id, s_id) not in direct_attack_pairs
        ]

        # Local fixed-point evaluation of the refuted suppositional component
        local_edges = direct_refutations + internal_sup_edges + mt_edges
        active_r_nodes = {p for e in direct_refutations for p in _edge_premises(e)}
        aux_non_sup_nodes = {
            p
            for e in internal_sup_edges
            for p in _edge_premises(e)
            if p not in sup_nodes
        }
        tau_sub: dict[str, float] = {
            nid: raw_base_tau[nid]
            for nid in (refuted_sup_nodes | active_r_nodes | aux_non_sup_nodes)
        }
        inc_by_target: dict[str, list[_AdmissibleEdge]] = {
            nid: [] for nid in refuted_sup_nodes
        }
        for e in local_edges:
            if e.target in inc_by_target:
                inc_by_target[e.target].append(e)

        iters = max(20, min(self.max_iterations, 50))
        for _ in range(iters):
            next_tau = dict(tau_sub)
            max_delta = 0.0
            for nid in refuted_sup_nodes:
                s_sum = 0.0
                a_sum = 0.0
                for inc in inc_by_target.get(nid, ()):
                    inc_prems = _edge_premises(inc)
                    if not inc_prems:
                        continue
                    act = _conjunctive_t_norm(
                        [tau_sub[p] for p in inc_prems], self.t_norm
                    )
                    if inc.polarity > 0:
                        s_sum += act * inc.weight
                    elif inc.polarity < 0:
                        a_sum += act * inc.weight
                updated = self._compute_update(
                    tau_0=raw_base_tau[nid],
                    support=s_sum,
                    attack=a_sum,
                    model=self.semantics_model,
                )
                max_delta = max(max_delta, abs(updated - tau_sub[nid]))
                next_tau[nid] = updated
            tau_sub = next_tau
            if max_delta < self.tolerance:
                break

        discharged_edges: list[_AdmissibleEdge] = []
        for e in sup_candidate_edges:
            # Discharge applies only when a refuted supposition (alone or conjunctively)
            # attacked an in-perspective non-suppositional claim (indirect proof: ¬S |- T).
            premises = _edge_premises(e)
            sup_prems = [p for p in premises if p in sup_nodes]
            refuted_prems = [p for p in premises if p in refuted_sup_nodes]
            if (
                not refuted_prems
                or len(refuted_prems) != len(sup_prems)
                or e.target not in in_persp_non_sup
                or e.polarity >= 0
                or e.weight <= 0.0
            ):
                continue
            prior_act = _conjunctive_t_norm(
                [raw_base_tau[p] for p in premises], self.t_norm
            )
            post_act = _conjunctive_t_norm(
                [tau_sub.get(p, raw_base_tau[p]) for p in premises], self.t_norm
            )
            delta_ref = max(0.0, prior_act - post_act)
            if delta_ref <= 1e-6:
                continue
            contribs: dict[str, float] = {}
            for sp in refuted_prems:
                for r_id, c_val in refuter_contrib.get(sp, {}).items():
                    contribs[r_id] = contribs.get(r_id, 0.0) + c_val
            total_c = sum(contribs.values())
            if total_c <= 0.0:
                continue
            discharged_energy = delta_ref * e.weight
            for r_id, c_val in contribs.items():
                share = c_val / total_c
                ref_tau = max(tau_sub.get(r_id, 0.0), 1e-6)
                discharge_w = min(1.0, (share * discharged_energy) / ref_tau)
                if discharge_w > 0.0:
                    discharged_edges.append(
                        _AdmissibleEdge(
                            source=r_id,
                            target=e.target,
                            polarity=1,
                            weight=discharge_w,
                        )
                    )

        return refuted_sup_nodes, local_edges + discharged_edges

    def _prepare_graph_data(
        self,
        nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
        edges: Sequence[Any] | None,
        normalization_mode: WeightNormalizationMode,
        active_adm_mode: Literal["hard", "soft"],
        active_tau_p: float,
        active_tau_c: float,
        perspective: str | None = None,
        isolate_suppositional: bool | None = None,
        isolate_attributed: bool | None = None,
        base_prior_policy: BasePriorPolicy | None = None,
    ) -> tuple[dict[str, float], list[_AdmissibleEdge], int, int, int]:
        """Normalize node base plausibilities, apply intensional scoping, and filter edges."""
        if isinstance(nodes, TheoryGraph):
            raw_nodes: Mapping[str, Any] | Sequence[Any] = nodes.nodes
            raw_edges: Sequence[Any] = edges if edges is not None else nodes.edges
        else:
            raw_nodes = nodes
            raw_edges = edges if edges is not None else ()

        eff_policy = base_prior_policy or self.base_prior_policy
        eff_perspective = perspective if perspective is not None else self.perspective
        active_perspective = (
            eff_perspective.strip().lower() if eff_perspective is not None else None
        )
        eff_isolate_sup = (
            self.isolate_suppositional
            if isolate_suppositional is None
            else isolate_suppositional
        )
        eff_isolate_attr = (
            self.isolate_attributed
            if isolate_attributed is None
            else isolate_attributed
        )

        def _is_evidential_node(obj: Any) -> bool:
            if isinstance(obj, TheoryNode):
                if obj.node_type == NodeType.EVIDENCE:
                    return True
                if obj.semantic_sentence_type == "EMPIRICAL":
                    return True
                comp_t = str(obj.attributes.get("component_type", "")).strip().lower()
                return comp_t in _EVIDENTIAL_NODE_TYPES
            if isinstance(obj, BaseModel):
                return _is_evidential_node(obj.model_dump())
            if isinstance(obj, Mapping):
                if str(obj.get("semantic_sentence_type", "")).upper() == "EMPIRICAL":
                    return True
                nt = (
                    str(obj.get("node_type") or obj.get("component_type") or "")
                    .strip()
                    .lower()
                )
                return nt in _EVIDENTIAL_NODE_TYPES
            return False

        raw_base_tau: dict[str, float] = {}
        node_modes: dict[str, str] = {}
        node_attributions: dict[str, str | None] = {}
        evidential_nodes: set[str] = set()

        if isinstance(raw_nodes, Mapping):
            for nid, val in raw_nodes.items():
                nid_str = str(nid)
                if isinstance(val, (int, float)):
                    raw_base_tau[nid_str] = max(0.0, min(1.0, float(val)))
                    node_modes[nid_str] = "asserted"
                    node_attributions[nid_str] = None
                else:
                    _, extracted_tau, mode, attr = self._extract_node_spec(val)
                    raw_base_tau[nid_str] = max(0.0, min(1.0, extracted_tau))
                    node_modes[nid_str] = mode
                    node_attributions[nid_str] = attr
                    if _is_evidential_node(val):
                        evidential_nodes.add(nid_str)
        else:
            for item in raw_nodes:
                nid, val, mode, attr = self._extract_node_spec(item)
                raw_base_tau[nid] = max(0.0, min(1.0, val))
                node_modes[nid] = mode
                node_attributions[nid] = attr
                if _is_evidential_node(item):
                    evidential_nodes.add(nid)

        if eff_policy == BasePriorPolicy.NORMATIVE_UNIFORM:
            for nid in list(raw_base_tau.keys()):
                raw_base_tau[nid] = self.normative_hypothesis_prior
        elif eff_policy == BasePriorPolicy.NORMATIVE_DATA_PRIORITY:
            for nid in list(raw_base_tau.keys()):
                raw_base_tau[nid] = (
                    self.normative_data_prior
                    if nid in evidential_nodes
                    else self.normative_hypothesis_prior
                )

        # Parse all edges and skip non-dialectical structural edges (e.g. ALTERNATIVE_READING_OF)
        parsed_edges: list[_ParsedEdge] = []
        for edge_item in raw_edges:
            parsed = self._parse_edge(edge_item)
            if not parsed or parsed.polarity == 0:
                continue
            parsed_edges.append(parsed)

        explicit_edge_ids = {pe.id for pe in parsed_edges if pe.id}
        undercut_target_ids = {
            pe.undercuts_relation_id for pe in parsed_edges if pe.undercuts_relation_id
        }
        explicit_warrant_ids = explicit_edge_ids | undercut_target_ids
        warrant_parent_map: dict[str, str] = {}
        target_atom_by_warrant: dict[str, str] = {}
        for pe in parsed_edges:
            if not pe.id:
                continue
            direct_tgt = pe.undercuts_relation_id or pe.target
            if (
                pe.undercuts_relation_id is None
                and pe.target not in explicit_warrant_ids
            ):
                target_atom_by_warrant[pe.id] = pe.target
            elif direct_tgt:
                warrant_parent_map[pe.id] = direct_tgt

        def _resolve_ultimate_atom(w_id: str) -> str | None:
            curr = w_id
            seen: set[str] = set()
            while curr not in target_atom_by_warrant:
                if curr in seen or curr not in warrant_parent_map:
                    return None
                seen.add(curr)
                curr = warrant_parent_map[curr]
            return target_atom_by_warrant[curr]

        for wid in list(warrant_parent_map.keys()):
            atom_tgt = _resolve_ultimate_atom(wid)
            if atom_tgt is not None:
                target_atom_by_warrant[wid] = atom_tgt

        # Never treat explicit or referenced inference/warrant IDs as atom nodes in base_scores
        for wid in explicit_warrant_ids:
            raw_base_tau.pop(wid, None)
            node_modes.pop(wid, None)
            node_attributions.pop(wid, None)

        default_unseen_tau = (
            0.0
            if active_perspective is not None
            and active_perspective not in ("all", "suppositional")
            else 0.5
        )
        for pe in parsed_edges:
            atom_endpoints = (
                list(pe.premise_ids)
                if pe.premise_ids
                else ([pe.source] if pe.source else [])
            )
            if (
                pe.target
                and pe.undercuts_relation_id is None
                and pe.target not in explicit_warrant_ids
            ):
                atom_endpoints.append(pe.target)
            for ep in atom_endpoints:
                if ep not in raw_base_tau:
                    raw_base_tau[ep] = default_unseen_tau
                    node_modes.setdefault(ep, "asserted")
                    node_attributions.setdefault(ep, None)

        def _is_unattributed(nid: str) -> bool:
            attr_norm = (node_attributions.get(nid) or "").strip().lower()
            return attr_norm in ("", "author", "self")

        def _is_authorial(nid: str) -> bool:
            mode = node_modes.get(nid, "asserted")
            allowed_modes = (
                ("asserted", "historical")
                if eff_isolate_sup
                else ("asserted", "historical", "suppositional")
            )
            return mode in allowed_modes and _is_unattributed(nid)

        def _matches_agent(nid: str, agent_norm: str) -> bool:
            mode = node_modes.get(nid, "asserted")
            if eff_isolate_sup and mode == "suppositional":
                return False
            attr_norm = (node_attributions.get(nid) or "").strip().lower()
            if attr_norm == agent_norm:
                return True
            return mode == "historical" and _is_unattributed(nid)

        sup_nodes = {nid for nid, mode in node_modes.items() if mode == "suppositional"}
        sup_isolation_active = eff_isolate_sup and active_perspective != "suppositional"
        suppositional_isolated = len(sup_nodes) if sup_isolation_active else 0

        in_persp: dict[str, bool] = {}
        for nid in raw_base_tau:
            mode = node_modes.get(nid, "asserted")
            if sup_isolation_active and mode == "suppositional":
                in_persp[nid] = False
            elif active_perspective is None or active_perspective in (
                "all",
                "suppositional",
            ):
                in_persp[nid] = True
            elif active_perspective in ("author", "asserted"):
                in_persp[nid] = _is_authorial(nid)
            else:
                in_persp[nid] = _matches_agent(nid, active_perspective)

        # In dialectical mode (isolate_attributed=False) with an active perspective,
        # external non-suppositional attackers attacking in-perspective claims remain active.
        external_challengers: set[str] = set()
        if (
            not eff_isolate_attr
            and active_perspective is not None
            and active_perspective not in ("all", "suppositional")
        ):
            for pe in parsed_edges:
                is_warrant_mod = (
                    pe.undercuts_relation_id is not None
                    or pe.target in explicit_warrant_ids
                )
                eff_tgt = (
                    target_atom_by_warrant.get(
                        pe.undercuts_relation_id or pe.target, pe.target
                    )
                    if is_warrant_mod
                    else pe.target
                )
                if (
                    pe.polarity < 0
                    and pe.source not in sup_nodes
                    and not in_persp.get(pe.source, False)
                    and in_persp.get(eff_tgt, False)
                ):
                    keep, _, _ = self._evaluate_admissibility_gate(
                        pe.eff_w,
                        pe.acc,
                        pe.p_stance,
                        pe.model_conf,
                        normalization_mode,
                        active_adm_mode,
                        active_tau_p,
                        active_tau_c,
                    )
                    if keep:
                        external_challengers.add(pe.source)

        base_tau: dict[str, float] = {}
        perspective_filtered_nodes: set[str] = set()
        for nid, tau in raw_base_tau.items():
            if nid in sup_nodes:
                base_tau[nid] = 0.0 if sup_isolation_active else tau
            elif in_persp[nid] or nid in external_challengers:
                base_tau[nid] = tau
            else:
                base_tau[nid] = 0.0
                perspective_filtered_nodes.add(nid)

        admissible_edges: list[_AdmissibleEdge] = []
        sup_candidate_edges: list[_AdmissibleEdge] = []
        admissibility_pruned = 0

        for pe in parsed_edges:
            src, tgt = pe.source, pe.target
            premises = pe.premise_ids if pe.premise_ids else ((src,) if src else ())
            is_warrant_mod = (
                pe.undercuts_relation_id is not None or tgt in explicit_warrant_ids
            )
            eff_tgt = (
                target_atom_by_warrant.get(pe.undercuts_relation_id or tgt, tgt)
                if is_warrant_mod
                else tgt
            )
            src_sup = any(p in sup_nodes for p in premises)
            tgt_sup = False if is_warrant_mod else (eff_tgt in sup_nodes)

            # Handle edges touching suppositional nodes under active supposition isolation
            if sup_isolation_active and (src_sup or tgt_sup):
                # Only allow non-suppositional side to belong to active perspective
                src_eligible = all(
                    (p in sup_nodes)
                    or (in_persp.get(p, False) and base_tau.get(p, 0.0) > 0.0)
                    for p in premises
                )
                tgt_eligible = tgt_sup or in_persp.get(eff_tgt, False)
                if not (src_eligible and tgt_eligible):
                    continue
                keep, final_w, pruned = self._evaluate_admissibility_gate(
                    pe.eff_w,
                    pe.acc,
                    pe.p_stance,
                    pe.model_conf,
                    normalization_mode,
                    active_adm_mode,
                    active_tau_p,
                    active_tau_c,
                )
                if pruned:
                    admissibility_pruned += 1
                if keep:
                    sup_candidate_edges.append(
                        _AdmissibleEdge(
                            source=src,
                            target=tgt,
                            polarity=pe.polarity,
                            weight=final_w,
                            id=pe.id,
                            premise_ids=pe.premise_ids,
                            undercuts_relation_id=pe.undercuts_relation_id,
                            base_warrant=pe.base_warrant,
                        )
                    )
                continue

            # Non-suppositional perspective edge filtering
            if active_perspective is None:
                if (
                    eff_isolate_attr
                    and _is_authorial(eff_tgt)
                    and any(not _is_authorial(p) for p in premises)
                ):
                    for p in premises:
                        if not _is_authorial(p):
                            perspective_filtered_nodes.add(p)
                    continue
            elif active_perspective in ("all", "suppositional"):
                if (
                    eff_isolate_attr
                    and active_perspective == "suppositional"
                    and not (src_sup and tgt_sup)
                ):
                    continue
            else:
                both_in_persp = all(
                    in_persp.get(p, False) for p in premises
                ) and in_persp.get(eff_tgt, False)
                is_external_attack = (
                    not eff_isolate_attr
                    and src in external_challengers
                    and in_persp.get(eff_tgt, False)
                    and pe.polarity < 0
                )
                is_same_challenger_support = (
                    not eff_isolate_attr
                    and src in external_challengers
                    and eff_tgt in external_challengers
                    and (node_attributions.get(src) or "").strip().lower()
                    == (node_attributions.get(eff_tgt) or "").strip().lower()
                )
                if not (
                    both_in_persp or is_external_attack or is_same_challenger_support
                ):
                    continue

            keep, final_w, pruned = self._evaluate_admissibility_gate(
                pe.eff_w,
                pe.acc,
                pe.p_stance,
                pe.model_conf,
                normalization_mode,
                active_adm_mode,
                active_tau_p,
                active_tau_c,
            )
            if pruned:
                admissibility_pruned += 1
            if keep:
                admissible_edges.append(
                    _AdmissibleEdge(
                        source=src,
                        target=tgt,
                        polarity=pe.polarity,
                        weight=final_w,
                        id=pe.id,
                        premise_ids=pe.premise_ids,
                        undercuts_relation_id=pe.undercuts_relation_id,
                        base_warrant=pe.base_warrant,
                    )
                )

        if sup_isolation_active and sup_candidate_edges:
            active_refuters = {
                nid
                for nid in raw_base_tau
                if nid not in sup_nodes
                and base_tau.get(nid, 0.0) > 0.0
                and (
                    in_persp.get(nid, False)
                    or active_perspective in (None, "all", "suppositional")
                )
            }
            in_persp_non_sup = {
                nid
                for nid in raw_base_tau
                if nid not in sup_nodes and in_persp.get(nid, False)
            }
            refuted_sup_nodes, reductio_edges = self._resolve_reductio_discharge(
                sup_nodes=sup_nodes,
                active_refuters=active_refuters,
                in_persp_non_sup=in_persp_non_sup,
                raw_base_tau=raw_base_tau,
                sup_candidate_edges=sup_candidate_edges,
            )
            for nid in refuted_sup_nodes:
                base_tau[nid] = raw_base_tau[nid]
            admissible_edges.extend(reductio_edges)

        return (
            base_tau,
            admissible_edges,
            admissibility_pruned,
            suppositional_isolated,
            len(perspective_filtered_nodes),
        )

    def _extract_node_spec(self, node: Any) -> tuple[str, float, str, str | None]:
        """Extract canonical ID, prior plausibility, intensional mode, and attribution.

        Parameters
        ----------
        node : Any
            Node representation (TheoryNode, BaseModel, Mapping, tuple, or identifier).

        Returns
        -------
        tuple of (str, float, str, str or None)
            Tuple of ``(node_id, tau_0, intensional_mode, attributed_to)``.
        """
        if isinstance(node, TheoryNode):
            if "base_score" in node.model_fields_set:
                tau = node.base_score
            elif "confidence" in node.model_fields_set:
                tau = node.confidence
            else:
                tau = node.base_score
            return (
                node.id,
                float(tau),
                str(node.intensional_mode).strip().lower(),
                node.attributed_to,
            )

        if isinstance(node, BaseModel):
            return self._extract_node_spec(node.model_dump())

        if isinstance(node, Mapping):
            nid = str(node.get("id") or node.get("node_id") or "unknown")
            raw_tau = node.get("base_score")
            if raw_tau is None:
                raw_tau = node.get("prior")
            if raw_tau is None:
                raw_tau = node.get("plausibility")
            if raw_tau is None:
                modal_prior = node.get("modal_prior")
                if modal_prior is not None:
                    local_ten = node.get("local_tenability")
                    if local_ten is None and isinstance(
                        node.get("tenability"), Mapping
                    ):
                        local_ten = node["tenability"].get("local_score")
                    raw_tau = float(modal_prior) * float(
                        local_ten if local_ten is not None else 1.0
                    )
            if raw_tau is None:
                raw_tau = node.get("confidence")
            tau = float(raw_tau) if raw_tau is not None else 0.5
            mode = str(node.get("intensional_mode") or "asserted").strip().lower()
            raw_attr = node.get("attributed_to")
            attr = str(raw_attr) if raw_attr is not None else None
            return nid, tau, mode, attr

        if isinstance(node, (tuple, list)) and len(node) >= 2:
            nid = str(node[0])
            tau = float(node[1])
            mode = (
                str(node[2]).strip().lower()
                if len(node) >= 3 and node[2] is not None
                else "asserted"
            )
            attr = str(node[3]) if len(node) >= 4 and node[3] is not None else None
            return nid, tau, mode, attr

        return str(node), 0.5, "asserted", None

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
        nid, tau, _, _ = self._extract_node_spec(node)
        return nid, tau

    def _parse_edge(self, edge: Any) -> _ParsedEdge | None:
        """Parse edge into typed intermediate attributes without reflection.

        Parameters
        ----------
        edge : Any
            Edge representation (TheoryEdge, BaseModel, Mapping, or tuple).

        Returns
        -------
        _ParsedEdge or None
            Parsed relational attributes, or ``None`` if endpoints cannot be determined.
        """
        # 1. First-class TheoryEdge domain object
        if isinstance(edge, TheoryEdge):
            if edge.relation_type == RelationType.ALTERNATIVE_READING_OF:
                return None
            pol = edge.polarity
            if pol == 0:
                pol = (
                    edge.relation_type.default_polarity
                    if isinstance(edge.relation_type, RelationType)
                    else 1
                )
            eff_w, acc, p_stance, model_conf = self._extract_edge_weights_from_model(
                edge
            )
            norm_premises = tuple(p for p in edge.premise_ids if p)
            src = edge.source or (norm_premises[0] if norm_premises else "")
            tgt = edge.target or (edge.undercuts_relation_id or "")
            if not src or not tgt:
                return None
            return _ParsedEdge(
                source=src,
                target=tgt,
                polarity=pol,
                eff_w=eff_w,
                acc=acc,
                p_stance=p_stance,
                model_conf=model_conf,
                id=edge.id,
                premise_ids=norm_premises,
                undercuts_relation_id=edge.undercuts_relation_id,
                base_warrant=float(edge.inferential_force),
            )

        # 2. Foreign Pydantic BaseModel (e.g. episteme_pipeline TheoryRelation)
        if isinstance(edge, BaseModel):
            return self._parse_edge(edge.model_dump())

        # 3. Mapping representation
        if isinstance(edge, Mapping):
            raw_props = edge.get("properties")
            props = raw_props if isinstance(raw_props, Mapping) else edge
            raw_premises = edge.get("premise_ids") or props.get("premise_ids") or ()
            norm_premises = tuple(str(p) for p in raw_premises if p)
            edge_id_val = edge.get("id") or props.get("id")
            edge_id = str(edge_id_val) if edge_id_val else None
            undercut_val = edge.get("undercuts_relation_id") or props.get(
                "undercuts_relation_id"
            )
            undercut_id = str(undercut_val) if undercut_val else None

            src = str(
                edge.get("source")
                or edge.get("source_id")
                or edge.get("from_id")
                or (norm_premises[0] if norm_premises else "")
            )
            tgt = str(
                edge.get("target")
                or edge.get("target_id")
                or edge.get("to_id")
                or (undercut_id or "")
            )
            if not src or not tgt:
                return None
            pol = self._resolve_polarity(
                props.get("polarity"),
                edge.get("relation_type")
                or props.get("relation_type")
                or props.get("type"),
            )
            eff_w, acc, p_stance, model_conf = self._extract_edge_weights_from_mapping(
                props
            )
            raw_warrant = props.get("inferential_force")
            if raw_warrant is None:
                raw_warrant = props.get("inferential_warrant")
            base_warrant = float(raw_warrant) if raw_warrant is not None else 0.75
            return _ParsedEdge(
                source=src,
                target=tgt,
                polarity=pol,
                eff_w=eff_w,
                acc=acc,
                p_stance=p_stance,
                model_conf=model_conf,
                id=edge_id,
                premise_ids=norm_premises,
                undercuts_relation_id=undercut_id,
                base_warrant=base_warrant,
            )

        # 4. Tuple (src, tgt, weight, polarity)
        if isinstance(edge, (tuple, list)) and len(edge) >= 2:
            src = str(edge[0])
            tgt = str(edge[1])
            w = float(edge[2]) if len(edge) >= 3 else 1.0
            pol = int(edge[3]) if len(edge) >= 4 else 1
            return _ParsedEdge(
                source=src,
                target=tgt,
                polarity=pol,
                eff_w=w,
                acc=None,
                p_stance=None,
                model_conf=None,
            )

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
            if relation_type == RelationType.ALTERNATIVE_READING_OF:
                return 0
            pol = relation_type.default_polarity
            return pol if pol != 0 else 1

        if relation_type is not None:
            r_str = str(relation_type).upper()
            if r_str == "ALTERNATIVE_READING_OF":
                return 0
            if r_str in {
                "SUPPORTS",
                "SUPPORTS_ARG",
                "BACKS",
                "ENTAILS",
                "IMPLIES",
                "DEDUCES",
                "COHERES_WITH",
            }:
                return 1
            if r_str in {
                "ATTACKS",
                "REBUTS",
                "REFUTES",
                "CONTRADICTS",
                "UNDERCUTS",
                "UNDERMINES",
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
        p_stance = (
            edge.stance_probability
            if edge.stance_probability is not None
            else edge.class_probability
        )
        model_conf = edge.model_confidence
        acc = edge.empirical_accuracy
        inferential = edge.inferential_force
        modal = edge.modal_strength

        if edge.effective_weight is not None:
            w = float(edge.effective_weight)
        elif (
            "active_weight" in edge.model_fields_set and edge.active_weight is not None
        ):
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

        c_val = (
            float(model_conf)
            if model_conf is not None
            else (float(acc) if acc is not None else None)
        )
        return max(0.0, w), acc, p_stance, c_val

    def _extract_edge_weights_from_mapping(
        self, obj: Mapping[str, Any]
    ) -> tuple[float, float | None, float | None, float | None]:
        """Extract decoupled mathematical weights from mapping representation.

        Supports both ``epistemetrics`` dict keys (``inferential_force``,
        ``stance_probability``, ``model_confidence``, ``empirical_accuracy``)
        and ``episteme_pipeline`` dumped ``TheoryRelation`` keys
        (``inferential_warrant``, ``perception_stance_prob``,
        ``calibrated_confidence``, ``perception_empirical_acc``, ``edge_tenability``).

        Parameters
        ----------
        obj : Mapping of str to Any
            Relational property mapping.

        Returns
        -------
        tuple of (float, float | None, float | None, float | None)
            Resolved weight magnitude, empirical accuracy, stance probability, and model confidence.
        """
        inferential = obj.get("inferential_force")
        if inferential is None:
            inferential = obj.get("inferential_warrant")
        modal = float(obj.get("modal_strength", 1.0) or 1.0)
        p_stance = obj.get("stance_probability")
        if p_stance is None:
            p_stance = obj.get("perception_stance_prob")
        if p_stance is None:
            p_stance = obj.get("class_probability")
        model_conf = obj.get("model_confidence")
        if model_conf is None:
            model_conf = obj.get("calibrated_confidence")
        acc = obj.get("empirical_accuracy")
        if acc is None:
            acc = obj.get("perception_empirical_acc")
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
        c_val = (
            float(model_conf)
            if model_conf is not None
            else (float(acc) if acc is not None else None)
        )
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
    perspective: str | None = None,
    isolate_suppositional: bool = True,
    isolate_attributed: bool = True,
    t_norm: Literal["product", "godel"] = "product",
    base_prior_policy: BasePriorPolicy | str = BasePriorPolicy.DESCRIPTIVE_AUTHORIAL,
    normative_hypothesis_prior: float = 0.5,
    normative_data_prior: float = 0.8,
) -> QBAFSolverResult:
    """Convenience functional interface for solving QBAF gradual semantics."""
    solver = QBAFGradualSemanticsSolver(
        semantics_model=semantics_model,
        max_iterations=max_iterations,
        tolerance=tolerance,
        admissibility_threshold=admissibility_threshold,
        admissibility_mode=admissibility_mode,
        tau_p=tau_p,
        tau_c=tau_c,
        use_continuous=continuous,
        perspective=perspective,
        isolate_suppositional=isolate_suppositional,
        isolate_attributed=isolate_attributed,
        t_norm=t_norm,
        base_prior_policy=base_prior_policy,
        normative_hypothesis_prior=normative_hypothesis_prior,
        normative_data_prior=normative_data_prior,
    )
    return solver.solve(
        nodes=nodes,
        edges=edges,
        normalization_mode=normalization_mode,
        admissibility_mode=admissibility_mode,
        tau_p=tau_p,
        tau_c=tau_c,
        continuous=continuous,
        perspective=perspective,
        isolate_suppositional=isolate_suppositional,
        isolate_attributed=isolate_attributed,
        base_prior_policy=base_prior_policy,
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
    perspective: str | None = None,
    isolate_suppositional: bool = True,
    isolate_attributed: bool = True,
    t_norm: Literal["product", "godel"] = "product",
    base_prior_policy: BasePriorPolicy | str = BasePriorPolicy.DESCRIPTIVE_AUTHORIAL,
    normative_hypothesis_prior: float = 0.5,
    normative_data_prior: float = 0.8,
) -> QBAFSolverResult:
    """Convenience functional interface for continuous Quadratic Energy QBAF solving."""
    solver = QBAFGradualSemanticsSolver(
        semantics_model=GradualSemanticsModel.QUADRATIC,
        tolerance=tolerance,
        admissibility_mode=admissibility_mode,
        tau_p=tau_p,
        tau_c=tau_c,
        perspective=perspective,
        isolate_suppositional=isolate_suppositional,
        isolate_attributed=isolate_attributed,
        t_norm=t_norm,
        base_prior_policy=base_prior_policy,
        normative_hypothesis_prior=normative_hypothesis_prior,
        normative_data_prior=normative_data_prior,
    )
    return solver.solve_continuous(
        nodes=nodes,
        edges=edges,
        normalization_mode=normalization_mode,
        perspective=perspective,
        isolate_suppositional=isolate_suppositional,
        isolate_attributed=isolate_attributed,
        base_prior_policy=base_prior_policy,
    )


class QBAFPriorSensitivityResult(BaseModel):
    """Sensitivity analysis across normative and descriptive base-prior policies.

    Parameters
    ----------
    results_by_policy : dict of str to QBAFSolverResult
        Equilibrium results keyed by :class:`BasePriorPolicy` value.
    max_drift_descriptive_vs_uniform : float
        Maximum absolute acceptability difference between descriptive authorial
        priors and uniform normative priors.
    mean_drift_descriptive_vs_uniform : float
        Mean absolute acceptability shift between descriptive and uniform modes.
    rank_reversals_descriptive_vs_uniform : int
        Count of argument pairs whose acceptability ordering flips between
        descriptive authorial and uniform normative priors.
    """

    model_config = ConfigDict(frozen=True)

    results_by_policy: dict[str, QBAFSolverResult] = Field(default_factory=dict)
    max_drift_descriptive_vs_uniform: float = Field(default=0.0)
    mean_drift_descriptive_vs_uniform: float = Field(default=0.0)
    rank_reversals_descriptive_vs_uniform: int = Field(default=0)


def compare_prior_policies(
    nodes: TheoryGraph | Mapping[str, float] | Sequence[Any],
    edges: Sequence[Any] | None = None,
    *,
    continuous: bool = True,
    normative_hypothesis_prior: float = 0.5,
    normative_data_prior: float = 0.8,
    t_norm: Literal["product", "godel"] = "product",
) -> QBAFPriorSensitivityResult:
    """Evaluate QBAF sensitivity across descriptive, uniform, and Data-Priority priors.

    Parameters
    ----------
    nodes : TheoryGraph or Mapping or Sequence
        Argument nodes.
    edges : Sequence or None, optional
        Dialectical inferences.
    continuous : bool, default True
        Whether to use continuous Quadratic Energy solving.
    normative_hypothesis_prior : float, default 0.5
        Neutral prior assigned to hypotheses under normative policies.
    normative_data_prior : float, default 0.8
        Defeasible Data-Priority prior assigned to evidential base atoms.
    t_norm : Literal["product", "godel"], default "product"
        Conjunctive t-norm operator.

    Returns
    -------
    QBAFPriorSensitivityResult
        Per-policy equilibria and drift/rank-reversal diagnostics.
    """
    results: dict[str, QBAFSolverResult] = {}
    for policy in (
        BasePriorPolicy.DESCRIPTIVE_AUTHORIAL,
        BasePriorPolicy.NORMATIVE_UNIFORM,
        BasePriorPolicy.NORMATIVE_DATA_PRIORITY,
    ):
        results[policy.value] = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            continuous=continuous,
            t_norm=t_norm,
            base_prior_policy=policy,
            normative_hypothesis_prior=normative_hypothesis_prior,
            normative_data_prior=normative_data_prior,
        )

    desc = results[BasePriorPolicy.DESCRIPTIVE_AUTHORIAL.value]
    unif = results[BasePriorPolicy.NORMATIVE_UNIFORM.value]
    all_nodes = list(desc.degrees.keys())
    drifts = [abs(desc.degrees[n] - unif.degrees[n]) for n in all_nodes]
    max_drift = max(drifts) if drifts else 0.0
    mean_drift = float(np.mean(drifts)) if drifts else 0.0

    reversals = 0
    for i in range(len(all_nodes)):
        for j in range(i + 1, len(all_nodes)):
            u, v = all_nodes[i], all_nodes[j]
            d_diff = desc.degrees[u] - desc.degrees[v]
            u_diff = unif.degrees[u] - unif.degrees[v]
            if (d_diff > 1e-4 and u_diff < -1e-4) or (
                d_diff < -1e-4 and u_diff > 1e-4
            ):
                reversals += 1

    return QBAFPriorSensitivityResult(
        results_by_policy=results,
        max_drift_descriptive_vs_uniform=round(max_drift, 6),
        mean_drift_descriptive_vs_uniform=round(mean_drift, 6),
        rank_reversals_descriptive_vs_uniform=reversals,
    )


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
