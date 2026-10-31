"""Unit and integration tests for component fingerprinting and tree discovery.

Grounding & Verification:
- Verifies that any object implementing the ``Fingerprintable`` protocol
  is automatically discovered across phase runners and nested composite subgraphs.
- Verifies that DecisionEngine, ModalStrengthResolver, rerankers, and extractors
  participate in deterministic manifest fingerprinting and cache invalidation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.decision.jev_client import LayaDecisionEngine
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.decision.modal_resolver import (
    DecisionEngineModalResolver,
    HybridModalResolver,
    StructuralistModalResolver,
)
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols.fingerprint import (
    Fingerprintable,
    find_components,
    is_component,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.runs.models import (
    RunManifest,
    RunPhaseRecord,
    RunStatus,
)
from pydantic import BaseModel


class CustomLeafComponent:
    """Mock leaf component implementing Fingerprintable."""

    def __init__(self, model_id: str, threshold: float = 0.5) -> None:
        self.model_id = model_id
        self.threshold = threshold

    def fingerprint(self) -> dict[str, Any]:
        return {
            "class": self.__class__.__name__,
            "model_id": self.model_id,
            "threshold": self.threshold,
        }


class CustomCompositeComponent:
    """Mock composite component containing nested components."""

    def __init__(self, name: str, sub_component: CustomLeafComponent) -> None:
        self.name = name
        self.sub_component = sub_component


class DummyPhase(PhaseRunner[Any]):
    name = "Phase: Custom Verification"
    phase_key = "phase1"

    def __init__(
        self,
        component_a: Any,
        component_list: list[Any] | None = None,
        component_dict: dict[str, Any] | None = None,
    ) -> None:
        self.component_a = component_a
        self.component_list = component_list or []
        self.component_dict = component_dict or {}

    async def run(
        self, input: Any, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        return ArtifactCollection([])


def test_is_component_identifies_fingerprintable() -> None:
    leaf = CustomLeafComponent("m1", 0.8)
    assert is_component(leaf) is True
    assert isinstance(leaf, Fingerprintable)


def test_is_component_ignores_primitives() -> None:
    assert is_component("hello") is False
    assert is_component(42) is False
    assert is_component(True) is False
    assert is_component(None) is False


def test_is_component_ignores_pydantic_models() -> None:
    class DummyConfig(BaseModel):
        threshold: float = 0.5
        name: str = "config"

    cfg = DummyConfig()
    assert is_component(cfg) is False


def test_is_component_requires_fingerprintable_protocol() -> None:
    class UnannotatedModel:
        pass

    obj = UnannotatedModel()
    assert is_component(obj) is False

    class AnnotatedComponent:
        def fingerprint(self) -> dict[str, str]:
            return {"type": "annotated"}

    assert is_component(AnnotatedComponent()) is True


def test_is_component_rejects_non_callable_fingerprint() -> None:
    class NonCallableFingerprint:
        fingerprint = "not-a-method"

    obj = NonCallableFingerprint()
    # While PEP 544 @runtime_checkable does shallow attribute existence check,
    # is_component strictly verifies that the fingerprint method is callable.
    assert is_component(obj) is False


def test_find_components_ignores_private_attributes() -> None:
    class RunnerWithPrivate:
        def __init__(self) -> None:
            self._private_comp = CustomLeafComponent("hidden", 0.5)
            self.public_comp = CustomLeafComponent("visible", 0.5)

    discovered = find_components(RunnerWithPrivate())
    assert "public_comp" in discovered
    assert "_private_comp" not in discovered


def test_find_components_handles_mocks_safely() -> None:
    class RunnerWithMocks:
        def __init__(self) -> None:
            self.mock_service = MagicMock()
            self.llm = Mock()
            self.llm.fingerprint = Mock(return_value={"model": "test"})
            self.real_comp = CustomLeafComponent("real", 0.7)

    runner = RunnerWithMocks()
    discovered = find_components(runner)
    assert "llm" in discovered
    assert "real_comp" in discovered
    assert not any("mock_service." in k for k in discovered)
    assert not any("llm." in k for k in discovered)


def test_phase_runner_components_method_delegation() -> None:
    leaf = CustomLeafComponent("bert", 0.8)
    runner = DummyPhase(component_a=leaf)
    comps = runner.components()
    assert "component_a" in comps
    assert comps["component_a"] is leaf


def test_find_components_mixed_collections() -> None:
    leaf = CustomLeafComponent("item", 0.5)

    class RunnerWithMixed:
        def __init__(self) -> None:
            self.items = [1, "text", None, leaf, False]
            self.mapping = {"num": 10, "leaf": leaf, "_priv": leaf}

    discovered = find_components(RunnerWithMixed())
    assert "items[3]" in discovered
    assert discovered["items[3]"] is leaf
    assert len([k for k in discovered if k.startswith("items")]) == 1

    assert "mapping.leaf" in discovered
    assert discovered["mapping.leaf"] is leaf
    assert "mapping._priv" not in discovered


def test_find_components_recursive_discovery() -> None:
    leaf = CustomLeafComponent("bert-base", 0.9)
    composite = CustomCompositeComponent("outer", leaf)
    item_in_list = CustomLeafComponent("list-item", 0.1)
    item_in_dict = CustomLeafComponent("dict-item", 0.2)

    runner = DummyPhase(
        component_a=composite,
        component_list=[item_in_list],
        component_dict={"special": item_in_dict},
    )

    discovered = find_components(runner)

    # Sub-component in composite
    assert "component_a.sub_component" in discovered
    assert discovered["component_a.sub_component"] is leaf

    # Items in lists and dicts
    assert "component_list[0]" in discovered
    assert discovered["component_list[0]"] is item_in_list
    assert "component_dict.special" in discovered
    assert discovered["component_dict.special"] is item_in_dict


def test_find_components_cycle_protection() -> None:
    class CyclicNode:
        def __init__(self) -> None:
            self.child: Any = None

        def fingerprint(self) -> dict[str, Any]:
            return {"class": "CyclicNode"}

    node_a = CyclicNode()
    node_b = CyclicNode()
    node_a.child = node_b
    node_b.child = node_a

    # Should not raise RecursionError
    discovered = find_components(node_a)
    assert len(discovered) > 0


def test_decision_engine_fingerprint_sensitivity() -> None:
    eng1 = LayaDecisionEngine(checkpoint="model-v1", default_confidence_threshold=0.8)
    eng2 = LayaDecisionEngine(checkpoint="model-v1", default_confidence_threshold=0.9)
    eng3 = LayaDecisionEngine(checkpoint="model-v2", default_confidence_threshold=0.8)

    fp1 = fingerprint_method(eng1)
    fp2 = fingerprint_method(eng2)
    fp3 = fingerprint_method(eng3)

    assert fp1 is not None and fp2 is not None and fp3 is not None
    assert fp1 != fp2, "Changing confidence threshold must change fingerprint"
    assert fp1 != fp3, "Changing checkpoint must change fingerprint"


def test_mock_decision_engine_fingerprint_sensitivity() -> None:
    mock1 = MockJevDecisionEngine(default_confidence_threshold=0.85)
    mock2 = MockJevDecisionEngine(default_confidence_threshold=0.95)

    fp1 = fingerprint_method(mock1)
    fp2 = fingerprint_method(mock2)

    assert fp1 is not None and fp2 is not None
    assert fp1 != fp2

    mock1.register_noul_response("test question", probability=0.9)
    fp1_with_rule = fingerprint_method(mock1)
    assert fp1 != fp1_with_rule, "Registering rule must change mock fingerprint"


def test_observable_decision_engine_propagates_fingerprint() -> None:
    inner = MockJevDecisionEngine(default_confidence_threshold=0.85)
    obs1 = ObservableDecisionEngine(inner, stochastic_audit_rate=0.0)
    obs2 = ObservableDecisionEngine(inner, stochastic_audit_rate=0.1)

    fp1 = fingerprint_method(obs1)
    fp2 = fingerprint_method(obs2)

    assert fp1 != fp2, "Changing stochastic audit rate must change fingerprint"

    inner2 = MockJevDecisionEngine(default_confidence_threshold=0.95)
    obs3 = ObservableDecisionEngine(inner2, stochastic_audit_rate=0.0)
    fp3 = fingerprint_method(obs3)

    assert fp1 != fp3, "Changing inner engine must change wrapped fingerprint"


def test_modal_resolver_fingerprint_sensitivity() -> None:
    struct1 = StructuralistModalResolver(default_base_score=0.6)
    struct2 = StructuralistModalResolver(default_base_score=0.7)

    assert fingerprint_method(struct1) != fingerprint_method(struct2)

    eng = MockJevDecisionEngine()
    dec_res1 = DecisionEngineModalResolver(eng, question_template="Q1")
    dec_res2 = DecisionEngineModalResolver(eng, question_template="Q2")

    assert fingerprint_method(dec_res1) != fingerprint_method(dec_res2)

    hybrid1 = HybridModalResolver(structural_resolver=struct1, decision_resolver=dec_res1, mode="guardrail")
    hybrid2 = HybridModalResolver(structural_resolver=struct1, decision_resolver=dec_res1, mode="convex")

    assert fingerprint_method(hybrid1) != fingerprint_method(hybrid2)


@pytest.mark.asyncio
async def test_pipeline_invalidates_when_decision_engine_changes(tmp_path, graph_store):
    """Integration test: changing DecisionEngine invalidates the consuming phase."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    eng_old = MockJevDecisionEngine(default_confidence_threshold=0.80)
    eng_new = MockJevDecisionEngine(default_confidence_threshold=0.95)

    class PhaseWithDecisionEngine(PhaseRunner[Any]):
        name = "Phase 2: Entity & Local Relation Discovery"
        phase_key = "phase2"

        def __init__(self, engine: Any) -> None:
            self.decision_engine = engine

        async def run(self, input: Any, context: ArtifactExecutionContext) -> ArtifactCollection:
            return ArtifactCollection([])

    pipeline = Pipeline(
        phases=[PhaseWithDecisionEngine(eng_new)],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    old_manifest_fps = {
        "Phase 2: Entity & Local Relation Discovery.decision_engine": fingerprint_method(eng_old)
    }

    prior = RunManifest(
        run_id="run-old",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input",
        phase_config_fingerprints={"phase2": "same"},
        method_fingerprints=old_manifest_fps,
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 2: Entity & Local Relation Discovery",
                ordinal=1,
                status=RunStatus.COMPLETED,
            ),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)

    current_manifest = pipeline._build_manifest(
        run_id="run-new",
        pipeline_input=MagicMock(source_paths=[], bib_paths=[], metadata={}, structural_anchor=None),
    )
    current_manifest.input_fingerprint = "same-input"
    current_manifest.phase_config_fingerprints = {"phase2": "same"}

    decision = await pipeline._choose_reuse_source(current_manifest)

    assert 1 in decision.invalidated_phase_ordinals, "Phase 2 must be invalidated due to decision engine change"
    assert "method-changed" in decision.reason


def test_pipeline_manifest_captures_nested_component_hierarchy(tmp_path, graph_store) -> None:
    """Verify that Pipeline manifest captures dotted paths for nested components."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    leaf = CustomLeafComponent("bert-base", 0.95)
    composite = CustomCompositeComponent("wrapper", leaf)
    phase = DummyPhase(component_a=composite)

    pipeline = Pipeline(
        phases=[phase],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    manifest = pipeline._build_manifest(
        run_id="run-hierarchy",
        pipeline_input=MagicMock(source_paths=[], bib_paths=[], metadata={}, structural_anchor=None),
    )

    expected_key = "Phase: Custom Verification.component_a.sub_component"
    assert expected_key in manifest.method_fingerprints
    assert manifest.method_fingerprints[expected_key] == fingerprint_method(leaf)

