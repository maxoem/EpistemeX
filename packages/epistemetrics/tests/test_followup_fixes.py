"""Tests verifying follow-up formal-model fixes in epistemetrics (F-04, C-01..C-07)."""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from epistemetrics import (
    AlgorithmError,
    BasePriorPolicy,
    NodeType,
    RelationType,
    TheoryGraph,
    WeightedQuadraticEnergySolver,
    compare_prior_policies,
    compute_dung_extensions,
    eigenvector_centrality,
    katz_centrality,
    louvain_communities,
    participation_coefficient,
    per_community_modularity,
    project_to_echo_network,
    reduce_bipolar_to_dung,
    signed_modularity,
    solve_continuous_qbaf,
    solve_echo_lens,
    solve_qbaf_gradual_semantics,
)


class TestVolatilityIndexAndConvergence:
    """Tests for C-01 (Volatility Index) and F-04 (Lipschitz/non-convergence)."""

    def test_volatility_distinguishes_balanced_high_prior_from_uncontested(self) -> None:
        """C-01: Balanced support+attack at high prior yields high volatility; uncontested claim yields 0."""
        # Counter-example from B-19: beta=0.9 with balanced support & attack (S+ == S- == 5.0)
        nodes_contested = {"target": 0.9, "s1": 1.0, "a1": 1.0}
        edges_contested = [
            ("s1", "target", 5.0, 1),
            ("a1", "target", 5.0, -1),
        ]

        res_cont = solve_continuous_qbaf(nodes=nodes_contested, edges=edges_contested)
        res_disc = solve_qbaf_gradual_semantics(nodes=nodes_contested, edges=edges_contested)

        # S+ = S- = 5.0 -> Wt = 10/11 ~= 0.9091, Controv = 1.0 -> V ~= 0.9091
        expected_v = 10.0 / 11.0
        assert res_cont.volatility_index["target"] == pytest.approx(expected_v, abs=1e-3)
        assert res_disc.volatility_index["target"] == pytest.approx(expected_v, abs=1e-3)

        # Counter-example part 2: beta=0.5 with purely positive support has zero controversy -> V = 0.0
        nodes_uncontested = {"target": 0.5, "s1": 1.0}
        edges_uncontested = [("s1", "target", 5.0, 1)]
        res_u_cont = solve_continuous_qbaf(nodes=nodes_uncontested, edges=edges_uncontested)
        res_u_disc = solve_qbaf_gradual_semantics(nodes=nodes_uncontested, edges=edges_uncontested)
        assert res_u_cont.volatility_index["target"] == pytest.approx(0.0, abs=1e-6)
        assert res_u_disc.volatility_index["target"] == pytest.approx(0.0, abs=1e-6)

    def test_godel_tnorm_cyclic_bipartite_hypergraph_with_tied_premises(self) -> None:
        """F-04: Coupled ODE under Goedel t-norm handles premise ties on cyclic hypergraphs."""
        nodes = {
            "a": 0.7,
            "b": 0.7,  # Tied premise with 'a'
            "c": 0.5,
        }
        edges = [
            {
                "id": "w1",
                "source": "a",
                "premise_ids": ["a", "b"],
                "target": "c",
                "relation_type": "SUPPORTS",
                "inferential_force": 0.8,
            },
            {
                "id": "w2",
                "source": "c",
                "premise_ids": ["c"],
                "target": "a",
                "relation_type": "ATTACKS",
                "inferential_force": 0.6,
            },
            {
                "id": "w3",
                "source": "c",
                "premise_ids": ["c"],
                "target": "b",
                "relation_type": "ATTACKS",
                "inferential_force": 0.6,
            },
        ]

        res = solve_continuous_qbaf(nodes=nodes, edges=edges, t_norm="godel")
        assert res.converged is True
        assert abs(res.degrees["a"] - res.degrees["b"]) < 1e-4
        assert 0.0 <= res.degrees["c"] <= 1.0
        assert res.final_delta < 1e-3

    def test_ode_solver_reports_non_convergence_when_t_max_reached(self) -> None:
        """F-04 / B-17: Solver reports converged=False and positive residual when stopped early."""
        base_scores = np.array([0.8, 0.8])
        g_supp = np.zeros((2, 2))
        g_att = np.array([[0.0, 0.9], [0.9, 0.0]])

        # Tiny t_max prevents reaching stationary point
        solver = WeightedQuadraticEnergySolver(t_max=0.05, max_step=0.05)
        _, converged, telemetry = solver.solve(base_scores, g_supp, g_att)

        assert converged is False
        assert float(telemetry["final_residual"][0]) > 1e-3


class TestBasePriorPoliciesAndExegeticalReading:
    """Tests for C-03 (base prior policies) and C-04 (ALTERNATIVE_READING_OF & reading_id)."""

    def test_base_prior_policies_decouple_hedging_from_normative_acceptability(self) -> None:
        """C-03: Compare descriptive authorial priors against uniform and Data-Priority modes."""
        tg = TheoryGraph(name="HedgingTest")
        tg.add_node("obs", confidence=0.3, node_type=NodeType.EVIDENCE)
        tg.add_node("bold_claim", confidence=0.95, node_type=NodeType.CLAIM)
        tg.add_node("cautious_claim", confidence=0.35, node_type=NodeType.CLAIM)
        tg.add_edge("obs", "cautious_claim", relation_type=RelationType.SUPPORTS, weight=0.9)

        sensitivity = compare_prior_policies(tg, continuous=True)
        desc = sensitivity.results_by_policy[BasePriorPolicy.DESCRIPTIVE_AUTHORIAL.value]
        unif = sensitivity.results_by_policy[BasePriorPolicy.NORMATIVE_UNIFORM.value]
        data_p = sensitivity.results_by_policy[BasePriorPolicy.NORMATIVE_DATA_PRIORITY.value]

        # Under descriptive authorial priors, ungrounded bold claim outranks supported cautious claim
        assert desc.degrees["bold_claim"] > desc.degrees["cautious_claim"]
        # Under normative uniform & Data-Priority priors, supported claim outranks ungrounded claim
        assert unif.degrees["cautious_claim"] > unif.degrees["bold_claim"]
        assert data_p.degrees["cautious_claim"] > unif.degrees["cautious_claim"]
        assert sensitivity.rank_reversals_descriptive_vs_uniform >= 1
        assert sensitivity.max_drift_descriptive_vs_uniform > 0.2

    def test_alternative_reading_of_ignored_by_dialectical_solver(self) -> None:
        """C-04: Structural ALTERNATIVE_READING_OF edges carry polarity 0 and do not attack targets."""
        tg = TheoryGraph(name="ExegeticalGraph")
        tg.add_node(
            "r1",
            confidence=0.8,
            reading_id="reading_kant_1",
            semantic_sentence_type="PURE_THEORETICAL",
        )
        tg.add_node(
            "r2",
            confidence=0.8,
            reading_id="reading_kant_2",
            semantic_sentence_type="MIXED",
        )
        tg.add_edge("r1", "r2", relation_type=RelationType.ALTERNATIVE_READING_OF, weight=1.0)

        assert tg.edges[0].polarity == 0
        assert tg.nodes["r1"].reading_id == "reading_kant_1"
        assert tg.nodes["r2"].semantic_sentence_type == "MIXED"

        res_cont = solve_continuous_qbaf(tg)
        res_disc = solve_qbaf_gradual_semantics(tg)
        assert res_cont.degrees["r2"] == pytest.approx(0.8, abs=1e-5)
        assert res_disc.degrees["r2"] == pytest.approx(0.8, abs=1e-5)
        assert res_cont.attack_sums["r2"] == 0.0
        assert res_cont.support_sums["r2"] == 0.0


class TestGraphAlgorithmsAndCommunityMetrics:
    """Tests for C-06 (Katz, Eigenvector guards, signed/per-community modularity, P_i)."""

    def test_katz_succeeds_on_dag_while_eigenvector_guards_reject_dag_and_negative(self) -> None:
        """C-06: Katz works on DAGs and cyclic graphs; eigenvector raises on DAG/negative."""
        dag = nx.DiGraph([("a", "b"), ("b", "c"), ("a", "c")])

        with pytest.raises(AlgorithmError, match="acyclic"):
            eigenvector_centrality(dag, prefer_neo4j=False)

        fallback_res = eigenvector_centrality(
            dag, prefer_neo4j=False, fallback_to_katz=True
        )
        assert fallback_res.algorithm == "katz"
        assert fallback_res.scores["c"] > fallback_res.scores["a"] > 0.0

        katz_res = katz_centrality(dag)
        assert katz_res.scores["c"] > katz_res.scores["b"] > katz_res.scores["a"] > 0.0

        signed_g = nx.Graph()
        signed_g.add_edge("x", "y", weight=-1.0)
        with pytest.raises(AlgorithmError, match="negative"):
            eigenvector_centrality(signed_g, weight_property="weight", prefer_neo4j=False)
        with pytest.raises(AlgorithmError, match="negative"):
            katz_centrality(signed_g, weight_property="weight")

    def test_per_community_and_signed_modularity_and_participation_coefficient(self) -> None:
        """C-06: Verify additive q_c, signed modularity opponent penalty, support_only Louvain, and P_i."""
        g = nx.DiGraph()
        # Two tight support triangles bridged by an explanatory principle 'u'
        for u, v in [
            ("a1", "a2"), ("a2", "a3"), ("a3", "a1"),
            ("b1", "b2"), ("b2", "b3"), ("b3", "b1"),
        ]:
            g.add_edge(u, v, weight=1.0, polarity=1)
        # Adversarial attacks between clusters
        g.add_edge("a1", "b1", weight=1.0, polarity=-1)
        g.add_edge("a2", "b2", weight=1.0, polarity=-1)

        parts_sep = [{"a1", "a2", "a3"}, {"b1", "b2", "b3"}]
        parts_merged = [{"a1", "a2", "a3", "b1", "b2", "b3"}]

        # Support-only Louvain separates the two clusters cleanly
        louv = louvain_communities(g, seed=42, support_only=True, prefer_neo4j=False)
        assert len(louv.partitions) == 2
        assert louv.modularity is not None
        assert louv.modularity == pytest.approx(sum(louv.community_modularities.values()))

        # Signed modularity favors separating opponents over merging them
        q_sep, q_sep_map = signed_modularity(g, parts_sep, weight_property="weight")
        q_merged, _ = signed_modularity(g, parts_merged, weight_property="weight")
        assert q_sep == pytest.approx(sum(q_sep_map.values()))
        assert q_sep > q_merged

        # Per-community modularity matches NetworkX modularity
        u_pos = nx.Graph([(u, v, {"weight": 1.0}) for u, v, d in g.edges(data=True) if d["polarity"] > 0])
        q_tot, q_map = per_community_modularity(u_pos, parts_sep, weight_property="weight")
        assert q_tot == pytest.approx(nx.community.modularity(u_pos, parts_sep, weight="weight"))
        assert q_tot == pytest.approx(sum(q_map.values()))

        # Participation coefficient: bridge node connecting both communities has P_i = 0.5
        g_part = nx.DiGraph()
        g_part.add_edge("unifier", "a1")
        g_part.add_edge("unifier", "b1")
        g_part.add_edge("local", "a1")
        g_part.add_edge("local", "a2")
        partition = {
            "unifier": 0,
            "local": 0,
            "a1": 0,
            "a2": 0,
            "b1": 1,
        }
        p_scores = participation_coefficient(g_part, partition, direction="out")
        assert p_scores["local"] == pytest.approx(0.0)
        assert p_scores["unifier"] == pytest.approx(0.5)


class TestSecondaryAnalyticalLenses:
    """Tests for C-07 (symmetrized ECHO lens and support-preserving Dung reduction)."""

    def test_echo_lens_symmetrization_dilution_and_harmony(self) -> None:
        """C-07: ECHO projection creates symmetric co-hypothesis links and favors data-backed hypothesis."""
        nodes = {
            "e1": {"node_type": "evidence"},
            "e2": {"node_type": "evidence"},
            "h_good": {"node_type": "hypothesis"},
            "h_aux": {"node_type": "hypothesis"},
            "h_rival": {"node_type": "hypothesis"},
        }
        edges = [
            # Conjunctive explanation: (h_good, h_aux) -> e1 (m=2 dilution + co-hypothesis link)
            {"premise_ids": ["h_good", "h_aux"], "target": "e1", "relation_type": "SUPPORTS", "weight": 1.0},
            {"premise_ids": ["h_good"], "target": "e2", "relation_type": "SUPPORTS", "weight": 1.0},
            {"premise_ids": ["h_good"], "target": "h_rival", "relation_type": "ATTACKS", "weight": 1.0},
        ]

        _, data_nodes, sym_w = project_to_echo_network(nodes, edges, excitation=0.04, inhibition=0.06)
        assert data_nodes == {"e1", "e2"}
        # Co-hypothesis link between h_aux and h_good with diluted weight 0.04 / 2 = 0.02
        assert sym_w[("h_aux", "h_good")] == pytest.approx(0.02)
        assert sym_w[("e1", "h_good")] == pytest.approx(0.02)
        assert sym_w[("e2", "h_good")] == pytest.approx(0.04)
        assert sym_w[("h_good", "h_rival")] == pytest.approx(-0.06)

        res = solve_echo_lens(nodes, edges)
        assert res.converged is True
        assert all(-1.0 <= v <= 1.0 for v in res.activations.values())
        assert res.activations["h_good"] > res.activations["h_rival"]
        assert res.harmony > 0.0

    def test_bipolar_to_dung_reduction_preserves_support_semantics(self) -> None:
        """C-07: Support-preserving Dung reduction derives complex attacks under all 3 interpretations."""
        nodes = ["a", "b", "c", "d"]
        # a supports b, b attacks c, d supports c
        edges = [
            ("a", "b", 1.0, 1),
            ("b", "c", 1.0, -1),
            ("d", "c", 1.0, 1),
        ]

        # Deductive support: supported attack (a -> c) and mediated attack (b -> d)
        _, direct_d, derived_d = reduce_bipolar_to_dung(nodes, edges, support_type="deductive")
        assert direct_d == {("b", "c")}
        assert ("a", "c") in derived_d
        assert ("b", "d") in derived_d

        # Necessary support: secondary attack (b -> ...) and extended attack
        _, _, derived_n = reduce_bipolar_to_dung(
            ["x", "y", "z"],
            [("x", "y", 1.0, -1), ("y", "z", 1.0, 1)],
            support_type="necessary",
        )
        assert ("x", "z") in derived_n

        # Evidential support: supported attack + secondary attack
        _, _, derived_e = reduce_bipolar_to_dung(
            ["p", "q", "r", "s"],
            [("p", "q", 1.0, 1), ("q", "r", 1.0, -1), ("r", "s", 1.0, 1)],
            support_type="evidential",
        )
        assert ("p", "r") in derived_e
        assert ("q", "s") in derived_e

        ext_res = compute_dung_extensions(nodes, edges, support_type="deductive")
        # a and b are unattacked; b attacks c and (mediated) d, so grounded = {a, b}
        assert ext_res.grounded_extension == frozenset({"a", "b"})
        assert ext_res.preferred_extensions == [frozenset({"a", "b"})]
        assert ext_res.stable_extensions == [frozenset({"a", "b"})]
