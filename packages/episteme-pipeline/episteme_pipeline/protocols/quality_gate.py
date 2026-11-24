"""Protocol and contracts for inter-phase epistemic quality gates (ISSUE-058).

Defines the :class:`EpistemicQualityGate` protocol, :class:`QualityGateResult`
contract, :class:`QualityGateViolationError`, :class:`QualityGateWarning`,
and composition-root normalization helpers.

References
----------
.. [1] Shannon, C. E. (1948). A Mathematical Theory of Communication.
   Bell System Technical Journal, 27(3), 379-423.
.. [2] Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic Learning in a
   Random World. Springer.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from episteme_pipeline.protocols.fingerprint import Fingerprintable

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactCollection,
        ArtifactExecutionContext,
    )


class QualityGateWarning(UserWarning):
    """Warning emitted when an epistemic quality gate breaches a soft threshold."""


class QualityGateResult(BaseModel):
    """Evaluation result returned by an :class:`EpistemicQualityGate`.

    Parameters
    ----------
    gate_name : str
        Unique identifier of the quality gate.
    phase_key : str
        Machine key of the phase whose artifacts were evaluated.
    passed : bool
        Whether the phase artifacts satisfied all homeostatic bounds.
    severity : Literal["pass", "warn", "halt"], default "pass"
        Action severity resolved from the evaluation outcome and gate policy.
    metrics : dict of str to float
        Quantitative telemetry computed by the gate (e.g., Shannon entropy,
        largest component ratio, conformal OOD rate).
    message : str, default ""
        Human-readable diagnostic summary.
    """

    model_config = ConfigDict(frozen=True)

    gate_name: str
    phase_key: str
    passed: bool
    severity: Literal["pass", "warn", "halt"] = "pass"
    metrics: dict[str, float] = Field(default_factory=dict)
    message: str = ""


class QualityGateViolationError(RuntimeError):
    """Exception raised when an :class:`EpistemicQualityGate` halts pipeline execution.

    Parameters
    ----------
    result : QualityGateResult
        The failing quality gate evaluation result.
    """

    def __init__(self, result: QualityGateResult) -> None:
        self.result = result
        self.gate_name = result.gate_name
        self.phase_key = result.phase_key
        self.metrics = dict(result.metrics)
        message = (
            result.message
            or f"Epistemic quality gate '{result.gate_name}' failed after phase '{result.phase_key}'."
        )
        super().__init__(message)


@runtime_checkable
class EpistemicQualityGate(Fingerprintable, Protocol):
    """Protocol for inter-phase homeostatic circuit breakers over artifact collections.

    Implementations inspect the phase-emitted and cumulative
    :class:`~episteme_pipeline.artifacts.execution.ArtifactCollection` between
    phases to detect structural or calibration pathologies (such as ontological
    collapse, giant-component percolation, or conformal OOD spikes) before
    downstream compute is expended.
    """

    @property
    def name(self) -> str:
        """Return the unique identifier of this quality gate.

        Returns
        -------
        str
            Gate identifier string.
        """
        ...

    @property
    def target_phases(self) -> frozenset[str]:
        """Return the set of ``phase_key`` strings after which this gate executes.

        Returns
        -------
        frozenset of str
            Target ``phase_key`` identifiers (or ``frozenset({"*"})`` for all phases).
        """
        ...

    def evaluate(
        self,
        phase_key: str,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
        context: ArtifactExecutionContext | None = None,
    ) -> QualityGateResult:
        """Evaluate epistemic quality invariants after ``phase_key`` completes.

        Parameters
        ----------
        phase_key : str
            Machine key of the completed phase.
        phase_collection : ArtifactCollection
            Artifacts emitted specifically by ``phase_key``.
        cumulative_collection : ArtifactCollection
            Cumulative artifacts accumulated across the workflow up to and
            including ``phase_key``.
        context : ArtifactExecutionContext or None, optional
            Active phase execution context.

        Returns
        -------
        QualityGateResult
            Structured quality evaluation outcome.
        """
        ...


def ensure_quality_gate(gate: Any) -> EpistemicQualityGate:
    """Validate and normalize a candidate object as an :class:`EpistemicQualityGate`.

    Parameters
    ----------
    gate : Any
        Object expected to implement :class:`EpistemicQualityGate`.

    Returns
    -------
    EpistemicQualityGate
        The validated quality gate instance.

    Raises
    ------
    TypeError
        If ``gate`` does not satisfy the :class:`EpistemicQualityGate` protocol.
    """
    if isinstance(gate, EpistemicQualityGate):
        return gate
    raise TypeError(
        f"Expected an EpistemicQualityGate implementation (defining 'name', "
        f"'target_phases', 'evaluate', and 'fingerprint'), got {type(gate).__name__}."
    )


def ensure_quality_gates(
    gates: Iterable[Any] | None,
) -> tuple[EpistemicQualityGate, ...]:
    """Normalize an optional iterable of quality gates into an immutable tuple.

    Parameters
    ----------
    gates : Iterable of Any or None
        Candidate quality gate instances.

    Returns
    -------
    tuple of EpistemicQualityGate
        Validated quality gates in registration order.
    """
    if gates is None:
        return ()
    return tuple(ensure_quality_gate(g) for g in gates)
