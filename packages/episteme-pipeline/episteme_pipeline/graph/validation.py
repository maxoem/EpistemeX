"""Graph validation and structural constraints.

This module replaces external OWL reasoners by using native Neo4j Cypher queries
to enforce logical disjointness and structural integrity within the theory graph.
"""

from __future__ import annotations

import logging
from typing import Any

from episteme_pipeline.schema.default_schema import L3_COMPONENT_TYPES

logger = logging.getLogger(__name__)

POS_TYPES = ["SUPPORTS", "Z1_SUPPORTS", "BESTAETIGT", "BASIERT_AUF"]
NEG_TYPES = [
    "UNDERMINES",
    "Z1_UNDERMINES",
    "CONFLICTS",
    "WIDERSPRICHT",
    "FALSIFIZIERT",
    "KRITISIERT",
    "KONTRASTIEREND_ZU",
]


class GraphValidator:
    """Executes structural integrity queries against the Neo4j property graph.

    Parameters
    ----------
    store : Any
        An active Neo4j connection instance that provides a `_session()` async method.
    """

    def __init__(self, store: Any) -> None:
        """Initialize the GraphValidator."""
        self.store = store

    async def check_direct_disjointness(self) -> list[dict[str, Any]]:
        """Find instances where an entity simultaneously supports and attacks the same target.

        This violates logical disjointness constraints for argumentative discourse.

        Returns
        -------
        list of dict
            A list of dictionary records containing the violating node IDs.
        """
        pos_cypher = "|".join(POS_TYPES)
        neg_cypher = "|".join(NEG_TYPES)

        query = f"""
        MATCH (a)-[r1:{pos_cypher}]->(b)
        MATCH (a)-[r2:{neg_cypher}]->(b)
        RETURN a.id AS source_id, b.id AS target_id, labels(a) AS source_labels, labels(b) AS target_labels, type(r1) AS positive_relation, type(r2) AS negative_relation
        """
        logger.info("Executing direct disjointness check...")
        async with self.store._session() as session:
            result = await session.run(query)
            return await result.data()

    async def check_transitive_disjointness(self) -> list[dict[str, Any]]:
        """Find cyclical support/attack paths resulting in logical contradictions.

        For example: A supports B, B supports C, A attacks C.

        Returns
        -------
        list of dict
            A list of dictionary records containing the violating paths.
        """
        pos_cypher = "|".join(POS_TYPES)
        neg_cypher = "|".join(NEG_TYPES)

        query = f"""
        MATCH path_support = (a)-[:{pos_cypher}*2..4]->(c)
        MATCH path_attack = (a)-[:{neg_cypher}]->(c)
        RETURN a.id AS source, c.id AS target, length(path_support) AS support_depth
        """
        logger.info("Executing transitive disjointness check...")
        async with self.store._session() as session:
            result = await session.run(query)
            return await result.data()

    async def check_type_constraints(self) -> list[dict[str, Any]]:
        """Verify that TheoryAtom component_type values are valid.

        Checks against the allowed types in L3_COMPONENT_TYPES.

        Returns
        -------
        list of dict
            A list of dictionary records for nodes with invalid component types.
        """
        query = """
        MATCH (n:TheoryAtom)
        WHERE NOT n.component_type IN $valid_types
        RETURN n.id AS node_id, n.component_type AS invalid_type
        """
        logger.info("Executing type constraint check...")
        async with self.store._session() as session:
            result = await session.run(query, valid_types=L3_COMPONENT_TYPES)
            return await result.data()
