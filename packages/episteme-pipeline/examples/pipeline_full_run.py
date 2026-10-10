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
from episteme_pipeline import Phase2Config, Phase3Config, Pipeline
from episteme_pipeline.config import (
    ExecutionConfig,
    Phase3bConfig,
    Phase5Config,
    PipelineConfig,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.graph import (
    Neo4jGraphReader,
    Neo4jGraphWriter,
    Neo4jProcessingGraph,
)
from episteme_pipeline.phases.phase3_global_relations.rerankers import (
    SentenceTransformerCrossEncoderReranker,
)
from episteme_pipeline.runs.reporting import format_text
from llama_index.embeddings.litellm import LiteLLMEmbedding
from llama_index.llms.litellm import LiteLLM

if TYPE_CHECKING:
    from episteme_pipeline.events import EventEmitter
    from episteme_pipeline.runs.models import ExecutionResult

from episteme_pipeline.contracts.domain import GlobalStructuralAnchor
from episteme_pipeline.events import (
    LangfuseObserver,
    RichProgressObserver,
    SimpleEventEmitter,
)

_SOURCE_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_PATHS: list[str] = [str(_SOURCE_ROOT / "examples" / "text" / "teachers_expectancies.md")]



async def run_pipeline(
    source_paths: list[str] | None = None,
    *,
    event_emitter: EventEmitter | None = None,
) -> ExecutionResult:
    """Run a complete 7-runner pipeline pass using LiteLLM, CrossEncoder, and Neo4j.

    Parameters
    ----------
    source_paths : list[str] | None, optional
        List of file paths to process. Defaults to ``DEFAULT_SOURCE_PATHS``.
    event_emitter : EventEmitter | None, optional
        Emitter the pipeline binds for the duration of the run, so observers
        registered on it see every domain event. Defaults to a no-op emitter.
        See ``examples/observers/kg_construction_events.py``.

    Returns
    -------
    ExecutionResult
        The run's manifest and report.
    """
    source_paths = list(source_paths) if source_paths else list(DEFAULT_SOURCE_PATHS)

    # 1. OpenAILike / LiteLLM Generation Model
    llm_kwargs = {
        "model": os.getenv("LLM_MODEL", ""),
        "api_key": os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    }
    api_base = os.getenv("LITELLM_API_BASE")
    if api_base:
        llm_kwargs["api_base"] = api_base

    llm = LiteLLM(**llm_kwargs)

    # 2. OpenAILike / LiteLLM Embedding Model
    embed_kwargs = {
        "model_name": os.getenv("EMBED_MODEL", ""),
        "api_key": os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    }
    if api_base:
        embed_kwargs["api_base"] = api_base

    embed_model = LiteLLMEmbedding(**embed_kwargs)

    # 3. HuggingFace CrossEncoder Reranker Model
    reranker = SentenceTransformerCrossEncoderReranker(
        model_name=os.getenv("RERANKER_MODEL", ""),
        cache_model=True,
        model_kwargs={"torch_dtype": "auto"},
    )

    # 4. Neo4j Graph Store Components
    neo4j_url = os.getenv("NEO4J_URL", "neo4j://127.0.0.1:7687")
    neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "neo4jdbpass")
    neo4j_db = os.getenv("NEO4J_DATABASE", "neo4j")

    graph_reader = Neo4jGraphReader(
        url=neo4j_url, username=neo4j_user, password=neo4j_password, database=neo4j_db
    )
    projection_graph = Neo4jGraphWriter(
        url=neo4j_url, username=neo4j_user, password=neo4j_password, database=neo4j_db
    )
    checkpoint_store = Neo4jProcessingGraph(
        url=neo4j_url, username=neo4j_user, password=neo4j_password, database=neo4j_db
    )

    # 5. Pipeline Configuration
    cfg = PipelineConfig(
        execution=ExecutionConfig(project_artifacts_to_graph=True),
        phase2=Phase2Config(max_gleanings=2),
        phase3=Phase3Config(dense_similarity_threshold=0.8),
        phase3b=Phase3bConfig(dense_similarity_threshold=0.8),
        phase5=Phase5Config(theory_fusion_enabled=True, cluster_layer="both")
    )

    # 6. Instantiate 7-Runner Pipeline via Pipeline.for_task()
    # Phases included:
    #   - Phase 1: Data Foundation (Phase1Runner)
    #   - Phase 2: Entity Discovery & Local Relations (Phase2Runner)
    #   - Phase 3: Global Relation Extractor (Phase3Runner)
    #   - Phase 3b: Latent Graph Consolidation (Phase3bLatentConsolidationRunner)
    #   - Phase 4: Entity Maturation (Phase4EntityMaturationRunner)
    #   - Phase 4: Argument Mining (Phase4Runner)
    #   - Phase 5: Alignment & Theory Fusion (Phase5bTheoryFusionRunner)
    pipeline = Pipeline.for_task(
        task="knowledge_graph",
        llm=llm,
        relation_reranker=reranker,
        cross_encoder=reranker,
        embedding_model=embed_model,
        config=cfg,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
        event_emitter=event_emitter,
    )

    try:
        # 7. Ensure the Neo4j vector index exists before any chunk is written.
        # The dimensionality must match the embedding model in use.
        await projection_graph.ensure_indexes(
            embedding_dim=int(os.getenv("EMBED_DIM", "1536"))
        )

        # 8. Execute Pipeline Pass
        logging.info("Starting complete pipeline execution across 7 phase runners...")
        thesis = (
            "Within each of 18 classrooms, an average of 20% of the children were reported "
            "to classroom teachers as showing unusual potential for intellectual gains. "
            "Eight months later these 'unusual' children (who had actually been selected at random) "
            "showed significantly greater gains in IQ than did the remaining children in the control group. "
            "These effects of teachers' expectancies operated primarily among the younger children."
        )
        result = await pipeline.run(
            PipelineInput(
                source_paths=source_paths,
                structural_anchor=GlobalStructuralAnchor(global_thesis=thesis),
            )
        )

        # 9. Report Execution Results
        manifest = result.manifest
        report = result.report
        print(format_text(report, manifest))
        return result
    finally:
        # 10. Release the three Neo4j drivers. Each handle owns its own driver
        # and connection pool; leaking them keeps the event loop alive and
        # emits "Unclosed AsyncSession" warnings on interpreter shutdown.
        for handle in (graph_reader, projection_graph, checkpoint_store):
            await handle.close()


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
            asyncio.run(run_pipeline(event_emitter=emitter))


