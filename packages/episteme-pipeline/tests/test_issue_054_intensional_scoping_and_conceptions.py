"""Deterministic unit and integration tests for ISSUE-054.

Covers all acceptance criteria and edge cases for:
1. Layer 3 ``intensional_mode`` and ``attributed_to`` contracts, codecs,
   dependency fingerprints, Neo4j graph mappers, and ACC classifier propagation.
2. Perspective-filtered and supposition-aware D-QBAF evaluation in
   :class:`TheoryNetProjector` and :class:`QBAFGradualSemanticsSolver`.
3. Multi-modal polysemy detection and perspective-stratified conception
   maturation in :class:`Phase4EntityMaturationRunner` and
   :class:`ConceptionClusterer`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_chunk_artifact,
    build_document_artifact,
    build_entity_mention_artifact,
    build_linked_entity_artifact,
    build_theory_atom_artifact,
)
from episteme_pipeline.artifacts.codecs import LinkedEntityCodec, TheoryAtomCodec
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
    Phase5ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import Phase4EntityMaturationConfig, Phase6Config
from episteme_pipeline.contracts.domain import (
    EntityConception,
    IntensionalMode,
    L1Chunk,
    L1Document,
    L2Entity,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import use_event_emitter
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import (
    EntityConceptionStratified,
    EntityMaturationSynthesized,
)
from episteme_pipeline.graph.theory_graph_mapper import theory_atom_to_graph_properties
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.phases.phase4_argument_mining.acc_classifier import (
    LLMACCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.models import (
    ACCOutput,
    ExtractedComponent,
)
from episteme_pipeline.phases.phase4_entity_maturation import (
    ConceptionClusterer,
    EntitySynthesisOutput,
    Phase4EntityMaturationRunner,
)
from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


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


class _DeterministicMaturationLLM:
    """Deterministic structured LLM stub returning perspective-labeled descriptions."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def predict_structured(
        self,
        schema: type[Any],
        prompts: Any,
        *,
        strategy: Any = None,
        entity_name: str = "",
        envelopes: str = "",
        **kwargs: Any,
    ) -> Any:
        self.calls.append(
            {
                "entity_name": entity_name,
                "envelopes": envelopes,
                "strategy": strategy,
            }
        )
        if self.fail:
            raise RuntimeError("Simulated structured LLM failure")
        return EntitySynthesisOutput(
            description=f"Synthesized conception for {entity_name}: {envelopes.splitlines()[0]}"
        )

    async def predict_text(self, *args: Any, **kwargs: Any) -> str:
        return ""


class _DeterministicBiEncoder:
    """Keyword-mapped bi-encoder producing controlled unit vectors."""

    def encode_text(self, text: str) -> list[float]:
        low = text.lower()
        if "a priori" in low or "sensible intuition" in low:
            return [1.0, 0.0, 0.0, 0.0]
        if "coexistences" in low or "relational" in low or "monads" in low:
            return [0.0, 1.0, 0.0, 0.0]
        if "pragmatic" in low or "utility" in low:
            return [0.0, 0.0, 1.0, 0.0]
        if "syllogism" in low or "inferential" in low:
            return [0.0, 0.0, 0.99, 0.14]
        return [0.0, 0.0, 0.0, 1.0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.encode_text(t) for t in texts]

    async def aget_text_embedding(self, text: str) -> list[float]:
        return self.encode_text(text)


# ---------------------------------------------------------------------------
# AC 1: Layer 3 Intensional Scoping & Layer 2 Conception Contracts/Codecs
# ---------------------------------------------------------------------------


def test_intensional_mode_normalization_and_theory_atom_defaults() -> None:
    """Verify IntensionalMode aliases normalize cleanly on TheoryAtom."""
    assert IntensionalMode.from_str(None) == IntensionalMode.ASSERTED
    assert IntensionalMode.from_str("reductio") == IntensionalMode.SUPPOSITIONAL
    assert IntensionalMode.from_str("counterfactual") == IntensionalMode.SUPPOSITIONAL
    assert IntensionalMode.from_str("exegetical") == IntensionalMode.ATTRIBUTED
    assert IntensionalMode.from_str("historical") == IntensionalMode.HISTORICAL
    assert IntensionalMode.from_str("unrecognized") == IntensionalMode.ASSERTED

    atom = TheoryAtom(
        id="a_sup",
        text="Assume space is merely an empirical abstraction.",
        component_type="Premise",
        source_chunk_id="c1",
        intensional_mode="reductio",
        attributed_to=None,
    )
    assert atom.intensional_mode == "suppositional"
    assert atom.attributed_to is None

    atom_attr = TheoryAtom(
        id="a_attr",
        text="Custom and habit alone ground causal expectations.",
        component_type="Premise",
        source_chunk_id="c1",
        intensional_mode="exegetical",
        attributed_to="David Hume",
    )
    assert atom_attr.intensional_mode == "attributed"
    assert atom_attr.attributed_to == "David Hume"


def test_theory_atom_effective_base_prior_intensional_scoping() -> None:
    """Verify effective_base_prior gates suppositional and attributed claims by perspective."""
    asserted = TheoryAtom(
        id="a1",
        text="Mathematical judgments are synthetic a priori.",
        component_type="CoreAxiom",
        source_chunk_id="c1",
        modal_prior=0.80,
        local_tenability=0.50,
        intensional_mode="asserted",
    )
    suppositional = TheoryAtom(
        id="a2",
        text="Suppose space were derived only from outer sensations.",
        component_type="Premise",
        source_chunk_id="c1",
        modal_prior=0.90,
        local_tenability=1.0,
        intensional_mode="suppositional",
    )
    attributed = TheoryAtom(
        id="a3",
        text="Causal necessity is nothing beyond constant conjunction.",
        component_type="Premise",
        source_chunk_id="c2",
        modal_prior=0.85,
        local_tenability=1.0,
        intensional_mode="attributed",
        attributed_to="David Hume",
    )

    assert asserted.effective_base_prior() == pytest.approx(0.40)
    assert asserted.effective_base_prior(perspective="author") == pytest.approx(0.40)
    assert asserted.effective_base_prior(perspective="David Hume") == pytest.approx(0.0)

    # Suppositional claims contribute 0.0 unless explicitly enabled
    assert suppositional.effective_base_prior() == pytest.approx(0.0)
    assert suppositional.effective_base_prior(perspective="author") == pytest.approx(
        0.0
    )
    assert suppositional.effective_base_prior(
        include_suppositional=True
    ) == pytest.approx(0.90)
    assert suppositional.effective_base_prior(
        include_suppositional=True, perspective="author"
    ) == pytest.approx(0.90)

    # Attributed claims are excluded for author, enabled for matching agent or 'all'
    assert attributed.effective_base_prior(perspective="author") == pytest.approx(0.0)
    assert attributed.effective_base_prior(perspective="david hume") == pytest.approx(
        0.85
    )
    assert attributed.effective_base_prior(perspective="all") == pytest.approx(0.85)


def test_theory_atom_codec_builder_fingerprint_and_mapper_roundtrip() -> None:
    """Verify lossless round-trips, fingerprint sensitivity, and Neo4j mapper fields."""
    atom = TheoryAtom(
        id="atom_hume_1",
        text="Ideas are faint copies of impressions.",
        component_type="Premise",
        source_chunk_id="chunk_1",
        modal_prior=0.82,
        intensional_mode="attributed",
        attributed_to="David Hume",
    )
    artifact = TheoryAtomCodec.to_payload(atom)
    assert artifact.intensional_mode == "attributed"
    assert artifact.attributed_to == "David Hume"

    reconstructed = TheoryAtomCodec.to_domain(artifact)
    assert reconstructed.intensional_mode == "attributed"
    assert reconstructed.attributed_to == "David Hume"

    env_a = build_theory_atom_artifact(atom, run_id="r1", phase_name="P4", method="m")
    atom_diff_scope = atom.model_copy(
        update={"intensional_mode": "asserted", "attributed_to": None}
    )
    env_b = build_theory_atom_artifact(
        atom_diff_scope, run_id="r1", phase_name="P4", method="m"
    )
    assert env_a.dependency_fingerprint != env_b.dependency_fingerprint

    props = theory_atom_to_graph_properties(atom)
    assert props["intensional_mode"] == "attributed"
    assert props["attributed_to"] == "David Hume"


def test_entity_conception_and_linked_entity_codec_roundtrip() -> None:
    """Verify EntityConception facets and polysemy_variance survive codec round-trip."""
    conception_k = EntityConception(
        id="ent_space::conception::doc_kant",
        entity_id="ent_space",
        perspective="doc_kant",
        description="Pure a priori form of outer sensible intuition.",
        representative_envelopes=["Space is a necessary representation a priori."],
        source_chunk_ids=["chunk_k1"],
        centroid_dispersion=0.02,
        confidence=0.98,
    )
    conception_l = EntityConception(
        id="ent_space::conception::doc_leibniz",
        entity_id="ent_space",
        perspective="doc_leibniz",
        description="Relational order of coexistences among substances.",
        representative_envelopes=["Space is the order of coexistences."],
        source_chunk_ids=["chunk_l1"],
        centroid_dispersion=0.04,
        confidence=0.96,
    )
    entity = L2Entity(
        id="ent_space",
        label="CONCEPT",
        name="Space",
        description="[doc_kant] Pure a priori form... | [doc_leibniz] Relational order...",
        source_chunk_ids=["chunk_k1", "chunk_l1"],
        is_mature=True,
        conceptions=[conception_k, conception_l],
        polysemy_variance=0.41,
    )

    artifact = LinkedEntityCodec.to_payload(entity)
    assert len(artifact.conceptions) == 2
    assert artifact.polysemy_variance == pytest.approx(0.41)

    restored = LinkedEntityCodec.to_domain(artifact)
    assert restored.polysemy_variance == pytest.approx(0.41)
    assert [c.perspective for c in restored.conceptions] == ["doc_kant", "doc_leibniz"]
    assert restored.conceptions[0].description == conception_k.description
    assert restored.conceptions[1].source_chunk_ids == ["chunk_l1"]


@pytest.mark.asyncio
async def test_llm_acc_classifier_propagates_intensional_mode_and_attributed_to(
    tmp_path: Path,
) -> None:
    """Verify ACC classifier transfers intensional_mode and attributed_to to TheoryAtom."""

    class _FakeACCLLM:
        async def predict_text(self, *args: Any, **kwargs: Any) -> str:
            return ""

        async def predict_structured(self, *args: Any, **kwargs: Any) -> ACCOutput:
            return ACCOutput(
                components=[
                    ExtractedComponent(
                        id="AC1",
                        component_type="TheoreticalHypothesis",
                        text="Leibniz holds that space is merely relative order.",
                        confidence=0.91,
                        plausibility=0.80,
                        intensional_mode="attributed",
                        attributed_to="Leibniz",
                    ),
                    ExtractedComponent(
                        id="AC2",
                        component_type="TheoreticalHypothesis",
                        text="Suppose space were empirical; geometry would lack apodictic certainty.",
                        confidence=0.88,
                        plausibility=0.75,
                        intensional_mode="suppositional",
                    ),
                ],
                relations=[],
            )

    classifier = LLMACCClassifier(
        llm=DiskCachedStructuredLLM(_FakeACCLLM(), cache_dir=tmp_path / "acc_cache")
    )
    atoms, _ = await classifier.classify(
        chunk_id="chunk_test",
        tagged_text="[AC1] Leibniz holds... [/AC1] [AC2] Suppose space... [/AC2]",
        adu_ids=["AC1", "AC2"],
        schema=DEFAULT_SCHEMA,
    )
    assert len(atoms) == 2
    assert atoms[0].intensional_mode == "attributed"
    assert atoms[0].attributed_to == "Leibniz"
    assert atoms[1].intensional_mode == "suppositional"
    assert atoms[1].attributed_to is None


# ---------------------------------------------------------------------------
# AC 2: Perspective-Filtered & Supposition-Aware Projection
# ---------------------------------------------------------------------------


def test_theorynet_projector_isolates_reductio_and_attributed_subgraphs() -> None:
    """Verify TheoryNetProjector prevents suppositional/opponent pollution."""
    author_claim = TheoryAtom(
        id="author_claim",
        text="Space is an a priori intuition.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.50,
        intensional_mode="asserted",
    )
    reductio_premise = TheoryAtom(
        id="reductio_premise",
        text="Assume space is an empirical abstraction.",
        component_type="Premise",
        source_chunk_id="c1",
        modal_prior=0.95,
        intensional_mode="suppositional",
    )
    hume_premise = TheoryAtom(
        id="hume_premise",
        text="Causality reduces to constant conjunction.",
        component_type="Premise",
        source_chunk_id="c2",
        modal_prior=0.90,
        intensional_mode="attributed",
        attributed_to="David Hume",
    )
    hume_conclusion = TheoryAtom(
        id="hume_conclusion",
        text="Necessary connection cannot be observed in experience.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        modal_prior=0.50,
        intensional_mode="attributed",
        attributed_to="David Hume",
    )

    rels = [
        TheoryRelation(
            source_id="reductio_premise",
            target_id="author_claim",
            relation_type="SUPPORTS",
            confidence=0.95,
            inferential_warrant=1.0,
            scope="local",
        ),
        TheoryRelation(
            source_id="hume_premise",
            target_id="author_claim",
            relation_type="SUPPORTS",
            confidence=0.95,
            inferential_warrant=1.0,
            scope="global",
        ),
        TheoryRelation(
            source_id="hume_premise",
            target_id="hume_conclusion",
            relation_type="SUPPORTS",
            confidence=0.95,
            inferential_warrant=1.0,
            scope="local",
        ),
    ]
    view = Phase4ArtifactsView(
        theory_atoms=[author_claim, reductio_premise, hume_premise, hume_conclusion],
        theory_relations=rels,
    )

    author_projector = TheoryNetProjector(
        schema=DEFAULT_SCHEMA,
        perspective="author",
        isolate_suppositional=True,
        isolate_attributed=True,
    )
    fp = author_projector.fingerprint()
    assert fp["perspective"] == "author"
    assert fp["isolate_suppositional"] is True
    assert fp["isolate_attributed"] is True

    net_author = author_projector.project(view)
    by_id_author = {a.id: a for a in net_author.atoms}
    # Author claim remains strictly at its intrinsic prior (0.50), unpolluted by Reductio/Hume
    assert by_id_author["author_claim"].equilibrium_strength == pytest.approx(0.50)

    # Perspective override evaluates David Hume's internal argument cleanly
    net_hume = author_projector.project(view, perspective="David Hume")
    by_id_hume = {a.id: a for a in net_hume.atoms}
    assert by_id_hume["hume_conclusion"].equilibrium_strength is not None
    assert by_id_hume["hume_conclusion"].equilibrium_strength > 0.50
    assert by_id_hume["author_claim"].equilibrium_strength == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_phase6_runner_wires_perspective_and_isolates_reductio_artifacts() -> (
    None
):
    """Verify Phase6Runner propagates Phase6Config perspective/isolation settings."""
    ctx = ArtifactExecutionContext(
        run_id="r_p6_054",
        manifest=RunManifest(run_id="r_p6_054"),
        pipeline_input=PipelineInput(source_paths=[]),
    )
    a_claim = TheoryAtom(
        id="p6_author",
        text="Arithmetic propositions are synthetic a priori.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.50,
        intensional_mode="asserted",
    )
    a_reductio = TheoryAtom(
        id="p6_reductio",
        text="Suppose arithmetic propositions were merely analytic tautologies.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.92,
        intensional_mode="suppositional",
    )
    rel = TheoryRelation(
        source_id="p6_reductio",
        target_id="p6_author",
        relation_type="SUPPORTS",
        confidence=0.95,
        inferential_warrant=1.0,
        scope="local",
    )
    collection = ArtifactCollection(
        [
            build_argument_component_artifact(
                a_claim, run_id="r_p6_054", phase_name="P4", method="m"
            ),
            build_argument_component_artifact(
                a_reductio, run_id="r_p6_054", phase_name="P4", method="m"
            ),
            build_argument_relation_artifact(
                rel, run_id="r_p6_054", phase_name="P4", method="m"
            ),
        ]
    )
    view = Phase5ArtifactsView.from_collection(collection)

    runner = Phase6Runner(
        config=Phase6Config(
            perspective="author",
            isolate_suppositional=True,
            isolate_attributed=True,
        ),
        schema=DEFAULT_SCHEMA,
    )
    assert runner.projector.perspective == "author"
    assert runner.projector.isolate_suppositional is True
    assert runner.projector.isolate_attributed is True

    out = await runner.run(view, ctx)
    atom_payloads = {
        env.payload.component_id: env.payload
        for env in out.of_kind(ArtifactKind.THEORY_ATOM)
    }
    assert atom_payloads["p6_author"].equilibrium_strength == pytest.approx(0.50)
    assert atom_payloads["p6_author"].intensional_mode == "asserted"
    assert atom_payloads["p6_reductio"].intensional_mode == "suppositional"


# ---------------------------------------------------------------------------
# AC 3: Multi-Modal Conception Stratification in Phase 4 Maturation
# ---------------------------------------------------------------------------


def test_conception_clusterer_unimodal_vs_multimodal_and_edge_cases() -> None:
    """Verify spherical dispersion detection and cluster stratification edge cases."""
    clusterer = ConceptionClusterer(
        polysemy_variance_threshold=0.15,
        min_silhouette_score=0.15,
        max_conceptions=4,
        min_envelopes=2,
        top_k_per_conception=3,
    )

    # Edge case 1: Zero-norm embeddings do not falsely report maximal dispersion
    zero_vecs = np.zeros((3, 4), dtype=np.float32)
    assert clusterer.compute_spherical_variance(zero_vecs) == pytest.approx(0.0)

    # Edge case 2: Single vector or tightly aligned vectors remain uni-modal
    tight_vecs = np.array([[1.0, 0.0, 0.0], [0.99, 0.14, 0.0]], dtype=np.float32)
    var_tight, clusters_tight = clusterer.stratify(["e1", "e2"], tight_vecs)
    assert var_tight < 0.05
    assert clusters_tight == []

    # Edge case 3: N=2 orthogonal unlabeled envelopes split into 2 singleton clusters
    two_orth = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    var_two, clusters_two = clusterer.stratify(["ctx A", "ctx B"], two_orth)
    assert var_two > 0.25
    assert len(clusters_two) == 2
    assert [c.perspective for c in clusters_two] == [
        "concept_cluster_1",
        "concept_cluster_2",
    ]

    # Case 4: Unlabeled N=4 multi-modal vectors stratify via spherical k-means + silhouette
    unlabeled_vecs = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.98, 0.20, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.18, 0.98],
        ],
        dtype=np.float32,
    )
    var_unsup, clusters_unsup = clusterer.stratify(
        ["a1", "a2", "b1", "b2"],
        unlabeled_vecs,
        envelope_chunk_ids=["c1", "c2", "c3", "c4"],
    )
    assert var_unsup > 0.20
    assert len(clusters_unsup) == 2
    assert {tuple(sorted(c.envelopes)) for c in clusters_unsup} == {
        ("a1", "a2"),
        ("b1", "b2"),
    }


@pytest.mark.asyncio
async def test_phase4_maturation_runner_stratifies_polysemous_entities(
    tmp_path: Path,
) -> None:
    """Verify Phase4EntityMaturationRunner preserves EntityConceptions on divergence."""
    doc_kant = L1Document(
        id="doc_kant",
        title="Critique of Pure Reason",
        source_path="/tmp/kant.txt",
        chapter_count=1,
        chunk_count=4,
    )
    doc_leibniz = L1Document(
        id="doc_leibniz",
        title="Leibniz-Clarke Correspondence",
        source_path="/tmp/leibniz.txt",
        chapter_count=1,
        chunk_count=2,
    )
    chunks = [
        L1Chunk(
            id="ck_1",
            text="Space is a necessary representation a priori underlying outer intuitions.",
            source_doc_id="doc_kant",
            sequence_index=0,
            token_count=11,
        ),
        L1Chunk(
            id="ck_2",
            text="Space constitutes the pure form of sensible intuition.",
            source_doc_id="doc_kant",
            sequence_index=1,
            token_count=8,
        ),
        L1Chunk(
            id="cl_1",
            text="Space is an order of coexistences among monads, purely relational.",
            source_doc_id="doc_leibniz",
            sequence_index=0,
            token_count=10,
        ),
        L1Chunk(
            id="cl_2",
            text="Space arises as a relational abstraction over coexisting monads.",
            source_doc_id="doc_leibniz",
            sequence_index=1,
            token_count=9,
        ),
        L1Chunk(
            id="cr_1",
            text="Reason governs syllogism formation.",
            source_doc_id="doc_kant",
            sequence_index=2,
            token_count=5,
        ),
        L1Chunk(
            id="cr_2",
            text="Reason coordinates inferential rules.",
            source_doc_id="doc_kant",
            sequence_index=3,
            token_count=5,
        ),
    ]

    e_space = L2Entity(
        id="ent_space",
        label="CONCEPT",
        name="Space",
        description="Immature initial mention of Space.",
        source_chunk_ids=["ck_1", "ck_2", "cl_1", "cl_2"],
        is_mature=False,
    )
    e_reason = L2Entity(
        id="ent_reason",
        label="CONCEPT",
        name="Reason",
        description="Immature mention of Reason.",
        source_chunk_ids=["cr_1", "cr_2"],
        is_mature=False,
    )

    envelopes = [
        build_document_artifact(doc_kant, run_id="r054", phase_name="P1", method="m"),
        build_document_artifact(
            doc_leibniz, run_id="r054", phase_name="P1", method="m"
        ),
        *(
            build_chunk_artifact(c, run_id="r054", phase_name="P1", method="m")
            for c in chunks
        ),
        # Mentions for Space with divergent contextual envelopes
        build_entity_mention_artifact(
            e_space.model_copy(
                update={
                    "textual_envelope": "Space is a necessary representation a priori for sensible intuition."
                }
            ),
            "ck_1",
            run_id="r054",
            phase_name="P2",
            method="m",
        ),
        build_entity_mention_artifact(
            e_space.model_copy(
                update={
                    "textual_envelope": "Pure form of sensible intuition a priori is Space."
                }
            ),
            "ck_2",
            run_id="r054",
            phase_name="P2",
            method="m",
        ),
        build_entity_mention_artifact(
            e_space.model_copy(
                update={
                    "textual_envelope": "Space is simply an order of coexistences among monads."
                }
            ),
            "cl_1",
            run_id="r054",
            phase_name="P2",
            method="m",
        ),
        build_entity_mention_artifact(
            e_space.model_copy(
                update={
                    "textual_envelope": "Space is a relational property of coexisting monads."
                }
            ),
            "cl_2",
            run_id="r054",
            phase_name="P2",
            method="m",
        ),
        # Coherent uni-modal mentions for Reason
        build_entity_mention_artifact(
            e_reason.model_copy(
                update={"textual_envelope": "Reason organizes formal syllogism."}
            ),
            "cr_1",
            run_id="r054",
            phase_name="P2",
            method="m",
        ),
        build_entity_mention_artifact(
            e_reason.model_copy(
                update={"textual_envelope": "Reason regulates inferential rules."}
            ),
            "cr_2",
            run_id="r054",
            phase_name="P2",
            method="m",
        ),
        build_linked_entity_artifact(
            e_space,
            [f"m::{e_space.id}::{cid}" for cid in e_space.source_chunk_ids],
            run_id="r054",
            phase_name="P3b",
            method="m",
        ),
        build_linked_entity_artifact(
            e_reason,
            [f"m::{e_reason.id}::{cid}" for cid in e_reason.source_chunk_ids],
            run_id="r054",
            phase_name="P3b",
            method="m",
        ),
    ]

    view = Phase3ArtifactsView.from_collection(ArtifactCollection(envelopes))
    ctx = ArtifactExecutionContext(
        run_id="r054",
        manifest=RunManifest(run_id="r054"),
        pipeline_input=PipelineInput(source_paths=[]),
    )

    llm = _DeterministicMaturationLLM()
    runner = Phase4EntityMaturationRunner(
        config=Phase4EntityMaturationConfig(),
        llm=DiskCachedStructuredLLM(llm, cache_dir=tmp_path / "mat_cache"),
        graph_store=None,
        embedding_model=_DeterministicBiEncoder(),
    )

    components = runner.components()
    assert "conception_clusterer" in components
    assert isinstance(components["conception_clusterer"], ConceptionClusterer)
    assert (
        components["conception_clusterer"].fingerprint()["component"]
        == "ConceptionClusterer"
    )

    recorder = _RecordingEmitter()
    with use_event_emitter(recorder):
        output = await runner.run(view, ctx)

    assert len(llm.calls) == 3

    by_id = {
        env.payload.entity_id: env.payload.to_domain()
        for env in output.of_kind(ArtifactKind.LINKED_ENTITY)
    }
    assert set(by_id.keys()) == {"ent_space", "ent_reason"}

    matured_space = by_id["ent_space"]
    assert matured_space.is_mature is True
    assert matured_space.polysemy_variance is not None
    assert matured_space.polysemy_variance > 0.15
    assert len(matured_space.conceptions) == 2
    assert {c.perspective for c in matured_space.conceptions} == {
        "doc_kant",
        "doc_leibniz",
    }
    assert "[doc_kant]" in matured_space.description
    assert "[doc_leibniz]" in matured_space.description

    matured_reason = by_id["ent_reason"]
    assert matured_reason.is_mature is True
    assert matured_reason.conceptions == []
    assert matured_reason.polysemy_variance is not None
    assert matured_reason.polysemy_variance < 0.05

    strat_events = [
        ev for ev in recorder.events if isinstance(ev, EntityConceptionStratified)
    ]
    synth_events = [
        ev for ev in recorder.events if isinstance(ev, EntityMaturationSynthesized)
    ]
    assert len(strat_events) == 1
    assert strat_events[0].entity_id == "ent_space"
    assert strat_events[0].conception_count == 2
    assert set(strat_events[0].perspectives) == {"doc_kant", "doc_leibniz"}
    assert len(synth_events) == 2

    # Failure-mode test: failing structured LLM returns empty collection safely
    failing_runner = Phase4EntityMaturationRunner(
        config=Phase4EntityMaturationConfig(),
        llm=DiskCachedStructuredLLM(
            _DeterministicMaturationLLM(fail=True),
            cache_dir=tmp_path / "mat_fail_cache",
        ),
        graph_store=None,
        embedding_model=_DeterministicBiEncoder(),
    )
    failing_out = await failing_runner.run(view, ctx)
    assert failing_out.artifacts == []


def test_issue_054_documentation_and_adr_sync() -> None:
    """Verify ADR-0023, ADR index, concept docs, related ADRs, and ISSUE-054 are synced."""
    repo_root = Path(__file__).resolve().parents[3]

    adr_0023_path = (
        repo_root
        / "docs"
        / "adr"
        / "0023-intensional-perspectival-scoping-and-conception-stratification.md"
    )
    assert adr_0023_path.exists()
    adr_0023 = adr_0023_path.read_text(encoding="utf-8")
    assert "Intensional" in adr_0023
    assert "EntityConception" in adr_0023
    assert "QBAFGradualSemanticsSolver" in adr_0023

    adr_index = (repo_root / "docs" / "adr" / "index.md").read_text(encoding="utf-8")
    assert "0023" in adr_index

    for rel_path in (
        "docs/concepts/formal_graph_model.md",
        "docs/concepts/assumptions_limitations.md",
        "docs/adr/0003-coreference-absorbed-into-fusion.md",
        "docs/adr/0016-attribute-alignment-deferred.md",
        "docs/adr/0020-propositional-modal-strength-resolver.md",
    ):
        text = (repo_root / rel_path).read_text(encoding="utf-8")
        assert "0023" in text

    issue_filename = (
        "ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md"
    )
    issue_candidates = [
        repo_root / "issues" / "09-architecture-workflow-domain" / issue_filename,
        repo_root
        / "issues"
        / "09-architecture-workflow-domain"
        / "resolved"
        / issue_filename,
        repo_root / "issues" / "archived" / issue_filename,
        *sorted((repo_root / "issues").rglob("*ISSUE-054*.md")),
    ]
    issue_path = next((p for p in issue_candidates if p.exists()), None)
    if issue_path is not None:
        issue_text = issue_path.read_text(encoding="utf-8")
        assert "`Completed`" in issue_text or "`Resolved`" in issue_text
        assert "- [ ]" not in issue_text
        assert "- [x]" in issue_text


def test_theorynet_projector_reductio_discharge_and_dialectical_critique() -> None:
    """Verify TheoryNetProjector handles Reductio discharge, historical premises, and dialectical attacks."""
    from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
    from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

    thesis = TheoryAtom(
        id="p_thesis",
        text="A priori synthetic judgments are possible.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.50,
        intensional_mode="asserted",
    )
    rival_supp = TheoryAtom(
        id="p_rival",
        text="Suppose all knowledge derives strictly from habit.",
        component_type="Premise",
        source_chunk_id="c1",
        modal_prior=0.90,
        intensional_mode="suppositional",
    )
    absurd_conseq = TheoryAtom(
        id="p_absurd",
        text="Mathematics would lack universal necessity.",
        component_type="Premise",
        source_chunk_id="c1",
        modal_prior=0.85,
        intensional_mode="suppositional",
    )
    math_fact = TheoryAtom(
        id="p_math",
        text="Arithmetic propositions possess universal necessity.",
        component_type="Evidence",
        source_chunk_id="c1",
        modal_prior=0.95,
        intensional_mode="historical",
    )
    other_thesis = TheoryAtom(
        id="p_other",
        text="Causality grounds objective succession.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        modal_prior=0.50,
        intensional_mode="asserted",
    )
    unrefuted_supp = TheoryAtom(
        id="p_unrefuted",
        text="Suppose causality were merely subjective.",
        component_type="Premise",
        source_chunk_id="c2",
        modal_prior=0.95,
        intensional_mode="suppositional",
    )
    hume_critique = TheoryAtom(
        id="p_hume",
        text="No impression of necessary connection exists.",
        component_type="CounterArgument",
        source_chunk_id="c2",
        modal_prior=0.90,
        intensional_mode="attributed",
        attributed_to="David Hume",
    )

    rels = [
        TheoryRelation(
            source_id="p_rival",
            target_id="p_absurd",
            relation_type="SUPPORTS",
            confidence=0.95,
            inferential_warrant=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="p_math",
            target_id="p_absurd",
            relation_type="ATTACKS",
            confidence=0.95,
            inferential_warrant=0.95,
            scope="local",
        ),
        TheoryRelation(
            source_id="p_rival",
            target_id="p_thesis",
            relation_type="ATTACKS",
            confidence=0.95,
            inferential_warrant=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="p_unrefuted",
            target_id="p_other",
            relation_type="ATTACKS",
            confidence=0.95,
            inferential_warrant=0.95,
            scope="local",
        ),
        TheoryRelation(
            source_id="p_hume",
            target_id="p_other",
            relation_type="ATTACKS",
            confidence=0.95,
            inferential_warrant=0.9,
            scope="local",
        ),
    ]
    view = Phase4ArtifactsView(
        theory_atoms=[
            thesis,
            rival_supp,
            absurd_conseq,
            math_fact,
            other_thesis,
            unrefuted_supp,
            hume_critique,
        ],
        theory_relations=rels,
    )

    isolated_proj = TheoryNetProjector(
        schema=DEFAULT_SCHEMA,
        perspective="author",
        isolate_suppositional=True,
        isolate_attributed=True,
    )
    net_iso = isolated_proj.project(view)
    by_iso = {a.id: a for a in net_iso.atoms}
    assert by_iso["p_thesis"].equilibrium_strength is not None
    assert by_iso["p_thesis"].equilibrium_strength > 0.50
    assert by_iso["p_other"].equilibrium_strength == pytest.approx(0.50)

    dialectic_proj = TheoryNetProjector(
        schema=DEFAULT_SCHEMA,
        perspective="author",
        isolate_suppositional=True,
        isolate_attributed=False,
    )
    net_dia = dialectic_proj.project(view)
    by_dia = {a.id: a for a in net_dia.atoms}
    assert by_dia["p_other"].equilibrium_strength is not None
    assert by_dia["p_other"].equilibrium_strength < 0.50


@pytest.mark.asyncio
async def test_llm_acc_classifier_defers_to_modal_resolver_when_plausibility_unset(
    tmp_path: Path,
) -> None:
    """Verify LLMACCClassifier leaves modal_prior unset when ext.plausibility is None."""

    class _FakeUnsetPlausibilityLLM:
        async def predict_text(self, *args: Any, **kwargs: Any) -> str:
            return ""

        async def predict_structured(self, *args: Any, **kwargs: Any) -> ACCOutput:
            return ACCOutput(
                components=[
                    ExtractedComponent(
                        id="AC1",
                        text="Bodies attract with inverse-square force.",
                        component_type="TheoreticalHypothesis",
                        confidence=0.80,
                        plausibility=None,
                    )
                ],
                relations=[],
            )

    clf = LLMACCClassifier(
        llm=DiskCachedStructuredLLM(
            _FakeUnsetPlausibilityLLM(),
            cache_dir=tmp_path / "unset_plaus_cache",
        )
    )
    atoms, _ = await clf.classify(
        chunk_id="c1",
        tagged_text="<AC1>Bodies attract with inverse-square force.</AC1>",
        adu_ids=["AC1"],
        schema=DEFAULT_SCHEMA,
    )
    assert len(atoms) == 1
    assert atoms[0].modal_prior == pytest.approx(0.6)
    assert "modal_prior" not in atoms[0].model_fields_set


@pytest.mark.asyncio
async def test_phase5_fusion_preserves_distinct_intensional_scopes() -> None:
    """Verify Phase 5 clustering and L3 fusion never merge incompatible intensional scopes."""
    from episteme_pipeline.artifacts.execution import _resolve_l3_atoms_and_relations
    from episteme_pipeline.artifacts.models import FusionDecisionArtifact
    from episteme_pipeline.phases.phase5_fusion.argument_clustering import (
        EmbeddingArgumentClustering,
    )

    atom_author_1 = TheoryAtom(
        id="ac_auth_1",
        text="Reason supplies universal laws.",
        component_type="Premise",
        source_chunk_id="c1",
        intensional_mode="asserted",
    )
    atom_author_2 = TheoryAtom(
        id="ac_auth_2",
        text="Reason provides universal principles.",
        component_type="Premise",
        source_chunk_id="c2",
        intensional_mode="asserted",
    )
    atom_hume = TheoryAtom(
        id="ac_hume_1",
        text="Reason supplies universal laws.",
        component_type="Premise",
        source_chunk_id="c3",
        intensional_mode="attributed",
        attributed_to="David Hume",
    )

    class _IdenticalEmbedder:
        async def aget_text_embedding_batch(
            self, texts: list[str]
        ) -> list[list[float]]:
            return [[1.0, 0.0, 0.0] for _ in texts]

    class _FakeGraphReader:
        async def get_theory_atoms(self) -> list[TheoryAtom]:
            return [atom_author_1, atom_hume]

    clusterer = EmbeddingArgumentClustering(
        embedding_model=_IdenticalEmbedder(),
        similarity_threshold=0.85,
    )
    clusters = await clusterer.cluster(_FakeGraphReader())  # type: ignore[arg-type]
    assert clusters == []

    # Even if an upstream decision groups incompatible scopes, _resolve_l3_atoms_and_relations splits safely.
    decision = FusionDecisionArtifact(
        decision_id="fd_1",
        decision_type="merge",
        canonical_artifact_id="ac_auth_1",
        artifact_ids=["ac_auth_1", "ac_auth_2", "ac_hume_1"],
    )
    relations = [
        TheoryRelation(
            source_id="ac_auth_2",
            target_id="ac_hume_1",
            relation_type="ATTACKS",
            confidence=0.9,
            scope="global",
        )
    ]
    resolved_atoms, resolved_rels = _resolve_l3_atoms_and_relations(
        [atom_author_1, atom_author_2, atom_hume],
        relations,
        [decision],
    )
    resolved_ids = {a.id for a in resolved_atoms}
    assert resolved_ids == {"ac_auth_1", "ac_hume_1"}
    assert len(resolved_rels) == 1
    assert resolved_rels[0].source_id == "ac_auth_1"
    assert resolved_rels[0].target_id == "ac_hume_1"


@pytest.mark.asyncio
async def test_entity_maturation_protocol_injection_and_duplicate_envelopes(
    tmp_path: Path,
) -> None:
    """Verify ConceptionClustererProtocol DI and preservation of duplicate envelopes across chunks."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    from episteme_pipeline.phases.phase4_entity_maturation import (
        ConceptionCluster,
        Phase4EntityMaturationRunner,
    )
    from episteme_pipeline.protocols.entity_maturation import (
        ConceptionClustererProtocol,
    )

    seen_envelopes: list[str] = []

    class _CustomClusterer:
        def fingerprint(self) -> dict[str, Any]:
            return {"component": "_CustomClusterer"}

        def compute_spherical_variance(self, embeddings: np.ndarray) -> float:
            return 0.0

        def stratify(
            self,
            envelopes: list[str],
            embeddings: np.ndarray,
            *,
            envelope_chunk_ids: list[str] | None = None,
            envelope_perspectives: list[str] | None = None,
        ) -> tuple[float, list[ConceptionCluster]]:
            seen_envelopes.extend(envelopes)
            assert envelope_chunk_ids == ["c1", "c2"]
            assert envelope_perspectives == ["doc_1", "doc_2"]
            return 0.0, []

    custom = _CustomClusterer()
    assert isinstance(custom, ConceptionClustererProtocol)

    with pytest.raises(TypeError, match="ConceptionClustererProtocol"):
        Phase4EntityMaturationRunner(
            config=Phase4EntityMaturationConfig(),
            llm=DiskCachedStructuredLLM(
                _DeterministicMaturationLLM(),
                cache_dir=tmp_path / "bad_clusterer_cache",
            ),
            embedding_model=_DeterministicBiEncoder(),
            conception_clusterer="invalid",  # type: ignore[arg-type]
        )

    runner = Phase4EntityMaturationRunner(
        config=Phase4EntityMaturationConfig(),
        llm=DiskCachedStructuredLLM(
            _DeterministicMaturationLLM(),
            cache_dir=tmp_path / "custom_clusterer_cache",
        ),
        embedding_model=_DeterministicBiEncoder(),
        conception_clusterer=custom,
    )

    entity = L2Entity(
        id="ent_dup",
        name="Matter",
        label="Concept",
        is_mature=False,
    )
    identical_env = "Matter is extended substance."
    out = await runner._process_entity(
        entity,
        run_id="run_dup",
        input_envelopes=[identical_env],
        mention_records=[
            {"chunk_id": "c1", "textual_envelope": identical_env},
            {"chunk_id": "c2", "textual_envelope": identical_env},
        ],
        chunk_to_doc={"c1": "doc_1", "c2": "doc_2"},
    )
    assert out is not None
    assert seen_envelopes == [identical_env, identical_env]
