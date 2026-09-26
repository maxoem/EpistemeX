"""Comprehensive unit and integration tests for the Studio evaluation backend.

Verifies:
1. Pure domain models serialization and threshold verification.
2. Anti-corruption EvaluationAdapter discovery and pipeline bridging.
3. EvaluationService orchestration (report discovery, in-memory run evaluation).
4. FastAPI REST endpoints for reports, benchmarks, manifests, comparisons, and run evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.adapters.evaluation_adapter import EvaluationAdapter
from episteme_studio.app import create_app
from episteme_studio.domain.evaluation import (
    BenchmarkDescriptor,
    ComparativeMetricDelta,
    EvaluateRunRequest,
    EvaluationOutcome,
    EvaluationReportDetail,
    EvaluationReportSummary,
    ModelDecompositionEntry,
    PosetEvaluationDetail,
)
from episteme_studio.services.evaluation_service import EvaluationService
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

