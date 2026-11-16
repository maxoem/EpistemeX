"""Deterministic tests for ISSUE-053 Step 3a refinement handlers and ARC pair fixes.

Covers:
1. ``TAGARCClassifier.classify_pairs`` argument-order fix and compatibility with
   ``ArtifactSubgraphReader``.
2. ``JevARCClassifier.classify_pairs`` and ``CascadingARCClassifier.classify_pairs``
   adhering to Pattern 4 (``TriageDecision`` and per-item System 1 -> System 2
   escalation without whole-corpus re-execution).
3. ``LLMTheoryGuidedPremiseRecoverer`` localized ``ENTHYMEME_GAP`` recovery conditioned
   on ``theory_lens`` and scoped strictly to target chunks + delta ARC pairing.
4. ``ConceptionConceptSplitter`` localized ``POLYSEMY_COLLISION`` splitting via
   ``EntityConception``s, ``ConceptionClusterer``, deterministic conflict partitioning,
   ``cannot_link_pairs`` generation, and chunk-scoped triple/atom rewiring.
5. ``TheoryGuidedAxiomGrounder`` localized ``UNGROUNDED_AXIOM`` recovery across
   neighbor-window / vector-matched chunks with ``PromptContextual`` NER anchoring,
   LLM measurements, and ``TheoryProjector`` parameter projection.
6. ``Fingerprintable`` discovery, domain event emission, and static AST audit
   verifying zero ``getattr``/``hasattr`` across all added/modified files.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_chunk_artifact,
    build_document_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicDeficitArtifactsView,
    EpistemicStateView,
)
from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import (
    EntityConception,
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import (
    EpistemicCurationLedger,
    PipelineInput,
)
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.events import use_event_emitter
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import (
    ComponentCompleted,
    ComponentStarted,
    EntityProcessed,
)
from episteme_pipeline.phases.phase4_argument_mining.arc_classifier import (
    TAGARCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
    CascadingARCClassifier,
    JevARCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.models import ARCRelationOutput
from episteme_pipeline.phases.phase4_entity_maturation import ConceptionClusterer
from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
    GenericTheoryProjector,
)
from episteme_pipeline.protocols.argument_mining import ARCClassifier
from episteme_pipeline.protocols.decision import DecisionScore
from episteme_pipeline.protocols.extractors import (
    GlobalRelationExtractor,
    NERExtractor,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable, find_components
from episteme_pipeline.protocols.prompts import PromptContextual
from episteme_pipeline.protocols.refinement import (
    LocalizedAxiomGrounder,
    TargetedConceptSplitter,
    TheoryGuidedPremiseRecoverer,
)
from episteme_pipeline.refinement.axiom_grounder import (
    AxiomGroundingOutput,
    RecoveredGroundingEntity,
    RecoveredMeasurement,
    RecoveredObservationAtom,
    TheoryGuidedAxiomGrounder,
)
from episteme_pipeline.refinement.concept_splitter import ConceptionConceptSplitter
from episteme_pipeline.refinement.premise_recovery import (
    LLMTheoryGuidedPremiseRecoverer,
    PremiseRecoveryOutput,
    RecoveredImplicitPremise,
)
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig


class _RecordingEmitter:
    """Minimal in-memory EventEmitter capturing emitted domain events."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def emit(self, event: Any) -> None:
        self.events.append(event)

    def register_observer(self, observer: Any) -> None:
        return None

    def unregister_observer(self, observer: Any) -> None:
        return None

    def flush(self) -> None:
        return None

    def get_observer_telemetry(self) -> dict[str, Any]:
        return {"events_delivered": len(self.events), "observer_errors": {}}


assert isinstance(_RecordingEmitter(), EventEmitter)


class _StubStructuredLLM:
    """Deterministic StructuredLLM stub recording prompt arguments and returning scripted payloads."""

    def __init__(self, responses: list[Any] | Any) -> None:
        self._responses = list(responses) if isinstance(responses, list) else [responses]
        self.calls: list[dict[str, Any]] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubStructuredLLM", "count": len(self._responses)}

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        self.calls.append(
            {
                "output_cls": output_cls,
                "prompt_bundle": prompt_bundle,
                "strategy": strategy,
                "prompt_args": dict(prompt_args),
            }
        )
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[idx]

    async def predict_text(self, *args: Any, **kwargs: Any) -> str:
        return ""


class _StubARCClassifier:
    """Minimal Fingerprintable + ARCClassifier stub delegating classify_pairs to an AsyncMock."""

    def __init__(self, return_value: list[TheoryRelation] | None = None) -> None:
        self.classify_pairs = AsyncMock(return_value=return_value or [])

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubARCClassifier"}


class _StubGlobalExtractor:
    """Minimal Fingerprintable + GlobalRelationExtractor stub delegating extract_pairs."""

    def __init__(self, triples: list[L2Triple] | None = None) -> None:
        self.extract_pairs = AsyncMock(return_value=(triples or [], []))

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubGlobalExtractor"}


def _make_context(run_id: str = "run-053-handlers") -> ArtifactExecutionContext:
    """Construct a minimal deterministic ArtifactExecutionContext."""
    return ArtifactExecutionContext(
        run_id=run_id,
        manifest=RunManifest(run_id=run_id),
        pipeline_input=PipelineInput(source_paths=[]),
    )


# ---------------------------------------------------------------------------
# 1. ARCClassifier classify_pairs fixes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tag_arc_classifier_classify_pairs_with_artifact_subgraph_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify TAGARCClassifier.classify_pairs passes args cleanly and reads ArtifactSubgraphReader."""
    monkeypatch.chdir(tmp_path)
    stub_llm = _StubStructuredLLM(
        ARCRelationOutput(
            relation_type="SUPPORTS_ARG",
            confidence=0.91,
            weight=0.88,
            direction="A_to_B",
            reasoning="Empirical observation supports the theoretical hypothesis.",
        )
    )
    classifier = TAGARCClassifier(llm=stub_llm, subgraph_depth=1, confidence_threshold=0.65)

    ent_a = L2Entity(
        id="ent_obs",
        label="Concept",
        name="Sensory Manifold",
        source_chunk_ids=["c1"],
    )
    ent_b = L2Entity(
        id="ent_hyp",
        label="Concept",
        name="A Priori Space",
        source_chunk_ids=["c2"],
    )
    triple = L2Triple(
        subject_id="ent_obs",
        predicate="IMPLIES",
        object_id="ent_hyp",
        confidence=0.9,
        scope="global",
        source_chunk_id="c1",
    )
    atom_a = TheoryAtom(
        id="atom_obs",
        text="Spatial measurements exhibit invariant Euclidean geometry.",
        component_type="ObservationUnit",
        source_chunk_id="c1",
        entity_ids=["ent_obs"],
    )
    atom_b = TheoryAtom(
        id="atom_hyp",
        text="Space is an a priori form of outer intuition.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        entity_ids=["ent_hyp"],
    )

    reader = ArtifactSubgraphReader(
        entities=[ent_a, ent_b],
        triples=[triple],
        theory_atoms=[atom_a, atom_b],
    )

    relations = await classifier.classify_pairs(
        pairs=[(atom_a, atom_b)],
        graph_store=reader,
        schema=DEFAULT_SCHEMA,
        global_extractor=None,
    )

    assert len(relations) == 1
    rel = relations[0]
    assert rel.source_id == "atom_obs"
    assert rel.target_id == "atom_hyp"
    assert rel.relation_type == "SUPPORTS_ARG"
    assert rel.confidence == pytest.approx(0.91)
    assert len(stub_llm.calls) == 1
    envelope_json = json.loads(stub_llm.calls[0]["prompt_args"]["subgraph_envelope"])
    assert any(node["id"] == "ent_obs" for node in envelope_json["nodes"])
    assert any(edge["predicate"] == "IMPLIES" for edge in envelope_json["edges"])


@pytest.mark.asyncio
async def test_jev_and_cascading_arc_classify_pairs_per_item_escalation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify JevARCClassifier & CascadingARCClassifier.classify_pairs escalate strictly per item."""
    monkeypatch.chdir(tmp_path)
    atom_fast_src = TheoryAtom(
        id="fast_src",
        text="Premise confirming causal law.",
        component_type="EmpiricalStatement",
        source_chunk_id="c1",
    )
    atom_fast_tgt = TheoryAtom(
        id="fast_tgt",
        text="Causal law holds uniformly.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
    )
    atom_amb_src = TheoryAtom(
        id="amb_src",
        text="Ambiguous counterexample in boundary conditions.",
        component_type="EmpiricalStatement",
        source_chunk_id="c3",
    )
    atom_amb_tgt = TheoryAtom(
        id="amb_tgt",
        text="Boundary theory requires modification.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c4",
    )
    unrelated_atom = TheoryAtom(
        id="unrelated_corpus_atom",
        text="Unrelated text that must never be paired.",
        component_type="ObservationUnit",
        source_chunk_id="c99",
    )

    engine = MockJevDecisionEngine(default_confidence_threshold=0.70)
    engine.register_choice_response(
        question_pattern="dialectical relation",
        state_pattern="premise confirming causal law",
        selected_option="SUPPORTS_ARG",
        class_probability=0.95,
        empirical_accuracy=0.93,
        prediction_set=["SUPPORTS_ARG"],
    )
    engine.register_choice_response(
        question_pattern="dialectical relation",
        state_pattern="ambiguous counterexample",
        selected_option="ATTACKS",
        class_probability=0.60,
        empirical_accuracy=0.58,
        prediction_set=["ATTACKS", "NEUTRAL"],
    )

    fast_arc = JevARCClassifier(engine, confidence_threshold=0.70)
    reader = ArtifactSubgraphReader(
        theory_atoms=[
            atom_fast_src,
            atom_fast_tgt,
            atom_amb_src,
            atom_amb_tgt,
            unrelated_atom,
        ]
    )

    # 1. Standalone JevARCClassifier.classify_pairs evaluates only targeted pairs
    jev_rels = await fast_arc.classify_pairs(
        pairs=[(atom_fast_src, atom_fast_tgt), (atom_amb_src, atom_amb_tgt)],
        graph_store=reader,
        schema=DEFAULT_SCHEMA,
    )
    assert len(jev_rels) == 1
    assert jev_rels[0].source_id == "fast_src"
    assert jev_rels[0].target_id == "fast_tgt"
    assert jev_rels[0].relation_type == "SUPPORTS_ARG"
    assert len(engine.calls) == 2

    # 2. CascadingARCClassifier.classify_pairs escalates ONLY the ambiguous pair to System 2
    llm_arc = _StubStructuredLLM(
        ARCRelationOutput(
            relation_type="ATTACKS",
            confidence=0.89,
            weight=0.85,
            direction="A_to_B",
            reasoning="Ambiguous counterexample attacks the boundary hypothesis.",
        )
    )
    tag_arc = TAGARCClassifier(llm=llm_arc, confidence_threshold=0.65)
    cascade = CascadingARCClassifier(
        fast_classifier=fast_arc,
        llm_classifier=tag_arc,
        config=Phase4Config(stochastic_audit_rate=0.0),
    )

    assert isinstance(fast_arc, Fingerprintable)
    assert isinstance(cascade, Fingerprintable)
    assert cascade.fingerprint()["class"] == "CascadingARCClassifier"

    merged_rels = await cascade.classify_pairs(
        pairs=[(atom_fast_src, atom_fast_tgt), (atom_amb_src, atom_amb_tgt)],
        graph_store=reader,
        schema=DEFAULT_SCHEMA,
    )

    assert len(llm_arc.calls) == 1
    assert llm_arc.calls[0]["prompt_args"]["component_a_id"] == "amb_src"
    assert llm_arc.calls[0]["prompt_args"]["component_b_id"] == "amb_tgt"
    by_src = {r.source_id: r for r in merged_rels}
    assert set(by_src.keys()) == {"fast_src", "amb_src"}
    assert by_src["fast_src"].relation_type == "SUPPORTS_ARG"
    assert by_src["amb_src"].relation_type == "ATTACKS"


@pytest.mark.asyncio
async def test_cascading_arc_classify_pairs_generic_arc_fallback_and_audit() -> None:
    """Verify CascadingARCClassifier handles non-triage ARCClassifier fast stubs cleanly."""
    a1 = TheoryAtom(id="a1", text="P1", component_type="EmpiricalStatement", source_chunk_id="c1")
    a2 = TheoryAtom(id="a2", text="C1", component_type="TheoreticalHypothesis", source_chunk_id="c2")
    b1 = TheoryAtom(id="b1", text="P2", component_type="EmpiricalStatement", source_chunk_id="c3")
    b2 = TheoryAtom(id="b2", text="C2", component_type="TheoreticalHypothesis", source_chunk_id="c4")

    fast_rel = TheoryRelation(
        source_id="a1",
        target_id="a2",
        relation_type="SUPPORTS_ARG",
        confidence=0.94,
        scope="global",
    )
    fast_stub = MagicMock(spec=ARCClassifier)
    fast_stub.classify_pairs = AsyncMock(return_value=[fast_rel])

    llm_rel = TheoryRelation(
        source_id="b1",
        target_id="b2",
        relation_type="ATTACKS",
        confidence=0.87,
        scope="global",
    )
    llm_stub = MagicMock(spec=ARCClassifier)
    llm_stub.classify_pairs = AsyncMock(return_value=[llm_rel])

    cascade = CascadingARCClassifier(
        fast_classifier=fast_stub,
        llm_classifier=llm_stub,
        stochastic_audit_rate=0.0,
    )
    out = await cascade.classify_pairs(
        pairs=[(a1, a2), (b1, b2)],
        graph_store=ArtifactSubgraphReader(),
        schema=DEFAULT_SCHEMA,
    )

    assert len(out) == 2
    llm_stub.classify_pairs.assert_awaited_once()
    assert llm_stub.classify_pairs.call_args.kwargs["pairs"] == [(b1, b2)]


# ---------------------------------------------------------------------------
# 2. LLMTheoryGuidedPremiseRecoverer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_premise_recoverer_scoped_to_target_chunks_with_theory_lens_and_arc() -> None:
    """Verify LLMTheoryGuidedPremiseRecoverer recovers implicit premises strictly in target chunks."""
    chunk_target = L1Chunk(
        id="chunk_target",
        text=(
            "Because Euclidean axioms hold necessarily and experience cannot yield necessity, "
            "space must be a pure a priori form of outer intuition."
        ),
        source_doc_id="doc_kant",
        sequence_index=0,
        token_count=22,
    )
    chunk_unrelated = L1Chunk(
        id="chunk_unrelated",
        text="This completely unrelated appendix discusses empirical botany.",
        source_doc_id="doc_other",
        sequence_index=0,
        token_count=8,
    )
    ent_space = L2Entity(
        id="ent_space",
        label="Concept",
        name="Space",
        source_chunk_ids=["chunk_target"],
    )
    target_claim = TheoryAtom(
        id="atom_claim",
        text="Space must be a pure a priori form of outer intuition.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_target",
        entity_ids=["ent_space"],
    )
    neighbor_atom = TheoryAtom(
        id="atom_neighbor",
        text="Geometry requires universal and apodictic synthetic propositions.",
        component_type="CoreExpansion",
        source_chunk_id="chunk_other",
    )
    unrelated_atom = TheoryAtom(
        id="atom_unrelated",
        text="Botanical taxonomies classify leaf shapes.",
        component_type="ObservationUnit",
        source_chunk_id="chunk_unrelated",
    )
    rel_neighbor = TheoryRelation(
        source_id="atom_claim",
        target_id="atom_neighbor",
        relation_type="ENTAILS",
        confidence=0.85,
        scope="global",
    )

    collection = ArtifactCollection(
        [
            build_chunk_artifact(chunk_target, run_id="r1", phase_name="P1", method="m"),
            build_chunk_artifact(chunk_unrelated, run_id="r1", phase_name="P1", method="m"),
            build_linked_entity_artifact(
                ent_space, ["artifact::mention::ent_space::chunk_target"], run_id="r1", phase_name="P2", method="m"
            ),
            build_argument_component_artifact(target_claim, run_id="r1", phase_name="P4", method="m"),
            build_argument_component_artifact(neighbor_atom, run_id="r1", phase_name="P4", method="m"),
            build_argument_component_artifact(unrelated_atom, run_id="r1", phase_name="P4", method="m"),
            build_argument_relation_artifact(rel_neighbor, run_id="r1", phase_name="P4", method="m"),
        ]
    )
    state = EpistemicDeficitArtifactsView.from_collection(collection)

    llm_stub = _StubStructuredLLM(
        PremiseRecoveryOutput(
            recovered_premises=[
                RecoveredImplicitPremise(
                    local_id="P1",
                    text="Sensory experience alone cannot ground apodictic necessity of Space.",
                    component_type="EmpiricalStatement",
                    source_chunk_id="chunk_unrelated",  # Should be clamped back to chunk_target!
                    target_atom_id="atom_claim",
                    relation_type="SUPPORTS_ARG",
                    confidence=0.90,
                    weight=0.88,
                )
            ]
        )
    )
    arc_mock = _StubARCClassifier(return_value=[])

    recoverer = LLMTheoryGuidedPremiseRecoverer(
        llm=llm_stub,
        arc_classifier=arc_mock,
        schema=DEFAULT_SCHEMA,
    )
    assert isinstance(recoverer, TheoryGuidedPremiseRecoverer)
    assert isinstance(recoverer, Fingerprintable)
    assert set(find_components(recoverer).keys()) >= {"llm", "arc_classifier"}

    deficit = EpistemicDeficit(
        deficit_id="def-enthymeme-1",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        severity=0.88,
        target_chunk_ids=["chunk_target"],
        target_atom_ids=["atom_claim"],
        theory_id="transcendental_aesthetic",
        theory_lens={"M_p": ["a_priori_intuition"], "required_dimensions": ["apodictic_necessity"]},
        rationale="Major claim has high PageRank centrality and zero incoming supports.",
        refinement_pass=0,
    )

    emitter = _RecordingEmitter()
    with use_event_emitter(emitter):
        delta = await recoverer.recover_premises(deficit, state, context=_make_context())

    assert isinstance(delta, RefinementDelta)
    assert delta.refinement_pass == 1
    assert delta.resolved_deficit_ids == ["def-enthymeme-1"]
    assert len(delta.theory_atoms) == 1
    recovered_atom = delta.theory_atoms[0]
    assert recovered_atom.source_chunk_id == "chunk_target"
    assert "ent_space" in recovered_atom.entity_ids
    assert len(delta.theory_relations) == 1
    assert delta.theory_relations[0].source_id == recovered_atom.id
    assert delta.theory_relations[0].target_id == "atom_claim"
    assert delta.theory_relations[0].relation_type == "SUPPORTS_ARG"
    assert delta.theory_relations[0].scope == "local"

    # Prompt inspected ONLY chunk_target, never chunk_unrelated
    prompt_args = llm_stub.calls[0]["prompt_args"]
    assert "chunk_target" in prompt_args["source_chunks"]
    assert "botany" not in prompt_args["source_chunks"]
    assert "a_priori_intuition" in prompt_args["theory_lens"]

    # ARC classifier ran strictly on (recovered_atom, target_claim) and (recovered_atom, neighbor_atom)
    arc_pairs = arc_mock.classify_pairs.call_args.args[0]
    pair_target_ids = {pair[1].id for pair in arc_pairs}
    assert pair_target_ids == {"atom_claim", "atom_neighbor"}
    assert "atom_unrelated" not in pair_target_ids

    assert any(isinstance(ev, ComponentStarted) for ev in emitter.events)
    assert any(isinstance(ev, ComponentCompleted) and ev.success for ev in emitter.events)


@pytest.mark.asyncio
async def test_premise_recoverer_validation_guards() -> None:
    """Verify LLMTheoryGuidedPremiseRecoverer rejects mismatched kinds and missing LLM."""
    recoverer_no_llm = LLMTheoryGuidedPremiseRecoverer(llm=None)
    state = EpistemicStateView()
    wrong_deficit = EpistemicDeficit(
        deficit_id="d-wrong",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
    )
    with pytest.raises(ValueError, match="ENTHYMEME_GAP"):
        await recoverer_no_llm.recover_premises(wrong_deficit, state)

    right_deficit = EpistemicDeficit(
        deficit_id="d-ent",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
    )
    with pytest.raises(ValueError, match="StructuredLLM"):
        await recoverer_no_llm.recover_premises(right_deficit, state)


# ---------------------------------------------------------------------------
# 3. ConceptionConceptSplitter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concept_splitter_conceptions_rewires_only_affected_chunks_and_emits_cannot_link() -> None:
    """Verify ConceptionConceptSplitter splits hub conceptions and leaves unaffected subgraphs untouched."""
    doc_kant = L1Document(
        id="doc_kant",
        title="Critique of Pure Reason",
        source_path="/tmp/kant.txt",
        chapter_count=1,
        chunk_count=1,
    )
    doc_leibniz = L1Document(
        id="doc_leibniz",
        title="Leibniz Correspondence",
        source_path="/tmp/leibniz.txt",
        chapter_count=1,
        chunk_count=1,
    )
    c_kant = L1Chunk(
        id="ck_1",
        text="Space is a pure form of sensible intuition a priori.",
        source_doc_id="doc_kant",
        sequence_index=0,
        token_count=10,
    )
    c_leibniz = L1Chunk(
        id="cl_1",
        text="Space is a relational order of coexistences among monads.",
        source_doc_id="doc_leibniz",
        sequence_index=0,
        token_count=10,
    )
    c_unaffected = L1Chunk(
        id="cu_1",
        text="Geometry studies axioms of triangular figures.",
        source_doc_id="doc_kant",
        sequence_index=1,
        token_count=7,
    )

    hub_space = L2Entity(
        id="ent_space",
        label="Concept",
        name="Space",
        description="Conflated hub concept.",
        source_chunk_ids=["ck_1", "cl_1"],
        is_mature=True,
        polysemy_variance=0.45,
        conceptions=[
            EntityConception(
                id="ent_space::conception::kant",
                entity_id="ent_space",
                perspective="transcendental_idealism",
                description="Pure a priori form of outer sensible intuition.",
                representative_envelopes=["Space is a pure form of sensible intuition a priori."],
                source_chunk_ids=["ck_1"],
                centroid_dispersion=0.05,
                confidence=0.95,
            ),
            EntityConception(
                id="ent_space::conception::leibniz",
                entity_id="ent_space",
                perspective="relationalism",
                description="Relational order of coexistences among monads.",
                representative_envelopes=["Space is a relational order of coexistences among monads."],
                source_chunk_ids=["cl_1"],
                centroid_dispersion=0.04,
                confidence=0.96,
            ),
        ],
    )
    ent_intuition = L2Entity(
        id="ent_intuition",
        label="Concept",
        name="Intuition",
        source_chunk_ids=["ck_1"],
    )
    ent_monads = L2Entity(
        id="ent_monads",
        label="Concept",
        name="Monads",
        source_chunk_ids=["cl_1"],
    )
    ent_geometry = L2Entity(
        id="ent_geometry",
        label="Concept",
        name="Geometry",
        source_chunk_ids=["cu_1"],
    )

    triple_kant = L2Triple(
        subject_id="ent_space",
        predicate="INSTANCE_OF",
        object_id="ent_intuition",
        confidence=0.9,
        scope="local",
        source_chunk_id="ck_1",
    )
    triple_leibniz = L2Triple(
        subject_id="ent_space",
        predicate="PART_OF",
        object_id="ent_monads",
        confidence=0.9,
        scope="local",
        source_chunk_id="cl_1",
    )
    triple_unaffected = L2Triple(
        subject_id="ent_geometry",
        predicate="RELATED_TO",
        object_id="ent_intuition",
        confidence=0.8,
        scope="local",
        source_chunk_id="cu_1",
    )

    atom_kant = TheoryAtom(
        id="atom_k",
        text="Space is an a priori intuition.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="ck_1",
        entity_ids=["ent_space", "ent_intuition"],
    )
    atom_leibniz = TheoryAtom(
        id="atom_l",
        text="Space is a relational order of monads.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="cl_1",
        entity_ids=["ent_space", "ent_monads"],
    )
    atom_unaffected = TheoryAtom(
        id="atom_u",
        text="Triangles obey Euclidean sum of angles.",
        component_type="ObservationUnit",
        source_chunk_id="cu_1",
        entity_ids=["ent_geometry"],
    )

    collection = ArtifactCollection(
        [
            build_document_artifact(doc_kant, run_id="r1", phase_name="P1", method="m"),
            build_document_artifact(doc_leibniz, run_id="r1", phase_name="P1", method="m"),
            build_chunk_artifact(c_kant, run_id="r1", phase_name="P1", method="m"),
            build_chunk_artifact(c_leibniz, run_id="r1", phase_name="P1", method="m"),
            build_chunk_artifact(c_unaffected, run_id="r1", phase_name="P1", method="m"),
            build_linked_entity_artifact(hub_space, [], run_id="r1", phase_name="P4m", method="m"),
            build_linked_entity_artifact(ent_intuition, [], run_id="r1", phase_name="P2", method="m"),
            build_linked_entity_artifact(ent_monads, [], run_id="r1", phase_name="P2", method="m"),
            build_linked_entity_artifact(ent_geometry, [], run_id="r1", phase_name="P2", method="m"),
            build_local_relation_artifact(triple_kant, run_id="r1", phase_name="P2", method="m"),
            build_local_relation_artifact(triple_leibniz, run_id="r1", phase_name="P2", method="m"),
            build_local_relation_artifact(triple_unaffected, run_id="r1", phase_name="P2", method="m"),
            build_argument_component_artifact(atom_kant, run_id="r1", phase_name="P4", method="m"),
            build_argument_component_artifact(atom_leibniz, run_id="r1", phase_name="P4", method="m"),
            build_argument_component_artifact(atom_unaffected, run_id="r1", phase_name="P4", method="m"),
        ]
    )
    state = EpistemicDeficitArtifactsView.from_collection(collection)

    global_extractor_mock = _StubGlobalExtractor(
        triples=[
            L2Triple(
                subject_id="ent_space__sense_1",
                predicate="CONTRADICTS",
                object_id="ent_space__sense_2",
                confidence=0.88,
                scope="global",
            )
        ]
    )

    splitter = ConceptionConceptSplitter(
        conception_clusterer=ConceptionClusterer(),
        global_extractor=global_extractor_mock,
    )
    assert isinstance(splitter, TargetedConceptSplitter)
    assert isinstance(splitter, Fingerprintable)
    assert set(find_components(splitter).keys()) >= {
        "conception_clusterer",
        "global_extractor",
    }

    deficit = EpistemicDeficit(
        deficit_id="def-polysemy-1",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
        severity=0.92,
        target_entity_ids=["ent_space"],
        target_chunk_ids=["ck_1", "cl_1"],
        target_atom_ids=["atom_k", "atom_l"],
        rationale="Hub concept Space bridges conflicting Kantian and Leibnizian subgraphs.",
        refinement_pass=0,
    )

    emitter = _RecordingEmitter()
    with use_event_emitter(emitter):
        delta = await splitter.split_concept(deficit, state, context=_make_context())

    assert delta.refinement_pass == 1
    assert delta.resolved_deficit_ids == ["def-polysemy-1"]

    split_by_id = {e.id: e for e in delta.entities}
    assert set(split_by_id.keys()) == {"ent_space__sense_1", "ent_space__sense_2"}
    assert split_by_id["ent_space__sense_1"].source_chunk_ids == ["ck_1"]
    assert split_by_id["ent_space__sense_2"].source_chunk_ids == ["cl_1"]
    assert split_by_id["ent_space__sense_1"].name != split_by_id["ent_space__sense_2"].name

    # Cannot-link pairs block re-merging in EpistemicCurationLedger
    ledger = EpistemicCurationLedger(cannot_link_entities=set(delta.cannot_link_pairs))
    assert ledger.is_cannot_link("ent_space__sense_1", "ent_space__sense_2")
    assert ledger.is_cannot_link("ent_space", "ent_space__sense_1")
    assert ledger.is_cannot_link("ent_space", "ent_space__sense_2")

    # Only local triples in ck_1 and cl_1 were rewritten; cu_1 triple was untouched!
    assert len(delta.local_triples) == 2
    rewritten_by_chunk = {t.source_chunk_id: t for t in delta.local_triples}
    assert rewritten_by_chunk["ck_1"].subject_id == "ent_space__sense_1"
    assert rewritten_by_chunk["cl_1"].subject_id == "ent_space__sense_2"
    assert "cu_1" not in rewritten_by_chunk

    # Only TheoryAtoms in ck_1 and cl_1 were rewritten; atom_u was untouched!
    rewritten_atoms = {a.id: a for a in delta.theory_atoms}
    assert set(rewritten_atoms.keys()) == {"atom_k", "atom_l"}
    assert rewritten_atoms["atom_k"].entity_ids == ["ent_space__sense_1", "ent_intuition"]
    assert rewritten_atoms["atom_l"].entity_ids == ["ent_space__sense_2", "ent_monads"]

    # GlobalRelationExtractor ran strictly on pairs involving split senses (not ent_geometry!)
    called_pairs = global_extractor_mock.extract_pairs.call_args.args[0]
    involved_ids = {
        eid for pair in called_pairs for eid in (pair.entity_a.id, pair.entity_b.id)
    }
    assert "ent_space__sense_1" in involved_ids
    assert "ent_space__sense_2" in involved_ids
    assert "ent_geometry" not in involved_ids
    assert len(delta.global_triples) == 1
    assert delta.global_triples[0].predicate == "CONTRADICTS"

    assert any(isinstance(ev, EntityProcessed) for ev in emitter.events)
    assert any(isinstance(ev, ComponentCompleted) and ev.success for ev in emitter.events)


@pytest.mark.asyncio
async def test_concept_splitter_deterministic_partition_without_preexisting_conceptions() -> None:
    """Verify ConceptionConceptSplitter splits entities lacking pre-stratified conceptions."""
    c1 = L1Chunk(
        id="c1",
        text="Kant defines energy as dynamic force in transcendental mechanics.",
        source_doc_id="doc_1",
        sequence_index=0,
        token_count=9,
    )
    c2 = L1Chunk(
        id="c2",
        text="Aristotle defines energeia as actuality of essence.",
        source_doc_id="doc_2",
        sequence_index=0,
        token_count=7,
    )
    hub = L2Entity(
        id="ent_energy",
        label="Concept",
        name="Energy",
        source_chunk_ids=["c1", "c2"],
        conceptions=[],
    )
    atom1 = TheoryAtom(
        id="a1",
        text="Kant treats energy dynamically.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        intensional_mode="attributed",
        attributed_to="Kant",
        entity_ids=["ent_energy"],
    )
    atom2 = TheoryAtom(
        id="a2",
        text="Aristotle treats energy teleologically.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        intensional_mode="attributed",
        attributed_to="Aristotle",
        entity_ids=["ent_energy"],
    )
    state = EpistemicStateView(
        chunks=[c1, c2],
        entities=[hub],
        theory_atoms=[atom1, atom2],
        canonical_theory_atoms=[atom1, atom2],
    )
    splitter = ConceptionConceptSplitter()
    deficit = EpistemicDeficit(
        deficit_id="def-poly-2",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
        target_entity_ids=["ent_energy"],
        target_atom_ids=["a1", "a2"],
        refinement_pass=1,
    )

    delta = await splitter.split_concept(deficit, state)
    assert len(delta.entities) == 2
    assert delta.refinement_pass == 2
    assert len(delta.cannot_link_pairs) == 3
    rewritten_atoms = {a.id: a for a in delta.theory_atoms}
    assert rewritten_atoms["a1"].entity_ids != rewritten_atoms["a2"].entity_ids


# ---------------------------------------------------------------------------
# 4. TheoryGuidedAxiomGrounder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_axiom_grounder_expands_neighbor_window_and_vector_hits_strictly() -> None:
    """Verify TheoryGuidedAxiomGrounder grounds via local neighbors + vector hits without touching unrelated docs."""
    # Same document chunks: seq 0 (neighbor), seq 1 (target), seq 3 (outside window=1)
    chunk_neighbor = L1Chunk(
        id="c_neighbor",
        text="Microdialysis recorded extracellular dopamine_depletion = 0.78 uM in prefrontal cortex.",
        source_doc_id="doc_neuro",
        sequence_index=0,
        token_count=10,
        embedding=[0.95, 0.30, 0.0],
    )
    chunk_target = L1Chunk(
        id="c_target",
        text="Prefrontal working memory deficits follow mesocortical dysregulation.",
        source_doc_id="doc_neuro",
        sequence_index=1,
        token_count=8,
        embedding=[1.0, 0.0, 0.0],
    )
    chunk_far = L1Chunk(
        id="c_far",
        text="Distant chapter summary unrelated to local measurement window.",
        source_doc_id="doc_neuro",
        sequence_index=5,
        token_count=8,
        embedding=[0.0, 0.0, 1.0],
    )
    chunk_unrelated_doc = L1Chunk(
        id="c_unrelated",
        text="Botanical classification of alpine mosses.",
        source_doc_id="doc_botany",
        sequence_index=0,
        token_count=6,
        embedding=[0.0, 1.0, 0.0],
    )
    # Related chunk in secondary empirical table via vector similarity
    chunk_vector_hit = L1Chunk(
        id="c_vec_hit",
        text="Table 2 reports synaptic_plasticity = 0.72 normalized units.",
        source_doc_id="doc_appendix",
        sequence_index=0,
        token_count=9,
        embedding=[0.92, 0.0, 0.39],
    )

    axiom_atom = TheoryAtom(
        id="atom_axiom",
        text="Mesocortical dopamine dysregulation impairs working memory.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c_target",
        local_tenability=0.25,
    )
    unrelated_atom = TheoryAtom(
        id="atom_botany",
        text="Alpine mosses prefer acidic soil.",
        component_type="ObservationUnit",
        source_chunk_id="c_unrelated",
    )

    state = EpistemicStateView(
        chunks=[
            chunk_neighbor,
            chunk_target,
            chunk_far,
            chunk_unrelated_doc,
            chunk_vector_hit,
        ],
        theory_atoms=[axiom_atom, unrelated_atom],
        canonical_theory_atoms=[axiom_atom, unrelated_atom],
    )

    ner_seen_chunks: list[str] = []
    ner_seen_anchors: list[str] = []

    class _StubNER(NERExtractor):
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "_StubNER"}

        async def extract(
            self,
            chunk_id: str,
            chunk_text: str,
            schema: SchemaConfig,
            memory: Any | None = None,
            anchor: Any | None = None,
        ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]:
            del schema, memory
            ner_seen_chunks.append(chunk_id)
            if isinstance(anchor, PromptContextual):
                ner_seen_anchors.append(anchor.to_prompt_context())
            if chunk_id == "c_neighbor":
                e1 = L2Entity(
                    id="ent_dopamine",
                    label="Concept",
                    name="Extracellular Dopamine",
                    source_chunk_ids=["c_neighbor"],
                )
                e2 = L2Entity(
                    id="ent_pfc",
                    label="Concept",
                    name="Prefrontal Cortex",
                    source_chunk_ids=["c_neighbor"],
                )
                t1 = L2Triple(
                    subject_id="ent_dopamine",
                    predicate="PART_OF",
                    object_id="ent_pfc",
                    confidence=0.91,
                    scope="local",
                    source_chunk_id="c_neighbor",
                )
                return [e1, e2], [t1], None, False, None
            return [], [], None, False, None

    llm_stub = _StubStructuredLLM(
        AxiomGroundingOutput(
            observations=[
                RecoveredObservationAtom(
                    local_id="OBS1",
                    text="Extracellular dopamine depletion measured at 0.78 uM in prefrontal cortex.",
                    component_type="ObservationUnit",
                    source_chunk_id="c_neighbor",
                    target_atom_id="atom_axiom",
                    relation_type="SUPPORTS_ARG",
                    confidence=0.92,
                    measurements=[
                        RecoveredMeasurement(
                            dimension="dopamine_depletion",
                            value=0.78,
                            unit="uM",
                        ),
                        RecoveredMeasurement(
                            dimension="synaptic_plasticity",
                            value=0.72,
                            unit="norm",
                        ),
                    ],
                )
            ],
            entities=[
                RecoveredGroundingEntity(
                    name="Working Memory Assay",
                    label="Concept",
                    description="Behavioral assay quantifying PFC performance.",
                    source_chunk_id="c_target",
                )
            ],
        )
    )

    grounder = TheoryGuidedAxiomGrounder(
        ner_extractor=_StubNER(),
        llm=llm_stub,
        theory_projector=GenericTheoryProjector(),
        neighbor_window=1,
        vector_top_k=3,
    )
    assert isinstance(grounder, LocalizedAxiomGrounder)
    assert isinstance(grounder, Fingerprintable)
    assert set(find_components(grounder).keys()) >= {
        "ner_extractor",
        "llm",
        "theory_projector",
    }

    deficit = EpistemicDeficit(
        deficit_id="def-ungrounded-1",
        deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
        severity=0.89,
        target_chunk_ids=["c_target"],
        target_atom_ids=["atom_axiom"],
        theory_id="dopamine_hypothesis",
        theory_lens={
            "name": "Dopamine Hypothesis",
            "required_dimensions": ["dopamine_depletion", "synaptic_plasticity"],
            "parameter_names": ["DopamineDepletion", "SynapticPlasticity"],
            "laws": [
                {
                    "law_id": "law_pfc",
                    "description": "Dopamine depletion tracks plasticity loss.",
                    "formula_expression": "abs(DopamineDepletion - SynapticPlasticity)",
                    "involved_parameters": ["DopamineDepletion", "SynapticPlasticity"],
                }
            ],
        },
        rationale="TS_local < 0.5 due to missing M_pp measurements.",
        refinement_pass=0,
    )

    emitter = _RecordingEmitter()
    with use_event_emitter(emitter):
        delta = await grounder.ground_axiom(deficit, state, context=_make_context())

    assert delta.refinement_pass == 1
    assert delta.resolved_deficit_ids == ["def-ungrounded-1"]

    # Strictly expanded to c_neighbor, c_target, and high-sim c_vec_hit; NEVER c_far or c_unrelated!
    assert set(ner_seen_chunks) == {"c_neighbor", "c_target", "c_vec_hit"}
    assert "c_far" not in ner_seen_chunks
    assert "c_unrelated" not in ner_seen_chunks
    assert len(ner_seen_anchors) == 3
    assert "dopamine_depletion" in ner_seen_anchors[0]

    assert len(delta.entities) == 3  # ent_dopamine, ent_pfc, Working Memory Assay
    assert len(delta.local_triples) == 1

    atoms_by_id = {a.id: a for a in delta.theory_atoms}
    assert "atom_botany" not in atoms_by_id
    obs_atoms = [a for a in delta.theory_atoms if a.id != "atom_axiom"]
    assert len(obs_atoms) == 1
    obs = obs_atoms[0]
    assert obs.component_type == "ObservationUnit"
    assert obs.source_chunk_id == "c_neighbor"
    assert len(obs.measurements) == 2
    assert obs.parameters["DopamineDepletion"] == pytest.approx(0.78)
    assert obs.parameters["SynapticPlasticity"] == pytest.approx(0.72)

    # Target axiom updated with projected parameters without altering unrelated atoms
    assert "atom_axiom" in atoms_by_id
    assert atoms_by_id["atom_axiom"].parameters["DopamineDepletion"] == pytest.approx(0.78)

    assert len(delta.theory_relations) == 1
    assert delta.theory_relations[0].source_id == obs.id
    assert delta.theory_relations[0].target_id == "atom_axiom"
    assert delta.theory_relations[0].relation_type == "SUPPORTS_ARG"
    assert delta.theory_relations[0].scope == "global"

    assert any(isinstance(ev, ComponentStarted) for ev in emitter.events)
    assert any(isinstance(ev, ComponentCompleted) and ev.success for ev in emitter.events)


@pytest.mark.asyncio
async def test_axiom_grounder_deterministic_fallback_without_llm() -> None:
    """Verify TheoryGuidedAxiomGrounder recovers deterministic measurements when llm is None."""
    c0 = L1Chunk(
        id="c0",
        text="Observed dopamine_depletion: 0.65 in assay.",
        source_doc_id="doc1",
        sequence_index=0,
        token_count=6,
    )
    c1 = L1Chunk(
        id="c1",
        text="Hypothesis claims depletion alters working memory.",
        source_doc_id="doc1",
        sequence_index=1,
        token_count=7,
    )
    axiom = TheoryAtom(
        id="ax_1",
        text="Hypothesis claims depletion alters working memory.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
    )
    state = EpistemicStateView(
        chunks=[c0, c1],
        theory_atoms=[axiom],
        canonical_theory_atoms=[axiom],
    )

    grounder = TheoryGuidedAxiomGrounder(neighbor_window=1)
    deficit = EpistemicDeficit(
        deficit_id="def-det-1",
        deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
        target_chunk_ids=["c1"],
        target_atom_ids=["ax_1"],
        theory_id="t1",
        theory_lens={
            "required_dimensions": ["dopamine_depletion"],
            "parameter_names": ["DopamineDepletion"],
        },
    )

    delta = await grounder.ground_axiom(deficit, state)
    assert delta.resolved_deficit_ids == ["def-det-1"]
    assert any(a.component_type == "ObservationUnit" and a.measurements for a in delta.theory_atoms)
    assert len(delta.theory_relations) == 1
    assert delta.theory_relations[0].target_id == "ax_1"


# ---------------------------------------------------------------------------
# 5. Static AST Guard & Docstring Standards
# ---------------------------------------------------------------------------


def test_zero_reflection_and_docstrings_in_step3a_files() -> None:
    """Verify zero getattr/hasattr and complete NumPy docstrings across Step 3a files."""
    pkg_root = Path(__file__).resolve().parent.parent / "episteme_pipeline"
    test_file = Path(__file__).resolve()

    audited_files = [
        pkg_root / "phases" / "phase4_argument_mining" / "arc_classifier.py",
        pkg_root / "phases" / "phase4_argument_mining" / "classifiers.py",
        pkg_root / "refinement" / "premise_recovery.py",
        pkg_root / "refinement" / "concept_splitter.py",
        pkg_root / "refinement" / "axiom_grounder.py",
        test_file,
    ]

    violations: list[str] = []
    for py_file in audited_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"getattr", "hasattr"}:
                    violations.append(f"{py_file.name}:{node.lineno} calls {node.func.id}")

    assert not violations, "Forbidden getattr/hasattr detected:\n" + "\n".join(violations)

    documented_symbols = [
        LLMTheoryGuidedPremiseRecoverer,
        LLMTheoryGuidedPremiseRecoverer.fingerprint,
        LLMTheoryGuidedPremiseRecoverer.recover_premises,
        ConceptionConceptSplitter,
        ConceptionConceptSplitter.fingerprint,
        ConceptionConceptSplitter.split_concept,
        TheoryGuidedAxiomGrounder,
        TheoryGuidedAxiomGrounder.fingerprint,
        TheoryGuidedAxiomGrounder.ground_axiom,
        JevARCClassifier.classify_pairs,
        JevARCClassifier.classify_pairs_with_triage,
        JevARCClassifier.classify_pair_decision,
        JevARCClassifier.fingerprint,
        CascadingARCClassifier.classify_pairs,
        CascadingARCClassifier.fingerprint,
        TAGARCClassifier.classify_pairs,
    ]
    missing_docs = [
        sym.__qualname__
        for sym in documented_symbols
        if not (sym.__doc__ and sym.__doc__.strip())
    ]
    assert not missing_docs, f"Missing docstrings on: {missing_docs}"
