"""Domain models for run summaries, phase steppers, and detailed run manifests."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field

from .errors import ProblemDetail


class RunStatus(StrEnum):
    """Pipeline execution status."""

    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class PhaseStatus(BaseModel):
    """Execution status and metrics for an individual pipeline phase.

    Parameters
    ----------
    phase_name : str
        Human-readable name of the phase (may not be unique, e.g. two 'Phase 4's).
    phase_ordinal : int
        Sequential index / ordinal of the phase, used as React key.
    status : RunStatus
        Current status of this phase.
    started_at : datetime or None, optional
        Timestamp when the phase began execution.
    completed_at : datetime or None, optional
        Timestamp when the phase completed.
    duration_seconds : float or None, optional
        Elapsed wall-clock time for the phase in seconds.
    reused : bool, default False
        Whether phase artifacts were reused from cache.
    artifact_count : int, default 0
        Number of artifacts produced or reused by this phase.
    yield_summary : str or None, optional
        Human-readable domain summary of extracted artifacts (e.g. '27 ADUs • 87 Relations').
    artifact_counts_by_kind : dict of str to int, optional
        Detailed count of artifacts produced by this phase grouped by artifact kind.
    """

    phase_name: str
    phase_ordinal: int
    status: RunStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    reused: bool = False
    artifact_count: int = 0
    yield_summary: str | None = None
    artifact_counts_by_kind: dict[str, int] = Field(default_factory=dict)


class GlobalStructuralAnchor(BaseModel):
    """Static global structural coordinate system anchor for LLM prompts.

    Parameters
    ----------
    toc_structure : list[str] | str, optional
        Structural outline or Table of Contents of the document, by default "".
    document_summary : str | None, optional
        Global summary of the document, by default None.
    global_thesis : str | None, optional
        Primary theoretical thesis or domain scope, by default None.
    """

    toc_structure: list[str] | str = ""
    document_summary: str | None = None
    global_thesis: str | None = None


class RunSummary(BaseModel):
    """Summary record of a pipeline run for table listings.

    Parameters
    ----------
    run_id : str
        Unique identifier of the run.
    status : RunStatus
        Overall run execution status.
    created_at : datetime
        Timestamp when the run record was created.
    completed_at : datetime or None, optional
        Timestamp when the run ended.
    duration_seconds : float or None, optional
        Total elapsed duration of the run in seconds.
    pipeline_version : str
        Version of the pipeline code that executed this run.
    schema_version : str or None, optional
        Version of the schema snapshot used for this run.
    input_sources : list of str, optional
        Paths or identifiers of input documents.
    bib_sources : list of str, optional
        Paths or identifiers of bibliography references (.bib).
    metadata : dict of str to str, optional
        Execution metadata key-values.
    structural_anchor : GlobalStructuralAnchor or None, optional
        Global structural anchor coordinate system.
    primary_input : str or None, optional
        Primary input file or corpus descriptor (e.g. 'planwirtschaft.md').
    models : dict of str to str, optional
        Resolved model names (LLM, embedding, reranker).
    artifact_count : int, default 0
        Total artifacts associated with this run.
    size_bytes : int, default 0
        Total size of artifact envelopes on disk in bytes.
    reused_phase_count : int, default 0
        Number of phases reused from previous checkpoint cache.
    total_phase_count : int, default 0
        Total number of executed or planned phases in the run.
    tags : list of str, optional
        Categorical labels or tags assigned to the run.
    parent_run_id : str or None, optional
        Identifier of parent run if resumed from a previous checkpoint.
    """

    run_id: str
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    pipeline_version: str
    schema_version: str | None = None
    input_sources: list[str] = Field(default_factory=list)
    bib_sources: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    structural_anchor: GlobalStructuralAnchor | None = None
    primary_input: str | None = None
    models: dict[str, str] = Field(default_factory=dict)
    artifact_count: int = 0
    size_bytes: int = 0
    reused_phase_count: int = 0
    total_phase_count: int = 0
    tags: list[str] = Field(default_factory=list)
    parent_run_id: str | None = None


class RunDetail(RunSummary):
    """Full detail view of a run including configuration and phase records.

    Parameters
    ----------
    phase_records : list of PhaseStatus
        Chronological status records for all executed phases.
    artifact_counts_by_kind : dict of str to int
        Breakdown of artifact counts by artifact kind.
    graph_schema : dict of str to Any
        Exact schema configuration active during the run.
    config_snapshot : dict of str to Any
        Snapshot of the full pipeline configuration (secrets redacted).
    fingerprints : dict of str to Any
        Phase and method fingerprint hashes.
    unresolved_count : int, default 0
        Number of dangling components referenced in this run.
    langfuse_url : str or None, optional
        Direct URL to inspect trace and LLM spans in Langfuse.
    failure : ProblemDetail or None, optional
        Failure detail if the run terminated in an error state.
    """

    phase_records: list[PhaseStatus]
    artifact_counts_by_kind: dict[str, int] = Field(default_factory=dict)
    graph_schema: dict[str, Any] = Field(default_factory=dict)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    fingerprints: dict[str, Any] = Field(default_factory=dict)
    unresolved_count: int = 0
    langfuse_url: str | None = None
    failure: ProblemDetail | None = None


class ArtifactRef(BaseModel):
    """Reference metadata for an individual persisted artifact envelope.

    Parameters
    ----------
    artifact_id : str
        Unique artifact identifier.
    identity_key : str
        Stable content/semantic identity key.
    kind : str
        Artifact kind (e.g. 'chunk', 'entity', 'global_relation', 'theory_atom').
    phase_name : str or None, optional
        Pipeline phase that created this artifact.
    created_at : datetime or None, optional
        Creation timestamp.
    size_bytes : int, default 0
        Size of the serialized artifact file on disk.
    """

    artifact_id: str
    identity_key: str
    kind: str
    phase_name: str | None = None
    created_at: datetime | None = None
    size_bytes: int = 0


class TextAnchor(BaseModel):
    """Multi-modal source evidence anchor for textual, tabular, or visual grounding.

    Parameters
    ----------
    source_doc_id : str or None, optional
        Identifier of the parent document.
    char_start : int or None, optional
        0-indexed character start offset in document/chunk text.
    char_end : int or None, optional
        0-indexed character end offset in document/chunk text.
    verbatim_quote : str or None, optional
        Verbatim textual quote.
    bbox : list of float or None, optional
        2D bounding box region [x0, y0, x1, y1] or [x0, y0, x1, y1, page].
    page : int or None, optional
        Document page number.
    formula_id : str or None, optional
        Formula identifier for mathematical equation blocks.
    table_id : str or None, optional
        Table identifier for tabular data grounding.
    figure_id : str or None, optional
        Figure identifier for diagrammatic and image grounding.
    """

    source_doc_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    verbatim_quote: str | None = None
    bbox: list[float] | None = None
    page: int | None = None
    formula_id: str | None = None
    table_id: str | None = None
    figure_id: str | None = None


class EvidenceSpan(BaseModel):
    """Multi-modal evidence region offset within a source text chunk, figure, or table.

    Parameters
    ----------
    start_char : int or None, optional
        0-indexed start character offset in chunk text.
    end_char : int or None, optional
        0-indexed end character offset in chunk text.
    text : str or None, optional
        Extracted text snippet.
    mode : Literal["exact", "substring", "whole_chunk", "visual", "tabular", "formula"]
        Resolution mode used to locate the span (D-19).
    bbox : list of float or None, optional
        Spatial bounding box region [x0, y0, x1, y1] or [x0, y0, x1, y1, page].
    page : int or None, optional
        Document page number.
    formula_id : str or None, optional
        Formula identifier for mathematical equations.
    table_id : str or None, optional
        Table identifier for tabular grounding.
    figure_id : str or None, optional
        Figure identifier for diagram grounding.
    """

    start_char: int | None = None
    end_char: int | None = None
    text: str | None = None
    mode: str = "exact"
    bbox: list[float] | None = None
    page: int | None = None
    formula_id: str | None = None
    table_id: str | None = None
    figure_id: str | None = None


class EvidenceChunk(BaseModel):
    """Source text chunk grounding an entity or theoretical atom.

    Parameters
    ----------
    chunk_id : str
        Identifier of the L1 source chunk.
    document_id : str or None, optional
        Identifier of the parent document.
    text : str
        Raw textual content of the chunk.
    spans : list of EvidenceSpan, optional
        Highlighted character spans within the chunk text.
    """

    chunk_id: str
    document_id: str | None = None
    text: str
    spans: list[EvidenceSpan] = Field(default_factory=list)


class EvidenceTrail(BaseModel):
    """Complete provenance trail tracing a graph node back to source chunks and multimodal anchors.

    Parameters
    ----------
    node_id : str
        Identifier of the graph node being inspected.
    layer : int
        Graph layer (1, 2, or 3).
    chunks : list of EvidenceChunk, optional
        Grounding source chunks with highlighted spans.
    anchors : list of TextAnchor, optional
        Explicit multimodal anchors (text, bbox, formula, table).
    """

    node_id: str
    layer: int
    chunks: list[EvidenceChunk] = Field(default_factory=list)
    anchors: list[TextAnchor] = Field(default_factory=list)


class StartRunRequest(BaseModel):
    """Payload to initiate a pipeline run.

    Parameters
    ----------
    profile_id : str or None, optional
        Preconfigured configuration profile name.
    patch : dict of str to Any, optional
        Dotted configuration override paths and values.
    source_paths : list of str, optional
        Input document paths to process.
    bib_paths : list of str, optional
        Optional file paths to bibliography references (.bib), by default empty list.
    metadata : dict of str to str, optional
        Arbitrary execution metadata strings, by default empty dict.
    structural_anchor : GlobalStructuralAnchor or None, optional
        Global structural anchor coordinate system (ToC outline, document summary, and/or
        global thesis) for the target document or pipeline run, by default None.
    demo_mode : bool, default False
        Whether to execute in lightweight demo mode.
    run_id : str or None, optional
        Explicit run identifier to align pipeline run and observability session.
    """

    profile_id: str | None = None
    patch: dict[str, Any] = Field(default_factory=dict)
    source_paths: list[str] = Field(default_factory=list)
    bib_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    structural_anchor: GlobalStructuralAnchor | None = None
    demo_mode: bool = False
    run_id: str | None = None
    parent_run_id: str | None = None

