"""Unit and integration tests for ISSUE-049: Reproducibility & Cache Coherence Hazards.

Covers:
1. Concurrency invariance of HMAC-SHA256 PRF in ObservableDecisionEngine for stochastic auditing.
2. Fingerprintable implementation on StructuredPromptBundle and automatic discovery via find_components.
3. Mondrian (task- and language-stratified) ConformalCalibrator with fingerprinting in Pipeline._method_fingerprints.
4. Schema- and decoding-aware cache key computation in DiskCachedStructuredLLM.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any
from unittest.mock import MagicMock

import pytest
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
)
from episteme_pipeline.protocols.fingerprint import (
    Fingerprintable,
    find_components,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.fingerprints import stable_fingerprint
from pydantic import BaseModel, Field

# ============================================================================
# Acceptance Criterion 1: Deterministic PRF Stochastic Auditing
# ============================================================================


class MockInnerEngine(DecisionEngine):
    """Mock engine returning deterministic decisions."""

    @property
    def name(self) -> str:
        return "MockInnerEngine"

    def fingerprint(self) -> dict[str, Any]:
        return {"name": self.name}

    async def evaluate_noul(
        self, state: str | dict[str, Any] | list[Any], question: str
    ) -> DecisionNoulResult:
        return DecisionNoulResult(
            probability=0.95,
            empirical_accuracy=0.92,
            passed=True,
        )

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        opts = list(options.keys()) if isinstance(options, dict) else list(options)
        return DecisionScore(
            selected_option=opts[0] if opts else "A",
            class_probability=0.90,
            empirical_accuracy=0.88,
        )

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        min_level: int,
        max_level: int,
        alpha: float | None = None,
    ) -> DecisionScore:
        return DecisionScore(
            selected_option=min_level,
            class_probability=0.85,
            empirical_accuracy=0.80,
        )


def test_hmac_prf_deterministic_across_evaluations():
    """Verify HMAC-SHA256 PRF generates identical audit decisions for same seed and state hash."""
    engine = ObservableDecisionEngine(
        inner=MockInnerEngine(),
        stochastic_audit_rate=0.5,
        seed=1337,
        task_id="p3b_merge",
    )

    state_hashes = [f"state_{i}_{i * 17}" for i in range(100)]

    run1_audits = [engine._should_audit(h, task_id="p3b_merge") for h in state_hashes]
    run2_audits = [engine._should_audit(h, task_id="p3b_merge") for h in state_hashes]

    assert run1_audits == run2_audits
    # At rate 0.5, some should be True and some False
    assert any(run1_audits)
    assert not all(run1_audits)

    # Different seed should yield different decisions
    engine_other_seed = ObservableDecisionEngine(
        inner=MockInnerEngine(),
        stochastic_audit_rate=0.5,
        seed=9999,
        task_id="p3b_merge",
    )
    other_audits = [
        engine_other_seed._should_audit(h, task_id="p3b_merge") for h in state_hashes
    ]
    assert other_audits != run1_audits


@pytest.mark.asyncio
async def test_hmac_prf_concurrency_invariance():
    """Verify stochastic audit flags are completely invariant to async concurrency schedule."""
    engine = ObservableDecisionEngine(
        inner=MockInnerEngine(),
        stochastic_audit_rate=0.3,
        seed=42,
        task_id="p4_arc",
    )

    items = [(f"content_block_{i * 31}", f"item_{i}") for i in range(50)]

    # Sequential evaluation
    sequential_results = []
    for s, q in items:
        h, _ = engine._compute_state_hash(s)
        audit = engine._should_audit(h, "noul")
        await engine.evaluate_noul(s, q)
        sequential_results.append((q, audit))

    # Concurrent evaluation with randomized delays simulating network/worker jitter
    async def _evaluate_jittered(s: str, q: str):
        await asyncio.sleep(random.uniform(0.001, 0.01))
        h, _ = engine._compute_state_hash(s)
        audit = engine._should_audit(h, "noul")
        await engine.evaluate_noul(s, q)
        return (q, audit)

    concurrent_tasks = [_evaluate_jittered(s, q) for s, q in items]
    random.shuffle(concurrent_tasks)
    concurrent_results_list = await asyncio.gather(*concurrent_tasks)
    concurrent_results = {q: audit for q, audit in concurrent_results_list}

    # Verify that every question has the exact same audit decision in concurrent execution
    for q, audit in sequential_results:
        assert concurrent_results[q] == audit, f"Audit decision diverged under concurrency for {q}"


# ============================================================================
# Acceptance Criterion 2: StructuredPromptBundle Fingerprintable & Auto-Discovery
# ============================================================================


def test_structured_prompt_bundle_is_fingerprintable():
    """Verify StructuredPromptBundle implements Fingerprintable and detects content edits."""
    bundle1 = StructuredPromptBundle(
        name="test_relation_prompt",
        direct_template="Extract relations between {entity_a} and {entity_b}.",
        decision_criteria={"completeness": "Must extract all valid links"},
        version="1.0.0",
    )

    assert isinstance(bundle1, Fingerprintable)
    fp1 = bundle1.fingerprint()
    hash1 = stable_fingerprint(fp1)

    # Identical bundle produces same fingerprint
    bundle1_copy = StructuredPromptBundle(
        name="test_relation_prompt",
        direct_template="Extract relations between {entity_a} and {entity_b}.",
        decision_criteria={"completeness": "Must extract all valid links"},
        version="1.0.0",
    )
    assert stable_fingerprint(bundle1_copy.fingerprint()) == hash1

    # Modified direct template produces different fingerprint
    bundle2 = StructuredPromptBundle(
        name="test_relation_prompt",
        direct_template="Extract relations between {entity_a} and {entity_b} with reasoning.",
        decision_criteria={"completeness": "Must extract all valid links"},
        version="1.0.0",
    )
    assert stable_fingerprint(bundle2.fingerprint()) != hash1

    # Modified criteria produces different fingerprint
    bundle3 = StructuredPromptBundle(
        name="test_relation_prompt",
        direct_template="Extract relations between {entity_a} and {entity_b}.",
        decision_criteria={"completeness": "Strict extraction criteria"},
        version="1.0.0",
    )
    assert stable_fingerprint(bundle3.fingerprint()) != hash1


class RunnerWithPromptBundle(PhaseRunner):
    """Runner holding an attached StructuredPromptBundle."""

    phase_key = "phase3b"
    name = "Phase 3b: Borderline Merge"
    checkpoint_store = None

    def __init__(self, prompt: StructuredPromptBundle) -> None:
        self.merge_prompt = prompt

    async def run(self, phase_input: Any, context: Any) -> Any:
        return None

    def components(self) -> dict[str, Any]:
        return {"merge_prompt": self.merge_prompt}


def test_find_components_and_prompt_fingerprints_discover_bundles():
    """Verify find_components discovers StructuredPromptBundle and Pipeline._prompt_fingerprints includes it."""
    bundle = StructuredPromptBundle(
        name="borderline_merge_prompt",
        direct_template="Merge entities: {a} and {b}",
    )
    runner = RunnerWithPromptBundle(bundle)

    # find_components discovers bundle
    comps = find_components(runner)
    assert "merge_prompt" in comps
    assert isinstance(comps["merge_prompt"], StructuredPromptBundle)

    # Pipeline discovers bundle across runner components without hardcoding
    config = PipelineConfig()
    pipeline = Pipeline(
        phases=[runner],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
    )

    fps = pipeline._prompt_fingerprints()
    assert "phase3b" in fps
    assert "borderline_merge_prompt" in fps["phase3b"]


# ============================================================================
# Acceptance Criterion 3: Mondrian Conformal Calibration & Manifest Lineage
# ============================================================================


def test_mondrian_conformal_calibrator_stratification_and_fingerprint():
    """Verify ConformalCalibrator supports per-task and per-language stratification and fingerprinting."""
    calibrator = ConformalCalibrator(alpha=0.1)

    # Calibrate task p4_acc with distinct English and German scores (n >= 10 needed for alpha=0.1)
    en_scores = [0.01 * i for i in range(1, 21)]  # 0.01 to 0.20 (high confidence)
    de_scores = [0.03 * i for i in range(1, 21)]  # 0.03 to 0.60 (lower confidence)

    calibrator.calibrate(en_scores, task_id="p4_acc", language="en")
    calibrator.calibrate(de_scores, task_id="p4_acc", language="de")

    q_en = calibrator.get_q_hat(task_id="p4_acc", language="en")
    q_de = calibrator.get_q_hat(task_id="p4_acc", language="de")

    assert q_en < q_de, f"Expected English quantile {q_en} to be lower than German quantile {q_de}"

    # Prediction set stratified by language
    score_obj = DecisionScore(
        selected_option="A",
        class_probability=0.75,
        empirical_accuracy=0.80,
        probabilities={"A": 0.75, "B": 0.25},
    )
    set_en = calibrator.predict_set(score_obj, task_id="p4_acc", language="en")
    set_de = calibrator.predict_set(score_obj, task_id="p4_acc", language="de")
    assert len(set_de) >= len(set_en)

    # Fingerprint verification
    fp = calibrator.fingerprint()
    cal_state = fp["calibration_state"]
    assert "p4_acc_en" in cal_state
    assert "p4_acc_de" in cal_state
    assert cal_state["p4_acc_en"]["q_hat"] == q_en
    assert cal_state["p4_acc_en"]["n_cal"] == len(en_scores)
    assert "dataset_sha256" in cal_state["p4_acc_en"]


def test_calibrator_discovered_in_pipeline_method_fingerprints():
    """Verify decision_engine and its calibrator are discovered in Pipeline._method_fingerprints."""
    calibrator = ConformalCalibrator()
    calibrator.calibrate([0.1, 0.2, 0.3], task_id="p3_rerank", language="en")

    engine = ObservableDecisionEngine(
        inner=MockInnerEngine(),
        calibrator=calibrator,
        seed=123,
    )

    config = PipelineConfig()
    pipeline = Pipeline(
        phases=[],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        decision_engine=engine,
    )

    method_fps = pipeline._method_fingerprints()
    assert any("decision_engine" in k for k in method_fps)
    assert any("calibrator" in k for k in method_fps)


# ============================================================================
# Acceptance Criterion 4: Schema & Decoding-Aware DiskCachedStructuredLLM
# ============================================================================


class OutputModelA(BaseModel):
    name: str
    confidence: float


class OutputModelB(BaseModel):
    name: str
    confidence: float
    reasoning: str = Field(description="Explanation of classification")


def test_disk_cached_structured_llm_schema_and_decoding_sensitivity(tmp_path):
    """Verify DiskCachedStructuredLLM cache keys change when schema or decoding strategy changes."""
    mock_base_llm = MagicMock()
    mock_base_llm.model_name = "test-model"

    cached_llm = DiskCachedStructuredLLM(
        base_llm=mock_base_llm,
        cache_dir=tmp_path / "llm_cache",
    )

    prompt = "Extract entity details from text."

    # Cache path for Model A
    path_a = cached_llm._get_cache_path(
        cache_prefix="struct",
        output_schema=OutputModelA.__name__,
        prompt=prompt,
        prompt_args={},
        strategy="direct_constrained",
        schema_json_hash=stable_fingerprint(OutputModelA.model_json_schema()),
    )

    # Cache path for Model B (modified schema)
    path_b = cached_llm._get_cache_path(
        cache_prefix="struct",
        output_schema=OutputModelB.__name__,
        prompt=prompt,
        prompt_args={},
        strategy="direct_constrained",
        schema_json_hash=stable_fingerprint(OutputModelB.model_json_schema()),
    )

    # Different schemas must produce different cache paths
    assert path_a != path_b

    # Cache path for Model A with nl_to_format decoding strategy
    path_a_nl = cached_llm._get_cache_path(
        cache_prefix="struct",
        output_schema=OutputModelA.__name__,
        prompt=prompt,
        prompt_args={},
        strategy="nl_to_format",
        schema_json_hash=stable_fingerprint(OutputModelA.model_json_schema()),
    )

    # Different decoding strategies must produce different cache paths
    assert path_a != path_a_nl


def test_should_audit_combines_engine_task_id_and_primitive():
    """Verify _should_audit combines self.task_id with primitive task_id so tasks do not collide."""
    engine_p3 = ObservableDecisionEngine(
        inner=MockInnerEngine(),
        stochastic_audit_rate=0.5,
        seed=42,
        task_id="p3_rerank",
    )
    engine_p5 = ObservableDecisionEngine(
        inner=MockInnerEngine(),
        stochastic_audit_rate=0.5,
        seed=42,
        task_id="p5_fusion",
    )
    hashes = [f"state_{i}" for i in range(50)]
    audits_p3 = [engine_p3._should_audit(h, "noul") for h in hashes]
    audits_p5 = [engine_p5._should_audit(h, "noul") for h in hashes]
    assert audits_p3 != audits_p5


@pytest.mark.asyncio
async def test_calibrator_drift_invalidates_phase_reuse(tmp_path):
    """Verify that recalibrating ConformalCalibrator on decision_engine invalidates prior run reuse."""
    from episteme_pipeline.contracts.phase_contracts import PipelineInput
    from episteme_pipeline.runs.models import RunPhaseRecord, RunStatus

    class DummyPhase1(PhaseRunner):
        phase_key = "phase1"
        name = "Phase 1"
        checkpoint_store = None

        async def run(self, phase_input: Any, context: Any) -> Any:
            from episteme_pipeline.artifacts.execution import ArtifactCollection

            return ArtifactCollection([])

        def components(self) -> dict[str, Any]:
            return {}

    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    cal1 = ConformalCalibrator(alpha=0.1)
    cal1.calibrate([0.05 * i for i in range(1, 15)], task_id="p3b_merge", language="en")
    engine1 = ObservableDecisionEngine(inner=MockInnerEngine(), calibrator=cal1)

    p1 = Pipeline(
        phases=[DummyPhase1()],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        decision_engine=engine1,
    )
    pipe_input = PipelineInput(source_paths=[])
    manifest1 = p1._build_manifest(run_id="run-1", pipeline_input=pipe_input)
    manifest1.status = RunStatus.COMPLETED
    manifest1.phase_records = [
        RunPhaseRecord(phase_name="Phase 1", ordinal=1, status=RunStatus.COMPLETED)
    ]
    p1._manifest_store.write_manifest(manifest1)

    # Recalibrate with shifted scores
    cal2 = ConformalCalibrator(alpha=0.1)
    cal2.calibrate([0.09 * i for i in range(1, 15)], task_id="p3b_merge", language="en")
    engine2 = ObservableDecisionEngine(inner=MockInnerEngine(), calibrator=cal2)

    p2 = Pipeline(
        phases=[DummyPhase1()],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        decision_engine=engine2,
    )
    manifest2 = p2._build_manifest(run_id="run-2", pipeline_input=pipe_input)
    decision = await p2._choose_reuse_source(manifest2)

    assert decision.reused_phase_ordinals == []
    assert decision.invalidated_phase_ordinals == [1]
    assert decision.reason == "method-changed:decision_engine"


@pytest.mark.asyncio
async def test_nl_to_format_preserves_prompt_bundle_hash_in_pass_2(tmp_path):
    """Verify NL_TO_FORMAT pass 2 cache key incorporates StructuredPromptBundle fingerprint."""
    from episteme_pipeline.config import StructuredDecodingStrategy

    call_count = {"structured": 0, "text": 0}

    class StubStructuredLLM:
        async def predict_text(self, prompt: Any, llm_kwargs: Any = None, **kwargs: Any) -> str:
            call_count["text"] += 1
            return "stub reasoning text"

        async def predict_structured(
            self,
            output_cls: type[BaseModel],
            prompt_bundle: Any,
            strategy: Any = "direct_constrained",
            fallback_behavior: Any = "retry_then_omit",
            llm_kwargs: Any = None,
            **kwargs: Any,
        ) -> Any:
            call_count["structured"] += 1
            return OutputModelA(name="ent", confidence=0.9)

    cached_llm = DiskCachedStructuredLLM(
        base_llm=StubStructuredLLM(),
        cache_dir=tmp_path / "nl_cache",
    )

    bundle_v1 = StructuredPromptBundle(
        name="ner_test",
        version="1.0.0",
        reasoning_template="Reason about {text}",
        format_template="Format {reasoning_text}",
        direct_template="Direct {text}",
    )
    bundle_v2 = bundle_v1.model_copy(update={"version": "2.0.0"})

    await cached_llm.predict_structured(
        OutputModelA,
        bundle_v1,
        strategy=StructuredDecodingStrategy.NL_TO_FORMAT,
        text="sample",
    )
    assert call_count["structured"] == 1

    # Bumping bundle version must miss Pass 2 cache even if reasoning_text and format_template are unchanged
    await cached_llm.predict_structured(
        OutputModelA,
        bundle_v2,
        strategy=StructuredDecodingStrategy.NL_TO_FORMAT,
        text="sample",
    )
    assert call_count["structured"] == 2

