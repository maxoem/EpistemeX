"""Calibrated cascade routing and deterministic stochastic auditing primitives.

Provides shared System 1 to System 2 cascade abstractions, including the typed
``TriageDecision[T]`` envelope and the deterministic PRF ``should_audit_deterministically``
(Pattern 4, ADR-0018).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import TYPE_CHECKING, Any, Generic, Iterator, TypeVar

if TYPE_CHECKING:
    from episteme_pipeline.protocols.decision import DecisionScore

T = TypeVar("T")


def should_audit_deterministically(
    run_seed: str,
    phase_key: str,
    item_id: str,
    audit_rate: float,
) -> bool:
    """Compute a reproducible Bernoulli audit decision in [0, 1) via SHA-256.

    Parameters
    ----------
    run_seed : str
        Deterministic seed (e.g., run identifier, chunk identifier, or document key).
    phase_key : str
        Phase or component identifier namespace (e.g., "phase4_acc", "phase4_arc").
    item_id : str
        Item or candidate pair identifier.
    audit_rate : float
        Target Bernoulli sampling probability in [0.0, 1.0].

    Returns
    -------
    bool
        True if deterministic pseudo-random variable is strictly less than audit_rate.
    """
    if audit_rate <= 0.0:
        return False
    if audit_rate >= 1.0:
        return True
    digest = hashlib.sha256(f"{run_seed}:{phase_key}:{item_id}".encode("utf-8")).digest()
    uniform_val = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return uniform_val < audit_rate


@dataclass(slots=True)
class TriageDecision(Generic[T]):
    """Uniform decision envelope for System 1 fast triage.

    Conforms to the dual-process cognitive architecture (ADR-0018 / Design Standards §3.4).

    Parameters
    ----------
    value : T
        The predicted domain output (e.g., matched L2Entity, predicted TheoryRelation, or None).
    decision : DecisionScore or Any or None, default None
        Raw DecisionScore or decision telemetry from the underlying DecisionEngine.
    empirical_accuracy : float, default 1.0
        Calibrated empirical accuracy frequency of being correct.
    prediction_set : list of str, default empty list
        Conformal prediction set guaranteeing 1 - alpha coverage.
    is_ambiguous : bool, default False
        True if conformal prediction set size != 1 or confidence below threshold.
    is_audit : bool, default False
        True if this item was flagged for deterministic calibration audit.
    """

    value: T
    decision: DecisionScore | Any | None = None
    empirical_accuracy: float = 1.0
    prediction_set: list[str] = field(default_factory=list)
    is_ambiguous: bool = False
    is_audit: bool = False

    def __iter__(self) -> Iterator[Any]:
        """Support legacy tuple unpacking: ``(value, decision, is_ambiguous)``.

        Returns
        -------
        Iterator of Any
            Iterator yielding (value, decision, is_ambiguous).
        """
        return iter((self.value, self.decision, self.is_ambiguous))
