"""Test suite for TheoryNet calibrated projection and QBAF propagation (Stage 5 / ISSUE-041).

Verifies that:
1. TheoryRelation domain contracts serialize and preserve calibrated confidence and probability distributions.
2. Propositional modal strength M(phi) is properly decoupled from extraction confidence P(stance).
3. Empirical accuracy serves as an admissibility gate.
4. Phase 6 projection writes calibrated attributes (effective_weight, weight_support, weight_attack) to graph edges.
5. Calibration metrics (ECE, Brier score) are reported in evaluation runs.
"""

from __future__ import annotations

import pytest
from episteme_pipeline.artifacts.builders import (
    build_argument_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase4ArtifactsView,
)
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryNet, TheoryRelation
from episteme_pipeline.evaluation.strategies import ArgumentationStrategy
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner
from episteme_pipeline.projection.theorynet_projector import (
    TheoryNetProjector,
    derive_atom_modality,
    derive_relation_warrant,
    get_cypher_projection_query,
)
from episteme_pipeline.schema.default_schema import SchemaConfig


class TestTheoryRelationContracts:
    """Test suite for TheoryRelation calibrated attributes and weight decoupling."""

    def test_theory_relation_calibrated_fields_defaults(self) -> None:
        """Verify default effective weight is derived as M * P."""
        rel = TheoryRelation(
            source_id="c1",
            target_id="c2",
            relation_type="SUPPORTS",
            confidence=0.8,
            scope="global",
        )
        assert rel.modal_strength == 1.0
        assert rel.class_probability is None
        assert rel.empirical_accuracy is None
        # Default effective_weight = modal_strength (1.0) * confidence (0.8)
        assert pytest.approx(rel.effective_weight) == 0.8
        assert pytest.approx(rel.weight) == 0.8

    def test_decoupling_epistemic_confidence_from_modal_strength(self) -> None:
        """Verify high extraction confidence does not inflate tentative epistemic modality."""
        # Author: 'It is conceivable that space is an illusion' (Extraction P=0.99, but Modality M=0.30)
        rel = TheoryRelation(
            source_id="speculative_hypothesis",
            target_id="space_concept",
            relation_type="SUPPORTS",
            confidence=0.99,
            class_probability=0.99,
            empirical_accuracy=0.96,
            modal_strength=0.30,
            scope="global",
            decision_engine_provider="typesafe_jev",
        )

        assert rel.class_probability == 0.99
        assert rel.empirical_accuracy == 0.96
        assert rel.modal_strength == 0.30
        # Crucial check: effective weight is M * P = 0.30 * 0.99 = 0.297, NOT 0.99!
        assert pytest.approx(rel.effective_weight, rel=1e-3) == 0.297
        assert pytest.approx(rel.weight, rel=1e-3) == 0.297
        assert rel.decision_engine_provider == "typesafe_jev"

    def test_artifact_builder_and_view_roundtrip(self) -> None:
        """Verify calibrated attributes survive serialization through the artifact system."""
        rel = TheoryRelation(
            source_id="atom_1",
            target_id="atom_2",
            relation_type="ATTACKS",
            confidence=0.88,
            class_probability=0.88,
            empirical_accuracy=0.92,
            modal_strength=0.75,
            scope="global",
            decision_engine_provider="mock_jev",
        )
        env = build_argument_relation_artifact(
            rel, run_id="run_test", phase_name="phase4", method="jev"
        )
        collection = ArtifactCollection([env])

        view = Phase4ArtifactsView.from_collection(collection)
        assert len(view.theory_relations) == 1
        restored = view.theory_relations[0]

        assert restored.source_id == "atom_1"
        assert restored.target_id == "atom_2"
        assert restored.relation_type == "ATTACKS"
        assert restored.class_probability == 0.88
        assert restored.empirical_accuracy == 0.92
        assert restored.modal_strength == 0.75
        assert pytest.approx(restored.effective_weight, rel=1e-3) == 0.75 * 0.88
        assert restored.decision_engine_provider == "mock_jev"


class TestTheoryNetProjectorCalibrated:
    """Test suite for TheoryNetProjector decoupled weights and admissibility gating."""

    def test_projector_computes_signed_effective_weights(self) -> None:
        """Verify supports has positive polarity, attacks has negative polarity."""
        proj = TheoryNetProjector()
        rel_sup = TheoryRelation(
            source_id="a1",
            target_id="a2",
            relation_type="SUPPORTS",
            confidence=0.9,
            class_probability=0.9,
            modal_strength=0.5,
            scope="global",
        )
        rel_att = TheoryRelation(
            source_id="a3",
            target_id="a2",
            relation_type="ATTACKS",
            confidence=0.8,
            class_probability=0.8,
            modal_strength=0.5,
            scope="global",
        )

        assert pytest.approx(proj.compute_relation_weight(rel_sup)) == 0.45
        assert pytest.approx(proj.compute_relation_weight(rel_att)) == -0.40

    def test_admissibility_gating_pruning(self) -> None:
        """Verify relations below admissibility threshold are pruned when configured."""
        proj_pruning = TheoryNetProjector(
            admissibility_threshold=0.75,
            prune_inadmissible=True,
        )

        atom = TheoryAtom(
            id="a1",
            text="Premise",
            component_type="ObservationUnit",
            source_chunk_id="c1",
        )
        rel_admissible = TheoryRelation(
            source_id="a1",
            target_id="a2",
            relation_type="SUPPORTS",
            confidence=0.9,
            empirical_accuracy=0.85,
            scope="global",
        )
        rel_inadmissible = TheoryRelation(
            source_id="a1",
            target_id="a3",
            relation_type="ATTACKS",
            confidence=0.9,
            empirical_accuracy=0.60,  # Below 0.75!
            scope="global",
        )

        view = Phase4ArtifactsView(
            theory_atoms=[atom],
            theory_relations=[rel_admissible, rel_inadmissible],
        )

        tnet = proj_pruning.project(view)
        assert len(tnet.relations) == 1
        assert tnet.relations[0].target_id == "a2"

    def test_admissibility_gating_flagging(self) -> None:
        """Verify relations below threshold are flagged with tenability=0.0 when not pruning."""
        proj_flagging = TheoryNetProjector(
            admissibility_threshold=0.75,
            prune_inadmissible=False,
        )

        atom = TheoryAtom(
            id="a1",
            text="Premise",
            component_type="ObservationUnit",
            source_chunk_id="c1",
        )
        rel_inadmissible = TheoryRelation(
            source_id="a1",
            target_id="a3",
            relation_type="ATTACKS",
            confidence=0.9,
            empirical_accuracy=0.50,
            scope="global",
        )

        view = Phase4ArtifactsView(
            theory_atoms=[atom],
            theory_relations=[rel_inadmissible],
        )

        tnet = proj_flagging.project(view)
        assert len(tnet.relations) == 1
        assert tnet.relations[0].tenability == 0.0

    def test_double_penalization_elimination(self) -> None:
        """Verify conjecture premise M=0.35 connected via warrant I=1.0 does not double-penalize warrant weight."""
        atom_premise = TheoryAtom(
            id="p_conjecture",
            text="Conjecture premise",
            component_type="TentativeConjecture",
            modal_strength=0.35,
            source_chunk_id="c1",
        )
        atom_conclusion = TheoryAtom(
            id="c_target",
            text="Conclusion target",
            component_type="TheoreticalHypothesis",
            base_score=0.5,
            source_chunk_id="c1",
        )
        rel_deductive = TheoryRelation(
            source_id="p_conjecture",
            target_id="c_target",
            relation_type="ENTAILS",
            inferential_force=1.0,
            confidence=1.0,
            scope="global",
        )

        view = Phase4ArtifactsView(
            theory_atoms=[atom_premise, atom_conclusion],
            theory_relations=[rel_deductive],
        )

        proj = TheoryNetProjector()
        tnet = proj.project(view)

        # Inferential warrant force on the edge must NOT be scaled down by atom modal strength (no 0.35 * 0.35)
        projected_rel = tnet.relations[0]
        assert projected_rel.active_weight == 1.0
        assert projected_rel.inferential_force == 1.0

        # Conclusion's plausibility increases mediated strictly by premise's justification degree (s_p <= 0.35)
        # under warrant weight W = 1.0
        c_projected = next(a for a in tnet.atoms if a.id == "c_target")
        assert c_projected.plausibility > 0.5

    def test_upstream_heuristic_mappings(self) -> None:
        """Verify Phase 6 heuristic mappings assign expected modal strength and warrant validity."""
        axiom = TheoryAtom(id="a1", text="Axiom", component_type="CoreAxiom", source_chunk_id="c1")
        obs = TheoryAtom(id="a2", text="Obs", component_type="ObservationUnit", source_chunk_id="c1")
        hyp_ana = TheoryAtom(id="a3", text="Hyp", component_type="TheoreticalHypothesis", epistemic_status="Analytisch", source_chunk_id="c1")
        hyp_syn = TheoryAtom(id="a4", text="Hyp", component_type="TheoreticalHypothesis", epistemic_status="Synthetisch", source_chunk_id="c1")
        conj = TheoryAtom(id="a5", text="Conjecture", component_type="TentativeConjecture", source_chunk_id="c1")

        assert derive_atom_modality(axiom) == 1.0
        assert derive_atom_modality(obs) == 0.85
        assert derive_atom_modality(hyp_ana) == 0.75
        assert derive_atom_modality(hyp_syn) == 0.60
        assert derive_atom_modality(conj) == 0.35

        rel_ded = TheoryRelation(source_id="1", target_id="2", relation_type="DEDUCES", confidence=1.0, scope="global")
        rel_sup = TheoryRelation(source_id="1", target_id="2", relation_type="SUPPORTS", confidence=1.0, scope="global")
        rel_und = TheoryRelation(source_id="1", target_id="2", relation_type="UNDERCUTS", confidence=1.0, scope="global")
        rel_ana = TheoryRelation(source_id="1", target_id="2", relation_type="ANALOGY", confidence=1.0, scope="global")

        assert derive_relation_warrant(rel_ded) == 1.0
        assert derive_relation_warrant(rel_sup) == 0.75
        assert derive_relation_warrant(rel_und) == 0.60
        assert derive_relation_warrant(rel_ana) == 0.40

    def test_cypher_projection_query_modes(self) -> None:
        """Verify Cypher projection query generation differentiates hard database pruning vs soft passthrough."""
        q_hard = get_cypher_projection_query(graph_name="test_hard", admissibility_mode="hard", tau_p="$tau_p", tau_c="$tau_c")
        assert "WHERE r.stance_probability >= $tau_p AND r.model_confidence >= $tau_c" in q_hard
        assert "r.inferential_force AS weight" in q_hard

        q_soft = get_cypher_projection_query(graph_name="test_soft", admissibility_mode="soft", tau_p="$tau_p", tau_c="$tau_c")
        assert "WHERE r.stance_probability" not in q_soft
        assert "r.inferential_force AS inferential_force" in q_soft
        assert "r.stance_probability AS stance_probability" in q_soft
        assert "r.model_confidence AS model_confidence" in q_soft


@pytest.mark.asyncio
class TestPhase6RunnerProjection:
    """Test suite for Phase6Runner projection writing properties to graph store."""

    async def test_phase6_projects_calibrated_properties_to_store(self) -> None:
        """Verify Neo4j/In-Memory store receives all decoupled and calibrated properties."""
        graph_store = InMemoryGraphStore()

        atom1 = TheoryAtom(
            id="atom_premise",
            text="Empirical observation data",
            component_type="ObservationUnit",
            source_chunk_id="chk1",
            plausibility=0.9,
        )
        atom2 = TheoryAtom(
            id="atom_conclusion",
            text="Theoretical hypothesis",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chk1",
            plausibility=0.5,
        )
        rel = TheoryRelation(
            source_id="atom_premise",
            target_id="atom_conclusion",
            relation_type="SUPPORTS",
            confidence=0.95,
            class_probability=0.95,
            empirical_accuracy=0.92,
            modal_strength=0.80,
            scope="global",
            decision_engine_provider="typesafe_jev",
        )

        view = Phase4ArtifactsView(
            theory_atoms=[atom1, atom2],
            theory_relations=[rel],
        )

        runner = Phase6Runner(
            config={"admissibility_threshold": 0.50},
            schema=SchemaConfig(),
            graph_store=graph_store,
        )
        from episteme_pipeline.artifacts.execution import PipelineInput
        from episteme_pipeline.runs.models import RunManifest

        ctx = ArtifactExecutionContext(
            run_id="run_p6_test",
            manifest=RunManifest(run_id="run_p6_test"),
            pipeline_input=PipelineInput(source_paths=[]),
            previous=None,
        )

        await runner.run(view, ctx)

        # Check graph store relations
        all_rels = await graph_store.get_all_theory_relations()
        assert len(all_rels) == 1
        stored_rel = all_rels[0]

        assert stored_rel.source_id == "atom_premise"
        assert stored_rel.target_id == "atom_conclusion"
        assert stored_rel.relation_type == "SUPPORTS"

        assert stored_rel.class_probability == 0.95
        assert stored_rel.empirical_accuracy == 0.92
        assert stored_rel.modal_strength == 0.80
        assert pytest.approx(stored_rel.effective_weight, rel=1e-3) == 0.76
        assert stored_rel.decision_engine_provider == "typesafe_jev"

        # Check raw upserted relation properties
        raw_rels = graph_store._generic_relations
        assert len(raw_rels) == 1
        props = raw_rels[0]["properties"]

        assert props["calibrated_confidence"] == 0.92
        assert props["class_probability"] == 0.95
        assert props["empirical_accuracy"] == 0.92
        assert props["modal_strength"] == 0.80
        # effective_weight = 0.80 * 0.95 = 0.76
        assert pytest.approx(props["effective_weight"], rel=1e-3) == 0.76
        assert pytest.approx(props["weight_support"], rel=1e-3) == 0.76
        assert props["weight_attack"] == 0.0
        assert props["decision_engine_provider"] == "typesafe_jev"
        assert props["decision_engine_provider"] == "typesafe_jev"


@pytest.mark.asyncio
class TestEvaluationCalibrationMetrics:
    """Test suite for calibration metrics integration in evaluation runs."""

    async def test_argumentation_strategy_computes_ece_and_brier(self) -> None:
        """Verify ArgumentationStrategy reports ECE and Brier Score on predicted relations."""
        pred_rel1 = TheoryRelation(
            source_id="c1",
            target_id="c2",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="global",
        )
        pred_rel2 = TheoryRelation(
            source_id="c1",
            target_id="c3",
            relation_type="ATTACKS",
            confidence=0.8,
            scope="global",
        )

        gold_rel = TheoryRelation(
            source_id="c1",
            target_id="c2",
            relation_type="SUPPORTS",
            confidence=1.0,
            scope="global",
        )

        atom1 = TheoryAtom(id="c1", text="text 1", component_type="ObservationUnit", source_chunk_id="1")
        atom2 = TheoryAtom(id="c2", text="text 2", component_type="ObservationUnit", source_chunk_id="1")
        atom3 = TheoryAtom(id="c3", text="text 3", component_type="ObservationUnit", source_chunk_id="1")

        pred_net = TheoryNet(atoms=[atom1, atom2, atom3], relations=[pred_rel1, pred_rel2])
        gold_net = TheoryNet(atoms=[atom1, atom2], relations=[gold_rel])

        strategy = ArgumentationStrategy()
        results = await strategy.evaluate(pred_net, gold_net, run_id="run_eval_test")

        assert len(results) == 1
        res = results[0]
        metric_names = {m.name for m in res.metrics}

        assert "ece" in metric_names
        assert "brier_score" in metric_names
        assert "mce" in metric_names
        assert res.reliability_diagram is not None
