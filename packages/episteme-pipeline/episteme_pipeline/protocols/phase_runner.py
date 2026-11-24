from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ClassVar, TypeVar

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.artifacts.models import ArtifactKind
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
    name: ClassVar[str] = ""

    #: Stable machine key for this phase. Part of the orchestrator contract:
    #: the phase's config block is ``PipelineConfig.get_phase_config(phase_key)`` and
    #: its persistence toggle is ``ExecutionConfig.should_persist_artifacts(phase_key)``.
    phase_key: ClassVar[str] = ""

    #: Artifact view class this phase consumes, e.g. ``Phase1ArtifactsView``.
    #: ``None`` means the phase is fed the raw ``PipelineInput`` — Phase 1 only.
    input_view: ClassVar[type | None] = None

    #: The set of artifact kinds consumed by this phase. Derived from
    #: ``input_view._allowed_kinds`` if empty, or declared explicitly.
    reads_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset()

    #: The set of artifact kinds produced and written by this phase.
    writes_kinds: ClassVar[frozenset[ArtifactKind]] = frozenset()

    #: Explicit upstream ``phase_key`` dependencies when not derived solely
    #: from ``reads_kinds`` / ``writes_kinds`` intersection.
    dependencies: ClassVar[tuple[str, ...] | None] = None

    #: Conformal decision task identifiers and config stage keys owned by this phase.
    conformal_tasks: ClassVar[frozenset[str]] = frozenset()
    _builtins_loaded: ClassVar[bool] = False

    @classmethod
    def _ensure_builtin_runners_loaded(cls) -> None:
        """Lazily import built-in phase runner modules so ``__subclasses__()`` is complete."""
        if cls._builtins_loaded:
            return
        cls._builtins_loaded = True
        for mod_path in (
            "episteme_pipeline.phases.phase1_foundation",
            "episteme_pipeline.phases.phase2_entity_discovery",
            "episteme_pipeline.phases.phase3_global_relations",
            "episteme_pipeline.phases.phase3b_consolidation",
            "episteme_pipeline.phases.phase4_entity_maturation",
            "episteme_pipeline.phases.phase4_argument_mining",
            "episteme_pipeline.phases.phase5_fusion.argument_web",
            "episteme_pipeline.phases.phase6_theorynet.runner",
            "episteme_pipeline.post_processing.theoretical_enrichment",
        ):
            try:
                __import__(mod_path)
            except Exception:  # noqa: BLE001, S110 baseline
                pass

    @classmethod
    def _iter_subclasses(cls) -> Iterator[type[PhaseRunner[object]]]:
        """Yield all concrete and abstract PhaseRunner subclasses recursively."""
        cls._ensure_builtin_runners_loaded()
        stack = list(cls.__subclasses__())
        seen: set[type[PhaseRunner[object]]] = set()
        while stack:
            sub = stack.pop()
            if sub in seen:
                continue
            seen.add(sub)
            yield sub
            stack.extend(sub.__subclasses__())

    @classmethod
    def resolve_phase_key(
        cls,
        target: type[PhaseRunner[object]] | PhaseRunner[object] | str,
    ) -> str:
        """Resolve a PhaseRunner class, instance, class name, or task ID to its canonical ``phase_key``.

        Parameters
        ----------
        target : type of PhaseRunner, PhaseRunner, or str
            PhaseRunner subclass, instance, class name (e.g. ``"Phase4Runner"``),
            canonical ``phase_key`` (e.g. ``"phase4"``), or owned conformal task ID.

        Returns
        -------
        str
            Canonical ``phase_key`` for the phase (or ``str(target)`` if unregistered).
        """
        if isinstance(target, PhaseRunner):
            return target.phase_key or target.__class__.__name__
        if isinstance(target, type) and issubclass(target, PhaseRunner):
            return target.phase_key or target.__name__
        if not isinstance(target, str):
            return str(target)

        for sub in cls._iter_subclasses():
            key = sub.phase_key
            if not key:
                continue
            if target == key or target == sub.__name__ or target in sub.conformal_tasks:
                return key
        return target

    @classmethod
    def related_identifiers(
        cls,
        target: type[PhaseRunner[object]] | PhaseRunner[object] | str,
    ) -> tuple[str, ...]:
        """Return all identifiers (``phase_key``, class name, and ``conformal_tasks``) for ``target``.

        Parameters
        ----------
        target : type of PhaseRunner, PhaseRunner, or str
            PhaseRunner subclass, instance, class name, ``phase_key``, or task ID.

        Returns
        -------
        tuple of str
            Ordered tuple of matching identifiers for the resolved phase.
        """
        canonical = cls.resolve_phase_key(target)
        identifiers: list[str] = []
        if isinstance(target, str):
            identifiers.append(target)
        if canonical not in identifiers:
            identifiers.append(canonical)

        for sub in cls._iter_subclasses():
            key = sub.phase_key
            if not key:
                continue
            if (
                canonical == key
                or target is sub
                or (isinstance(target, PhaseRunner) and isinstance(target, sub))
                or (
                    isinstance(target, str)
                    and (
                        target == key
                        or target == sub.__name__
                        or target in sub.conformal_tasks
                    )
                )
            ):
                if sub.__name__ not in identifiers:
                    identifiers.append(sub.__name__)
                for task_key in sorted(sub.conformal_tasks):
                    if task_key not in identifiers:
                        identifiers.append(task_key)
        return tuple(identifiers)

    def config_fingerprint(self) -> str | None:
        """Return optional stable configuration fingerprint for custom runners.

        Subclasses and custom post-processors may override this method to provide
        a deterministic SHA-256 fingerprint of runner-specific configuration when
        the runner does not correspond to a sub-config on ``PipelineConfig``.

        Returns
        -------
        str or None
            A deterministic fingerprint string, or None to defer to standard
            ``PipelineConfig.get_phase_config()`` resolution.
        """
        return None

    @abstractmethod
    async def run(
        self, input: InputT, context: ArtifactExecutionContext
    ) -> ArtifactCollection: ...

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
            self.event_emitter.emit(ProgressAdvanced(task_name=task_name, advance=step))

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
