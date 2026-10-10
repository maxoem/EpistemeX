from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)

InputT = TypeVar("InputT")


class PhaseRunner[InputT](ABC):
    """
    Base for every pipeline phase. Each phase accepts a typed input contract
    and returns an artifact collection. Phases may still project to the graph incrementally for crash resilience, but artifact collections are the runtime handoff.

    The Pipeline class composes PhaseRunner instances into a DAG and exposes
    .run(), .run_phase(n), and .run_from_phase(n).

    Dispatch contract (O-09)
    ------------------------
    The orchestrator needs three things from a phase that ``name`` cannot
    safely supply: which config block to fingerprint, whether to persist its
    artifacts, and which artifact view to feed it. Those used to be recovered
    by string-matching ``name`` (``name.startswith("Phase 3b")``), which made a
    display string load-bearing — renaming a phase silently changed its
    behaviour, and the match order mattered ("Phase 3b" had to be tested before
    "Phase 3"). They are now explicit class attributes.
    """

    #: Human-readable phase name. **Display only** — appears in manifests,
    #: reports and logs. Never dispatch on it.
    name: ClassVar[str]

    #: Stable machine key for this phase. Part of the orchestrator contract:
    #: the phase's config block is ``getattr(PipelineConfig, phase_key)`` and
    #: its persistence toggle is
    #: ``getattr(ExecutionConfig, f"persist_{phase_key}_artifacts")``.
    #: ``Pipeline.__init__`` validates both, so a typo fails at composition
    #: time rather than silently selecting the wrong config.
    phase_key: ClassVar[str]

    #: Artifact view class this phase consumes, e.g. ``Phase1ArtifactsView``.
    #: ``None`` means the phase is fed the raw ``PipelineInput`` — Phase 1 only.
    input_view: ClassVar[type | None] = None

    @abstractmethod
    async def run(self, input: InputT, context: ArtifactExecutionContext) -> ArtifactCollection: ...

    def components(self) -> dict[str, object]:
        """Discover all injected computational components attached to this runner.

        Recursively inspects runner attributes to discover objects implementing
        the ``Fingerprintable`` protocol, LLM facades, embedders, decision engines,
        and classifiers.

        Returns
        -------
        dict of str to object
            Mapping from dotted hierarchical path to component instances.
        """
        from episteme_pipeline.protocols.fingerprint import find_components

        return find_components(self)
