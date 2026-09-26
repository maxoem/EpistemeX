"""Unit and integration tests for the evaluation pipeline example implementation.

Verifies:
1. Sample CPM TheoryNet construction and structuralist model decomposition.
2. Specialization poset verification and capability subsumption.
3. Schema-driven polarity concordance and topological error tracking.
4. Extrinsic downstream retrieval competency query evaluation.
5. Comparative baseline benchmarking against BaselineNaiveKG.
6. Manifest-driven batch evaluation, event bus telemetry, and report persistence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR.parent))

from episteme_pipeline.evaluation.models import EvaluationLevel, EvaluationOutcome
from examples.pipeline_evaluation_run import (
    create_sample_cpm_theory_net,
    parse_args,
    run_baseline_comparison_demo,
    run_manifest_demo,
    run_polarity_alignment_demo,
    run_retrieval_demo,
    run_structuralist_demo,
)


class TestEvaluationPipelineExample:
    """Test suite for the pipeline_evaluation_run.py example script."""

    def test_sample_cpm_theory_net_integrity(self):
        """Verify the sample CPM TheoryNet has all formal structuralist components."""
        net = create_sample_cpm_theory_net()

        assert len(net.atoms) == 19
        assert len(net.relations) == 3

        component_types = {atom.component_type for atom in net.atoms}
        assert "theory_element" in component_types
        assert "actual_model" in component_types
        assert "potential_model" in component_types
        assert "partial_potential_model" in component_types
        assert "constraint" in component_types
        assert "paradigm" in component_types

        # Verify all specialization relations point to root CPM base element
        for rel in net.relations:
            assert rel.relation_type == "specializes"
            assert rel.target_id == "str:T_CPM_Base"

    @pytest.mark.asyncio
    async def test_run_structuralist_demo(self):
        """Verify Scenario 1 satisfies capability subsumption and DAG properties."""
        report = await run_structuralist_demo(verbose=False)

        assert report.evaluation_id == "eval_cpm_principia_structuralist_eval"
        assert str(EvaluationLevel.STAGE) in report.results_by_level

        stage_results = report.results_by_level[str(EvaluationLevel.STAGE)]
        assert len(stage_results) > 0

        metrics = {m.name: m.value for res in stage_results for m in res.metrics}
        assert metrics.get("mcc", 0.0) >= 1.0
        assert metrics.get("aor", 1.0) == 0.0
        assert metrics.get("pfs", 0.0) >= 0.4
        assert metrics.get("is_dag", 0.0) == 1.0

        for res in stage_results:
            assert res.outcome == EvaluationOutcome.PASS

    @pytest.mark.asyncio
    async def test_run_polarity_alignment_demo(self):
        """Verify Scenario 2 accurately calculates polarity concordance and OEP error rates."""
        metrics = await run_polarity_alignment_demo(verbose=False)

        assert "polarity_accuracy" in metrics
        assert "polarity_conflict_rate" in metrics
        assert "alignment_score" in metrics
        assert "hallucination_rate" in metrics
        assert "omission_rate" in metrics

        # In the demo setup, 1 of 2 shared pairs matches, and 1 has conflicting polarity (SUPPORTS vs REFUTES)
        assert metrics["polarity_accuracy"] == 0.5
        assert metrics["polarity_conflict_rate"] == 0.5
        assert 0.0 <= metrics["hallucination_rate"] <= 1.0
        assert 0.0 <= metrics["omission_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_run_retrieval_demo(self):
        """Verify Scenario 3 executes batch competency queries and computes IR metrics."""
        metrics = await run_retrieval_demo(verbose=False)

        assert "MRR" in metrics
        assert "Hits@1" in metrics
        assert "Hits@3" in metrics
        assert "Hits@10" in metrics
        assert "nDCG" in metrics

    @pytest.mark.asyncio
    async def test_run_baseline_comparison_demo(self):
        """Verify Scenario 4 computes pairwise deltas against BaselineNaiveKG."""
        comp = await run_baseline_comparison_demo(verbose=False)

        assert comp.comparison_id == "comp_pipeline_vs_naive_kg"
        assert len(comp.pairwise_comparisons) > 0
        assert "Baseline" in comp.summary
        assert "Pipeline" in comp.summary

    @pytest.mark.asyncio
    async def test_run_manifest_demo_with_custom_reports_dir(self, tmp_path: Path):
        """Verify Scenario 5 persists structured JSON and Markdown reports to target directory."""
        reports_dir = tmp_path / "custom_reports"
        report = await run_manifest_demo(
            reports_dir=reports_dir,
            verbose=False,
        )

        assert report.evaluation_id == "eval_stnb_cpm_pilot_eval_01"

        json_file = reports_dir / f"report_{report.run_ids[0]}.json"
        md_file = reports_dir / f"report_{report.run_ids[0]}.md"

        assert json_file.is_file(), f"Expected JSON report at {json_file}"
        assert md_file.is_file(), f"Expected Markdown report at {md_file}"

        json_content = json_file.read_text(encoding="utf-8")
        assert "eval_stnb_cpm_pilot_eval_01" in json_content

        md_content = md_file.read_text(encoding="utf-8")
        assert "# Evaluation Report:" in md_content

    def test_cli_argument_parsing(self, monkeypatch):
        """Verify CLI argument parser handles all supported scenario flags."""
        monkeypatch.setattr("sys.argv", ["pipeline_evaluation_run.py", "--mode", "structuralist", "-v"])
        args = parse_args()
        assert args.mode == "structuralist"
        assert args.verbose is True
        assert args.baseline == "naive_kg"
