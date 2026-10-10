from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from episteme_pipeline.runs.models import RunManifest, RunReport

from episteme_pipeline.contracts.domain import (
    GlobalStructuralAnchor,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
    TheoryNet,
    SearchResult,
    SubGraph,
)
class PipelineInput(BaseModel):
    """
    Entry point for the full pipeline.

    Parameters
    ----------
    source_paths : list[str]
        File paths to the source documents to ingest and process.
    bib_paths : list[str | Path], optional
        Optional file paths to bibliography references (.bib), by default empty list.
    metadata : dict[str, str], optional
        Arbitrary execution metadata strings, by default empty dict.
    structural_anchor : GlobalStructuralAnchor | None, optional
        Global structural anchor coordinate system (ToC outline, document summary, and/or
        global thesis) for the target document or pipeline run, by default None.
    """

    source_paths: list[str]
    bib_paths: list[str | Path] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    structural_anchor: GlobalStructuralAnchor | None = None


class Phase1Output(BaseModel):
    documents: list[L1Document] = Field(default_factory=list)
    chunks: list[L1Chunk] = Field(default_factory=list)


class Phase2Output(BaseModel):
    entities: list[L2Entity] = Field(default_factory=list)
    local_triples: list[L2Triple] = Field(default_factory=list)


class Phase3Output(BaseModel):
    global_triples: list[L2Triple] = Field(default_factory=list)


class Phase4Output(BaseModel):
    theory_atoms: list[TheoryAtom] = Field(default_factory=list)
    theory_relations: list[TheoryRelation] = Field(default_factory=list)
    argument_relations: list[TheoryRelation] | None = None
    theory_net: TheoryNet | None = None
    qbaf: Any = None

    def model_post_init(self, __context: Any) -> None:
        if self.argument_relations and not self.theory_relations:
            object.__setattr__(self, "theory_relations", self.argument_relations)
        elif self.theory_relations and not self.argument_relations:
            object.__setattr__(self, "argument_relations", self.theory_relations)


class Phase5Output(BaseModel):
    pass


class PipelineResult(BaseModel):
    """Result envelope for running (part of) the pipeline."""
    # Use explicit models to ensure required fields (e.g., run_id) exist.
    manifest: "RunManifest | None" = None
    artifacts: list[object] = Field(default_factory=list)
    report: "RunReport | None" = None


__all__ = [
    "L1Chunk",
    "L1Document",
    "L2Entity",
    "L2Triple",
    "TheoryAtom",
    "TheoryRelation",
    "TheoryNet",
    "SearchResult",
    "SubGraph",
    "PipelineInput",
    "Phase1Output",
    "Phase2Output",
    "Phase3Output",
    "Phase4Output",
    "Phase5Output",
    "PipelineResult",
]
