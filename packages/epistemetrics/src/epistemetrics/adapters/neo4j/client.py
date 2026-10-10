"""
Neo4j driver connection and session management.

Provides managed database driver lifecycle, health checking, GDS availability
detection, and domain exception translation.
"""

from __future__ import annotations

import logging
from typing import Any

from epistemetrics.core.exceptions import (
    AdapterError,
    GDSNotAvailableError,
    RepositoryConnectionError,
)

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Manages driver connections, sessions, and queries for Neo4j.

    Parameters
    ----------
    uri : str
        Neo4j bolt/neo4j connection URI (e.g. 'bolt://localhost:7687').
    username : str
        Database username.
    password : str
        Database password.
    database : str, optional
        Target Neo4j database name (default: 'neo4j').
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
    ) -> None:
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self._driver: Any | None = None

    def _ensure_driver(self) -> Any:
        """Instantiate driver lazily with exception translation."""
        if self._driver is not None:
            return self._driver

        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise AdapterError(
                "The 'neo4j' package is required to use Neo4j adapters. "
                "Install it with 'pip install epistemetrics[neo4j]' or 'uv add neo4j'."
            ) from exc

        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
            return self._driver
        except Exception as exc:
            raise RepositoryConnectionError(
                f"Failed to initialize Neo4j driver for URI {self.uri}: {exc}"
            ) from exc

    def check_connectivity(self) -> bool:
        """Verify if Neo4j is reachable and authentication is valid.

        Returns
        -------
        bool
            True if database is reachable, False otherwise.
        """
        try:
            driver = self._ensure_driver()
            driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.debug("Neo4j connectivity check failed: %s", exc)
            return False

    def is_gds_available(self) -> bool:
        """Check whether the Neo4j Graph Data Science (GDS) library is installed and operational.

        Returns
        -------
        bool
            True if GDS procedures are available, False otherwise.
        """
        if not self.check_connectivity():
            return False

        try:
            results = self.execute_query("RETURN gds.version() AS version")
            return bool(results and results[0].get("version"))
        except Exception as exc:
            logger.debug("Neo4j GDS version query failed: %s", exc)
            return False

    def ensure_gds_available(self) -> None:
        """Assert that Neo4j GDS is operational, raising domain error otherwise.

        Raises
        ------
        GDSNotAvailableError
            If GDS is not installed or unreachable.
        """
        if not self.is_gds_available():
            raise GDSNotAvailableError(
                "Neo4j Graph Data Science (GDS) library is not installed or reachable on the server."
            )

    def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query synchronously and return records as dictionaries.

        Parameters
        ----------
        query : str
            Parameterized Cypher query string.
        parameters : dict[str, Any] | None, optional
            Query parameters.

        Returns
        -------
        list[dict[str, Any]]
            List of record dictionaries.

        Raises
        ------
        RepositoryConnectionError
            If connection fails.
        AdapterError
            If query execution fails.
        """
        driver = self._ensure_driver()
        try:
            with driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as exc:
            err_type = type(exc).__name__
            if "ServiceUnavailable" in err_type or "AuthError" in err_type:
                raise RepositoryConnectionError(f"Neo4j connection error: {exc}") from exc
            raise AdapterError(f"Neo4j query execution failed: {exc}") from exc

    def close(self) -> None:
        """Close the underlying driver."""
        if self._driver is not None:
            try:
                self._driver.close()
            finally:
                self._driver = None
