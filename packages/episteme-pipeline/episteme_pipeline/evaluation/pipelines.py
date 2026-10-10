"""Pipeline construction factories for evaluation benchmarks.

Configures and instantiates Level 2 (Entity & Local Relation), Level 3 (Global Argumentation),
and Level 4 (Formal TheoryNet Projection) evaluation pipelines.
Supports pure in-memory execution requiring zero Neo4j database connectivity.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from episteme_pipeline.config import (
    ExecutionConfig,
    Phase2Config,
    Phase3Config,
    Phase3bConfig,
    PipelineConfig,
)
from episteme_pipeline.events import EventEmitter, NoOpEventEmitter
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.graph.neo4j_store import (
    Neo4jGraphReader,
    Neo4jGraphWriter,
    Neo4jProcessingGraph,
)
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.phases.phase3_global_relations.rerankers import (
    CrossEncoderRelationReranker,
    SentenceTransformerCrossEncoderReranker,
)
from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase4_entity_maturation import Phase4EntityMaturationRunner
from episteme_pipeline.phases.phase6_theorynet import Phase6Runner
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols.extractors import ensure_embedding_model


class _MockOfflineEmbeddingModel:
    """Offline fallback embedding model returning constant zero vectors."""

    async def aget_text_embedding(self, text: str) -> list[float]:
        return [0.0] * 384

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]


class _MockOfflineCrossEncoder:
    """Offline fallback cross-encoder returning neutral probability scores."""

    def predict(self, pairs: Any) -> list[float]:
        return [0.5] * len(pairs)


def _init_components(
    event_emitter: EventEmitter | None = None,
    in_memory: bool = True,
    llm: Any | None = None,
    embed_model: Any | None = None,
    reranker: Any | None = None,
):
    """Initialize shared models, configs, and graph storage handles with offline fallbacks.

    Parameters
    ----------
    event_emitter : EventEmitter, optional
        Telemetry event bus.
    in_memory : bool, optional
        If True, initializes pure in-memory stores; if False, connects to Neo4j.
    llm : Any, optional
        Explicit LLM handle.
    embed_model : Any, optional
        Explicit embedding model handle.
    reranker : Any, optional
        Explicit reranker handle.

    Returns
    -------
    tuple
        Tuple of (llm, embed_model, reranker, graph_reader, projection_graph, checkpoint_store, cfg).
    """
    load_dotenv()
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    if in_memory or os.getenv("OFFLINE") == "1":
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    api_key = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    api_base = os.getenv("LITELLM_API_BASE")

    if llm is None:
        try:
            from llama_index.llms.litellm import LiteLLM

            llm_kwargs = {
                "model": os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
                "api_key": api_key,
            }
            if api_base:
                llm_kwargs["api_base"] = api_base
            llm = LiteLLM(**llm_kwargs)
        except Exception:
            class _DummyLLM:
                async def acomplete(self, prompt: str) -> str:
                    return ""
            llm = _DummyLLM()

    if embed_model is None:
        default_embed = (
            "openai/text-embedding-3-small" if api_key else "sentence-transformers/all-MiniLM-L6-v2"
        )
        embed_model_name = os.getenv("EMBED_MODEL", default_embed)

        try:
            if (
                embed_model_name.startswith("local:")
                or "MiniLM" in embed_model_name
                or "huggingface" in embed_model_name
                or not api_key
            ):
                from sentence_transformers import SentenceTransformer

                clean_name = embed_model_name.replace("local:", "").replace("huggingface/", "")
                if clean_name == "openai/text-embedding-3-small" or not clean_name:
                    clean_name = "sentence-transformers/all-MiniLM-L6-v2"
                embed_model = ensure_embedding_model(SentenceTransformer(clean_name))
            else:
                from llama_index.embeddings.litellm import LiteLLMEmbedding

                embed_kwargs = {"model_name": embed_model_name, "api_key": api_key}
                if api_base:
                    embed_kwargs["api_base"] = api_base
                embed_model = ensure_embedding_model(LiteLLMEmbedding(**embed_kwargs))
        except Exception:
            embed_model = ensure_embedding_model(_MockOfflineEmbeddingModel())
    else:
        embed_model = ensure_embedding_model(embed_model)

    if reranker is None:
        try:
            reranker = SentenceTransformerCrossEncoderReranker(
                model_name=os.getenv("RERANKER_MODEL", "Qwen/Qwen3-Reranker-0.6B")
            )
        except Exception:
            reranker = _MockOfflineCrossEncoder()

    if in_memory:
        in_mem_store = InMemoryGraphStore()
        graph_reader = in_mem_store
        projection_graph = in_mem_store
        checkpoint_store = in_mem_store
    else:
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

    cfg = PipelineConfig(
        execution=ExecutionConfig(project_artifacts_to_graph=True),
        phase2=Phase2Config(max_gleanings=2),
        phase3=Phase3Config(dense_similarity_threshold=0.8),
        phase3b=Phase3bConfig(dense_similarity_threshold=0.8),
    )

    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM, default_cache_dir
    from episteme_pipeline.llm.structured import ensure_structured_llm

    try:
        llm = DiskCachedStructuredLLM(
            ensure_structured_llm(llm, use_cache=False, event_emitter=event_emitter),
            cache_dir=default_cache_dir(cfg.execution.runs_dir),
        )
    except Exception:
        pass

    return llm, embed_model, reranker, graph_reader, projection_graph, checkpoint_store, cfg


def build_l2_eval_pipeline(
    event_emitter: EventEmitter | None = None,
    in_memory: bool = True,
    llm: Any | None = None,
    embed_model: Any | None = None,
    reranker: Any | None = None,
) -> Pipeline:
    """Build a pipeline up to Phase 3 for SciERC / NER & Relation extraction evaluation.

    Parameters
    ----------
    event_emitter : EventEmitter, optional
        Telemetry event bus.
    in_memory : bool, optional
        If True, operates in memory without connecting to Neo4j (default: True).
    llm : Any, optional
        Explicit LLM model.
    embed_model : Any, optional
        Explicit embedding model.
    reranker : Any, optional
        Explicit cross-encoder reranker.

    Returns
    -------
    Pipeline
        Configured L2 evaluation pipeline.
    """
    (
        llm,
        embed_model,
        reranker,
        graph_reader,
        projection_graph,
        checkpoint_store,
        cfg,
    ) = _init_components(
        event_emitter,
        in_memory=in_memory,
        llm=llm,
        embed_model=embed_model,
        reranker=reranker,
    )

    cross_reranker = CrossEncoderRelationReranker(reranker)
    global_extractor = DenseRetrievalGlobalRelationExtractor(
        llm, embed_model, cross_reranker, cfg.phase3
    )

    phases = [
        Phase1Runner(cfg.phase1, llm=llm, embedding_model=embed_model, graph_store=projection_graph),
        Phase2Runner(
            cfg.phase2,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=checkpoint_store,
            cross_encoder=reranker,
        ),
        Phase3Runner(
            cfg.phase3,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
    ]

    return Pipeline(
        phases=phases,
        config=cfg,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
        event_emitter=event_emitter or NoOpEventEmitter(),
    )


def build_l3_eval_pipeline(
    event_emitter: EventEmitter | None = None,
    in_memory: bool = True,
    llm: Any | None = None,
    embed_model: Any | None = None,
    reranker: Any | None = None,
) -> Pipeline:
    """Build a pipeline up to Phase 4 for Arg-Microtexts argumentation evaluation.

    Parameters
    ----------
    event_emitter : EventEmitter, optional
        Telemetry event bus.
    in_memory : bool, optional
        If True, operates in memory without connecting to Neo4j (default: True).
    llm : Any, optional
        Explicit LLM model.
    embed_model : Any, optional
        Explicit embedding model.
    reranker : Any, optional
        Explicit cross-encoder reranker.

    Returns
    -------
    Pipeline
        Configured L3 evaluation pipeline.
    """
    (
        llm,
        embed_model,
        reranker,
        graph_reader,
        projection_graph,
        checkpoint_store,
        cfg,
    ) = _init_components(
        event_emitter,
        in_memory=in_memory,
        llm=llm,
        embed_model=embed_model,
        reranker=reranker,
    )

    cross_reranker = CrossEncoderRelationReranker(reranker)
    global_extractor = DenseRetrievalGlobalRelationExtractor(
        llm, embed_model, cross_reranker, cfg.phase3
    )

    phases = [
        Phase1Runner(cfg.phase1, llm=llm, embedding_model=embed_model, graph_store=projection_graph),
        Phase2Runner(
            cfg.phase2,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=checkpoint_store,
            cross_encoder=reranker,
        ),
        Phase3Runner(
            cfg.phase3,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            cfg.phase3b, embedding_model=embed_model, graph_store=graph_reader
        ),
        Phase4EntityMaturationRunner(
            cfg.phase4_maturation,
            llm=llm,
            graph_store=checkpoint_store,
            embedding_model=embed_model,
        ),
        Phase4Runner(
            cfg.phase4,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
    ]

    return Pipeline(
        phases=phases,
        config=cfg,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
        event_emitter=event_emitter or NoOpEventEmitter(),
    )


def build_l4_theorynet_eval_pipeline(
    event_emitter: EventEmitter | None = None,
    in_memory: bool = True,
    llm: Any | None = None,
    embed_model: Any | None = None,
    reranker: Any | None = None,
) -> Pipeline:
    """Build a full pipeline up to Phase 6 for Level 4 TheoryNet evaluation.

    Configures Phases 1, 2, 3, 3b, 4 (Maturation & Mining), and appends
    Phase 6 (TheoryNet Projection) to materialize formal structuralist model classes.

    Parameters
    ----------
    event_emitter : EventEmitter, optional
        Telemetry event bus.
    in_memory : bool, optional
        If True, operates in memory without connecting to Neo4j (default: True).
    llm : Any, optional
        Explicit LLM model.
    embed_model : Any, optional
        Explicit embedding model.
    reranker : Any, optional
        Explicit cross-encoder reranker.

    Returns
    -------
    Pipeline
        Configured L4 TheoryNet evaluation pipeline.
    """
    (
        llm,
        embed_model,
        reranker,
        graph_reader,
        projection_graph,
        checkpoint_store,
        cfg,
    ) = _init_components(
        event_emitter,
        in_memory=in_memory,
        llm=llm,
        embed_model=embed_model,
        reranker=reranker,
    )

    cross_reranker = CrossEncoderRelationReranker(reranker)
    global_extractor = DenseRetrievalGlobalRelationExtractor(
        llm, embed_model, cross_reranker, cfg.phase3
    )

    phases = [
        Phase1Runner(cfg.phase1, llm=llm, embedding_model=embed_model, graph_store=projection_graph),
        Phase2Runner(
            cfg.phase2,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=checkpoint_store,
            cross_encoder=reranker,
        ),
        Phase3Runner(
            cfg.phase3,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            cfg.phase3b, embedding_model=embed_model, graph_store=graph_reader
        ),
        Phase4EntityMaturationRunner(
            cfg.phase4_maturation,
            llm=llm,
            graph_store=checkpoint_store,
            embedding_model=embed_model,
        ),
        Phase4Runner(
            cfg.phase4,
            cfg.graph_schema,
            llm=llm,
            embedding_model=embed_model,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase6Runner(
            config=None,
            schema=cfg.graph_schema,
            graph_store=projection_graph,
        ),
    ]

    return Pipeline(
        phases=phases,
        config=cfg,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
        event_emitter=event_emitter or NoOpEventEmitter(),
    )
