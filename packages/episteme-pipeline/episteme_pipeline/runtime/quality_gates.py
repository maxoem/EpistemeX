"""Built-in inter-phase epistemic quality gates (ISSUE-058).

Implements homeostatic circuit breakers evaluated between pipeline phases over
the emitted :class:`~episteme_pipeline.artifacts.execution.ArtifactCollection`:

1. :class:`OntologyEntropyGate` (Post-Phase 2): Verifies Shannon entropy
   :math:`H(\\text{entity\\_types}) \\ge H_{\\min}`, bounds single-type dominance
   ratio, and checks that non-empty chunks yield non-zero entity density.
2. :class:`PercolationQualityGate` (Post-Phase 3b & Phase 5): Verifies that the
   largest merged equivalence class does not exceed :math:`\\rho_{\\max} \\cdot |E|`,
   preventing giant-component percolation collapse.
3. :class:`ConformalCalibrationGate` (Post-Phase 3 & Phase 4): Monitors the
   empirical rate of empty (:math:`|C(X)| = 0`) and ambiguous (:math:`|C(X)| > 1`)
   conformal prediction sets, emitting a :class:`QualityGateWarning` or halting
   with :class:`QualityGateViolationError` when OOD rates exceed configured bounds.

References
----------
.. [1] Shannon, C. E. (1948). A Mathematical Theory of Communication.
   Bell System Technical Journal, 27(3), 379-423.
.. [2] Bollobás, B. (2001). Random Graphs (2nd ed.). Cambridge University Press.
.. [3] Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic Learning in a
   Random World. Springer.
"""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any, Literal

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    _resolve_alias_chain,
    _strip_artifact_prefix,
)
from episteme_pipeline.artifacts.models import (
    ArtifactKind,
    CanonicalizationArtifact,
    ChunkArtifact,
    EntityMentionArtifact,
    FusionDecisionArtifact,
    LinkedEntityArtifact,
    TheoryAtomArtifact,
)
from episteme_pipeline.config import PipelineConfig, QualityGatesConfig
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import QualityGateEvaluated
from episteme_pipeline.protocols.quality_gate import (
    EpistemicQualityGate,
    QualityGateResult,
    QualityGateViolationError,
    QualityGateWarning,
)

if TYPE_CHECKING:
    from episteme_pipeline.protocols.decision import DecisionEngine


def _finalize_gate_evaluation(
    *,
    gate_name: str,
    phase_key: str,
    passed: bool,
    on_violation: Literal["warn", "raise"],
    metrics: dict[str, float],
    message: str,
) -> QualityGateResult:
    """Emit telemetry event and apply violation policy for a quality gate check.

    Parameters
    ----------
    gate_name : str
        Unique identifier of the quality gate.
    phase_key : str
        Machine key of the evaluated phase.
    passed : bool
        Whether all thresholds passed.
    on_violation : Literal["warn", "raise"]
        Violation policy ('warn' or 'raise').
    metrics : dict of str to float
        Computed numerical metrics.
    message : str
        Diagnostic message.

    Returns
    -------
    QualityGateResult
        Evaluation outcome contract.

    Raises
    ------
    QualityGateViolationError
        If ``passed`` is False and ``on_violation == "raise"``.
    """
    severity: Literal["pass", "warn", "halt"] = (
        "pass"
        if passed
        else ("halt" if on_violation == "raise" else "warn")
    )
    result = QualityGateResult(
        gate_name=gate_name,
        phase_key=phase_key,
        passed=passed,
        severity=severity,
        metrics=metrics,
        message=message,
    )
    get_event_emitter().emit(
        QualityGateEvaluated(
            gate_name=gate_name,
            phase_key=phase_key,
            passed=passed,
            severity=severity,
            metrics=dict(metrics),
            message=message,
            phase=phase_key,
        )
    )
    if not passed:
        if on_violation == "raise":
            raise QualityGateViolationError(result)
        warnings.warn(message, QualityGateWarning, stacklevel=3)
    return result


class OntologyEntropyGate:
    """Post-Phase 2 quality gate preventing ontological collapse and empty extraction.

    Computes Shannon entropy :math:`H(\\text{entity\\_types}) = -\\sum_c p(c) \\log_2 p(c)`
    over extracted entity labels, checks the maximum single-label dominance ratio,
    and verifies that non-empty chunks yield a non-zero entity extraction density.

    Parameters
    ----------
    min_entropy : float, default 0.30
        Minimum acceptable Shannon entropy in bits when at least ``min_entities``
        are extracted and the schema defines multiple entity types.
    max_dominant_type_ratio : float, default 0.90
        Maximum acceptable fraction of entities assigned to a single type label.
    min_entities : int, default 5
        Minimum entity population required before entropy and dominance ratio
        checks are enforced.
    min_entity_density : float, default 0.0
        Minimum entities-per-non-empty-chunk density floor.
    require_nonzero_density : bool, default True
        Whether to flag a violation if non-empty chunks exist in the corpus
        and Phase 2 produced zero entities (while ``min_entity_density > 0.0``
        or ``check_empty_extraction=True``).
    on_violation : Literal["warn", "raise"], default "warn"
        Action taken when a quality invariant fails.
    target_phases : frozenset of str, optional
        Phase keys after which this gate is evaluated (defaults to ``{"phase2"}``).
    """

    def __init__(
        self,
        *,
        min_entropy: float = 0.30,
        max_dominant_type_ratio: float = 0.90,
        min_entities: int = 5,
        min_entity_density: float = 0.0,
        require_nonzero_density: bool = True,
        on_violation: Literal["warn", "raise"] = "warn",
        target_phases: frozenset[str] = frozenset({"phase2"}),
    ) -> None:
        self.min_entropy = min_entropy
        self.max_dominant_type_ratio = max_dominant_type_ratio
        self.min_entities = min_entities
        self.min_entity_density = min_entity_density
        self.require_nonzero_density = require_nonzero_density
        self.on_violation: Literal["warn", "raise"] = on_violation
        self._target_phases = frozenset(target_phases)

    @property
    def name(self) -> str:
        """Return the gate identifier."""
        return "ontology_entropy_gate"

    @property
    def target_phases(self) -> frozenset[str]:
        """Return target phase keys."""
        return self._target_phases

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint dictionary.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of gate parameters.
        """
        return {
            "class": self.__class__.__name__,
            "name": self.name,
            "min_entropy": self.min_entropy,
            "max_dominant_type_ratio": self.max_dominant_type_ratio,
            "min_entities": self.min_entities,
            "min_entity_density": self.min_entity_density,
            "require_nonzero_density": self.require_nonzero_density,
            "on_violation": self.on_violation,
            "target_phases": sorted(self._target_phases),
        }

    @staticmethod
    def compute_shannon_entropy(type_counts: dict[str, int]) -> tuple[float, float]:
        """Compute Shannon entropy in bits and dominant type ratio.

        Parameters
        ----------
        type_counts : dict of str to int
            Counts of entities per ontological type.

        Returns
        -------
        tuple of (float, float)
            Tuple of ``(shannon_entropy_bits, max_dominant_ratio)``.
        """
        total = sum(c for c in type_counts.values() if c > 0)
        if total <= 0:
            return 0.0, 0.0

        entropy = 0.0
        max_ratio = 0.0
        for count in type_counts.values():
            if count <= 0:
                continue
            p = count / total
            max_ratio = max(max_ratio, p)
            entropy -= p * math.log2(p)
        return entropy, max_ratio

    def evaluate(
        self,
        phase_key: str,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
        context: ArtifactExecutionContext | None = None,
    ) -> QualityGateResult:
        """Evaluate ontological entropy and entity extraction density.

        Parameters
        ----------
        phase_key : str
            Completed phase key.
        phase_collection : ArtifactCollection
            Artifacts emitted by ``phase_key``.
        cumulative_collection : ArtifactCollection
            Cumulative artifacts up to ``phase_key``.
        context : ArtifactExecutionContext or None, optional
            Active execution context.

        Returns
        -------
        QualityGateResult
            Evaluation result.
        """
        linked_envelopes = phase_collection.of_kind(
            ArtifactKind.LINKED_ENTITY, latest_only=True
        )
        if not linked_envelopes:
            linked_envelopes = cumulative_collection.of_kind(
                ArtifactKind.LINKED_ENTITY, latest_only=True
            )

        type_counts: dict[str, int] = {}
        entity_count = 0
        for env in linked_envelopes:
            if isinstance(env.payload, LinkedEntityArtifact):
                label = env.payload.entity_type or "UNKNOWN"
                type_counts[label] = type_counts.get(label, 0) + 1
                entity_count += 1

        if entity_count == 0:
            mention_envelopes = phase_collection.of_kind(
                ArtifactKind.ENTITY_MENTION, latest_only=True
            )
            for env in mention_envelopes:
                if isinstance(env.payload, EntityMentionArtifact):
                    label = env.payload.entity_type or "UNKNOWN"
                    type_counts[label] = type_counts.get(label, 0) + 1
                    entity_count += 1

        chunk_envelopes = cumulative_collection.of_kind(
            ArtifactKind.CHUNK, latest_only=True
        )
        non_empty_chunks = 0
        for env in chunk_envelopes:
            if isinstance(env.payload, ChunkArtifact) and env.payload.text.strip():
                non_empty_chunks += 1

        entity_density = (
            float(entity_count) / float(non_empty_chunks)
            if non_empty_chunks > 0
            else (float(entity_count) if entity_count > 0 else 0.0)
        )
        entropy, dominant_ratio = self.compute_shannon_entropy(type_counts)

        metrics: dict[str, float] = {
            "entity_count": float(entity_count),
            "non_empty_chunks": float(non_empty_chunks),
            "entity_density": entity_density,
            "shannon_entropy": entropy,
            "dominant_type_ratio": dominant_ratio,
            "distinct_type_count": float(len(type_counts)),
        }

        reasons: list[str] = []
        if non_empty_chunks > 0:
            if self.require_nonzero_density and entity_count == 0:
                reasons.append(
                    f"zero entity density (0 entities across {non_empty_chunks} non-empty chunks)"
                )
            elif self.min_entity_density > 0.0 and entity_density < self.min_entity_density:
                reasons.append(
                    f"entity density {entity_density:.3f} < min_entity_density {self.min_entity_density:.3f}"
                )

        if entity_count >= self.min_entities:
            if entropy < self.min_entropy:
                reasons.append(
                    f"ontological Shannon entropy H={entropy:.3f} < H_min={self.min_entropy:.3f}"
                )
            if dominant_ratio > self.max_dominant_type_ratio:
                reasons.append(
                    f"dominant entity type ratio {dominant_ratio:.3f} > max_dominant_type_ratio={self.max_dominant_type_ratio:.3f}"
                )

        passed = len(reasons) == 0
        message = (
            f"OntologyEntropyGate passed after '{phase_key}' "
            f"(entities={entity_count}, H={entropy:.3f}, dominant_ratio={dominant_ratio:.3f})."
            if passed
            else f"OntologyEntropyGate violation after '{phase_key}': {'; '.join(reasons)}."
        )
        return _finalize_gate_evaluation(
            gate_name=self.name,
            phase_key=phase_key,
            passed=passed,
            on_violation=self.on_violation,
            metrics=metrics,
            message=message,
        )


class PercolationQualityGate:
    """Post-Phase 3b and Phase 5 quality gate preventing giant-component percolation.

    Verifies that the largest merged equivalence class :math:`|C_{\\max}|` does not
    exceed :math:`\\rho_{\\max} \\cdot |E|`, preventing permissive similarity thresholds
    or transitive chaining from collapsing the entity or theory graph into a single
    giant connected component.

    Parameters
    ----------
    max_cluster_fraction : float, default 0.50
        Maximum allowed fraction :math:`\\rho_{\\max} \\in (0, 1]` of total population
        in the largest merged equivalence class.
    min_population : int, default 4
        Minimum population size :math:`|E|` required before percolation fraction
        bounds are enforced.
    on_violation : Literal["warn", "raise"], default "warn"
        Action taken when the percolation bound is violated.
    target_phases : frozenset of str, optional
        Phase keys after which this gate is evaluated (defaults to
        ``{"phase3b", "phase5"}``).
    """

    def __init__(
        self,
        *,
        max_cluster_fraction: float = 0.50,
        min_population: int = 4,
        on_violation: Literal["warn", "raise"] = "warn",
        target_phases: frozenset[str] = frozenset({"phase3b", "phase5"}),
    ) -> None:
        self.max_cluster_fraction = max_cluster_fraction
        self.min_population = min_population
        self.on_violation: Literal["warn", "raise"] = on_violation
        self._target_phases = frozenset(target_phases)

    @property
    def name(self) -> str:
        """Return the gate identifier."""
        return "percolation_quality_gate"

    @property
    def target_phases(self) -> frozenset[str]:
        """Return target phase keys."""
        return self._target_phases

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint dictionary.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of gate parameters.
        """
        return {
            "class": self.__class__.__name__,
            "name": self.name,
            "max_cluster_fraction": self.max_cluster_fraction,
            "min_population": self.min_population,
            "on_violation": self.on_violation,
            "target_phases": sorted(self._target_phases),
        }

    def _compute_l2_percolation(
        self,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
    ) -> tuple[int, int, int]:
        """Compute population size, largest cluster size, and merge count for Phase 3b."""
        canon_envelopes = phase_collection.of_kind(
            ArtifactKind.CANONICALIZATION, latest_only=True
        )
        if not canon_envelopes:
            canon_envelopes = cumulative_collection.of_kind(
                ArtifactKind.CANONICALIZATION, latest_only=True
            )

        alias_map: dict[str, str] = {}
        population_ids: set[str] = set()

        for env in cumulative_collection.of_kind(
            ArtifactKind.LINKED_ENTITY, latest_only=True
        ):
            if isinstance(env.payload, LinkedEntityArtifact):
                clean_id = _strip_artifact_prefix(env.payload.entity_id)
                if clean_id:
                    population_ids.add(clean_id)

        for env in canon_envelopes:
            if isinstance(env.payload, CanonicalizationArtifact):
                canon_id = _strip_artifact_prefix(env.payload.canonical_entity_id)
                if canon_id:
                    population_ids.add(canon_id)
                for orig_id in env.payload.merged_entity_ids:
                    clean_orig = _strip_artifact_prefix(orig_id)
                    if clean_orig:
                        population_ids.add(clean_orig)
                        if canon_id and clean_orig != canon_id:
                            alias_map[clean_orig] = canon_id

        if not population_ids:
            return 0, 0, 0

        clusters: dict[str, set[str]] = {}
        for node_id in population_ids:
            rep = _resolve_alias_chain(node_id, alias_map)
            clusters.setdefault(rep, set()).add(node_id)

        max_cluster_size = max((len(members) for members in clusters.values()), default=0)
        return len(population_ids), max_cluster_size, len(alias_map)

    def _compute_l3_percolation(
        self,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
    ) -> tuple[int, int, int]:
        """Compute population size, largest cluster size, and merge count for Phase 5."""
        fusion_envelopes = phase_collection.of_kind(
            ArtifactKind.FUSION_DECISION, latest_only=True
        )
        if not fusion_envelopes:
            fusion_envelopes = cumulative_collection.of_kind(
                ArtifactKind.FUSION_DECISION, latest_only=True
            )

        alias_map: dict[str, str] = {}
        population_ids: set[str] = set()

        for env in cumulative_collection.of_kind(
            ArtifactKind.THEORY_ATOM, latest_only=True
        ):
            if isinstance(env.payload, TheoryAtomArtifact):
                clean_id = _strip_artifact_prefix(env.payload.component_id)
                if clean_id:
                    population_ids.add(clean_id)

        for env in fusion_envelopes:
            if isinstance(env.payload, FusionDecisionArtifact):
                if env.payload.decision_type not in ("merge", "cluster"):
                    continue
                clean_ids = [
                    _strip_artifact_prefix(aid)
                    for aid in env.payload.artifact_ids
                    if _strip_artifact_prefix(aid)
                ]
                for cid in clean_ids:
                    population_ids.add(cid)
                if len(clean_ids) < 2:
                    continue
                canon_id = (
                    _strip_artifact_prefix(env.payload.canonical_artifact_id)
                    if env.payload.canonical_artifact_id
                    else clean_ids[0]
                )
                if canon_id:
                    population_ids.add(canon_id)
                    for member_id in clean_ids:
                        if member_id != canon_id:
                            alias_map[member_id] = canon_id

        if not population_ids:
            return 0, 0, 0

        clusters: dict[str, set[str]] = {}
        for node_id in population_ids:
            rep = _resolve_alias_chain(node_id, alias_map)
            clusters.setdefault(rep, set()).add(node_id)

        max_cluster_size = max((len(members) for members in clusters.values()), default=0)
        return len(population_ids), max_cluster_size, len(alias_map)

    def evaluate(
        self,
        phase_key: str,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
        context: ArtifactExecutionContext | None = None,
    ) -> QualityGateResult:
        """Evaluate equivalence class percolation ratio after consolidation or fusion.

        Parameters
        ----------
        phase_key : str
            Completed phase key ('phase3b' or 'phase5').
        phase_collection : ArtifactCollection
            Artifacts emitted by ``phase_key``.
        cumulative_collection : ArtifactCollection
            Cumulative artifacts up to ``phase_key``.
        context : ArtifactExecutionContext or None, optional
            Active execution context.

        Returns
        -------
        QualityGateResult
            Evaluation result.
        """
        has_fusion = bool(
            phase_collection.of_kind(ArtifactKind.FUSION_DECISION, latest_only=True)
        )
        if phase_key == "phase5" or has_fusion:
            population_size, max_cluster_size, merged_count = self._compute_l3_percolation(
                phase_collection, cumulative_collection
            )
        else:
            population_size, max_cluster_size, merged_count = self._compute_l2_percolation(
                phase_collection, cumulative_collection
            )

        cluster_fraction = (
            float(max_cluster_size) / float(population_size)
            if population_size > 0
            else 0.0
        )

        metrics: dict[str, float] = {
            "population_size": float(population_size),
            "max_cluster_size": float(max_cluster_size),
            "merged_count": float(merged_count),
            "max_cluster_fraction": cluster_fraction,
            "threshold_fraction": self.max_cluster_fraction,
        }

        passed = True
        message = (
            f"PercolationQualityGate passed after '{phase_key}' "
            f"(max_cluster={max_cluster_size}/{population_size}, ratio={cluster_fraction:.3f})."
        )
        if (
            population_size >= self.min_population
            and max_cluster_size > 1
            and cluster_fraction > self.max_cluster_fraction
        ):
            passed = False
            message = (
                f"PercolationQualityGate violation after '{phase_key}': "
                f"largest equivalence class {max_cluster_size}/{population_size} "
                f"({cluster_fraction:.3f}) exceeds rho_max={self.max_cluster_fraction:.3f}."
            )

        return _finalize_gate_evaluation(
            gate_name=self.name,
            phase_key=phase_key,
            passed=passed,
            on_violation=self.on_violation,
            metrics=metrics,
            message=message,
        )


class ConformalCalibrationGate:
    """Post-Phase 3 and Phase 4 quality gate monitoring conformal prediction set health.

    Tracks the empirical rate of empty (:math:`|C(X)| = 0`, indicating severe
    out-of-distribution shift) and ambiguous (:math:`|C(X)| > 1`, indicating
    multi-class uncertainty escalation) conformal prediction sets.

    Parameters
    ----------
    max_empty_rate : float, default 0.30
        Maximum allowed fraction of empty prediction sets :math:`|C(X)| = 0`.
    max_ambiguous_rate : float, default 0.70
        Maximum allowed fraction of ambiguous prediction sets :math:`|C(X)| > 1`.
    max_ood_rate : float, default 0.70
        Maximum allowed combined non-singleton rate :math:`|C(X)| \\ne 1`.
    min_samples : int, default 1
        Minimum number of observed conformal evaluations before bounds are enforced.
    on_violation : Literal["warn", "raise"], default "warn"
        Action taken when OOD rates exceed configured bounds.
    decision_engine : DecisionEngine or None, optional
        Optional decision engine reference (e.g. :class:`ObservableDecisionEngine`)
        from which phase-level recorded prediction sets are harvested.
    target_phases : frozenset of str, optional
        Phase keys after which this gate is evaluated (defaults to
        ``{"phase3", "phase4"}``).
    """

    def __init__(
        self,
        *,
        max_empty_rate: float = 0.30,
        max_ambiguous_rate: float = 0.70,
        max_ood_rate: float = 0.70,
        min_samples: int = 1,
        on_violation: Literal["warn", "raise"] = "warn",
        decision_engine: DecisionEngine | None = None,
        target_phases: frozenset[str] = frozenset({"phase3", "phase4"}),
    ) -> None:
        self.max_empty_rate = max_empty_rate
        self.max_ambiguous_rate = max_ambiguous_rate
        self.max_ood_rate = max_ood_rate
        self.min_samples = min_samples
        self.on_violation: Literal["warn", "raise"] = on_violation
        self.decision_engine = decision_engine
        self._target_phases = frozenset(target_phases)

    @property
    def name(self) -> str:
        """Return the gate identifier."""
        return "conformal_calibration_gate"

    @property
    def target_phases(self) -> frozenset[str]:
        """Return target phase keys."""
        return self._target_phases

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint dictionary.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of gate parameters.
        """
        return {
            "class": self.__class__.__name__,
            "name": self.name,
            "max_empty_rate": self.max_empty_rate,
            "max_ambiguous_rate": self.max_ambiguous_rate,
            "max_ood_rate": self.max_ood_rate,
            "min_samples": self.min_samples,
            "on_violation": self.on_violation,
            "target_phases": sorted(self._target_phases),
        }

    def _collect_prediction_set_sizes(
        self,
        phase_collection: ArtifactCollection,
    ) -> list[int]:
        """Extract conformal prediction set cardinalities from phase artifacts and engine."""
        sizes: list[int] = []
        for env in phase_collection.artifacts:
            meta = env.metadata
            if "prediction_set" in meta:
                ps = meta["prediction_set"]
                if isinstance(ps, (list, tuple, set)):
                    sizes.append(len(ps))
            elif "prediction_set_size" in meta:
                ps_size = meta["prediction_set_size"]
                if isinstance(ps_size, (int, float)):
                    sizes.append(int(ps_size))
            elif "prediction_sets" in meta:
                ps_list = meta["prediction_sets"]
                if isinstance(ps_list, (list, tuple)):
                    for item in ps_list:
                        if isinstance(item, (list, tuple, set)):
                            sizes.append(len(item))
                        elif isinstance(item, (int, float)):
                            sizes.append(int(item))

            if isinstance(env.payload, TheoryAtomArtifact):
                params = env.payload.parameters
                if "prediction_set" in params and "prediction_set" not in meta:
                    ps_param = params["prediction_set"]
                    if isinstance(ps_param, (list, tuple, set)):
                        sizes.append(len(ps_param))
                elif (
                    "prediction_set_size" in params
                    and "prediction_set_size" not in meta
                ):
                    ps_param_size = params["prediction_set_size"]
                    if isinstance(ps_param_size, (int, float)):
                        sizes.append(int(ps_param_size))

        if isinstance(self.decision_engine, ObservableDecisionEngine):
            recorded = self.decision_engine.consume_prediction_sets()
            if not sizes and recorded:
                sizes.extend(len(ps) for ps in recorded)

        return sizes

    def evaluate(
        self,
        phase_key: str,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
        context: ArtifactExecutionContext | None = None,
    ) -> QualityGateResult:
        """Evaluate conformal prediction set empty and ambiguous rates.

        Parameters
        ----------
        phase_key : str
            Completed phase key ('phase3' or 'phase4').
        phase_collection : ArtifactCollection
            Artifacts emitted by ``phase_key``.
        cumulative_collection : ArtifactCollection
            Cumulative artifacts up to ``phase_key``.
        context : ArtifactExecutionContext or None, optional
            Active execution context.

        Returns
        -------
        QualityGateResult
            Evaluation result.
        """
        sizes = self._collect_prediction_set_sizes(phase_collection)
        sample_count = len(sizes)
        if sample_count == 0 or sample_count < self.min_samples:
            metrics = {
                "sample_count": float(sample_count),
                "empty_rate": 0.0,
                "ambiguous_rate": 0.0,
                "singleton_rate": 0.0,
                "ood_rate": 0.0,
            }
            return _finalize_gate_evaluation(
                gate_name=self.name,
                phase_key=phase_key,
                passed=True,
                on_violation=self.on_violation,
                metrics=metrics,
                message=(
                    f"ConformalCalibrationGate skipped after '{phase_key}' "
                    f"(samples={sample_count} < min_samples={self.min_samples})."
                ),
            )

        empty_count = sum(1 for s in sizes if s == 0)
        singleton_count = sum(1 for s in sizes if s == 1)
        ambiguous_count = sum(1 for s in sizes if s > 1)

        empty_rate = float(empty_count) / float(sample_count)
        singleton_rate = float(singleton_count) / float(sample_count)
        ambiguous_rate = float(ambiguous_count) / float(sample_count)
        ood_rate = float(empty_count + ambiguous_count) / float(sample_count)

        metrics = {
            "sample_count": float(sample_count),
            "empty_count": float(empty_count),
            "singleton_count": float(singleton_count),
            "ambiguous_count": float(ambiguous_count),
            "empty_rate": empty_rate,
            "singleton_rate": singleton_rate,
            "ambiguous_rate": ambiguous_rate,
            "ood_rate": ood_rate,
        }

        reasons: list[str] = []
        if empty_rate > self.max_empty_rate:
            reasons.append(
                f"empty prediction set rate {empty_rate:.3f} > max_empty_rate={self.max_empty_rate:.3f}"
            )
        if ambiguous_rate > self.max_ambiguous_rate:
            reasons.append(
                f"ambiguous prediction set rate {ambiguous_rate:.3f} > max_ambiguous_rate={self.max_ambiguous_rate:.3f}"
            )
        if ood_rate > self.max_ood_rate:
            reasons.append(
                f"conformal OOD rate {ood_rate:.3f} > max_ood_rate={self.max_ood_rate:.3f}"
            )

        passed = len(reasons) == 0
        message = (
            f"ConformalCalibrationGate passed after '{phase_key}' "
            f"(samples={sample_count}, empty_rate={empty_rate:.3f}, ambiguous_rate={ambiguous_rate:.3f})."
            if passed
            else f"ConformalCalibrationGate violation after '{phase_key}': {'; '.join(reasons)}."
        )
        return _finalize_gate_evaluation(
            gate_name=self.name,
            phase_key=phase_key,
            passed=passed,
            on_violation=self.on_violation,
            metrics=metrics,
            message=message,
        )


def build_default_quality_gates(
    config: PipelineConfig | QualityGatesConfig | None = None,
    *,
    decision_engine: DecisionEngine | None = None,
) -> tuple[EpistemicQualityGate, ...]:
    """Construct the standard suite of inter-phase epistemic quality gates.

    Parameters
    ----------
    config : PipelineConfig or QualityGatesConfig or None, optional
        Pipeline or quality gates configuration.
    decision_engine : DecisionEngine or None, optional
        Active decision engine for conformal prediction set monitoring.

    Returns
    -------
    tuple of EpistemicQualityGate
        Configured ``(OntologyEntropyGate, PercolationQualityGate, ConformalCalibrationGate)``
        or empty tuple if quality gates are disabled in configuration.
    """
    if isinstance(config, PipelineConfig):
        gate_cfg = config.quality_gates
    elif isinstance(config, QualityGatesConfig):
        gate_cfg = config
    else:
        gate_cfg = QualityGatesConfig()

    if not gate_cfg.enabled:
        return ()

    return (
        OntologyEntropyGate(
            min_entropy=gate_cfg.min_entity_type_entropy,
            max_dominant_type_ratio=gate_cfg.max_dominant_type_ratio,
            min_entities=gate_cfg.min_entities_for_entropy,
            min_entity_density=gate_cfg.min_entity_density,
            require_nonzero_density=gate_cfg.min_entity_density > 0.0,
            on_violation=gate_cfg.on_violation,
        ),
        PercolationQualityGate(
            max_cluster_fraction=gate_cfg.max_percolation_fraction,
            min_population=gate_cfg.min_population_for_percolation,
            on_violation=gate_cfg.on_violation,
        ),
        ConformalCalibrationGate(
            max_empty_rate=gate_cfg.max_conformal_empty_rate,
            max_ambiguous_rate=gate_cfg.max_conformal_ambiguous_rate,
            max_ood_rate=gate_cfg.max_conformal_ood_rate,
            min_samples=gate_cfg.min_conformal_samples,
            on_violation=gate_cfg.on_violation,
            decision_engine=decision_engine,
        ),
    )
