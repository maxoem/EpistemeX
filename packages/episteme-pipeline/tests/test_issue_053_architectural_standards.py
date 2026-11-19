"""Architectural, domain, and composition-root tests for ISSUE-053 refactoring.

Verifies sustainable compliance with ``docs/architecture/design_patterns_and_standards.md``
and ``AGENTS.md`` across:
1. Prompt management & fingerprinting (``DefaultPromptProvider``,
   ``ArtifactExecutionEngine.prompt_fingerprints()``).
2. Single-source ``SchemaConfig`` partition/polarity resolution & shared ``Z_1`` logic.
3. System 1 ``DecisionEngine`` triage gates (``evaluate_choice`` conformal split
   gating, ``evaluate_noul`` recoverability/grounding gating, deterministic audit).
4. Split parent retirement, mention updates, and pass-aware ``ArtifactDependencyGraph``
   DAG acyclicity without stripping ``deficit_artifact_id`` provenance.
5. Intra-pass sequential overlay coherence and connected-component localization.
6. Shared ``PipelineFactory`` / ``Pipeline`` composition root wiring
   (``CascadingARCClassifier``, ``CascadingEntityLinker``, ``HybridModalResolver``,
   ``TheoryProjector`` vs ``TheoryNetProjector`` type enforcement).
7. Static zero-reflection AST and NumPy docstring audit on all new/refactored files.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_chunk_artifact,
    build_entity_mention_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicDeficitArtifactsView,
    EpistemicStateView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.invalidate import ArtifactDependencyGraph
from episteme_pipeline.artifacts.models import (
    ArtifactKind,
    EntityMentionArtifact,
    LinkedEntityArtifact,
)
from episteme_pipeline.artifacts.refinement_overlay import (
    build_deficit_envelope,
    build_delta_envelopes,
    overlay_collection,
    slice_phase4_component_view,
)
from episteme_pipeline.config import (
    HermeneuticRefinementConfig,
    PipelineConfig,
)
from episteme_pipeline.contracts import (
    EntityConception,
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    L2Triple,
    PipelineInput,
    RefinementDelta,
    SubGraph,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.phases.phase2_entity_discovery.jev_entity_linker import (
    CascadingEntityLinker,
)
from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import (
    LLMNERExtractor,
)
from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
    CascadingARCClassifier,
)
from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
    GenericTheoryProjector,
    TheoryProjector,
)
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.prompts.providers import (
    DefaultPromptProvider,
    FilePromptProvider,
)
from episteme_pipeline.protocols.decision import (
    DecisionNoulResult,
    DecisionScore,
)
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    RelationReranker,
)
from episteme_pipeline.refinement import (
    ClosedLoopRefinementCoordinator,
    ConceptionConceptSplitter,
    LLMTheoryGuidedPremiseRecoverer,
    TheoryGuidedAxiomGrounder,
    TheoryNetDeficitDetector,
)
from episteme_pipeline.refinement.premise_recovery import (
    PremiseRecoveryOutput,
    RecoveredImplicitPremise,
)
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.runtime.execution_engine import ArtifactExecutionEngine
from episteme_pipeline.runtime.pipeline_factory import PipelineFactory
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig
from episteme_pipeline.utils.similarity import cosine_similarity

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "episteme_pipeline"


def _make_context(
    run_id: str = "run-std",
    refinement_pass: int = 0,
    ledger: EpistemicCurationLedger | None = None,
) -> ArtifactExecutionContext:
    """Create a deterministic execution context for tests."""
    return ArtifactExecutionContext(
        run_id=run_id,
        manifest=RunManifest(run_id=run_id, refinement_pass=refinement_pass),
        pipeline_input=PipelineInput(source_paths=[], curation_ledger=ledger),
    )


class _StructuredStub:
    """Minimal structured prediction port stub."""

    def __init__(self, output: Any) -> None:
        self._output = output
        self.calls: int = 0

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StructuredStub"}

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        del output_cls, prompt_bundle, strategy, fallback_behavior, llm_kwargs, prompt_args
        self.calls += 1
        return self._output


class _EmbedderStub(EmbeddingModel):
    """Deterministic unit-vector embedding stub."""

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_EmbedderStub"}

    async def aget_text_embedding(self, text: str) -> list[float]:
        lowered = text.lower()
        if "physic" in lowered or "mass" in lowered:
            return [1.0, 0.0, 0.0]
        if "ethic" in lowered or "moral" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.7, 0.7, 0.0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.aget_text_embedding(t) for t in texts]


class _RerankerStub(RelationReranker):
    """Minimal RelationReranker stub."""

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_RerankerStub"}

    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: SubGraph,
        entity_b: L2Entity,
        env_b: SubGraph,
    ) -> float:
        del entity_a, env_a, entity_b, env_b
        return 0.9

    async def score_pairs(
        self, pairs: list[tuple[Any, Any]]
    ) -> list[tuple[Any, float]]:
        return [(p, 0.9) for p in pairs]


class _ScriptedDecisionEngine(MockJevDecisionEngine):
    """DecisionEngine allowing deterministic scripting of choice and noul responses."""

    def __init__(
        self,
        *,
        choice_result: DecisionScore | None = None,
        noul_result: DecisionNoulResult | None = None,
    ) -> None:
        super().__init__()
        self._choice_result = choice_result
        self._noul_result = noul_result
        self.choice_calls: int = 0
        self.noul_calls: int = 0

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        self.choice_calls += 1
        if self._choice_result is not None:
            return self._choice_result
        return await super().evaluate_choice(state, question, options, alpha=alpha)

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        self.noul_calls += 1
        if self._noul_result is not None:
            return self._noul_result
        return await super().evaluate_noul(state, question)


# ---------------------------------------------------------------------------
# 1. Prompt Management & Config Centralization
# ---------------------------------------------------------------------------


def test_refinement_prompts_registered_and_fingerprinted_only_when_active(
    tmp_path: Path,
) -> None:
    """Refinement prompt bundles live in prompt providers and fingerprint cleanly."""
    provider = DefaultPromptProvider()
    for name in ("concept_split", "premise_recovery", "axiom_grounding"):
        bundle = provider.get_bundle(name)
        assert bundle.direct_template.strip()
        assert bundle.decision_template and bundle.decision_template.strip()

    cfg_off = PipelineConfig(refinement=HermeneuticRefinementConfig(max_refinement_cycles=0))
    provider.populate_config(cfg_off)
    assert cfg_off.refinement.concept_split_prompts.name == "concept_split"
    assert cfg_off.refinement.premise_recovery_prompts.name == "premise_recovery"
    assert cfg_off.refinement.axiom_grounding_prompts.name == "axiom_grounding"

    workflow = PipelineFactory.build_workflow(task="knowledge_graph", phases=[])
    fps_off = ArtifactExecutionEngine(workflow=workflow, config=cfg_off).prompt_fingerprints()
    assert "refinement" not in fps_off
    expected_forward_keys = set(fps_off.keys())
    assert {"phase2", "phase3", "phase4"}.issubset(expected_forward_keys)

    cfg_on = cfg_off.model_copy(
        update={"refinement": cfg_off.refinement.model_copy(update={"max_refinement_cycles": 1})}
    )
    fps_on = ArtifactExecutionEngine(workflow=workflow, config=cfg_on).prompt_fingerprints()
    assert set(fps_on.keys()) == expected_forward_keys | {"refinement"}
    for phase_key in expected_forward_keys:
        assert fps_on[phase_key] == fps_off[phase_key]
    assert set(fps_on["refinement"].keys()) == {
        "concept_split",
        "premise_recovery",
        "axiom_grounding",
    }

    # Mutating template alters refinement prompt fingerprint while preserving forward fingerprints
    custom_dir = tmp_path / "prompts"
    custom_dir.mkdir(parents=True)
    custom_bundle = cfg_on.refinement.premise_recovery_prompts.model_copy(
        update={"direct_template": "Custom recovery template for {theory_id}: {source_chunks}"}
    )
    (custom_dir / "premise_recovery.json").write_text(
        custom_bundle.model_dump_json(), encoding="utf-8"
    )
    file_cfg = PipelineConfig(refinement=HermeneuticRefinementConfig(max_refinement_cycles=1))
    FilePromptProvider(custom_dir).populate_config(file_cfg)
    fps_mutated = ArtifactExecutionEngine(workflow=workflow, config=file_cfg).prompt_fingerprints()
    assert fps_mutated["refinement"]["premise_recovery"] != fps_on["refinement"]["premise_recovery"]
    assert fps_mutated["phase2"] == fps_on["phase2"]


# ---------------------------------------------------------------------------
# 2. Single-Source Schema & Similarity Centralization
# ---------------------------------------------------------------------------


def test_schema_config_centralizes_partitions_and_polarities() -> None:
    """Custom SchemaConfig component partition and polarity tables drive detection without hacks."""
    custom_schema = SchemaConfig(
        component_types=["FieldReport", "GrandPostulate"],
        component_partitions={"FieldReport": "B", "GrandPostulate": "A"},
        argument_relation_types=["BOLSTERS", "UNDERMINES"],
        relation_polarities={"BOLSTERS": 1, "UNDERMINES": -1},
    )
    assert custom_schema.resolve_component_partition("FieldReport") == "B"
    assert custom_schema.resolve_component_partition("GrandPostulate") == "A"
    assert custom_schema.get_partition_components("B") == ["FieldReport"]
    assert custom_schema.default_observation_component_type() == "FieldReport"
    assert custom_schema.default_support_relation() == "BOLSTERS"
    assert custom_schema.get_relation_polarity("bolsters") == 1
    assert custom_schema.get_relation_polarity("UNDERMINES") == -1

    detector = TheoryNetDeficitDetector(schema=custom_schema)
    state = EpistemicDeficitArtifactsView(
        chunks=[L1Chunk(id="c1", text="Telemetry log", source_doc_id="d1", sequence_index=0, token_count=3)],
        theory_atoms=[
            TheoryAtom(id="obs", text="Telemetry datum", component_type="FieldReport", source_chunk_id="c1"),
            TheoryAtom(id="post", text="Core postulate", component_type="GrandPostulate", source_chunk_id="c1"),
        ],
    )
    deficits = detector.detect_deficits(state)
    assert len(deficits) == 1
    assert deficits[0].deficit_kind == EpistemicDeficitKind.ENTHYMEME_GAP
    assert deficits[0].target_atom_ids == ["post"]

    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


# ---------------------------------------------------------------------------
# 3. DecisionEngine Triage & Scoping Integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concept_splitter_decision_engine_prevents_univocal_disagreement_split() -> None:
    """High-confidence UNIVOCAL_DISAGREEMENT conformal set blocks spurious entity split."""
    c1 = L1Chunk(id="c1", text="Author A affirms X.", source_doc_id="d1", sequence_index=0, token_count=4)
    c2 = L1Chunk(id="c2", text="Author B critiques X.", source_doc_id="d2", sequence_index=0, token_count=4)
    ent = L2Entity(
        id="ent_x",
        label="Concept",
        name="Consciousness",
        source_chunk_ids=["c1", "c2"],
        conceptions=[
            EntityConception(
                id="ec1",
                entity_id="ent_x",
                perspective="A",
                description="Conception A",
                source_chunk_ids=["c1"],
            ),
            EntityConception(
                id="ec2",
                entity_id="ent_x",
                perspective="B",
                description="Conception B",
                source_chunk_ids=["c2"],
            ),
        ],
    )
    state = EpistemicStateView(chunks=[c1, c2], entities=[ent])
    deficit = EpistemicDeficit(
        deficit_id="polysemy::ent_x",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
        target_entity_ids=["ent_x"],
        target_chunk_ids=["c1", "c2"],
    )

    engine_univocal = _ScriptedDecisionEngine(
        choice_result=DecisionScore(
            selected_option="UNIVOCAL_DISAGREEMENT",
            class_probability=0.95,
            probabilities={"UNIVOCAL_DISAGREEMENT": 0.95, "TRUE_POLYSEMY_SPLIT": 0.05},
            prediction_set=["UNIVOCAL_DISAGREEMENT"],
            empirical_accuracy=0.95,
        )
    )
    cfg_no_audit = HermeneuticRefinementConfig(max_refinement_cycles=1, stochastic_audit_rate=0.0)
    delta_blocked = await ConceptionConceptSplitter(
        decision_engine=engine_univocal,
        config=cfg_no_audit,
        schema=DEFAULT_SCHEMA,
    ).split_concept(deficit, state, context=_make_context())
    assert delta_blocked.is_empty
    assert engine_univocal.choice_calls == 1

    # Ambiguous multi-label conformal prediction set escalates cleanly to split
    engine_ambiguous = _ScriptedDecisionEngine(
        choice_result=DecisionScore(
            selected_option="UNIVOCAL_DISAGREEMENT",
            class_probability=0.52,
            probabilities={"UNIVOCAL_DISAGREEMENT": 0.52, "TRUE_POLYSEMY_SPLIT": 0.48},
            prediction_set=["UNIVOCAL_DISAGREEMENT", "TRUE_POLYSEMY_SPLIT"],
            empirical_accuracy=0.70,
        )
    )
    delta_split = await ConceptionConceptSplitter(
        decision_engine=engine_ambiguous,
        config=cfg_no_audit,
        schema=DEFAULT_SCHEMA,
    ).split_concept(deficit, state, context=_make_context())
    assert len(delta_split.entities) == 2
    assert delta_split.retired_entity_ids == ["ent_x"]
    assert delta_split.split_entity_parents == {
        "ent_x__sense_1": "ent_x",
        "ent_x__sense_2": "ent_x",
    }


@pytest.mark.asyncio
async def test_premise_recoverer_preserves_adr0023_scoping_and_decision_gate() -> None:
    """Premise recoverer runs DecisionEngine gate, preserves scoping, and resolves modality."""
    chunk = L1Chunk(id="ck1", text="Hume noted causation may be constant conjunction.", source_doc_id="d1", sequence_index=0, token_count=8)
    claim = TheoryAtom(id="c_main", text="Causation requires necessity.", component_type="TheoreticalHypothesis", source_chunk_id="ck1")
    state = EpistemicStateView(chunks=[chunk], theory_atoms=[claim], canonical_theory_atoms=[claim])
    deficit = EpistemicDeficit(
        deficit_id="enth::c_main",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        target_chunk_ids=["ck1"],
        target_atom_ids=["c_main"],
    )

    llm = _StructuredStub(
        PremiseRecoveryOutput(
            recovered_premises=[
                RecoveredImplicitPremise(
                    local_id="P1",
                    text="Hume denies observable necessary connection.",
                    component_type="TheoreticalHypothesis",
                    source_chunk_id="ck1",
                    target_atom_id="c_main",
                    relation_type="ATTACKS",
                    confidence=0.88,
                    weight=0.75,
                    scope_type="Essentieller Allsatz",
                    epistemic_status="Synthetisch",
                    intensional_mode="attributed",
                    attributed_to="Hume",
                )
            ]
        )
    )

    class _ModalStub:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "_ModalStub"}

        async def resolve_modality(self, atom: TheoryAtom, context: str | None = None) -> float:
            del atom, context
            return 0.62

    cfg = HermeneuticRefinementConfig(max_refinement_cycles=1, stochastic_audit_rate=0.0)
    # High-confidence negative DecisionEngine gates out System 2 LLM call
    gate_off = _ScriptedDecisionEngine(
        noul_result=DecisionNoulResult(probability=0.05, empirical_accuracy=0.95, passed=False)
    )
    delta_skipped = await LLMTheoryGuidedPremiseRecoverer(
        llm=llm,
        decision_engine=gate_off,
        config=cfg,
    ).recover_premises(deficit, state, context=_make_context())
    assert delta_skipped.is_empty
    assert llm.calls == 0

    # Confident pass runs extraction, retains ADR-0023 scope, and resolves modal_prior
    gate_on = _ScriptedDecisionEngine(
        noul_result=DecisionNoulResult(probability=0.92, empirical_accuracy=0.94, passed=True)
    )
    delta_ok = await LLMTheoryGuidedPremiseRecoverer(
        llm=llm,
        decision_engine=gate_on,
        modal_resolver=_ModalStub(),
        config=cfg,
    ).recover_premises(deficit, state, context=_make_context())
    assert llm.calls == 1
    assert len(delta_ok.theory_atoms) == 1
    atom = delta_ok.theory_atoms[0]
    assert atom.scope_type == "Essentieller Allsatz"
    assert atom.epistemic_status == "Synthetisch"
    assert atom.intensional_mode == "attributed"
    assert atom.attributed_to == "Hume"
    assert atom.modal_prior == pytest.approx(0.62)


# ---------------------------------------------------------------------------
# 4. Split Parent Retirement, Mention Updates, & Pass-Aware DAG Lineage
# ---------------------------------------------------------------------------


def test_split_parent_retirement_mentions_and_pass_aware_dag_acyclicity() -> None:
    """Full concept split retires parent entity/mentions and keeps multi-pass DAG acyclic."""
    chunk_1 = L1Chunk(id="c1", text="Physics context.", source_doc_id="d1", sequence_index=0, token_count=3)
    chunk_2 = L1Chunk(id="c2", text="Ethics context.", source_doc_id="d2", sequence_index=0, token_count=3)
    ent_parent = L2Entity(id="ent_hub", label="Concept", name="Law", source_chunk_ids=["c1", "c2"])
    m1 = build_entity_mention_artifact(ent_parent, "c1", run_id="r1", phase_name="P2", method="ner")
    m2 = build_entity_mention_artifact(ent_parent, "c2", run_id="r1", phase_name="P2", method="ner")
    ent_env = build_linked_entity_artifact(
        ent_parent, [m1.artifact_id, m2.artifact_id], run_id="r1", phase_name="P2", method="ner"
    )
    atom_1 = TheoryAtom(id="a1", text="Physical claim", component_type="TheoreticalHypothesis", source_chunk_id="c1", entity_ids=["ent_hub"])
    atom_env = build_argument_component_artifact(atom_1, run_id="r1", phase_name="P4", method="acc")

    base = ArtifactCollection(
        [
            build_chunk_artifact(chunk_1, run_id="r1", phase_name="P1", method="c"),
            build_chunk_artifact(chunk_2, run_id="r1", phase_name="P1", method="c"),
            m1,
            m2,
            ent_env,
            atom_env,
        ]
    )
    deficit = EpistemicDeficit(
        deficit_id="polysemy::ent_hub",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
        target_entity_ids=["ent_hub"],
        target_chunk_ids=["c1", "c2"],
        target_atom_ids=["a1"],
        refinement_pass=0,
    )
    def_env, _ = build_deficit_envelope(
        deficit, base, run_id="r1", phase_name="Refine (Pass 1)", detector_method="Det", pass_idx=1
    )

    s1 = L2Entity(id="ent_hub__sense_1", label="Concept", name="Law (Physics)", source_chunk_ids=["c1"])
    s2 = L2Entity(id="ent_hub__sense_2", label="Concept", name="Law (Ethics)", source_chunk_ids=["c2"])
    delta = RefinementDelta(
        entities=[s1, s2],
        theory_atoms=[atom_1.model_copy(update={"entity_ids": ["ent_hub__sense_1"]})],
        cannot_link_pairs=[("ent_hub", "ent_hub__sense_1"), ("ent_hub__sense_1", "ent_hub__sense_2")],
        retired_entity_ids=["ent_hub"],
        split_entity_parents={"ent_hub__sense_1": "ent_hub", "ent_hub__sense_2": "ent_hub"},
        resolved_deficit_ids=[deficit.deficit_id],
        refinement_pass=1,
    )
    delta_envs = build_delta_envelopes(
        delta,
        deficit=deficit,
        deficit_artifact_id=def_env.artifact_id,
        collection=base,
        run_id="r1",
        phase_name="Refine (Pass 1)",
        method_name="ConceptionConceptSplitter",
        pass_idx=1,
    )
    updated = overlay_collection(base, {e.artifact_id: e for e in [def_env, *delta_envs]})

    # Retired parent & stale mentions are excluded from active view while history persists
    view = Phase4ArtifactsView.from_collection(updated)
    assert {e.id for e in view.entities} == {"ent_hub__sense_1", "ent_hub__sense_2"}
    retired_payloads = [
        e.payload
        for e in updated.of_kind(ArtifactKind.LINKED_ENTITY, latest_only=True)
        if isinstance(e.payload, LinkedEntityArtifact) and e.payload.is_retired
    ]
    assert [p.entity_id for p in retired_payloads] == ["ent_hub"]
    assert all(
        e.payload.is_retired
        for e in updated.of_kind(ArtifactKind.ENTITY_MENTION, latest_only=True)
        if isinstance(e.payload, EntityMentionArtifact) and e.payload.entity_id == "ent_hub"
    )

    # Full history including pass-0 deficit -> pass-1 atom remains acyclic WITH intact upstream lineage
    dag = ArtifactDependencyGraph.from_artifacts(updated.history)
    order = dag.topsort()
    assert order.index(def_env.identity_key) < order.index("argument_component::a1")
    assert def_env.identity_key in dag.upstream["argument_component::a1"]


# ---------------------------------------------------------------------------
# 5. Localized Component Slicing & Intra-Pass Coherence
# ---------------------------------------------------------------------------


def test_slice_phase4_component_view_preserves_connected_component_and_excludes_unrelated() -> None:
    """Connected-component slicing isolates affected D-QBAF subnet cleanly."""
    a1 = TheoryAtom(id="a1", text="A1", component_type="ObservationUnit", source_chunk_id="c1")
    a2 = TheoryAtom(id="a2", text="A2", component_type="TheoreticalHypothesis", source_chunk_id="c1")
    b1 = TheoryAtom(id="b1", text="Unrelated", component_type="TheoreticalHypothesis", source_chunk_id="c2")
    rel_a = TheoryRelation(id="r_a", source_id="a1", target_id="a2", relation_type="SUPPORTS_ARG", confidence=0.9, scope="local")
    rel_b = TheoryRelation(id="r_b", source_id="b1", target_id="b1", relation_type="SUPPORTS_ARG", confidence=0.9, scope="local")
    view = Phase4ArtifactsView(
        theory_atoms=[a1, a2, b1],
        theory_relations=[rel_a, rel_b],
        canonical_theory_atoms=[a1, a2, b1],
        canonical_theory_relations=[rel_a, rel_b],
    )
    sliced = slice_phase4_component_view(view, {"a2"})
    assert {a.id for a in sliced.theory_atoms} == {"a1", "a2"}
    assert [r.id for r in sliced.theory_relations] == ["r_a"]


# ---------------------------------------------------------------------------
# 6. Composition Root & Shared Strategy Enforcement
# ---------------------------------------------------------------------------


def test_pipeline_factory_shares_decision_engine_strategies_and_validates_projector() -> None:
    """PipelineFactory shares CascadingARCClassifier, EntityLinker, NER, ModalResolver, and TheoryProjector."""
    cfg = PipelineConfig(
        refinement=HermeneuticRefinementConfig(max_refinement_cycles=1),
    )
    llm = AsyncMock()
    llm.fingerprint = lambda: {"class": "LLMStub"}
    engine = _ScriptedDecisionEngine()

    components = PipelineFactory.resolve_components(
        config=cfg,
        llm=llm,
        relation_reranker=_RerankerStub(),
        embedding_model=_EmbedderStub(),
        decision_engine=engine,
    )
    coord = components.refinement_coordinator
    assert isinstance(coord, ClosedLoopRefinementCoordinator)
    assert isinstance(components.entity_linker, CascadingEntityLinker)
    assert isinstance(components.arc_classifier, CascadingARCClassifier)
    assert isinstance(coord.premise_recoverer, LLMTheoryGuidedPremiseRecoverer)
    assert coord.premise_recoverer.arc_classifier is components.arc_classifier
    assert coord.premise_recoverer.entity_linker is components.entity_linker
    assert isinstance(coord.premise_recoverer.decision_engine, ObservableDecisionEngine)
    assert coord.premise_recoverer.decision_engine.inner is engine
    assert coord.premise_recoverer.modal_resolver is components.modal_resolver
    assert isinstance(coord.concept_splitter, ConceptionConceptSplitter)
    assert isinstance(coord.concept_splitter.decision_engine, ObservableDecisionEngine)
    assert coord.concept_splitter.decision_engine.inner is engine
    assert isinstance(coord.axiom_grounder, TheoryGuidedAxiomGrounder)
    assert isinstance(coord.axiom_grounder.decision_engine, ObservableDecisionEngine)
    assert coord.axiom_grounder.decision_engine.inner is engine
    assert coord.axiom_grounder.entity_linker is components.entity_linker
    assert isinstance(coord.axiom_grounder.theory_projector, TheoryProjector)
    assert not isinstance(coord.axiom_grounder.theory_projector, TheoryNetProjector)

    with pytest.raises(TypeError, match="TheoryProjector"):
        TheoryGuidedAxiomGrounder(theory_projector=TheoryNetProjector())


# ---------------------------------------------------------------------------
# 7. Extended Zero-Reflection AST & Docstring Audit
# ---------------------------------------------------------------------------


def test_refactored_modules_zero_reflection_and_docstrings() -> None:
    """All refactored and newly created modules avoid getattr/hasattr and include docstrings."""
    audited = [
        PACKAGE_ROOT / "refinement" / "_shared.py",
        PACKAGE_ROOT / "refinement" / "_detector_analysis.py",
        PACKAGE_ROOT / "refinement" / "_sub_detectors.py",
        PACKAGE_ROOT / "refinement" / "detector.py",
        PACKAGE_ROOT / "refinement" / "concept_splitter.py",
        PACKAGE_ROOT / "refinement" / "premise_recovery.py",
        PACKAGE_ROOT / "refinement" / "axiom_grounder.py",
        PACKAGE_ROOT / "refinement" / "coordinator.py",
        PACKAGE_ROOT / "artifacts" / "refinement_overlay.py",
        PACKAGE_ROOT / "utils" / "identifiers.py",
    ]
    for path in audited:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert ast.get_docstring(tree), f"Missing module docstring: {path}"
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"getattr", "hasattr"}, (
                    f"Forbidden {node.func.id} in {path}:{node.lineno}"
                )
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                assert ast.get_docstring(node), f"Missing docstring on {path.name}:{node.name}"
