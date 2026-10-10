"""Diachronic Dynamics and Lakatosian Degeneration Evaluation.

Operationalizes Task 5 of the Structuralist Theory-Net Benchmark (STNB):
1. Lakatosian Degeneration Index (DI):
   DI = (Delta |Auxiliary Hypotheses| + |Anomalies|) / (Delta |Empirical Content| + epsilon)
2. Hard-Core Invariance Verification across historical snapshots (TN_t -> TN_{t+1}).
3. Node-Level Immunization Index (II) tracking ad-hoc stratagems.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from epistemetrics.core.models import (
    EpistemicStatus,
    NodeType,
)
from epistemetrics.graph.theory_graph import TheoryGraph


class DynamicsEvaluationResult(BaseModel):
    """Result container for diachronic theory evolution and degeneration evaluation.

    Parameters
    ----------
    degeneration_index : float
        Lakatosian Degeneration Index (DI) across snapshot transition(s).
    is_progressive : bool
        True if the research program is progressive (DI < 1.0 and core invariant).
    core_invariant : bool
        True if foundational core axioms (T_0) remain strictly invariant.
    delta_auxiliary : int
        Net count of added auxiliary hypotheses across snapshots.
    anomalies_count : int
        Total unresolved empirical anomalies in current epoch.
    delta_empirical_content : int
        Net gain of novel empirical content / paradigms.
    violated_invariance : list[dict[str, Any]]
        List of detected core axiom modifications, deletions, or corruptions.
    node_immunization_scores : dict[str, float]
        Per-node immunization index (II) for auxiliary hypotheses.
    trajectory : list[dict[str, Any]]
        Step-by-step transition metrics for each adjacent snapshot pair.
    details : dict[str, Any]
        Diagnostic metadata.
    """

    model_config = ConfigDict(frozen=True)

    degeneration_index: float = Field(
        ..., description="Lakatosian Degeneration Index (DI)."
    )
    is_progressive: bool = Field(
        ..., description="Whether the theoretical trajectory is progressive."
    )
    core_invariant: bool = Field(
        ..., description="Whether foundational core axioms T_0 remain invariant."
    )
    delta_auxiliary: int = Field(
        default=0, description="Increase in auxiliary hypotheses."
    )
    anomalies_count: int = Field(
        default=0, description="Count of empirical anomalies."
    )
    delta_empirical_content: int = Field(
        default=0, description="Increase in novel empirical content."
    )
    violated_invariance: list[dict[str, Any]] = Field(
        default_factory=list, description="Details of violated core axioms."
    )
    node_immunization_scores: dict[str, float] = Field(
        default_factory=dict, description="Immunization indices for auxiliary nodes."
    )
    trajectory: list[dict[str, Any]] = Field(
        default_factory=list, description="Epoch-by-epoch evaluation steps."
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Evaluation diagnostics."
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert result model to a serializable dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of dynamics evaluation results.
        """
        return self.model_dump()

    def to_markdown(self) -> str:
        """Format the dynamics evaluation result as a Markdown report.

        Returns
        -------
        str
            GitHub-flavored Markdown report.
        """
        status_prog = "✅ PROGRESSIVE" if self.is_progressive else "❌ DEGENERATING"
        status_core = "✅ INVARIANT" if self.core_invariant else "❌ CORE MUTATED"

        lines = [
            "# Diachronic Dynamics & Lakatosian Degeneration Report",
            "",
            f"- **Research Program Status:** {status_prog}",
            f"- **Hard-Core Invariance Checker ($T_0$):** {status_core}",
            f"- **Degeneration Index ($DI$):** {self.degeneration_index:.4f} {'(< 1.0 Progressive)' if self.degeneration_index < 1.0 else '(>= 1.0 Degenerating)'}",
            "",
            "## Quantitative Evolution Metrics",
            f"- **Delta Auxiliary Hypotheses ($\\Delta |Aux|$):** {self.delta_auxiliary}",
            f"- **Unresolved Anomalies ($|Anom|$):** {self.anomalies_count}",
            f"- **Delta Empirical Content ($\\Delta |Emp|$):** {self.delta_empirical_content}",
        ]

        if self.node_immunization_scores:
            lines.append("")
            lines.append("## Auxiliary Node Immunization Breakdown")
            lines.append("| Auxiliary Node ID | Immunization Index ($II$) | Stance |")
            lines.append("| :--- | :---: | :--- |")
            for nid, score in self.node_immunization_scores.items():
                stance = "Ad-Hoc Immunization ❌" if score >= 0.8 else "Progressive Expansion ✅"
                lines.append(f"| `{nid}` | {score:.4f} | {stance} |")

        if self.violated_invariance:
            lines.append("")
            lines.append("## Violated Core Invariances")
            for viol in self.violated_invariance:
                lines.append(f"- ❌ `{viol.get('node_id')}`: {viol.get('reason')}")

        return "\n".join(lines)


def _extract_snapshot_components(
    snapshot: Any,
) -> tuple[dict[str, str], set[str], set[str], set[str]]:
    """Extract (core_axioms, auxiliary_hypotheses, anomalies, empirical_content) from a snapshot.

    Returns
    -------
    tuple of (dict[str, str], set[str], set[str], set[str])
        - core_axioms: map of node_id -> formal_axiom or label
        - auxiliary_hypotheses: set of node_ids
        - anomalies: set of node_ids
        - empirical_content: set of node_ids
    """
    core_axioms: dict[str, str] = {}
    auxiliary: set[str] = set()
    anomalies: set[str] = set()
    empirical: set[str] = set()

    # Case 1: Dict-like explicit snapshot
    if isinstance(snapshot, dict) and (
        "core_axioms" in snapshot
        or "auxiliary_hypotheses" in snapshot
        or "anomalies" in snapshot
    ):
        raw_core = snapshot.get("core_axioms", [])
        if isinstance(raw_core, dict):
            core_axioms.update({str(k): str(v) for k, v in raw_core.items()})
        else:
            for item in raw_core:
                if isinstance(item, tuple):
                    core_axioms[str(item[0])] = str(item[1])
                else:
                    core_axioms[str(item)] = str(item)

        auxiliary.update(str(x) for x in snapshot.get("auxiliary_hypotheses", []))
        anomalies.update(str(x) for x in snapshot.get("anomalies", []))
        empirical.update(str(x) for x in snapshot.get("empirical_content", []))
        return core_axioms, auxiliary, anomalies, empirical

    # Case 2: TheoryGraph
    if isinstance(snapshot, TheoryGraph):
        for nid, node in snapshot.nodes.items():
            nt = node.node_type
            es = node.epistemic_status
            axiom_str = str(node.attributes.get("formalAxiom") or node.attributes.get("formal_axiom") or node.name or nid)

            if es == EpistemicStatus.HARD_CORE or nt in {NodeType.AXIOM, NodeType.ACTUAL_MODEL}:
                core_axioms[nid] = axiom_str
            elif es == EpistemicStatus.PROTECTIVE_BELT or nt == NodeType.HYPOTHESIS:
                auxiliary.add(nid)
            elif es == EpistemicStatus.ANOMALOUS:
                anomalies.add(nid)
            elif nt in {NodeType.PARADIGM, NodeType.PHENOMENON, NodeType.EVIDENCE, NodeType.CLAIM}:
                empirical.add(nid)

        return core_axioms, auxiliary, anomalies, empirical

    # Case 3: NetworkX Graph
    if isinstance(snapshot, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        for nid, data in snapshot.nodes(data=True):
            node_id = str(nid)
            nt_str = str(data.get("node_type", data.get("type", ""))).lower()
            es_str = str(data.get("epistemic_status", "")).lower()
            axiom_str = str(data.get("formalAxiom", data.get("formal_axiom", data.get("name", node_id))))

            if "hard_core" in es_str or "axiom" in nt_str or "actual_model" in nt_str:
                core_axioms[node_id] = axiom_str
            elif "protective_belt" in es_str or "hypothesis" in nt_str or "auxiliary" in nt_str:
                auxiliary.add(node_id)
            elif "anomal" in es_str or "anomaly" in nt_str:
                anomalies.add(node_id)
            elif any(k in nt_str for k in ["paradigm", "phenomenon", "evidence", "claim"]):
                empirical.add(node_id)

        return core_axioms, auxiliary, anomalies, empirical

    raise TypeError(f"Unsupported snapshot type {type(snapshot).__name__}")


def verify_hard_core_invariance(
    snapshots: Sequence[Any],
    core_node_ids: set[str] | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Verify that root axioms and hard-core laws remain invariant across snapshots.

    Parameters
    ----------
    snapshots : Sequence of Any
        Chronological sequence of theory snapshots [TN_0, TN_1, ..., TN_k].
    core_node_ids : set of str, optional
        Pre-defined set of core axiom identifiers to monitor. If None,
        core axioms extracted from the initial snapshot TN_0 are used.

    Returns
    -------
    tuple of (bool, list of dict of str to Any)
        Boolean indicating strict invariance, and list of violation descriptors.
    """
    if len(snapshots) < 2:
        return True, []

    c0, _, _, _ = _extract_snapshot_components(snapshots[0])
    target_core = core_node_ids or set(c0.keys())
    violations: list[dict[str, Any]] = []

    for t in range(1, len(snapshots)):
        c_t, _, _, _ = _extract_snapshot_components(snapshots[t])

        for core_id in target_core:
            # Check presence
            if core_id not in c_t:
                violations.append(
                    {
                        "epoch": t,
                        "node_id": core_id,
                        "reason": f"Core axiom '{core_id}' dropped in epoch {t}.",
                    }
                )
                continue

            # Check axiomatic consistency if both have formulas
            f0 = c0.get(core_id)
            f_t = c_t.get(core_id)
            if f0 and f_t and f0.strip() != f_t.strip():
                violations.append(
                    {
                        "epoch": t,
                        "node_id": core_id,
                        "reason": f"Core axiom '{core_id}' modified in epoch {t} ('{f0}' -> '{f_t}').",
                    }
                )

    is_invariant = len(violations) == 0
    return is_invariant, violations


def evaluate_diachronic_dynamics(
    snapshots: Sequence[Any],
    *,
    epsilon: float = 1e-6,
    core_node_ids: set[str] | None = None,
) -> DynamicsEvaluationResult:
    """Evaluate diachronic dynamics, Lakatosian degeneration index, and immunization shifts.

    Computes:
    DI = (Delta |Auxiliary Hypotheses| + |Anomalies|) / (Delta |Empirical Content| + epsilon)

    Parameters
    ----------
    snapshots : Sequence of Any
        Chronological sequence of theory net snapshots [TN_0, ..., TN_m].
    epsilon : float, optional
        Small stability constant avoiding division by zero (default: 1e-6).
    core_node_ids : set of str, optional
        Optional explicit hard-core node IDs to monitor for invariance.

    Returns
    -------
    DynamicsEvaluationResult
        Evaluation metrics including DI, invariance status, and node immunization scores.
    """
    if not snapshots:
        return DynamicsEvaluationResult(
            degeneration_index=0.0,
            is_progressive=True,
            core_invariant=True,
            delta_auxiliary=0,
            anomalies_count=0,
            delta_empirical_content=0,
            violated_invariance=[],
            node_immunization_scores={},
            trajectory=[],
            details={"status": "Empty snapshot sequence."},
        )

    # 1. Verify Hard-Core Invariance
    core_invariant, violations = verify_hard_core_invariance(
        snapshots, core_node_ids=core_node_ids
    )

    if len(snapshots) == 1:
        c, aux, anom, emp = _extract_snapshot_components(snapshots[0])
        di = float(len(aux) + len(anom)) / float(len(emp) + epsilon)
        return DynamicsEvaluationResult(
            degeneration_index=di,
            is_progressive=(di < 1.0),
            core_invariant=core_invariant,
            delta_auxiliary=len(aux),
            anomalies_count=len(anom),
            delta_empirical_content=len(emp),
            violated_invariance=violations,
            node_immunization_scores={},
            trajectory=[],
            details={"single_snapshot": True},
        )

    # Multi-epoch trajectory tracking
    trajectory: list[dict[str, Any]] = []
    total_delta_aux = 0
    total_delta_emp = 0
    node_immunization: dict[str, float] = {}

    for t in range(len(snapshots) - 1):
        _, aux_prev, anom_prev, emp_prev = _extract_snapshot_components(snapshots[t])
        _, aux_curr, anom_curr, emp_curr = _extract_snapshot_components(snapshots[t + 1])

        # New auxiliary nodes introduced in this step
        added_aux = aux_curr - aux_prev
        delta_aux = max(0, len(added_aux))
        total_delta_aux += delta_aux

        # New empirical content introduced in this step
        added_emp = emp_curr - emp_prev
        delta_emp = max(0, len(added_emp))
        total_delta_emp += delta_emp

        anom_curr_count = len(anom_curr)

        step_di = float(delta_aux + anom_curr_count) / float(delta_emp + epsilon)

        # Track node-level immunization:
        # II = Delta_anom / (Delta_anom + Delta_content)
        # If auxiliary added without empirical expansion, it is ad-hoc immunization (II = 1.0)
        for aux_node in added_aux:
            if delta_emp == 0:
                node_immunization[aux_node] = 1.0
            else:
                anom_resolved = max(1, len(anom_prev - anom_curr))
                node_immunization[aux_node] = float(anom_resolved) / float(
                    anom_resolved + delta_emp
                )

        trajectory.append(
            {
                "step": f"T_{t} -> T_{t + 1}",
                "delta_auxiliary": delta_aux,
                "anomalies_count": anom_curr_count,
                "delta_empirical": delta_emp,
                "step_degeneration_index": step_di,
            }
        )

    # Final overall metrics
    final_anomalies = len(_extract_snapshot_components(snapshots[-1])[2])
    overall_di = float(total_delta_aux + final_anomalies) / float(
        total_delta_emp + epsilon
    )

    is_progressive = (overall_di < 1.0) and core_invariant

    return DynamicsEvaluationResult(
        degeneration_index=overall_di,
        is_progressive=is_progressive,
        core_invariant=core_invariant,
        delta_auxiliary=total_delta_aux,
        anomalies_count=final_anomalies,
        delta_empirical_content=total_delta_emp,
        violated_invariance=violations,
        node_immunization_scores=node_immunization,
        trajectory=trajectory,
        details={
            "total_epochs": len(snapshots),
            "trend": (
                trajectory[-1]["step_degeneration_index"]
                - trajectory[0]["step_degeneration_index"]
                if len(trajectory) > 1
                else 0.0
            ),
        },
    )
