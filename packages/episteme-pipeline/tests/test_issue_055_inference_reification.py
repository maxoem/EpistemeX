"""Deterministic tests for ISSUE-055: Bipartite Inference Hypergraph in episteme-pipeline.

Covers contracts, codecs, Phase 4 ACC local resolution, Phase 5 canonical
resolution, ArtifactGraphProjector (:TheoryInference node/edge projection +
domain event emission + fingerprinting), and Phase 6 TheoryNetProjector
end-to-end execution under Product and Godel t-norms.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from episteme_pipeline.artifacts.builders import (
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.codecs import TheoryRelationCodec
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase4ArtifactsView,
    _resolve_l3_atoms_and_relations,
)
from episteme_pipeline.artifacts.models import (
    FusionDecisionArtifact,
    TheoryInferenceArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.config import Phase6Config
from episteme_pipeline.contracts.domain import (
    TheoryAtom,
    TheoryInference,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.events import (
    ArtifactProjected,
    EventObserver,
    SimpleEventEmitter,
    use_event_emitter,
)
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.graph.neo4j_store import _NON_ENTITY_LABELS, Neo4jGraphReader
from episteme_pipeline.graph.theory_graph_mapper import (
    is_theory_edge,
    theory_relation_from_graph_properties,
    theory_relation_to_graph_properties,
)
from episteme_pipeline.phases.phase4_argument_mining import (
    _filter_valid_local_relations,
)
from episteme_pipeline.phases.phase4_argument_mining.acc_classifier import (
    LLMACCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.models import (
    ACCOutput,
    ExtractedComponent,
    ExtractedTheoryRelation,
)
from episteme_pipeline.phases.phase4_argument_mining.pairing import stable_component_id
from episteme_pipeline.post_processing.theoretical_enrichment.runner import (
    _enrichment_rel_key,
)
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.prompts.default_prompts import (
    ACC_DIRECT_PROMPT,
    ACC_FORMAT_PROMPT,
    ACC_REASONING_PROMPT,
)
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


class _RecordingObserver(EventObserver):
    def __init__(self) -> None:
        self.events: list[object] = []

    def on_event(self, event: object) -> None:
        self.events.append(event)


def _atom(
    atom_id: str, text: str = "claim", modal: float = 0.85, ctype: str = "Premise"
) -> TheoryAtom:
    return TheoryAtom(
        id=atom_id,
        text=text,
        component_type=ctype,
        source_chunk_id="c1",
        confidence=0.95,
        modal_prior=modal,
    )


class TestDomainContractsAndCodecs:
    """Verify TheoryRelation / TheoryInference fields, validators, and codec round-trip."""

    def test_conjunctive_and_undercutting_properties_and_codec_roundtrip(self) -> None:
        conj = TheoryInference(
            id="inf_1",
            source_id="",
            premise_ids=("a1", "a2", "a1"),
            target_id="a3",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
            inferential_warrant=0.8,
        )
        assert conj.source_id == "a1"
        assert conj.premise_ids == ("a1", "a2")
        assert conj.effective_premise_ids == ("a1", "a2")
        assert conj.has_conjunctive_premises is True
        assert conj.relation_id == "inf_1"

        und = TheoryRelation(
            source_id="u1",
            target_id="",
            undercuts_relation_id="inf_1",
            relation_type="UNDERCUTS",
            confidence=0.88,
            scope="local",
        )
        assert und.target_id == "inf_1"
        assert und.relation_id == "argument-relation::u1::UNDERCUTS::inf_1"

        # Lossless codec + artifact round-trip
        for rel in (conj, und):
            payload = TheoryRelationCodec.to_payload(rel)
            assert isinstance(payload, TheoryInferenceArtifact)
            assert TheoryRelationCodec.to_domain(payload) == rel

        # Graph properties serialization / reconstruction round-trip
        props = theory_relation_to_graph_properties(conj)
        assert props["id"] == "inf_1"
        assert props["premise_ids"] == ["a1", "a2"]
        reconstructed = theory_relation_from_graph_properties(
            conj.source_id, conj.relation_type, conj.target_id, props
        )
        assert reconstructed.id == "inf_1"
        assert reconstructed.premise_ids == ("a1", "a2")

        # Structural bipartite edge labels are excluded from pairwise theory edge detection
        assert is_theory_edge(relation_type="HAS_PREMISE", source_is_atom=True) is False
        assert is_theory_edge(relation_type="CONCLUDES", target_is_atom=True) is False

    def test_curation_ledger_preserves_hyperedge_fields(self) -> None:
        conj = TheoryRelation(
            id="inf_c",
            source_id="a1",
            premise_ids=("a1", "a2"),
            target_id="c1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="global",
        )
        und = TheoryRelation(
            id="und_c",
            source_id="u1",
            target_id="inf_c",
            undercuts_relation_id="inf_c",
            relation_type="UNDERCUTS",
            confidence=0.85,
            scope="global",
        )
        ledger = EpistemicCurationLedger()
        curated = ledger.apply_to_theory_relations([conj, und])
        assert curated[0].id == "inf_c"
        assert curated[0].premise_ids == ("a1", "a2")
        assert curated[1].undercuts_relation_id == "inf_c"


class TestPhase4AndPhase5Resolution:
    """Verify local Phase 4 extraction remapping and Phase 5 canonical merging."""

    def test_acc_output_validates_conjunctive_premises_and_undercuts(self) -> None:
        comp1 = ExtractedComponent(
            id="AC1", component_type="EmpiricalStatement", text="Premise 1"
        )
        comp2 = ExtractedComponent(
            id="AC2", component_type="ObservationUnit", text="Premise 2"
        )
        comp3 = ExtractedComponent(
            id="AC3", component_type="TheoreticalHypothesis", text="Conclusion"
        )
        comp_u = ExtractedComponent(
            id="AC4", component_type="ObservationUnit", text="Undercutter"
        )

        good = ACCOutput(
            components=[comp1, comp2, comp3, comp_u],
            relations=[
                ExtractedTheoryRelation(
                    id="R1",
                    premise_ids=["AC1", "AC2"],
                    target_id="AC3",
                    relation="SUPPORTS_ARG",
                ),
                ExtractedTheoryRelation(
                    id="R2",
                    source_id="AC4",
                    undercuts_relation_id="R1",
                    relation="UNDERCUTS",
                ),
            ],
        )
        validated = good.validate_references()
        assert len(validated.relations) == 2

        dangling_und = ACCOutput(
            components=[comp1, comp3, comp_u],
            relations=[
                ExtractedTheoryRelation(
                    id="R2",
                    source_id="AC4",
                    undercuts_relation_id="R99",
                    relation="UNDERCUTS",
                ),
            ],
        )
        assert dangling_und.validate_references().relations == []

        # Dropping a premise must cascade-drop dependent conjunctive relation AND its undercutter
        with_missing_prem = ACCOutput(
            components=[comp1, comp3, comp_u],
            relations=[
                ExtractedTheoryRelation(
                    id="R1",
                    premise_ids=["AC1", "AC99"],
                    target_id="AC3",
                    relation="SUPPORTS_ARG",
                ),
                ExtractedTheoryRelation(
                    id="R2",
                    source_id="AC4",
                    undercuts_relation_id="R1",
                    relation="UNDERCUTS",
                ),
            ],
        )
        assert with_missing_prem.validate_references().relations == []

    @pytest.mark.asyncio
    async def test_llm_acc_classifier_resolves_local_hyperedges_and_undercutters(
        self,
    ) -> None:
        acc_output = ACCOutput(
            components=[
                ExtractedComponent(
                    id="AC1",
                    component_type="TheoreticalHypothesis",
                    text="Universal law L.",
                ),
                ExtractedComponent(
                    id="AC2",
                    component_type="ObservationUnit",
                    text="Boundary condition B.",
                ),
                ExtractedComponent(
                    id="AC3",
                    component_type="EmpiricalStatement",
                    text="Derived consequence C.",
                ),
                ExtractedComponent(
                    id="AC4",
                    component_type="ObservationUnit",
                    text="Instrument calibration failure U.",
                ),
            ],
            relations=[
                ExtractedTheoryRelation(
                    id="R1",
                    premise_ids=["AC1", "AC2"],
                    target_id="AC3",
                    relation="SUPPORTS_ARG",
                    confidence=0.9,
                ),
                ExtractedTheoryRelation(
                    id="R2",
                    source_id="AC4",
                    undercuts_relation_id="R1",
                    relation="UNDERCUTS",
                    confidence=0.85,
                ),
            ],
        )
        mock_llm = MagicMock()
        mock_llm.predict_structured = AsyncMock(return_value=acc_output)
        mock_llm.predict_text = AsyncMock(return_value="")
        classifier = LLMACCClassifier(llm=mock_llm)
        # Bypass disk cache in unit test while keeping ensure_structured_llm contract exercised
        classifier.llm = mock_llm

        atoms, rels = await classifier.classify(
            chunk_id="chunk-42",
            tagged_text="<AC1>L</AC1><AC2>B</AC2><AC3>C</AC3><AC4>U</AC4>",
            adu_ids=["AC1", "AC2", "AC3", "AC4"],
            schema=DEFAULT_SCHEMA,
        )

        expected_ids = {
            k: stable_component_id("chunk-42", k) for k in ("AC1", "AC2", "AC3", "AC4")
        }
        assert {a.id for a in atoms} == set(expected_ids.values())
        assert len(rels) == 2

        conj_rel = next(r for r in rels if r.relation_type == "SUPPORTS_ARG")
        und_rel = next(r for r in rels if r.relation_type == "UNDERCUTS")
        assert conj_rel.premise_ids == (expected_ids["AC1"], expected_ids["AC2"])
        assert conj_rel.target_id == expected_ids["AC3"]
        assert und_rel.source_id == expected_ids["AC4"]
        assert und_rel.undercuts_relation_id == conj_rel.relation_id
        assert und_rel.target_id == conj_rel.relation_id

    def test_phase5_canonical_resolution_remaps_premises_and_undercut_targets(
        self,
    ) -> None:
        a1_canon = _atom("canon_a1", "Law")
        a1 = _atom("raw_a1", "Law")
        a2 = _atom("raw_a2", "Condition")
        c_canon = _atom("canon_c", "Result")
        c = _atom("raw_c", "Result")
        u = _atom("raw_u", "Confounder")

        r1 = TheoryRelation(
            id=None,
            source_id="raw_a1",
            premise_ids=("raw_a1", "raw_a2"),
            target_id="raw_c",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        )
        r2 = TheoryRelation(
            source_id="raw_u",
            target_id=r1.relation_id,
            undercuts_relation_id=r1.relation_id,
            relation_type="UNDERCUTS",
            confidence=0.8,
            scope="local",
        )
        decisions = [
            FusionDecisionArtifact(
                decision_id="fd_1",
                decision_type="merge",
                canonical_artifact_id="canon_a1",
                artifact_ids=["canon_a1", "raw_a1"],
            ),
            FusionDecisionArtifact(
                decision_id="fd_2",
                decision_type="merge",
                canonical_artifact_id="canon_c",
                artifact_ids=["canon_c", "raw_c"],
            ),
        ]
        canon_atoms, canon_rels = _resolve_l3_atoms_and_relations(
            [a1_canon, a1, a2, c_canon, c, u], [r1, r2], decisions
        )
        assert {a.id for a in canon_atoms} == {"canon_a1", "raw_a2", "canon_c", "raw_u"}

        resolved_conj = next(r for r in canon_rels if r.relation_type == "SUPPORTS")
        resolved_und = next(r for r in canon_rels if r.relation_type == "UNDERCUTS")
        assert resolved_conj.premise_ids == ("canon_a1", "raw_a2")
        assert resolved_conj.source_id == "canon_a1"
        assert resolved_conj.target_id == "canon_c"
        assert resolved_und.undercuts_relation_id == resolved_conj.relation_id
        assert resolved_und.undercuts_relation_id != r1.relation_id
        assert resolved_und.target_id == resolved_conj.relation_id


class TestArtifactGraphProjectorBipartiteReification:
    """Verify :TheoryInference node materialization, bipartite edges, events, and fingerprints."""

    @pytest.mark.asyncio
    async def test_project_collection_reifies_conjunctive_and_targeted_inferences(
        self,
    ) -> None:
        store = InMemoryGraphStore()
        atoms = [
            _atom("a_law", "Law"),
            _atom("a_cond", "Condition"),
            _atom("a_conc", "Conclusion"),
            _atom("a_pair", "Pairwise premise"),
            _atom("a_under", "Undercutter"),
            _atom("a_back", "Backing"),
        ]
        conj_rel = TheoryRelation(
            id="inf_conj",
            source_id="a_law",
            premise_ids=("a_law", "a_cond"),
            target_id="a_conc",
            relation_type="SUPPORTS",
            confidence=0.92,
            scope="global",
            inferential_warrant=0.8,
        )
        targeted_unary = TheoryRelation(
            id="inf_unary_undercut",
            source_id="a_pair",
            target_id="a_conc",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="global",
            inferential_warrant=0.75,
        )
        undercut_rel = TheoryRelation(
            source_id="a_under",
            target_id="inf_unary_undercut",
            undercuts_relation_id="inf_unary_undercut",
            relation_type="UNDERCUTS",
            confidence=0.88,
            scope="global",
        )
        back_rel = TheoryRelation(
            source_id="a_back",
            target_id="inf_conj",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="global",
        )
        plain_unary = TheoryRelation(
            source_id="a_law",
            target_id="a_pair",
            relation_type="SUPPORTS",
            confidence=0.85,
            scope="global",
        )

        envelopes = [
            build_theory_atom_artifact(
                a, run_id="r1", phase_name="phase4", method="test"
            )
            for a in atoms
        ] + [
            build_theory_relation_artifact(
                r, run_id="r1", phase_name="phase4", method="test"
            )
            for r in (conj_rel, targeted_unary, undercut_rel, back_rel, plain_unary)
        ]
        collection = ArtifactCollection(envelopes)

        recorder = _RecordingObserver()
        emitter = SimpleEventEmitter()
        emitter.register_observer(recorder)

        projector = ArtifactGraphProjector(store, schema=DEFAULT_SCHEMA, t_norm="godel")
        assert projector.fingerprint()["t_norm"] == "godel"

        with use_event_emitter(emitter):
            await projector.project_collection(collection)

        # Two reified :TheoryInference nodes created (conjunctive + targeted unary)
        inf_nodes = {
            nid: props
            for nid, props in store._nodes.items()
            if props.get("label") == "TheoryInference"
        }
        assert set(inf_nodes.keys()) == {"inf_conj", "inf_unary_undercut"}
        assert inf_nodes["inf_conj"]["premise_ids"] == ["a_law", "a_cond"]
        assert inf_nodes["inf_conj"]["t_norm"] == "godel"

        # Inspect bipartite edges stored in generic relations
        edge_triples = {
            (e["from_id"], e["relation_type"], e["to_id"])
            for e in store._generic_relations
        }
        assert ("a_law", "HAS_PREMISE", "inf_conj") in edge_triples
        assert ("a_cond", "HAS_PREMISE", "inf_conj") in edge_triples
        assert ("inf_conj", "CONCLUDES", "a_conc") in edge_triples
        assert ("a_back", "BACKS", "inf_conj") in edge_triples
        assert ("a_pair", "HAS_PREMISE", "inf_unary_undercut") in edge_triples
        assert ("inf_unary_undercut", "CONCLUDES", "a_conc") in edge_triples
        assert ("a_under", "UNDERCUTS", "inf_unary_undercut") in edge_triples

        # Plain untargeted unary relation remains direct pairwise TheoryRelation
        assert any(
            r.source_id == "a_law" and r.target_id == "a_pair"
            for r in await store.get_all_theory_relations()
        )
        # Event emitter recorded successful ArtifactProjected event
        projected_events = [
            e for e in recorder.events if isinstance(e, ArtifactProjected)
        ]
        assert len(projected_events) == 1
        assert projected_events[0].success is True

    @pytest.mark.asyncio
    async def test_single_envelope_projection_emits_event_and_reifies_conjunctive_artifact(
        self,
    ) -> None:
        store = InMemoryGraphStore()
        rel = TheoryRelation(
            id="inf_single",
            source_id="p1",
            premise_ids=("p1", "p2"),
            target_id="c1",
            relation_type="EXPLAINS",
            confidence=0.9,
            scope="global",
        )
        payload = TheoryRelationCodec.to_payload(rel)
        assert isinstance(payload, TheoryRelationArtifact)
        env = build_theory_relation_artifact(
            payload.to_domain(), run_id="r1", phase_name="phase4", method="test"
        )
        recorder = _RecordingObserver()
        emitter = SimpleEventEmitter()
        emitter.register_observer(recorder)

        projector = ArtifactGraphProjector(store)
        with use_event_emitter(emitter):
            await projector.project(env)

        assert store._nodes["inf_single"]["label"] == "TheoryInference"
        triples = {
            (e["from_id"], e["relation_type"], e["to_id"])
            for e in store._generic_relations
        }
        assert ("p1", "HAS_PREMISE", "inf_single") in triples
        assert ("p2", "HAS_PREMISE", "inf_single") in triples
        assert ("inf_single", "CONCLUDES", "c1") in triples
        assert any(
            isinstance(e, ArtifactProjected) and e.success for e in recorder.events
        )


class TestPhase6TheoryNetProjectorHypergraph:
    """Verify TheoryNetProjector end-to-end integration with Phase6Config.conjunctive_t_norm."""

    def test_theorynet_projector_respects_t_norm_and_undercuts_end_to_end(self) -> None:
        atoms = [
            _atom("law", "Universal law", modal=0.9, ctype="CoreAxiom"),
            _atom("cond_true", "Present condition", modal=0.5, ctype="ObservationUnit"),
            _atom(
                "cond_false", "Falsified condition", modal=0.0, ctype="ObservationUnit"
            ),
            _atom(
                "conc_active",
                "Supported conclusion",
                modal=0.2,
                ctype="EmpiricalStatement",
            ),
            _atom(
                "conc_falsified",
                "Blocked conclusion",
                modal=0.2,
                ctype="EmpiricalStatement",
            ),
            _atom("undercutter", "Methodological defeater", modal=1.0, ctype="Claim"),
        ]
        rels = [
            TheoryRelation(
                id="inf_active",
                source_id="law",
                premise_ids=("law", "cond_true"),
                target_id="conc_active",
                relation_type="SUPPORTS",
                confidence=1.0,
                scope="global",
                inferential_warrant=0.8,
                perception_stance_prob=1.0,
            ),
            TheoryRelation(
                id="inf_blocked",
                source_id="law",
                premise_ids=("law", "cond_false"),
                target_id="conc_falsified",
                relation_type="SUPPORTS",
                confidence=1.0,
                scope="global",
                inferential_warrant=0.8,
                perception_stance_prob=1.0,
            ),
        ]
        view = Phase4ArtifactsView(theory_atoms=atoms, theory_relations=rels)

        proj_prod = TheoryNetProjector(t_norm="product")
        proj_godel = TheoryNetProjector(t_norm="godel")
        assert proj_prod.fingerprint() != proj_godel.fingerprint()
        assert Phase6Config().conjunctive_t_norm == "product"

        net_prod = proj_prod.project(view)
        net_godel = proj_godel.project(view)

        by_id_prod = {a.id: a.equilibrium_strength for a in net_prod.atoms}
        by_id_godel = {a.id: a.equilibrium_strength for a in net_godel.atoms}

        # Falsified boundary condition blocks support in both t-norms
        assert by_id_prod["conc_falsified"] == pytest.approx(0.2, abs=1e-5)
        assert by_id_godel["conc_falsified"] == pytest.approx(0.2, abs=1e-5)
        # Godel min(0.9, 0.5)=0.5 > Product 0.9*0.5=0.45
        assert by_id_godel["conc_active"] > by_id_prod["conc_active"]

        # Adding an undercutter targeting inf_active reduces conc_active without dropping below 0.2
        undercut_rels = rels + [
            TheoryRelation(
                source_id="undercutter",
                target_id="inf_active",
                undercuts_relation_id="inf_active",
                relation_type="UNDERCUTS",
                confidence=1.0,
                scope="global",
                inferential_warrant=1.0,
                perception_stance_prob=1.0,
            )
        ]
        net_undercut = proj_prod.project(
            Phase4ArtifactsView(theory_atoms=atoms, theory_relations=undercut_rels)
        )
        by_id_und = {a.id: a.equilibrium_strength for a in net_undercut.atoms}
        assert 0.2 < by_id_und["conc_active"] < by_id_prod["conc_active"]


class TestSingleEnvelopeAndStoreRoundTrip:
    """Verify single-envelope projection, schema/prompt sync, and store round-trips."""

    def test_backs_in_default_schema_and_prompts_updated(self) -> None:
        assert "BACKS" in DEFAULT_SCHEMA.argument_relation_types
        assert "BACKS" in DEFAULT_SCHEMA.argument_relation_definitions
        assert DEFAULT_SCHEMA.relation_polarities["BACKS"] == 1
        assert "premise_ids" in ACC_DIRECT_PROMPT
        assert "undercuts_relation_id" in ACC_DIRECT_PROMPT
        assert "undercuts_relation_id" in ACC_REASONING_PROMPT
        assert "premise_ids" in ACC_FORMAT_PROMPT
        assert "undercuts_relation_id" in ACC_FORMAT_PROMPT

    async def test_single_envelope_projection_and_in_memory_roundtrip(self) -> None:
        store = InMemoryGraphStore()
        projector = ArtifactGraphProjector(store, t_norm="godel")

        atoms = [_atom("p1"), _atom("p2"), _atom("c1"), _atom("b1"), _atom("u1")]
        for atom in atoms:
            await projector.project(
                build_theory_atom_artifact(
                    atom, run_id="r1", phase_name="p4", method="m"
                )
            )

        rels = [
            TheoryRelation(
                source_id="p1",
                target_id="c1",
                relation_type="SUPPORTS",
                confidence=0.9,
                scope="local",
            ),
            TheoryRelation(
                source_id="p1",
                premise_ids=("p1", "p2"),
                target_id="c1",
                relation_type="SUPPORTS",
                confidence=0.85,
                scope="local",
            ),
            TheoryRelation(
                id="inf_w",
                source_id="p2",
                premise_ids=("p2",),
                target_id="c1",
                relation_type="ENTAILS",
                confidence=0.95,
                scope="local",
            ),
            TheoryRelation(
                source_id="b1",
                target_id="inf_w",
                relation_type="SUPPORTS",
                confidence=0.8,
                scope="local",
            ),
            TheoryRelation(
                source_id="u1",
                target_id="c1",
                undercuts_relation_id="inf_w",
                relation_type="UNDERCUTS",
                confidence=0.75,
                scope="local",
            ),
        ]
        for rel in rels:
            await projector.project(
                build_theory_relation_artifact(
                    rel, run_id="r1", phase_name="p4", method="m"
                )
            )

        recovered = await store.get_all_theory_relations()
        assert len(recovered) == 5

        by_sig = {
            (
                r.id,
                r.source_id,
                r.premise_ids,
                r.relation_type,
                r.target_id,
                r.undercuts_relation_id,
            ): r
            for r in recovered
        }
        # Auto-ID conjunctive relation preserves id=None and t_norm metadata without leaking IDs
        conj_key = (None, "p1", ("p1", "p2"), "SUPPORTS", "c1", None)
        assert conj_key in by_sig
        assert store._nodes[by_sig[conj_key].relation_id]["t_norm"] == "godel"

        # Single-envelope undercutter targeting existing inf_w does not wipe inf_w properties
        assert ("inf_w", "p2", ("p2",), "ENTAILS", "c1", None) in by_sig
        assert (None, "b1", (), "SUPPORTS", "inf_w", None) in by_sig
        assert (None, "u1", (), "UNDERCUTS", "c1", "inf_w") in by_sig

    async def test_neo4j_get_all_theory_relations_roundtrip_and_labels(self) -> None:
        assert "TheoryInference" in _NON_ENTITY_LABELS

        captured_queries: list[str] = []
        mock_result = AsyncMock()
        mock_result.data.return_value = [
            {
                "source_id": "p1",
                "relation_type": "SUPPORTS",
                "target_id": "c1",
                "confidence": 0.9,
                "scope": "global",
                "weight": 0.8,
                "edge_tenability": 0.7,
                "props": None,
            },
            {
                "source_id": "p1",
                "relation_type": "SUPPORTS",
                "target_id": "c1",
                "confidence": 0.9,
                "scope": "global",
                "weight": 0.8,
                "edge_tenability": None,
                "props": {
                    "id": "argument-relation::p1+p2::SUPPORTS::c1",
                    "has_explicit_id": False,
                    "source_id": "p1",
                    "relation_type": "SUPPORTS",
                    "target_id": "c1",
                    "premise_ids": ["p1", "p2"],
                    "has_explicit_premise_ids": True,
                },
            },
            {
                "source_id": "b1",
                "relation_type": "SUPPORTS",
                "target_id": "c1",
                "confidence": 0.8,
                "scope": "local",
                "weight": 0.6,
                "edge_tenability": None,
                "props": {
                    "relation_type": "SUPPORTS",
                    "target_id": "c1",
                    "undercuts_relation_id": "inf_w",
                },
            },
        ]
        mock_session = AsyncMock()

        async def _run(query: str, **_: object) -> AsyncMock:
            captured_queries.append(query)
            return mock_result

        mock_session.run = _run
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        store = object.__new__(Neo4jGraphReader)
        store._session = lambda: mock_cm  # type: ignore[method-assign]

        rels = await store.get_all_theory_relations()
        assert len(captured_queries) == 1
        assert "r.edge_tenability as edge_tenability" in captured_queries[0]
        assert "UNION ALL" in captured_queries[0]
        assert len(rels) == 3

        conj = next(r for r in rels if r.premise_ids == ("p1", "p2"))
        assert conj.id is None
        back = next(r for r in rels if r.source_id == "b1")
        assert back.relation_type == "SUPPORTS"
        assert back.undercuts_relation_id == "inf_w"


class TestPhase4AndEnrichmentHypergraphPreservation:
    """Verify fixed-point local relation validation and collision-free keys."""

    def test_fixed_point_local_relation_filtering_and_chain_pruning(self) -> None:
        valid_atoms = {"p1", "p2", "c1", "u1", "u2"}
        r_valid_conj = TheoryRelation(
            id="inf_keep",
            source_id="p1",
            premise_ids=("p1", "p2"),
            target_id="c1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        )
        r_bad_conj = TheoryRelation(
            id="inf_drop",
            source_id="p1",
            premise_ids=("p1", "missing_atom"),
            target_id="c1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        )
        r_und_keep_1 = TheoryRelation(
            id="u_rel_1",
            source_id="u1",
            target_id="c1",
            undercuts_relation_id="inf_keep",
            relation_type="UNDERCUTS",
            confidence=0.9,
            scope="local",
        )
        r_und_keep_2 = TheoryRelation(
            id="u_rel_2",
            source_id="u2",
            target_id="u_rel_1",
            undercuts_relation_id="u_rel_1",
            relation_type="UNDERCUTS",
            confidence=0.9,
            scope="local",
        )
        r_und_drop_1 = TheoryRelation(
            id="u_dead_1",
            source_id="u1",
            target_id="c1",
            undercuts_relation_id="inf_drop",
            relation_type="UNDERCUTS",
            confidence=0.9,
            scope="local",
        )
        r_und_drop_2 = TheoryRelation(
            id="u_dead_2",
            source_id="u2",
            target_id="u_dead_1",
            undercuts_relation_id="u_dead_1",
            relation_type="UNDERCUTS",
            confidence=0.9,
            scope="local",
        )

        # Put second-order modifiers BEFORE their targets to ensure order-independent fixed-point
        retained = _filter_valid_local_relations(
            [
                r_und_drop_2,
                r_und_keep_2,
                r_und_drop_1,
                r_und_keep_1,
                r_bad_conj,
                r_valid_conj,
            ],
            valid_atoms,
        )
        retained_ids = [r.relation_id for r in retained]
        assert retained_ids == ["u_rel_2", "u_rel_1", "inf_keep"]

    def test_enrichment_rel_key_distinguishes_conjunctive_and_modifier_variants(
        self,
    ) -> None:
        pairwise = TheoryRelation(
            source_id="p1",
            target_id="c1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        )
        conj_a = TheoryRelation(
            source_id="p1",
            premise_ids=("p1", "p2"),
            target_id="c1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        )
        conj_b = TheoryRelation(
            source_id="p1",
            premise_ids=("p1", "p3"),
            target_id="c1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        )
        und_a = TheoryRelation(
            source_id="u1",
            target_id="c1",
            undercuts_relation_id="w1",
            relation_type="UNDERCUTS",
            confidence=0.9,
            scope="local",
        )
        und_b = TheoryRelation(
            source_id="u1",
            target_id="c1",
            undercuts_relation_id="w2",
            relation_type="UNDERCUTS",
            confidence=0.9,
            scope="local",
        )

        assert _enrichment_rel_key(pairwise) == "p1->SUPPORTS->c1"
        keys = {
            _enrichment_rel_key(r) for r in (pairwise, conj_a, conj_b, und_a, und_b)
        }
        assert len(keys) == 5
