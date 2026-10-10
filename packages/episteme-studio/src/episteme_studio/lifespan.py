"""Lifespan context manager for application setup and teardown."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from episteme_studio.runtime.broker import EventBroker
from episteme_studio.runtime.executor import PipelineExecutor
from episteme_studio.runtime.registry import RunRegistry

if TYPE_CHECKING:
    from episteme_studio.settings import StudioSettings


def create_lifespan(settings: StudioSettings):
    """Factory creating a FastAPI lifespan context manager with configured settings.

    Parameters
    ----------
    settings : StudioSettings
        The runtime settings for the studio instance.

    Returns
    -------
    Callable
        An async context manager suitable for FastAPI(lifespan=...).
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings

        if not hasattr(app.state, "broker") or app.state.broker is None:
            app.state.broker = EventBroker()
        if not hasattr(app.state, "registry") or app.state.registry is None:
            app.state.registry = RunRegistry()
        if not hasattr(app.state, "executor") or app.state.executor is None:
            app.state.executor = PipelineExecutor(app.state.registry, app.state.broker)

        # Neo4j AsyncDriver management (M6)
        driver = getattr(app.state, "neo4j_driver", None)
        if driver is None and settings.neo4j_url:
            try:
                import asyncio
                from neo4j import AsyncGraphDatabase
                auth = (
                    (settings.neo4j_user, settings.neo4j_password)
                    if settings.neo4j_user
                    else None
                )
                driver = AsyncGraphDatabase.driver(settings.neo4j_url, auth=auth)
                app.state.neo4j_driver = driver
                try:
                    async with asyncio.timeout(2.0):
                        await driver.verify_connectivity()
                    app.state.neo4j_available = True
                except Exception:
                    app.state.neo4j_available = False
            except Exception:
                app.state.neo4j_driver = None
                app.state.neo4j_available = False
        elif driver is not None:
            if getattr(app.state, "neo4j_available", None) is None:
                try:
                    import asyncio
                    async with asyncio.timeout(2.0):
                        await driver.verify_connectivity()
                    app.state.neo4j_available = True
                except Exception:
                    app.state.neo4j_available = False
        else:
            app.state.neo4j_driver = None
            app.state.neo4j_available = False

        # Optional Demo Seeding for Neo4j
        if settings.demo_mode and getattr(app.state, "neo4j_available", False):
            neo4j_driver = getattr(app.state, "neo4j_driver", None)
            if neo4j_driver:
                try:
                    await _seed_demo_neo4j(neo4j_driver, settings.neo4j_database)
                except Exception as err:
                    import sys
                    sys.stderr.write(f"Warning: Failed to seed demo datasets into Neo4j: {err}\n")

        try:
            yield
        finally:
            # Teardown: close Neo4j driver if managed
            neo4j_driver = getattr(app.state, "neo4j_driver", None)
            if neo4j_driver is not None:
                try:
                    await neo4j_driver.close()
                except Exception:
                    pass

            # Teardown: cancel or terminate any running subprocesses
            registry = getattr(app.state, "registry", None)
            if registry:
                for handle in registry.list_all():
                    if handle.process and handle.process.is_alive():
                        handle.process.terminate()
                        try:
                            handle.process.join(timeout=1.0)
                        except Exception:
                            pass
                        if handle.process.is_alive():
                            handle.process.kill()

    return lifespan


async def _seed_demo_neo4j(driver: Any, database: str | None = None) -> None:
    """Idempotently seed packaged demo datasets into Neo4j when running in demo mode.

    Parameters
    ----------
    driver : Any
        Active Neo4j AsyncDriver.
    database : str or None, optional
        Target Neo4j database name.
    """
    from episteme_studio.fixtures import get_fixture_cypher_dir

    cypher_dir = get_fixture_cypher_dir()
    if not cypher_dir.is_dir():
        return

    async with driver.session(database=database) as session:
        # Check if demo nodes already exist
        result = await session.run(
            "MATCH (n) WHERE n.id IN ['TN_NEWTON_V1', 'T_FREUD'] RETURN count(n) AS cnt"
        )
        record = await result.single()
        if record and record["cnt"] > 0:
            return

        for cypher_file in sorted(cypher_dir.glob("*.cypher")):
            content = cypher_file.read_text(encoding="utf-8")
            clean_lines = []
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("//") or not stripped:
                    continue
                clean_lines.append(line)
            full_script = "\n".join(clean_lines)
            statements = [stmt.strip() for stmt in full_script.split(";") if stmt.strip()]

            for stmt in statements:
                await session.run(stmt)

        # Apply dual marker labels for layer projection:
        # Layer 3: TheoryAtom
        await session.run(
            """
            MATCH (n)
            WHERE n:BasicAxiom OR n:DerivedEmpiricalLaw OR n:Evidence OR n:Claim OR n:Premise OR n:EmpiricalSentence
            SET n:TheoryAtom
            """
        )
        # Layer 2: Entity
        await session.run(
            """
            MATCH (n)
            WHERE n:PrimitiveTerm OR n:EmpiricalIndicator OR n:TheoreticalConstruct OR n:TheoryNet OR n:TheoryCore OR n:EmpiricalApplication OR n:Theory
            SET n:Entity
            """
        )
