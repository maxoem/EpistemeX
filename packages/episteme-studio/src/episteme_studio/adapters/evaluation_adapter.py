"""Anti-corruption adapter bridging pipeline evaluation to GLP Studio domain.

In accordance with architectural constraint D-01 and SPEC §2, this adapter
is the ONLY module within the evaluation subsystem permitted to import from
`episteme_pipeline.*` or `epistemetrics.*`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import networkx as nx
import yaml

from episteme_pipeline.contracts.domain import (
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.evaluation.baselines import (
    BaselineNaiveKG,
    BaselineTextRAG,
    BaselineZeroShotLLM,
)
from episteme_pipeline.evaluation.comparison import (
    ComparisonAxis,
    compute_run_comparisons,
    format_comparison_markdown,
)
from episteme_pipeline.evaluation.harness import EvaluationHarness
from episteme_pipeline.evaluation.models import (
    EvaluationLevel,
    EvaluationOutcome as PipelineOutcome,
    EvaluationReport as PipelineEvaluationReport,
    EvaluationResult as PipelineEvaluationResult,
)
from episteme_pipeline.evaluation.scorers.domain_bridge import (
    l2_triples_to_digraph,
    theory_net_to_digraph,
)
from episteme_pipeline.evaluation.scorers.retrieval import ExtrinsicRetrievalEvaluator
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig
from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.domain.evaluation import (
    BenchmarkDescriptor,
    ComparativeEvaluationResponse,
    ComparativeMetricDelta,
    EvaluationLevelResult,
    EvaluationMetricValue,
    EvaluationOutcome,
    EvaluationReportDetail,
    EvaluationReportSummary,
    ModelDecompositionEntry,
    PolarityConcordanceDetail,
    PosetEvaluationDetail,
    RetrievalEvaluationDetail,
)

logger = logging.getLogger(__name__)

def _resolve_pipeline_root() -> Path:
    """Resolve the episteme-pipeline package root directory resiliently."""
    curr = Path(__file__).resolve()
    for parent in curr.parents:
        cand = parent / "packages" / "episteme-pipeline"
        if cand.is_dir():
            return cand
        cand_direct = parent / "episteme-pipeline"
        if cand_direct.is_dir():
            return cand_direct
    return Path("packages/episteme-pipeline")


_PIPELINE_ROOT = _resolve_pipeline_root()
_DEFAULT_EVAL_DATA_DIR = _PIPELINE_ROOT / "episteme_pipeline" / "evaluation" / "data"
_DEFAULT_EVAL_MANIFESTS_DIR = _PIPELINE_ROOT / "episteme_pipeline" / "evaluation" / "manifests"


class EvaluationAdapter:
    """Anti-corruption adapter orchestrating pipeline evaluation and report discovery.

    Parameters
    ----------
    reports_dir : Path or str
        Filesystem directory storing serialized JSON/Markdown evaluation reports.
    eval_data_dir : Path or str, optional
        Filesystem directory hosting gold benchmark datasets.
    manifests_dir : Path or str, optional
        Filesystem directory hosting evaluation YAML manifests.
    """

    def __init__(
        self,
        reports_dir: Path | str = "evaluation/reports",
        eval_data_dir: Path | str | None = None,
        manifests_dir: Path | str | None = None,
    ) -> None:
        self.reports_dir = Path(reports_dir)
        self.eval_data_dir = Path(eval_data_dir) if eval_data_dir else _DEFAULT_EVAL_DATA_DIR
        self.manifests_dir = Path(manifests_dir) if manifests_dir else _DEFAULT_EVAL_MANIFESTS_DIR

    def discover_benchmarks(self) -> list[BenchmarkDescriptor]:
        """Discover registered gold-standard benchmarks available on filesystem.

        Returns
        -------
        list of BenchmarkDescriptor
            Available benchmark descriptors.
        """
        cpm_gold = self.eval_data_dir / "stnb_cpm_pilot.jsonld"
        cpm_queries = self.eval_data_dir / "stnb_cpm_queries.yaml"

        benchmarks: list[BenchmarkDescriptor] = [
            BenchmarkDescriptor(
                id="stnb_cpm_pilot",
                name="STNB Classical Particle Mechanics (CPM Pilot)",
                description=(
                    "Formal structuralist reconstruction of Newton's Principia (1687) "
                    "following Balzer et al. (1987). Verifies Bourbaki model decomposition, "
                    "axiom coverage, and specialization posets."
                ),
                task_type="structuralist",
                gold_standard_path=str(cpm_gold),
                queries_path=str(cpm_queries) if cpm_queries.is_file() else None,
                available=cpm_gold.is_file(),
            ),
            BenchmarkDescriptor(
                id="stnb_competency_queries",
                name="Principia Downstream Competency Suite",
                description=(
                    "Batch information retrieval competency query testbed evaluating "
                    "downstream utility via MRR, Hits@k, and nDCG."
                ),
                task_type="retrieval",
                gold_standard_path=str(cpm_gold),
                queries_path=str(cpm_queries),
                available=cpm_queries.is_file(),
            ),
        ]

        # Scan for any additional .jsonld or .json gold files in eval_data_dir
        if self.eval_data_dir.is_dir():
            for p in self.eval_data_dir.glob("*.jsonld"):
                if p.stem != "stnb_cpm_pilot":
                    benchmarks.append(
                        BenchmarkDescriptor(
                            id=p.stem,
                            name=f"Benchmark: {p.stem}",
                            description=f"Auto-discovered gold benchmark from {p.name}",
                            task_type="structuralist",
                            gold_standard_path=str(p),
                            available=True,
                        )
                    )

        return benchmarks

    def discover_manifests(self) -> list[dict[str, Any]]:
        """Discover existing evaluation YAML manifests.

        Returns
        -------
        list of dict of str to Any
            Manifest descriptors with id, path, run_id, and task_type.
        """
        manifests: list[dict[str, Any]] = []
        if not self.manifests_dir.is_dir():
            return manifests

        for p in sorted(self.manifests_dir.glob("*.yaml")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                manifests.append(
                    {
                        "id": p.stem,
                        "path": str(p),
                        "run_id": data.get("run_id", p.stem),
                        "dataset_type": data.get("corpus", {}).get("dataset_type", "unknown"),
                        "strategy": data.get("strategy") or data.get("corpus", {}).get("strategy"),
                        "gold_path": data.get("corpus", {}).get("gold_standard_path"),
                    }
                )
            except Exception as e:
                logger.debug("Failed to inspect manifest %s: %s", p, e)

        return manifests

    def list_reports(
        self,
        run_id: str | None = None,
        outcome: str | None = None,
    ) -> list[EvaluationReportSummary]:
        """Scan reports_dir and return summary descriptors for all serialized reports.

        Parameters
        ----------
        run_id : str or None, optional
            Filter by participating run identifier.
        outcome : str or None, optional
            Filter by evaluation outcome ('pass', 'fail', 'warning').

        Returns
        -------
        list of EvaluationReportSummary
            Summaries sorted by generation timestamp (newest first).
        """
        if not self.reports_dir.is_dir():
            return []

        summaries: list[EvaluationReportSummary] = []
        for p in sorted(self.reports_dir.glob("report_*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summary = self._map_json_to_summary(data, p)

                if run_id and run_id not in summary.run_ids:
                    continue
                if outcome and summary.outcome.value.lower() != outcome.lower():
                    continue

                summaries.append(summary)
            except Exception as e:
                logger.debug("Error reading report JSON %s: %s", p, e)

        return summaries

    def get_report(self, evaluation_id: str) -> EvaluationReportDetail | None:
        """Load and parse the complete detailed report for an evaluation ID.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier (e.g. 'eval_run_01' or 'run_01').

        Returns
        -------
        EvaluationReportDetail or None
            Detailed report if found, None otherwise.
        """
        if not self.reports_dir.is_dir():
            return None

        # Clean search keys
        clean_id = evaluation_id.removeprefix("eval_")
        candidates = [
            self.reports_dir / f"report_{clean_id}.json",
            self.reports_dir / f"report_{evaluation_id}.json",
            self.reports_dir / f"report_eval_{clean_id}.json",
        ]

        target_file: Path | None = None
        for cand in candidates:
            if cand.is_file():
                target_file = cand
                break

        if not target_file:
            # Fallback search across directory
            for p in self.reports_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get("evaluation_id") == evaluation_id or clean_id in d.get("run_ids", []):
                        target_file = p
                        break
                except Exception:
                    continue

        if not target_file:
            return None

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            md_path = target_file.with_suffix(".md")
            md_content = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
            return self._map_json_to_detail(data, target_file, md_content=md_content)
        except Exception as e:
            logger.error("Failed to parse evaluation report detail from %s: %s", target_file, e)
            return None

    async def evaluate_run(
        self,
        run_id: str,
        reader: ArtifactReader,
        gold_standard_path: str | Path | None = None,
        benchmark_id: str | None = None,
        queries_path: str | Path | None = None,
        strategy: str | None = None,
        baseline: str | None = None,
        min_mcc: float = 1.0,
        min_pfs: float = 0.8,
        sim_threshold: float = 0.50,
        persist: bool = True,
    ) -> EvaluationReportDetail:
        """Evaluate a completed pipeline run against a gold standard in-memory.

        Parameters
        ----------
        run_id : str
            Identifier of target run to evaluate.
        reader : ArtifactReader
            Studio artifact reader to load run intermediate outputs.
        gold_standard_path : str or Path, optional
            Path to gold benchmark annotations.
        benchmark_id : str, optional
            Identifier of registered benchmark if path omitted.
        queries_path : str or Path, optional
            Path to competency retrieval queries YAML.
        strategy : str, optional
            Evaluation strategy override ('structuralist', 'extraction', etc.).
        baseline : str, optional
            Comparative baseline to evaluate alongside ('naive_kg', 'text_rag').
        min_mcc : float, default 1.0
            Minimum Model Component Completeness threshold.
        min_pfs : float, default 0.8
            Minimum Property Fidelity Score threshold.
        sim_threshold : float, default 0.50
            Soft alignment cosine threshold.
        persist : bool, default True
            Whether to write report JSON & MD to reports_dir.

        Returns
        -------
        EvaluationReportDetail
            Synthesized evaluation report.
        """
        # 1. Resolve gold benchmark path and competency queries
        target_gold = gold_standard_path
        target_queries = queries_path

        if not target_gold and benchmark_id:
            for bm in self.discover_benchmarks():
                if bm.id == benchmark_id:
                    target_gold = bm.gold_standard_path
                    target_queries = target_queries or bm.queries_path
                    break

        if not target_gold:
            # Fallback to default STNB pilot
            target_gold = str(self.eval_data_dir / "stnb_cpm_pilot.jsonld")
            if not target_queries:
                q_cand = self.eval_data_dir / "stnb_cpm_queries.yaml"
                if q_cand.is_file():
                    target_queries = str(q_cand)

        target_gold_path = Path(target_gold)
        if not target_gold_path.is_file():
            raise FileNotFoundError(f"Gold standard benchmark not found at: {target_gold}")

        # 2. Extract run representation
        predicted_target = self._load_run_evaluation_target(run_id, reader)

        # 3. Instantiate sovereign EvaluationHarness
        harness = EvaluationHarness(
            schema=DEFAULT_SCHEMA,
            reports_dir=self.reports_dir,
        )

        # 4. In-memory evaluation via pluggable strategy
        report = await harness.evaluate_in_memory(
            predicted=predicted_target,
            gold=str(target_gold_path),
            run_id=run_id,
            strategy=strategy,
            dataset_ref=str(target_gold_path),
            min_mcc=min_mcc,
            min_pfs=min_pfs,
            sim_threshold=sim_threshold,
        )

        # 5. Optional Extrinsic Retrieval Scoring
        retrieval_detail: RetrievalEvaluationDetail | None = None
        if target_queries and Path(target_queries).is_file():
            try:
                with open(target_queries, "r", encoding="utf-8") as qf:
                    q_data = yaml.safe_load(qf) or {}
                queries = q_data.get("queries", [])
                if queries:
                    in_mem_store = InMemoryGraphStore()
                    in_mem_store.index_for_search(predicted_target, run_id=run_id)
                    retrieval_eval = ExtrinsicRetrievalEvaluator(graph_reader=in_mem_store)
                    ret_metrics = await retrieval_eval.evaluate_batch(queries, top_k=10, run_id=run_id)

                    retrieval_detail = RetrievalEvaluationDetail(
                        mrr=ret_metrics.get("MRR", 0.0),
                        hits_at_1=ret_metrics.get("Hits@1", 0.0),
                        hits_at_3=ret_metrics.get("Hits@3", 0.0),
                        hits_at_10=ret_metrics.get("Hits@10", 0.0),
                        ndcg=ret_metrics.get("nDCG", 0.0),
                        num_queries=len(queries),
                    )
            except Exception as e:
                logger.warning("Downstream retrieval evaluation skipped: %s", e)

        # 6. Optional Comparative Baseline Evaluation
        comparative_deltas: list[ComparativeMetricDelta] = []
        baseline_summary_md = ""
        baseline_run_id = f"baseline_{baseline}_{run_id}" if baseline else ""

        if baseline and baseline.strip().lower() in ("naive_kg", "text_rag", "zero_shot"):
            b_name = baseline.strip().lower()
            try:
                pipeline_metrics: dict[str, float] = {}
                for stage_list in report.results_by_level.values():
                    for res in stage_list:
                        for m in res.metrics:
                            pipeline_metrics[m.name] = m.value

                baseline_metrics: dict[str, float] = {}
                if b_name == "naive_kg":
                    nkg = BaselineNaiveKG(schema=DEFAULT_SCHEMA)
                    nkg_results, _ = await nkg.run_and_evaluate(
                        corpus=str(target_gold_path),
                        gold=str(target_gold_path),
                        run_id=baseline_run_id,
                    )
                    for r in nkg_results:
                        for m in r.metrics:
                            baseline_metrics[m.name] = m.value
                elif b_name == "text_rag" and target_queries:
                    rag = BaselineTextRAG(graph_store=InMemoryGraphStore())
                    rag_res, _ = await rag.run_and_evaluate(
                        corpus=str(target_gold_path),
                        queries=str(target_queries),
                        run_id=baseline_run_id,
                    )
                    for m in rag_res.metrics:
                        baseline_metrics[m.name] = m.value

                comparisons = compute_run_comparisons(
                    run_id_a=baseline_run_id,
                    run_id_b=run_id,
                    metrics_a=baseline_metrics,
                    metrics_b=pipeline_metrics,
                    axis=ComparisonAxis.METHOD,
                )
                comparative_deltas = [
                    ComparativeMetricDelta(
                        metric_name=c.metric_name,
                        value_baseline=c.value_a,
                        value_pipeline=c.value_b,
                        delta=c.delta,
                        favorable=(c.winner == "b") if c.winner else None,
                        winner="Pipeline" if c.winner == "b" else ("Baseline" if c.winner == "a" else "Tie"),
                    )
                    for c in comparisons
                ]
                baseline_summary_md = "\n\n" + format_comparison_markdown(
                    comparisons,
                    title=f"Comparative Benchmark ({b_name.upper()})",
                    name_a="Baseline",
                    name_b="Pipeline",
                )
            except Exception as e:
                logger.warning("Baseline evaluation %s failed: %s", b_name, e)

        # 7. Synthesize complete detail domain model
        full_md = report.summary + baseline_summary_md
        detail = self._map_pipeline_report_to_detail(
            report,
            summary_markdown=full_md,
            retrieval_detail=retrieval_detail,
            comparative_deltas=comparative_deltas,
        )

        # 8. Persist if requested
        if persist:
            self._persist_evaluation_report(detail, full_md)

        return detail

    async def evaluate_manifest(
        self,
        manifest_path: str | Path,
        baseline: str | None = None,
        build_graph: bool = False,
    ) -> EvaluationReportDetail:
        """Execute a manifest-driven evaluation run and return domain detail.

        Parameters
        ----------
        manifest_path : str or Path
            Path to YAML manifest file.
        baseline : str, optional
            Baseline override ('naive_kg', 'text_rag', 'zero_shot').
        build_graph : bool, default False
            Whether to trigger pipeline generation prior to scoring.

        Returns
        -------
        EvaluationReportDetail
            Parsed domain report detail.
        """
        path = Path(manifest_path)
        if not path.is_file():
            raise FileNotFoundError(f"Manifest not found: {path}")

        harness = EvaluationHarness(
            schema=DEFAULT_SCHEMA,
            reports_dir=self.reports_dir,
        )

        pipeline_report = await harness.evaluate_manifest(
            manifest_path=path,
            build_graph=build_graph,
            baseline=baseline,
        )

        detail = self._map_pipeline_report_to_detail(
            pipeline_report,
            summary_markdown=pipeline_report.summary,
        )
        return detail

    def compare_runs(
        self,
        run_id_a: str,
        run_id_b: str,
        axis: str = "method",
    ) -> ComparativeEvaluationResponse:
        """Compare two runs by looking up their evaluated reports.

        Parameters
        ----------
        run_id_a : str
            First run identifier.
        run_id_b : str
            Second run identifier.
        axis : str, default 'method'
            Comparison axis.

        Returns
        -------
        ComparativeEvaluationResponse
            Pairwise deltas and formatted summary table.
        """
        rep_a = self.get_report(run_id_a)
        rep_b = self.get_report(run_id_b)

        metrics_a = rep_a.key_metrics if rep_a else {}
        metrics_b = rep_b.key_metrics if rep_b else {}

        cmp_axis = ComparisonAxis.METHOD
        if axis.lower() == "prompt":
            cmp_axis = ComparisonAxis.PROMPT
        elif axis.lower() == "model":
            cmp_axis = ComparisonAxis.MODEL

        comparisons = compute_run_comparisons(
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            axis=cmp_axis,
        )

        deltas = [
            ComparativeMetricDelta(
                metric_name=c.metric_name,
                value_baseline=c.value_a,
                value_pipeline=c.value_b,
                delta=c.delta,
                favorable=(c.winner == "b") if c.winner else None,
                winner=run_id_b if c.winner == "b" else (run_id_a if c.winner == "a" else "Tie"),
            )
            for c in comparisons
        ]

        summary_md = format_comparison_markdown(
            comparisons,
            title=f"Comparative Run Analysis ({run_id_a} vs {run_id_b})",
            name_a=run_id_a,
            name_b=run_id_b,
        )

        return ComparativeEvaluationResponse(
            comparison_id=f"comp_{run_id_a}_vs_{run_id_b}",
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            axis=axis,
            dataset_ref=rep_a.dataset_ref if rep_a else (rep_b.dataset_ref if rep_b else None),
            deltas=deltas,
            summary_markdown=summary_md,
        )

    # -------------------------------------------------------------------------
    # Internal Artifact & Model Bridge Helpers
    # -------------------------------------------------------------------------

    def _load_run_evaluation_target(self, run_id: str, reader: ArtifactReader) -> Any:
        """Extract a pipeline evaluation representation from a Studio run.

        Parameters
        ----------
        run_id : str
            Target run ID.
        reader : ArtifactReader
            Active artifact reader.

        Returns
        -------
        TheoryNet or nx.DiGraph
            Evaluation target representation.
        """
        envelopes = reader._collect_run_envelopes(run_id)

        atoms: list[TheoryAtom] = []
        relations: list[TheoryRelation] = []
        entities: list[L2Entity] = []
        triples: list[L2Triple] = []

        for data, p in envelopes:
            kind = data.get("kind", "")
            payload = data.get("payload", {})
            art_id = data.get("artifact_id", p.stem)

            if kind in ("theory_atom", "argument_component"):
                comp_id = payload.get("component_id") or payload.get("id") or art_id
                comp_type = payload.get("component_type") or "actual_model"
                text = payload.get("text") or payload.get("formalAxiom") or comp_id
                atoms.append(
                    TheoryAtom(
                        id=comp_id,
                        text=text,
                        component_type=comp_type,
                        source_chunk_id=payload.get("source_chunk_id") or "chunk_0",
                        confidence=payload.get("confidence", 1.0),
                    )
                )
            elif kind in ("theory_relation", "argument_relation"):
                rel_type = payload.get("relation_type", "specializes")
                src = payload.get("source_component_id") or payload.get("source_id")
                tgt = payload.get("target_component_id") or payload.get("target_id")
                if src and tgt:
                    relations.append(
                        TheoryRelation(
                            source_id=src,
                            target_id=tgt,
                            relation_type=rel_type,
                            confidence=payload.get("confidence", 1.0),
                            scope=payload.get("scope", "global"),
                        )
                    )
            elif kind in ("linked_entity", "entity", "mature_entity"):
                ent_id = payload.get("entity_id") or art_id
                name = payload.get("canonical_name") or payload.get("name") or ent_id
                label = payload.get("entity_type") or payload.get("label") or "Entity"
                entities.append(L2Entity(id=ent_id, name=name, label=label))
            elif kind in ("global_relation", "local_relation"):
                src = payload.get("subject_entity_id") or payload.get("source_id")
                tgt = payload.get("object_entity_id") or payload.get("target_id")
                pred = payload.get("predicate", "RELATED_TO")
                if src and tgt:
                    triples.append(
                        L2Triple(
                            subject_id=src,
                            predicate=pred,
                            object_id=tgt,
                            confidence=payload.get("confidence", 1.0),
                            scope=payload.get("scope", "global" if kind == "global_relation" else "local"),
                        )
                    )

        if atoms or relations:
            return TheoryNet(atoms=atoms, relations=relations)
        elif entities or triples:
            return l2_triples_to_digraph(entities, triples)

        # Fallback: materialize via GraphView and convert to DiGraph
        graph_view = reader.get_graph(run_id)
        g = nx.DiGraph()
        for n in graph_view.nodes:
            g.add_node(n.id, label=n.label, node_type=n.type, layer=n.layer.value)
        for e in graph_view.edges:
            g.add_edge(e.source, e.target, label=e.type, polarity=e.polarity, confidence=e.confidence)
        return g

    def _persist_evaluation_report(self, detail: EvaluationReportDetail, full_markdown: str) -> None:
        """Persist generated report JSON and Markdown into reports_dir."""
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            report_name = detail.run_ids[0] if detail.run_ids else detail.evaluation_id
            json_file = self.reports_dir / f"report_{report_name}.json"
            md_file = self.reports_dir / f"report_{report_name}.md"

            with open(json_file, "w", encoding="utf-8") as f:
                f.write(detail.model_dump_json(indent=2))

            with open(md_file, "w", encoding="utf-8") as f:
                f.write(full_markdown)
        except Exception as e:
            logger.error("Failed to persist evaluation report to %s: %s", self.reports_dir, e)

    def _map_pipeline_report_to_detail(
        self,
        report: PipelineEvaluationReport,
        summary_markdown: str = "",
        retrieval_detail: RetrievalEvaluationDetail | None = None,
        comparative_deltas: list[ComparativeMetricDelta] | None = None,
    ) -> EvaluationReportDetail:
        """Translate pipeline EvaluationReport into Studio EvaluationReportDetail."""
        results_by_lvl: dict[str, list[EvaluationLevelResult]] = {}
        key_metrics: dict[str, float] = {}

        for lvl, stage_results in report.results_by_level.items():
            lvl_results: list[EvaluationLevelResult] = []
            for r in stage_results:
                m_vals = [
                    EvaluationMetricValue(
                        name=m.name,
                        value=m.value,
                        unit=getattr(m, "unit", ""),
                        threshold=getattr(m, "threshold", None),
                        passes_threshold=getattr(m, "passes_threshold", None),
                    )
                    for m in r.metrics
                ]
                for mv in m_vals:
                    key_metrics[mv.name] = mv.value

                lvl_results.append(
                    EvaluationLevelResult(
                        run_id=r.run_id,
                        level=str(r.evaluation_level),
                        phase_name=r.phase_name,
                        dataset_ref=r.dataset_ref,
                        outcome=EvaluationOutcome(r.outcome.value if hasattr(r.outcome, "value") else str(r.outcome)),
                        metrics=m_vals,
                        notes=getattr(r, "notes", {}),
                        evaluated_at=getattr(r, "evaluated_at", datetime.now(timezone.utc)),
                    )
                )
            results_by_lvl[str(lvl)] = lvl_results

        # Synthesize overall outcome
        all_res = [res for sublist in results_by_lvl.values() for res in sublist]
        overall_outcome = (
            EvaluationOutcome.PASS
            if all(r.outcome in (EvaluationOutcome.PASS, EvaluationOutcome.WARNING) for r in all_res) and all_res
            else EvaluationOutcome.FAIL
        )

        # Parse structuralist decomposition, poset, and retrieval from summary markdown
        decomp = self._parse_model_decomposition_table(summary_markdown)
        poset = self._parse_poset_detail(summary_markdown, key_metrics)
        retrieval = retrieval_detail or self._parse_retrieval_detail(summary_markdown, key_metrics)
        polarity = self._parse_polarity_detail(key_metrics)

        deltas = comparative_deltas or []
        if not deltas and report.pairwise_comparisons:
            deltas = [
                ComparativeMetricDelta(
                    metric_name=c.metric_name,
                    value_baseline=c.value_a,
                    value_pipeline=c.value_b,
                    delta=c.delta,
                    favorable=(c.winner == "b") if c.winner else None,
                    winner=c.run_id_b if c.winner == "b" else (c.run_id_a if c.winner == "a" else "Tie"),
                )
                for c in report.pairwise_comparisons
            ]

        return EvaluationReportDetail(
            evaluation_id=report.evaluation_id,
            run_ids=report.run_ids,
            dataset_ref=report.dataset_ref,
            dataset_type=str(report.dataset_type.value if hasattr(report.dataset_type, "value") else report.dataset_type or "gold"),
            outcome=overall_outcome,
            created_at=report.created_at,
            key_metrics=key_metrics,
            has_markdown=bool(summary_markdown),
            has_baseline=bool(deltas),
            results_by_level=results_by_lvl,
            model_decomposition=decomp,
            poset_detail=poset,
            polarity_detail=polarity,
            retrieval_detail=retrieval,
            comparative_deltas=deltas,
            summary_markdown=summary_markdown,
        )

    def _map_json_to_summary(self, data: dict[str, Any], path: Path) -> EvaluationReportSummary:
        """Map raw JSON report file to lightweight EvaluationReportSummary."""
        evaluation_id = data.get("evaluation_id", path.stem.replace("report_", ""))
        run_ids = data.get("run_ids", [])
        dataset_ref = data.get("dataset_ref")
        dataset_type = str(data.get("dataset_type", "gold"))

        key_metrics: dict[str, float] = {}
        all_outcomes: list[str] = []

        res_by_lvl = data.get("results_by_level", {})
        for lvl, res_list in res_by_lvl.items():
            if isinstance(res_list, list):
                for r in res_list:
                    if isinstance(r, dict):
                        all_outcomes.append(str(r.get("outcome", "inconclusive")).lower())
                        for m in r.get("metrics", []):
                            if isinstance(m, dict) and "name" in m and "value" in m:
                                key_metrics[m["name"]] = float(m["value"])

        overall = EvaluationOutcome.INCONCLUSIVE
        if all_outcomes:
            overall = EvaluationOutcome.PASS if all(o in ("pass", "warning") for o in all_outcomes) else EvaluationOutcome.FAIL

        created_str = data.get("created_at")
        try:
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        has_baseline = "baseline" in res_by_lvl or bool(data.get("pairwise_comparisons"))
        return EvaluationReportSummary(
            evaluation_id=evaluation_id,
            run_ids=run_ids,
            dataset_ref=dataset_ref,
            dataset_type=dataset_type,
            outcome=overall,
            created_at=created_at,
            key_metrics=key_metrics,
            has_markdown=path.with_suffix(".md").is_file() or bool(data.get("summary")),
            has_baseline=has_baseline,
        )

    def _map_json_to_detail(self, data: dict[str, Any], path: Path, md_content: str = "") -> EvaluationReportDetail:
        """Map raw JSON report file to comprehensive EvaluationReportDetail."""
        summary_model = self._map_json_to_summary(data, path)
        full_md = md_content or data.get("summary", "")

        results_by_lvl: dict[str, list[EvaluationLevelResult]] = {}
        for lvl, r_list in data.get("results_by_level", {}).items():
            lvl_results: list[EvaluationLevelResult] = []
            if isinstance(r_list, list):
                for r in r_list:
                    if isinstance(r, dict):
                        m_vals = [
                            EvaluationMetricValue(
                                name=m.get("name", "unknown"),
                                value=float(m.get("value", 0.0)),
                                unit=m.get("unit", ""),
                                threshold=m.get("threshold"),
                                passes_threshold=m.get("passes_threshold"),
                            )
                            for m in r.get("metrics", [])
                            if isinstance(m, dict)
                        ]
                        lvl_results.append(
                            EvaluationLevelResult(
                                run_id=r.get("run_id", summary_model.run_ids[0] if summary_model.run_ids else "unknown"),
                                level=str(r.get("evaluation_level", lvl)),
                                phase_name=r.get("phase_name"),
                                dataset_ref=r.get("dataset_ref"),
                                outcome=EvaluationOutcome(r.get("outcome", "inconclusive").lower()),
                                metrics=m_vals,
                                notes=r.get("notes", {}),
                                evaluated_at=summary_model.created_at,
                            )
                        )
            results_by_lvl[str(lvl)] = lvl_results

        decomp = self._parse_model_decomposition_table(full_md)
        poset = self._parse_poset_detail(full_md, summary_model.key_metrics)
        retrieval = self._parse_retrieval_detail(full_md, summary_model.key_metrics)
        polarity = self._parse_polarity_detail(summary_model.key_metrics)

        comparative_deltas: list[ComparativeMetricDelta] = []
        for c in data.get("pairwise_comparisons", []):
            if isinstance(c, dict):
                comparative_deltas.append(
                    ComparativeMetricDelta(
                        metric_name=c.get("metric_name", "unknown"),
                        value_baseline=float(c.get("value_a", 0.0)),
                        value_pipeline=float(c.get("value_b", 0.0)),
                        delta=float(c.get("delta", 0.0)),
                        favorable=c.get("favorable"),
                        winner=c.get("winner", "Tie"),
                    )
                )

        return EvaluationReportDetail(
            **summary_model.model_dump(),
            results_by_level=results_by_lvl,
            model_decomposition=decomp,
            poset_detail=poset,
            polarity_detail=polarity,
            retrieval_detail=retrieval,
            comparative_deltas=comparative_deltas,
            summary_markdown=full_md,
        )

    # -------------------------------------------------------------------------
    # Markdown Detail Parsers
    # -------------------------------------------------------------------------

    def _parse_model_decomposition_table(self, markdown: str) -> list[ModelDecompositionEntry]:
        """Extract Model Class Decomposition Breakdown table from report markdown."""
        entries: list[ModelDecompositionEntry] = []
        if not markdown:
            return entries

        lines = markdown.splitlines()
        in_table = False
        for line in lines:
            if "Model Class Decomposition Breakdown" in line:
                in_table = True
                continue
            if in_table:
                if line.startswith("#"):
                    break
                if line.startswith("| `") and "|" in line:
                    parts = [p.strip() for p in line.strip("|").split("|")]
                    if len(parts) >= 6:
                        try:
                            c_name = parts[0].strip("`")
                            symbol = parts[1].strip("$")
                            ref_c = int(parts[2])
                            pred_c = int(parts[3])
                            match_c = int(parts[4])
                            comp_str = parts[5].replace("%", "").strip()
                            comp = float(comp_str) / 100.0 if comp_str else 0.0

                            entries.append(
                                ModelDecompositionEntry(
                                    class_name=c_name,
                                    symbol=symbol,
                                    reference_count=ref_c,
                                    predicted_count=pred_c,
                                    matched_count=match_c,
                                    completeness=comp,
                                )
                            )
                        except (ValueError, IndexError):
                            pass
        return entries

    def _parse_poset_detail(self, markdown: str, metrics: dict[str, float]) -> PosetEvaluationDetail | None:
        """Extract poset hierarchy metrics from report markdown and metrics map."""
        if "poset_f1" not in metrics and "is_dag" not in metrics and "Specialization Poset" not in markdown:
            return None

        is_dag = bool(metrics.get("is_dag", 1.0 > 0))
        root_conf = bool(metrics.get("root_conformity", 0.0 > 0))
        tr_f1 = metrics.get("poset_f1", 0.0)
        reach_f1 = metrics.get("poset_reachability_f1", 0.0)

        # Regex search for root element
        m_root = re.search(r"Root:\s*`([^`]+)`", markdown)
        root_elem = m_root.group(1) if m_root else None

        # Regex search for edge counts
        m_edges = re.search(r"Predicted\s*=\s*(\d+),\s*Reference\s*=\s*(\d+)", markdown)
        pred_edges = int(m_edges.group(1)) if m_edges else 0
        ref_edges = int(m_edges.group(2)) if m_edges else 0

        return PosetEvaluationDetail(
            is_dag=is_dag,
            root_element=root_elem,
            root_conformity=root_conf,
            transitive_reduction_f1=tr_f1,
            reachability_f1=reach_f1,
            predicted_edge_count=pred_edges,
            reference_edge_count=ref_edges,
        )

    def _parse_polarity_detail(self, metrics: dict[str, float]) -> PolarityConcordanceDetail | None:
        """Extract polarity accuracy and conflict rate from metrics map."""
        if "polarity_accuracy" not in metrics and "polarity_conflict_rate" not in metrics:
            return None

        return PolarityConcordanceDetail(
            polarity_accuracy=metrics.get("polarity_accuracy", 1.0),
            polarity_conflict_rate=metrics.get("polarity_conflict_rate", 0.0),
        )

    def _parse_retrieval_detail(self, markdown: str, metrics: dict[str, float]) -> RetrievalEvaluationDetail | None:
        """Extract Information Retrieval ranking metrics."""
        if "mrr" not in metrics and "Hits@1" not in markdown and "MRR" not in markdown:
            return None

        mrr = metrics.get("mrr", 0.0)
        h1 = metrics.get("hits@1", 0.0)
        h3 = metrics.get("hits@3", 0.0)
        h10 = metrics.get("hits@10", 0.0)
        ndcg = metrics.get("ndcg", 0.0)

        # Fallback to regex on markdown
        if mrr == 0.0:
            m_mrr = re.search(r"- \*\*MRR:\*\*\s*([\d\.]+)", markdown)
            if m_mrr:
                mrr = float(m_mrr.group(1))
        if h1 == 0.0:
            m_h1 = re.search(r"- \*\*Hits@1:\*\*\s*([\d\.]+)", markdown)
            if m_h1:
                h1 = float(m_h1.group(1))

        return RetrievalEvaluationDetail(
            mrr=mrr,
            hits_at_1=h1,
            hits_at_3=h3,
            hits_at_10=h10,
            ndcg=ndcg,
        )
