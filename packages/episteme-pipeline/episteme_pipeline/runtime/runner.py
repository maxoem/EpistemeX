"""Pipeline execution runner and runtime entry points.

Provides reusable factory and execution functions for launching the full
Grund GLP theory graph construction pipeline from API workers, scripts,
or interactive environments.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from llama_index.embeddings.litellm import LiteLLMEmbedding
from llama_index.llms.litellm import LiteLLM

from episteme_pipeline.config import (
    ExecutionConfig,
    Phase2Config,
    Phase3bConfig,
    Phase3Config,
    Phase5Config,
    PipelineConfig,
)
from episteme_pipeline.contracts.domain import GlobalStructuralAnchor
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.graph import (
    Neo4jGraphReader,
    Neo4jGraphWriter,
    Neo4jProcessingGraph,
)
from episteme_pipeline.phases.phase3_global_relations.rerankers import (
    SentenceTransformerCrossEncoderReranker,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.prompts import LangfusePromptProvider
from episteme_pipeline.runs.models import ExecutionResult

logger = logging.getLogger(__name__)


async def run_pipeline(
    source_paths: Sequence[str] | None = None,
    *,
    bib_paths: Sequence[str | Path] | None = None,
    metadata: dict[str, str] | None = None,
    structural_anchor: GlobalStructuralAnchor | dict[str, Any] | None = None,
    pipeline_input: PipelineInput | None = None,
    config: PipelineConfig | dict[str, Any] | None = None,
    event_emitter: EventEmitter | None = None,
    run_id: str | None = None,
    parent_run_id: str | None = None,
    neo4j_url: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
    neo4j_database: str | None = None,
) -> ExecutionResult:
    """Execute a complete pipeline pass across all conceptual phases.

    Instantiates LLM generation, embedding models, rerankers, and graph store
    drivers, binds the event emitter for live telemetry, and orchestrates the
    pipeline execution.

    Parameters
    ----------
    source_paths : Sequence of str or None, optional
        List of file paths to source documents to process.
    bib_paths : Sequence of str or Path or None, optional
        Optional file paths to bibliography references (.bib), by default None.
    metadata : dict of str to str or None, optional
        Arbitrary execution metadata strings, by default None.
    structural_anchor : GlobalStructuralAnchor or dict or None, optional
        Global structural anchor coordinate system (ToC outline, document summary, and/or
        global thesis) for the target document or pipeline run, by default None.
    pipeline_input : PipelineInput or None, optional
        Explicit PipelineInput instance. If omitted, built from source_paths, bib_paths,
        metadata, and structural_anchor.
    config : PipelineConfig or dict of str to Any or None, optional
        Pipeline configuration instance or dictionary snapshot. If omitted,
        a default production configuration is built and populated via Langfuse.
    event_emitter : EventEmitter or None, optional
        Event bus emitter to receive real-time domain and progress events.
    run_id : str or None, optional
        Unique run identifier for this execution.
    parent_run_id : str or None, optional
        Identifier of parent run if resuming or forking from a previous checkpoint.
    neo4j_url : str or None, optional
        Neo4j connection URL override. Defaults to NEO4J_URL environment variable.
    neo4j_user : str or None, optional
        Neo4j username override. Defaults to NEO4J_USERNAME environment variable.
    neo4j_password : str or None, optional
        Neo4j password override. Defaults to NEO4J_PASSWORD environment variable.
    neo4j_database : str or None, optional
        Neo4j database name override. Defaults to NEO4J_DATABASE environment variable.

    Returns
    -------
    ExecutionResult
        Result containing execution manifest, reports, and artifact metrics.
    """
    paths = list(source_paths) if source_paths else []

    # 1. Resolve Pipeline Configuration
    if isinstance(config, PipelineConfig):
        cfg = config
    elif isinstance(config, dict):
        cfg = PipelineConfig(**config)
    else:
        prompt_provider = LangfusePromptProvider()
        cfg = PipelineConfig(
            execution=ExecutionConfig(project_artifacts_to_graph=True),
            phase2=Phase2Config(max_gleanings=2),
            phase3=Phase3Config(dense_similarity_threshold=0.8),
            phase3b=Phase3bConfig(dense_similarity_threshold=0.8),
            phase5=Phase5Config(theory_fusion_enabled=True, cluster_layer="both"),
        )
        try:
            cfg = prompt_provider.populate_config(cfg, label_or_version="production")
        except Exception as exc:
            logger.warning("Could not populate config from Langfuse prompt provider: %s", exc)

    # 2. OpenAILike / LiteLLM Generation Model
    model_name = getattr(cfg.models, "llm_model", None) or os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    api_base = getattr(cfg.models, "llm_api_base", None) or os.getenv("LITELLM_API_BASE")
    temperature = getattr(cfg.models, "temperature", 0.0)

    llm_kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "temperature": temperature,
    }
    if api_base:
        llm_kwargs["api_base"] = api_base

    llm = LiteLLM(**llm_kwargs)

    # 3. OpenAILike / LiteLLM Embedding Model
    embed_name = getattr(cfg.models, "embedding_model", None) or os.getenv("EMBED_MODEL", "openai/text-embedding-3-small")
    embed_kwargs: dict[str, Any] = {
        "model_name": embed_name,
        "api_key": os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
    }
    if api_base:
        embed_kwargs["api_base"] = api_base

    embed_model = LiteLLMEmbedding(**embed_kwargs)

    # 4. HuggingFace CrossEncoder Reranker Model
    reranker_name = getattr(cfg.models, "reranker_model", None) or os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-0.6B")
    reranker = SentenceTransformerCrossEncoderReranker(
        model_name=reranker_name,
        cache_model=True,
        model_kwargs={"torch_dtype": "auto"},
    )

    # 5. Neo4j Graph Store Components
    url = neo4j_url or os.getenv("NEO4J_URL", "neo4j://127.0.0.1:7687")
    user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
    password = neo4j_password or os.getenv("NEO4J_PASSWORD", "neo4jdbpass")
    database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")

    graph_reader = Neo4jGraphReader(
        url=url, username=user, password=password, database=database
    )
    projection_graph = Neo4jGraphWriter(
        url=url, username=user, password=password, database=database
    )
    checkpoint_store = Neo4jProcessingGraph(
        url=url, username=user, password=password, database=database
    )

    # 6. Instantiate Pipeline via Pipeline.for_task()
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
        # 7. Ensure the Neo4j vector index exists
        embedding_dim = int(os.getenv("EMBED_DIM", "1536"))
        await projection_graph.ensure_indexes(embedding_dim=embedding_dim)

        # 8. Execute Pipeline Pass
        if pipeline_input is None:
            anchor_obj = None
            if structural_anchor is not None:
                if isinstance(structural_anchor, GlobalStructuralAnchor):
                    anchor_obj = structural_anchor
                elif isinstance(structural_anchor, dict):
                    anchor_obj = GlobalStructuralAnchor(**structural_anchor)
            pipeline_input = PipelineInput(
                source_paths=paths,
                bib_paths=list(bib_paths) if bib_paths else [],
                metadata=metadata or {},
                structural_anchor=anchor_obj,
            )

        logger.info(
            "Starting complete pipeline execution for run_id=%s (parent_run_id=%s) with %d source paths",
            run_id,
            parent_run_id,
            len(pipeline_input.source_paths),
        )
        result = await pipeline.run(pipeline_input, run_id=run_id, parent_run_id=parent_run_id)
        return result
    finally:
        for handle in (graph_reader, projection_graph, checkpoint_store):
            try:
                await handle.close()
            except Exception as close_exc:
                logger.debug("Error closing graph handle %s: %s", handle, close_exc)
