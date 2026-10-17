from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Callable, ClassVar, Iterator, TypeVar

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
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

    @property
    def event_emitter(self) -> EventEmitter:
        """Return the active contextual event emitter.

        Returns
        -------
        EventEmitter
            The domain event emitter for the current execution context.
        """
        return get_event_emitter()

    @contextmanager
    def progress_scope(
        self, task_name: str, total_items: int, description: str = ""
    ) -> Iterator[Callable[[int], None]]:
        """Emit ProgressStarted and guarantee ProgressCompleted in a finally block.

        Parameters
        ----------
        task_name : str
            Unique or readable name of the progress task.
        total_items : int
            Total number of units to be processed.
        description : str, optional
            Human-readable description of the task, defaults to runner name.

        Yields
        ------
        Iterator of Callable[[int], None]
            Advance callback taking an optional integer step (default 1).
        """
        self.event_emitter.emit(
            ProgressStarted(
                task_name=task_name,
                total_items=total_items,
                description=description or self.name,
            )
        )

        def advance(step: int = 1) -> None:
            self.event_emitter.emit(
                ProgressAdvanced(task_name=task_name, advance=step)
            )

        try:
            yield advance
        finally:
            self.event_emitter.emit(ProgressCompleted(task_name=task_name))

    @property
    def checkpoint_store(self) -> object | None:
        """Return the checkpoint store if supported by this runner's backend.

        Returns
        -------
        PhaseCheckpointStore or None
            Checkpoint store instance, or None if not supported.
        """
        return None


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
