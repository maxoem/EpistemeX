"""Complete Grund GLP theory graph construction pipeline example.

This module demonstrates executing a complete 7-runner pipeline pass across all
5 conceptual phases as defined in `docs/concepts/pipeline_architecture.md`.

Components used:
- Generation: OpenAILike / LiteLLM (`llama_index.llms.litellm.LiteLLM`)
- Embeddings: OpenAILike / LiteLLM (`llama_index.embeddings.litellm.LiteLLMEmbedding`)
- Reranking: HuggingFace CrossEncoder (`SentenceTransformerCrossEncoderReranker`)
- Graph Backend: Neo4j (`Neo4jGraphReader`, `Neo4jGraphWriter`, `Neo4jProcessingGraph`)

Environment Variables
---------------------
OPENAI_API_KEY : str, optional
    API key for OpenAI or compatible provider.
LITELLM_API_KEY : str, optional
    LiteLLM API key override.
LITELLM_API_BASE : str, optional
    Base URL for LiteLLM / OpenAI-compatible endpoint.
LLM_MODEL : str, default="openai/gpt-4o-mini"
    Model identifier for generation.
EMBED_MODEL : str, default="openai/text-embedding-3-small"
    Model identifier for embeddings.
EMBED_DIM : int, default=1536
    Dimensionality of the embedding model, used to create the Neo4j vector index.
RERANKER_MODEL : str, default="Qwen/Qwen3-Reranker-0.6B"
    HuggingFace cross-encoder model identifier for relation reranking.
NEO4J_URL : str, default="neo4j://127.0.0.1:7687"
    URL for the Neo4j graph store instance.
NEO4J_USERNAME : str, default="neo4j"
    Username for Neo4j authentication.
NEO4J_PASSWORD : str, default="neo4jdbpass"
    Password for Neo4j authentication.
NEO4J_DATABASE : str, default="neo4j"
    Target Neo4j database name.

Run
---
    uv run python examples/pipeline_full_run.py

Notes
-----
For live updating Rich progress bars, execute this script in an interactive terminal (TTY):
    uv run python examples/pipeline_full_run.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Ensure project root is on sys.path when run directly from examples/ directory
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
from episteme_pipeline.runs.reporting import format_text

if TYPE_CHECKING:
    from episteme_pipeline.events import EventEmitter
    from episteme_pipeline.runs.models import ExecutionResult

from episteme_pipeline.events import (
    LangfuseObserver,
    RichProgressObserver,
    SimpleEventEmitter,
)
from episteme_pipeline.runs.observability import run_observability_context

_SOURCE_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_PATHS: list[str] = [str(_SOURCE_ROOT / "examples" / "text" / "teachers_expectancies.md")]


async def run_pipeline(
    source_paths: list[str] | None = None,
    *,
    event_emitter: EventEmitter | None = None,
    run_id: str | None = None,
) -> ExecutionResult:
    """Run a complete 7-runner pipeline pass using LiteLLM, CrossEncoder, and Neo4j.

    Parameters
    ----------
    source_paths : list[str] | None, optional
        List of file paths to process. Defaults to ``DEFAULT_SOURCE_PATHS``.
    event_emitter : EventEmitter | None, optional
        Emitter the pipeline binds for the duration of the run.
    run_id : str or None, optional
        Unique run identifier.

    Returns
    -------
    ExecutionResult
        The run's manifest and report.
    """
    source_paths = list(source_paths) if source_paths else list(DEFAULT_SOURCE_PATHS)
    from episteme_pipeline.runtime.runner import run_pipeline as _run_pipeline

    result = await _run_pipeline(
        source_paths=source_paths,
        event_emitter=event_emitter,
        run_id=run_id,
    )
    manifest = result.manifest
    report = result.report
    print(format_text(report, manifest))
    return result


if __name__ == "__main__":
    load_dotenv()

    # Setup the decoupled event emitter and Rich progress observer
    emitter = SimpleEventEmitter()
    
    try:
        langfuse_observer = LangfuseObserver()
        emitter.register_observer(langfuse_observer)
    except RuntimeError:
        logging.warning("Langfuse is not installed. Pipeline will run without Langfuse observability.")

    with RichProgressObserver(third_party_log_level=logging.WARNING) as observer:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            handlers=[observer.get_rich_handler(rich_tracebacks=True, show_path=False)],
            force=True,
        )
        emitter.register_observer(observer)
        from uuid import uuid4
        session_id = os.getenv("LANGFUSE_SESSION_ID") or f"kg-session-{uuid4().hex[:8]}"
        with run_observability_context(
            name="full_pipeline_run",
            session_id=session_id,
            tags=["example", "knowledge_graph"],
        ):
            asyncio.run(run_pipeline(event_emitter=emitter, run_id=session_id))


