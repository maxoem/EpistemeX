"""Hexagonal port protocols for closed-loop hermeneutic refinement (ISSUE-053).

Defines narrow, ``@runtime_checkable`` interfaces extending
:class:`~episteme_pipeline.protocols.fingerprint.Fingerprintable` for top-down
epistemic deficit detection (L4/L3 -> L2/L1) and localized targeted refinement
across enthymeme gaps, polysemy collisions, and ungrounded axioms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

from episteme_pipeline.contracts.domain import EpistemicDeficit, RefinementDelta
from episteme_pipeline.protocols.fingerprint import Fingerprintable

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactCollection,
        ArtifactExecutionContext,
        EpistemicStateView,
    )
    from episteme_pipeline.config import HermeneuticRefinementConfig

ProtocolT = TypeVar("ProtocolT")


@runtime_checkable
class EpistemicDeficitDetector(Fingerprintable, Protocol):
    """Port for detecting top-down epistemic deficits across L3/L4 state."""

    def detect_deficits(
        self,
        state: EpistemicStateView,
        *,
        refinement_pass: int = 0,
        config: HermeneuticRefinementConfig | None = None,
        context: ArtifactExecutionContext | None = None,
    ) -> list[EpistemicDeficit]:
        """Inspect cumulative epistemic state and emit prioritized deficits.

        Parameters
        ----------
        state : EpistemicStateView
            Cumulative epistemic view (typically ``Phase4ArtifactsView`` or
            ``EpistemicDeficitArtifactsView``) containing L1–L4 artifacts.
        refinement_pass : int, default 0
            Current refinement cycle index recorded on emitted deficits.
        config : HermeneuticRefinementConfig or None, optional
            Optional refinement thresholds overriding detector defaults.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for run lineage metadata.

        Returns
        -------
        list of EpistemicDeficit
            Detected deficits ordered by descending severity/priority.
        """
        ...


@runtime_checkable
class ConditionalRefinementHandler(Protocol):
    """Capability protocol for refinement handlers whose availability depends on runtime ports."""

    @property
    def is_available(self) -> bool:
        """Return True when required runtime ports are wired and ready."""
        ...


@runtime_checkable
class TheoryGuidedPremiseRecoverer(Fingerprintable, Protocol):
    """Port for recovering implicit premises (enthymemes) under a theory lens."""

    async def recover_premises(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Perform localized theory-guided gleaning for an ``ENTHYMEME_GAP``.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``ENTHYMEME_GAP`` deficit naming target chunks, atoms, and
            conditioning ``theory_lens``.
        state : EpistemicStateView
            Cumulative epistemic state view providing chunks, entities, and atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context.

        Returns
        -------
        RefinementDelta
            Recovered implicit premise atoms and dialectical relations.
        """
        ...


@runtime_checkable
class TargetedConceptSplitter(Fingerprintable, Protocol):
    """Port for splitting polysemous L2 hub entities implicated by collisions."""

    async def split_concept(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Split a conflated entity for a ``POLYSEMY_COLLISION`` deficit.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``POLYSEMY_COLLISION`` deficit naming target entities, chunks,
            and incompatible theory communities.
        state : EpistemicStateView
            Cumulative epistemic state view providing entities, conceptions, and
            affected triples/atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context.

        Returns
        -------
        RefinementDelta
            Sense-disambiguated entities, rewritten local/global triples and atoms,
            and ``cannot_link_pairs`` preventing downstream re-merging.
        """
        ...


@runtime_checkable
class LocalizedAxiomGrounder(Fingerprintable, Protocol):
    """Port for re-grounding ungrounded axioms and recovering observations."""

    async def ground_axiom(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Perform localized observation/parameter recovery for ``UNGROUNDED_AXIOM``.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``UNGROUNDED_AXIOM`` deficit naming target chunks, atoms, and
            conditioning theory parameters.
        state : EpistemicStateView
            Cumulative epistemic state view providing source and neighbor chunks.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context.

        Returns
        -------
        RefinementDelta
            Recovered entities, observation atoms, empirical measurements, and
            support relations grounding the axiom.
        """
        ...


@runtime_checkable
class TargetedRefinementPort(Fingerprintable, Protocol):
    """Unified port dispatching a single epistemic deficit to a localized refiner."""

    async def refine_deficit(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Route a single epistemic deficit to its localized refinement handler.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Epistemic deficit to address.
        state : EpistemicStateView
            Cumulative epistemic state view.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context.

        Returns
        -------
        RefinementDelta
            Localized refinement output delta.
        """
        ...


@runtime_checkable
class HermeneuticRefinementCoordinator(Fingerprintable, Protocol):
    """Coordinator port executing bounded closed-loop hermeneutic refinement."""

    async def refine(
        self,
        collection: ArtifactCollection,
        context: ArtifactExecutionContext,
        *,
        config: HermeneuticRefinementConfig | None = None,
    ) -> ArtifactCollection:
        """Execute bounded top-down refinement cycles over ``collection``.

        Parameters
        ----------
        collection : ArtifactCollection
            Cumulative artifact collection emitted by the forward pipeline pass.
        context : ArtifactExecutionContext
            Active run execution context carrying manifest and curation ledger.
        config : HermeneuticRefinementConfig or None, optional
            Optional refinement configuration overriding coordinator defaults.

        Returns
        -------
        ArtifactCollection
            Updated artifact collection overlaying localized delta artifacts,
            ``EpistemicDeficitArtifact`` records, and re-converged L3/L4 outputs.
        """
        ...


def _ensure_optional_protocol(
    candidate: Any | None,
    protocol_cls: type[ProtocolT],
    required_members: str,
) -> ProtocolT | None:
    """Validate an optional candidate object against a runtime-checkable protocol.

    Parameters
    ----------
    candidate : Any or None
        Candidate implementation object, or ``None``.
    protocol_cls : type
        Target ``@runtime_checkable`` protocol class.
    required_members : str
        Human-readable summary of expected protocol members for error reporting.

    Returns
    -------
    ProtocolT or None
        Validated protocol implementation, or ``None`` if ``candidate`` is ``None``.

    Raises
    ------
    TypeError
        If ``candidate`` is not ``None`` and does not satisfy ``protocol_cls``.
    """
    if candidate is None:
        return None
    if isinstance(candidate, protocol_cls):
        return candidate
    raise TypeError(
        f"{type(candidate).__name__} does not satisfy the {protocol_cls.__name__} "
        f"protocol: it must implement {required_members}."
    )


def ensure_deficit_detector(
    detector: Any | None,
) -> EpistemicDeficitDetector | None:
    """Validate and normalize an optional :class:`EpistemicDeficitDetector`.

    Parameters
    ----------
    detector : Any or None
        Candidate deficit detector instance.

    Returns
    -------
    EpistemicDeficitDetector or None
        Validated detector instance, or ``None``.
    """
    return _ensure_optional_protocol(
        detector, EpistemicDeficitDetector, "detect_deficits and fingerprint"
    )


def ensure_refinement_coordinator(
    coordinator: Any | None,
) -> HermeneuticRefinementCoordinator | None:
    """Validate and normalize an optional :class:`HermeneuticRefinementCoordinator`.

    Parameters
    ----------
    coordinator : Any or None
        Candidate refinement coordinator instance.

    Returns
    -------
    HermeneuticRefinementCoordinator or None
        Validated coordinator instance, or ``None``.
    """
    return _ensure_optional_protocol(
        coordinator, HermeneuticRefinementCoordinator, "refine and fingerprint"
    )
