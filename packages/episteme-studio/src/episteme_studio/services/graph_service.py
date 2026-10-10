"""Service layer for graph projections, seed expansions, evidence queries, and Cypher execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.adapters.neo4j_reader import Neo4jReader
from episteme_studio.api.errors import StudioProblemException
from episteme_studio.domain.errors import Neo4jUnavailableError
from episteme_studio.domain.graph import CypherResult, GraphView
from episteme_studio.domain.runs import EvidenceTrail

if TYPE_CHECKING:
    from episteme_studio.settings import StudioSettings


class GraphService:
    """Orchestrates graph view queries, artifact provenance, and Neo4j Cypher execution.

    Parameters
    ----------
    reader : ArtifactReader or None, optional
        Underlying filesystem artifact reader.
    default_budget : int, default 500
        Default maximum node budget for materialization.
    neo4j_reader : Neo4jReader or None, optional
        Active Neo4j adapter instance.
    query_timeout_seconds : float, default 30.0
        Default query execution timeout limit.
    """

    def __init__(
        self,
        reader: ArtifactReader | None = None,
        default_budget: int = 500,
        neo4j_reader: Neo4jReader | None = None,
        query_timeout_seconds: float = 30.0,
    ) -> None:
        self.reader = reader
        self.default_budget = default_budget
        self.neo4j_reader = neo4j_reader
        self.query_timeout_seconds = query_timeout_seconds

    @classmethod
    def from_settings(
        cls,
        settings: StudioSettings,
        neo4j_reader: Neo4jReader | None = None,
    ) -> GraphService:
        """Instantiate GraphService from application settings.

        Parameters
        ----------
        settings : StudioSettings
            Application settings.
        neo4j_reader : Neo4jReader or None, optional
            Active Neo4j reader instance.

        Returns
        -------
        GraphService
            Configured service instance.
        """
        reader = ArtifactReader(
            runs_dir=settings.runs_dir,
            artifacts_dir=settings.artifacts_dir,
            extra_runs_dirs=settings.extra_runs_dirs,
            extra_artifacts_dirs=settings.extra_artifacts_dirs,
        )
        return cls(
            reader=reader,
            default_budget=settings.node_budget,
            neo4j_reader=neo4j_reader,
            query_timeout_seconds=settings.query_timeout_seconds,
        )

    def require_reader(self) -> ArtifactReader:
        """Ensure filesystem ArtifactReader is configured.

        Returns
        -------
        ArtifactReader
            Active artifact reader.

        Raises
        ------
        StudioProblemException
            If reader is not configured.
        """
        if self.reader is None:
            raise StudioProblemException(
                type="artifact-store-unavailable",
                title="Artifact Store Unavailable",
                status=503,
                detail="Artifact reader is not configured.",
            )
        return self.reader

    def require_neo4j(self) -> Neo4jReader:
        """Ensure Neo4j adapter is active and configured.

        Returns
        -------
        Neo4jReader
            Active Neo4j reader instance.

        Raises
        ------
        Neo4jUnavailableError
            If Neo4j adapter is not available.
        """
        if self.neo4j_reader is None:
            raise Neo4jUnavailableError("Neo4j database connection is not available.")
        return self.neo4j_reader

    def get_run_graph(
        self,
        run_id: str,
        budget: int | None = None,
        use_run_schema: bool = False,
    ) -> GraphView:
        """Retrieve the materialized GraphView for a pipeline run.

        Parameters
        ----------
        run_id : str
            Unique run ID.
        budget : int or None, optional
            Node budget override.
        use_run_schema : bool, default False
            If True, uses the run's embedded schema. Otherwise active schema.

        Returns
        -------
        GraphView
            Subsystem graph view.

        Raises
        ------
        StudioProblemException
            If run does not exist.
        """
        active_budget = budget or self.default_budget
        reader = self.require_reader()
        run = reader.get_run(run_id)
        if run is None:
            raise StudioProblemException(
                type="run-not-found",
                title="Run Not Found",
                status=404,
                detail=f"Run '{run_id}' not found.",
                instance=f"/api/runs/{run_id}/graph",
            )
        return reader.get_graph(run_id, budget=active_budget, use_run_schema=use_run_schema)

    def get_evidence(self, run_id: str, node_id: str) -> EvidenceTrail:
        """Trace the evidence trail for a specific graph node.

        Parameters
        ----------
        run_id : str
            Unique run ID.
        node_id : str
            Target node identifier.

        Returns
        -------
        EvidenceTrail
            Structured provenance trail.
        """
        reader = self.require_reader()
        run = reader.get_run(run_id)
        if run is None:
            raise StudioProblemException(
                type="run-not-found",
                title="Run Not Found",
                status=404,
                detail=f"Run '{run_id}' not found.",
                instance=f"/api/runs/{run_id}/evidence/{node_id}",
            )
        return reader.get_evidence(run_id, node_id)

    async def get_neo4j_view(
        self,
        budget: int | None = None,
        layer: int | None = None,
    ) -> GraphView:
        """Retrieve full or layer-filtered GraphView projected from Neo4j.

        Parameters
        ----------
        budget : int or None, optional
            Node budget limit, defaulting to default_budget.
        layer : int or None, optional
            Optional layer filter (1, 2, or 3).

        Returns
        -------
        GraphView
            Materialized graph projection.
        """
        reader = self.require_neo4j()
        eff_budget = budget or self.default_budget
        return await reader.get_graph_view(
            budget=eff_budget,
            layer=layer,
            timeout=self.query_timeout_seconds,
        )

    async def expand_neo4j_graph(
        self,
        seeds: list[str],
        depth: int = 1,
        budget: int | None = None,
    ) -> GraphView:
        """Expand k-hop neighborhood from seed node IDs in Neo4j.

        Parameters
        ----------
        seeds : list of str
            Seed node IDs.
        depth : int, default 1
            Hop distance.
        budget : int or None, optional
            Node budget limit, defaulting to default_budget.

        Returns
        -------
        GraphView
            Expanded sub-graph projection.
        """
        reader = self.require_neo4j()
        eff_budget = budget or self.default_budget
        return await reader.expand_graph(
            seeds=seeds,
            depth=depth,
            budget=eff_budget,
            timeout=self.query_timeout_seconds,
        )

    async def execute_cypher(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> CypherResult:
        """Execute an ad-hoc Cypher query through Neo4j read-only session.

        Parameters
        ----------
        query : str
            Cypher statement.
        params : dict of str to Any, optional
            Query parameters.
        limit : int or None, optional
            Row cap limit, defaulting to default_budget.

        Returns
        -------
        CypherResult
            Tabular query results.
        """
        reader = self.require_neo4j()
        eff_limit = limit or self.default_budget
        return await reader.execute_cypher(
            query=query,
            params=params,
            limit=eff_limit,
            timeout=self.query_timeout_seconds,
        )
