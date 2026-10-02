"""Unit and integration tests for ConformalCalibrator and Phase 5 Theory Fusion Gating (ISSUE-046)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from episteme_pipeline.artifacts.execution import ArtifactExecutionContext, Phase4ArtifactsView
from episteme_pipeline.config import FusionGatingConfig, Phase5Config
from episteme_pipeline.contracts.domain import TheoryAtom
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.events import SimpleEventEmitter, set_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.phases.phase5_fusion.argument_clustering import verify_inter_document_cluster
from episteme_pipeline.phases.phase5_fusion.argument_web import Phase5ArgumentWebRunner
from episteme_pipeline.protocols.decision import DecisionScore


def test_conformal_calibrator_calibration_quantile():
    """ConformalCalibrator computes empirical quantile at level ceil((n+1)(1-alpha))/n."""
    calibrator = ConformalCalibrator(alpha=0.10)
    # Suppose we have 9 calibration scores: s_i in [0.05, 0.10, ..., 0.45]
    scores = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
    # n = 9, alpha = 0.10 -> ceil((9 + 1) * 0.90) = ceil(9.0) = 9
    # Target score index 9 -> 0.45
    q_hat = calibrator.calibrate(scores, alpha=0.10)
    assert q_hat == 0.45
    assert calibrator.q_hat == 0.45


def test_conformal_calibrator_predict_set_and_triage():
    """ConformalCalibrator emits prediction sets and routes triage appropriately."""
    calibrator = ConformalCalibrator(alpha=0.05, q_hat=0.70)
    # Threshold = 1 - q_hat = 0.30

    # Unambiguous distribution -> singleton set
    score_unambiguous = DecisionScore(
        selected_option="EQUIVALENT_FUSION",
        class_probability=0.85,
        empirical_accuracy=0.90,
        probabilities={"EQUIVALENT_FUSION": 0.85, "COMPETING_THEORIES": 0.10, "DISTINCT_APPLICATIONS": 0.05},
    )

    pred_set_1 = calibrator.predict_set(score_unambiguous)
    assert pred_set_1 == ["EQUIVALENT_FUSION"]
    assert calibrator.triage(pred_set_1) == "fast_exit"

    # Ambiguous distribution -> multi-label set
    score_ambiguous = DecisionScore(
        selected_option="EQUIVALENT_FUSION",
        class_probability=0.45,
        empirical_accuracy=0.60,
        probabilities={"EQUIVALENT_FUSION": 0.45, "COMPETING_THEORIES": 0.40, "DISTINCT_APPLICATIONS": 0.15},
    )

    pred_set_2 = calibrator.predict_set(score_ambiguous)
    # Both 0.45 and 0.40 >= 0.30
    assert "EQUIVALENT_FUSION" in pred_set_2
    assert "COMPETING_THEORIES" in pred_set_2
    assert calibrator.triage(pred_set_2) == "escalate_to_system2"


def test_conformal_calibrator_enforces_decision_score_contract():
    """ConformalCalibrator operates strictly on DecisionScore contracts."""
    calibrator = ConformalCalibrator(alpha=0.05)

    # Empty probabilities falls back to selected_option
    score_empty_probs = DecisionScore(
        selected_option="FALLBACK_OPTION",
        class_probability=0.9,
        empirical_accuracy=0.9,
        probabilities={},
    )
    assert calibrator.predict_set(score_empty_probs) == ["FALLBACK_OPTION"]

    # Pre-computed prediction set is reused when q_hat is None
    score_precomputed = DecisionScore(
        selected_option="A",
        class_probability=0.9,
        empirical_accuracy=0.9,
        probabilities={"A": 0.9, "B": 0.1},
        prediction_set=["A"],
    )
    assert calibrator.predict_set(score_precomputed) == ["A"]

    # Passing non-DecisionScore raises AttributeError
    with pytest.raises(AttributeError):
        calibrator.predict_set({"A": 0.8, "B": 0.2})  # type: ignore[arg-type]


class EventCollector:
    def __init__(self):
        self.events = []

    def on_event(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_verify_inter_document_cluster_confirms_equivalent_fusion():
    """Cluster verification confirms equivalent fusion with fast-exit."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="semantically equivalent for knowledge graph fusion",
        selected_option="EQUIVALENT_FUSION",
        probabilities={"EQUIVALENT_FUSION": 0.92, "COMPETING_THEORIES": 0.05, "DISTINCT_APPLICATIONS": 0.03},
        empirical_accuracy=0.91,
        prediction_set=["EQUIVALENT_FUSION"],
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    nodes = [
        TheoryAtom(id="a1", text="All knowledge begins with experience.", component_type="CLAIM", source_chunk_id="c1"),
        TheoryAtom(id="a2", text="Cognition originates from empirical input.", component_type="CLAIM", source_chunk_id="c2"),
    ]

    is_confirmed, emp_acc, pred_set = await verify_inter_document_cluster(
        cluster_nodes=nodes,
        decision_engine=engine,
        alpha=0.05,
        threshold=0.85,
    )

    assert is_confirmed is True
    assert pred_set == ["EQUIVALENT_FUSION"]
    assert emp_acc == 0.91

    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].gate_name == "fusion_gate"
    assert gating_events[0].action_taken == "fast_exit"


@pytest.mark.asyncio
async def test_verify_inter_document_cluster_rejects_competing_theories():
    """Cluster verification rejects merge for rival philosophical frameworks."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="semantically equivalent for knowledge graph fusion",
        selected_option="COMPETING_THEORIES",
        probabilities={"EQUIVALENT_FUSION": 0.05, "COMPETING_THEORIES": 0.90, "DISTINCT_APPLICATIONS": 0.05},
        empirical_accuracy=0.88,
        prediction_set=["COMPETING_THEORIES"],
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    nodes = [
        TheoryAtom(id="a1", text="Rationalism: ideas are innate.", component_type="CLAIM", source_chunk_id="c1"),
        TheoryAtom(id="a2", text="Empiricism: mind is a blank slate.", component_type="CLAIM", source_chunk_id="c2"),
    ]

    is_confirmed, _, pred_set = await verify_inter_document_cluster(
        cluster_nodes=nodes,
        decision_engine=engine,
    )

    assert is_confirmed is False
    assert "COMPETING_THEORIES" in pred_set
    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "rejected"


@pytest.mark.asyncio
async def test_verify_inter_document_cluster_routes_to_active_learning_on_multi_class():
    """High-entropy multi-label prediction set routes to active learning."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="semantically equivalent for knowledge graph fusion",
        selected_option="EQUIVALENT_FUSION",
        probabilities={"EQUIVALENT_FUSION": 0.52, "COMPETING_THEORIES": 0.44, "DISTINCT_APPLICATIONS": 0.04},
        empirical_accuracy=0.62,
        prediction_set=["EQUIVALENT_FUSION", "COMPETING_THEORIES"],
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    nodes = [
        TheoryAtom(id="a1", text="Pragmatic truth assertion", component_type="CLAIM", source_chunk_id="c1"),
        TheoryAtom(id="a2", text="Coherence truth assertion", component_type="CLAIM", source_chunk_id="c2"),
    ]

    is_confirmed, _, pred_set = await verify_inter_document_cluster(
        cluster_nodes=nodes,
        decision_engine=engine,
        threshold=0.85,
    )

    assert is_confirmed is False
    assert len(pred_set) == 2
    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "active_learning"


@pytest.mark.asyncio
async def test_phase5_runner_gates_spurious_clusters():
    """Phase5ArgumentWebRunner filters out unverified clusters when fusion gating is enabled."""
    engine = MockJevDecisionEngine()
    # Reject cluster by declaring COMPETING_THEORIES
    engine.register_choice_response(
        question_pattern="semantically equivalent for knowledge graph fusion",
        selected_option="COMPETING_THEORIES",
        probabilities={"EQUIVALENT_FUSION": 0.05, "COMPETING_THEORIES": 0.95},
        prediction_set=["COMPETING_THEORIES"],
        empirical_accuracy=0.90,
    )

    config = Phase5Config(
        argument_clustering_enabled=True,
        theory_fusion_enabled=False,
        gating=FusionGatingConfig(
            enabled=True,
            confidence_threshold=0.85,
            audit_rate=0.0,
        ),
    )

    clustering_mock = AsyncMock()
    clustering_mock.cluster.return_value = [["a1", "a2"]]

    graph_store = AsyncMock()
    a1 = TheoryAtom(id="a1", text="Theory X", component_type="CLAIM", source_chunk_id="c1")
    a2 = TheoryAtom(id="a2", text="Theory Y", component_type="CLAIM", source_chunk_id="c2")
    graph_store.get_theory_atoms.return_value = [a1, a2]

    runner = Phase5ArgumentWebRunner(
        config=config,
        embedding_model=MagicMock(),
        graph_store=graph_store,
        argument_clustering=clustering_mock,
        decision_engine=engine,
    )

    context = ArtifactExecutionContext(
        run_id="run_test",
        manifest=MagicMock(),
        pipeline_input=PipelineInput(source_paths=[]),
    )

    artifacts = await runner.run(Phase4ArtifactsView(theory_atoms=[], theory_relations=[]), context)
    # The cluster ["a1", "a2"] was rejected by the gate, so 0 fusion artifacts emitted!
    assert len(artifacts.artifacts) == 0
