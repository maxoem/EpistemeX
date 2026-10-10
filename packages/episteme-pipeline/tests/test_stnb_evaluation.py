"""Comprehensive unit tests for STNB evaluation capabilities (ISSUE-026, ISSUE-027, ISSUE-028).

Verifies:
1. STNB JSON-LD adapter fixes (dual edge attributes, array normalization, resilient anchors, complete edge coverage, poset orientation).
2. STNB ground truth data and CPM pilot corpus integrity (token offsets, model classes, constraints, paradigms).
3. Consolidated evaluation packaging, in-memory TheoryNet execution, and EvaluationHarness without Neo4j.
"""

from __future__ import annotations

import json
from pathlib import Path

import epistemetrics as em
import networkx as nx
import pytest
import yaml
from episteme_pipeline.artifacts.execution import ArtifactCollection
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    TheoryAtomArtifact,
)
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryNet
from episteme_pipeline.evaluation.benchmarks.structuralist import (
    _as_list,
    load_structuralist_benchmark,
    load_structuralist_theory_graph,
)
from episteme_pipeline.evaluation.harness import EvaluationHarness
from episteme_pipeline.evaluation.models import EvaluationLevel, EvaluationOutcome
from episteme_pipeline.evaluation.pipelines import (
    build_l4_theorynet_eval_pipeline,
)
from episteme_pipeline.evaluation.scorers.domain_bridge import (
    artifact_collection_to_theory_graph,
)

# ===========================================================================
# ISSUE-027: Adapter Schema Inconsistencies & Edge Decoding Bugs
# ===========================================================================


class TestSTNBAdapterIssue027:
    """Test suite for ISSUE-027 fixes in structuralist benchmark adapter."""

    def test_as_list_helper(self):
        """Test normalization of scalar strings, lists, and None values."""
        assert _as_list(None) == []
        assert _as_list("single_id") == ["single_id"]
        assert _as_list(["id1", "id2"]) == ["id1", "id2"]
        assert _as_list(["id1", None, "id2"]) == ["id1", "id2"]

    def test_dual_edge_attributes(self, tmp_path: Path):
        """Verify every edge in gold_graph has both label and relation populated."""
        jsonld_data = {
            "@context": {
                "str": "https://structuralism.org/ontology#",
                "Episteme": "https://grund.ai/schema#",
            },
            "@graph": [
                {
                    "@id": "str:T_Root",
                    "@type": "TheoryElement",
                    "str:hasActualModel": "str:M_Law1",
                },
                {
                    "@id": "str:M_Law1",
                    "@type": "ActualModel",
                    "str:formalAxiom": "F = m * a",
                },
            ],
        }
        test_file = tmp_path / "test_dual.jsonld"
        test_file.write_text(json.dumps(jsonld_data), encoding="utf-8")

        chunks, gold_graph = load_structuralist_benchmark(test_file)
        assert gold_graph.number_of_edges() == 1

        for u, v, d in gold_graph.edges(data=True):
            assert d.get("label") == "hasActualModel"
            assert d.get("relation") == "hasActualModel"
            assert d.get("label") is not None
            assert d.get("relation") is not None

        # Verify downstream scorers querying data='label' receive string
        labels = [str(data) for _, _, data in gold_graph.edges(data="label")]
        assert labels == ["hasActualModel"]
        assert "None" not in labels

    def test_array_target_normalization(self, tmp_path: Path):
        """Verify list-valued relational targets parse without TypeError: unhashable type: 'list'."""
        jsonld_data = {
            "@context": {
                "str": "https://structuralism.org/ontology#",
                "Episteme": "https://grund.ai/schema#",
            },
            "@graph": [
                {
                    "@id": "str:T_Root",
                    "@type": "TheoryElement",
                    "str:hasActualModel": ["str:M_Law1", "str:M_Law2", "str:M_Law3"],
                    "str:hasConstraint": ["str:GC_1", "str:GC_2"],
                },
                {"@id": "str:M_Law1", "@type": "ActualModel"},
                {"@id": "str:M_Law2", "@type": "ActualModel"},
                {"@id": "str:M_Law3", "@type": "ActualModel"},
                {"@id": "str:GC_1", "@type": "Constraint"},
                {"@id": "str:GC_2", "@type": "Constraint"},
            ],
        }
        test_file = tmp_path / "test_array.jsonld"
        test_file.write_text(json.dumps(jsonld_data), encoding="utf-8")

        # Parsing should succeed without TypeError
        chunks, gold_graph = load_structuralist_benchmark(test_file)
        assert gold_graph.number_of_nodes() == 6
        assert gold_graph.number_of_edges() == 5

    def test_resilient_text_anchor_namespaces(self, tmp_path: Path):
        """Verify text anchor extraction across Episteme, glp, and unprefixed namespaces."""
        jsonld_data = {
            "@context": {"str": "https://structuralism.org/ontology#"},
            "@graph": [
                {
                    "@id": "str:N1",
                    "@type": "ActualModel",
                    "Episteme:textAnchor": {
                        "chunkId": "c1",
                        "verbatimQuote": "First quote.",
                        "sourceDocId": "doc1",
                        "charStart": 0,
                        "charEnd": 12,
                    },
                },
                {
                    "@id": "str:N2",
                    "@type": "ActualModel",
                    "glp:textAnchor": {
                        "chunkId": "c2",
                        "verbatimQuote": "Second quote.",
                        "sourceDocId": "doc1",
                        "charStart": 13,
                        "charEnd": 26,
                    },
                },
                {
                    "@id": "str:N3",
                    "@type": "ActualModel",
                    "textAnchor": {
                        "chunkId": "c3",
                        "verbatimQuote": "Third quote.",
                        "sourceDocId": "doc1",
                        "charStart": 27,
                        "charEnd": 39,
                    },
                },
            ],
        }
        test_file = tmp_path / "test_anchors.jsonld"
        test_file.write_text(json.dumps(jsonld_data), encoding="utf-8")

        chunks, gold_graph = load_structuralist_benchmark(test_file)
        assert len(chunks) == 3
        assert [c.id for c in chunks] == ["c1", "c2", "c3"]
        assert [c.text for c in chunks] == ["First quote.", "Second quote.", "Third quote."]

    def test_complete_edge_coverage(self, tmp_path: Path):
        """Verify all structuralist edge types are decoded properly."""
        jsonld_data = {
            "@context": {"str": "https://structuralism.org/ontology#"},
            "@graph": [
                {
                    "@id": "str:T1",
                    "@type": "TheoryElement",
                    "str:reducesTo": "str:T2",
                    "str:hasPotentialModel": "str:Mp1",
                    "str:hasActualModel": "str:M1",
                    "str:hasPartialPotentialModel": "str:Mpp1",
                    "str:hasConstraint": "str:GC1",
                    "str:hasParadigm": "str:I1",
                    "str:presupposes": "str:T3",
                    "str:empiricallyEquivalent": "str:T4",
                },
                {"@id": "str:T2", "@type": "TheoryElement"},
                {"@id": "str:T3", "@type": "TheoryElement"},
                {"@id": "str:T4", "@type": "TheoryElement"},
                {"@id": "str:Mp1", "@type": "PotentialModel"},
                {"@id": "str:M1", "@type": "ActualModel"},
                {"@id": "str:Mpp1", "@type": "PartialPotentialModel"},
                {"@id": "str:GC1", "@type": "Constraint"},
                {"@id": "str:I1", "@type": "Paradigm"},
            ],
        }
        test_file = tmp_path / "test_edges.jsonld"
        test_file.write_text(json.dumps(jsonld_data), encoding="utf-8")

        chunks, gold_graph = load_structuralist_benchmark(test_file)
        assert gold_graph.has_edge("str:T1", "str:T2")
        assert gold_graph["str:T1"]["str:T2"]["relation"] == "reducesTo"

        assert gold_graph.has_edge("str:T1", "str:Mp1")
        assert gold_graph["str:T1"]["str:Mp1"]["relation"] == "hasPotentialModel"

        assert gold_graph.has_edge("str:T1", "str:M1")
        assert gold_graph["str:T1"]["str:M1"]["relation"] == "hasActualModel"

        assert gold_graph.has_edge("str:T1", "str:Mpp1")
        assert gold_graph["str:T1"]["str:Mpp1"]["relation"] == "hasPartialPotentialModel"

        assert gold_graph.has_edge("str:T1", "str:GC1")
        assert gold_graph["str:T1"]["str:GC1"]["relation"] == "hasConstraint"

        assert gold_graph.has_edge("str:T1", "str:I1")
        assert gold_graph["str:T1"]["str:I1"]["relation"] == "hasParadigm"

        assert gold_graph.has_edge("str:T1", "str:T3")
        assert gold_graph["str:T1"]["str:T3"]["relation"] == "presupposes"

        # Empirically equivalent is symmetric
        assert gold_graph.has_edge("str:T1", "str:T4")
        assert gold_graph.has_edge("str:T4", "str:T1")
        assert gold_graph["str:T1"]["str:T4"]["relation"] == "empiricallyEquivalent"
        assert gold_graph["str:T4"]["str:T1"]["relation"] == "empiricallyEquivalent"

    def test_specialization_poset_orientation(self, tmp_path: Path):
        """Verify specialization edges flow Root -> Sub-theory (T0 -> T1)."""
        jsonld_data = {
            "@context": {"str": "https://structuralism.org/ontology#"},
            "@graph": [
                {
                    "@id": "str:T_Root",
                    "@type": "TheoryElement",
                    "rdfs:label": "Root Core",
                },
                {
                    "@id": "str:T_Sub1",
                    "@type": "TheoryElement",
                    "rdfs:label": "Sub-Theory 1",
                    "str:specializes": "str:T_Root",
                },
                {
                    "@id": "str:T_Sub2",
                    "@type": "TheoryElement",
                    "rdfs:label": "Sub-Theory 2",
                    "specializes": "str:T_Root",
                },
            ],
        }
        test_file = tmp_path / "test_poset.jsonld"
        test_file.write_text(json.dumps(jsonld_data), encoding="utf-8")

        chunks, gold_graph = load_structuralist_benchmark(test_file)
        # Specialization edges must flow from parent to child
        assert gold_graph.has_edge("str:T_Root", "str:T_Sub1")
        assert gold_graph.has_edge("str:T_Root", "str:T_Sub2")
        assert not gold_graph.has_edge("str:T_Sub1", "str:T_Root")
        assert not gold_graph.has_edge("str:T_Sub2", "str:T_Root")

        # Root must have in-degree 0 in the specialization DAG
        spec_subgraph = nx.DiGraph(
            [
                (u, v)
                for u, v, d in gold_graph.edges(data=True)
                if d.get("relation") == "specializes"
            ]
        )
        assert spec_subgraph.in_degree("str:T_Root") == 0
        assert nx.is_directed_acyclic_graph(spec_subgraph)


# ===========================================================================
# ISSUE-026: STNB Ground-Truth Data & CPM Pilot Corpus
# ===========================================================================


class TestSTNBGroundTruthIssue026:
    """Test suite for ISSUE-026 CPM pilot corpus and ground-truth verification."""

    CPM_PILOT_PATH = Path(
        "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld"
    )
    CPM_CORPUS_PATH = Path(
        "packages/episteme-pipeline/episteme_pipeline/evaluation/data/newton_principia_1687.txt"
    )
    CPM_MANIFEST_PATH = Path(
        "packages/episteme-pipeline/episteme_pipeline/evaluation/manifests/eval_stnb.yaml"
    )

    def test_pilot_files_exist(self):
        """Verify ground-truth data, corpus, and manifest exist."""
        assert self.CPM_PILOT_PATH.is_file(), f"Missing {self.CPM_PILOT_PATH}"
        assert self.CPM_CORPUS_PATH.is_file(), f"Missing {self.CPM_CORPUS_PATH}"
        assert self.CPM_MANIFEST_PATH.is_file(), f"Missing {self.CPM_MANIFEST_PATH}"

    def test_cpm_pilot_component_counts(self):
        """Verify CPM pilot contains required structuralist components."""
        chunks, gold_graph = load_structuralist_benchmark(self.CPM_PILOT_PATH)

        # Count node types
        types = [d.get("node_type") for _, d in gold_graph.nodes(data=True)]
        theory_elements = [t for t in types if t == "TheoryElement"]
        actual_models = [t for t in types if t == "ActualModel"]
        potential_models = [t for t in types if t == "PotentialModel"]
        constraints = [t for t in types if t == "Constraint"]
        paradigms = [t for t in types if t == "Paradigm"]

        assert len(theory_elements) >= 4
        assert len(actual_models) + len(potential_models) >= 8
        assert len(constraints) >= 2
        assert len(paradigms) >= 2

    def test_text_anchor_verbatim_alignment(self):
        """Verify every text anchor in CPM pilot exactly matches primary source text."""
        corpus_text = self.CPM_CORPUS_PATH.read_text(encoding="utf-8")

        with open(self.CPM_PILOT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        anchored_nodes = 0
        for item in data["@graph"]:
            anchor = (
                item.get("Episteme:textAnchor")
                or item.get("glp:textAnchor")
                or item.get("textAnchor")
            )
            if anchor and isinstance(anchor, dict):
                anchored_nodes += 1
                char_start = anchor["charStart"]
                char_end = anchor["charEnd"]
                quote = anchor["verbatimQuote"]

                # Verbatim character slice must match exactly
                assert corpus_text[char_start:char_end] == quote, (
                    f"Mismatch in node {item['@id']}: slice '{corpus_text[char_start:char_end]}' != '{quote}'"
                )

        assert anchored_nodes >= 10

    def test_cpm_manifest_validity(self):
        """Verify eval_stnb.yaml parses cleanly and targets valid files."""
        with open(self.CPM_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        assert manifest["corpus"]["dataset_type"] == "structuralist"
        gold_path = Path(manifest["corpus"]["gold_standard_path"])
        assert gold_path.is_file()
        texts_dir = Path(manifest["corpus"]["texts_dir"])
        assert texts_dir.is_dir()


# ===========================================================================
# ISSUE-028: Packaging Consolidation & In-Memory TheoryNet Execution
# ===========================================================================


class TestPackagingAndInMemoryExecutionIssue028:
    """Test suite for ISSUE-028 packaging consolidation and in-memory evaluation."""

    def test_no_legacy_evaluation_dir(self):
        """Verify legacy evaluation directory is completely removed."""
        legacy_dir = Path("packages/episteme-pipeline/evaluation")
        assert not legacy_dir.exists(), "Legacy packages/episteme-pipeline/evaluation must be deleted."

    def test_package_exports_cleanly(self):
        """Verify all evaluation symbols are importable from episteme_pipeline.evaluation."""
        from episteme_pipeline.evaluation import (
            EvaluationHarness,
            ModelScorer,
            build_l4_theorynet_eval_pipeline,
        )

        assert EvaluationHarness is not None
        assert ModelScorer is not None
        assert callable(build_l4_theorynet_eval_pipeline)

    def test_in_memory_theorynet_model_evaluation(self):
        """Verify EvaluationHarness evaluates in-memory TheoryNet against gold STNB graph."""
        cpm_gold_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld"
        )
        chunks, gold_graph = load_structuralist_benchmark(cpm_gold_path)

        # Construct an in-memory TheoryNet mimicking pipeline output for CPM
        atoms = [
            TheoryAtom(
                id="str:M_CPM_Newton1",
                text="forall p in P, t in T: (sum_i f(p, t, i) = 0) -> d2/dt2(s(p, t)) = 0",
                component_type="actual_model",
                source_chunk_id="chunk_principia_law_1",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:M_CPM_Newton2",
                text="forall p in P, t in T: m(p) * d2/dt2(s(p, t)) = sum_i f(p, t, i)",
                component_type="actual_model",
                source_chunk_id="chunk_principia_law_2",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:M_CPM_Newton3",
                text="forall p, p' in P, t in T: f(p, p', t) = -f(p', p, t)",
                component_type="actual_model",
                source_chunk_id="chunk_principia_law_3",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:M_CPM_Grav",
                text="forall p1, p2 in P: f_G(p1, p2) = -G * (m(p1) * m(p2) / ||s(p1) - s(p2)||^2) * r_hat",
                component_type="actual_model",
                source_chunk_id="chunk_principia_prop_74",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:M_CPM_Hooke",
                text="forall p in P: f_H(p) = -k * s(p)",
                component_type="actual_model",
                source_chunk_id="chunk_principia_prop_10",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:M_CPM_Free",
                text="forall p in P, t in T: m(p) * d2/dt2(s(p, t)) = 0",
                component_type="actual_model",
                source_chunk_id="chunk_principia_def_3",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:Mp_CPM",
                text="Mp(CPM) = <P, T, s, m, f>",
                component_type="potential_model",
                source_chunk_id="chunk_principia_def_1",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:Mp_Grav",
                text="Mp(Grav) = <P, T, s, m, f, G>",
                component_type="potential_model",
                source_chunk_id="chunk_principia_def_8",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:Mp_Harmonic",
                text="Mp(Harmonic) = <P, T, s, m, f, k>",
                component_type="potential_model",
                source_chunk_id="chunk_principia_def_5",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:Mpp_CPM",
                text="Mpp(CPM) = <P, T, s>",
                component_type="partial_potential_model",
                source_chunk_id="chunk_principia_scholium_space_time",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:GC_Mass",
                text="forall p in P, forall x, x' in I: m_x(p) = m_x'(p)",
                component_type="constraint",
                source_chunk_id="chunk_principia_rule_3",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:GC_Force",
                text="forall p, p' in P: f(p, p') + f(p', p) = 0",
                component_type="constraint",
                source_chunk_id="chunk_principia_cor_3",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:I0_PlanetaryOrbits",
                text="Keplerian planetary orbits",
                component_type="paradigm",
                source_chunk_id="chunk_principia_prop_1",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:I0_TerrestrialFreeFall",
                text="Terrestrial Galileo free fall",
                component_type="paradigm",
                source_chunk_id="chunk_principia_free_fall",
                confidence=1.0,
            ),
            TheoryAtom(
                id="str:I0_HarmonicSpring",
                text="Harmonic spring oscillation",
                component_type="paradigm",
                source_chunk_id="chunk_principia_prop_10",
                confidence=1.0,
            ),
        ]
        theory_net = TheoryNet(atoms=atoms, relations=[])

        harness = EvaluationHarness()
        import asyncio

        report = asyncio.run(
            harness.evaluate_in_memory(
                predicted=theory_net,
                gold=gold_graph,
                run_id="test_in_memory_run",
                min_pfs=0.4,
            )
        )

        assert report.evaluation_id == "eval_test_in_memory_run"
        stage_res = report.results_by_level[em.EvaluationLevel.STAGE if hasattr(em, "EvaluationLevel") else "stage"][0]
        assert stage_res.outcome == EvaluationOutcome.PASS
        metrics = {m.name: m.value for m in stage_res.metrics}
        assert metrics["mcc"] == 1.0
        assert metrics["aor"] == 0.0

    def test_in_memory_artifact_collection_evaluation(self):
        """Verify EvaluationHarness evaluates in-memory ArtifactCollection."""
        cpm_gold_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld"
        )
        chunks, gold_graph = load_structuralist_benchmark(cpm_gold_path)

        atom_payload = TheoryAtomArtifact(
            component_id="str:M_CPM_Newton2",
            chunk_id="chunk_principia_law_2",
            text="forall p in P, t in T: m(p) * d2/dt2(s(p, t)) = sum_i f(p, t, i)",
            component_type="actual_model",
            confidence=1.0,
        )
        envelope = ArtifactEnvelope(
            artifact_id="art_atom_newton2",
            kind=ArtifactKind.THEORY_ATOM,
            run_id="run_test",
            phase_name="phase4",
            method="test",
            payload=atom_payload,
        )
        collection = ArtifactCollection(artifacts=[envelope])

        # Convert to theory graph
        tg = artifact_collection_to_theory_graph(collection)
        assert tg.num_nodes == 1
        assert tg.get_node("str:M_CPM_Newton2") is not None

    def test_build_l4_theorynet_eval_pipeline_structure(self):
        """Verify build_l4_theorynet_eval_pipeline configures Phases 1 through 6."""
        pipeline = build_l4_theorynet_eval_pipeline(in_memory=True)
        phase_names = [p.name for p in pipeline.phases]
        assert "Phase 1: Data Foundation" in phase_names[0]
        assert "Phase 2: Entity & Local Relation Discovery" in phase_names[1]
        assert "Phase 3: Global Relation Extraction" in phase_names[2]
        assert "Phase 6: TheoryNet Projection" in phase_names[-1]


# ===========================================================================
# ISSUE-031 & ISSUE-032: Poset Specialization & Extrinsic Competency Testbed
# ===========================================================================


class TestSTNBIssue031PosetSpecialization:
    """Test suite for ISSUE-031 specialization poset evaluation on STNB pilot data."""

    def test_stnb_cpm_pilot_poset_properties(self):
        """Verify specialization tree in stnb_cpm_pilot conforms to strict poset properties."""
        cpm_gold_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld"
        )
        _, tg = load_structuralist_theory_graph(cpm_gold_path)

        poset_res = em.evaluate_specialization_poset(
            pred_graph=tg,
            ref_graph=tg,
            gold_root_id="str:T_CPM_Base",
        )

        assert poset_res.is_dag is True
        assert poset_res.is_strict_partial_order is True
        assert poset_res.has_unique_root is True
        assert poset_res.root_node == "str:T_CPM_Base"
        assert poset_res.root_conformity is True
        assert poset_res.num_predicted_edges == 3
        assert poset_res.f1 == 1.0
        assert poset_res.reachability_f1 == 1.0
        assert poset_res.hierarchical_subsumption_valid is True
        assert poset_res.hierarchical_subsumption_score == 1.0
        assert len(poset_res.cycles) == 0


class TestSTNBIssue032CompetencyRetrieval:
    """Test suite for ISSUE-032 competency query testbed and extrinsic retrieval."""

    def test_stnb_cpm_queries_file_integrity(self):
        """Verify stnb_cpm_queries.yaml contains valid queries matching pilot node IDs."""
        queries_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_queries.yaml"
        )
        cpm_gold_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld"
        )

        assert Path(queries_path).is_file()
        with open(queries_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        queries = data.get("queries", [])
        assert len(queries) >= 5

        # Check every query has mandatory fields
        _, gold_graph = load_structuralist_benchmark(cpm_gold_path)
        gold_node_ids = set(gold_graph.nodes())

        for q in queries:
            assert "id" in q
            assert "query" in q and len(q["query"]) > 10
            assert "gold_target_ids" in q and len(q["gold_target_ids"]) > 0
            assert "category" in q

            # Verify target IDs exist in gold graph
            for target_id in q["gold_target_ids"]:
                assert target_id in gold_node_ids, f"Target ID '{target_id}' missing in gold graph"

    @pytest.mark.asyncio
    async def test_evaluation_harness_manifest_with_competency_queries(self, tmp_path: Path):
        """Verify evaluate_manifest runs both intrinsic scoring and extrinsic competency retrieval."""
        manifest_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/manifests/eval_stnb.yaml"
        )
        cpm_gold_path = (
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld"
        )
        harness = EvaluationHarness(reports_dir=tmp_path / "reports")
        _, gold_graph = load_structuralist_benchmark(cpm_gold_path)
        harness.graph_store.index_theory_graph(gold_graph)

        report = await harness.evaluate_manifest(manifest_path, build_graph=False)

        assert report.evaluation_id.startswith("eval_")
        assert EvaluationLevel.STAGE in report.results_by_level
        assert EvaluationLevel.DOWNSTREAM in report.results_by_level

        # Stage intrinsic results
        stage_res = report.results_by_level[EvaluationLevel.STAGE][0]
        stage_metrics = {m.name: m.value for m in stage_res.metrics}
        assert stage_metrics["mcc"] == 1.0
        assert stage_metrics["aor"] == 0.0
        assert "poset_f1" in stage_metrics
        assert stage_metrics["poset_f1"] == 1.0
        assert stage_metrics["root_conformity"] == 1.0

        # Downstream extrinsic retrieval results
        downstream_res = report.results_by_level[EvaluationLevel.DOWNSTREAM][0]
        downstream_metrics = {m.name: m.value for m in downstream_res.metrics}
        assert "mrr" in downstream_metrics
        assert "hits@1" in downstream_metrics
        assert "hits@3" in downstream_metrics
        assert "hits@10" in downstream_metrics
        assert "ndcg" in downstream_metrics

        for m_name, val in downstream_metrics.items():
            assert 0.0 <= val <= 1.0, f"Metric {m_name} out of bounds: {val}"

        # MRR should be positive since nodes are indexed
        assert downstream_metrics["mrr"] > 0.0
        assert downstream_metrics["hits@10"] > 0.0

        # Reports persisted
        assert (tmp_path / "reports" / f"report_{report.run_ids[0]}.json").is_file()
        assert (tmp_path / "reports" / f"report_{report.run_ids[0]}.md").is_file()

