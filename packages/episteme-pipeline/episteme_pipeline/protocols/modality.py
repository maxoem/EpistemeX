"""Structural protocol and normalization helpers for propositional modal strength estimation.

Grounding:
- Toulmin (1958): Modal Qualifier Q on propositions.
- Schurz (2014): Structuralist Epistemic Status and Scope Types.
- Decoupled QBAF: Prior base score tau_0(a) = M(phi_a).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from episteme_pipeline.contracts.domain import TheoryAtom
from episteme_pipeline.protocols.fingerprint import Fingerprintable


@runtime_checkable
class ModalStrengthResolver(Fingerprintable, Protocol):
    """Structural protocol for resolving author propositional modal certainty M(phi).

    Implementations resolve the author's epistemic commitment to a claim, combining
    symbolic structuralist properties (ScopeType, EpistemicStatus) with empirical
    linguistic hedging evaluations (DecisionEngine / LLM).
    """

    async def resolve_modality(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Asynchronously resolve author propositional certainty M(phi) in [0.0, 1.0].

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom containing syntactic structuralist attributes.
        context : str or None, optional
            Surrounding sentence or textual context for linguistic hedge analysis.

        Returns
        -------
        float
            Calibrated or bounded propositional modal certainty M(phi) in [0.0, 1.0].
        """
        ...

    def resolve_modality_sync(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Synchronously resolve author propositional certainty M(phi) in [0.0, 1.0].

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom containing syntactic structuralist attributes.
        context : str or None, optional
            Surrounding sentence or textual context for linguistic hedge analysis.

        Returns
        -------
        float
            Calibrated or bounded propositional modal certainty M(phi) in [0.0, 1.0].
        """
        ...


def ensure_modal_strength_resolver(resolver: Any | None) -> ModalStrengthResolver | None:
    """Normalize an optional user-supplied object into a ModalStrengthResolver.

    Parameters
    ----------
    resolver : Any or None
        Candidate resolver instance.

    Returns
    -------
    ModalStrengthResolver or None
        Validated resolver instance, or None if resolver is None.

    Raises
    ------
    TypeError
        If resolver is not None and does not satisfy the ModalStrengthResolver protocol.
    """
    if resolver is None:
        return None
    if isinstance(resolver, ModalStrengthResolver):
        return resolver
    raise TypeError(
        f"{type(resolver).__name__} does not satisfy the ModalStrengthResolver protocol: "
        "it must implement resolve_modality and resolve_modality_sync."
    )
