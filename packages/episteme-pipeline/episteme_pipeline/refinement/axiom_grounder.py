"""Localized axiom grounding and observation recovery handler (ISSUE-053).

Implements :class:`TheoryGuidedAxiomGrounder`, satisfying
:class:`~episteme_pipeline.protocols.refinement.LocalizedAxiomGrounder` and
:class:`~episteme_pipeline.protocols.fingerprint.Fingerprintable`.

Expands ``deficit.target_chunk_ids`` strictly locally to immediate document
neighbors (``sequence_index ± neighbor_window`` within the same ``source_doc_id``)
and optional bounded vector search over :class:`ArtifactSubgraphReader`, without
ever re-chunking the corpus or touching unrelated documents/subgraphs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, ValidationError, field_validator

from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    L2Triple,
    Measurement,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import ComponentCompleted, ComponentStarted
from episteme_pipeline.llm.structured import StructuredLLM, ensure_structured_llm
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    EmpiricalCluster,
    TheoryElementDefinition,
    TheoryLaw,
)
from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
    GenericTheoryProjector,
    TheoryProjector,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.extractors import EmbeddingModel, NERExtractor
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.prompts import PromptContextual
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactExecutionContext,
        EpistemicStateView,
    )

logger = logging.getLogger(__name__)


DEFAULT_AXIOM_GROUNDING_PROMPT = """\
You are an expert in empirical epistemology, scientific measurement extraction, and structuralist metatheory.
A theoretical hypothesis or axiom lacks sufficient empirical grounding (an UNGROUNDED_AXIOM deficit).
Inspect ONLY the provided targeted and immediate neighbor source chunks conditioned on the macro-theory
lens to extract missed empirical observation units, quantitative measurements, and grounding entities.

### Theory Lens (M_pp / M_p / M)
Theory ID: {theory_id}
Required Empirical Dimensions (M_pp): {required_dimensions}
Postulated Theoretical Parameters (M_p): {parameter_names}
Theory Lens Details: {theory_lens}
Deficit Rationale: {rationale}

### Target Ungrounded Axiom(s) / Hypothesis(es)
{target_atoms}

### Allowed Component Types
{component_types}

### Allowed Argument Relation Types
{argument_relation_types}

### Scoped Source Chunks
{source_chunks}

### Instructions
1. Extract concrete ``ObservationUnit`` or ``EmpiricalStatement`` propositions from the provided
   chunks: [{allowed_chunk_ids}].
2. Attach explicit ``measurements`` (``dimension``, ``value``, optional ``unit``) aligning with
   the required empirical dimensions where present.
3. Ground each observation in its exact ``source_chunk_id`` from [{allowed_chunk_ids}] and link
   it to the target atom via ``target_atom_id`` and ``relation_type`` (typically ``SUPPORTS_ARG``).
4. Optionally extract any missed domain entities within those chunks.
5. Output strictly valid JSON matching the schema.
"""


@runtime_checkable
class _StructuredPredictPort(Protocol):
    """Minimal structural port for objects exposing ``predict_structured``."""

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        """Predict a structured Pydantic output."""
        ...


class _TheoryLensAnchor:
    """``PromptContextual`` adapter rendering ``deficit.theory_lens`` for NER."""

    def __init__(
        self,
        *,
        theory_id: str | None,
        theory_lens: dict[str, Any],
        rationale: str,
        target_atom_texts: list[str],
    ) -> None:
        self.theory_id = theory_id
        self.theory_lens = theory_lens
        self.rationale = rationale
        self.target_atom_texts = target_atom_texts

    def to_prompt_context(self) -> str:
        """Format the theory lens context as a structured prompt anchor string.

        Returns
        -------
        str
            Prompt context guiding localized NER re-extraction.
        """
        lines = [f"Theory Lens ({self.theory_id or 'unspecified'}):"]
        req_dims = self.theory_lens.get("required_dimensions")
        if req_dims:
            lines.append(f"- Required empirical dimensions (M_pp): {req_dims}")
        params = self.theory_lens.get("parameter_names")
        if params:
            lines.append(f"- Theoretical parameters (M_p): {params}")
        laws = self.theory_lens.get("laws")
        if laws:
            lines.append(f"- Theory laws (M): {laws}")
        if self.target_atom_texts:
            lines.append(
                "- Target ungrounded claim(s): " + "; ".join(self.target_atom_texts)
            )
        if self.rationale:
            lines.append(f"- Deficit rationale: {self.rationale}")
        return "\n".join(lines)


assert isinstance(
    _TheoryLensAnchor(
        theory_id=None, theory_lens={}, rationale="", target_atom_texts=[]
    ),
    PromptContextual,
)


class RecoveredMeasurement(BaseModel):
    """Structured empirical measurement recovered during axiom grounding.

    Attributes
    ----------
    dimension : str
        Empirical observation dimension name.
    value : float or str
        Observed quantitative or categorical value.
    unit : str or None, optional
        Optional physical or observational unit.
    """

    dimension: str
    value: float | str
    unit: str | None = None


class RecoveredGroundingEntity(BaseModel):
    """Optional L2 entity recovered during LLM-guided axiom grounding.

    Attributes
    ----------
    name : str
        Canonical entity name.
    label : str, default "Concept"
        Entity type validated against ``SchemaConfig.node_types``.
    description : str or None, optional
        Contextual entity description.
    source_chunk_id : str, default ""
        Originating chunk identifier.
    confidence : float, default 0.85
        Extraction confidence in ``[0.0, 1.0]``.
    """

    name: str
    label: str = "Concept"
    description: str | None = None
    source_chunk_id: str = ""
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class RecoveredObservationAtom(BaseModel):
    """Structured LLM output for a single grounding observation atom.

    Attributes
    ----------
    local_id : str, default "OBS1"
        Local identifier within the response.
    text : str
        Empirical observation or statement text.
    component_type : str, default "ObservationUnit"
        Component type (typically ``ObservationUnit`` or ``EmpiricalStatement``).
    source_chunk_id : str, default ""
        Chunk identifier grounding this observation.
    target_atom_id : str, default ""
        Target ungrounded atom identifier receiving support.
    relation_type : str, default "SUPPORTS_ARG"
        Grounding relation type toward ``target_atom_id``.
    confidence : float, default 0.85
        Extraction confidence in ``[0.0, 1.0]``.
    measurements : list of RecoveredMeasurement, optional
        Empirical measurements attached to this observation.
    entity_ids : list of str, optional
        Scoped L2 entity IDs referenced by this observation.
    """

    local_id: str = "OBS1"
    text: str
    component_type: str = "ObservationUnit"
    source_chunk_id: str = ""
    target_atom_id: str = ""
    relation_type: str = "SUPPORTS_ARG"
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    measurements: list[RecoveredMeasurement] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Recovered observation text must not be empty.")
        return cleaned

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.85


class AxiomGroundingOutput(BaseModel):
    """Structured LLM response envelope for localized axiom grounding.

    Attributes
    ----------
    observations : list of RecoveredObservationAtom, optional
        Recovered empirical observation atoms and measurements.
    entities : list of RecoveredGroundingEntity, optional
        Optional newly recovered L2 entities in the targeted chunks.
    """

    observations: list[RecoveredObservationAtom] = Field(default_factory=list)
    entities: list[RecoveredGroundingEntity] = Field(default_factory=list)


def _normalize_structured_llm(llm: Any | None) -> StructuredLLM | _StructuredPredictPort | None:
    """Normalize an optional LLM backend to a structured prediction port."""
    if llm is None:
        return None
    if isinstance(llm, _StructuredPredictPort):
        return llm
    return ensure_structured_llm(llm, use_cache=False)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two equal-length float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _stable_grounding_atom_id(
    deficit_id: str,
    chunk_id: str,
    local_id: str,
    text: str,
) -> str:
    """Compute a deterministic identifier for a grounded observation atom."""
    payload = f"{deficit_id}:{chunk_id}:{local_id}:{text.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:14]
    return f"ac_ground_{digest}"


def _stable_entity_id(label: str, name: str) -> str:
    """Compute a deterministic identifier for a recovered L2 entity."""
    key = f"{label.upper()}::{name.strip().lower()}"
    return f"entity_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:14]}"


class TheoryGuidedAxiomGrounder:
    """Localized observation and parameter grounder for ``UNGROUNDED_AXIOM`` deficits.

    Expands ``deficit.target_chunk_ids`` strictly locally via immediate same-document
    neighbors (``sequence_index ± neighbor_window``) and bounded vector similarity
    search when chunk embeddings exist, then extracts missing empirical observations,
    quantitative measurements, L2 entities/triples, and parameter projections
    conditioned on ``deficit.theory_lens``.

    Parameters
    ----------
    ner_extractor : NERExtractor or None, optional
        Optional Phase 2 NER extractor invoked with a ``PromptContextual``
        theory-lens anchor on the expanded local chunks.
    llm : StructuredLLM or Any or None, optional
        Optional structured LLM used to recover empirical observations and
        measurements.
    theory_projector : TheoryProjector or None, optional
        Optional structuralist theory projector projecting recovered observations
        into theoretical parameters ``M_p``. Defaults to :class:`GenericTheoryProjector`.
    embedding_model : EmbeddingModel or None, optional
        Optional bi-encoder used to embed the theory-lens query for bounded
        chunk vector search when seed chunks lack precomputed embeddings.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.
    neighbor_window : int, default 1
        Maximum ``sequence_index`` offset within the same ``source_doc_id`` for
        localized neighbor chunk expansion.
    vector_top_k : int, default 3
        Maximum candidate chunks retrieved by bounded ``vector_search`` when
        chunk embeddings are available.
    prompts : StructuredPromptBundle or str or None, optional
        Optional custom prompt bundle for LLM-assisted grounding.
    strategy : Any, default "direct_constrained"
        Structured decoding strategy passed to ``llm.predict_structured``.
    confidence_threshold : float, default 0.5
        Minimum confidence required to retain an LLM-recovered observation atom.
    """

    def __init__(
        self,
        ner_extractor: NERExtractor | None = None,
        llm: StructuredLLM | Any | None = None,
        theory_projector: TheoryProjector | None = None,
        *,
        embedding_model: EmbeddingModel | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
        neighbor_window: int = 1,
        vector_top_k: int = 3,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = "direct_constrained",
        confidence_threshold: float = 0.5,
    ) -> None:
        self.ner_extractor = ner_extractor
        self.llm = _normalize_structured_llm(llm)
        self.theory_projector: TheoryProjector = (
            theory_projector if theory_projector is not None else GenericTheoryProjector()
        )
        self.embedding_model = embedding_model
        self.schema = schema
        self.neighbor_window = max(0, neighbor_window)
        self.vector_top_k = max(0, vector_top_k)
        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        else:
            self.prompts = StructuredPromptBundle(
                direct_template=prompts or DEFAULT_AXIOM_GROUNDING_PROMPT,
                name="refinement_axiom_grounding",
            )
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache lineage.

        Returns
        -------
        dict of str to Any
            JSON-serializable dictionary capturing window parameters, schema version,
            and sub-component fingerprints.
        """
        strategy_str = (
            self.strategy.value if isinstance(self.strategy, Enum) else str(self.strategy)
        )
        return {
            "class": self.__class__.__name__,
            "schema_version": self.schema.version,
            "neighbor_window": self.neighbor_window,
            "vector_top_k": self.vector_top_k,
            "strategy": strategy_str,
            "confidence_threshold": self.confidence_threshold,
            "prompts": self.prompts.fingerprint(),
            "ner_extractor": (
                self.ner_extractor.fingerprint()
                if isinstance(self.ner_extractor, Fingerprintable)
                else fingerprint_method(self.ner_extractor)
            ),
            "llm": (
                self.llm.fingerprint()
                if isinstance(self.llm, Fingerprintable)
                else fingerprint_method(self.llm)
            ),
            "theory_projector": (
                self.theory_projector.fingerprint()
                if isinstance(self.theory_projector, Fingerprintable)
                else fingerprint_method(self.theory_projector)
            ),
            "embedding_model": (
                self.embedding_model.fingerprint()
                if isinstance(self.embedding_model, Fingerprintable)
                else fingerprint_method(self.embedding_model)
            ),
        }

    def _resolve_observation_type(self, candidate: str) -> str:
        """Resolve an observation component type against the configured schema."""
        if candidate in self.schema.component_types:
            return candidate
        if "ObservationUnit" in self.schema.component_types:
            return "ObservationUnit"
        if "EmpiricalStatement" in self.schema.component_types:
            return "EmpiricalStatement"
        return self.schema.component_types[0]

    def _resolve_support_relation_type(self, candidate: str) -> str:
        """Resolve a grounding support relation type against the configured schema."""
        resolved = self.schema.resolve_relation_type(candidate)
        if resolved is not None:
            return resolved
        fallback = self.schema.resolve_relation_type("SUPPORTS_ARG")
        if fallback is not None:
            return fallback
        support_rels = self.schema.get_support_relations()
        if support_rels:
            return support_rels[0]
        return self.schema.argument_relation_types[0]

    async def _expand_local_chunks(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        target_atoms: list[TheoryAtom],
    ) -> list[L1Chunk]:
        """Expand target chunks strictly to document-window neighbors & vector hits."""
        chunks_by_id: dict[str, L1Chunk] = {c.id: c for c in state.chunks}
        if deficit.target_chunk_ids:
            seed_ids = list(dict.fromkeys(deficit.target_chunk_ids))
        else:
            seed_ids = list(
                dict.fromkeys(
                    a.source_chunk_id for a in target_atoms if a.source_chunk_id
                )
            )

        expanded: dict[str, L1Chunk] = {}
        seed_chunks: list[L1Chunk] = []
        for cid in seed_ids:
            chunk = chunks_by_id.get(cid)
            if chunk is not None:
                expanded[chunk.id] = chunk
                seed_chunks.append(chunk)

        if not seed_chunks:
            return []

        # 1. Immediate document neighbor window (sequence_index +/- neighbor_window)
        if self.neighbor_window > 0:
            for seed in seed_chunks:
                for cand in state.chunks:
                    if (
                        cand.source_doc_id == seed.source_doc_id
                        and abs(cand.sequence_index - seed.sequence_index)
                        <= self.neighbor_window
                    ):
                        expanded[cand.id] = cand

        # 2. Bounded vector search when chunk embeddings exist
        embedded_chunks = [c for c in state.chunks if c.embedding]
        if self.vector_top_k > 0 and embedded_chunks:
            query_embedding: list[float] | None = None
            seed_embs = [c.embedding for c in seed_chunks if c.embedding]
            if seed_embs:
                dim = len(seed_embs[0])
                aligned = [vec for vec in seed_embs if len(vec) == dim]
                if aligned:
                    query_embedding = [
                        sum(vec[idx] for vec in aligned) / len(aligned)
                        for idx in range(dim)
                    ]
            elif self.embedding_model is not None:
                req_dims = [
                    str(d) for d in deficit.theory_lens.get("required_dimensions", [])
                ]
                query_parts = [a.text for a in target_atoms] + req_dims
                query_text = " ".join(p for p in query_parts if p).strip()
                if query_text:
                    query_embedding = await self.embedding_model.aget_text_embedding(
                        query_text
                    )

            if query_embedding:
                reader = ArtifactSubgraphReader.from_view(state)
                try:
                    results = await reader.vector_search(
                        query_embedding,
                        top_k=self.vector_top_k,
                        node_label="Chunk",
                    )
                    scored_hits = [(r.node_id, float(r.score)) for r in results]
                except ValidationError:
                    scored_hits = sorted(
                        (
                            (
                                c.id,
                                _cosine_similarity(query_embedding, c.embedding or []),
                            )
                            for c in embedded_chunks
                        ),
                        key=lambda item: item[1],
                        reverse=True,
                    )[: self.vector_top_k]

                for chunk_id, score in scored_hits:
                    if score > 0.25 and chunk_id in chunks_by_id:
                        expanded[chunk_id] = chunks_by_id[chunk_id]

        return sorted(
            expanded.values(),
            key=lambda c: (c.source_doc_id, c.sequence_index, c.id),
        )

    def _build_theory_definition(
        self,
        deficit: EpistemicDeficit,
        target_atoms: list[TheoryAtom],
    ) -> TheoryElementDefinition:
        """Construct a ``TheoryElementDefinition`` from ``deficit.theory_lens``."""
        lens = deficit.theory_lens
        theory_id = deficit.theory_id or str(lens.get("theory_id", "refined_theory"))
        theory_name = str(lens.get("name", theory_id))

        raw_req_dims = lens.get("required_dimensions", [])
        required_dimensions = (
            [str(d) for d in raw_req_dims] if isinstance(raw_req_dims, list) else []
        )
        raw_params = lens.get("parameter_names", [])
        parameter_names = (
            [str(p) for p in raw_params] if isinstance(raw_params, list) else []
        )

        laws: list[TheoryLaw] = []
        raw_laws = lens.get("laws", [])
        if isinstance(raw_laws, list):
            for idx, item in enumerate(raw_laws, start=1):
                if isinstance(item, TheoryLaw):
                    laws.append(item)
                elif isinstance(item, dict):
                    laws.append(
                        TheoryLaw(
                            law_id=str(item.get("law_id", f"law_{idx}")),
                            description=str(item.get("description", "")),
                            formula_expression=str(
                                item.get("formula_expression", "")
                            ),
                            involved_parameters=[
                                str(p)
                                for p in item.get("involved_parameters", [])
                                if p
                            ],
                        )
                    )
                elif isinstance(item, str) and item.strip():
                    laws.append(TheoryLaw(law_id=f"law_{idx}", description=item.strip()))

        raw_blur = lens.get("max_admissible_blur", 1.0)
        try:
            max_blur = float(raw_blur)
        except (TypeError, ValueError):
            max_blur = 1.0

        return TheoryElementDefinition(
            theory_id=theory_id,
            name=theory_name,
            required_dimensions=required_dimensions,
            parameter_names=parameter_names,
            laws=laws,
            max_admissible_blur=max_blur,
            claimant_hypothesis_ids=[a.id for a in target_atoms],
        )

    def _extract_deterministic_observations(
        self,
        deficit: EpistemicDeficit,
        expanded_chunks: list[L1Chunk],
        theory_def: TheoryElementDefinition,
        existing_atoms: list[TheoryAtom],
        target_atoms: list[TheoryAtom],
        recovered_entities: list[L2Entity],
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        """Extract deterministic measurements & observation atoms when LLM is absent."""
        atoms: list[TheoryAtom] = []
        relations: list[TheoryRelation] = []
        expanded_chunk_ids = {c.id for c in expanded_chunks}
        primary_target = target_atoms[0] if target_atoms else None

        obs_types = {"ObservationUnit", "EmpiricalStatement"}
        existing_obs_in_scope = [
            a
            for a in existing_atoms
            if a.source_chunk_id in expanded_chunk_ids
            and (
                a.component_type in obs_types
                or self.schema.component_partitions.get(a.component_type) == "B"
            )
            and (primary_target is None or a.id != primary_target.id)
        ]

        # Extract quantitative dimension mentions from expanded chunks
        dim_candidates = list(
            dict.fromkeys(
                [*theory_def.required_dimensions, *theory_def.parameter_names]
            )
        )
        for chunk in expanded_chunks:
            chunk_measurements: list[Measurement] = []
            low_text = chunk.text.lower()
            for dim in dim_candidates:
                dim_clean = dim.strip().lower()
                if not dim_clean:
                    continue
                tokens = [
                    re.escape(tok)
                    for tok in re.split(r"[_\s]+", dim_clean)
                    if tok
                ]
                dim_pattern = r"[\s_-]*".join(tokens)
                match = re.search(
                    rf"\b{dim_pattern}\b\s*(?:=|:|of|at|is)?\s*(-?\d+(?:\.\d+)?)\s*([a-zA-Z%/]+)?",
                    low_text,
                )
                if match:
                    val = float(match.group(1))
                    unit = match.group(2)
                    chunk_measurements.append(
                        Measurement(dimension=dim, value=val, unit=unit)
                    )
                elif dim_clean.replace("_", " ") in low_text or dim_clean in low_text:
                    chunk_measurements.append(
                        Measurement(dimension=dim, value=1.0)
                    )

            if chunk_measurements:
                obs_id = _stable_grounding_atom_id(
                    deficit.deficit_id, chunk.id, "DET", chunk.text[:80]
                )
                ent_ids = [
                    ent.id
                    for ent in recovered_entities
                    if chunk.id in ent.source_chunk_ids
                ]
                obs_atom = TheoryAtom(
                    id=obs_id,
                    text=chunk.text.strip(),
                    component_type=self._resolve_observation_type("ObservationUnit"),
                    source_chunk_id=chunk.id,
                    confidence=0.80,
                    entity_ids=ent_ids,
                    measurements=chunk_measurements,
                )
                atoms.append(obs_atom)
                if primary_target is not None:
                    rel_scope = (
                        "local"
                        if obs_atom.source_chunk_id == primary_target.source_chunk_id
                        else "global"
                    )
                    relations.append(
                        TheoryRelation(
                            source_id=obs_atom.id,
                            target_id=primary_target.id,
                            relation_type=self._resolve_support_relation_type(
                                "SUPPORTS_ARG"
                            ),
                            confidence=0.80,
                            scope=rel_scope,
                            weight=0.80,
                        )
                    )

        if not atoms and existing_obs_in_scope and primary_target is not None:
            for obs in existing_obs_in_scope:
                rel_scope = (
                    "local"
                    if obs.source_chunk_id == primary_target.source_chunk_id
                    else "global"
                )
                relations.append(
                    TheoryRelation(
                        source_id=obs.id,
                        target_id=primary_target.id,
                        relation_type=self._resolve_support_relation_type(
                            "SUPPORTS_ARG"
                        ),
                        confidence=obs.confidence or 0.75,
                        scope=rel_scope,
                        weight=obs.confidence or 0.75,
                    )
                )

        return atoms, relations

    async def ground_axiom(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Perform localized observation and parameter recovery for ``UNGROUNDED_AXIOM``.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``UNGROUNDED_AXIOM`` deficit naming target chunks, target atoms,
            and conditioning ``theory_lens`` schema.
        state : EpistemicStateView
            Cumulative epistemic state view providing chunks, entities, and atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for event lineage.

        Returns
        -------
        RefinementDelta
            Delta containing recovered entities, local triples, observation atoms
            with empirical measurements/parameters, and grounding support relations.

        Raises
        ------
        ValueError
            If ``deficit.deficit_kind`` is not ``UNGROUNDED_AXIOM``.
        """
        if deficit.deficit_kind != EpistemicDeficitKind.UNGROUNDED_AXIOM:
            raise ValueError(
                f"TheoryGuidedAxiomGrounder only handles UNGROUNDED_AXIOM deficits "
                f"(got {deficit.deficit_kind})."
            )

        run_id = context.run_id if context is not None else None
        next_pass = deficit.refinement_pass + 1
        emitter = get_event_emitter()
        comp_name = f"{self.__class__.__name__}:{deficit.deficit_id}"
        start_time = time.perf_counter()
        emitter.emit(
            ComponentStarted(
                run_id=run_id,
                phase="refinement",
                component_name=comp_name,
                input_description=(
                    f"chunks={len(deficit.target_chunk_ids)}, "
                    f"atoms={len(deficit.target_atom_ids)}"
                ),
            )
        )

        try:
            all_atoms = (
                state.canonical_theory_atoms
                if state.canonical_theory_atoms
                else state.theory_atoms
            )
            atoms_by_id: dict[str, TheoryAtom] = {a.id: a for a in all_atoms}
            target_atoms: list[TheoryAtom] = [
                atoms_by_id[aid] for aid in deficit.target_atom_ids if aid in atoms_by_id
            ]

            expanded_chunks = await self._expand_local_chunks(
                deficit, state, target_atoms
            )
            if not expanded_chunks:
                emitter.emit(
                    ComponentCompleted(
                        run_id=run_id,
                        phase="refinement",
                        component_name=comp_name,
                        duration_seconds=time.perf_counter() - start_time,
                        output_description="no_matching_target_chunks",
                        success=True,
                    )
                )
                return RefinementDelta(refinement_pass=next_pass)

            expanded_chunk_ids = {c.id for c in expanded_chunks}
            theory_def = self._build_theory_definition(deficit, target_atoms)
            lens_anchor = _TheoryLensAnchor(
                theory_id=theory_def.theory_id,
                theory_lens=deficit.theory_lens,
                rationale=deficit.rationale,
                target_atom_texts=[a.text for a in target_atoms],
            )

            recovered_entities_by_id: dict[str, L2Entity] = {}
            recovered_triples: list[L2Triple] = []
            seen_triple_keys: set[tuple[str, str, str, str, str | None]] = set()

            def _merge_entity(ent: L2Entity) -> None:
                existing = recovered_entities_by_id.get(ent.id)
                if existing is None:
                    recovered_entities_by_id[ent.id] = ent
                else:
                    merged_chunks = list(
                        dict.fromkeys([*existing.source_chunk_ids, *ent.source_chunk_ids])
                    )
                    recovered_entities_by_id[ent.id] = existing.model_copy(
                        update={
                            "source_chunk_ids": merged_chunks,
                            "description": existing.description or ent.description,
                            "textual_envelope": existing.textual_envelope
                            or ent.textual_envelope,
                        }
                    )

            # 1. Localized theory-anchored NER extraction across expanded chunks
            if self.ner_extractor is not None:
                for chunk in expanded_chunks:
                    ents, trips, _, _, _ = await self.ner_extractor.extract(
                        chunk.id,
                        chunk.text,
                        self.schema,
                        memory=None,
                        anchor=lens_anchor,
                    )
                    for ent in ents:
                        scoped_cids = [
                            cid
                            for cid in ent.source_chunk_ids
                            if cid in expanded_chunk_ids
                        ] or [chunk.id]
                        _merge_entity(ent.model_copy(update={"source_chunk_ids": scoped_cids}))
                    for triple in trips:
                        scoped_triple = (
                            triple
                            if triple.source_chunk_id in expanded_chunk_ids
                            else triple.model_copy(update={"source_chunk_id": chunk.id})
                        )
                        tkey = (
                            scoped_triple.subject_id,
                            scoped_triple.predicate,
                            scoped_triple.object_id,
                            scoped_triple.scope,
                            scoped_triple.source_chunk_id,
                        )
                        if tkey not in seen_triple_keys:
                            seen_triple_keys.add(tkey)
                            recovered_triples.append(scoped_triple)

            recovered_obs_atoms: list[TheoryAtom] = []
            recovered_relations: list[TheoryRelation] = []
            seen_rel_keys: set[tuple[str, str, str]] = set()

            # 2. Structured LLM observation/measurement extraction over expanded chunks
            if self.llm is not None:
                target_atoms_text = (
                    "\n".join(
                        f"- [{a.id}] ({a.component_type}, chunk={a.source_chunk_id}) {a.text}"
                        for a in target_atoms
                    )
                    or "None."
                )
                source_chunks_text = "\n\n".join(
                    f"[Chunk {c.id} (doc={c.source_doc_id}, seq={c.sequence_index})]\n{c.text}"
                    for c in expanded_chunks
                )
                raw_grounding: AxiomGroundingOutput = await self.llm.predict_structured(
                    AxiomGroundingOutput,
                    self.prompts,
                    strategy=self.strategy,
                    theory_id=theory_def.theory_id,
                    required_dimensions=", ".join(theory_def.required_dimensions)
                    or "None specified",
                    parameter_names=", ".join(theory_def.parameter_names)
                    or "None specified",
                    theory_lens=json.dumps(
                        deficit.theory_lens, sort_keys=True, ensure_ascii=False
                    ),
                    rationale=deficit.rationale or "Ungrounded axiom detected.",
                    target_atoms=target_atoms_text,
                    source_chunks=source_chunks_text,
                    allowed_chunk_ids=", ".join(c.id for c in expanded_chunks),
                    component_types=self.schema.component_types_str(),
                    argument_relation_types=self.schema.argument_relation_types_str(),
                )

                default_chunk_id = expanded_chunks[0].id
                valid_node_types = set(self.schema.node_types)
                fallback_label = (
                    "Concept"
                    if "Concept" in valid_node_types
                    else self.schema.node_types[0]
                )

                for raw_ent in raw_grounding.entities:
                    ent_label = (
                        raw_ent.label
                        if raw_ent.label in valid_node_types
                        else fallback_label
                    )
                    ent_cid = (
                        raw_ent.source_chunk_id
                        if raw_ent.source_chunk_id in expanded_chunk_ids
                        else default_chunk_id
                    )
                    _merge_entity(
                        L2Entity(
                            id=_stable_entity_id(ent_label, raw_ent.name),
                            label=ent_label,
                            name=raw_ent.name,
                            description=raw_ent.description,
                            confidence=raw_ent.confidence,
                            source_chunk_ids=[ent_cid],
                        )
                    )

                known_entity_ids = {e.id for e in state.entities} | set(
                    recovered_entities_by_id.keys()
                )
                scoped_entities = [
                    e
                    for e in [*state.entities, *recovered_entities_by_id.values()]
                    if any(cid in expanded_chunk_ids for cid in e.source_chunk_ids)
                ]

                for idx, obs in enumerate(raw_grounding.observations, start=1):
                    if obs.confidence < self.confidence_threshold:
                        continue
                    obs_cid = (
                        obs.source_chunk_id
                        if obs.source_chunk_id in expanded_chunk_ids
                        else default_chunk_id
                    )
                    obs_id = _stable_grounding_atom_id(
                        deficit.deficit_id,
                        obs_cid,
                        obs.local_id or f"OBS{idx}",
                        obs.text,
                    )
                    valid_eids = [
                        eid for eid in obs.entity_ids if eid in known_entity_ids
                    ]
                    if not valid_eids and scoped_entities:
                        low_obs = obs.text.lower()
                        valid_eids = list(
                            dict.fromkeys(
                                ent.id
                                for ent in scoped_entities
                                if ent.name.strip()
                                and ent.name.strip().lower() in low_obs
                            )
                        )

                    measurements = [
                        Measurement(
                            dimension=m.dimension,
                            value=m.value,
                            unit=m.unit,
                        )
                        for m in obs.measurements
                    ]
                    obs_atom = TheoryAtom(
                        id=obs_id,
                        text=obs.text,
                        component_type=self._resolve_observation_type(
                            obs.component_type
                        ),
                        source_chunk_id=obs_cid,
                        confidence=obs.confidence,
                        entity_ids=valid_eids,
                        measurements=measurements,
                    )
                    recovered_obs_atoms.append(obs_atom)

                    resolved_target: TheoryAtom | None = None
                    if obs.target_atom_id and obs.target_atom_id in atoms_by_id:
                        resolved_target = atoms_by_id[obs.target_atom_id]
                    elif target_atoms:
                        resolved_target = target_atoms[0]

                    if resolved_target is not None and resolved_target.id != obs_atom.id:
                        rel_type = self._resolve_support_relation_type(obs.relation_type)
                        rel_scope = (
                            "local"
                            if obs_atom.source_chunk_id == resolved_target.source_chunk_id
                            else "global"
                        )
                        rel = TheoryRelation(
                            source_id=obs_atom.id,
                            target_id=resolved_target.id,
                            relation_type=rel_type,
                            confidence=obs.confidence,
                            scope=rel_scope,
                            weight=obs.confidence,
                        )
                        rkey = (rel.source_id, rel.relation_type, rel.target_id)
                        if rkey not in seen_rel_keys:
                            seen_rel_keys.add(rkey)
                            recovered_relations.append(rel)
            else:
                det_atoms, det_rels = self._extract_deterministic_observations(
                    deficit,
                    expanded_chunks,
                    theory_def,
                    all_atoms,
                    target_atoms,
                    list(recovered_entities_by_id.values()),
                )
                recovered_obs_atoms.extend(det_atoms)
                for rel in det_rels:
                    rkey = (rel.source_id, rel.relation_type, rel.target_id)
                    if rkey not in seen_rel_keys:
                        seen_rel_keys.add(rkey)
                        recovered_relations.append(rel)

            # 3. Project recovered observations into theoretical parameters M_p
            emitted_atoms: list[TheoryAtom] = list(recovered_obs_atoms)
            cluster_obs = list(recovered_obs_atoms)
            if not cluster_obs:
                obs_types = {"ObservationUnit", "EmpiricalStatement"}
                cluster_obs = [
                    a
                    for a in all_atoms
                    if a.source_chunk_id in expanded_chunk_ids
                    and (
                        a.component_type in obs_types
                        or self.schema.component_partitions.get(a.component_type) == "B"
                    )
                ]

            if cluster_obs and (
                theory_def.parameter_names or theory_def.required_dimensions
            ):
                cluster = EmpiricalCluster(
                    cluster_id=f"grounding-{deficit.deficit_id}",
                    observations=cluster_obs,
                    claimant_theory_ids=[theory_def.theory_id],
                    relations=recovered_relations,
                )
                projected_params = await self.theory_projector.aproject(
                    cluster, theory_def
                )
                if projected_params:
                    updated_obs: list[TheoryAtom] = []
                    for atom in emitted_atoms:
                        merged_p = dict(atom.parameters)
                        merged_p.update(projected_params)
                        updated_obs.append(
                            atom.model_copy(update={"parameters": merged_p})
                        )
                    emitted_atoms = updated_obs

                    for tgt in target_atoms:
                        merged_tgt_p = dict(tgt.parameters)
                        merged_tgt_p.update(projected_params)
                        emitted_atoms.append(
                            tgt.model_copy(update={"parameters": merged_tgt_p})
                        )

            recovered_entities = list(recovered_entities_by_id.values())
            has_delta = bool(
                recovered_entities
                or recovered_triples
                or emitted_atoms
                or recovered_relations
            )
            resolved_ids = [deficit.deficit_id] if has_delta else []

            delta = RefinementDelta(
                entities=recovered_entities,
                local_triples=recovered_triples,
                theory_atoms=emitted_atoms,
                theory_relations=recovered_relations,
                resolved_deficit_ids=resolved_ids,
                refinement_pass=next_pass,
            )
            emitter.emit(
                ComponentCompleted(
                    run_id=run_id,
                    phase="refinement",
                    component_name=comp_name,
                    duration_seconds=time.perf_counter() - start_time,
                    output_description=(
                        f"entities={len(recovered_entities)}, "
                        f"triples={len(recovered_triples)}, "
                        f"atoms={len(emitted_atoms)}, "
                        f"relations={len(recovered_relations)}"
                    ),
                    success=True,
                )
            )
            return delta
        except Exception as exc:
            emitter.emit(
                ComponentCompleted(
                    run_id=run_id,
                    phase="refinement",
                    component_name=comp_name,
                    duration_seconds=time.perf_counter() - start_time,
                    output_description="failed",
                    success=False,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            )
            raise


__all__ = [
    "AxiomGroundingOutput",
    "DEFAULT_AXIOM_GROUNDING_PROMPT",
    "RecoveredGroundingEntity",
    "RecoveredMeasurement",
    "RecoveredObservationAtom",
    "TheoryGuidedAxiomGrounder",
]
