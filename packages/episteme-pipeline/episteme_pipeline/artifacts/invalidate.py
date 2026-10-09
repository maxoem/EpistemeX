"""Artifact dependency graph diffing for selective stale-artifact invalidation.

Builds a directed acyclic graph of artifact identity keys with edges from
upstream dependencies, then detects which artifacts are stale because their
``dependency_fingerprint`` changed with respect to a prior run.

Key spaces
----------
Every artifact carries **two** identifiers, and they never coincide:

``artifact_id``    ``f"artifact::{x}"``  — how other artifacts *reference* it
                                          (``provenance.upstream_artifact_ids``)
``identity_key``   ``f"{kind}::{x}"``    — how this graph *indexes* it

Edges therefore have to be translated: the raw provenance references are
``artifact_id``s, while nodes are keyed by ``identity_key``. Storing edges
without translating them (the original behaviour) produced a graph whose
adjacency maps shared no keys with its node map, so staleness never propagated
and ``topsort`` degenerated to insertion order — silently, since both are
plain ``str``.

Edges are resolved lazily from a ``artifact_id -> identity_key`` index built as
nodes are added, so ``add()`` remains order-independent: an artifact may be
added before the upstream artifacts it references.
"""

from __future__ import annotations


from collections import defaultdict, deque

from episteme_pipeline.artifacts.models import ArtifactEnvelope


class ArtifactDependencyGraph:
    """A directed DAG of artifact identities and their dependency relationships.

    Nodes are keyed by ``identity_key``. ``upstream``/``downstream`` are keyed by
    ``identity_key`` on both sides — provenance ``artifact_id`` references are
    translated on access.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, ArtifactEnvelope] = {}
        self._identity_by_artifact_id: dict[str, str] = {}
        self._raw_upstream: dict[str, tuple[str, ...]] = {}
        self._downstream: dict[str, set[str]] = defaultdict(set)
        self._upstream: dict[str, set[str]] = defaultdict(set)
        self._unresolved_upstream: dict[str, set[str]] = defaultdict(set)
        self._edges_resolved = False

    def add(self, artifact: ArtifactEnvelope) -> None:
        key = artifact.identity_key
        if key is None:
            return
        self.nodes[key] = artifact
        self._identity_by_artifact_id[artifact.artifact_id] = key
        self._raw_upstream[key] = tuple(artifact.provenance.upstream_artifact_ids)
        self._edges_resolved = False

    def _resolve_edges(self) -> None:
        """Translate provenance ``artifact_id`` references into ``identity_key`` edges."""
        if self._edges_resolved:
            return
        self._downstream = defaultdict(set)
        self._upstream = defaultdict(set)
        self._unresolved_upstream = defaultdict(set)
        for key, raw_ids in self._raw_upstream.items():
            for up_id in raw_ids:
                up_key = self._identity_by_artifact_id.get(up_id)
                if up_key is None:
                    # The referenced artifact is not part of this artifact set —
                    # e.g. a phase hydrated from a parent run whose artifacts were
                    # not loaded. Recorded rather than dropped so callers can see
                    # that the graph is incomplete instead of reading a missing
                    # edge as "no dependency".
                    self._unresolved_upstream[key].add(up_id)
                    continue
                self._downstream[up_key].add(key)
                self._upstream[key].add(up_key)
        self._edges_resolved = True

    @property
    def downstream(self) -> dict[str, set[str]]:
        """``{identity_key: set(identity_key)}`` — dependents of each node."""
        self._resolve_edges()
        return self._downstream

    @property
    def upstream(self) -> dict[str, set[str]]:
        """``{identity_key: set(identity_key)}`` — dependencies of each node."""
        self._resolve_edges()
        return self._upstream

    @property
    def unresolved_upstream(self) -> dict[str, set[str]]:
        """``{identity_key: set(artifact_id)}`` — references to artifacts not in this set."""
        self._resolve_edges()
        return self._unresolved_upstream

    def topsort(self) -> list[str]:
        """Kahn's algorithm for topological ordering of the DAG."""
        downstream = self.downstream
        upstream = self.upstream
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        for nid in self.nodes:
            for dep in upstream.get(nid, set()):
                if dep in in_degree:
                    in_degree[nid] += 1
        queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for child in downstream.get(nid, set()):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        if len(order) != len(self.nodes):
            raise ValueError("Dependency graph has a cycle")
        return order

    @classmethod
    def from_artifacts(
        cls, artifacts: list[ArtifactEnvelope]
    ) -> ArtifactDependencyGraph:
        g = cls()
        for art in artifacts:
            g.add(art)
        return g

    def build_kind_staleness_map(
        self,
        prior_fps: dict[str, str],
        prior_artifacts: list[ArtifactEnvelope] | None = None,
    ) -> dict[str, list[str]]:
        """{kind: stale_identity_keys} grouped by ArtifactKind.

        Useful so upstream callers can map stale deps back to the
        phase that would need re-execution (each phase produces a
        fixed set of artifact kinds).
        """
        stale_nodes = find_stale_nodes(self, prior_fps, prior_artifacts=prior_artifacts)
        result: dict[str, list[str]] = {}
        for nid in stale_nodes:
            art = self.nodes[nid]
            kind_key = (
                str(art.kind)
                if hasattr(art.kind, "__str__")
                else str(type(art.kind).__name__)
            )
            result.setdefault(kind_key, []).append(nid)
        return result

    def build_phase_staleness_map(
        self,
        prior_fps: dict[str, str],
        prior_artifacts: list[ArtifactEnvelope] | None = None,
    ) -> dict[str, list[str]]:
        """{phase_name: stale_identity_keys} grouped by ArtifactEnvelop.phase_name.

        Useful because _choose_reuse_source invalidates by phase_name.
        """
        stale_nodes = find_stale_nodes(self, prior_fps, prior_artifacts=prior_artifacts)
        result: dict[str, list[str]] = {}
        for nid in stale_nodes:
            art = self.nodes[nid]
            result.setdefault(art.phase_name, []).append(nid)
        return result


def _build_prior_upstream(
    prior_artifacts: list[ArtifactEnvelope],
) -> dict[str, set[str]]:
    """Extract {identity_key: set(upstream_artifact_ids)} from prior artifacts."""
    upstream: dict[str, set[str]] = {}
    for art in prior_artifacts:
        if art.identity_key:
            upstream[art.identity_key] = set(art.provenance.upstream_artifact_ids)
    return upstream


def _compare_dag_structures(
    current: ArtifactDependencyGraph, prior_upstream: dict[str, set[str]]
) -> set[str]:
    """Return node keys whose provenance edge set diverged between current and prior.

    Structural staleness occurs when the actual upstream dependency set of a node
    changed — different upstream artifacts present/absent — even if its
    ``dependency_fingerprint`` happened to match.
    """
    structurally_stale: set[str] = set()
    all_keys = set(current.nodes.keys()) | set(prior_upstream.keys())

    for nid in all_keys:
        art = current.nodes.get(nid)
        prior_deps = prior_upstream.get(nid)
        if art is None:
            # Node existed in prior run but is absent in current DAG
            structurally_stale.add(nid)
            continue
        if prior_deps is None:
            current_deps = set(art.provenance.upstream_artifact_ids)
            if current_deps:
                structurally_stale.add(nid)
            continue
        current_deps = set(art.provenance.upstream_artifact_ids)
        if current_deps != prior_deps:
            structurally_stale.add(nid)
    return structurally_stale


def find_stale_nodes(
    dag: ArtifactDependencyGraph,
    prior_fps: dict[str, str],
    prior_upstream: dict[str, set[str]] | None = None,
    prior_artifacts: list[ArtifactEnvelope] | None = None,
) -> set[str]:
    """Return stale node identity keys with structural and fingerprint changes.

    A node is stale when:
    - It has no entry in ``prior_fps`` (new artifact with unknown prior), or
    - Its ``dependency_fingerprint`` differs from the stored prior value, or
    - Its provenance edge set differs from the prior graph (structural diff), or
    - It transitively depends on a stale node.

    Structural comparison uses ``prior_upstream`` when provided (precomputed
    ``{identity_key: upstream_set}``), or fallback to ``prior_artifacts``
    which are converted via ``_build_prior_upstream``.

    Propagates staleness breadth-first through the downstream edges.
    """
    stale: set[str] = set()
    q: deque[str] = deque()

    if prior_upstream is None and prior_artifacts is not None:
        prior_upstream = _build_prior_upstream(prior_artifacts)

    structurally_stale = _compare_dag_structures(dag, prior_upstream or {})

    for nid, art in dag.nodes.items():
        if art.dependency_fingerprint is None:
            continue
        prior_fp = prior_fps.get(nid)
        is_structural = nid in structurally_stale
        if prior_fp is None or art.dependency_fingerprint != prior_fp or is_structural:
            stale.add(nid)
            q.append(nid)

    while q:
        nid = q.popleft()
        for child in list(dag.downstream.get(nid, [])):
            if child not in stale:
                stale.add(child)
                q.append(child)

    return stale


def build_prior_fingerprints(
    artifacts: list[ArtifactEnvelope],
) -> dict[str, str]:
    """Extract {identity_key: dependency_fingerprint} map from artifacts."""
    fps: dict[str, str] = {}
    for art in artifacts:
        if art.identity_key and art.dependency_fingerprint:
            fps[art.identity_key] = art.dependency_fingerprint
    return fps
