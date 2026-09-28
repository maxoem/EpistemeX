"""Comprehensive unit and integration tests for the Studio evaluation backend.

Verifies:
1. Pure domain models serialization and threshold verification.
2. Anti-corruption EvaluationAdapter discovery and pipeline bridging.
3. EvaluationService orchestration (report discovery, in-memory run evaluation).
4. FastAPI REST endpoints for reports, benchmarks, manifests, comparisons, and run evaluation.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.adapters.evaluation_adapter import EvaluationAdapter
from episteme_studio.app import create_app
from episteme_studio.domain.evaluation import (
    ComparativeMetricDelta,
    EvaluationOutcome,
    EvaluationReportDetail,
    EvaluationReportSummary,
    ModelDecompositionEntry,
    PosetEvaluationDetail,
)
from episteme_studio.runtime import EventBroker
from episteme_studio.settings import StudioSettings


class TestEvaluationDomainModels:
    """Test suite for pure Pydantic evaluation domain models."""

    def test_summary_and_detail_serialization(self):
        """Verify summary and detail models serialize cleanly without pipeline deps."""
        summary = EvaluationReportSummary(
            evaluation_id="eval_run_test_01",
            run_ids=["run_test_01"],
            dataset_ref="data/test_gold.jsonld",
            outcome=EvaluationOutcome.PASS,
            key_metrics={"mcc": 1.0, "aor": 0.0, "pfs": 0.85},
            has_markdown=True,
            has_baseline=False,
        )

        serialized = summary.model_dump()
        assert serialized["evaluation_id"] == "eval_run_test_01"
        assert serialized["outcome"] == "pass"
        assert serialized["key_metrics"]["mcc"] == 1.0

        detail = EvaluationReportDetail(
            **summary.model_dump(),
            model_decomposition=[
                ModelDecompositionEntry(
                    class_name="actual_models",
                    symbol="M",
                    reference_count=3,
                    predicted_count=3,
                    matched_count=3,
                    completeness=1.0,
                )
            ],
            poset_detail=PosetEvaluationDetail(
                is_dag=True,
                root_element="str:T_Root",
                root_conformity=True,
                transitive_reduction_f1=1.0,
                reachability_f1=1.0,
                predicted_edge_count=2,
                reference_edge_count=2,
            ),
            comparative_deltas=[
                ComparativeMetricDelta(
                    metric_name="f1",
                    value_baseline=0.70,
                    value_pipeline=0.90,
                    delta=0.20,
                    favorable=True,
                    winner="Pipeline",
                )
            ],
            summary_markdown="## Benchmark Passed",
        )

        assert len(detail.model_decomposition) == 1
        assert detail.poset_detail.is_dag is True
        assert detail.comparative_deltas[0].winner == "Pipeline"


class TestEvaluationAdapter:
    """Test suite for EvaluationAdapter bridging pipeline evaluation to studio."""

    def test_discover_benchmarks_and_manifests(self):
        """Verify adapter discovers built-in benchmarks and declarative manifests."""
        adapter = EvaluationAdapter()
        benchmarks = adapter.discover_benchmarks()
        manifests = adapter.discover_manifests()

        assert len(benchmarks) >= 1
        stnb_bm = next((b for b in benchmarks if b.id == "stnb_cpm_pilot"), None)
        assert stnb_bm is not None
        assert stnb_bm.task_type == "structuralist"
        assert Path(stnb_bm.gold_standard_path).is_file()

        assert len(manifests) >= 1
        stnb_man = next((m for m in manifests if m["id"] == "eval_stnb"), None)
        assert stnb_man is not None
        assert stnb_man["dataset_type"] == "structuralist"

    def test_list_and_get_persisted_reports(self, tmp_path: Path):
        """Verify adapter discovers and loads existing reports from reports_dir."""
        # Create a mock persisted report
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir(parents=True)

        report_data = {
            "evaluation_id": "eval_mock_run_01",
            "run_ids": ["mock_run_01"],
            "dataset_ref": "data/mock.jsonld",
            "dataset_type": "gold",
            "results_by_level": {
                "stage": [
                    {
                        "run_id": "mock_run_01",
                        "evaluation_level": "stage",
                        "phase_name": "Structuralist Evaluation",
                        "metrics": [
                            {"name": "mcc", "value": 1.0},
                            {"name": "aor", "value": 0.0},
                        ],
                        "outcome": "pass",
                    }
                ]
            },
            "summary": "## Formal Structuralist Evaluation\n- **Model Component Completeness (MCC):** 1.0000",
        }
        json_file = reports_dir / "report_mock_run_01.json"
        md_file = reports_dir / "report_mock_run_01.md"
        json_file.write_text(json.dumps(report_data), encoding="utf-8")
        md_file.write_text(report_data["summary"], encoding="utf-8")

        adapter = EvaluationAdapter(reports_dir=reports_dir)
        reports = adapter.list_reports()
        assert len(reports) == 1
        assert reports[0].evaluation_id == "eval_mock_run_01"
        assert reports[0].key_metrics.get("mcc") == 1.0
        assert reports[0].outcome == EvaluationOutcome.PASS

        detail = adapter.get_report("mock_run_01")
        assert detail is not None
        assert detail.evaluation_id == "eval_mock_run_01"
        assert "stage" in detail.results_by_level

    @pytest.mark.asyncio
    async def test_evaluate_run_with_synthetic_artifacts(self, tmp_path: Path):
        """Verify adapter evaluates a completed pipeline run against STNB CPM pilot."""
        runs_dir = tmp_path / "runs"
        artifacts_dir = tmp_path / "artifacts"
        runs_dir.mkdir()
        artifacts_dir.mkdir()

        run_id = "test_eval_run_cpm"
        run_art_dir = artifacts_dir / run_id
        run_art_dir.mkdir()

        # Seed CPM theory atoms as on-disk artifact envelopes
        atoms_data = [
            {"id": "str:T_CPM_Base", "text": "Classical Particle Mechanics Base", "component_type": "theory_element"},
            {"id": "str:T_CPM_Grav", "text": "Gravitation Specialization", "component_type": "theory_element"},
            {"id": "str:M_CPM_Newton1", "text": "Law 1", "component_type": "actual_model"},
            {"id": "str:M_CPM_Newton2", "text": "Law 2", "component_type": "actual_model"},
            {"id": "str:M_CPM_Newton3", "text": "Law 3", "component_type": "actual_model"},
            {"id": "str:M_CPM_Grav", "text": "Law Grav", "component_type": "actual_model"},
            {"id": "str:M_CPM_Hooke", "text": "Law Hooke", "component_type": "actual_model"},
            {"id": "str:M_CPM_Free", "text": "Law Free", "component_type": "actual_model"},
            {"id": "str:Mp_CPM", "text": "Mp CPM", "component_type": "potential_model"},
            {"id": "str:Mp_Grav", "text": "Mp Grav", "component_type": "potential_model"},
            {"id": "str:Mp_Harmonic", "text": "Mp Harmonic", "component_type": "potential_model"},
            {"id": "str:Mpp_CPM", "text": "Mpp CPM", "component_type": "partial_potential_model"},
            {"id": "str:GC_Mass", "text": "GC Mass", "component_type": "constraint"},
            {"id": "str:GC_Force", "text": "GC Force", "component_type": "constraint"},
            {"id": "str:I0_PlanetaryOrbits", "text": "Planetary Orbits", "component_type": "paradigm"},
            {"id": "str:I0_TerrestrialFreeFall", "text": "Free Fall", "component_type": "paradigm"},
            {"id": "str:I0_HarmonicSpring", "text": "Harmonic Spring", "component_type": "paradigm"},
        ]
        for atom in atoms_data:
            envelope = {
                "artifact_id": f"art_{atom['id'].replace(':', '_')}",
                "kind": "theory_atom",
                "payload": atom,
            }
            (run_art_dir / f"{envelope['artifact_id']}.json").write_text(json.dumps(envelope), encoding="utf-8")

        # Relation envelope
        rel_env = {
            "artifact_id": "art_rel_grav_base",
            "kind": "theory_relation",
            "payload": {
                "source_id": "str:T_CPM_Grav",
                "target_id": "str:T_CPM_Base",
                "relation_type": "specializes",
            },
        }
        (run_art_dir / "art_rel_grav_base.json").write_text(json.dumps(rel_env), encoding="utf-8")

        # Manifest
        manifest = {
            "run_id": run_id,
            "created_at": "2026-09-26T12:00:00Z",
            "status": "completed",
        }
        (runs_dir / f"{run_id}.json").write_text(json.dumps(manifest), encoding="utf-8")

        reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
        adapter = EvaluationAdapter(reports_dir=tmp_path / "reports")

        detail = await adapter.evaluate_run(
            run_id=run_id,
            reader=reader,
            benchmark_id="stnb_cpm_pilot",
            strategy="structuralist",
            min_pfs=0.4,
            persist=True,
        )

        assert detail.evaluation_id == f"eval_{run_id}"
        assert detail.outcome == EvaluationOutcome.PASS
        assert detail.key_metrics.get("mcc", 0.0) >= 1.0
        assert detail.key_metrics.get("aor", 1.0) == 0.0


class TestEvaluationAPI:
    """Test suite for FastAPI evaluation endpoints."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        """Create a test client backed by temporary directories."""
        settings = StudioSettings(
            runs_dir=tmp_path / "runs",
            artifacts_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            token=None,
        )
        settings.runs_dir.mkdir(parents=True)
        settings.artifacts_dir.mkdir(parents=True)
        settings.reports_dir.mkdir(parents=True)

        # Seed sample report
        report_data = {
            "evaluation_id": "eval_test_api_01",
            "run_ids": ["test_api_run"],
            "dataset_ref": "stnb_cpm_pilot.jsonld",
            "dataset_type": "gold",
            "results_by_level": {
                "stage": [
                    {
                        "run_id": "test_api_run",
                        "evaluation_level": "stage",
                        "phase_name": "TheoryNet Verification",
                        "metrics": [{"name": "mcc", "value": 1.0}, {"name": "aor", "value": 0.0}],
                        "outcome": "pass",
                    }
                ]
            },
            "summary": "# API Test Evaluation Report\n- **Status:** PASS",
        }
        (settings.reports_dir / "report_test_api_run.json").write_text(json.dumps(report_data), encoding="utf-8")
        (settings.reports_dir / "report_test_api_run.md").write_text(report_data["summary"], encoding="utf-8")

        app = create_app(settings)
        return TestClient(app)

    def test_list_and_get_reports_endpoint(self, client: TestClient):
        """Verify GET /api/evaluation/reports and GET /api/evaluation/reports/{id}."""
        resp = client.get("/api/evaluation/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) == 1
        assert reports[0]["evaluation_id"] == "eval_test_api_01"

        detail_resp = client.get("/api/evaluation/reports/test_api_run")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["evaluation_id"] == "eval_test_api_01"
        assert detail["key_metrics"]["mcc"] == 1.0

        md_resp = client.get("/api/evaluation/reports/test_api_run/markdown")
        assert md_resp.status_code == 200
        assert "# API Test Evaluation Report" in md_resp.text

    def test_list_benchmarks_and_manifests_endpoint(self, client: TestClient):
        """Verify GET /api/evaluation/benchmarks and GET /api/evaluation/manifests."""
        bm_resp = client.get("/api/evaluation/benchmarks")
        assert bm_resp.status_code == 200
        bms = bm_resp.json()
        assert any(b["id"] == "stnb_cpm_pilot" for b in bms)

        man_resp = client.get("/api/evaluation/manifests")
        assert man_resp.status_code == 200
        manifests = man_resp.json()
        assert any(m["id"] == "eval_stnb" for m in manifests)

    def test_get_run_evaluation_endpoint(self, client: TestClient):
        """Verify GET /api/runs/{run_id}/evaluation discovers linked report."""
        resp = client.get("/api/runs/test_api_run/evaluation")
        assert resp.status_code == 200
        report = resp.json()
        assert report is not None
        assert report["evaluation_id"] == "eval_test_api_01"

        # Non-evaluated run returns null
        resp_missing = client.get("/api/runs/non_existent_run/evaluation")
        assert resp_missing.status_code == 200
        assert resp_missing.json() is None

    def test_report_not_found(self, client: TestClient):
        """Verify GET /api/evaluation/reports/{unknown_id} returns 404 ProblemDetail."""
        resp = client.get("/api/evaluation/reports/unknown_report_xyz")
        assert resp.status_code == 404
        data = resp.json()
        assert data.get("type") == "evaluation-report-not-found"
        assert "unknown_report_xyz" in data.get("detail", "")

    def test_filter_reports(self, client: TestClient):
        """Verify filtering evaluation reports by run_id and outcome status."""
        resp_match = client.get("/api/evaluation/reports?run_id=test_api_run&outcome=pass")
        assert resp_match.status_code == 200
        assert len(resp_match.json()) == 1

        resp_none = client.get("/api/evaluation/reports?outcome=fail")
        assert resp_none.status_code == 200
        assert len(resp_none.json()) == 0

    def test_compare_runs_endpoint(self, client: TestClient):
        """Verify POST /api/evaluation/compare between two evaluated runs."""
        settings: StudioSettings = client.app.state.settings

        # Seed two run evaluation reports
        rep_a = {
            "evaluation_id": "eval_cmp_a",
            "run_ids": ["cmp_run_a"],
            "dataset_ref": "stnb_cpm_pilot.jsonld",
            "results_by_level": {
                "stage": [
                    {
                        "run_id": "cmp_run_a",
                        "evaluation_level": "stage",
                        "phase_name": "Test",
                        "metrics": [{"name": "f1", "value": 0.80}, {"name": "precision", "value": 0.85}],
                        "outcome": "pass",
                    }
                ]
            },
            "summary": "# Run A",
        }
        rep_b = {
            "evaluation_id": "eval_cmp_b",
            "run_ids": ["cmp_run_b"],
            "dataset_ref": "stnb_cpm_pilot.jsonld",
            "results_by_level": {
                "stage": [
                    {
                        "run_id": "cmp_run_b",
                        "evaluation_level": "stage",
                        "phase_name": "Test",
                        "metrics": [{"name": "f1", "value": 0.90}, {"name": "precision", "value": 0.82}],
                        "outcome": "pass",
                    }
                ]
            },
            "summary": "# Run B",
        }
        (settings.reports_dir / "report_cmp_run_a.json").write_text(json.dumps(rep_a), encoding="utf-8")
        (settings.reports_dir / "report_cmp_run_b.json").write_text(json.dumps(rep_b), encoding="utf-8")

        resp = client.post(
            "/api/evaluation/compare",
            json={"run_id_a": "cmp_run_a", "run_id_b": "cmp_run_b", "axis": "method"},
        )
        assert resp.status_code == 200
        comp_data = resp.json()
        assert comp_data["run_id_a"] == "cmp_run_a"
        assert comp_data["run_id_b"] == "cmp_run_b"
        assert len(comp_data["deltas"]) >= 2
        f1_delta = next((d for d in comp_data["deltas"] if d["metric_name"] == "f1"), None)
        assert f1_delta is not None
        assert f1_delta["value_baseline"] == 0.80
        assert f1_delta["value_pipeline"] == 0.90
        assert f1_delta["delta"] == 0.10
        assert f1_delta["winner"] == "cmp_run_b"

    def test_evaluate_run_endpoint(self, client: TestClient):
        """Verify POST /api/evaluation/run executes in-memory evaluation and returns 201."""
        settings: StudioSettings = client.app.state.settings
        run_id = "test_api_new_run"
        run_art_dir = settings.artifacts_dir / run_id
        run_art_dir.mkdir(parents=True, exist_ok=True)

        # Seed CPM theory atoms
        atoms = [
            {"id": "str:T_CPM_Base", "text": "Base", "component_type": "theory_element"},
            {"id": "str:T_CPM_Grav", "text": "Grav", "component_type": "theory_element"},
            {"id": "str:M_CPM_Newton1", "text": "Newton 1", "component_type": "actual_model"},
            {"id": "str:M_CPM_Newton2", "text": "Newton 2", "component_type": "actual_model"},
            {"id": "str:M_CPM_Newton3", "text": "Newton 3", "component_type": "actual_model"},
            {"id": "str:M_CPM_Grav", "text": "Grav", "component_type": "actual_model"},
            {"id": "str:M_CPM_Hooke", "text": "Hooke", "component_type": "actual_model"},
            {"id": "str:M_CPM_Free", "text": "Free", "component_type": "actual_model"},
            {"id": "str:Mp_CPM", "text": "Mp", "component_type": "potential_model"},
            {"id": "str:Mp_Grav", "text": "Mp", "component_type": "potential_model"},
            {"id": "str:Mp_Harmonic", "text": "Mp", "component_type": "potential_model"},
            {"id": "str:Mpp_CPM", "text": "Mpp", "component_type": "partial_potential_model"},
            {"id": "str:GC_Mass", "text": "GC Mass", "component_type": "constraint"},
            {"id": "str:GC_Force", "text": "GC Force", "component_type": "constraint"},
            {"id": "str:I0_PlanetaryOrbits", "text": "Planets", "component_type": "paradigm"},
            {"id": "str:I0_TerrestrialFreeFall", "text": "Fall", "component_type": "paradigm"},
            {"id": "str:I0_HarmonicSpring", "text": "Spring", "component_type": "paradigm"},
        ]
        for atom in atoms:
            env = {"artifact_id": f"art_{atom['id'].replace(':', '_')}", "kind": "theory_atom", "payload": atom}
            (run_art_dir / f"{env['artifact_id']}.json").write_text(json.dumps(env), encoding="utf-8")

        rel_env = {
            "artifact_id": "art_rel_grav_base",
            "kind": "theory_relation",
            "payload": {
                "source_id": "str:T_CPM_Grav",
                "target_id": "str:T_CPM_Base",
                "relation_type": "specializes",
            },
        }
        (run_art_dir / "art_rel_grav_base.json").write_text(json.dumps(rel_env), encoding="utf-8")

        manifest = {"run_id": run_id, "created_at": "2026-09-26T12:00:00Z", "status": "completed"}
        (settings.runs_dir / f"{run_id}.json").write_text(json.dumps(manifest), encoding="utf-8")

        resp = client.post(
            "/api/evaluation/run",
            json={
                "run_id": run_id,
                "benchmark_id": "stnb_cpm_pilot",
                "strategy": "structuralist",
                "min_pfs": 0.4,
                "persist": True,
            },
        )
        assert resp.status_code == 201
        report = resp.json()
        assert report["evaluation_id"] == f"eval_{run_id}"
        assert report["outcome"] == "pass"
        assert report["key_metrics"]["mcc"] >= 1.0
        assert (settings.reports_dir / f"report_{run_id}.json").is_file()

    def test_dynamics_trajectory_endpoint_progressive(self, client: TestClient):
        """Verify POST /api/evaluation/dynamics/trajectory evaluates progressive trajectory.

        Parameters
        ----------
        client : TestClient
            Initialized test client.
        """
        snapshots = [
            {
                "core_axioms": {"str:T_CPM_Base": "F = m*a"},
                "auxiliary_hypotheses": [],
                "anomalies": [],
                "empirical_content": ["str:I0_PlanetaryOrbits"],
            },
            {
                "core_axioms": {"str:T_CPM_Base": "F = m*a"},
                "auxiliary_hypotheses": ["str:M_CPM_Aux1"],
                "anomalies": [],
                "empirical_content": ["str:I0_PlanetaryOrbits", "str:I0_TerrestrialFreeFall", "str:I0_HarmonicSpring"],
            },
            {
                "core_axioms": {"str:T_CPM_Base": "F = m*a"},
                "auxiliary_hypotheses": ["str:M_CPM_Aux1"],
                "anomalies": [],
                "empirical_content": ["str:I0_PlanetaryOrbits", "str:I0_TerrestrialFreeFall", "str:I0_HarmonicSpring", "str:I0_Tides"],
            },
        ]

        resp = client.post(
            "/api/evaluation/dynamics/trajectory",
            json={
                "snapshots": snapshots,
                "core_node_ids": ["str:T_CPM_Base"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_progressive"] is True
        assert data["core_invariant"] is True
        assert data["degeneration_index"] < 1.0
        assert data["delta_auxiliary"] == 1
        assert data["delta_empirical_content"] == 3
        assert len(data["trajectory"]) == 2
        assert "epochs" in data["chart_data"]
        assert len(data["chart_data"]["epochs"]) == 3
        assert "di_series" in data["chart_data"]

    def test_dynamics_trajectory_endpoint_hard_core_violation(self, client: TestClient):
        """Verify POST /api/evaluation/dynamics/trajectory detects core axiom violation.

        Parameters
        ----------
        client : TestClient
            Initialized test client.
        """
        snapshots = [
            {
                "core_axioms": {"str:T_CPM_Base": "F = m*a", "str:T_CPM_Grav": "F_g = G*m1*m2/r^2"},
                "auxiliary_hypotheses": [],
                "anomalies": [],
                "empirical_content": ["str:I0_PlanetaryOrbits"],
            },
            {
                # Core axiom str:T_CPM_Grav deleted/mutated
                "core_axioms": {"str:T_CPM_Base": "F = m*a"},
                "auxiliary_hypotheses": ["str:M_CPM_Aux1", "str:M_CPM_Aux2"],
                "anomalies": ["str:Anom_Precession"],
                "empirical_content": ["str:I0_PlanetaryOrbits"],
            },
        ]

        resp = client.post(
            "/api/evaluation/dynamics/trajectory",
            json={
                "snapshots": snapshots,
                "core_node_ids": ["str:T_CPM_Base", "str:T_CPM_Grav"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["core_invariant"] is False
        assert len(data["violated_invariance"]) >= 1
        assert any(v["node_id"] == "str:T_CPM_Grav" for v in data["violated_invariance"])

    def test_record_and_list_adjudications_endpoint(self, client: TestClient):
        """Verify POST and GET /api/evaluation/adjudications.

        Parameters
        ----------
        client : TestClient
            Initialized test client.
        """
        items = [
            {
                "adjudication_id": "adj_test_01",
                "predicted_edge": {"source": "str:T_Grav", "predicate": "specializes", "target": "str:T_Base"},
                "decision": "true_positive",
                "similarity_score": 0.95,
                "rationale": "Correct theoretical specialization.",
                "adjudicated_by": "expert_reviewer_1",
            },
            {
                "adjudication_id": "adj_test_02",
                "predicted_edge": {"source": "str:T_Hooke", "predicate": "sub_model_of", "target": "str:T_Base"},
                "decision": "schema_alias",
                "alias_target": "str:specializes",
                "similarity_score": 0.82,
                "rationale": "sub_model_of is a semantic alias for specializes.",
                "adjudicated_by": "expert_reviewer_2",
            },
            {
                "adjudication_id": "adj_test_03",
                "predicted_edge": {"source": "str:T_Hooke", "predicate": "contradicts", "target": "str:T_Grav"},
                "decision": "false_positive",
                "similarity_score": 0.40,
                "rationale": "Spurious hallucinated relation.",
                "adjudicated_by": "expert_reviewer_1",
            },
        ]

        post_resp = client.post(
            "/api/evaluation/adjudications",
            json={"items": items},
        )
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        assert post_data["adjudicated_count"] == 3
        assert len(post_data["stored_items"]) == 3

        get_resp = client.get("/api/evaluation/adjudications")
        assert get_resp.status_code == 200
        saved_items = get_resp.json()
        assert len(saved_items) == 3
        decisions = {it["adjudication_id"]: it["decision"] for it in saved_items}
        assert decisions["adj_test_01"] == "true_positive"
        assert decisions["adj_test_02"] == "schema_alias"
        assert decisions["adj_test_03"] == "false_positive"

    def test_adjudication_export_curated_gold_standard(self, client: TestClient, tmp_path: Path):
        """Verify adjudications export and merge into a curated JSON-LD dataset.

        Parameters
        ----------
        client : TestClient
            Initialized test client.
        tmp_path : Path
            Pytest temporary directory fixture.
        """
        export_file = tmp_path / "curated_dataset.jsonld"
        items = [
            {
                "adjudication_id": "adj_gold_01",
                "predicted_edge": {"source": "str:T_CPM_Grav", "predicate": "specializes", "target": "str:T_CPM_Base"},
                "decision": "true_positive",
            },
            {
                "adjudication_id": "adj_gold_02",
                "predicted_edge": {"predicate": "derived_from"},
                "decision": "schema_alias",
                "alias_target": "str:specializes",
            },
        ]

        resp = client.post(
            "/api/evaluation/adjudications",
            json={
                "items": items,
                "export_dataset_path": str(export_file),
            },
        )
        assert resp.status_code == 200
        assert export_file.is_file()

        curated_data = json.loads(export_file.read_text(encoding="utf-8"))
        assert "@graph" in curated_data
        assert any(
            g.get("source") == "str:T_CPM_Grav"
            and g.get("target") == "str:T_CPM_Base"
            and g.get("adjudicated_status") == "true_positive"
            for g in curated_data["@graph"]
        )
        assert "@context" in curated_data
        assert curated_data["@context"].get("derived_from") == "str:specializes"

    def test_get_unknown_job_returns_404(self, client: TestClient):
        """Verify GET /api/evaluation/jobs/{job_id} returns 404 for unknown job.

        Parameters
        ----------
        client : TestClient
            Initialized test client.
        """
        resp = client.get("/api/evaluation/jobs/eval_job_unknown_9999")
        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_asynchronous_evaluation_job_lifecycle(self, tmp_path: Path):
        """Verify POST /api/evaluation/jobs/run initiates async job and reaches completed status.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture.
        """
        from httpx import ASGITransport, AsyncClient

        settings = StudioSettings(
            runs_dir=tmp_path / "runs",
            artifacts_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            token=None,
        )
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        settings.reports_dir.mkdir(parents=True, exist_ok=True)

        run_id = "test_async_job_run"
        run_art_dir = settings.artifacts_dir / run_id
        run_art_dir.mkdir(parents=True, exist_ok=True)

        atoms = [
            {"id": "str:T_CPM_Base", "text": "Base", "component_type": "theory_element"},
            {"id": "str:T_CPM_Grav", "text": "Grav", "component_type": "theory_element"},
            {"id": "str:M_CPM_Newton1", "text": "Law 1", "component_type": "actual_model"},
            {"id": "str:M_CPM_Newton2", "text": "Law 2", "component_type": "actual_model"},
            {"id": "str:M_CPM_Newton3", "text": "Law 3", "component_type": "actual_model"},
            {"id": "str:M_CPM_Grav", "text": "Grav Law", "component_type": "actual_model"},
            {"id": "str:M_CPM_Hooke", "text": "Hooke Law", "component_type": "actual_model"},
            {"id": "str:M_CPM_Free", "text": "Free Law", "component_type": "actual_model"},
            {"id": "str:Mp_CPM", "text": "Mp CPM", "component_type": "potential_model"},
            {"id": "str:Mp_Grav", "text": "Mp Grav", "component_type": "potential_model"},
            {"id": "str:Mp_Harmonic", "text": "Mp Harmonic", "component_type": "potential_model"},
            {"id": "str:Mpp_CPM", "text": "Mpp CPM", "component_type": "partial_potential_model"},
            {"id": "str:GC_Mass", "text": "GC Mass", "component_type": "constraint"},
            {"id": "str:GC_Force", "text": "GC Force", "component_type": "constraint"},
            {"id": "str:I0_PlanetaryOrbits", "text": "Planets", "component_type": "paradigm"},
            {"id": "str:I0_TerrestrialFreeFall", "text": "Fall", "component_type": "paradigm"},
            {"id": "str:I0_HarmonicSpring", "text": "Spring", "component_type": "paradigm"},
        ]
        for atom in atoms:
            env = {"artifact_id": f"art_{atom['id'].replace(':', '_')}", "kind": "theory_atom", "payload": atom}
            (run_art_dir / f"{env['artifact_id']}.json").write_text(json.dumps(env), encoding="utf-8")

        rel_env = {
            "artifact_id": "art_rel_grav_base",
            "kind": "theory_relation",
            "payload": {
                "source_id": "str:T_CPM_Grav",
                "target_id": "str:T_CPM_Base",
                "relation_type": "specializes",
            },
        }
        (run_art_dir / "art_rel_grav_base.json").write_text(json.dumps(rel_env), encoding="utf-8")

        manifest = {"run_id": run_id, "created_at": "2026-09-26T12:00:00Z", "status": "completed"}
        (settings.runs_dir / f"{run_id}.json").write_text(json.dumps(manifest), encoding="utf-8")

        app = create_app(settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            post_resp = await ac.post(
                "/api/evaluation/jobs/run",
                json={
                    "run_id": run_id,
                    "benchmark_id": "stnb_cpm_pilot",
                    "strategy": "structuralist",
                    "min_pfs": 0.4,
                },
            )
            assert post_resp.status_code == 202
            job_data = post_resp.json()
            job_id = job_data["job_id"]
            assert job_data["status"] in ("pending", "running")

            # Poll for completion
            for _ in range(30):
                await asyncio.sleep(0.1)
                get_resp = await ac.get(f"/api/evaluation/jobs/{job_id}")
                assert get_resp.status_code == 200
                status_val = get_resp.json()["status"]
                if status_val == "completed":
                    break
                assert status_val != "failed", f"Job failed: {get_resp.json().get('error')}"

            final_resp = await ac.get(f"/api/evaluation/jobs/{job_id}")
            final_data = final_resp.json()
            assert final_data["status"] == "completed"
            assert final_data["report_id"] == f"eval_{run_id}"
            assert final_data["report"] is not None
            assert final_data["report"]["outcome"] == "pass"

            # Verify events were captured in EventBroker
            broker: EventBroker = app.state.broker
            events = broker.get_history(job_id)
            assert len(events) >= 3
            kinds = [e.kind for e in events]
            assert "evaluation.job.started" in kinds
            assert "evaluation.job.completed" in kinds

    @pytest.mark.asyncio
    async def test_asynchronous_evaluation_job_sse_stream(self, tmp_path: Path):
        """Verify GET /api/evaluation/jobs/{job_id}/stream streams SSE events.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture.
        """
        from httpx import ASGITransport, AsyncClient

        settings = StudioSettings(
            runs_dir=tmp_path / "runs",
            artifacts_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            token=None,
        )
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        settings.reports_dir.mkdir(parents=True, exist_ok=True)

        app = create_app(settings)
        broker: EventBroker = app.state.broker
        job_id = "eval_job_stream_test"

        # Publish events into the broker for this job_id
        broker.publish(
            job_id,
            {
                "kind": "evaluation.job.started",
                "run_id": job_id,
                "message": "Job initiated",
            },
        )
        broker.publish(
            job_id,
            {
                "kind": "evaluation.stage.completed",
                "run_id": job_id,
                "message": "Stage verified",
            },
        )
        broker.publish(
            job_id,
            {
                "kind": "evaluation.job.completed",
                "run_id": job_id,
                "message": "Job finished",
            },
        )
        broker.close_run(job_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            async with ac.stream("GET", f"/api/evaluation/jobs/{job_id}/stream") as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                chunks: list[str] = []
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        chunks.append(line)

                assert len(chunks) == 3
                assert any("evaluation.job.started" in c for c in chunks)
                assert any("evaluation.job.completed" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_cancel_evaluation_job_lifecycle(self, tmp_path: Path):
        """Verify POST /api/evaluation/jobs/{job_id}/cancel cancels an active evaluation job.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture.
        """
        from httpx import ASGITransport, AsyncClient

        settings = StudioSettings(
            runs_dir=tmp_path / "runs",
            artifacts_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
        )
        app = create_app(settings)
        from episteme_studio.services.evaluation_service import EvaluationService

        eval_service = EvaluationService.from_settings(settings)
        app.state.evaluation_service = eval_service

        async def slow_evaluate_run(*args, **kwargs):
            await asyncio.sleep(1.0)
            return await eval_service.adapter.evaluate_run(*args, **kwargs)

        eval_service.evaluate_run = slow_evaluate_run

        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Start a job
            post_resp = await ac.post(
                "/api/evaluation/jobs/run",
                json={
                    "run_id": "test_cancellation_run",
                    "benchmark_id": "stnb_cpm_pilot",
                    "strategy": "structuralist",
                },
            )
            assert post_resp.status_code == 202
            job_id = post_resp.json()["job_id"]

            # 2. Cancel the job
            cancel_resp = await ac.post(f"/api/evaluation/jobs/{job_id}/cancel")
            assert cancel_resp.status_code == 200
            cancel_data = cancel_resp.json()
            assert cancel_data["job_id"] == job_id
            assert cancel_data["status"] == "aborted"

            # 3. Verify get_job returns aborted status
            get_resp = await ac.get(f"/api/evaluation/jobs/{job_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["status"] == "aborted"

    @pytest.mark.asyncio
    async def test_cancel_unknown_job_returns_404(self, tmp_path: Path):
        """Verify cancelling a non-existent job returns 404."""
        from httpx import ASGITransport, AsyncClient

        settings = StudioSettings(
            runs_dir=tmp_path / "runs",
            artifacts_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
        )
        app = create_app(settings)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/evaluation/jobs/eval_job_unknown_xyz/cancel")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_evaluate_run_request_boundary_validation(self, tmp_path: Path):
        """Verify Pydantic validation rejects out-of-range thresholds."""
        from httpx import ASGITransport, AsyncClient

        settings = StudioSettings(
            runs_dir=tmp_path / "runs",
            artifacts_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
        )
        app = create_app(settings)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # sim_threshold out of range [0.0, 1.0]
            resp_sim = await ac.post(
                "/api/evaluation/jobs/run",
                json={"run_id": "test_run", "sim_threshold": 1.5},
            )
            assert resp_sim.status_code == 422

            # delta_star out of range [0.0, 0.50]
            resp_delta = await ac.post(
                "/api/evaluation/jobs/run",
                json={"run_id": "test_run", "delta_star": 0.8},
            )
            assert resp_delta.status_code == 422

            # min_mcc out of range [0.0, 1.0]
            resp_mcc = await ac.post(
                "/api/evaluation/jobs/run",
                json={"run_id": "test_run", "min_mcc": -0.1},
            )
            assert resp_mcc.status_code == 422


class TestEvaluationWorkbenchEndpoints:
    """Comprehensive test suite for evaluation workbench endpoints (ISSUE-026 - ISSUE-033)."""

    @pytest.fixture
    def test_env(self, tmp_path: Path):
        """Prepare temporary test environment with a persisted evaluation report."""
        runs_dir = tmp_path / "runs"
        reports_dir = tmp_path / "reports"
        runs_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        eval_id = "eval_bench_test_01"
        report_data = {
            "evaluation_id": eval_id,
            "run_ids": ["run_bench_test_01"],
            "dataset_ref": "stnb_cpm_pilot",
            "dataset_type": "gold",
            "outcome": "pass",
            "key_metrics": {"f1": 0.88, "mcc": 1.0, "pfs": 0.85, "mrr": 0.80, "ece": 0.04},
            "omitted_components": ["str:CPM_Axiom_3_ActionReaction"],
            "violations": [{"type": "disjointness", "node_id": "pred:Unverified_Kinematic_Claim"}],
            "model_decomposition": [
                {
                    "class_name": "actual_models",
                    "symbol": "M",
                    "reference_count": 3,
                    "predicted_count": 2,
                    "matched_count": 2,
                    "completeness": 0.67,
                }
            ],
            "summary_markdown": "## Bench Test Report\n- F1: 0.88",
        }
        (reports_dir / f"report_{eval_id}.json").write_text(json.dumps(report_data), encoding="utf-8")
        (reports_dir / f"report_{eval_id}.md").write_text(report_data["summary_markdown"], encoding="utf-8")

        settings = StudioSettings(
            runs_dir=runs_dir,
            reports_dir=reports_dir,
            eval_data_dir=tmp_path / "data",
        )
        app = create_app(settings)
        client = TestClient(app)
        return {"client": client, "eval_id": eval_id, "reports_dir": reports_dir, "run_id": "run_bench_test_01"}

    def test_graph_overlay_endpoints(self, test_env):
        """Verify graph canvas overlay endpoint returns classified nodes and ghost nodes (ISSUE-026)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]
        run_id = test_env["run_id"]

        # Test evaluation report overlay
        resp = client.get(f"/api/evaluation/reports/{eval_id}/graph-overlay?include_ghosts=true")
        assert resp.status_code == 200
        overlay = resp.json()
        assert overlay["evaluation_id"] == eval_id
        assert len(overlay["nodes"]) >= 2
        assert len(overlay["edges"]) >= 1
        assert overlay["summary_counts"]["fn_nodes"] >= 1
        ghost_node = next((n for n in overlay["nodes"] if n["is_ghost"]), None)
        assert ghost_node is not None
        assert ghost_node["alignment_status"] == "false_negative"

        # Test run-centric overlay endpoint
        resp_run = client.get(f"/api/runs/{run_id}/evaluation/graph-overlay")
        assert resp_run.status_code == 200
        assert resp_run.json()["evaluation_id"] == run_id

    def test_adjudication_queue_and_recalculate(self, test_env):
        """Verify HITL adjudication queue and live metric recalculation (ISSUE-027)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]

        # Get queue
        resp = client.get(f"/api/evaluation/reports/{eval_id}/adjudication-queue?status=pending")
        assert resp.status_code == 200
        queue = resp.json()
        assert queue["evaluation_id"] == eval_id
        assert queue["total_candidates"] >= 1
        assert len(queue["candidates"]) >= 1

        cand = queue["candidates"][0]

        # Submit adjudication and recalculate
        adj_payload = {
            "items": [
                {
                    "adjudication_id": f"adj_{cand['candidate_id']}",
                    "predicted_edge": cand["predicted_edge"],
                    "reference_edge": cand["reference_edge"],
                    "similarity_score": cand["similarity_score"],
                    "decision": "true_positive",
                    "rationale": "Verified correct by physics domain expert.",
                }
            ]
        }
        recalc_resp = client.post(
            f"/api/evaluation/reports/{eval_id}/adjudicate-and-recalculate",
            json=adj_payload,
        )
        assert recalc_resp.status_code == 200
        recalc_data = recalc_resp.json()
        assert recalc_data["adjudicated_count"] == 1
        assert "f1" in recalc_data["metric_deltas"]
        assert recalc_data["metric_deltas"]["f1"] > 0
        assert recalc_data["updated_report"]["key_metrics"]["f1"] > 0.88

    def test_calibration_diagnostics(self, test_env):
        """Verify confidence calibration and reliability diagram endpoint (ISSUE-028)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]
        run_id = test_env["run_id"]

        resp = client.get(f"/api/evaluation/reports/{eval_id}/calibration")
        assert resp.status_code == 200
        calib = resp.json()
        assert calib["evaluation_id"] == eval_id
        assert len(calib["bins"]) == 10
        assert calib["expected_calibration_error"] >= 0.0
        assert calib["brier_score"] >= 0.0
        assert len(calib["high_confidence_hallucinations"]) >= 1
        assert "accuracies" in calib["chart_series"]

        # Run-centric calibration
        resp_run = client.get(f"/api/runs/{run_id}/evaluation/calibration")
        assert resp_run.status_code == 200

    def test_multimodal_evidence_grounding(self, test_env):
        """Verify deep multimodal evidence grounding inspection endpoint (ISSUE-029)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]
        run_id = test_env["run_id"]

        comp_id = "str:CPM_Axiom_2_Force"
        resp = client.get(f"/api/evaluation/reports/{eval_id}/evidence/{comp_id}")
        assert resp.status_code == 200
        evidence = resp.json()
        assert evidence["component_id"] == comp_id
        assert evidence["predicted_anchor"] is not None
        assert evidence["predicted_anchor"]["bbox"] is not None
        assert evidence["predicted_anchor"]["bbox"]["page"] == 14
        assert evidence["iou_score"] > 0.50

        # Run-centric evidence
        resp_run = client.get(f"/api/runs/{run_id}/evaluation/evidence/{comp_id}")
        assert resp_run.status_code == 200

    def test_leaderboard_and_pareto_frontier(self, test_env):
        """Verify multi-run benchmark leaderboard matrix and Pareto frontier (ISSUE-030)."""
        client = test_env["client"]

        # Test POST
        resp_post = client.post(
            "/api/evaluation/leaderboard",
            json={"pareto_axes": ["f1", "ece"], "sort_by": "f1"},
        )
        assert resp_post.status_code == 200
        lb_post = resp_post.json()
        assert lb_post["total_runs"] >= 2
        assert len(lb_post["pareto_frontier"]) >= 1
        assert any(e["is_pareto_optimal"] for e in lb_post["entries"])
        assert "Multi-Run Benchmark Leaderboard" in lb_post["summary_markdown"]

        # Test GET
        resp_get = client.get("/api/evaluation/leaderboard?sort_by=f1")
        assert resp_get.status_code == 200
        assert resp_get.json()["total_runs"] >= 2

    def test_noise_robustness_stress_test(self, test_env):
        """Verify adversarial noise robustness stress test and curves (ISSUE-031)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]
        run_id = test_env["run_id"]

        stress_req = {
            "run_id": run_id,
            "perturbation_types": ["typo_insertion", "synonym_replacement"],
            "noise_levels": [0.05, 0.10, 0.20],
        }
        resp = client.post("/api/evaluation/stress-test", json=stress_req)
        assert resp.status_code == 201
        stress_data = resp.json()
        assert stress_data["run_id"] == run_id
        assert stress_data["overall_rdf"] >= 0.0
        assert "typo_insertion" in stress_data["breakdown_by_perturbation"]
        assert len(stress_data["breakdown_by_perturbation"]["typo_insertion"]) == 3

        # Retrieve report
        resp_get = client.get(f"/api/evaluation/reports/{run_id}/robustness")
        assert resp_get.status_code == 200
        assert resp_get.json()["run_id"] == run_id

    def test_retrieval_diagnostics(self, test_env):
        """Verify competency question per-query diagnostics endpoint (ISSUE-032)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]

        resp = client.get(f"/api/evaluation/reports/{eval_id}/retrieval-diagnostics")
        assert resp.status_code == 200
        diag = resp.json()
        assert diag["evaluation_id"] == eval_id
        assert diag["total_queries"] >= 1
        assert diag["mrr"] > 0.0
        assert len(diag["queries"]) >= 1
        q0 = diag["queries"][0]
        assert "query_text" in q0
        assert len(q0["retrieved_candidates"]) >= 1

    def test_benchmark_validation_and_registration(self, test_env):
        """Verify pre-flight benchmark validation and registration (ISSUE-033)."""
        client = test_env["client"]

        # Valid DAG benchmark
        valid_jsonld = json.dumps(
            {
                "@graph": [
                    {"@id": "str:Root", "rdfs:label": "Root Law"},
                    {"@id": "str:SubLaw", "rdfs:label": "Specialized Law", "source": "str:Root", "target": "str:SubLaw", "relation": "SPECIALIZES_TO"},
                ]
            }
        )
        resp_valid = client.post("/api/evaluation/benchmarks/validate", json={"content": valid_jsonld})
        assert resp_valid.status_code == 200
        val_res = resp_valid.json()
        assert val_res["is_valid"] is True
        assert val_res["is_dag"] is True

        # Cyclic benchmark
        cyclic_jsonld = json.dumps(
            {
                "@graph": [
                    {"@id": "str:A", "source": "str:A", "target": "str:B"},
                    {"@id": "str:B", "source": "str:B", "target": "str:A"},
                ]
            }
        )
        resp_cyclic = client.post("/api/evaluation/benchmarks/validate", json={"content": cyclic_jsonld})
        assert resp_cyclic.status_code == 200
        cyclic_res = resp_cyclic.json()
        assert cyclic_res["is_valid"] is False
        assert cyclic_res["is_dag"] is False
        assert any(i["rule_id"] == "DAG_CYCLE_DETECTED" for i in cyclic_res["issues"])

        # Register custom benchmark
        reg_payload = {
            "id": "quantum_mechanics_pilot",
            "name": "Quantum Mechanics Pilot",
            "description": "Dirac-von Neumann formulation of quantum theory",
            "task_type": "structuralist",
            "gold_standard_jsonld": valid_jsonld,
        }
        try:
            reg_resp = client.post("/api/evaluation/benchmarks", json=reg_payload)
            assert reg_resp.status_code == 201
            assert reg_resp.json()["id"] == "quantum_mechanics_pilot"
        finally:
            bench_path = Path("packages/episteme-pipeline/episteme_pipeline/evaluation/data/quantum_mechanics_pilot.jsonld")
            if bench_path.is_file():
                bench_path.unlink()

    def test_export_report_formats(self, test_env):
        """Verify LaTeX, CSV, and JSON-LD report export (ISSUE-033)."""
        client = test_env["client"]
        eval_id = test_env["eval_id"]

        # LaTeX export
        resp_tex = client.get(f"/api/evaluation/reports/{eval_id}/export?format=latex")
        assert resp_tex.status_code == 200
        assert "text/x-tex" in resp_tex.headers.get("content-type", "")
        assert "\\begin{table}" in resp_tex.text
        assert "\\toprule" in resp_tex.text

        # CSV export
        resp_csv = client.get(f"/api/evaluation/reports/{eval_id}/export?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers.get("content-type", "")
        assert "metric,value" in resp_csv.text

        # JSON-LD export
        resp_json = client.get(f"/api/evaluation/reports/{eval_id}/export?format=jsonld")
        assert resp_json.status_code == 200
        assert "application/ld+json" in resp_json.headers.get("content-type", "")
        parsed = json.loads(resp_json.text)
        assert parsed["evaluation_id"] == eval_id


class TestStudioDemoModeEvaluation:
    """Test suite validating studio --demo mode with Festinger & Carlsmith (1959) cognitive dissonance."""

    @pytest.fixture
    def demo_client(self, tmp_path: Path):
        """Create a TestClient initialized in demo mode isolated to tmp_path."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        settings = StudioSettings(
            demo_mode=True,
            reports_dir=reports_dir,
            token=None,
        )
        app = create_app(settings)
        return TestClient(app)

    def test_demo_mode_run_and_reports_discovery(self, demo_client: TestClient):
        """Verify demo mode discovers run-demo-festinger1959 and canned evaluation reports."""
        # 1. Runs endpoint discovers run-demo-festinger1959
        runs_resp = demo_client.get("/api/runs")
        assert runs_resp.status_code == 200
        run_ids = [r["run_id"] for r in runs_resp.json()]
        assert "run-demo-festinger1959" in run_ids

        # 2. Evaluation reports discovery includes Festinger report
        rep_resp = demo_client.get("/api/evaluation/reports")
        assert rep_resp.status_code == 200
        rep_eval_ids = [r["evaluation_id"] for r in rep_resp.json()]
        assert any("festinger1959" in eid for eid in rep_eval_ids)

        # 3. Linked evaluation on run endpoint
        run_eval_resp = demo_client.get("/api/runs/run-demo-festinger1959/evaluation")
        assert run_eval_resp.status_code == 200
        run_eval = run_eval_resp.json()
        assert run_eval is not None
        assert run_eval["outcome"] == "pass"

    def test_demo_evaluation_metrics_and_decomposition(self, demo_client: TestClient):
        """Verify Festinger report achieves gold metrics and full Bourbaki model decomposition."""
        resp = demo_client.get("/api/evaluation/reports/eval_run-demo-festinger1959")
        assert resp.status_code == 200
        detail = resp.json()

        metrics = detail["key_metrics"]
        assert metrics["mcc"] == 1.0
        assert metrics["aor"] == 0.0
        assert metrics["ag_iou"] == 1.0
        assert metrics["edge_fidelity"] == 1.0
        assert metrics["poset_f1"] == 1.0
        assert metrics["root_conformity"] == 1.0

        # Bourbaki model decomposition grid
        decomp = {d["class_name"]: d for d in detail["model_decomposition"]}
        assert "potential_models" in decomp
        assert "actual_models" in decomp
        assert "paradigms" in decomp
        assert "theory_elements" in decomp
        assert decomp["potential_models"]["completeness"] == 1.0
        assert decomp["actual_models"]["completeness"] == 1.0

        # Specialization Poset DAG
        poset = detail["poset_detail"]
        assert poset["is_dag"] is True
        assert poset["root_conformity"] is True
        assert poset["root_element"] == "str:TE_DissF"
        assert poset["transitive_reduction_f1"] == 1.0

        # Polarity Concordance
        polarity = detail["polarity_detail"]
        assert polarity is not None
        assert polarity["polarity_accuracy"] == 1.0
        assert polarity["polarity_conflict_rate"] == 0.0

    def test_topological_canvas_overlay(self, demo_client: TestClient):
        """Verify graph canvas overlay includes true positives, dialectical attacks, and summary counts."""
        resp = demo_client.get("/api/evaluation/reports/eval_run-demo-festinger1959/graph-overlay")
        assert resp.status_code == 200
        overlay = resp.json()

        assert len(overlay["nodes"]) == 9
        assert len(overlay["edges"]) == 8

        # Check attack edges are preserved
        attack_edges = [e for e in overlay["edges"] if e["predicate"] == "attacks"]
        assert len(attack_edges) == 2

        # Check nodes have structuralist symbols
        symbols = {n["id"]: n["symbol"] for n in overlay["nodes"]}
        assert symbols["str:MP_DissF6"] == "Mp"
        assert symbols["str:M_DissF6_RatioLaw"] == "M"
        assert symbols["str:I0_Carlsmith1959"] == "I0"
        assert symbols["str:TE_DissF"] == "T"

    def test_hitl_adjudication_desk(self, demo_client: TestClient):
        """Verify borderline candidate review queue and dynamic recalculation for Festinger."""
        queue_resp = demo_client.get("/api/evaluation/reports/eval_run-demo-festinger1959/adjudication-queue")
        assert queue_resp.status_code == 200
        queue = queue_resp.json()
        assert queue["total_candidates"] >= 3

        # Submit adjudication decision
        cand = queue["candidates"][0]
        adj_payload = {
            "items": [
                {
                    "candidate_id": cand["candidate_id"],
                    "evaluation_id": "eval_run-demo-festinger1959",
                    "predicted_edge": cand["predicted_edge"],
                    "reference_edge": cand["reference_edge"],
                    "decision": "true_positive",
                    "notes": "Verified experimentally in Festinger & Carlsmith Table 1.",
                }
            ]
        }
        recalc_resp = demo_client.post(
            "/api/evaluation/reports/eval_run-demo-festinger1959/adjudicate-and-recalculate",
            json=adj_payload,
        )
        assert recalc_resp.status_code == 200
        recalc = recalc_resp.json()
        assert recalc["adjudicated_count"] == 1
        assert "f1" in recalc["metric_deltas"]

    def test_calibration_lab(self, demo_client: TestClient):
        """Verify calibration report, reliability bins, and overconfidence errors."""
        calib_resp = demo_client.get("/api/evaluation/reports/eval_run-demo-festinger1959/calibration")
        assert calib_resp.status_code == 200
        calib = calib_resp.json()

        assert len(calib["bins"]) == 10
        assert calib["expected_calibration_error"] >= 0.0
        assert len(calib["high_confidence_hallucinations"]) >= 1

        # Check domain-appropriate cognitive dissonance hallucinations
        halluc_text = calib["high_confidence_hallucinations"][0]["descriptor"]
        assert any(k in halluc_text for k in ("RatioLaw", "Bem", "Janis"))

    def test_multimodal_document_grounding(self, demo_client: TestClient):
        """Verify text anchor grounding with exact character offsets in festinger_carlsmith_1959.md."""
        evidence_resp = demo_client.get(
            "/api/evaluation/reports/eval_run-demo-festinger1959/evidence/str:M_DissF6_RatioLaw"
        )
        assert evidence_resp.status_code == 200
        grounding = evidence_resp.json()

        assert grounding["component_id"] == "str:M_DissF6_RatioLaw"
        assert grounding["iou_score"] == 1.0
        assert grounding["grounding_passed"] is True

        pred = grounding["predicted_anchor"]
        assert pred["doc_id"] == "festinger_carlsmith_1959.md"
        assert pred["char_start"] == 3723
        assert pred["char_end"] == 4072
        assert "total magnitude of dissonance" in pred["verbatim_text"]
        assert pred["formula_latex"] is not None

    def test_competency_retrieval_diagnostics(self, demo_client: TestClient):
        """Verify 6 competency queries breakdown and ranking metrics."""
        diag_resp = demo_client.get("/api/evaluation/reports/eval_run-demo-festinger1959/retrieval-diagnostics")
        assert diag_resp.status_code == 200
        diag = diag_resp.json()

        assert diag["total_queries"] == 6
        assert diag["mrr"] == 1.0
        assert diag["hits_at_1"] == 1.0
        assert len(diag["queries"]) == 6
        assert diag["queries"][0]["query_id"] == "fc_q01"
        assert diag["queries"][0]["first_hit_rank"] == 1

    def test_noise_robustness_stress_test(self, demo_client: TestClient):
        """Verify noise robustness report retrieval and stress test execution."""
        rob_resp = demo_client.get("/api/evaluation/reports/eval_run-demo-festinger1959/robustness")
        assert rob_resp.status_code == 200
        rob = rob_resp.json()

        assert rob["overall_rdf"] >= 0.0
        assert "typo_insertion" in rob["breakdown_by_perturbation"]

        # Run synthetic stress test
        stress_payload = {
            "run_id": "run-demo-festinger1959",
            "perturbation_types": ["typo_insertion", "synonym_replacement"],
            "noise_levels": [0.05, 0.10, 0.20],
        }
        stress_resp = demo_client.post(
            "/api/evaluation/stress-test",
            json=stress_payload,
        )
        assert stress_resp.status_code == 201
        stress_res = stress_resp.json()
        assert len(stress_res["breakdown_by_perturbation"]) == 2

    def test_multi_run_leaderboard(self, demo_client: TestClient):
        """Verify multi-run benchmark leaderboard matrix and Pareto frontier calculation."""
        board_payload = {
            "sort_by": "f1",
            "ascending": False,
            "pareto_axes": ["f1", "ece"],
        }
        board_resp = demo_client.post("/api/evaluation/leaderboard", json=board_payload)
        assert board_resp.status_code == 200
        board = board_resp.json()

        assert board["total_runs"] >= 2
        assert len(board["entries"]) >= 2
        assert len(board["pareto_frontier"]) >= 1
        assert "Multi-Run Benchmark Leaderboard" in board["summary_markdown"]



