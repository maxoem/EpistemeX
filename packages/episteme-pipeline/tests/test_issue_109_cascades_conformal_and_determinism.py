"""Unit and integration tests for ISSUE-109:
System 1/2 Cascade Regression, Compositional Conformal Risk Budgeting & Audit Determinism.

Verifies all five acceptance criteria:
1. CascadingACCClassifier no longer runs JevACCClassifier only to discard and re-escalate 100%
   of multi-ADU and entity-bearing chunks; JevACCClassifier/CascadingACCClassifier expose
   fingerprint(), infer_intensional_mode escalation policy is consistent, and
   InterDocumentClusterVerifier.verify() does not confirm ambiguous len(pred_set) > 1 clusters.
2. config.phase4.conformal_alpha and refinement.conformal_alpha are synced from
   DecisionEngineConfig and passed to evaluate_choice(..., alpha=...) / predict_set(...),
   ConformalCalibrator honors get_allocated_alpha(task_id), and risk_budget_weights
   allocate budget strictly across active conformal stages.
3. LatentGraphConsolidation.fuse() separates CSLS candidate ranking from raw cosine
   min_internal_similarity / max_diameter checks, stamps sim_matrix[i, j] = -1.0 on
   rejected borderline pairs, and is verified by discriminating Phase 3b/5 tests that
   fail under Union-Find.
4. JevGleaningGate.should_continue() and DenseRetrievalGlobalRelationExtractor.filter_candidate_pairs()
   use deterministic HMAC-SHA256 auditing (should_audit_deterministically) with zero
   unseeded random.random() calls.
5. ConformalCalibrator.calibrate() preserves global self.alpha on stratum-scoped calibration,
   ObservableDecisionEngine propagates task_id/language, ObservableDecisionEngine._compute_state_hash
   uses canonical JSON, DiskCachedStructuredLLM.predict_text hashes prompt_bundle_hash,
   fingerprint_method() reads .seed, and docs/architecture/conformal_prediction.md links are current.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from episteme_pipeline.config import (
    DecisionEngineConfig,
    Phase3Config,
    Phase4Config,
    PipelineConfig,
    StructuredDecodingStrategy,
)
from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.gleaning import JevGleaningGate
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.events import SimpleEventEmitter, use_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    CandidatePair,
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.phases.phase3b_consolidation.clustering import (
    BorderlinePairVerifier,
)
from episteme_pipeline.phases.phase3b_consolidation.consolidation import (
    LatentGraphConsolidation,
)
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
    CascadingACCClassifier,
    JevACCClassifier,
)
from episteme_pipeline.phases.phase5_fusion.argument_clustering import (
    InterDocumentClusterVerifier,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.argument_mining import ACCClassifier
from episteme_pipeline.protocols.decision import DecisionNoulResult, DecisionScore
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.runtime.pipeline_factory import PipelineFactory
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA
from pydantic import BaseModel

# ===========================================================================
# AC 1: CascadingACCClassifier, JevACCClassifier & InterDocumentClusterVerifier
# ===========================================================================


@pytest.mark.asyncio
async def test_cascading_acc_fast_exits_multi_adu_and_entity_bearing_chunks() -> None:
    """Verify CascadingACCClassifier fast-exits confident multi-ADU and entity-bearing chunks."""
    mock_engine = MagicMock()
    mock_engine.evaluate_choice = AsyncMock(
        return_value=DecisionScore(
            selected_option="TheoreticalHypothesis",
            class_probability=0.93,
            empirical_accuracy=0.91,
            prediction_set=["TheoreticalHypothesis"],
        )
    )
    fast_acc = JevACCClassifier(
        decision_engine=mock_engine,
        infer_intensional_mode=True,
        conformal_alpha=0.0125,
    )
    llm_acc = MagicMock(spec=ACCClassifier)
    llm_acc.classify = AsyncMock()

    config = Phase4Config(
        triage_confidence_threshold=0.85,
        stochastic_audit_rate=0.0,
        conformal_alpha=0.0125,
    )
    cascade = CascadingACCClassifier(fast_acc, llm_acc, config=config)

    ent_kant = L2Entity(id="ent_kant", name="Kant", label="Person")
    ent_space = L2Entity(id="ent_space", name="Space", label="Concept")
    tagged = (
        "<AC1>Kant argues that Space is an a priori intuition.</AC1> "
        "<AC2>Space is not an empirical concept derived from outer experiences.</AC2>"
    )

    atoms, relations = await cascade.classify(
        chunk_id="chunk_multi_1",
        tagged_text=tagged,
        adu_ids=["AC1", "AC2"],
        schema=DEFAULT_SCHEMA,
        chunk_entities=[ent_kant, ent_space],
    )

    # Must fast-exit without invoking llm_acc
    assert not llm_acc.classify.called
    assert len(atoms) == 2
    assert atoms[0].entity_ids == ["ent_kant", "ent_space"]
    assert atoms[1].entity_ids == ["ent_space"]
    assert relations == []


@pytest.mark.asyncio
async def test_cascading_acc_short_circuits_before_jev_when_policy_requires_llm() -> (
    None
):
    """Verify CascadingACCClassifier skips JevACCClassifier entirely when escalation flags are set."""
    fast_acc = MagicMock(spec=ACCClassifier)
    fast_acc.classify = AsyncMock()

    llm_atom = TheoryAtom(
        id="ac_llm_1",
        text="Claim 1",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
    )
    llm_acc = MagicMock(spec=ACCClassifier)
    llm_acc.classify = AsyncMock(return_value=([llm_atom], []))

    cascade_multi = CascadingACCClassifier(
        fast_acc,
        llm_acc,
        stochastic_audit_rate=0.0,
        require_multi_adu_relations=True,
    )
    out_atoms, _ = await cascade_multi.classify(
        chunk_id="c1",
        tagged_text="<AC1>A</AC1> <AC2>B</AC2>",
        adu_ids=["AC1", "AC2"],
        schema=DEFAULT_SCHEMA,
    )
    assert out_atoms == [llm_atom]
    assert not fast_acc.classify.called
    assert llm_acc.classify.call_count == 1

    cascade_entity = CascadingACCClassifier(
        fast_acc,
        llm_acc,
        stochastic_audit_rate=0.0,
        require_entity_binding=True,
    )
    await cascade_entity.classify(
        chunk_id="c1",
        tagged_text="<AC1>A</AC1>",
        adu_ids=["AC1"],
        schema=DEFAULT_SCHEMA,
        chunk_entities=[L2Entity(id="e1", name="Kant", label="Person")],
    )
    assert not fast_acc.classify.called
    assert llm_acc.classify.call_count == 2


@pytest.mark.asyncio
async def test_cascading_acc_preserves_confident_suppositional_mode_and_escalates_attributed() -> (
    None
):
    """Verify CascadingACCClassifier accepts confident suppositional mode from System 1 and escalates attributed."""
    mock_engine = MagicMock()
    mock_engine.evaluate_choice = AsyncMock(
        side_effect=[
            DecisionScore(
                selected_option="Premise",
                class_probability=0.94,
                empirical_accuracy=0.92,
                prediction_set=["Premise"],
            ),
            DecisionScore(
                selected_option="suppositional",
                class_probability=0.91,
                empirical_accuracy=0.90,
                prediction_set=["suppositional"],
            ),
        ]
    )
    fast_acc = JevACCClassifier(mock_engine, infer_intensional_mode=True)
    llm_acc = MagicMock(spec=ACCClassifier)
    llm_acc.classify = AsyncMock()

    cascade = CascadingACCClassifier(
        fast_acc,
        llm_acc,
        triage_confidence_threshold=0.85,
        stochastic_audit_rate=0.0,
    )
    atoms, _ = await cascade.classify(
        chunk_id="c_supp",
        tagged_text="<AC1>Suppose space were purely empirical.</AC1>",
        adu_ids=["AC1"],
        schema=DEFAULT_SCHEMA,
    )
    assert not llm_acc.classify.called
    assert len(atoms) == 1
    assert atoms[0].intensional_mode == "suppositional"
    assert atoms[0].confidence == pytest.approx(0.91)


def test_jev_acc_and_cascading_acc_expose_deterministic_fingerprints() -> None:
    """Verify JevACCClassifier and CascadingACCClassifier implement non-None fingerprint()."""
    engine = MockJevDecisionEngine()
    fast_acc = JevACCClassifier(
        decision_engine=engine,
        infer_intensional_mode=True,
        conformal_alpha=0.02,
    )
    llm_acc = MagicMock(spec=ACCClassifier)
    llm_acc.fingerprint = MagicMock(return_value={"class": "LLMACCClassifier"})

    cascade = CascadingACCClassifier(
        fast_classifier=fast_acc,
        llm_classifier=llm_acc,
        triage_confidence_threshold=0.88,
        stochastic_audit_rate=0.03,
        require_multi_adu_relations=True,
    )

    assert isinstance(fast_acc, Fingerprintable)
    assert isinstance(cascade, Fingerprintable)

    fast_fp = fast_acc.fingerprint()
    assert fast_fp is not None
    assert fast_fp["class"] == "JevACCClassifier"
    assert fast_fp["infer_intensional_mode"] is True
    assert fast_fp["conformal_alpha"] == 0.02

    cascade_fp = cascade.fingerprint()
    assert cascade_fp is not None
    assert cascade_fp["class"] == "CascadingACCClassifier"
    assert cascade_fp["triage_confidence_threshold"] == 0.88
    assert cascade_fp["stochastic_audit_rate"] == 0.03
    assert cascade_fp["require_multi_adu_relations"] is True
    assert cascade_fp["fast_classifier"] == fast_fp


@pytest.mark.asyncio
async def test_inter_document_cluster_verifier_never_confirms_ambiguous_prediction_set() -> (
    None
):
    """Verify InterDocumentClusterVerifier does not confirm len(pred_set) > 1 even when emp_acc >= threshold."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="semantically equivalent for knowledge graph fusion",
        selected_option="EQUIVALENT_FUSION",
        probabilities={
            "EQUIVALENT_FUSION": 0.55,
            "COMPETING_THEORIES": 0.42,
            "DISTINCT_APPLICATIONS": 0.03,
        },
        empirical_accuracy=0.92,  # Above confidence_threshold=0.85!
        prediction_set=["EQUIVALENT_FUSION", "COMPETING_THEORIES"],
    )

    emitter = SimpleEventEmitter()
    events: list[Any] = []

    class _Obs:
        def on_event(self, ev: Any) -> None:
            events.append(ev)

    emitter.register_observer(_Obs())

    verifier = InterDocumentClusterVerifier(
        decision_engine=engine,
        confidence_threshold=0.85,
        conformal_alpha=0.05,
        audit_rate=0.0,
    )
    nodes = [
        TheoryAtom(
            id="a1", text="Claim 1", component_type="CLAIM", source_chunk_id="c1"
        ),
        TheoryAtom(
            id="a2", text="Claim 2", component_type="CLAIM", source_chunk_id="c2"
        ),
    ]

    with use_event_emitter(emitter):
        is_confirmed, emp_acc, pred_set = await verifier.verify(nodes)

    assert len(pred_set) == 2
    assert emp_acc == 0.92
    assert is_confirmed is False
    gating_events = [e for e in events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "active_learning"


# ===========================================================================
# AC 2: End-to-End Compositional Conformal Risk Budgeting
# ===========================================================================


@pytest.mark.asyncio
async def test_end_to_end_compositional_conformal_risk_budget_wiring() -> None:
    """Verify Phase 4, Refinement, ConformalCalibrator, and risk_budget_weights wire allocated alphas."""
    config = PipelineConfig(
        decision_engine=DecisionEngineConfig(
            global_alpha=0.05,
        )
    )
    # Default risk_budget_weights strictly cover active conformal stages
    weights = config.decision_engine.risk_budget_weights
    assert set(weights.keys()) == {
        "phase2_entity_discovery",
        "phase3b_consolidation",
        "phase4_argument_mining",
        "phase5_fusion",
        "refinement",
    }
    assert "phase3_global_relations" not in weights
    assert "phase4_entity_maturation" not in weights

    config.sync_allocated_risk_budgets()
    total_allocated = (
        config.phase2.conformal_linking_alpha
        + config.phase3b.verification.conformal_alpha
        + config.phase4.conformal_alpha
        + config.phase5.gating.conformal_alpha
        + config.refinement.conformal_alpha
    )
    assert np.isclose(total_allocated, 0.05)
    assert np.isclose(config.phase4.conformal_alpha, 0.0125)
    assert np.isclose(config.refinement.conformal_alpha, 0.0075)

    # Verify Phase4Runner passes config.phase4.conformal_alpha into JevACCClassifier and JevARCClassifier
    captured_alphas: list[tuple[str, float | None]] = []
    mock_engine = MagicMock()

    async def _capture_choice(
        state: Any, question: str, options: Any, alpha: float | None = None
    ) -> DecisionScore:
        captured_alphas.append((question, alpha))
        first_opt = next(iter(options))
        return DecisionScore(
            selected_option=first_opt,
            class_probability=0.95,
            empirical_accuracy=0.95,
            prediction_set=[first_opt],
        )

    mock_engine.evaluate_choice = AsyncMock(side_effect=_capture_choice)

    runner = Phase4Runner(
        config=config.phase4,
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
        decision_engine=mock_engine,
    )
    assert isinstance(runner.acc_classifier, CascadingACCClassifier)
    assert isinstance(runner.acc_classifier.fast_classifier, JevACCClassifier)
    assert runner.acc_classifier.fast_classifier.conformal_alpha == pytest.approx(
        0.0125
    )
    assert runner.acc_classifier.fast_classifier.infer_intensional_mode is True

    # Run ACC and ARC and confirm evaluate_choice receives alpha=0.0125
    runner.acc_classifier.fast_classifier.modal_resolver = None
    await runner.acc_classifier.fast_classifier.classify(
        "c1", "<AC1>Synthetic a priori proposition.</AC1>", ["AC1"], DEFAULT_SCHEMA
    )
    arc_clf = PipelineFactory._build_arc_classifier(
        config=config,
        llm=MagicMock(),
        embedding_model=None,
        decision_engine=mock_engine,
    )
    a1 = TheoryAtom(id="a1", text="P1", component_type="Premise", source_chunk_id="c1")
    a2 = TheoryAtom(id="a2", text="C1", component_type="Claim", source_chunk_id="c2")
    await arc_clf.fast_classifier.classify_pair(a1, a2, DEFAULT_SCHEMA)

    assert len(captured_alphas) == 3  # ACC type + ACC intensional mode + ARC pair
    assert all(a == pytest.approx(0.0125) for _, a in captured_alphas)


def test_conformal_calibrator_predict_set_and_calibrate_use_allocated_alpha() -> None:
    """Verify ConformalCalibrator resolves get_allocated_alpha(task_id) when alpha is None."""
    calibrator = ConformalCalibrator(
        alpha=0.05,
        global_alpha=0.04,
        risk_budget_weights={
            "phase3b_consolidation": 0.25,  # allocated alpha = 0.01 (target mass = 0.99)
            "phase4_argument_mining": 0.75,  # allocated alpha = 0.03 (target mass = 0.97)
        },
    )
    score = DecisionScore(
        selected_option="OPT_A",
        class_probability=0.975,
        empirical_accuracy=0.95,
        probabilities={"OPT_A": 0.975, "OPT_B": 0.025},
    )
    # Under phase4 (alpha=0.03, target_mass=0.97), 0.975 >= 0.97 -> singleton ["OPT_A"]
    set_p4 = calibrator.predict_set(score, task_id="p4_acc")
    assert set_p4 == ["OPT_A"]

    # Under phase3b (alpha=0.01, target_mass=0.99), 0.975 < 0.99 -> ["OPT_A", "OPT_B"]
    set_p3b = calibrator.predict_set(score, task_id="p3b_merge")
    assert set_p3b == ["OPT_A", "OPT_B"]


# ===========================================================================
# AC 3: Phase 3b CSLS vs Cosine Scale Separation & Rejected Pair Blocking
# ===========================================================================


@pytest.mark.asyncio
async def test_phase3b_rejected_borderline_pair_blocks_transitive_merge() -> None:
    """Verify pairs rejected by BorderlinePairVerifier get sim=-1.0 and cannot merge transitively."""
    e0 = L2Entity(id="e0", name="Concept A", label="Concept", source_chunk_ids=["c1"])
    e1 = L2Entity(
        id="e1", name="Concept B (Bridge)", label="Concept", source_chunk_ids=["c2"]
    )
    e2 = L2Entity(id="e2", name="Concept C", label="Concept", source_chunk_ids=["c3"])

    store = AsyncMock()
    store.get_entities.return_value = [e0, e1, e2]
    neighborhood = MagicMock()
    neighborhood.nodes = [MagicMock(id="n1")]
    t_shared = MagicMock(subject_id="e0", predicate="REL", object_id="x")
    neighborhood.triples = [t_shared]
    store.get_neighborhood.return_value = neighborhood

    # Make (0, 1) and (1, 2) definite merges (>= 0.88), while (0, 2) is in borderline band [0.75, 0.88)
    # v1 = [1, 0, 0]
    # v0 = [0.90, 0.43589, 0] -> cos(0, 1) = 0.90 >= 0.88
    # v2 = [0.90, -0.43589, 0] -> cos(1, 2) = 0.90 >= 0.88, cos(0, 2) = 0.81 - 0.19 = 0.62
    # Wait: we want cos(0, 2) in [0.75, 0.88), e.g. cos(0, 1) = 0.94, cos(1, 2) = 0.94 -> cos(0, 2) = 0.94^2 - 0.34117^2 = 0.7672!
    v0 = [0.94, 0.34117444, 0.0]
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.94, -0.34117444, 0.0]
    # Check: cos(0, 1) = 0.94 >= 0.88 (definite)
    # cos(1, 2) = 0.94 >= 0.88 (definite)
    # cos(0, 2) = 0.8836 - 0.1164 = 0.7672 in [0.75, 0.88) AND >= min_internal_similarity (0.70)!
    embedding_model = AsyncMock()
    embedding_model.aget_text_embedding_batch.return_value = [v0, v1, v2]

    verifier = MagicMock(spec=BorderlinePairVerifier)
    verifier.confidence_threshold = 0.80
    # Verifier explicitly rejects (e0, e2) as DISTINCT_SEPARATE!
    verifier.verify = AsyncMock(
        return_value=("DISTINCT_SEPARATE", 0.92, ["DISTINCT_SEPARATE"])
    )

    consolidation = LatentGraphConsolidation(
        embedding_model=embedding_model,
        dense_similarity_threshold=0.85,
        relation_overlap_threshold=0.0,
        borderline_similarity_lower=0.75,
        borderline_similarity_upper=0.88,
        min_internal_similarity=0.70,
        verifier=verifier,
        use_csls=False,
    )

    fused_map = await consolidation.fuse(store)

    # Verifier was consulted on the borderline pair (e0, e2)
    assert verifier.verify.call_count == 1
    # Because verifier rejected (e0, e2), e0 and e2 MUST NOT merge transitively through e1!
    canon_e0 = fused_map.get("e0", "e0")
    canon_e2 = fused_map.get("e2", "e2")
    assert canon_e0 != canon_e2


@pytest.mark.asyncio
async def test_phase3b_csls_uses_raw_cosine_for_internal_similarity_and_diameter() -> (
    None
):
    """Verify LatentGraphConsolidation with use_csls=True evaluates diameter/internal floor on raw cosine."""
    # 3 entities where e0 and e1 are nearly identical (cos = 0.99), and e2 is a nearby hub (cos = 0.92).
    # Under CSLS with k=2, high mean neighborhood similarity r_T(u) >= 0.95 subtracts ~0.95 from 2*cos,
    # pushing CSLS(0, 1) below 1.0, or if a cluster has raw cosine 0.80 >= min_internal_similarity=0.75
    # while CSLS < 0.75 due to hub penalty, raw cosine must govern min_internal_similarity / max_diameter.
    e0 = L2Entity(id="e0", name="A1", label="Concept", source_chunk_ids=["c1"])
    e1 = L2Entity(id="e1", name="A2", label="Concept", source_chunk_ids=["c2"])
    e2 = L2Entity(id="e2", name="A3", label="Concept", source_chunk_ids=["c3"])

    store = AsyncMock()
    store.get_entities.return_value = [e0, e1, e2]
    neighborhood = MagicMock()
    neighborhood.nodes = [MagicMock(id="n1")]
    neighborhood.triples = [
        MagicMock(subject_id="e0", predicate="REL", object_id="x"),
        MagicMock(subject_id="e1", predicate="REL", object_id="x"),
        MagicMock(subject_id="e2", predicate="REL", object_id="x"),
    ]
    store.get_neighborhood.return_value = neighborhood

    # Add 4th orthogonal anchor so CSLS local neighborhood mean r_T(u) is low while
    # raw cosine between e0 and e1 is 0.98 (diameter 0.02 <= 0.05) and cos(e0, e2) = 0.86 (< min_internal_similarity 0.90)
    e3 = L2Entity(id="e3", name="Anchor", label="OtherLabel", source_chunk_ids=["c4"])
    store.get_entities.return_value = [e0, e1, e2, e3]

    v0 = [1.0, 0.0, 0.0]
    v1 = [0.98, 0.198997, 0.0]  # cos(0, 1) = 0.98
    v2 = [0.86, 0.510294, 0.0]  # cos(0, 2) = 0.86, cos(1, 2) = 0.9443
    v3 = [0.0, 0.0, 1.0]  # orthogonal anchor
    embedding_model = AsyncMock()
    embedding_model.aget_text_embedding_batch.return_value = [v0, v1, v2, v3]

    consolidation = LatentGraphConsolidation(
        embedding_model=embedding_model,
        dense_similarity_threshold=0.65,
        relation_overlap_threshold=0.0,
        use_csls=True,
        csls_k_nearest=3,
        min_internal_similarity=0.95,
        max_diameter=0.05,
    )
    fused_map = await consolidation.fuse(store)
    # (0, 1) has raw cosine 0.98 >= 0.95 and diameter 0.02 <= 0.05, while e2 (cos(0, 2)=0.86 < 0.95) is excluded
    canon_0 = fused_map.get("e0", "e0")
    canon_1 = fused_map.get("e1", "e1")
    canon_2 = fused_map.get("e2", "e2")
    assert canon_0 == canon_1
    assert canon_2 == "e2"


# ===========================================================================
# AC 4: Deterministic HMAC-SHA256 Auditing in Gleaning & Phase 3 Pair Gating
# ===========================================================================


@pytest.mark.asyncio
async def test_gleaning_gate_and_phase3_pair_gating_are_deterministic_under_concurrency() -> (
    None
):
    """Verify JevGleaningGate.should_continue and filter_candidate_pairs are 100% deterministic."""
    engine = MockJevDecisionEngine()
    engine.register_noul_response(
        question_pattern="salient theoretical assertions",
        probability=0.10,
        empirical_accuracy=0.90,
    )
    gate = JevGleaningGate(
        decision_engine=engine,
        default_threshold=0.65,
        default_audit_rate=0.50,
        seed=42,
    )

    chunks = [
        f"Philosophical passage {i} on transcendental idealism." for i in range(30)
    ]
    run1 = [(await gate.should_continue(text, [], pass_count=0))[0] for text in chunks]
    # Run concurrently in reversed order
    run2_rev = await asyncio.gather(
        *[gate.should_continue(text, [], pass_count=0) for text in reversed(chunks)]
    )
    run2 = [res[0] for res in reversed(run2_rev)]

    assert run1 == run2
    assert any(run1) and not all(run1)

    # Phase 3 DenseRetrievalGlobalRelationExtractor.filter_candidate_pairs determinism
    p3_engine = MagicMock()
    p3_engine.evaluate_noul = AsyncMock(
        return_value=DecisionNoulResult(
            passed=False,
            probability=0.90,  # p_has_relation = 1 - 0.90 = 0.10 < threshold 0.60
            empirical_accuracy=0.88,
        )
    )
    p3_cfg = Phase3Config(
        use_jev_pair_gating=True,
        pair_gating_threshold=0.60,
        pair_gating_audit_rate=0.50,
    )
    extractor = DenseRetrievalGlobalRelationExtractor(
        llm=MagicMock(),
        embedding_model=MagicMock(),
        reranker=MagicMock(),
        config=p3_cfg,
        decision_engine=p3_engine,
    )
    candidates = [
        CandidatePair(
            entity_a=L2Entity(id=f"ea_{i}", name=f"EntityA_{i}", label="Concept"),
            entity_b=L2Entity(id=f"eb_{i}", name=f"EntityB_{i}", label="Concept"),
            score=0.80,
        )
        for i in range(40)
    ]
    gated_1 = await extractor.filter_candidate_pairs(candidates)
    gated_2 = await extractor.filter_candidate_pairs(candidates)

    ids_1 = [(c.entity_a.id, c.entity_b.id) for c in gated_1]
    ids_2 = [(c.entity_a.id, c.entity_b.id) for c in gated_2]
    assert ids_1 == ids_2
    assert 0 < len(ids_1) < len(candidates)


# ===========================================================================
# AC 5: Mondrian Alpha Isolation, Observable Propagation, State Hash, LLM Cache & Seed Fingerprint
# ===========================================================================


@pytest.mark.asyncio
async def test_calibrator_preserves_global_alpha_and_observable_propagates_mondrian_strata() -> (
    None
):
    """Verify stratum calibration does not overwrite self.alpha and ObservableDecisionEngine uses task_id/language."""
    calibrator = ConformalCalibrator(alpha=0.05)
    # Stratum calibration with custom alpha=0.20 must NOT mutate global calibrator.alpha
    scores_de = [0.05 * i for i in range(1, 20)]
    calibrator.calibrate(scores_de, alpha=0.20, task_id="p4_acc", language="de")
    assert calibrator.alpha == 0.05

    scores_en = [0.01 * i for i in range(1, 20)]
    calibrator.calibrate(scores_en, alpha=0.10, task_id="p4_acc", language="en")
    assert calibrator.alpha == 0.05

    # Global calibration DOES update calibrator.alpha
    calibrator.calibrate(scores_en, alpha=0.08)
    assert calibrator.alpha == 0.08

    # ObservableDecisionEngine propagates task_id and language into calibrator.predict_set
    class _RawChoiceEngine:
        name = "raw_choice"

        async def evaluate_noul(self, state: Any, question: str) -> DecisionNoulResult:
            return DecisionNoulResult(
                passed=True, probability=0.9, empirical_accuracy=0.9
            )

        async def evaluate_choice(
            self, state: Any, question: str, options: Any, alpha: float | None = None
        ) -> DecisionScore:
            return DecisionScore(
                selected_option="A",
                class_probability=0.70,
                empirical_accuracy=0.80,
                probabilities={"A": 0.70, "B": 0.30},
                prediction_set=None,
            )

        async def evaluate_score(
            self, state: Any, question: str, levels: list[int | str]
        ) -> DecisionScore:
            return DecisionScore(
                selected_option=1,
                class_probability=0.70,
                empirical_accuracy=0.80,
                probabilities={"1": 0.70, "2": 0.30},
                prediction_set=None,
            )

    obs_en = ObservableDecisionEngine(
        inner=_RawChoiceEngine(),  # type: ignore[arg-type]
        task_id="p4_acc",
        language="en",
        calibrator=calibrator,
    )
    obs_de = ObservableDecisionEngine(
        inner=_RawChoiceEngine(),  # type: ignore[arg-type]
        task_id="p4_acc",
        language="de",
        calibrator=calibrator,
    )

    res_en = await obs_en.evaluate_choice("state", "Q?", ["A", "B"])
    res_de = await obs_de.evaluate_choice("state", "Q?", ["A", "B"])
    # English stratum has tight q_hat (~0.19 -> threshold 0.81 -> fallback top-1 ["A"]),
    # German stratum has loose q_hat (~0.80 -> threshold 0.20 -> ["A", "B"])
    assert res_en.prediction_set == ["A"]
    assert res_de.prediction_set == ["A", "B"]


@pytest.mark.asyncio
async def test_canonical_state_hash_predict_text_bundle_hash_seed_fp_and_docs(
    tmp_path: Path,
) -> None:
    """Verify canonical state hash, predict_text prompt_bundle_hash, seed fingerprinting, and docs links."""
    # 1. Canonical JSON state hash on dicts with different key insertion orders
    state_a = {"entity_b": "Hume", "entity_a": "Kant", "nested": {"y": 2, "x": 1}}
    state_b = {"nested": {"x": 1, "y": 2}, "entity_a": "Kant", "entity_b": "Hume"}
    hash_a, len_a = ObservableDecisionEngine._compute_state_hash(state_a)
    hash_b, len_b = ObservableDecisionEngine._compute_state_hash(state_b)
    assert hash_a == hash_b
    assert len_a == len_b

    # 2. DiskCachedStructuredLLM.predict_text hashes prompt_bundle_hash in NL_TO_FORMAT Pass 1
    calls = {"text": 0, "structured": 0}

    class _OutModel(BaseModel):
        answer: str = "ok"

    class _CountingLLM:
        async def predict_text(
            self, prompt: Any, llm_kwargs: Any = None, **kwargs: Any
        ) -> str:
            calls["text"] += 1
            return f"reasoning_{calls['text']}"

        async def predict_structured(
            self,
            output_cls: type[BaseModel],
            prompt_bundle: Any,
            strategy: Any = "direct_constrained",
            fallback_behavior: Any = "retry_then_omit",
            llm_kwargs: Any = None,
            **kwargs: Any,
        ) -> Any:
            calls["structured"] += 1
            return _OutModel(answer=kwargs.get("reasoning_text", "none"))

    cached_llm = DiskCachedStructuredLLM(
        base_llm=_CountingLLM(),
        cache_dir=tmp_path / "cache_109",
    )
    b1 = StructuredPromptBundle(
        name="bundle_test",
        version="1.0.0",
        reasoning_template="Reason about {text}",
        format_template="Format {reasoning_text}",
        direct_template="Direct {text}",
    )
    b2 = b1.model_copy(update={"version": "2.0.0"})

    await cached_llm.predict_structured(
        _OutModel, b1, strategy=StructuredDecodingStrategy.NL_TO_FORMAT, text="input"
    )
    assert calls["text"] == 1
    assert calls["structured"] == 1

    # Bumping bundle version must invalidate Pass 1 (predict_text) as well as Pass 2!
    await cached_llm.predict_structured(
        _OutModel, b2, strategy=StructuredDecodingStrategy.NL_TO_FORMAT, text="input"
    )
    assert calls["text"] == 2
    assert calls["structured"] == 2

    # 3. fingerprint_method() probes .seed
    class _SeededModel:
        def __init__(self, seed: int) -> None:
            self.model_name = "gpt-test"
            self.seed = seed

    fp_s1 = fingerprint_method(_SeededModel(seed=42))
    fp_s2 = fingerprint_method(_SeededModel(seed=99))
    assert fp_s1 != fp_s2

    # 4. Verify docs/architecture/conformal_prediction.md has no stale pre-refactor links
    repo_root = Path(__file__).resolve().parents[3]
    doc_text = (
        repo_root / "docs" / "architecture" / "conformal_prediction.md"
    ).read_text(encoding="utf-8")
    assert "pipeline.py#L879-L891" not in doc_text
    assert "phase3b_consolidation/runner.py" not in doc_text
    assert "phase5_fusion/runner.py" not in doc_text


def test_dynamic_workflow_dag_order_independent_sorting_and_class_based_phase_selection() -> (
    None
):
    """Verify WorkflowDAG infers dependencies from reads_kinds/writes_kinds regardless of input order and selects phases by class/classname."""
    from episteme_pipeline.phases.phase1_foundation import Phase1Runner
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
    from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
    from episteme_pipeline.phases.phase3b_consolidation import (
        Phase3bLatentConsolidationRunner,
    )
    from episteme_pipeline.phases.phase4_entity_maturation import (
        Phase4EntityMaturationRunner,
    )
    from episteme_pipeline.phases.phase5_fusion.argument_web import (
        Phase5ArgumentWebRunner,
    )
    from episteme_pipeline.runtime.workflow_dag import WorkflowDAG

    p1 = Phase1Runner(config=MagicMock(), graph_store=None, embedding_model=MagicMock())
    p2 = Phase2Runner(
        config=MagicMock(),
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
    )
    p3 = Phase3Runner(
        config=MagicMock(),
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
        graph_store=None,
        global_extractor=MagicMock(),
    )
    p3b = Phase3bLatentConsolidationRunner(
        config=MagicMock(),
        embedding_model=MagicMock(),
    )
    p4_mat = Phase4EntityMaturationRunner(
        config=MagicMock(),
        llm=MagicMock(),
        embedding_model=MagicMock(),
    )
    p4 = Phase4Runner(
        config=Phase4Config(),
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=MagicMock(),
    )
    p5 = Phase5ArgumentWebRunner(
        config=MagicMock(),
        embedding_model=MagicMock(),
    )

    # Pass phases in scrambled order: P5, P4, P3b, P4_mat, P2, P3, P1
    scrambled = [p5, p4, p3b, p4_mat, p2, p3, p1]
    dag = WorkflowDAG(phases=scrambled)

    sorted_runners = [node.runner for node in dag.topological_order()]
    assert sorted_runners == [p1, p2, p3, p3b, p4_mat, p4, p5]

    # Select nodes by PhaseRunner class, instance, class name, or phase_key
    assert dag.get_node(Phase4Runner) is not None
    assert dag.get_node(Phase4Runner).runner is p4
    assert dag.get_node("Phase4Runner").runner is p4
    assert dag.get_node(p4).runner is p4
    assert dag.get_node("phase4").runner is p4

    # ConformalCalibrator resolves allocated alpha by PhaseRunner class or class name with zero _STAGE_ALIASES
    assert not hasattr(ConformalCalibrator, "_STAGE_ALIASES")
    calibrator = ConformalCalibrator(
        alpha=0.05,
        global_alpha=0.04,
        risk_budget_weights={
            "Phase3bLatentConsolidationRunner": 0.25,
            "Phase4Runner": 0.75,
        },
    )
    assert calibrator.get_allocated_alpha(
        Phase3bLatentConsolidationRunner
    ) == pytest.approx(0.01)
    assert calibrator.get_allocated_alpha("phase3b") == pytest.approx(0.01)
    assert calibrator.get_allocated_alpha("p3b_merge") == pytest.approx(0.01)
    assert calibrator.get_allocated_alpha(Phase4Runner) == pytest.approx(0.03)
    assert calibrator.get_allocated_alpha("Phase4Runner") == pytest.approx(0.03)
    assert calibrator.get_allocated_alpha("p4_acc") == pytest.approx(0.03)
