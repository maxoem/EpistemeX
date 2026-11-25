"""Diachronic Dynamics and Bounded Lakatosian Degeneration Evaluation.

Computes hard-core invariance across chronological theory-net snapshots,
the bounded degeneration proxy :math:`D_{\\text{deg}} \\in [0, 1]`, the
empirical failure rate :math:`R_{\\text{fail}} \\in [0, 1]`, and node-level
immunization indices.
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


def compute_bounded_degeneration_proxy(
    novel_successes: int,
    direct_failures: int,
    adhoc_failures: int,
) -> tuple[float, float]:
    """Compute bounded degeneration proxy and empirical failure rate in ``[0, 1]``.

    .. math::

        D_{\\text{deg}} = \\frac{|\\mathsf{Fail}_b|}{|\\mathsf{Succ}^{\\text{nov}}| + |\\mathsf{Fail}_b|}, \\qquad
        R_{\\text{fail}} = \\frac{|\\mathsf{Fail}_a| + |\\mathsf{Fail}_b|}{|\\mathsf{Succ}^{\\text{nov}}| + |\\mathsf{Fail}_a| + |\\mathsf{Fail}_b|}

    Both indicators return ``0.0`` when their respective denominators are zero.
    ``D_deg`` is strictly monotone increasing in ``adhoc_failures``, strictly
    monotone decreasing in ``novel_successes``, and invariant to
    ``direct_failures`` (which instead increase ``R_fail``).

    Parameters
    ----------
    novel_successes : int
        Count of corroborated novel predictions :math:`|\\mathsf{Succ}^{\\text{nov}}|`.
    direct_failures : int
        Count of direct refutations :math:`|\\mathsf{Fail}_a|`.
    adhoc_failures : int
        Count of ad-hoc1 immunizations :math:`|\\mathsf{Fail}_b|`.

    Returns
    -------
    tuple of (float, float)
        Pair ``(d_deg, r_fail)`` bounded in ``[0.0, 1.0]``.
    """
    n_nov = max(0, int(novel_successes))
    n_fa = max(0, int(direct_failures))
    n_fb = max(0, int(adhoc_failures))

    deg_denom = n_nov + n_fb
    d_deg = float(n_fb) / float(deg_denom) if deg_denom > 0 else 0.0

    fail_denom = n_nov + n_fa + n_fb
    r_fail = float(n_fa + n_fb) / float(fail_denom) if fail_denom > 0 else 0.0
    return d_deg, r_fail


class DynamicsEvaluationResult(BaseModel):
    """Result container for diachronic theory evolution and degeneration evaluation.

    Parameters
    ----------
    degeneration_index : float
        Bounded degeneration proxy :math:`D_{\\text{deg}} \\in [0, 1]`.
    empirical_failure_rate : float
        Overall empirical failure rate :math:`R_{\\text{fail}} \\in [0, 1]`.
    is_progressive : bool
        True iff hard core is invariant and ``D_deg < 0.5`` with ``R_fail < 0.5``
        (or no failures are present).
    core_invariant : bool
        True if foundational core axioms remain strictly invariant.
    delta_auxiliary : int
        Net count of added auxiliary hypotheses across snapshots.
    anomalies_count : int
        Total unresolved direct refutations (Failure Type a) in the latest epoch.
    adhoc_failures_count : int
        Count of ad-hoc1 immunizing modifications (Failure Type b).
    delta_empirical_content : int
        Net gain of corroborated novel empirical content across snapshots.
    accommodated_successes_count : int
        Count of post-hoc accommodated explanations excluded from novel progress.
    violated_invariance : list[dict[str, Any]]
        Detected core axiom modifications or removals.
    node_immunization_scores : dict[str, float]
        Per-node immunization index for newly introduced auxiliary hypotheses.
    trajectory : list[dict[str, Any]]
        Step-by-step transition metrics for each adjacent snapshot pair.
    details : dict[str, Any]
        Diagnostic metadata including trajectory trend :math:`\\Delta D_{\\text{deg}}`.
    """

    model_config = ConfigDict(frozen=True)

    degeneration_index: float = Field(
        ..., ge=0.0, le=1.0, description="Bounded degeneration proxy D_deg in [0, 1]."
    )
    empirical_failure_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall empirical failure rate R_fail in [0, 1].",
    )
    is_progressive: bool = Field(
        ..., description="Whether the theoretical trajectory is progressive."
    )
    core_invariant: bool = Field(
        ..., description="Whether foundational hard-core axioms remain invariant."
    )
    delta_auxiliary: int = Field(
        default=0, description="Net count of added auxiliary hypotheses."
    )
    anomalies_count: int = Field(
        default=0, description="Count of direct empirical refutations (Fail_a)."
    )
    adhoc_failures_count: int = Field(
        default=0, description="Count of ad-hoc1 immunizations (Fail_b)."
    )
    delta_empirical_content: int = Field(
        default=0, description="Net gain of corroborated novel empirical content."
    )
    accommodated_successes_count: int = Field(
        default=0, description="Count of post-hoc accommodated explanations."
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
        status_prog = "PROGRESSIVE" if self.is_progressive else "DEGENERATING"
        status_core = "INVARIANT" if self.core_invariant else "CORE MUTATED"

        lines = [
            "# Diachronic Dynamics & Lakatosian Degeneration Report",
            "",
            f"- **Research Programme Status:** {status_prog}",
            f"- **Hard-Core Invariance (HC):** {status_core}",
            f"- **Bounded Degeneration Proxy ($D_{{\\text{{deg}}}}$):** {self.degeneration_index:.4f} (in [0, 1])",
            f"- **Empirical Failure Rate ($R_{{\\text{{fail}}}}$):** {self.empirical_failure_rate:.4f} (in [0, 1])",
            "",
            "## Quantitative Evolution Metrics",
            f"- **Corroborated Novel Content ($\\Delta |\\mathsf{{Succ}}^{{\\text{{nov}}}}|$):** {self.delta_empirical_content}",
            f"- **Accommodated Explanations ($|\\mathsf{{Succ}}^{{\\text{{acc}}}}|$):** {self.accommodated_successes_count}",
            f"- **Direct Refutations ($|\\mathsf{{Fail}}_a|$):** {self.anomalies_count}",
            f"- **Ad-Hoc₁ Immunizations ($|\\mathsf{{Fail}}_b|$):** {self.adhoc_failures_count}",
            f"- **Added Auxiliary Hypotheses ($\\Delta |\\Pi|$):** {self.delta_auxiliary}",
        ]

        if self.node_immunization_scores:
            lines.append("")
            lines.append("## Auxiliary Node Immunization Breakdown")
            lines.append("| Auxiliary Node ID | Immunization Index ($II$) | Classification |")
            lines.append("| :--- | :---: | :--- |")
            for nid, score in self.node_immunization_scores.items():
                stance = "Ad-Hoc Immunization" if score >= 0.8 else "Progressive Expansion"
                lines.append(f"| `{nid}` | {score:.4f} | {stance} |")

        if self.violated_invariance:
            lines.append("")
            lines.append("## Violated Core Invariances")
            for viol in self.violated_invariance:
                lines.append(f"- `{viol.get('node_id')}`: {viol.get('reason')}")

        return "\n".join(lines)


def _extract_snapshot_components(
    snapshot: Any,
) -> tuple[dict[str, str], set[str], set[str], set[str], set[str], set[str]]:
    """Extract structured components from a theory snapshot.

    Returns
    -------
    tuple of (core_axioms, auxiliary, direct_failures, novel_empirical, accommodated, explicit_adhoc)
        - core_axioms: map of node_id -> formal_axiom or label
        - auxiliary: set of auxiliary hypothesis IDs
        - direct_failures: set of Failure Type a IDs (anomalies)
        - novel_empirical: set of corroborated novel success IDs
        - accommodated: set of post-hoc accommodated success IDs
        - explicit_adhoc: set of explicit Failure Type b (ad-hoc1) IDs
    """
    core_axioms: dict[str, str] = {}
    auxiliary: set[str] = set()
    direct_failures: set[str] = set()
    novel_empirical: set[str] = set()
    accommodated: set[str] = set()
    explicit_adhoc: set[str] = set()

    if isinstance(snapshot, dict) and any(
        k in snapshot
        for k in (
            "core_axioms",
            "auxiliary_hypotheses",
            "anomalies",
            "direct_failures",
            "adhoc_failures",
            "novel_successes",
            "empirical_content",
        )
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
        direct_failures.update(
            str(x)
            for x in snapshot.get("direct_failures", snapshot.get("anomalies", []))
        )
        explicit_adhoc.update(str(x) for x in snapshot.get("adhoc_failures", []))
        novel_raw = snapshot.get(
            "novel_successes", snapshot.get("empirical_content", [])
        )
        novel_empirical.update(str(x) for x in novel_raw)
        accommodated.update(str(x) for x in snapshot.get("accommodated_successes", []))
        return (
            core_axioms,
            auxiliary,
            direct_failures,
            novel_empirical,
            accommodated,
            explicit_adhoc,
        )

    if isinstance(snapshot, TheoryGraph):
        for nid, node in snapshot.nodes.items():
            nt = node.node_type
            es = node.epistemic_status
            axiom_str = str(
                node.attributes.get("formalAxiom")
                or node.attributes.get("formal_axiom")
                or node.name
                or nid
            )
            if node.attributes.get("is_adhoc") or node.attributes.get("failure_type") == "b":
                explicit_adhoc.add(nid)
                continue

            if es == EpistemicStatus.HARD_CORE or nt in {
                NodeType.AXIOM,
                NodeType.ACTUAL_MODEL,
            }:
                core_axioms[nid] = axiom_str
            elif es == EpistemicStatus.PROTECTIVE_BELT or nt == NodeType.HYPOTHESIS:
                auxiliary.add(nid)
            elif es == EpistemicStatus.ANOMALOUS:
                direct_failures.add(nid)
            elif nt in {
                NodeType.PARADIGM,
                NodeType.PHENOMENON,
                NodeType.EVIDENCE,
                NodeType.CLAIM,
            }:
                if node.attributes.get("is_accommodated"):
                    accommodated.add(nid)
                else:
                    novel_empirical.add(nid)

        return (
            core_axioms,
            auxiliary,
            direct_failures,
            novel_empirical,
            accommodated,
            explicit_adhoc,
        )

    if isinstance(snapshot, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        for nid, data in snapshot.nodes(data=True):
            node_id = str(nid)
            nt_str = str(data.get("node_type", data.get("type", ""))).lower()
            es_str = str(data.get("epistemic_status", "")).lower()
            axiom_str = str(
                data.get(
                    "formalAxiom", data.get("formal_axiom", data.get("name", node_id))
                )
            )
            if data.get("is_adhoc") or data.get("failure_type") == "b":
                explicit_adhoc.add(node_id)
                continue

            if "hard_core" in es_str or "axiom" in nt_str or "actual_model" in nt_str:
                core_axioms[node_id] = axiom_str
            elif (
                "protective_belt" in es_str
                or "hypothesis" in nt_str
                or "auxiliary" in nt_str
            ):
                auxiliary.add(node_id)
            elif "anomal" in es_str or "anomaly" in nt_str:
                direct_failures.add(node_id)
            elif any(
                k in nt_str for k in ["paradigm", "phenomenon", "evidence", "claim"]
            ):
                if data.get("is_accommodated"):
                    accommodated.add(node_id)
                else:
                    novel_empirical.add(node_id)

        return (
            core_axioms,
            auxiliary,
            direct_failures,
            novel_empirical,
            accommodated,
            explicit_adhoc,
        )

    raise TypeError(f"Unsupported snapshot type {type(snapshot).__name__}")


def verify_hard_core_invariance(
    snapshots: Sequence[Any],
    core_node_ids: set[str] | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Verify that hard-core axioms remain invariant across snapshots.

    Parameters
    ----------
    snapshots : Sequence of Any
        Chronological sequence of theory snapshots ``[T^(0), T^(1), ..., T^(m)]``.
    core_node_ids : set of str, optional
        Explicit hard-core axiom identifiers to monitor. If None, core axioms
        extracted from ``snapshots[0]`` are monitored.

    Returns
    -------
    tuple of (bool, list of dict of str to Any)
        Invariance flag and list of violation descriptors.
    """
    if len(snapshots) < 2:
        return True, []

    c0 = _extract_snapshot_components(snapshots[0])[0]
    target_core = core_node_ids or set(c0.keys())
    violations: list[dict[str, Any]] = []

    for t in range(1, len(snapshots)):
        c_t = _extract_snapshot_components(snapshots[t])[0]

        for core_id in target_core:
            if core_id not in c_t:
                violations.append(
                    {
                        "epoch": t,
                        "node_id": core_id,
                        "reason": f"Core axiom '{core_id}' dropped in epoch {t}.",
                    }
                )
                continue

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

    return len(violations) == 0, violations


def evaluate_diachronic_dynamics(
    snapshots: Sequence[Any],
    *,
    core_node_ids: set[str] | None = None,
) -> DynamicsEvaluationResult:
    """Evaluate diachronic dynamics, bounded degeneration proxy, and failure rate.

    Computes hard-core invariance across ``[T^(0), ..., T^(m)]``, per-step
    ad-hoc1 immunization counts, the bounded degeneration proxy
    :math:`D_{\\text{deg}} \\in [0, 1]`, and the empirical failure rate
    :math:`R_{\\text{fail}} \\in [0, 1]`.

    Parameters
    ----------
    snapshots : Sequence of Any
        Chronological sequence of theory snapshots.
    core_node_ids : set of str, optional
        Explicit hard-core node IDs to monitor for invariance.

    Returns
    -------
    DynamicsEvaluationResult
        Bounded degeneration proxy, empirical failure rate, invariance status,
        node immunization scores, and per-transition trajectory.
    """
    if not snapshots:
        return DynamicsEvaluationResult(
            degeneration_index=0.0,
            empirical_failure_rate=0.0,
            is_progressive=True,
            core_invariant=True,
            delta_auxiliary=0,
            anomalies_count=0,
            adhoc_failures_count=0,
            delta_empirical_content=0,
            accommodated_successes_count=0,
            violated_invariance=[],
            node_immunization_scores={},
            trajectory=[],
            details={"status": "Empty snapshot sequence."},
        )

    core_invariant, violations = verify_hard_core_invariance(
        snapshots, core_node_ids=core_node_ids
    )

    if len(snapshots) == 1:
        _, aux, fail_a, nov_emp, acc_emp, explicit_fb = _extract_snapshot_components(
            snapshots[0]
        )
        n_fb = len(explicit_fb) if explicit_fb else (len(aux) if len(nov_emp) == 0 else 0)
        d_deg, r_fail = compute_bounded_degeneration_proxy(
            novel_successes=len(nov_emp),
            direct_failures=len(fail_a),
            adhoc_failures=n_fb,
        )
        return DynamicsEvaluationResult(
            degeneration_index=d_deg,
            empirical_failure_rate=r_fail,
            is_progressive=(d_deg < 0.5 and r_fail < 0.5 and core_invariant),
            core_invariant=core_invariant,
            delta_auxiliary=len(aux),
            anomalies_count=len(fail_a),
            adhoc_failures_count=n_fb,
            delta_empirical_content=len(nov_emp),
            accommodated_successes_count=len(acc_emp),
            violated_invariance=violations,
            node_immunization_scores={},
            trajectory=[],
            details={"single_snapshot": True, "trend": 0.0},
        )

    trajectory: list[dict[str, Any]] = []
    total_delta_aux = 0
    total_delta_emp = 0
    total_adhoc_fb = 0
    node_immunization: dict[str, float] = {}

    for t in range(len(snapshots) - 1):
        _, aux_prev, fa_prev, nov_prev, _, fb_prev = _extract_snapshot_components(
            snapshots[t]
        )
        _, aux_curr, fa_curr, nov_curr, _, fb_curr = _extract_snapshot_components(
            snapshots[t + 1]
        )

        added_aux = aux_curr - aux_prev
        delta_aux = len(added_aux)
        total_delta_aux += delta_aux

        added_nov = nov_curr - nov_prev
        delta_nov = len(added_nov)
        total_delta_emp += delta_nov

        added_explicit_fb = fb_curr - fb_prev
        if added_explicit_fb:
            step_fb = len(added_explicit_fb)
        elif delta_nov == 0 and delta_aux > 0:
            step_fb = delta_aux
        else:
            step_fb = 0
        total_adhoc_fb += step_fb

        fa_count = len(fa_curr)
        step_d_deg, step_r_fail = compute_bounded_degeneration_proxy(
            novel_successes=delta_nov,
            direct_failures=fa_count,
            adhoc_failures=step_fb,
        )

        for aux_node in added_aux:
            if delta_nov == 0:
                node_immunization[aux_node] = 1.0
            else:
                anom_resolved = max(1, len(fa_prev - fa_curr))
                node_immunization[aux_node] = float(anom_resolved) / float(
                    anom_resolved + delta_nov
                )

        trajectory.append(
            {
                "step": f"T_{t} -> T_{t + 1}",
                "delta_auxiliary": delta_aux,
                "anomalies_count": fa_count,
                "adhoc_failures_count": step_fb,
                "delta_empirical": delta_nov,
                "step_degeneration_index": step_d_deg,
                "step_empirical_failure_rate": step_r_fail,
            }
        )

    _, _, final_fa, _, final_acc, _ = _extract_snapshot_components(snapshots[-1])
    final_fa_count = len(final_fa)

    overall_d_deg, overall_r_fail = compute_bounded_degeneration_proxy(
        novel_successes=total_delta_emp,
        direct_failures=final_fa_count,
        adhoc_failures=total_adhoc_fb,
    )

    is_progressive = (
        overall_d_deg < 0.5 and overall_r_fail < 0.5 and core_invariant
    )

    trend = (
        trajectory[-1]["step_degeneration_index"]
        - trajectory[0]["step_degeneration_index"]
        if len(trajectory) > 1
        else 0.0
    )

    return DynamicsEvaluationResult(
        degeneration_index=overall_d_deg,
        empirical_failure_rate=overall_r_fail,
        is_progressive=is_progressive,
        core_invariant=core_invariant,
        delta_auxiliary=total_delta_aux,
        anomalies_count=final_fa_count,
        adhoc_failures_count=total_adhoc_fb,
        delta_empirical_content=total_delta_emp,
        accommodated_successes_count=len(final_acc),
        violated_invariance=violations,
        node_immunization_scores=node_immunization,
        trajectory=trajectory,
        details={
            "total_epochs": len(snapshots),
            "trend": trend,
        },
    )
