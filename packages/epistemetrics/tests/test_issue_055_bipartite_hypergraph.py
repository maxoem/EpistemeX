"""Deterministic tests for ISSUE-055: Bipartite Inference Hypergraph in epistemetrics.

Verifies conjunctive t-norm aggregation (Product and Godel), Pollockian
undercutters, Toulmin backing, cyclic ODE convergence, closed-form vs. ODE
parity, exact pairwise equivalence on 1-premise unmodified inferences, and
error/edge-case handling.
"""

from __future__ import annotations

import numpy as np
import pytest
from epistemetrics.core.models import (
    EpistemicStatus,
    NodeType,
    RelationType,
    TheoryEdge,
)
from epistemetrics.epistemic.qbaf import (
    GradualSemanticsModel,
    HyperedgeSpec,
    QBAFGradualSemanticsSolver,
    WeightedQuadraticEnergySolver,
    WeightNormalizationMode,
    solve_continuous_qbaf,
    solve_qbaf_gradual_semantics,
)
from epistemetrics.graph.theory_graph import TheoryGraph


def _quadratic_impact(x: float) -> float:
    pos = max(x, 0.0)
    return (pos * pos) / (1.0 + pos * pos)


def _quadratic_update(w0: float, e: float) -> float:
    return w0 + (1.0 - w0) * _quadratic_impact(e) - w0 * _quadratic_impact(-e)


def _discrete_quadratic_update(w0: float, s: float, a: float = 0.0) -> float:
    return w0 + (1.0 - w0) * (s / (1.0 + s)) - w0 * (a / (1.0 + a))


class TestConjunctiveTNormSemantics:
    """Verify conjunctive (linked) premise aggregation under Product and Godel t-norms."""

    @pytest.mark.parametrize("use_continuous", [True, False])
    @pytest.mark.parametrize("t_norm", ["product", "godel"])
    def test_falsified_conjunctive_premise_eliminates_support(
        self, use_continuous: bool, t_norm: str
    ) -> None:
        """If boundary condition B1 == 0, Law L transmits zero support to C."""
        nodes = {"L": 0.9, "B1": 0.0, "C": 0.2}
        conj_edge = TheoryEdge(
            id="inf_deduction",
            source="L",
            premise_ids=("L", "B1"),
            target="C",
            relation_type=RelationType.EXPLAINS,
            polarity=1,
            weight=1.0,
            inferential_force=0.9,
            effective_weight=0.9,
        )

        solver = QBAFGradualSemanticsSolver(
            semantics_model=GradualSemanticsModel.QUADRATIC,
            use_continuous=use_continuous,
            t_norm=t_norm,
            tolerance=1e-7,
            max_iterations=200,
        )
        res = solver.solve(nodes=nodes, edges=[conj_edge])

        assert res.converged is True
        # Conjunctive activation is 0.0 -> C remains strictly at its prior 0.2
        assert res.degrees["C"] == pytest.approx(0.2, abs=1e-5)
        assert res.support_sums["C"] == pytest.approx(0.0, abs=1e-6)
        assert res.warrant_states["inf_deduction"] == pytest.approx(0.9, abs=1e-5)

        # Contrast: naive independent pairwise decomposition falsely elevates C > 0.2
        pairwise_res = solver.solve(
            nodes=nodes,
            edges=[
                TheoryEdge(source="L", target="C", polarity=1, effective_weight=0.9),
                TheoryEdge(source="B1", target="C", polarity=1, effective_weight=0.9),
            ],
        )
        assert pairwise_res.degrees["C"] > 0.45

    @pytest.mark.parametrize("use_continuous", [True, False])
    def test_product_vs_godel_partial_conjunctive_activation(
        self, use_continuous: bool
    ) -> None:
        """Verify Product (s_L * s_B1) and Godel (min(s_L, s_B1)) analytical equilibria."""
        nodes = {"L": 0.9, "B1": 0.5, "C": 0.2}
        conj_edge = TheoryEdge(
            id="inf_conj",
            source="L",
            premise_ids=("L", "B1"),
            target="C",
            relation_type=RelationType.SUPPORTS,
            polarity=1,
            weight=0.8,
            inferential_force=0.8,
            effective_weight=0.8,
        )

        res_prod = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=[conj_edge],
            continuous=use_continuous,
            t_norm="product",
            tolerance=1e-7,
            max_iterations=200,
        )
        res_godel = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=[conj_edge],
            continuous=use_continuous,
            t_norm="godel",
            tolerance=1e-7,
            max_iterations=200,
        )

        expected_e_prod = 0.8 * (0.9 * 0.5)
        expected_e_godel = 0.8 * min(0.9, 0.5)
        if use_continuous:
            expected_c_prod = _quadratic_update(0.2, expected_e_prod)
            expected_c_godel = _quadratic_update(0.2, expected_e_godel)
        else:
            expected_c_prod = _discrete_quadratic_update(0.2, expected_e_prod)
            expected_c_godel = _discrete_quadratic_update(0.2, expected_e_godel)

        assert res_prod.degrees["C"] == pytest.approx(expected_c_prod, abs=1e-5)
        assert res_godel.degrees["C"] == pytest.approx(expected_c_godel, abs=1e-5)
        assert res_godel.degrees["C"] > res_prod.degrees["C"]

        # Convenience continuous helper should agree identically with Product
        if use_continuous:
            res_cont_fn = solve_continuous_qbaf(
                nodes=nodes, edges=[conj_edge], t_norm="godel", tolerance=1e-7
            )
            assert res_cont_fn.degrees["C"] == pytest.approx(expected_c_godel, abs=1e-5)


class TestUndercuttersAndToulminBacking:
    """Verify Pollockian undercutters and Toulmin backing via warrant dynamics."""

    @pytest.mark.parametrize("use_continuous", [True, False])
    def test_pollockian_undercutter_neutralizes_inference_without_below_prior_rebuttal(
        self, use_continuous: bool
    ) -> None:
        """Strong undercutter suppresses inference P -> C back toward tau_0(C), never below."""
        nodes = {"P": 1.0, "C": 0.3, "U": 1.0}
        primary = TheoryEdge(
            id="inf_1",
            source="P",
            target="C",
            relation_type=RelationType.SUPPORTS,
            polarity=1,
            inferential_force=0.75,
            active_weight=0.75,
            effective_weight=0.75,
        )
        moderate_undercutter = TheoryEdge(
            source="U",
            target="inf_1",
            undercuts_relation_id="inf_1",
            relation_type=RelationType.ATTACKS,
            polarity=-1,
            inferential_force=1.0,
            effective_weight=1.0,
        )
        strong_undercutter = TheoryEdge(
            source="U",
            target="",
            undercuts_relation_id="inf_1",
            relation_type=RelationType.ATTACKS,
            polarity=-1,
            inferential_force=1.0,
            effective_weight=10.0,
        )

        solver = QBAFGradualSemanticsSolver(
            use_continuous=use_continuous,
            tolerance=1e-7,
            max_iterations=200,
        )
        baseline = solver.solve(nodes={"P": 1.0, "C": 0.3}, edges=[primary])
        mod_res = solver.solve(nodes=nodes, edges=[primary, moderate_undercutter])
        strong_res = solver.solve(nodes=nodes, edges=[primary, strong_undercutter])

        # Warrant prior drops from 0.75 to 0.75 - 0.75 * h(1.0) = 0.375
        assert mod_res.warrant_states["inf_1"] == pytest.approx(0.375, abs=1e-5)
        assert 0.3 < mod_res.degrees["C"] < baseline.degrees["C"]

        # Strong undercutter drives warrant down sharply per exact semantics and leaves C >= tau_0(C)
        expected_strong_warrant = (
            _quadratic_update(0.75, -10.0)
            if use_continuous
            else _discrete_quadratic_update(0.75, 0.0, a=10.0)
        )
        assert strong_res.warrant_states["inf_1"] == pytest.approx(
            expected_strong_warrant, abs=1e-5
        )
        assert strong_res.degrees["C"] >= 0.3
        assert strong_res.degrees["C"] < mod_res.degrees["C"]
        # P and U are unattacked premises/undercutters, untouched at priors
        assert strong_res.degrees["P"] == pytest.approx(1.0, abs=1e-6)
        assert strong_res.degrees["U"] == pytest.approx(1.0, abs=1e-6)
        # Reified warrant ID must NEVER pollute atom degree dictionary
        assert "inf_1" not in strong_res.degrees

    @pytest.mark.parametrize("use_continuous", [True, False])
    def test_toulmin_backing_strengthens_weak_warrant(
        self, use_continuous: bool
    ) -> None:
        """Toulmin backing targeting a warrant elevates s(w_k) and downstream conclusion C."""
        nodes = {"P": 1.0, "C": 0.2, "Bk": 1.0}
        weak_inference = TheoryEdge(
            id="inf_backed",
            source="P",
            target="C",
            relation_type=RelationType.SUPPORTS,
            polarity=1,
            inferential_force=0.25,
            active_weight=0.25,
            effective_weight=0.25,
        )
        backing = TheoryEdge(
            source="Bk",
            target="inf_backed",
            relation_type=RelationType.SUPPORTS,
            polarity=1,
            inferential_force=1.0,
            effective_weight=2.0,
        )

        solver = QBAFGradualSemanticsSolver(
            use_continuous=use_continuous,
            tolerance=1e-7,
            max_iterations=200,
        )
        unbacked = solver.solve(nodes={"P": 1.0, "C": 0.2}, edges=[weak_inference])
        backed = solver.solve(nodes=nodes, edges=[weak_inference, backing])

        expected_warrant = (
            _quadratic_update(0.25, 2.0)
            if use_continuous
            else _discrete_quadratic_update(0.25, 2.0)
        )
        assert backed.warrant_states["inf_backed"] == pytest.approx(
            expected_warrant, abs=1e-5
        )
        assert backed.warrant_states["inf_backed"] > 0.25
        assert backed.degrees["C"] > unbacked.degrees["C"]

    def test_competing_backing_and_undercutter_balance(self) -> None:
        """Equal backing and undercutter cancel warrant energy: E_w = 0 => s(w) = w0."""
        nodes = {"P": 1.0, "C": 0.2, "Bk": 0.8, "U": 0.8}
        primary = TheoryEdge(
            id="inf_bal",
            source="P",
            target="C",
            polarity=1,
            inferential_force=0.6,
            active_weight=0.6,
            effective_weight=0.6,
        )
        backing = TheoryEdge(
            source="Bk",
            target="inf_bal",
            polarity=1,
            effective_weight=1.0,
        )
        undercutter = TheoryEdge(
            source="U",
            target="inf_bal",
            undercuts_relation_id="inf_bal",
            relation_type=RelationType.ATTACKS,
            polarity=-1,
            effective_weight=1.0,
        )
        solver = QBAFGradualSemanticsSolver(use_continuous=True, tolerance=1e-7)
        res = solver.solve(nodes=nodes, edges=[primary, backing, undercutter])
        assert res.warrant_states["inf_bal"] == pytest.approx(0.6, abs=1e-5)

    def test_conjunctive_undercutter_only_fires_when_both_conditions_hold(self) -> None:
        """An undercutter itself can carry conjunctive premises (U1 AND U2)."""
        primary = TheoryEdge(
            id="inf_target",
            source="P",
            target="C",
            polarity=1,
            inferential_force=0.8,
            effective_weight=0.8,
        )
        conj_undercut = TheoryEdge(
            source="U1",
            premise_ids=("U1", "U2"),
            target="inf_target",
            undercuts_relation_id="inf_target",
            relation_type=RelationType.ATTACKS,
            polarity=-1,
            effective_weight=2.0,
        )
        solver = QBAFGradualSemanticsSolver(use_continuous=True, tolerance=1e-7)

        inactive = solver.solve(
            nodes={"P": 1.0, "C": 0.2, "U1": 1.0, "U2": 0.0},
            edges=[primary, conj_undercut],
        )
        active = solver.solve(
            nodes={"P": 1.0, "C": 0.2, "U1": 1.0, "U2": 1.0},
            edges=[primary, conj_undercut],
        )
        assert inactive.warrant_states["inf_target"] == pytest.approx(0.8, abs=1e-5)
        assert active.warrant_states["inf_target"] < 0.3
        assert active.degrees["C"] < inactive.degrees["C"]


class TestSolverEquivalenceAndDynamics:
    """Verify exact pairwise reduction, cyclic ODE convergence, and TheoryGraph helpers."""

    def test_unary_unmodified_hyperedge_reduces_identically_to_pairwise(self) -> None:
        """Single-premise unmodified HyperedgeSpec matches pairwise g_supp identically."""
        w = np.array([0.85, 0.3, 0.6], dtype=np.float64)
        # Pairwise DAG: 0 -> 1 (weight 0.9), 1 -> 2 (att 0.5)
        g_supp_pw = np.zeros((3, 3), dtype=np.float64)
        g_att_pw = np.zeros((3, 3), dtype=np.float64)
        g_supp_pw[0, 1] = 0.9
        g_att_pw[1, 2] = 0.5

        # Same DAG with 0 -> 1 reified as a 1-premise HyperedgeSpec (w0=0.6, gate=0.9/0.6)
        g_supp_hy = np.zeros((3, 3), dtype=np.float64)
        spec = HyperedgeSpec(
            warrant_id="w_equiv",
            premise_indices=(0,),
            target_idx=1,
            polarity=1,
            base_warrant=0.6,
            gate_factor=0.9 / 0.6,
        )

        ode = WeightedQuadraticEnergySolver()
        s_pw, conv_pw, tel_pw = ode.solve(w, g_supp_pw, g_att_pw)
        s_hy, conv_hy, tel_hy = ode.solve(w, g_supp_hy, g_att_pw, hyperedges=[spec])

        assert conv_pw and conv_hy
        assert np.allclose(s_pw, s_hy, atol=1e-10)
        assert np.allclose(tel_pw["support_energy"], tel_hy["support_energy"], atol=1e-10)
        assert np.allclose(tel_pw["attack_energy"], tel_hy["attack_energy"], atol=1e-10)
        assert np.allclose(tel_pw["volatility_index"], tel_hy["volatility_index"], atol=1e-10)
        assert float(tel_hy["warrant_states"][0]) == pytest.approx(0.6, abs=1e-10)

    def test_cyclic_bipartite_hypergraph_ode_converges_to_stationary_point(self) -> None:
        """Feedback cycle (A & B) -> C -> U -| inf_1 converges in augmented ODE integration."""
        w = np.array([0.8, 0.9, 0.25, 0.3], dtype=np.float64)  # A=0, B=1, C=2, U=3
        g_supp = np.zeros((4, 4), dtype=np.float64)
        g_att = np.zeros((4, 4), dtype=np.float64)
        # Conclusion C positively drives undercutter U, creating feedback onto inf_1
        g_supp[2, 3] = 1.2
        spec = HyperedgeSpec(
            warrant_id="inf_cyclic",
            premise_indices=(0, 1),
            target_idx=2,
            polarity=1,
            base_warrant=0.8,
            gate_factor=1.0,
            undercut_edges=(((3,), 1.0),),
        )
        ode = WeightedQuadraticEnergySolver(rtol=1e-6, atol=1e-8, t_norm="product")
        s_final, converged, telemetry = ode.solve(w, g_supp, g_att, hyperedges=[spec])

        assert converged is True
        assert telemetry["warrant_states"].shape == (1,)
        s_aug = np.concatenate([s_final, telemetry["warrant_states"]])
        deriv = ode._derivatives(0.0, s_aug, w, g_supp.T, g_att.T, hyperedges=[spec])
        assert np.max(np.abs(deriv)) < 1e-3

        # Both continuous QBAFGradualSemanticsSolver and discrete solver converge on feedback cycle
        common_edges = [
            TheoryEdge(
                id="inf_cyclic",
                source="A",
                premise_ids=("A", "B"),
                target="C",
                polarity=1,
                inferential_force=0.8,
                active_weight=0.8,
                effective_weight=0.8,
            ),
            TheoryEdge(source="C", target="U", polarity=1, effective_weight=1.2),
            TheoryEdge(
                source="U",
                target="inf_cyclic",
                undercuts_relation_id="inf_cyclic",
                relation_type=RelationType.ATTACKS,
                polarity=-1,
                effective_weight=1.0,
            ),
        ]
        node_priors = {"A": 0.8, "B": 0.9, "C": 0.25, "U": 0.3}

        solver_cont = QBAFGradualSemanticsSolver(
            use_continuous=True, tolerance=1e-7, max_iterations=200, t_norm="product"
        )
        res_cont = solver_cont.solve(nodes=node_priors, edges=common_edges)
        assert res_cont.converged is True
        assert res_cont.degrees["C"] == pytest.approx(float(s_final[2]), abs=1e-5)
        assert res_cont.warrant_states["inf_cyclic"] == pytest.approx(
            float(telemetry["warrant_states"][0]), abs=1e-5
        )

        solver_disc = QBAFGradualSemanticsSolver(
            use_continuous=False, tolerance=1e-6, max_iterations=200, t_norm="product"
        )
        res_disc = solver_disc.solve(nodes=node_priors, edges=common_edges)
        assert res_disc.converged is True
        assert res_disc.degrees["U"] > 0.3
        assert res_disc.warrant_states["inf_cyclic"] < 0.8

    def test_theory_graph_integration_and_insertion_order_invariance(self) -> None:
        """TheoryGraph.add_edge registers premises but never materializes warrant IDs as atoms."""
        tg = TheoryGraph("HyperTest")
        tg.add_node("A", node_type=NodeType.CLAIM, base_score=0.9, epistemic_status=EpistemicStatus.NEUTRAL)
        tg.add_node("B", node_type=NodeType.CLAIM, base_score=0.9)
        tg.add_node("C", node_type=NodeType.CLAIM, base_score=0.1)
        tg.add_node("U", node_type=NodeType.CLAIM, base_score=0.9)

        # Add undercutter BEFORE target inference to verify order-independence
        tg.add_edge(
            source="U",
            target="inf_main",
            relation_type="UNDERCUTS",
            undercuts_relation_id="inf_main",
            weight=2.0,
            effective_weight=2.0,
        )
        tg.add_edge(
            source="",
            premise_ids=("A", "B"),
            target="C",
            id="inf_main",
            relation_type=RelationType.EXPLAINS,
            weight=0.8,
            inferential_force=0.8,
            effective_weight=0.8,
        )

        assert set(tg.nodes) == {"A", "B", "C", "U"}
        solver = QBAFGradualSemanticsSolver(use_continuous=True, t_norm="product")
        res = solver.solve(
            tg, normalization_mode=WeightNormalizationMode.CALIBRATED_MODAL
        )
        assert "inf_main" not in res.degrees
        assert "inf_main" in res.warrant_states
        assert res.warrant_states["inf_main"] < 0.8

    def test_failure_modes_and_fingerprinting(self) -> None:
        """Invalid t-norm raises ValueError, missing undercut targets do not crash, fingerprints vary."""
        with pytest.raises(ValueError, match="Unsupported conjunctive t-norm"):
            WeightedQuadraticEnergySolver(t_norm="lukasiewicz")  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Unsupported conjunctive t-norm"):
            QBAFGradualSemanticsSolver(t_norm="invalid")  # type: ignore[arg-type]

        fp_prod = QBAFGradualSemanticsSolver(t_norm="product").fingerprint()
        fp_godel = QBAFGradualSemanticsSolver(t_norm="godel").fingerprint()
        assert fp_prod != fp_godel
        assert fp_godel["t_norm"] == "godel"
        assert WeightedQuadraticEnergySolver(t_norm="godel").fingerprint()["t_norm"] == "godel"

        # Dangling undercutter target does not crash solver
        dangling_res = solve_qbaf_gradual_semantics(
            nodes={"U": 0.9, "C": 0.4},
            edges=[
                TheoryEdge(
                    source="U",
                    target="nonexistent_inf",
                    undercuts_relation_id="nonexistent_inf",
                    relation_type=RelationType.ATTACKS,
                    polarity=-1,
                    effective_weight=1.0,
                )
            ],
            continuous=True,
        )
        assert dangling_res.degrees["C"] == pytest.approx(0.4, abs=1e-6)
