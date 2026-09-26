from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class GlobalStructuralAnchor(BaseModel):
    """
    Static global structural coordinate system anchor for LLM prompts.

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

    def to_prompt_context(self) -> str:
        """
        Format structural anchor coordinates as textual prompt context.

        Returns
        -------
        str
            Formatted prompt context block.
        """
        lines = []
        if isinstance(self.toc_structure, list):
            toc_str = "\n".join(f"- {item}" for item in self.toc_structure if item)
        else:
            toc_str = str(self.toc_structure).strip()

        if toc_str:
            lines.append(f"Global Table of Contents / Outline:\n{toc_str}")

        if self.document_summary:
            lines.append(f"\nDocument Overview:\n{self.document_summary}")
        if self.global_thesis:
            lines.append(f"\nGlobal Thesis / Scope:\n{self.global_thesis}")

        return "\n".join(lines).strip()




class TextAnchor(BaseModel):
    """Multi-modal source evidence anchor supporting text, formulas, tables, and figures.

    Parameters
    ----------
    source_doc_id : str or None, optional
        Document identifier.
    char_start : int or None, optional
        0-indexed character start offset.
    char_end : int or None, optional
        0-indexed character end offset.
    verbatim_quote : str or None, optional
        Verbatim textual quote.
    bbox : list of float or None, optional
        Bounding box region [x0, y0, x1, y1] or [x0, y0, x1, y1, page].
    page : int or None, optional
        Document page number.
    formula_id : str or None, optional
        Unique formula identifier.
    table_id : str or None, optional
        Unique table identifier.
    figure_id : str or None, optional
        Unique figure identifier.
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


class L1Chunk(BaseModel):
    id: str
    text: str
    source_doc_id: str
    chapter_id: str | None = None
    sequence_index: int
    token_count: int
    embedding: list[float] | None = None
    text_anchor: TextAnchor | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class L1Document(BaseModel):
    id: str
    title: str
    source_path: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chapter_count: int
    chunk_count: int
    structural_anchor: GlobalStructuralAnchor | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class L2Entity(BaseModel):
    """Layer 2 (global/logical) entity representation.

    Attributes
    ----------
    id : str
        The unique identifier for the entity (typically a UUID or stable hash).
    label : str
        The entity category or class label (e.g., 'CONCEPT', 'PERSON', 'WORK').
    name : str
        The canonical name of the entity.
    description : str, optional
        A synthesized textual description of what the entity represents.
    textual_envelope : str, optional
        The original text context where this entity was first discovered.
    is_mature : bool, default False
        Flag indicating if the entity's description has gone through the Stage 2
        maturation protocol. If True, the description is stable, centroid-fused,
        and protected against further epistemic drift.
    source_chunk_ids : list of str, default []
        Identifiers of all the source chunks where this entity has been mentioned.
    """
    id: str
    label: str
    name: str
    description: str | None = None
    textual_envelope: str | None = None
    is_mature: bool = False
    confidence: float | None = None
    text_anchor: TextAnchor | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)


class L2Triple(BaseModel):
    subject_id: str
    predicate: str
    object_id: str
    confidence: float = Field(
        description="Heterogeneous metric: could be LLM probability, reranker tau, or hardcoded 1.0."
    )
    rerank_score: float | None = None
    scope: Literal["local", "global"]
    source_chunk_id: str | None = None


class Measurement(BaseModel):
    """Represents an empirical observation measurement dimension and value.

    Parameters
    ----------
    dimension : str
        The empirical measurement dimension (e.g., 'blood_flow', 'repetition_count').
    value : float | str
        The observed scalar or categorical value.
    unit : str | None, optional
        Measurement unit (e.g., 'Hz', 'ml/min'), by default None.
    """

    dimension: str
    value: float | str
    unit: str | None = None


class TheoreticalParameter(BaseModel):
    """Represents a theoretical parameter postulated by a theory-element.

    Parameters
    ----------
    name : str
        Parameter name (e.g., 'DopamineDepletion', 'RepressionMagnitude').
    value : float | str
        Calculated or estimated parameter value.
    theory_id : str | None, optional
        Identifier of the theory-element postulating the parameter, by default None.
    unit : str | None, optional
        Unit of the theoretical parameter, by default None.
    """

    name: str
    value: float | str
    theory_id: str | None = None
    unit: str | None = None


class TenabilityResult(BaseModel):
    """Tenability evaluation result for a theory application or hypothesis.

    Parameters
    ----------
    local_score : float
        Local tenability score (TS_local in [0, 1]).
    edge_scores : dict[str, float]
        Constraint/intertheoretical link tenability scores (TS_edge in [0, 1]).
    aggregated_score : float
        Combined tenability score for the theory-element.
    is_tenable : bool
        True if aggregated tenability is greater than or equal to threshold (default 0.5).
    tightest_blur : float
        Tightest admissible blur (delta) reconciling observations with theory laws.
    anomalies : list[str]
        Descriptions of any severe law violations or constraint tensions detected.
    """

    local_score: float
    edge_scores: dict[str, float] = Field(default_factory=dict)
    aggregated_score: float
    is_tenable: bool
    tightest_blur: float
    anomalies: list[str] = Field(default_factory=list)


class TheoryAtom(BaseModel):
    id: str
    text: str
    component_type: str
    source_chunk_id: str
    confidence: float | None = None
    plausibility: float | None = None
    entity_ids: list[str] = Field(default_factory=list)
    epistemic_status: str | None = None
    scope_type: str | None = None
    text_anchor: TextAnchor | None = None
    measurements: list[Measurement] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tenability: TenabilityResult | None = None


class TheoryRelation(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    confidence: float
    scope: Literal["local", "global"]
    weight: float | None = None
    tenability: float | None = None


class SubGraph(BaseModel):
    """Depth-limited neighborhood returned by graph read operations.

    This model is the pipeline-level transport object for structural context.
    It intentionally does not expose backend-specific graph handles or third-
    party graph objects. Consumers should treat it as a compact, serializable
    snapshot of a local property-graph neighborhood.

    Parameters
    ----------
    center_id
        Identifier of the node around which the neighborhood was requested.
        The center node itself is referenced here and is not required to appear
        in ``nodes``.
    nodes
        Neighbor nodes materialized for the neighborhood. Implementations
        should return the reachable context nodes needed by downstream phases.
        Ordering is not semantically significant.
    triples
        Directed relations contained in the neighborhood snapshot. These are
        graph edges represented in the pipeline's canonical ``L2Triple`` shape
        so downstream components can inspect structure without depending on the
        persistence backend.
    depth
        Maximum traversal depth that was requested to construct the
        neighborhood.
    """
    center_id: str
    nodes: list[L2Entity]
    triples: list[L2Triple]
    depth: int


class SearchResult(BaseModel):
    node_id: str
    score: float
    node_label: str
    node_name: str


class TheoryNet(BaseModel):
    atoms: list[TheoryAtom]
    relations: list[TheoryRelation]


class PhaseItemRecord(BaseModel):
    """Execution checkpoint item tracking within a pipeline phase.

    Parameters
    ----------
    key : str
        Unique order-invariant item identifier.
    status : Literal["completed", "failed"], default "completed"
        Processing status of the item.
    error : str | None, optional
        Error summary if status is failed, by default None.
    """

    key: str
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None


class CandidatePair(BaseModel):
    """Candidate entity pair for global relation evaluation.

    Parameters
    ----------
    entity_a : L2Entity
        First candidate entity.
    entity_b : L2Entity
        Second candidate entity.
    dense_score : float | None, optional
        Bi-encoder dense cosine similarity score if computed, by default None.
    score : float | None, optional
        Alias for dense_score, by default None.
    """

    entity_a: L2Entity
    entity_b: L2Entity
    dense_score: float | None = None
    score: float | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.score is not None and self.dense_score is None:
            object.__setattr__(self, "dense_score", self.score)
        elif self.dense_score is not None and self.score is None:
            object.__setattr__(self, "score", self.dense_score)

    def __iter__(self):
        """Allow unpacking as (entity_a, entity_b)."""
        yield self.entity_a
        yield self.entity_b

    def __getitem__(self, item: int) -> L2Entity:
        """Allow positional indexing for tuple compatibility."""
        if item == 0:
            return self.entity_a
        elif item == 1:
            return self.entity_b
        raise IndexError("CandidatePair index out of range")

    @property
    def key(self) -> str:
        """Deterministic order-invariant pair key including entity content fingerprints.

        Returns
        -------
        str
            Canonical pair key.
        """
        from episteme_pipeline.runs.fingerprints import stable_fingerprint

        h_a = stable_fingerprint(self.entity_a.textual_envelope or self.entity_a.name)[:8]
        h_b = stable_fingerprint(self.entity_b.textual_envelope or self.entity_b.name)[:8]
        if self.entity_a.id <= self.entity_b.id:
            return f"{self.entity_a.id}::{self.entity_b.id}::{h_a}::{h_b}"
        return f"{self.entity_b.id}::{self.entity_a.id}::{h_b}::{h_a}"
