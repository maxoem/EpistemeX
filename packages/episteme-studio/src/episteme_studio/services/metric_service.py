"""Metric service coordinating metric descriptors, execution lifecycles, and QBAF/GDS execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from episteme_studio.adapters.metrics_adapter import (
    compute_degree,
    compute_leiden,
    compute_local_gradual_strength,
    compute_tenability,
    run_epistemetrics_betweenness,
    run_epistemetrics_eigenvector,
    run_epistemetrics_louvain,
    run_epistemetrics_pagerank,
    run_epistemetrics_wcc,
)
from episteme_studio.adapters.neo4j_reader import Neo4jReader
from episteme_studio.domain.errors import ProblemDetail
from episteme_studio.domain.graph import GraphView
from episteme_studio.domain.metrics import (
    AffectedNodeDetail,
    MetricDescriptor,
    MetricResult,
    MetricScope,
)

logger = logging.getLogger(__name__)


class ExecutionStatus(StrEnum):
    """Lifecycle status of an async metric execution job.

    Attributes
    ----------
    QUEUED : str
        Execution registered and waiting to start.
    RUNNING : str
        Execution currently in progress.
    COMPLETED : str
        Execution finished successfully with a MetricResult.
    FAILED : str
        Execution failed with an error.
    CANCELLED : str
        Execution cancelled cooperatively.
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionJob:
    """Internal tracker for an asynchronous metric computation job.

    Parameters
    ----------
    execution_id : str
        Unique identifier for the job.
    metric_id : str
        Target metric identifier.
    status : ExecutionStatus
        Current lifecycle state.
    progress : float or None, optional
        Progress fractional indicator between 0.0 and 1.0.
    result : MetricResult or None, optional
        Computation result if completed.
    error : ProblemDetail or None, optional
        Error details if failed.
    cancel_event : asyncio.Event or None, optional
        Cooperative cancellation event.
    """

    def __init__(
        self,
        execution_id: str,
        metric_id: str,
        status: ExecutionStatus = ExecutionStatus.QUEUED,
        progress: float | None = None,
        result: MetricResult | None = None,
        error: ProblemDetail | None = None,
    ) -> None:
        self.execution_id = execution_id
        self.metric_id = metric_id
        self.status = status
        self.progress = progress
        self.result = result
        self.error = error
        self.cancel_event = asyncio.Event()
        self.created_at = datetime.now(UTC)
        self.task: asyncio.Task[MetricResult] | None = None


class MetricService:
    """Service managing registered graph metrics, GDS capability probing, and async jobs.

    Parameters
    ----------
    neo4j_reader : Neo4jReader or None, optional
        Configured Neo4j reader instance.
    """

    def __init__(self, neo4j_reader: Neo4jReader | None = None) -> None:
        self._neo4j_reader = neo4j_reader
        self._executions: dict[str, ExecutionJob] = {}
        self._gds_cached_status: bool | None = None

    def set_neo4j_reader(self, reader: Neo4jReader | None) -> None:
        """Update active Neo4j reader instance and invalidate cached GDS status.

        Parameters
        ----------
        reader : Neo4jReader or None
            New Neo4j reader or None if disconnected.
        """
        self._neo4j_reader = reader
        self._gds_cached_status = None

    async def probe_gds_available(self) -> bool:
        """Check whether Neo4j GDS is currently available on the active driver.

        Returns
        -------
        bool
            True if GDS is installed and functional; False otherwise.
        """
        if self._neo4j_reader is None:
            return False
        try:
            available = await self._neo4j_reader.check_gds_availability(timeout=1.5)
            self._gds_cached_status = available
            return available
        except Exception:
            self._gds_cached_status = False
            return False

    async def list_descriptors(self) -> list[MetricDescriptor]:
        """List all registered metric descriptors with live availability flags and schemas.

        Returns
        -------
        list of MetricDescriptor
            Available and registered metric specifications.
        """
        has_gds = await self.probe_gds_available()

        descriptors = [
            MetricDescriptor(
                id="gradual_strength_local",
                label="Local Gradual Strength (QBAF)",
                description=(
                    "Evaluates iterative gradual semantics acceptability (rho) backwards from a focus "
                    "argument node, explaining upstream support and attack paths with marginal contributions."
                ),
                scope=MetricScope.SINGLE_NODE,
                available=True,
                engine="cypher",
                param_schema={
                    "type": "object",
                    "properties": {
                        "max_depth": {
                            "type": "integer",
                            "title": "Max Depth",
                            "description": "Maximum incoming hops to traverse upstream from focus node",
                            "default": 2,
                            "minimum": 1,
                            "maximum": 5,
                        },
                        "tolerance": {
                            "type": "number",
                            "title": "Convergence Tolerance",
                            "description": "Convergence delta threshold for gradual semantics iteration",
                            "default": 0.0001,
                            "minimum": 0.00001,
                            "maximum": 0.1,
                        },
                        "iterations": {
                            "type": "integer",
                            "title": "Max Iterations",
                            "description": "Maximum iteration cap preventing infinite loops on cyclic argument graphs",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                        },
                    },
                },
            ),
            MetricDescriptor(
                id="pagerank_global",
                label="Global PageRank Centrality",
                description=(
                    "Executes global PageRank centrality via Neo4j Graph Data Science (GDS) ephemeral projection, "
                    "with seamless fallback to Python igraph when GDS is unavailable."
                ),
                scope=MetricScope.GLOBAL,
                available=has_gds,
                unavailable_reason=None if has_gds else "Neo4j GDS plugin is not installed in the active Neo4j instance.",
                engine="gds",
                param_schema={
                    "type": "object",
                    "properties": {
                        "damping": {
                            "type": "number",
                            "title": "Damping Factor",
                            "description": "Damping factor for random walk transitions",
                            "default": 0.85,
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "max_iterations": {
                            "type": "integer",
                            "title": "Max Iterations",
                            "description": "Maximum number of power iterations",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "tolerance": {
                            "type": "number",
                            "title": "Tolerance",
                            "description": "Iteration convergence delta threshold",
                            "default": 0.0001,
                            "minimum": 0.00001,
                            "maximum": 0.1,
                        },
                    },
                },
            ),
            MetricDescriptor(
                id="degree_global",
                label="Global Degree Centrality",
                description="Calculates node connection degree across the graph snapshot.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="python",
                param_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MetricDescriptor(
                id="component_global",
                label="Weakly Connected Components",
                description="Identifies weakly connected components across the graph projection using epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
                param_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MetricDescriptor(
                id="betweenness_global",
                label="Global Betweenness Centrality",
                description="Calculates shortest-path broker centrality across nodes using epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
                param_schema={
                    "type": "object",
                    "properties": {
                        "normalized": {
                            "type": "boolean",
                            "title": "Normalized",
                            "description": "Normalize betweenness centrality scores",
                            "default": True,
                        }
                    },
                },
            ),
            MetricDescriptor(
                id="eigenvector_global",
                label="Global Eigenvector Centrality",
                description="Calculates eigenvector influence centrality across nodes using epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
                param_schema={
                    "type": "object",
                    "properties": {
                        "max_iterations": {
                            "type": "integer",
                            "title": "Max Iterations",
                            "default": 100,
                        },
                        "tolerance": {
                            "type": "number",
                            "title": "Tolerance",
                            "default": 0.0001,
                        },
                    },
                },
            ),
            MetricDescriptor(
                id="louvain_global",
                label="Global Louvain Community Detection",
                description="Partitions the graph into modular communities using Louvain via epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
                param_schema={
                    "type": "object",
                    "properties": {
                        "resolution": {
                            "type": "number",
                            "title": "Resolution",
                            "default": 1.0,
                        },
                    },
                },
            ),
            MetricDescriptor(
                id="leiden_global",
                label="Global Leiden Community Detection",
                description=(
                    "Partitions the graph into densely connected modular communities using the Leiden algorithm "
                    "via Neo4j GDS, with seamless igraph fallback."
                ),
                scope=MetricScope.GLOBAL,
                available=has_gds,
                unavailable_reason=None if has_gds else "Neo4j GDS plugin is not installed in the active Neo4j instance.",
                engine="gds",
                param_schema={
                    "type": "object",
                    "properties": {
                        "gamma": {
                            "type": "number",
                            "title": "Resolution (Gamma)",
                            "description": "Resolution parameter controlling community granularity",
                            "default": 1.0,
                            "minimum": 0.01,
                            "maximum": 10.0,
                        },
                        "theta": {
                            "type": "number",
                            "title": "Randomness (Theta)",
                            "description": "Randomness parameter for the refinement phase",
                            "default": 0.01,
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "tolerance": {
                            "type": "number",
                            "title": "Tolerance",
                            "description": "Convergence threshold delta",
                            "default": 0.0001,
                            "minimum": 0.00001,
                            "maximum": 0.1,
                        },
                        "max_levels": {
                            "type": "integer",
                            "title": "Max Levels",
                            "description": "Maximum number of hierarchical clustering levels",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                        },
                    },
                },
            ),
            MetricDescriptor(
                id="tenability_evaluation",
                label="Theoretical Tenability Evaluation",
                description=(
                    "Evaluates formal structuralist metatheory tenability (Stegmüller 1976, Balzer 1987). "
                    "Measures empirical base adherence, latent parameter blur delta, and intertheoretical consistency."
                ),
                scope=MetricScope.GLOBAL,
                available=True,
                engine="python",
                param_schema={
                    "type": "object",
                    "properties": {
                        "theory_id": {
                            "type": "string",
                            "title": "Target Theory",
                            "description": "Specific claimant theory ID (e.g. neurology, psychoanalysis) or empty for all",
                            "default": "",
                        },
                        "tenability_threshold": {
                            "type": "number",
                            "title": "Anomaly Cutoff",
                            "description": "Minimum acceptable score before flagging epistemic anomaly",
                            "default": 0.5,
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                },
            ),
        ]
        return descriptors

    def get_descriptor(self, metric_id: str) -> MetricDescriptor | None:
        """Retrieve descriptor metadata for a specific metric ID synchronously.

        Parameters
        ----------
        metric_id : str
            Identifier of target metric.

        Returns
        -------
        MetricDescriptor or None
            Descriptor if found.
        """
        for d in [
            MetricDescriptor(
                id="gradual_strength_local",
                label="Local Gradual Strength (QBAF)",
                description="Iterative QBAF gradual strength with causal path explanations.",
                scope=MetricScope.SINGLE_NODE,
                available=True,
                engine="cypher",
            ),
            MetricDescriptor(
                id="pagerank_global",
                label="Global PageRank Centrality",
                description="Global PageRank via GDS or igraph fallback.",
                scope=MetricScope.GLOBAL,
                available=bool(self._gds_cached_status),
                engine="gds",
            ),
            MetricDescriptor(
                id="degree_global",
                label="Global Degree Centrality",
                description="Node connection degree.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="python",
            ),
            MetricDescriptor(
                id="component_global",
                label="Weakly Connected Components",
                description="Weakly connected components via epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
            ),
            MetricDescriptor(
                id="betweenness_global",
                label="Global Betweenness Centrality",
                description="Shortest-path broker centrality across nodes via epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
            ),
            MetricDescriptor(
                id="eigenvector_global",
                label="Global Eigenvector Centrality",
                description="Eigenvector influence centrality across nodes via epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
            ),
            MetricDescriptor(
                id="louvain_global",
                label="Global Louvain Community Detection",
                description="Modular community detection via epistemetrics.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="epistemetrics",
            ),
            MetricDescriptor(
                id="leiden_global",
                label="Global Leiden Community Detection",
                description="Global Leiden community detection via GDS or igraph fallback.",
                scope=MetricScope.GLOBAL,
                available=bool(self._gds_cached_status),
                engine="gds",
            ),
            MetricDescriptor(
                id="tenability_evaluation",
                label="Theoretical Tenability Evaluation",
                description="Structuralist metatheory tenability and blur delta evaluation.",
                scope=MetricScope.GLOBAL,
                available=True,
                engine="python",
            ),
        ]:
            if d.id == metric_id:
                return d
        return None

    async def execute_metric(
        self,
        metric_id: str,
        graph_view: GraphView,
        focus_node_id: str | None = None,
        params: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> MetricResult:
        """Run the computation synchronously or in-process.

        Parameters
        ----------
        metric_id : str
            Identifier of target metric.
        graph_view : GraphView
            Graph snapshot to execute over.
        focus_node_id : str or None, optional
            Focus node identifier if single-node scope.
        params : dict of str to Any, optional
            Algorithmic parameters.
        execution_id : str or None, optional
            Optional execution identifier.

        Returns
        -------
        MetricResult
            Calculated metric result.
        """
        opts = params or {}
        exec_id = execution_id or f"exec-{uuid4().hex[:8]}"
        start = datetime.now(UTC)

        if opts.get("_mock_delay"):
            await asyncio.sleep(float(opts["_mock_delay"]))

        if metric_id == "gradual_strength_local":
            if not focus_node_id:
                raise ValueError("focus_node_id is required for gradual_strength_local")
            return compute_local_gradual_strength(
                graph=graph_view,
                focus_node_id=focus_node_id,
                params=opts,
                execution_id=exec_id,
            )

        elif metric_id == "pagerank_global":
            damping = float(opts.get("damping", 0.85))
            max_iterations = int(opts.get("max_iterations", 20))
            tolerance = float(opts.get("tolerance", 1e-4))
            warnings: list[str] = []

            # Try GDS if neo4j_reader is present and GDS available
            gds_available = await self.probe_gds_available()
            if self._neo4j_reader is not None and gds_available:
                try:
                    scores, summary = await self._neo4j_reader.run_gds_pagerank(
                        damping=damping,
                        max_iterations=max_iterations,
                        tolerance=tolerance,
                    )
                    end = datetime.now(UTC)
                    affected_nodes = {
                        nid: AffectedNodeDetail(
                            roles=["centrality"],
                            net_contribution=round(score, 6),
                            metadata={"pagerank": round(score, 6)},
                        )
                        for nid, score in scores.items()
                    }
                    return MetricResult(
                        execution_id=exec_id,
                        metric_id=metric_id,
                        scope=MetricScope.GLOBAL,
                        result_value=summary.get("mean_score", 0.0),
                        graph_revision=graph_view.graph_version,
                        duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                        summary=summary,
                        affected_nodes=affected_nodes,
                        affected_edges=[],
                        warnings=warnings,
                        computed_at=end,
                    )
                except Exception as exc:
                    logger.warning("GDS PageRank execution failed, falling back to igraph: %s", exc)
                    warnings.append("Executed via in-memory igraph fallback (GDS execution error)")

            # Fallback to epistemetrics
            if not any("Executed via in-memory epistemetrics fallback" in w for w in warnings):
                warnings.append("Executed via in-memory epistemetrics fallback (Neo4j GDS not detected)")

            pr_res = run_epistemetrics_pagerank(
                graph_view,
                params={"damping": damping, "max_iterations": max_iterations, "tolerance": tolerance, **opts},
            )
            end = datetime.now(UTC)
            scores = pr_res.scores
            vals = list(scores.values()) if scores else [0.0]
            summary = {
                "min_score": round(pr_res.min_score, 6),
                "max_score": round(pr_res.max_score, 6),
                "mean_score": round(pr_res.mean_score, 6),
                "iteration_count": max_iterations,
                "node_count": len(scores),
                "engine": "epistemetrics",
                "backend": pr_res.backend,
            }
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["centrality"],
                    net_contribution=round(score, 6),
                    metadata={"pagerank": round(score, 6)},
                )
                for nid, score in scores.items()
            }
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=summary.get("mean_score", 0.0),
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary=summary,
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=warnings,
                computed_at=end,
            )

        elif metric_id == "degree_global":
            overlay = compute_degree(graph_view, params=opts)
            end = datetime.now(UTC)
            scores = {
                nid: float(val) for nid, val in overlay.node_values.items() if val is not None
            }
            vals = list(scores.values()) if scores else [0.0]
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["degree"],
                    net_contribution=score,
                    metadata={"degree": score},
                )
                for nid, score in scores.items()
            }
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=round(sum(vals) / len(vals), 2) if vals else 0.0,
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary={
                    "min_degree": min(vals),
                    "max_degree": max(vals),
                    "mean_degree": round(sum(vals) / len(vals), 2) if vals else 0.0,
                    "node_count": len(scores),
                },
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=[],
                computed_at=end,
            )

        elif metric_id == "component_global":
            wcc_res = run_epistemetrics_wcc(graph_view, params=opts)
            end = datetime.now(UTC)
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["component"],
                    net_contribution=None,
                    metadata={"component": f"c_{part}"},
                )
                for nid, part in wcc_res.node_to_partition.items()
            }
            for n in graph_view.nodes:
                if n.id not in affected_nodes:
                    affected_nodes[n.id] = AffectedNodeDetail(
                        roles=["component"],
                        net_contribution=None,
                        metadata={"component": "c_0"},
                    )
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=wcc_res.num_partitions,
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary={
                    "component_count": wcc_res.num_partitions,
                    "node_count": len(affected_nodes),
                    "engine": "epistemetrics",
                    "backend": wcc_res.backend,
                },
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=[],
                computed_at=end,
            )

        elif metric_id in ("betweenness_global", "betweenness"):
            bet_res = run_epistemetrics_betweenness(graph_view, params=opts)
            end = datetime.now(UTC)
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["centrality", "betweenness"],
                    net_contribution=round(score, 6),
                    metadata={"betweenness": round(score, 6)},
                )
                for nid, score in bet_res.scores.items()
            }
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=round(bet_res.mean_score, 6),
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary={
                    "min_score": round(bet_res.min_score, 6),
                    "max_score": round(bet_res.max_score, 6),
                    "mean_score": round(bet_res.mean_score, 6),
                    "node_count": len(bet_res.scores),
                    "engine": "epistemetrics",
                    "backend": bet_res.backend,
                },
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=[],
                computed_at=end,
            )

        elif metric_id in ("eigenvector_global", "eigenvector"):
            eig_res = run_epistemetrics_eigenvector(graph_view, params=opts)
            end = datetime.now(UTC)
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["centrality", "eigenvector"],
                    net_contribution=round(score, 6),
                    metadata={"eigenvector": round(score, 6)},
                )
                for nid, score in eig_res.scores.items()
            }
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=round(eig_res.mean_score, 6),
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary={
                    "min_score": round(eig_res.min_score, 6),
                    "max_score": round(eig_res.max_score, 6),
                    "mean_score": round(eig_res.mean_score, 6),
                    "node_count": len(eig_res.scores),
                    "engine": "epistemetrics",
                    "backend": eig_res.backend,
                },
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=[],
                computed_at=end,
            )

        elif metric_id in ("louvain_global", "louvain"):
            louv_res = run_epistemetrics_louvain(graph_view, params=opts)
            end = datetime.now(UTC)
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["cluster"],
                    net_contribution=None,
                    metadata={
                        "community": str(comm_id),
                        "cluster": str(comm_id),
                    },
                )
                for nid, comm_id in louv_res.node_to_partition.items()
            }
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=louv_res.num_partitions,
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary={
                    "community_count": louv_res.num_partitions,
                    "node_count": len(affected_nodes),
                    "engine": "epistemetrics",
                    "backend": louv_res.backend,
                },
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=[],
                computed_at=end,
            )

        elif metric_id in ("leiden_global", "leiden"):
            gamma = float(opts.get("gamma", opts.get("resolution", 1.0)))
            theta = float(opts.get("theta", 0.01))
            tolerance = float(opts.get("tolerance", 1e-4))
            max_levels = int(opts.get("max_levels", opts.get("n_iterations", 10)))
            warnings = []

            # Try GDS if neo4j_reader is present and GDS available
            gds_available = await self.probe_gds_available()
            if self._neo4j_reader is not None and gds_available:
                try:
                    communities, summary = await self._neo4j_reader.run_gds_leiden(
                        gamma=gamma,
                        theta=theta,
                        tolerance=tolerance,
                        max_levels=max_levels,
                    )
                    end = datetime.now(UTC)
                    affected_nodes = {
                        nid: AffectedNodeDetail(
                            roles=["cluster"],
                            net_contribution=None,
                            metadata={
                                "community": str(comm_id),
                                "cluster": str(comm_id),
                            },
                        )
                        for nid, comm_id in communities.items()
                    }
                    return MetricResult(
                        execution_id=exec_id,
                        metric_id=metric_id,
                        scope=MetricScope.GLOBAL,
                        result_value=summary.get("community_count", len(set(communities.values()))),
                        graph_revision=graph_view.graph_version,
                        duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                        summary=summary,
                        affected_nodes=affected_nodes,
                        affected_edges=[],
                        warnings=warnings,
                        computed_at=end,
                    )
                except Exception as exc:
                    logger.warning("GDS Leiden execution failed, falling back to igraph: %s", exc)
                    warnings.append("Executed via in-memory igraph fallback (GDS execution error)")

            # Fallback to igraph
            if not any("Executed via in-memory igraph fallback" in w for w in warnings):
                warnings.append("Executed via in-memory igraph fallback (Neo4j GDS not detected)")

            overlay = compute_leiden(graph_view, params={"gamma": gamma, "max_levels": max_levels, **opts})
            end = datetime.now(UTC)
            communities = {
                nid: str(val) for nid, val in overlay.node_values.items() if val is not None
            }
            unique_comms = sorted(list(set(communities.values())))
            summary = {
                "community_count": len(unique_comms),
                "node_count": len(communities),
                "gamma": gamma,
                "max_levels": max_levels,
                "engine": "igraph",
            }
            affected_nodes = {
                nid: AffectedNodeDetail(
                    roles=["cluster"],
                    net_contribution=None,
                    metadata={
                        "community": comm_id,
                        "cluster": comm_id,
                    },
                )
                for nid, comm_id in communities.items()
            }
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=len(unique_comms),
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary=summary,
                affected_nodes=affected_nodes,
                affected_edges=[],
                warnings=warnings,
                computed_at=end,
            )

        elif metric_id in ("tenability_evaluation", "tenability"):
            theory_id = str(opts.get("theory_id", "")).strip() or None
            threshold = float(opts.get("tenability_threshold", 0.5))
            overlay = compute_tenability(
                graph_view,
                params={"theory_id": theory_id, "tenability_threshold": threshold},
            )
            end = datetime.now(UTC)
            scores = {
                nid: float(val) for nid, val in overlay.node_values.items() if val is not None
            }
            vals = list(scores.values()) if scores else [1.0]
            mean_val = round(sum(vals) / len(vals), 4) if vals else 1.0

            affected_nodes: dict[str, AffectedNodeDetail] = {}
            for nid, score in scores.items():
                node_obj = next((n for n in graph_view.nodes if n.id == nid), None)
                tenab = (
                    node_obj.tenability
                    or (node_obj.props.get("tenability") if node_obj else None)
                ) or {}
                is_anom = score < threshold
                affected_nodes[nid] = AffectedNodeDetail(
                    roles=["anomaly" if is_anom else "tenable"],
                    net_contribution=round(score, 4),
                    metadata={
                        "tenability": round(score, 4),
                        "theory_id": tenab.get("theory_id") or "global",
                        "tightest_blur": tenab.get("tightest_blur"),
                        "anomalies": tenab.get("anomalies", []),
                    },
                )

            affected_edges: list[AffectedEdgeDetail] = []
            for eid, escore in overlay.edge_values.items():
                edge_obj = next((e for e in graph_view.edges if e.id == eid), None)
                if edge_obj:
                    e_val = float(escore) if escore is not None else 1.0
                    affected_edges.append(
                        AffectedEdgeDetail(
                            source_node_id=edge_obj.source,
                            target_node_id=edge_obj.target,
                            relationship_id=edge_obj.id,
                            role="anomaly" if e_val < threshold else "consistent",
                            weight=round(e_val, 4),
                            polarity=edge_obj.polarity or 0,
                            hop_distance=1,
                            contribution=round(e_val, 4),
                            metadata={"tenability": round(e_val, 4), "type": edge_obj.type},
                        )
                    )

            anomalies_count = sum(1 for s in scores.values() if s < threshold)
            return MetricResult(
                execution_id=exec_id,
                metric_id=metric_id,
                scope=MetricScope.GLOBAL,
                result_value=mean_val,
                graph_revision=graph_view.graph_version,
                duration_ms=max(1, int((end - start).total_seconds() * 1000)),
                summary={
                    "mean_tenability": mean_val,
                    "evaluated_nodes": len(scores),
                    "anomalies_count": anomalies_count,
                    "is_tenable": anomalies_count == 0,
                    "theory_id": theory_id or "all",
                },
                affected_nodes=affected_nodes,
                affected_edges=affected_edges,
                warnings=[],
                computed_at=end,
            )

        else:
            raise ValueError(f"Unknown metric '{metric_id}'")

    async def submit_execution(
        self,
        metric_id: str,
        graph_view: GraphView,
        focus_node_id: str | None = None,
        params: dict[str, Any] | None = None,
        fast_path_timeout: float = 0.250,
    ) -> tuple[ExecutionJob, bool]:
        """Submit a metric calculation job with sub-250ms fast-path evaluation.

        Parameters
        ----------
        metric_id : str
            Target metric identifier.
        graph_view : GraphView
            Graph snapshot.
        focus_node_id : str or None, optional
            Target focus node.
        params : dict of str to Any, optional
            Calculation parameters.
        fast_path_timeout : float, default 0.250
            Fast-path synchronous timeout window in seconds.

        Returns
        -------
        tuple of (ExecutionJob, bool)
            The job instance, and a boolean indicating if it completed via fast-path.
        """
        execution_id = f"exec-{uuid4().hex[:8]}"
        job = ExecutionJob(execution_id=execution_id, metric_id=metric_id)
        self._executions[execution_id] = job

        async def _run_task() -> MetricResult:
            job.status = ExecutionStatus.RUNNING
            job.progress = 0.1
            try:
                res = await self.execute_metric(
                    metric_id=metric_id,
                    graph_view=graph_view,
                    focus_node_id=focus_node_id,
                    params=params,
                    execution_id=execution_id,
                )
                if job.cancel_event.is_set():
                    job.status = ExecutionStatus.CANCELLED
                    return res
                job.result = res
                job.status = ExecutionStatus.COMPLETED
                job.progress = 1.0
                return res
            except asyncio.CancelledError:
                job.status = ExecutionStatus.CANCELLED
                raise
            except Exception as exc:
                job.status = ExecutionStatus.FAILED
                job.error = ProblemDetail(
                    type="metric-execution-failed",
                    title="Metric Execution Failed",
                    status=500,
                    detail=str(exc),
                )
                raise

        # Fast-path attempt
        try:
            async with asyncio.timeout(fast_path_timeout):
                result = await _run_task()
                return job, True
        except TimeoutError:
            # Did not finish in fast-path window; convert to background execution
            background_task = asyncio.create_task(_run_task())
            job.task = background_task
            job.status = ExecutionStatus.RUNNING
            return job, False

    def get_execution(self, execution_id: str) -> ExecutionJob | None:
        """Retrieve tracking record for an execution job.

        Parameters
        ----------
        execution_id : str
            Target execution ID.

        Returns
        -------
        ExecutionJob or None
            Job instance if tracked.
        """
        return self._executions.get(execution_id)

    def cancel_execution(self, execution_id: str) -> bool:
        """Signal cooperative cancellation to an in-flight execution job.

        Parameters
        ----------
        execution_id : str
            Target execution ID.

        Returns
        -------
        bool
            True if cancellation was signaled, False if job not found.
        """
        job = self._executions.get(execution_id)
        if not job:
            return False
        job.cancel_event.set()
        job.status = ExecutionStatus.CANCELLED
        if job.task and not job.task.done():
            job.task.cancel()
        return True
