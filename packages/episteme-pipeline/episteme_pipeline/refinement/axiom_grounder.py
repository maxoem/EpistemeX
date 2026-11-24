"""Localized axiom and empirical grounder for ``UNGROUNDED_AXIOM`` deficits.

Implements :class:`TheoryGuidedAxiomGrounder`, satisfying
:class:`~episteme_pipeline.protocols.refinement.LocalizedAxiomGrounder`.

When empirical tenability (:math:`TS_{\\text{local}}`) fails or a theoretical
cluster lacks required :math:`M_{pp}` observation units, this grounder:

1. Expands target chunks strictly locally via immediate intra-document
   neighbors (``sequence_index +/- neighbor_window``) and bounded vector
   similarity search (``vector_top_k``) over embedded corpus chunks.
2. Applies a System 1 ``DecisionEngine.evaluate_noul`` triage gate (with
   deterministic false-negative auditing) before invoking heavy extraction.
3. Re-runs ``NERExtractor.extract`` with a ``PromptContextual`` theory-lens
   anchor and links entities through ``EntityLinker`` + ``EpistemicCurationLedger``.
4. Invokes the managed ``axiom_grounding`` structured prompt bundle (and
   deterministic measurement fallback when no LLM is supplied), resolves
   calibrated ``modal_prior`` via ``ModalStrengthResolver``, and projects
   parameters into :math:`M_p` using ``TheoryProjector``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    EpistemicStateView,
)
from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.config import HermeneuticRefinementConfig
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
from episteme_pipeline.events.models import EntityProcessed
from episteme_pipeline.llm.structured import (
    StructuredLLM,
    StructuredPredictable,
    normalize_structured_llm,
)
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
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    EntityLinker,
    NERExtractor,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.protocols.prompts import PromptContextual
from episteme_pipeline.refinement._shared import (
    compact_theory_lens,
    entity_ids_matching_text,
    evaluate_binary_triage,
    refinement_component_scope,
    resolve_atom_modal_prior,
    resolve_curation_ledger,
    resolve_grounding_entity,
    resolve_refinement_pass,
    resolve_schema_component_type,
    resolve_schema_relation_type,
)
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig
from episteme_pipeline.utils.identifiers import dedup_preserve_order

logger = logging.getLogger(__name__)


class _TheoryLensAnchor:
    """``PromptContextual`` adapter wrapping a macro-theory deficit lens for NER."""

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
        Physical or theoretical observable dimension name.
    value : float
        Measured numerical magnitude.
    unit : str or None, optional
        Measurement unit string (e.g. ``"ms"``, ``"uM"``).
    """

    dimension: str
    value: float
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
        Empirical schema component type (e.g. ``ObservationUnit``, ``EmpiricalStatement``).
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
        """Normalize observation proposition text."""
        return value.strip()

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        """Coerce and clamp confidence into ``[0.0, 1.0]``."""
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.85


class AxiomGroundingOutput(BaseModel):
    """Structured batch output emitted by LLM-assisted axiom grounding.

    Attributes
    ----------
    observations : list of RecoveredObservationAtom
        Empirical observation units recovered from local/vector chunks.
    entities : list of RecoveredGroundingEntity
        Additional domain entities identified in the grounding passages.
    """

    observations: list[RecoveredObservationAtom] = Field(default_factory=list)
    entities: list[RecoveredGroundingEntity] = Field(default_factory=list)


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


class TheoryGuidedAxiomGrounder:
    """Localized observation and parameter grounder for ``UNGROUNDED_AXIOM`` deficits.

    Expands ``deficit.target_chunk_ids`` strictly locally via immediate same-document
    neighbors and bounded vector search, gates extraction via System 1
    ``DecisionEngine``, re-runs localized NER + ``EntityLinker``, extracts missing
    observations & measurements via managed ``axiom_grounding`` prompts, resolves
    calibrated ``modal_prior`` via ``ModalStrengthResolver``, and projects
    theoretical parameters into :math:`M_p`.

    Parameters
    ----------
    ner_extractor : NERExtractor or None, optional
        Optional Phase 2 NER extractor invoked with a ``PromptContextual`` anchor.
    llm : StructuredLLM or StructuredPredictable or Any or None, optional
        Optional structured LLM used to recover empirical observations and measurements.
    theory_projector : TheoryProjector or None, optional
        Optional structuralist projector mapping observations into :math:`M_p`.
    embedding_model : EmbeddingModel or None, optional
        Optional bi-encoder used to embed the theory-lens query when seeds lack embeddings.
    entity_linker : EntityLinker or None, optional
        Optional entity linker associating extracted concepts with canonical L2 entities.
    modal_resolver : ModalStrengthResolver or None, optional
        Optional modal prior resolver applied to newly recovered observation atoms.
    decision_engine : DecisionEngine or None, optional
        Optional System 1 engine gating observation presence prior to extraction.
    config : HermeneuticRefinementConfig or None, optional
        Configuration holding prompt bundles, decoding strategy, and thresholds.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.
    neighbor_window : int, default 1
        Maximum ``sequence_index`` offset within the same ``source_doc_id``.
    vector_top_k : int, default 3
        Maximum candidate chunks retrieved by bounded ``vector_search``.
    prompts : StructuredPromptBundle or str or None, optional
        Optional prompt bundle override overriding ``config.axiom_grounding_prompts``.
    strategy : Any, optional
        Optional decoding strategy override overriding ``config.axiom_grounding_decoding_strategy``.
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
        entity_linker: EntityLinker | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        decision_engine: DecisionEngine | None = None,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
        neighbor_window: int = 1,
        vector_top_k: int = 3,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        self.ner_extractor = ner_extractor
        self.llm: StructuredPredictable | None = normalize_structured_llm(llm)
        if theory_projector is not None and not isinstance(
            theory_projector, TheoryProjector
        ):
            raise TypeError(
                f"{type(theory_projector).__name__} does not inherit from TheoryProjector"
            )
        self.theory_projector: TheoryProjector = (
            theory_projector
            if theory_projector is not None
            else GenericTheoryProjector()
        )
        self.embedding_model: EmbeddingModel | None = (
            ensure_embedding_model(embedding_model)
            if embedding_model is not None
            else None
        )
        self.entity_linker = entity_linker
        self.modal_resolver = modal_resolver
        self.decision_engine = decision_engine
        self.config = config or HermeneuticRefinementConfig()
        self.schema = schema
        self.neighbor_window = max(0, neighbor_window)
        self.vector_top_k = max(0, vector_top_k)

        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        elif isinstance(prompts, str):
            self.prompts = self.config.axiom_grounding_prompts.model_copy(
                update={"direct_template": prompts}
            )
        else:
            self.prompts = self.config.axiom_grounding_prompts

        self.strategy = (
            strategy
            if strategy is not None
            else self.config.axiom_grounding_decoding_strategy
        )
        self.confidence_threshold = float(confidence_threshold)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            JSON-serializable configuration snapshot across sub-components.
        """
        strategy_str = (
            self.strategy.value
            if isinstance(self.strategy, Enum)
            else str(self.strategy)
        )
        return {
            "class": self.__class__.__name__,
            "schema_version": self.schema.version,
            "neighbor_window": self.neighbor_window,
            "vector_top_k": self.vector_top_k,
            "confidence_threshold": self.confidence_threshold,
            "strategy": strategy_str,
            "use_decision_engine_gating": self.config.use_decision_engine_gating,
            "decision_confidence_threshold": self.config.decision_confidence_threshold,
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
            "entity_linker": (
                self.entity_linker.fingerprint()
                if isinstance(self.entity_linker, Fingerprintable)
                else fingerprint_method(self.entity_linker)
            ),
            "modal_resolver": (
                self.modal_resolver.fingerprint()
                if isinstance(self.modal_resolver, Fingerprintable)
                else fingerprint_method(self.modal_resolver)
            ),
            "decision_engine": (
                self.decision_engine.fingerprint()
                if isinstance(self.decision_engine, Fingerprintable)
                else fingerprint_method(self.decision_engine)
            ),
        }

    def _observation_types(self) -> list[str]:
        """Return configured partition-B observation component types from ``schema``."""
        b_types = self.schema.get_partition_components("B")
        return b_types or [self.schema.default_observation_component_type()]

    async def _expand_local_chunks(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        target_atoms: list[TheoryAtom],
    ) -> list[L1Chunk]:
        """Expand target chunks strictly to document-window neighbors & vector hits."""
        chunks_by_id: dict[str, L1Chunk] = {c.id: c for c in state.chunks}
        if deficit.target_chunk_ids:
            seed_ids = dedup_preserve_order(deficit.target_chunk_ids)
        else:
            seed_ids = dedup_preserve_order(
                a.source_chunk_id for a in target_atoms if a.source_chunk_id
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

        if self.neighbor_window > 0:
            for seed in seed_chunks:
                for cand in state.chunks:
                    if (
                        cand.source_doc_id == seed.source_doc_id
                        and abs(cand.sequence_index - seed.sequence_index)
                        <= self.neighbor_window
                    ):
                        expanded[cand.id] = cand

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
                results = await reader.vector_search(
                    query_embedding,
                    top_k=self.vector_top_k,
                    node_label="Chunk",
                )
                for hit in results:
                    if hit.score > 0.25 and hit.node_id in chunks_by_id:
                        expanded[hit.node_id] = chunks_by_id[hit.node_id]

        return sorted(
            expanded.values(),
            key=lambda c: (c.source_doc_id, c.sequence_index, c.id),
        )

    @staticmethod
    def _build_theory_definition(
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
                            formula_expression=str(item.get("formula_expression", "")),
                            involved_parameters=[
                                str(p) for p in item.get("involved_parameters", []) if p
                            ],
                        )
                    )
                elif isinstance(item, str) and item.strip():
                    laws.append(
                        TheoryLaw(law_id=f"law_{idx}", description=item.strip())
                    )

        raw_blur = lens.get("max_admissible_blur", 1.0)
        try:
            max_blur = float(raw_blur)
        except (TypeError, ValueError):
            max_blur = 1.0

        for atom in target_atoms:
            atom_dims = atom.parameters.get("required_dimensions")
            if isinstance(atom_dims, list):
                for dim in atom_dims:
                    if str(dim) not in required_dimensions:
                        required_dimensions.append(str(dim))
            for k in atom.parameters:
                if (
                    k not in {"required_dimensions", "theory_id"}
                    and k not in parameter_names
                ):
                    parameter_names.append(k)

        return TheoryElementDefinition(
            theory_id=theory_id,
            name=theory_name,
            parameter_names=parameter_names,
            required_dimensions=required_dimensions,
            laws=laws,
            max_admissible_blur=max_blur,
        )

    def _extract_deterministic_observations(
        self,
        *,
        deficit: EpistemicDeficit,
        expanded_chunks: list[L1Chunk],
        target_atoms: list[TheoryAtom],
        theory_def: TheoryElementDefinition,
        scoped_entities: list[L2Entity],
        existing_atoms: list[TheoryAtom],
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        """Extract quantitative observations deterministically when no LLM is available."""
        existing_obs_texts = {
            " ".join(a.text.lower().split())
            for a in existing_atoms
            if self.schema.resolve_component_partition(a.component_type) == "B"
        }
        primary_target = target_atoms[0] if target_atoms else None
        recovered_atoms: list[TheoryAtom] = []
        recovered_relations: list[TheoryRelation] = []
        default_obs_type = self.schema.default_observation_component_type()
        support_rel_type = self.schema.default_support_relation()

        req_dims = list(theory_def.required_dimensions)
        for chunk in expanded_chunks:
            extracted_measurements: list[Measurement] = []
            seen_dims: set[str] = set()

            for dim in req_dims:
                pattern = re.compile(
                    rf"\b{re.escape(dim)}\b\s*(?:=|:|is|at|of)?\s*"
                    rf"([-+]?\d+(?:\.\d+)?)\s*([a-zA-Z%/]+)?",
                    re.IGNORECASE,
                )
                match = pattern.search(chunk.text)
                if match is not None:
                    val = float(match.group(1))
                    unit = match.group(2) if match.group(2) else None
                    extracted_measurements.append(
                        Measurement(dimension=dim, value=val, unit=unit)
                    )
                    seen_dims.add(dim.lower())

            if not extracted_measurements and req_dims:
                dim_pattern = re.compile(
                    r"\b([a-z][a-z0-9_]{2,40})\b\s*=\s*([-+]?\d+(?:\.\d+)?)\s*([a-zA-Z%/]+)?",
                    re.IGNORECASE,
                )
                for dim_name, val_str, unit in dim_pattern.findall(chunk.text):
                    if dim_name.lower() not in seen_dims:
                        extracted_measurements.append(
                            Measurement(
                                dimension=dim_name,
                                value=float(val_str),
                                unit=unit or None,
                            )
                        )
                        seen_dims.add(dim_name.lower())

            if not extracted_measurements:
                continue

            obs_text = chunk.text.strip()
            norm_text = " ".join(obs_text.lower().split())
            if norm_text in existing_obs_texts:
                continue
            existing_obs_texts.add(norm_text)

            obs_id = _stable_grounding_atom_id(
                deficit.deficit_id,
                chunk.id,
                f"DET_{len(recovered_atoms) + 1}",
                obs_text,
            )
            linked_eids = entity_ids_matching_text(obs_text, scoped_entities)
            obs_atom = TheoryAtom(
                id=obs_id,
                text=obs_text,
                component_type=default_obs_type,
                source_chunk_id=chunk.id,
                confidence=0.80,
                modal_prior=0.80,
                entity_ids=linked_eids,
                measurements=extracted_measurements,
            )
            recovered_atoms.append(obs_atom)

            if primary_target is not None and primary_target.id != obs_atom.id:
                rel_scope = (
                    "local"
                    if obs_atom.source_chunk_id == primary_target.source_chunk_id
                    else "global"
                )
                recovered_relations.append(
                    TheoryRelation(
                        source_id=obs_atom.id,
                        target_id=primary_target.id,
                        relation_type=support_rel_type,
                        confidence=0.80,
                        weight=0.80,
                        active_weight=0.80,
                        scope=rel_scope,
                    )
                )

        return recovered_atoms, recovered_relations

    async def ground_axiom(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Ground an ungrounded axiom/cluster deficit in expanded local chunks.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``UNGROUNDED_AXIOM`` deficit carrying theory-lens and target chunk metadata.
        state : EpistemicStateView
            Cumulative epistemic state view containing corpus chunks, entities, and atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for event lineage and curation ledger.

        Returns
        -------
        RefinementDelta
            Delta holding recovered entities, triples, observation ``TheoryAtom``s,
            support relations, parameter-projected claimant updates, and resolved IDs.
        """
        if deficit.deficit_kind != EpistemicDeficitKind.UNGROUNDED_AXIOM:
            raise ValueError(
                f"TheoryGuidedAxiomGrounder only handles UNGROUNDED_AXIOM deficits "
                f"(got {deficit.deficit_kind.value})"
            )

        next_pass = resolve_refinement_pass(context, deficit)
        run_id = context.run_id if context is not None else "unknown"
        comp_name = type(self).__name__
        emitter = get_event_emitter()
        curation_ledger = resolve_curation_ledger(context)

        all_atoms = list(state.canonical_theory_atoms or state.theory_atoms)
        atoms_by_id = {a.id: a for a in all_atoms}
        chunks_by_id = {c.id: c for c in state.chunks}
        entities_by_id = {e.id: e for e in state.entities}
        obs_types = self._observation_types()
        default_obs_type = self.schema.default_observation_component_type()

        with refinement_component_scope(
            comp_name,
            context,
            input_description=f"deficit={deficit.deficit_id}",
        ) as outcome:
            target_atoms = [
                atoms_by_id[aid]
                for aid in deficit.target_atom_ids
                if aid in atoms_by_id
            ]
            if not target_atoms and deficit.target_chunk_ids:
                seed_set = set(deficit.target_chunk_ids)
                target_atoms = [
                    a
                    for a in all_atoms
                    if a.source_chunk_id in seed_set
                    and self.schema.resolve_component_partition(a.component_type) == "A"
                ]

            expanded_chunks = await self._expand_local_chunks(
                deficit, state, target_atoms
            )
            if not expanded_chunks:
                outcome.output_description = "no_target_chunks"
                return RefinementDelta(refinement_pass=next_pass)

            expanded_chunk_ids = {c.id for c in expanded_chunks}
            theory_def = self._build_theory_definition(deficit, target_atoms)

            # System 1 DecisionEngine pre-gate before NER / LLM extraction.
            if self.prompts.decision_template:
                chunks_preview = "\n\n".join(
                    f"[{c.id}] {c.text[:350]}" for c in expanded_chunks[:4]
                )
                triage = await evaluate_binary_triage(
                    self.decision_engine,
                    state_payload=(
                        f"Theory: {theory_def.theory_id}\n"
                        f"Required Dimensions: {theory_def.required_dimensions}\n"
                        f"Target Hypotheses: {[a.text for a in target_atoms]}\n"
                        f"Passages:\n{chunks_preview}"
                    ),
                    question=self.prompts.decision_template,
                    run_id=run_id,
                    phase_key="refinement_axiom_grounding",
                    item_id=deficit.deficit_id,
                    config=self.config,
                )
                if not triage.value:
                    outcome.output_description = "gated_out_by_decision_engine"
                    return RefinementDelta(refinement_pass=next_pass)

            lens_anchor = _TheoryLensAnchor(
                theory_id=theory_def.theory_id,
                theory_lens=deficit.theory_lens,
                rationale=deficit.rationale,
                target_atom_texts=[a.text for a in target_atoms],
            )

            recovered_entities: list[L2Entity] = []
            recovered_entities_by_id: dict[str, L2Entity] = {}
            recovered_triples: list[L2Triple] = []
            seen_triple_keys: set[tuple[str, str, str, str, str | None]] = {
                (t.subject_id, t.predicate, t.object_id, t.scope, t.source_chunk_id)
                for t in state.local_triples
            }
            reader = ArtifactSubgraphReader.from_view(state)

            def _record_entity(ent: L2Entity, should_emit: bool) -> L2Entity:
                """Merge or register an extracted entity in local state."""
                if ent.id in recovered_entities_by_id:
                    merged_chunks = dedup_preserve_order(
                        [
                            *recovered_entities_by_id[ent.id].source_chunk_ids,
                            *ent.source_chunk_ids,
                        ]
                    )
                    updated = recovered_entities_by_id[ent.id].model_copy(
                        update={
                            "source_chunk_ids": merged_chunks,
                            "description": recovered_entities_by_id[ent.id].description
                            or ent.description,
                        }
                    )
                    recovered_entities_by_id[ent.id] = updated
                    for idx, item in enumerate(recovered_entities):
                        if item.id == ent.id:
                            recovered_entities[idx] = updated
                            break
                    reader.register_entity(updated)
                    return updated
                if should_emit:
                    recovered_entities_by_id[ent.id] = ent
                    recovered_entities.append(ent)
                    reader.register_entity(ent)
                    emitter.emit(
                        EntityProcessed(
                            run_id=run_id,
                            phase="refinement",
                            entity_id=ent.id,
                            entity_name=ent.name,
                            entity_type=ent.label,
                        )
                    )
                return ent

            # 1. Localized NER extraction guided by TheoryLensAnchor + EntityLinker
            if self.ner_extractor is not None:
                for chunk in expanded_chunks:
                    ents, trips, _, _, _ = await self.ner_extractor.extract(
                        chunk.id,
                        chunk.text,
                        self.schema,
                        memory=None,
                        anchor=lens_anchor,
                    )
                    ner_id_remap: dict[str, str] = {}
                    for ent in ents:
                        scoped_cids = [
                            cid
                            for cid in ent.source_chunk_ids
                            if cid in expanded_chunk_ids
                        ] or [chunk.id]
                        resolved_ent, should_emit = await resolve_grounding_entity(
                            name=ent.name,
                            label=ent.label,
                            description=ent.description,
                            chunk_id=scoped_cids[0],
                            chunk_text=chunk.text,
                            confidence=float(ent.confidence or 0.85),
                            entities_by_id=entities_by_id,
                            entity_linker=self.entity_linker,
                            graph_reader=reader,
                            curation_ledger=curation_ledger,
                            schema=self.schema,
                        )
                        if resolved_ent.id != ent.id:
                            ner_id_remap[ent.id] = resolved_ent.id
                        _record_entity(resolved_ent, should_emit)

                    for triple in trips:
                        subj = ner_id_remap.get(triple.subject_id, triple.subject_id)
                        obj = ner_id_remap.get(triple.object_id, triple.object_id)
                        cid = (
                            triple.source_chunk_id
                            if triple.source_chunk_id in expanded_chunk_ids
                            else chunk.id
                        )
                        scoped_triple = triple.model_copy(
                            update={
                                "subject_id": subj,
                                "object_id": obj,
                                "source_chunk_id": cid,
                            }
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
                    theory_lens=compact_theory_lens(deficit.theory_lens),
                    rationale=deficit.rationale or "Ungrounded axiom detected.",
                    target_atoms=target_atoms_text,
                    source_chunks=source_chunks_text,
                    allowed_chunk_ids=", ".join(c.id for c in expanded_chunks),
                    component_types=self.schema.component_types_str(),
                    observation_component_types=", ".join(obs_types),
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
                    c_text = (
                        chunks_by_id[ent_cid].text if ent_cid in chunks_by_id else ""
                    )
                    linked_ent, should_emit = await resolve_grounding_entity(
                        name=raw_ent.name,
                        label=ent_label,
                        description=raw_ent.description,
                        chunk_id=ent_cid,
                        chunk_text=c_text,
                        confidence=float(raw_ent.confidence),
                        entities_by_id=entities_by_id,
                        entity_linker=self.entity_linker,
                        graph_reader=reader,
                        curation_ledger=curation_ledger,
                        schema=self.schema,
                    )
                    _record_entity(linked_ent, should_emit)

                scoped_entities = list(entities_by_id.values())
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
                        eid for eid in obs.entity_ids if eid in entities_by_id
                    ]
                    if not valid_eids and scoped_entities:
                        valid_eids = entity_ids_matching_text(obs.text, scoped_entities)

                    measurements = [
                        Measurement(dimension=m.dimension, value=m.value, unit=m.unit)
                        for m in obs.measurements
                    ]
                    comp_type = resolve_schema_component_type(
                        obs.component_type,
                        self.schema,
                        preferred_types=obs_types,
                        fallback=default_obs_type,
                    )
                    obs_atom = TheoryAtom(
                        id=obs_id,
                        text=obs.text,
                        component_type=comp_type,
                        source_chunk_id=obs_cid,
                        confidence=obs.confidence,
                        modal_prior=max(0.0, min(1.0, float(obs.confidence))),
                        entity_ids=valid_eids,
                        measurements=measurements,
                    )
                    c_text = (
                        chunks_by_id[obs_cid].text if obs_cid in chunks_by_id else ""
                    )
                    obs_atom = await resolve_atom_modal_prior(
                        obs_atom,
                        self.modal_resolver,
                        context_text=c_text or None,
                    )
                    recovered_obs_atoms.append(obs_atom)

                    resolved_target = (
                        atoms_by_id[obs.target_atom_id]
                        if obs.target_atom_id and obs.target_atom_id in atoms_by_id
                        else (target_atoms[0] if target_atoms else None)
                    )
                    if (
                        resolved_target is not None
                        and resolved_target.id != obs_atom.id
                    ):
                        rel_type = resolve_schema_relation_type(
                            obs.relation_type, self.schema
                        )
                        rel_scope = (
                            "local"
                            if obs_atom.source_chunk_id
                            == resolved_target.source_chunk_id
                            else "global"
                        )
                        rel = TheoryRelation(
                            source_id=obs_atom.id,
                            target_id=resolved_target.id,
                            relation_type=rel_type,
                            confidence=obs.confidence,
                            weight=obs.confidence,
                            active_weight=obs.confidence,
                            scope=rel_scope,
                        )
                        rkey = (rel.source_id, rel.relation_type, rel.target_id)
                        if rkey not in seen_rel_keys:
                            seen_rel_keys.add(rkey)
                            recovered_relations.append(rel)

            # 3. Deterministic measurement fallback when LLM unavailable or returned none
            if not recovered_obs_atoms:
                det_atoms, det_rels = self._extract_deterministic_observations(
                    deficit=deficit,
                    expanded_chunks=expanded_chunks,
                    target_atoms=target_atoms,
                    theory_def=theory_def,
                    scoped_entities=list(entities_by_id.values()),
                    existing_atoms=all_atoms,
                )
                for idx, det_atom in enumerate(det_atoms):
                    c_text = (
                        chunks_by_id[det_atom.source_chunk_id].text
                        if det_atom.source_chunk_id in chunks_by_id
                        else ""
                    )
                    det_atoms[idx] = await resolve_atom_modal_prior(
                        det_atom,
                        self.modal_resolver,
                        context_text=c_text or None,
                    )
                recovered_obs_atoms.extend(det_atoms)
                for rel in det_rels:
                    rkey = (rel.source_id, rel.relation_type, rel.target_id)
                    if rkey not in seen_rel_keys:
                        seen_rel_keys.add(rkey)
                        recovered_relations.append(rel)

            # 4. Re-project M_p parameters onto target atoms via TheoryProjector
            emitted_atoms: list[TheoryAtom] = list(recovered_obs_atoms)
            existing_obs = [
                a
                for a in all_atoms
                if a.source_chunk_id in expanded_chunk_ids
                and (
                    bool(a.measurements)
                    or self.schema.resolve_component_partition(a.component_type) == "B"
                )
            ]
            cluster_obs = [*existing_obs, *recovered_obs_atoms]
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

            resolved_ids = (
                [deficit.deficit_id]
                if (
                    recovered_entities
                    or recovered_triples
                    or emitted_atoms
                    or recovered_relations
                )
                else []
            )
            outcome.output_description = (
                f"entities={len(recovered_entities)}, triples={len(recovered_triples)}, "
                f"atoms={len(emitted_atoms)}, relations={len(recovered_relations)}"
            )
            return RefinementDelta(
                entities=recovered_entities,
                local_triples=recovered_triples,
                theory_atoms=emitted_atoms,
                theory_relations=recovered_relations,
                resolved_deficit_ids=resolved_ids,
                refinement_pass=next_pass,
            )


__all__ = [
    "AxiomGroundingOutput",
    "RecoveredGroundingEntity",
    "RecoveredMeasurement",
    "RecoveredObservationAtom",
    "TheoryGuidedAxiomGrounder",
]
