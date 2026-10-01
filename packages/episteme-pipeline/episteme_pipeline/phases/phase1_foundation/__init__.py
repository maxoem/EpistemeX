"""
Phase 1 — Data Foundation

Steps:
  1. Source Selection & Filtering (adapters choose the right converter)
  2. Data Acquisition via DataSourceAdapter (TeX/Markdown/text)
  3. Semantic Chunking — chapter/section → chunk hierarchy
  4. Provenance tracking — deterministic IDs, source metadata on every node
  5. Embedding — chunk text embedded and stored on the Chunk node
  6. Graph commit — Document → Chapter → Chunk nodes + CONTAINS / NEXT edges

All writes use MERGE semantics → safe to re-run on unchanged input.
Chunks that already exist in the graph (same deterministic ID) are skipped
via a graph-side existence check — crash-safe incremental processing.

See: docs/workflow/1_data_foundation/preprocess_clean.puml
     docs/workflow/1_data_foundation/metadata_provenance.puml
"""

from __future__ import annotations

import asyncio
import logging
from itertools import batched
from pathlib import Path

from episteme_pipeline.artifacts.builders import build_chunk_artifact, build_document_artifact
from episteme_pipeline.artifacts.execution import ArtifactCollection, ArtifactExecutionContext
from episteme_pipeline.config import Phase1Config
from episteme_pipeline.contracts.domain import L1Chunk, L1Document
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import (
    ChunksGenerated,
    EventEmitter,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
    get_event_emitter,
)
from episteme_pipeline.phases.phase1_foundation.adapters import DEFAULT_ADAPTERS, find_adapter
from episteme_pipeline.phases.phase1_foundation.chunker import chunk_document
from episteme_pipeline.phases.phase1_foundation.provenance import (
    base_provenance,
    canonical_source,
    chapter_id,
    chunk_id,
    creation_provenance,
    doc_id,
)
from episteme_pipeline.phases.phase1_foundation.toc_parser import AutoToCParser
from episteme_pipeline.protocols.data_source import DataSourceAdapter
from episteme_pipeline.protocols.extractors import EmbeddingModel
from episteme_pipeline.protocols.graph_store import GraphWriter
from episteme_pipeline.protocols.phase_runner import PhaseRunner

logger = logging.getLogger(__name__)


class Phase1Runner(PhaseRunner[PipelineInput]):
    name = "Phase 1: Data Foundation"
    phase_key = "phase1"
    input_view = None

    def __init__(
        self,
        config: Phase1Config,
        *,
        llm,
        embedding_model: EmbeddingModel | None = None,
        graph_store: GraphWriter,
        adapters: list[DataSourceAdapter] | None = None,
        toc_parser: AutoToCParser | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.embedding_model = embedding_model
        self.graph_store = graph_store
        self.adapters = adapters or DEFAULT_ADAPTERS
        self.toc_parser = toc_parser or AutoToCParser()

    @property
    def event_emitter(self) -> EventEmitter:
        return get_event_emitter()

    async def run(
        self, input: PipelineInput, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """
        Execute Phase 1 data ingestion, chunking, and embedding.

        Parameters
        ----------
        input : PipelineInput
            Input containing source document file paths and bibliography files.
        context : ArtifactExecutionContext
            Execution context containing run ID and pipeline manifest.

        Returns
        -------
        ArtifactCollection
            Generated DocumentArtifact and ChunkArtifact instances.
        """
        bib_paths = [Path(p) for p in input.bib_paths]
        
        progress_task = f"Phase 1: {len(input.source_paths)} docs"
        self.event_emitter.emit(ProgressStarted(task_name=progress_task, total_items=len(input.source_paths), description="Data Foundation"))

        async def _process_with_progress(path):
            res = await self._process_document(
                Path(path),
                bib_paths=bib_paths,
                run_id=context.run_id,
            )
            self.event_emitter.emit(ProgressAdvanced(task_name=progress_task, advance=1))
            return res

        results = await asyncio.gather(
            *[
                _process_with_progress(source_path)
                for source_path in input.source_paths
            ]
        )
        
        self.event_emitter.emit(ProgressCompleted(task_name=progress_task))
        documents: list[L1Document] = []
        all_chunks: list[L1Chunk] = []
        for doc, chunks in results:
            documents.append(doc)
            all_chunks.extend(chunks)

        artifacts = [
            build_document_artifact(
                document,
                run_id=context.run_id,
                phase_name=self.name,
                method="phase1.foundation",
            )
            for document in documents
        ]
        artifacts.extend(
            build_chunk_artifact(
                chunk,
                run_id=context.run_id,
                phase_name=self.name,
                method="phase1.foundation",
            )
            for chunk in all_chunks
        )
        return ArtifactCollection(artifacts)

    async def _process_document(
        self,
        path: Path,
        bib_paths: list[Path] | None = None,
        run_id: str | None = None,
    ) -> tuple[L1Document, list[L1Chunk]]:
        """
        Process a single document file into an L1Document and its chunk hierarchy.

        Parameters
        ----------
        path : Path
            File path of the document to process.
        bib_paths : list[Path] | None, optional
            Optional bibliography files, by default None.
        run_id : str | None, optional
            Current execution run ID, by default None.

        Returns
        -------
        tuple[L1Document, list[L1Chunk]]
            Constructed L1Document and list of extracted, embedded L1Chunks.
        """
        adapter = find_adapter(path, self.adapters)
        markdown = adapter.convert(path, bib_paths=bib_paths or None)

        # Extract document structural anchor via ToC Parser
        toc_anchor = self.toc_parser.parse(text=markdown, document_title=path.stem, path=path)

        raw_chunks = chunk_document(
            markdown,
            max_tokens=self.config.chunk_size,
            overlap_tokens=self.config.chunk_overlap,
        )

        d_id = doc_id(path)
        prov = base_provenance(path)
        # Written once, on node creation — see provenance.creation_provenance.
        created = creation_provenance()

        # Upsert Document node with local ToC anchor metadata
        await self.graph_store.upsert_node(
            label="Document",
            node_id=d_id,
            properties={
                "title": path.stem,
                "toc_structure": (
                    toc_anchor.toc_structure
                    if isinstance(toc_anchor.toc_structure, str)
                    else "\n".join(toc_anchor.toc_structure)
                ),
                "document_summary": toc_anchor.document_summary or "",
                **prov,
            },
            create_only_properties=created,
        )


        # Group raw_chunks by chapter → deduplicate chapter upserts
        seen_chapters: dict[str, str] = {}  # title -> chapter_id
        chunks: list[L1Chunk] = []
        
        # 1. Collect and Batch Embed
        texts = [raw.text for raw in raw_chunks]
        embeddings = await self._embed_batch(texts) if texts else []
        
        # 2. Build L1Chunk objects and relations
        for i, raw in enumerate(raw_chunks):
            # Chapter node (upserted once per title)
            if raw.chapter_title not in seen_chapters:
                chap_id = chapter_id(d_id, raw.chapter_title)
                seen_chapters[raw.chapter_title] = chap_id
                await self.graph_store.upsert_node(
                    label="Chapter",
                    node_id=chap_id,
                    properties={
                        "title": raw.chapter_title,
                        "source_doc_id": d_id,
                        **prov,
                    },
                    create_only_properties=created,
                )
                await self.graph_store.upsert_relation(d_id, "CONTAINS", chap_id)

            chap_id = seen_chapters[raw.chapter_title]
            c_id = chunk_id(chap_id, raw.sequence_index, raw.text)

            embedding = embeddings[i] if embeddings else None

            chunk = L1Chunk(
                id=c_id,
                text=raw.text,
                source_doc_id=d_id,
                chapter_id=chap_id,
                sequence_index=raw.sequence_index,
                token_count=len(raw.text.split()),
                embedding=embedding,
                metadata={
                    **prov,
                    "_create_props": created,
                }
            )
            chunks.append(chunk)

        # 3. Batch upsert chunks
        for chunk_batch in batched(chunks, 500):
            await self.graph_store.upsert_chunks(list(chunk_batch))
            
        # 4. Upsert relations
        prev_chunk_id: str | None = None
        for chunk in chunks:
            await self.graph_store.upsert_relation(chunk.chapter_id, "CONTAINS", chunk.id)
            if prev_chunk_id is not None:
                await self.graph_store.upsert_relation(
                    prev_chunk_id, "NEXT", chunk.id, {"distance": 1}
                )
            prev_chunk_id = chunk.id

        # Chunk ids carry a fingerprint of their text, so re-ingesting an edited
        # document writes new chunk nodes beside the previous ones. Without this
        # sweep the graph accumulates dead chunks that get_chunks() still
        # returns, and downstream phases keep mining text the source no longer
        # contains.
        await self.graph_store.prune_document_children(
            d_id,
            keep_chunk_ids=[c.id for c in chunks],
            keep_chapter_ids=list(seen_chapters.values()),
        )

        doc = L1Document(
            id=d_id,
            title=path.stem,
            source_path=canonical_source(path),
            chapter_count=len(seen_chapters),
            chunk_count=len(chunks),
            structural_anchor=toc_anchor,
        )

        # Emit ChunksGenerated event
        try:
            self.event_emitter.emit(
                ChunksGenerated(
                    run_id=run_id,
                    document_id=d_id,
                    document_title=path.stem,
                    chunk_count=len(chunks),
                    token_count=sum(c.token_count for c in chunks),
                    phase=self.name,
                )
            )
        except Exception as e:
            logger.error("Failed to emit ChunksGenerated event: %s", e)

        return doc, chunks

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.embedding_model is None or not texts:
            return []
        return await self.embedding_model.aget_text_embedding_batch(texts)
