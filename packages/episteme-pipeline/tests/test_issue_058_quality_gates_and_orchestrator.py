"""Deterministic unit and integration tests for ISSUE-058.

Verifies:
1. ``EpistemicQualityGate`` protocol, normalization helpers, and ``Fingerprintable``
   compliance across all built-in quality gates.
2. ``OntologyEntropyGate`` (Post-Phase 2): Shannon entropy $H(\\text{entity\\_types})$,
   dominant type ratio, and non-empty chunk entity density checks.
3. ``PercolationQualityGate`` (Post-Phase 3b & Phase 5): equivalence class
   percolation ratio $\\max |C| / |E| \\le \\rho_{\\max}$ across ``CanonicalizationArtifact``
   and ``FusionDecisionArtifact`` chains.
4. ``ConformalCalibrationGate`` (Post-Phase 3 & Phase 4): empty ($|C(X)| = 0$)
   and ambiguous ($|C(X)| > 1$) conformal prediction set rates from both artifact
   metadata/parameters and ``ObservableDecisionEngine``.
5. ``WorkflowDAG`` declarative topology resolution, topological sorting, cycle
   detection, and quality gate binding.
6. ``PipelineFactory`` composition root wiring and ``ArtifactExecutionEngine``
   runtime orchestration, caching, and circuit-breaker halting semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from episteme_pipeline.artifacts.builders import (
    build_canonicalization_artifact,
    build_chunk_artifact,
    build_entity_mention_artifact,
    build_fusion_cluster_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_theory_atom_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import PipelineConfig, QualityGatesConfig
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.events import (
    ComponentCompleted,
    ComponentStarted,
    PhaseFailed,
    QualityGateEvaluated,
    RunCompleted,
    RunFailed,
    RunStarted,
    SimpleEventEmitter,
    use_event_emitter,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.quality_gate import (
    EpistemicQualityGate,
    QualityGateViolationError,
    QualityGateWarning,
    ensure_quality_gate,
    ensure_quality_gates,
)
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.runs.models import RunStatus
from episteme_pipeline.runtime import (
    ArtifactExecutionEngine,
    ConformalCalibrationGate,
    OntologyEntropyGate,
    PercolationQualityGate,
    WorkflowDAG,
    build_default_quality_gates,
)

# ---------------------------------------------------------------------------
# Helpers & Stubs
# ---------------------------------------------------------------------------


def _make_linked_entity_env(
    entity_id: str,
    entity_type: str,
    name: str | None = None,
    run_id: str = "run-test",
) -> Any:
    """Create a LinkedEntityArtifact envelope for testing."""
    ent = L2Entity(
        id=entity_id,
        label=entity_type,
        name=name or f"Name_{entity_id}",
        textual_envelope="Sample philosophical context.",
        source_chunk_ids=["chunk_1"],
    )
    return build_linked_entity_artifact(
        ent,
        [f"artifact::mention::{entity_id}::chunk_1"],
        run_id=run_id,
        phase_name="Phase 2: Entity & Local Relation Discovery",
        method="test_linker",
    )


def _make_chunk_env(
    chunk_id: str,
    text: str = "Non-empty philosophical passage.",
    run_id: str = "run-test",
) -> Any:
    """Create a ChunkArtifact envelope for testing."""
    chunk = L1Chunk(
        id=chunk_id,
        source_doc_id="doc_1",
        text=text,
        sequence_index=0,
        token_count=len(text.split()),
    )
    return build_chunk_artifact(
        chunk,
        run_id=run_id,
        phase_name="Phase 1: Document Ingestion & Foundation",
        method="test_chunker",
    )


class _RecordingObserver:
    """In-memory event observer for deterministic verification."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def on_event(self, event: Any) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass


class _StubPhaseRunner(PhaseRunner[Any]):
    """Configurable deterministic phase runner for orchestrator tests."""

    def __init__(
        self,
        *,
        name: str,
        phase_key: str,
        reads_kinds: frozenset[ArtifactKind] = frozenset(),
        writes_kinds: frozenset[ArtifactKind] = frozenset(),
        dependencies: frozenset[str] | None = None,
        artifacts_to_emit: list[Any] | None = None,
    ) -> None:
        self.name = name
        self.phase_key = phase_key
        self.reads_kinds = reads_kinds
        self.writes_kinds = writes_kinds
        self._dependencies = dependencies
        self.artifacts_to_emit = list(artifacts_to_emit or [])
        self.run_count = 0

    @property
    def dependencies(self) -> frozenset[str] | None:
        return self._dependencies

    async def run(
        self, input: Any, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        self.run_count += 1
        return ArtifactCollection(list(self.artifacts_to_emit))


# ---------------------------------------------------------------------------
# 1. Protocol & Fingerprinting Tests
# ---------------------------------------------------------------------------


def test_quality_gates_implement_protocols_and_fingerprintable() -> None:
    """Verify all built-in quality gates satisfy EpistemicQualityGate and Fingerprintable."""
    g1 = OntologyEntropyGate(min_entropy=0.4, max_dominant_type_ratio=0.85)
    g2 = PercolationQualityGate(max_cluster_fraction=0.45)
    g3 = ConformalCalibrationGate(max_empty_rate=0.25, max_ambiguous_rate=0.60)

    for gate in (g1, g2, g3):
        assert isinstance(gate, EpistemicQualityGate)
        assert isinstance(gate, Fingerprintable)
        assert ensure_quality_gate(gate) is gate
        fp = fingerprint_method(gate)
        assert fp is not None and len(fp) == 64

    # Verify fingerprint sensitivity to threshold changes
    assert fingerprint_method(g1) != fingerprint_method(
        OntologyEntropyGate(min_entropy=0.6, max_dominant_type_ratio=0.85)
    )
    assert fingerprint_method(g2) != fingerprint_method(
        PercolationQualityGate(max_cluster_fraction=0.25)
    )
    assert fingerprint_method(g3) != fingerprint_method(
        ConformalCalibrationGate(max_empty_rate=0.10, max_ambiguous_rate=0.60)
    )

    normalized = ensure_quality_gates([g1, g2, g3])
    assert len(normalized) == 3

    with pytest.raises(TypeError, match="EpistemicQualityGate"):
        ensure_quality_gate(object())


# ---------------------------------------------------------------------------
# 2. OntologyEntropyGate Tests (Post-Phase 2)
# ---------------------------------------------------------------------------


def test_ontology_entropy_gate_passes_on_diverse_types() -> None:
    """Verify OntologyEntropyGate passes when entity types have sufficient entropy."""
    bus = SimpleEventEmitter()
    obs = _RecordingObserver()
    bus.register_observer(obs)

    chunks = [_make_chunk_env("c1"), _make_chunk_env("c2")]
    entities = [
        _make_linked_entity_env("e1", "Concept"),
        _make_linked_entity_env("e2", "Concept"),
        _make_linked_entity_env("e3", "Thesis"),
        _make_linked_entity_env("e4", "Thesis"),
        _make_linked_entity_env("e5", "Philosopher"),
        _make_linked_entity_env("e6", "Work"),
    ]
    phase_col = ArtifactCollection(entities)
    cum_col = ArtifactCollection(chunks + entities)

    gate = OntologyEntropyGate(
        min_entropy=0.8,
        max_dominant_type_ratio=0.80,
        min_entities=5,
        on_violation="raise",
    )

    with use_event_emitter(bus):
        result = gate.evaluate("phase2", phase_col, cum_col)

    assert result.passed is True
    assert result.severity == "pass"
    assert result.metrics["shannon_entropy"] > 1.5
    assert result.metrics["dominant_type_ratio"] == pytest.approx(2.0 / 6.0)
    assert result.metrics["entity_density"] == pytest.approx(3.0)

    gate_events = [e for e in obs.events if isinstance(e, QualityGateEvaluated)]
    assert len(gate_events) == 1
    assert gate_events[0].passed is True


def test_ontology_entropy_gate_detects_type_collapse_warn_and_raise() -> None:
    """Verify OntologyEntropyGate detects >90% single-type ontological collapse."""
    chunks = [_make_chunk_env("c1")]
    # 10 entities: 10 assigned to single fallback type 'Concept' -> H = 0.0, ratio = 1.0
    entities = [_make_linked_entity_env(f"e{i}", "Concept") for i in range(10)]
    phase_col = ArtifactCollection(entities)
    cum_col = ArtifactCollection(chunks + entities)

    warn_gate = OntologyEntropyGate(
        min_entropy=0.30,
        max_dominant_type_ratio=0.90,
        min_entities=5,
        on_violation="warn",
    )
    with pytest.warns(QualityGateWarning, match="OntologyEntropyGate violation"):
        res = warn_gate.evaluate("phase2", phase_col, cum_col)
    assert res.passed is False
    assert res.severity == "warn"
    assert res.metrics["shannon_entropy"] == 0.0
    assert res.metrics["dominant_type_ratio"] == 1.0

    halt_gate = OntologyEntropyGate(
        min_entropy=0.30,
        max_dominant_type_ratio=0.90,
        min_entities=5,
        on_violation="raise",
    )
    with pytest.raises(QualityGateViolationError) as exc_info:
        halt_gate.evaluate("phase2", phase_col, cum_col)
    assert exc_info.value.result.gate_name == "ontology_entropy_gate"
    assert exc_info.value.result.severity == "halt"


def test_ontology_entropy_gate_detects_zero_density_on_non_empty_chunks() -> None:
    """Verify OntologyEntropyGate flags zero extracted entities across non-empty chunks."""
    chunks = [_make_chunk_env("c1", "Kant's Critique of Pure Reason.")]
    empty_phase_col = ArtifactCollection([])
    cum_col = ArtifactCollection(chunks)

    gate = OntologyEntropyGate(
        require_nonzero_density=True,
        on_violation="raise",
    )
    with pytest.raises(QualityGateViolationError, match="zero entity density"):
        gate.evaluate("phase2", empty_phase_col, cum_col)


def test_ontology_entropy_gate_falls_back_to_entity_mentions() -> None:
    """Verify OntologyEntropyGate inspects EntityMentionArtifact when LinkedEntityArtifact is absent."""
    mentions = [
        build_entity_mention_artifact(
            L2Entity(
                id=f"m{i}",
                label="Concept" if i < 3 else "Thesis",
                name=f"Mention_{i}",
                textual_envelope="text",
                source_chunk_ids=["c1"],
            ),
            "c1",
            run_id="run-test",
            phase_name="Phase 2",
            method="test_ner",
        )
        for i in range(6)
    ]
    phase_col = ArtifactCollection(mentions)
    gate = OntologyEntropyGate(min_entropy=0.5, on_violation="raise")
    res = gate.evaluate("phase2", phase_col, phase_col)
    assert res.passed is True
    assert res.metrics["entity_count"] == 6.0


# ---------------------------------------------------------------------------
# 3. PercolationQualityGate Tests (Post-Phase 3b & Phase 5)
# ---------------------------------------------------------------------------


def test_percolation_gate_phase3b_balanced_vs_giant_component() -> None:
    """Verify PercolationQualityGate passes balanced merges and catches giant-component collapse in Phase 3b."""
    entities = [_make_linked_entity_env(f"e{i}", "Concept") for i in range(10)]

    # Balanced merge: only e1 -> e0 (cluster size 2 / 10 = 0.20 <= 0.50)
    balanced_canon = build_canonicalization_artifact(
        "e1",
        "e0",
        method="agglomerative",
        run_id="run-test",
        phase_name="Phase 3b: Latent Graph Consolidation",
    )
    gate = PercolationQualityGate(
        max_cluster_fraction=0.50,
        min_population=4,
        on_violation="raise",
    )
    res_ok = gate.evaluate(
        "phase3b",
        ArtifactCollection([balanced_canon]),
        ArtifactCollection(entities + [balanced_canon]),
    )
    assert res_ok.passed is True
    assert res_ok.metrics["max_cluster_fraction"] == pytest.approx(0.20)

    # Giant component collapse: 6 entities merged into e0 (cluster size 7 / 10 = 0.70 > 0.50)
    giant_canons = [
        build_canonicalization_artifact(
            f"e{i}",
            "e0",
            method="agglomerative",
            run_id="run-test",
            phase_name="Phase 3b: Latent Graph Consolidation",
        )
        for i in range(1, 7)
    ]
    with pytest.raises(QualityGateViolationError, match="exceeds rho_max"):
        gate.evaluate(
            "phase3b",
            ArtifactCollection(giant_canons),
            ArtifactCollection(entities + giant_canons),
        )


def test_percolation_gate_phase5_fusion_collapse() -> None:
    """Verify PercolationQualityGate catches giant-component percolation in Phase 5."""
    atoms = [
        build_theory_atom_artifact(
            TheoryAtom(
                id=f"atom_{i}",
                component_type="claim",
                text=f"Claim {i}",
                source_chunk_id="c1",
            ),
            run_id="run-test",
            phase_name="Phase 4: Argument Mining",
            method="test_acc",
        )
        for i in range(8)
    ]
    # Merge 6 of 8 atoms into atom_0 (6 / 8 = 0.75 > 0.50)
    fusion_env = build_fusion_cluster_artifact(
        [f"atom_{i}" for i in range(6)],
        True,
        run_id="run-test",
        phase_name="Phase 5: Argument Web & Fusion",
        method="test_fusion",
    )
    gate = PercolationQualityGate(
        max_cluster_fraction=0.50,
        min_population=4,
        on_violation="raise",
    )
    with pytest.raises(QualityGateViolationError) as exc_info:
        gate.evaluate(
            "phase5",
            ArtifactCollection([fusion_env]),
            ArtifactCollection(atoms + [fusion_env]),
        )
    assert exc_info.value.result.metrics["max_cluster_fraction"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# 4. ConformalCalibrationGate Tests (Post-Phase 3 & Phase 4)
# ---------------------------------------------------------------------------


def test_conformal_calibration_gate_healthy_vs_ood_spikes() -> None:
    """Verify ConformalCalibrationGate detects empty and ambiguous prediction set spikes."""
    def _make_rel_with_ps(idx: int, prediction_set: list[str]) -> Any:
        triple = L2Triple(
            subject_id=f"s_{idx}",
            predicate="SUPPORTS",
            object_id=f"o_{idx}",
            confidence=0.8,
            scope="global",
        )
        env = build_global_relation_artifact(
            triple,
            {"SUPPORTS": 1},
            run_id="run-test",
            phase_name="Phase 3: Global Relation Extraction",
            method="test_rel",
        )
        env.metadata["prediction_set"] = prediction_set
        return env

    # 1. Healthy: 9 singleton sets, 1 ambiguous -> empty_rate=0.0, ambiguous_rate=0.10
    healthy_envs = [
        _make_rel_with_ps(i, ["SUPPORTS"] if i < 9 else ["SUPPORTS", "ATTACKS"])
        for i in range(10)
    ]
    gate = ConformalCalibrationGate(
        max_empty_rate=0.30,
        max_ambiguous_rate=0.50,
        max_ood_rate=0.50,
        on_violation="raise",
    )
    res_ok = gate.evaluate(
        "phase3",
        ArtifactCollection(healthy_envs),
        ArtifactCollection(healthy_envs),
    )
    assert res_ok.passed is True
    assert res_ok.metrics["singleton_rate"] == pytest.approx(0.90)

    # 2. Empty set spike: 5 empty sets out of 10 (empty_rate=0.50 > 0.30)
    empty_spike_envs = [
        _make_rel_with_ps(i, [] if i < 5 else ["SUPPORTS"])
        for i in range(10)
    ]
    with pytest.raises(QualityGateViolationError, match="empty prediction set rate"):
        gate.evaluate(
            "phase3",
            ArtifactCollection(empty_spike_envs),
            ArtifactCollection(empty_spike_envs),
        )

    # 3. Ambiguous set spike with warn mode: 8 multi-label sets out of 10 (0.80 > 0.70)
    ambiguous_envs = [
        _make_rel_with_ps(
            i,
            ["SUPPORTS", "ATTACKS", "NEUTRAL"] if i < 8 else ["SUPPORTS"],
        )
        for i in range(10)
    ]
    warn_gate = ConformalCalibrationGate(
        max_empty_rate=0.30,
        max_ambiguous_rate=0.70,
        max_ood_rate=0.70,
        on_violation="warn",
    )
    with pytest.warns(QualityGateWarning, match="ambiguous prediction set rate"):
        res_warn = warn_gate.evaluate(
            "phase4",
            ArtifactCollection(ambiguous_envs),
            ArtifactCollection(ambiguous_envs),
        )
    assert res_warn.passed is False
    assert res_warn.severity == "warn"


@pytest.mark.asyncio
async def test_conformal_calibration_gate_harvests_observable_decision_engine() -> None:
    """Verify ConformalCalibrationGate harvests recorded prediction sets from ObservableDecisionEngine."""
    inner = MockJevDecisionEngine(default_confidence_threshold=0.85)
    inner.register_choice_response("relation?", prediction_set=[])
    obs_engine = ObservableDecisionEngine(inner=inner, stochastic_audit_rate=0.0)
    calibrator = ConformalCalibrator(alpha=0.10, q_hat=0.05)
    obs_engine.calibrator = calibrator

    for i in range(5):
        await obs_engine.evaluate_choice(
            state=f"ctx {i}",
            question="Relation?",
            options=["A", "B"],
        )

    assert len(obs_engine.recorded_prediction_sets) == 5

    gate = ConformalCalibrationGate(
        max_empty_rate=0.30,
        decision_engine=obs_engine,
        on_violation="raise",
    )
    with pytest.raises(QualityGateViolationError, match="empty prediction set rate"):
        gate.evaluate("phase3", ArtifactCollection([]), ArtifactCollection([]))

    # Buffer is consumed after evaluation so subsequent phases start fresh
    assert len(obs_engine.recorded_prediction_sets) == 0


# ---------------------------------------------------------------------------
# 5. WorkflowDAG Topology & Cycle Detection Tests
# ---------------------------------------------------------------------------


def test_workflow_dag_topology_and_cycle_detection() -> None:
    """Verify WorkflowDAG resolves dataflow dependencies, topological order, and cycles."""
    p1 = _StubPhaseRunner(
        name="Phase 1",
        phase_key="phase1",
        writes_kinds=frozenset({ArtifactKind.CHUNK}),
    )
    p2_branch_a = _StubPhaseRunner(
        name="Phase 2A",
        phase_key="phase2a",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
    )
    p2_branch_b = _StubPhaseRunner(
        name="Phase 2B",
        phase_key="phase2b",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM}),
    )
    p_join = _StubPhaseRunner(
        name="Phase Join",
        phase_key="phase_join",
        reads_kinds=frozenset(
            {ArtifactKind.LINKED_ENTITY, ArtifactKind.THEORY_ATOM}
        ),
        writes_kinds=frozenset({ArtifactKind.FUSION_DECISION}),
    )

    gate = OntologyEntropyGate(target_phases=frozenset({"phase2a"}))
    dag = WorkflowDAG(
        phases=[p1, p2_branch_a, p2_branch_b, p_join],
        quality_gates=[gate],
        task="comparative_alignment",
    )

    assert isinstance(dag, Fingerprintable)
    deps = dag.dependencies()
    assert deps["phase1"] == set()
    assert deps["phase2a"] == {"phase1"}
    assert deps["phase2b"] == {"phase1"}
    assert deps["phase_join"] == {"phase2a", "phase2b"}

    topo = [node.phase_key for node in dag.topological_order()]
    assert topo[0] == "phase1"
    assert topo[-1] == "phase_join"
    assert set(topo[1:3]) == {"phase2a", "phase2b"}

    assert dag.gates_for_phase("phase2a") == (gate,)
    assert dag.gates_for_phase("phase2b") == ()

    # Cyclic dependency detection
    c1 = _StubPhaseRunner(
        name="Cycle 1",
        phase_key="c1",
        dependencies=frozenset({"c2"}),
    )
    c2 = _StubPhaseRunner(
        name="Cycle 2",
        phase_key="c2",
        dependencies=frozenset({"c1"}),
    )
    cyclic_dag = WorkflowDAG(phases=[c1, c2])
    with pytest.raises(ValueError, match="Cycle detected"):
        cyclic_dag.topological_order()


# ---------------------------------------------------------------------------
# 6. PipelineFactory, ArtifactExecutionEngine & Pipeline Integration Tests
# ---------------------------------------------------------------------------


def test_pipeline_delegates_to_factory_workflow_and_execution_engine(
    tmp_path: Path,
) -> None:
    """Verify Pipeline.for_task delegates to PipelineFactory, WorkflowDAG, and ArtifactExecutionEngine."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    llm = MagicMock()
    llm.model_name = "mock-llm"
    emb = MagicMock()
    emb.aget_text_embedding = MagicMock()
    reranker = MagicMock()
    reranker.arerank = MagicMock()

    pipeline = Pipeline.for_task(
        task="knowledge_graph",
        llm=llm,
        embedding_model=emb,
        relation_reranker=reranker,
        config=config,
    )

    assert isinstance(pipeline.workflow, WorkflowDAG)
    assert isinstance(pipeline.engine, ArtifactExecutionEngine)
    assert isinstance(pipeline, Fingerprintable)
    assert len(pipeline.quality_gates) == 3
    assert len(pipeline.workflow.gates_for_phase("phase2")) == 1
    assert len(pipeline.workflow.gates_for_phase("phase3b")) == 1
    assert len(pipeline.workflow.gates_for_phase("phase5")) == 1
    assert len(pipeline.workflow.gates_for_phase("phase3")) == 1
    assert len(pipeline.workflow.gates_for_phase("phase4")) == 1


@pytest.mark.asyncio
async def test_execution_engine_halts_on_quality_gate_violation_before_downstream_phases(
    tmp_path: Path,
) -> None:
    """Verify ArtifactExecutionEngine halts on QualityGateViolationError with symmetric failure events."""
    config = PipelineConfig(
        quality_gates=QualityGatesConfig(
            enabled=True,
            on_violation="raise",
            min_entity_type_entropy=0.50,
            max_dominant_type_ratio=0.80,
            min_entities_for_entropy=5,
        )
    )
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    chunk_env = _make_chunk_env("c1", "Philosophical text.")
    # All 6 entities have the exact same fallback type -> triggers OntologyEntropyGate halt
    collapsed_entities = [
        _make_linked_entity_env(f"e{i}", "Concept") for i in range(6)
    ]

    p1 = _StubPhaseRunner(
        name="Phase 1: Document Ingestion & Foundation",
        phase_key="phase1",
        writes_kinds=frozenset({ArtifactKind.CHUNK}),
        artifacts_to_emit=[chunk_env],
    )
    p2 = _StubPhaseRunner(
        name="Phase 2: Entity & Local Relation Discovery",
        phase_key="phase2",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
        artifacts_to_emit=collapsed_entities,
    )
    p3 = _StubPhaseRunner(
        name="Phase 3: Global Relation Extraction",
        phase_key="phase3",
        reads_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
        writes_kinds=frozenset({ArtifactKind.GLOBAL_RELATION}),
    )

    bus = SimpleEventEmitter()
    observer = _RecordingObserver()
    bus.register_observer(observer)

    pipeline = Pipeline(
        phases=[p1, p2, p3],
        config=config,
        event_emitter=bus,
        quality_gates=build_default_quality_gates(config),
    )

    doc_path = tmp_path / "sample.md"
    doc_path.write_text("# Sample\nText.", encoding="utf-8")

    with pytest.raises(QualityGateViolationError, match="OntologyEntropyGate violation"):
        await pipeline.run(
            PipelineInput(source_paths=[str(doc_path)]),
            run_id="run-halt-test",
        )

    # Phase 1 and Phase 2 ran, but Phase 3 was prevented from running
    assert p1.run_count == 1
    assert p2.run_count == 1
    assert p3.run_count == 0

    # Manifest must be persisted as FAILED with quality gate diagnostic note
    manifest = pipeline.manifest_store.read_manifest("run-halt-test")
    assert manifest is not None
    assert manifest.status == RunStatus.FAILED
    p2_rec = next(r for r in manifest.phase_records if r.phase_key == "phase2")
    assert p2_rec.status == RunStatus.FAILED
    assert "quality_gate.ontology_entropy_gate" in p2_rec.notes

    # Corrupted Phase 2 artifacts must NOT have been persisted to the artifact store
    persisted = await pipeline.artifact_store.list_run_artifacts("run-halt-test")
    persisted_phases = {a.phase_name for a in persisted}
    assert "Phase 2: Entity & Local Relation Discovery" not in persisted_phases

    # Symmetric lifecycle events must be emitted
    started_comps = [e for e in observer.events if isinstance(e, ComponentStarted)]
    completed_comps = [e for e in observer.events if isinstance(e, ComponentCompleted)]
    assert len(started_comps) == len(completed_comps) == 2
    assert any(isinstance(e, RunStarted) for e in observer.events)
    assert any(isinstance(e, PhaseFailed) for e in observer.events)
    assert any(isinstance(e, RunFailed) for e in observer.events)
    assert not any(isinstance(e, RunCompleted) for e in observer.events)
    gate_events = [e for e in observer.events if isinstance(e, QualityGateEvaluated)]
    assert len(gate_events) == 1
    assert gate_events[0].passed is False
    assert gate_events[0].severity == "halt"


@pytest.mark.asyncio
async def test_multi_branch_workflow_dag_execution_and_selective_reuse(
    tmp_path: Path,
) -> None:
    """Verify ArtifactExecutionEngine executes multi-branch WorkflowDAGs and selectively reuses unchanged branches."""
    config = PipelineConfig(quality_gates=QualityGatesConfig(enabled=False))
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    doc_path = tmp_path / "corpus.md"
    doc_path.write_text("# Corpus\nParagraph.", encoding="utf-8")
    p_input = PipelineInput(source_paths=[str(doc_path)])

    class _ConfigurableBranchRunner(_StubPhaseRunner):
        def __init__(self, *, version: str, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.version = version

        def config_fingerprint(self) -> str:
            return f"cfg-{self.phase_key}-{self.version}"

    p1 = _ConfigurableBranchRunner(
        version="v1",
        name="Phase 1",
        phase_key="phase1",
        writes_kinds=frozenset({ArtifactKind.CHUNK}),
        artifacts_to_emit=[_make_chunk_env("c1")],
    )
    p2a = _ConfigurableBranchRunner(
        version="v1",
        name="Phase 2A",
        phase_key="phase2a",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
        artifacts_to_emit=[_make_linked_entity_env("e1", "Concept")],
    )
    p2b = _ConfigurableBranchRunner(
        version="v1",
        name="Phase 2B",
        phase_key="phase2b",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM}),
    )
    p_join = _ConfigurableBranchRunner(
        version="v1",
        name="Phase Join",
        phase_key="phase_join",
        reads_kinds=frozenset(
            {ArtifactKind.LINKED_ENTITY, ArtifactKind.THEORY_ATOM}
        ),
        writes_kinds=frozenset({ArtifactKind.FUSION_DECISION}),
    )

    workflow1 = WorkflowDAG(
        phases=[p1, p2a, p2b, p_join],
        task="comparative_alignment",
    )
    engine1 = ArtifactExecutionEngine(workflow=workflow1, config=config)
    res1 = await engine1.run(p_input, run_id="run-1")
    assert res1.manifest.status == RunStatus.COMPLETED
    assert (p1.run_count, p2a.run_count, p2b.run_count, p_join.run_count) == (1, 1, 1, 1)

    # Now mutate ONLY branch 2B's config fingerprint; p1 and p2a must be reused,
    # while p2b and its downstream dependent p_join must be invalidated and re-run!
    p2b.version = "v2"
    res2 = await engine1.run(p_input, run_id="run-2")
    assert res2.manifest.status == RunStatus.COMPLETED
    assert res2.report.reused_phase_ordinals == [1, 2]
    assert res2.report.invalidated_phase_ordinals == [3, 4]
    assert (p1.run_count, p2a.run_count, p2b.run_count, p_join.run_count) == (1, 1, 2, 2)


@pytest.mark.asyncio
async def test_branch_isolation_and_gate_fingerprint_invalidation(
    tmp_path: Path,
) -> None:
    """Verify parallel DAG branches only receive their transitive upstream artifacts and gate threshold changes invalidate gated phases."""
    config = PipelineConfig(quality_gates=QualityGatesConfig(enabled=False))
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    doc_path = tmp_path / "corpus.md"
    doc_path.write_text("# Corpus\nParagraph.", encoding="utf-8")
    p_input = PipelineInput(source_paths=[str(doc_path)])

    class _ContextInspectingRunner(_StubPhaseRunner):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.seen_previous_ids: list[str] = []
            self.seen_lineage_fp: str = ""

        async def run(
            self, input: Any, context: ArtifactExecutionContext
        ) -> ArtifactCollection:
            self.run_count += 1
            self.seen_previous_ids = (
                [a.artifact_id for a in context.previous.artifacts]
                if context.previous is not None
                else []
            )
            self.seen_lineage_fp = context.lineage_fingerprint
            return ArtifactCollection(list(self.artifacts_to_emit))

    c1_env = _make_chunk_env("c1")
    e_branch_a = _make_linked_entity_env("e_a", "Concept")
    e_branch_a.phase_name = "Phase 2A"

    p1 = _ContextInspectingRunner(
        name="Phase 1: Document Ingestion & Foundation",
        phase_key="phase1",
        writes_kinds=frozenset({ArtifactKind.CHUNK}),
        artifacts_to_emit=[c1_env],
    )
    p2a = _ContextInspectingRunner(
        name="Phase 2A",
        phase_key="phase2a",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
        artifacts_to_emit=[e_branch_a],
    )
    p2b = _ContextInspectingRunner(
        name="Phase 2B",
        phase_key="phase2b",
        reads_kinds=frozenset({ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM}),
        artifacts_to_emit=[],
    )

    gate_v1 = OntologyEntropyGate(
        min_entropy=0.0,
        require_nonzero_density=False,
        target_phases=frozenset({"phase2b"}),
    )
    workflow_v1 = WorkflowDAG(
        phases=[p1, p2a, p2b],
        quality_gates=[gate_v1],
    )
    engine_v1 = ArtifactExecutionEngine(workflow=workflow_v1, config=config)
    await engine_v1.run(p_input, run_id="run-branch-1")

    # Branch 2B only depends on Phase 1 (CHUNK), NOT Phase 2A (LINKED_ENTITY)
    assert p2b.seen_previous_ids == [c1_env.artifact_id]
    assert e_branch_a.artifact_id not in p2b.seen_previous_ids

    # Modifying quality gate threshold on phase2b must invalidate phase2b while reusing phase1 and phase2a
    gate_v2 = OntologyEntropyGate(
        min_entropy=0.95,
        require_nonzero_density=False,
        target_phases=frozenset({"phase2b"}),
    )
    workflow_v2 = WorkflowDAG(
        phases=[p1, p2a, p2b],
        quality_gates=[gate_v2],
    )
    engine_v2 = ArtifactExecutionEngine(workflow=workflow_v2, config=config)
    res2 = await engine_v2.run(p_input, run_id="run-branch-2")
    assert res2.report.reused_phase_ordinals == [1, 2]
    assert res2.report.invalidated_phase_ordinals == [3]


@pytest.mark.asyncio
async def test_phase_scoped_prediction_sets_do_not_bleed_across_phases() -> None:
    """Verify ObservableDecisionEngine.start_phase isolates prediction sets per phase."""
    inner = MockJevDecisionEngine(default_confidence_threshold=0.85)
    inner.register_choice_response("entity link?", prediction_set=[])
    obs_engine = ObservableDecisionEngine(inner=inner, stochastic_audit_rate=0.0)

    obs_engine.start_phase("phase2")
    await obs_engine.evaluate_choice(
        state="ctx", question="Entity link?", options=["e1", "e2"]
    )
    assert len(obs_engine.recorded_prediction_sets) == 1

    # Starting phase3 clears the active phase buffer so phase2's empty set cannot bleed into phase3
    obs_engine.start_phase("phase3")
    gate = ConformalCalibrationGate(
        max_empty_rate=0.10,
        decision_engine=obs_engine,
        on_violation="raise",
    )
    res = gate.evaluate("phase3", ArtifactCollection([]), ArtifactCollection([]))
    assert res.passed is True
    assert res.metrics["sample_count"] == 0.0


