"""Declarative workflow topology and phase dependency DAG (ISSUE-058).

Defines :class:`WorkflowNode` and :class:`WorkflowDAG`, decoupling phase
topology, artifact kind dependencies (``reads_kinds`` / ``writes_kinds``),
topological sorting, and inter-phase :class:`EpistemicQualityGate` bindings
from the composition root and execution engine.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.quality_gate import (
    EpistemicQualityGate,
    ensure_quality_gates,
)


@dataclass(frozen=True)
class WorkflowNode:
    """A single phase node in a :class:`WorkflowDAG`.

    Parameters
    ----------
    index : int
        1-based ordinal index in the workflow sequence.
    runner : PhaseRunner
        Phase runner instance executing the node's domain logic.
    phase_key : str
        Stable machine identifier for configuration and invalidation lookup.
    input_view : type or None
        Typed :class:`~episteme_pipeline.artifacts.execution.EpistemicStateView`
        subclass consumed by ``runner``, or ``None`` if it consumes raw
        :class:`~episteme_pipeline.contracts.phase_contracts.PipelineInput`.
    reads_kinds : frozenset of ArtifactKind, optional
        Artifact kinds read by this phase.
    writes_kinds : frozenset of ArtifactKind, optional
        Artifact kinds produced by this phase.
    quality_gates : tuple of EpistemicQualityGate, optional
        Inter-phase quality gates evaluated immediately after this node runs.
    explicit_dependencies : tuple of str or None, optional
        Explicit upstream ``phase_key`` dependencies overriding kind-based inference.
    """

    index: int
    runner: PhaseRunner[Any]
    phase_key: str
    input_view: type | None
    reads_kinds: frozenset[ArtifactKind] = frozenset()
    writes_kinds: frozenset[ArtifactKind] = frozenset()
    quality_gates: tuple[EpistemicQualityGate, ...] = ()
    explicit_dependencies: tuple[str, ...] | None = None

    @property
    def name(self) -> str:
        """Return the human-readable display name of the phase runner."""
        return self.runner.name


class WorkflowDAG(Fingerprintable):
    """Declarative directed acyclic graph of pipeline phases and quality gates.

    Validates phase runner contracts at composition time, resolves dataflow
    dependencies from ``reads_kinds`` and ``writes_kinds`` (or explicit
    ``dependencies``), and binds :class:`EpistemicQualityGate` checks to target
    phases.

    Parameters
    ----------
    phases : Sequence of PhaseRunner, optional
        Ordered sequence of phase runners to include in the workflow.
    quality_gates : Iterable of EpistemicQualityGate or None, optional
        Inter-phase quality gates to attach to matching ``phase_key`` nodes.
    task : str, default "knowledge_graph"
        Logical workflow task name.
    nodes : Sequence of WorkflowNode or None, optional
        Pre-constructed workflow nodes (if supplied, ``phases`` is ignored).
    """

    def __init__(
        self,
        phases: Sequence[PhaseRunner[Any]] = (),
        *,
        quality_gates: Iterable[EpistemicQualityGate] | None = None,
        task: str = "knowledge_graph",
        nodes: Sequence[WorkflowNode] | None = None,
    ) -> None:
        self.task = task
        self._quality_gates: tuple[EpistemicQualityGate, ...] = ensure_quality_gates(
            quality_gates
        )
        if nodes is not None:
            self._nodes: tuple[WorkflowNode, ...] = tuple(nodes)
        else:
            self._nodes = self._build_nodes(phases, self._quality_gates)

    @staticmethod
    def _build_nodes(
        phases: Sequence[PhaseRunner[Any]],
        quality_gates: tuple[EpistemicQualityGate, ...],
    ) -> tuple[WorkflowNode, ...]:
        """Validate phase runners and construct immutable :class:`WorkflowNode` entries."""
        entries: list[WorkflowNode] = []
        seen_phase_keys: set[str] = set()

        for i, runner in enumerate(phases, start=1):
            try:
                phase_key = runner.phase_key
            except AttributeError:
                try:
                    runner_name = runner.name
                except AttributeError:
                    runner_name = str(runner)
                raise TypeError(
                    f"PhaseRunner '{runner_name}' at index {i} must define a non-empty 'phase_key' attribute."
                ) from None

            if not phase_key or not isinstance(phase_key, str) or not phase_key.strip():
                try:
                    runner_name = runner.name
                except AttributeError:
                    runner_name = str(runner)
                raise TypeError(
                    f"PhaseRunner '{runner_name}' at index {i} has invalid 'phase_key' of type {type(phase_key)}."
                )

            if phase_key in seen_phase_keys:
                raise ValueError(
                    f"Duplicate phase_key '{phase_key}' found in pipeline phases at index {i}."
                )
            seen_phase_keys.add(phase_key)

            try:
                name = runner.name
                if not name:
                    raise AttributeError
            except AttributeError:
                raise TypeError(
                    f"PhaseRunner with phase_key '{phase_key}' at index {i} must define a non-empty 'name' attribute."
                ) from None

            try:
                input_view = runner.input_view
            except AttributeError:
                try:
                    input_view = runner.input_view_type  # type: ignore[attr-defined]
                except AttributeError:
                    input_view = None

            try:
                raw_reads = runner.reads_kinds
            except AttributeError:
                raw_reads = frozenset()

            if not raw_reads:
                try:
                    allowed = input_view._allowed_kinds  # type: ignore[union-attr]
                    reads_kinds: frozenset[ArtifactKind] = frozenset(allowed)
                except AttributeError:
                    reads_kinds = frozenset()
            else:
                reads_kinds = frozenset(raw_reads)

            try:
                raw_writes = runner.writes_kinds
                writes_kinds: frozenset[ArtifactKind] = (
                    frozenset(raw_writes) if raw_writes else frozenset()
                )
            except AttributeError:
                writes_kinds = frozenset()

            try:
                raw_deps = runner.dependencies
                explicit_deps = tuple(raw_deps) if raw_deps is not None else None
            except AttributeError:
                explicit_deps = None

            attached_gates = tuple(
                gate
                for gate in quality_gates
                if phase_key in gate.target_phases or "*" in gate.target_phases
            )

            entries.append(
                WorkflowNode(
                    index=i,
                    runner=runner,
                    phase_key=phase_key,
                    input_view=input_view,
                    reads_kinds=reads_kinds,
                    writes_kinds=writes_kinds,
                    quality_gates=attached_gates,
                    explicit_dependencies=explicit_deps,
                )
            )
        return tuple(entries)

    @classmethod
    def from_entries(
        cls,
        entries: Iterable[Any],
        *,
        quality_gates: Iterable[EpistemicQualityGate] | None = None,
        task: str = "knowledge_graph",
    ) -> WorkflowDAG:
        """Build a :class:`WorkflowDAG` from pre-existing node or entry objects.

        Parameters
        ----------
        entries : Iterable of Any
            Sequence of :class:`WorkflowNode` or mocked phase entry objects.
        quality_gates : Iterable of EpistemicQualityGate or None, optional
            Quality gates to attach.
        task : str, default "knowledge_graph"
            Logical task name.

        Returns
        -------
        WorkflowDAG
            Constructed workflow DAG.
        """
        gates = ensure_quality_gates(quality_gates)
        normalized_nodes: list[WorkflowNode] = []
        for idx, item in enumerate(entries, start=1):
            if isinstance(item, WorkflowNode):
                normalized_nodes.append(item)
                continue
            try:
                node_index = int(item.index)
            except AttributeError:
                node_index = idx
            runner = item.runner
            try:
                phase_key = str(item.phase_key)
            except AttributeError:
                try:
                    phase_key = str(runner.phase_key)
                except AttributeError:
                    phase_key = f"phase{node_index}"
            try:
                input_view = item.input_view
            except AttributeError:
                try:
                    input_view = item.input_view_type
                except AttributeError:
                    input_view = None
            try:
                reads_kinds = frozenset(item.reads_kinds)
            except (AttributeError, TypeError):
                reads_kinds = frozenset()
            try:
                writes_kinds = frozenset(item.writes_kinds)
            except (AttributeError, TypeError):
                writes_kinds = frozenset()

            attached = tuple(
                g for g in gates if phase_key in g.target_phases or "*" in g.target_phases
            )
            normalized_nodes.append(
                WorkflowNode(
                    index=node_index,
                    runner=runner,
                    phase_key=phase_key,
                    input_view=input_view,
                    reads_kinds=reads_kinds,
                    writes_kinds=writes_kinds,
                    quality_gates=attached,
                )
            )
        return cls(quality_gates=gates, task=task, nodes=normalized_nodes)

    @property
    def nodes(self) -> tuple[WorkflowNode, ...]:
        """Return the immutable tuple of workflow nodes."""
        return self._nodes

    @property
    def entries(self) -> list[WorkflowNode]:
        """Return workflow nodes as a list."""
        return list(self._nodes)

    @property
    def phases(self) -> list[PhaseRunner[Any]]:
        """Return the ordered list of phase runners in this workflow."""
        return [node.runner for node in self._nodes]

    @property
    def quality_gates(self) -> tuple[EpistemicQualityGate, ...]:
        """Return all epistemic quality gates registered on this workflow."""
        return self._quality_gates

    def __len__(self) -> int:
        """Return the number of phase nodes in the workflow."""
        return len(self._nodes)

    def phase_boundaries(self) -> list[tuple[int, str]]:
        """Return ``(ordinal, phase_name)`` boundaries for all workflow nodes.

        Returns
        -------
        list of tuple of (int, str)
            1-based ordinal and human-readable runner name pairs.
        """
        return [(node.index, node.runner.name) for node in self._nodes]

    def get_node(self, phase_key: str) -> WorkflowNode | None:
        """Look up a workflow node by its semantic ``phase_key``.

        Parameters
        ----------
        phase_key : str
            Machine key of the target phase.

        Returns
        -------
        WorkflowNode or None
            Matching workflow node, or ``None`` if not present.
        """
        for node in self._nodes:
            if node.phase_key == phase_key:
                return node
        return None

    def get_node_by_ordinal(self, ordinal: int) -> WorkflowNode | None:
        """Look up a workflow node by its 1-based ordinal index.

        Parameters
        ----------
        ordinal : int
            1-based phase index.

        Returns
        -------
        WorkflowNode or None
            Matching workflow node, or ``None`` if out of bounds.
        """
        for node in self._nodes:
            if node.index == ordinal:
                return node
        return None

    def gates_for_phase(self, phase_key: str) -> tuple[EpistemicQualityGate, ...]:
        """Return the quality gates bound to ``phase_key``.

        Parameters
        ----------
        phase_key : str
            Machine key of the phase.

        Returns
        -------
        tuple of EpistemicQualityGate
            Gates configured to run after ``phase_key``.
        """
        node = self.get_node(phase_key)
        if node is not None:
            return node.quality_gates
        return tuple(
            gate
            for gate in self._quality_gates
            if phase_key in gate.target_phases or "*" in gate.target_phases
        )

    def with_gates(
        self, gates: Iterable[EpistemicQualityGate]
    ) -> WorkflowDAG:
        """Return a new :class:`WorkflowDAG` with additional quality gates attached.

        Parameters
        ----------
        gates : Iterable of EpistemicQualityGate
            Additional quality gates to bind.

        Returns
        -------
        WorkflowDAG
            New workflow DAG instance with combined quality gates.
        """
        combined = (*self._quality_gates, *ensure_quality_gates(gates))
        return WorkflowDAG(
            phases=self.phases,
            quality_gates=combined,
            task=self.task,
        )

    def dependencies(self) -> dict[str, set[str]]:
        """Compute direct upstream ``phase_key`` dependencies for each node in the DAG.

        Resolves dependencies from explicit ``runner.dependencies`` when declared,
        or from ``node.reads_kinds & prev.writes_kinds`` producer-consumer edges.

        Returns
        -------
        dict of str to set of str
            Mapping from ``phase_key`` to its set of direct upstream ``phase_key``s.
        """
        deps: dict[str, set[str]] = {node.phase_key: set() for node in self._nodes}
        for i, node in enumerate(self._nodes):
            explicit_deps = node.explicit_dependencies
            if explicit_deps is None:
                try:
                    raw_deps = node.runner.dependencies
                    explicit_deps = tuple(raw_deps) if raw_deps is not None else None
                except AttributeError:
                    explicit_deps = None

            if explicit_deps is not None:
                deps[node.phase_key].update(explicit_deps)
            elif node.reads_kinds:
                for prev in self._nodes[:i]:
                    if node.reads_kinds & prev.writes_kinds:
                        deps[node.phase_key].add(prev.phase_key)
            elif not node.writes_kinds and i > 0 and node.input_view is None:
                deps[node.phase_key].add(self._nodes[i - 1].phase_key)
        return deps

    def topological_order(self) -> list[WorkflowNode]:
        """Return workflow nodes in a valid topological execution order.

        Uses Kahn's algorithm while preserving original registration order as a
        deterministic tie-breaker among independent branches.

        Returns
        -------
        list of WorkflowNode
            Topologically sorted workflow nodes.

        Raises
        ------
        ValueError
            If a cycle is detected in the phase dependency graph.
        """
        deps = self.dependencies()
        node_by_key = {node.phase_key: node for node in self._nodes}
        known_keys = set(node_by_key)

        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {k: [] for k in known_keys}
        for key, upstream_set in deps.items():
            valid_upstreams = [u for u in upstream_set if u in known_keys]
            in_degree[key] = len(valid_upstreams)
            for u in valid_upstreams:
                dependents[u].append(key)

        ready: list[WorkflowNode] = [
            node for node in self._nodes if in_degree[node.phase_key] == 0
        ]
        ordered: list[WorkflowNode] = []

        while ready:
            ready.sort(key=lambda n: n.index)
            current = ready.pop(0)
            ordered.append(current)
            for child_key in dependents[current.phase_key]:
                in_degree[child_key] -= 1
                if in_degree[child_key] == 0:
                    ready.append(node_by_key[child_key])

        if len(ordered) != len(self._nodes):
            raise ValueError(
                "Cycle detected in WorkflowDAG phase dependencies."
            )
        return ordered

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic dictionary representation of the workflow topology.

        Returns
        -------
        dict of str to Any
            JSON-serializable topology and quality gate fingerprint payload.
        """
        deps = self.dependencies()
        return {
            "class": self.__class__.__name__,
            "task": self.task,
            "nodes": [
                {
                    "index": node.index,
                    "phase_key": node.phase_key,
                    "name": node.name,
                    "reads_kinds": sorted(str(k.value) for k in node.reads_kinds),
                    "writes_kinds": sorted(str(k.value) for k in node.writes_kinds),
                    "dependencies": sorted(deps.get(node.phase_key, set())),
                    "quality_gates": [g.fingerprint() for g in node.quality_gates],
                }
                for node in self._nodes
            ],
        }
