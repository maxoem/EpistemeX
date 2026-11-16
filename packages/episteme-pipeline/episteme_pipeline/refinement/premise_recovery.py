"""Theory-guided implicit premise (enthymeme) recovery handler (ISSUE-053).

Implements :class:`LLMTheoryGuidedPremiseRecoverer`, satisfying
:class:`~episteme_pipeline.protocols.refinement.TheoryGuidedPremiseRecoverer` and
:class:`~episteme_pipeline.protocols.fingerprint.Fingerprintable`.

Operates strictly on the targeted source chunks and claim atoms named in an
``ENTHYMEME_GAP`` deficit without invalidating or modifying unaffected subgraphs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import ComponentCompleted, ComponentStarted
from episteme_pipeline.llm.structured import StructuredLLM, ensure_structured_llm
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.argument_mining import ARCClassifier
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactExecutionContext,
        EpistemicStateView,
    )

logger = logging.getLogger(__name__)


DEFAULT_PREMISE_RECOVERY_PROMPT = """\
You are an expert in formal argumentation, philosophy of science, and structuralist metatheory.
An argument component lacks explicit supporting premises or a bridging warrant (an enthymeme gap).
Re-read ONLY the provided source chunk(s) through the supplied macro-theory lens and recover any
implicit premises or bridging warrants implied by the prose.

### Theory Context (Macro-Theory Lens)
Theory ID: {theory_id}
Theory Lens: {theory_lens}
Deficit Rationale: {rationale}

### Target Ungrounded Claim(s)
{target_claims}

### Existing Argument Components in Target Chunks
{existing_atoms}

### Scoped Entities
{chunk_entities}

### Allowed Component Types
{component_types}

### Allowed Argument Relation Types
{argument_relation_types}

### Source Chunk Text(s)
{source_chunks}

### Instructions
1. Identify implicit premises, unstated auxiliary assumptions, or bridging warrants present or
   presupposed in the source chunk(s) that directly support or attack the target claim(s).
2. Ground each recovered premise in its exact ``source_chunk_id`` from [{target_chunk_ids}].
3. Specify ``target_atom_id`` and ``relation_type`` (typically ``SUPPORTS_ARG`` or ``ATTACKS``).
4. Do not duplicate components already listed in Existing Argument Components.
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


class RecoveredImplicitPremise(BaseModel):
    """Structured LLM prediction for a single recovered implicit premise.

    Attributes
    ----------
    local_id : str, default "P1"
        Local identifier within the recovery response.
    text : str
        Recovered implicit premise or bridging warrant statement.
    component_type : str, default "EmpiricalStatement"
        Ontological component type validated against ``SchemaConfig``.
    source_chunk_id : str, default ""
        Identifier of the targeted L1 chunk grounding this premise.
    target_atom_id : str, default ""
        Identifier of the target :class:`TheoryAtom` this premise bears upon.
    relation_type : str, default "SUPPORTS_ARG"
        Dialectical relation connecting this premise to ``target_atom_id``.
    confidence : float, default 0.85
        Normalized extraction confidence in ``[0.0, 1.0]``.
    weight : float or None, optional
        Optional dialectical relation weight in ``[0.0, 1.0]``.
    entity_ids : list of str, optional
        Identifiers of scoped L2 entities referenced by the premise.
    reasoning : str, default ""
        Brief diagnostic rationale explaining the enthymeme bridge.
    """

    local_id: str = "P1"
    text: str
    component_type: str = "EmpiricalStatement"
    source_chunk_id: str = ""
    target_atom_id: str = ""
    relation_type: str = "SUPPORTS_ARG"
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    entity_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""

    @field_validator("text")
    @classmethod
    def _strip_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Recovered implicit premise text must not be empty.")
        return cleaned

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.85


class PremiseRecoveryOutput(BaseModel):
    """Structured LLM response envelope for theory-guided premise recovery.

    Attributes
    ----------
    recovered_premises : list of RecoveredImplicitPremise, optional
        Implicit premises or bridging warrants recovered from targeted chunks.
    """

    recovered_premises: list[RecoveredImplicitPremise] = Field(default_factory=list)


def _normalize_structured_llm(llm: Any | None) -> StructuredLLM | _StructuredPredictPort | None:
    """Normalize an optional LLM backend to a structured prediction port."""
    if llm is None:
        return None
    if isinstance(llm, _StructuredPredictPort):
        return llm
    return ensure_structured_llm(llm, use_cache=False)


def _stable_premise_atom_id(
    deficit_id: str,
    chunk_id: str,
    local_id: str,
    text: str,
) -> str:
    """Compute a deterministic identifier for a recovered premise atom.

    Parameters
    ----------
    deficit_id : str
        Triggering epistemic deficit identifier.
    chunk_id : str
        Source L1 chunk identifier.
    local_id : str
        Local premise tag from the structured response.
    text : str
        Canonicalized premise text.

    Returns
    -------
    str
        Deterministic atom identifier prefixed with ``ac_ref_``.
    """
    payload = f"{deficit_id}:{chunk_id}:{local_id}:{text.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:14]
    return f"ac_ref_{digest}"


class LLMTheoryGuidedPremiseRecoverer:
    """Theory-conditioned premise recoverer for ``ENTHYMEME_GAP`` deficits.

    Inspects strictly the targeted source chunks and target claim atoms named in
    an ``ENTHYMEME_GAP`` deficit, conditions a structured LLM prompt on the
    discovered macro-theory lens (``deficit.theory_lens``), emits recovered
    :class:`TheoryAtom` and :class:`TheoryRelation` deltas, and optionally runs
    ``arc_classifier.classify_pairs(...)`` strictly over pairs connecting newly
    recovered premises to the target atom and its immediate 1-hop neighbors.

    Parameters
    ----------
    llm : StructuredLLM or Any or None, optional
        Structured LLM adapter or LlamaIndex LLM facade used for premise gleaning.
    arc_classifier : ARCClassifier or None, optional
        Optional argument relation classifier run strictly on delta pairs
        ``(recovered_premise, target_atom_and_neighbors)``.
    global_extractor : GlobalRelationExtractor or None, optional
        Optional global extractor forwarded to ``arc_classifier.classify_pairs``.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.
    prompts : StructuredPromptBundle or str or None, optional
        Optional custom prompt bundle or template string.
    strategy : Any, default "direct_constrained"
        Structured decoding strategy forwarded to ``llm.predict_structured``.
    confidence_threshold : float, default 0.5
        Minimum confidence required to retain a recovered implicit premise.
    """

    def __init__(
        self,
        llm: StructuredLLM | Any | None = None,
        *,
        arc_classifier: ARCClassifier | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = "direct_constrained",
        confidence_threshold: float = 0.5,
    ) -> None:
        self.llm = _normalize_structured_llm(llm)
        self.arc_classifier = arc_classifier
        self.global_extractor = global_extractor
        self.schema = schema
        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        else:
            self.prompts = StructuredPromptBundle(
                direct_template=prompts or DEFAULT_PREMISE_RECOVERY_PROMPT,
                name="refinement_premise_recovery",
            )
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache lineage.

        Returns
        -------
        dict of str to Any
            JSON-serializable dictionary capturing component settings and
            sub-component fingerprints.
        """
        strategy_str = (
            self.strategy.value if isinstance(self.strategy, Enum) else str(self.strategy)
        )
        llm_fp = (
            self.llm.fingerprint()
            if isinstance(self.llm, Fingerprintable)
            else fingerprint_method(self.llm)
        )
        arc_fp = (
            self.arc_classifier.fingerprint()
            if isinstance(self.arc_classifier, Fingerprintable)
            else fingerprint_method(self.arc_classifier)
        )
        global_fp = (
            self.global_extractor.fingerprint()
            if isinstance(self.global_extractor, Fingerprintable)
            else fingerprint_method(self.global_extractor)
        )
        return {
            "class": self.__class__.__name__,
            "schema_version": self.schema.version,
            "strategy": strategy_str,
            "confidence_threshold": self.confidence_threshold,
            "prompts": self.prompts.fingerprint(),
            "llm": llm_fp,
            "arc_classifier": arc_fp,
            "global_extractor": global_fp,
        }

    def _resolve_component_type(self, candidate: str) -> str:
        """Resolve a predicted component type against the configured schema."""
        if candidate in self.schema.component_types:
            return candidate
        if "EmpiricalStatement" in self.schema.component_types:
            return "EmpiricalStatement"
        if "ObservationUnit" in self.schema.component_types:
            return "ObservationUnit"
        return self.schema.component_types[0]

    def _resolve_relation_type(self, candidate: str) -> str:
        """Resolve a predicted dialectical relation type against the schema."""
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

    async def recover_premises(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Perform localized theory-guided premise recovery for an ``ENTHYMEME_GAP``.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``ENTHYMEME_GAP`` deficit specifying target chunks, target atoms,
            and the conditioning ``theory_lens``.
        state : EpistemicStateView
            Cumulative epistemic state view providing chunks, entities, and L3 atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for event lineage.

        Returns
        -------
        RefinementDelta
            Delta carrying newly recovered implicit premise atoms and dialectical
            relations strictly within the targeted subgraph.

        Raises
        ------
        ValueError
            If ``deficit.deficit_kind`` is not ``ENTHYMEME_GAP`` or no structured
            LLM is configured.
        """
        if deficit.deficit_kind != EpistemicDeficitKind.ENTHYMEME_GAP:
            raise ValueError(
                f"LLMTheoryGuidedPremiseRecoverer only handles ENTHYMEME_GAP deficits "
                f"(got {deficit.deficit_kind})."
            )
        if self.llm is None:
            raise ValueError(
                "LLMTheoryGuidedPremiseRecoverer requires a configured StructuredLLM."
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
            all_relations = (
                state.canonical_theory_relations
                if state.canonical_theory_relations
                else state.theory_relations
            )
            atoms_by_id: dict[str, TheoryAtom] = {a.id: a for a in all_atoms}
            target_atoms: list[TheoryAtom] = [
                atoms_by_id[aid] for aid in deficit.target_atom_ids if aid in atoms_by_id
            ]

            if deficit.target_chunk_ids:
                ordered_chunk_ids = list(dict.fromkeys(deficit.target_chunk_ids))
            else:
                ordered_chunk_ids = list(
                    dict.fromkeys(
                        a.source_chunk_id for a in target_atoms if a.source_chunk_id
                    )
                )

            target_chunk_id_set = set(ordered_chunk_ids)
            chunks_by_id: dict[str, L1Chunk] = {c.id: c for c in state.chunks}
            target_chunks: list[L1Chunk] = [
                chunks_by_id[cid] for cid in ordered_chunk_ids if cid in chunks_by_id
            ]

            if not target_chunks:
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

            scoped_entity_ids: set[str] = {
                eid for atom in target_atoms for eid in atom.entity_ids
            }
            for ent in state.entities:
                if any(cid in target_chunk_id_set for cid in ent.source_chunk_ids):
                    scoped_entity_ids.add(ent.id)
            scoped_entities: list[L2Entity] = [
                ent for ent in state.entities if ent.id in scoped_entity_ids
            ]
            all_entity_ids: set[str] = {ent.id for ent in state.entities}

            existing_chunk_atoms = [
                a for a in all_atoms if a.source_chunk_id in target_chunk_id_set
            ]

            target_claims_text = (
                "\n".join(
                    f"- [{a.id}] ({a.component_type}, chunk={a.source_chunk_id}) {a.text}"
                    for a in target_atoms
                )
                if target_atoms
                else "No explicit target atom resolved."
            )
            existing_atoms_text = (
                "\n".join(
                    f"- [{a.id}] ({a.component_type}, chunk={a.source_chunk_id}) {a.text}"
                    for a in existing_chunk_atoms
                )
                if existing_chunk_atoms
                else "None."
            )
            chunk_entities_text = (
                "\n".join(
                    f"- {e.id}: {e.name} ({e.label})" for e in scoped_entities
                )
                if scoped_entities
                else "None."
            )
            source_chunks_text = "\n\n".join(
                f"[Chunk {c.id} (doc={c.source_doc_id}, seq={c.sequence_index})]\n{c.text}"
                for c in target_chunks
            )

            raw_output: PremiseRecoveryOutput = await self.llm.predict_structured(
                PremiseRecoveryOutput,
                self.prompts,
                strategy=self.strategy,
                theory_id=deficit.theory_id or "unspecified",
                theory_lens=json.dumps(
                    deficit.theory_lens, sort_keys=True, ensure_ascii=False
                ),
                rationale=deficit.rationale or "Enthymeme gap detected.",
                target_claims=target_claims_text,
                existing_atoms=existing_atoms_text,
                chunk_entities=chunk_entities_text,
                source_chunks=source_chunks_text,
                target_chunk_ids=", ".join(c.id for c in target_chunks),
                component_types=self.schema.component_types_str(),
                argument_relation_types=self.schema.argument_relation_types_str(),
            )

            default_chunk_id = target_chunks[0].id
            existing_texts = {
                (a.source_chunk_id, a.text.strip().lower()) for a in existing_chunk_atoms
            }

            recovered_atoms: list[TheoryAtom] = []
            recovered_relations: list[TheoryRelation] = []
            seen_rel_keys: set[tuple[str, str, str]] = set()

            for idx, item in enumerate(raw_output.recovered_premises, start=1):
                if item.confidence < self.confidence_threshold:
                    continue

                assigned_chunk_id = (
                    item.source_chunk_id
                    if item.source_chunk_id in target_chunk_id_set
                    else default_chunk_id
                )
                if (assigned_chunk_id, item.text.strip().lower()) in existing_texts:
                    continue

                atom_id = _stable_premise_atom_id(
                    deficit.deficit_id,
                    assigned_chunk_id,
                    item.local_id or f"P{idx}",
                    item.text,
                )

                valid_entity_ids = [
                    eid for eid in item.entity_ids if eid in all_entity_ids
                ]
                if not valid_entity_ids and scoped_entities:
                    low_text = item.text.lower()
                    valid_entity_ids = [
                        ent.id
                        for ent in scoped_entities
                        if ent.name.strip() and ent.name.strip().lower() in low_text
                    ]

                new_atom = TheoryAtom(
                    id=atom_id,
                    text=item.text,
                    component_type=self._resolve_component_type(item.component_type),
                    source_chunk_id=assigned_chunk_id,
                    confidence=item.confidence,
                    entity_ids=valid_entity_ids,
                )
                recovered_atoms.append(new_atom)
                existing_texts.add((assigned_chunk_id, item.text.strip().lower()))

                resolved_target: TheoryAtom | None = None
                if item.target_atom_id and item.target_atom_id in atoms_by_id:
                    resolved_target = atoms_by_id[item.target_atom_id]
                elif target_atoms:
                    resolved_target = target_atoms[0]

                if resolved_target is not None and resolved_target.id != new_atom.id:
                    rel_type = self._resolve_relation_type(item.relation_type)
                    rel_scope = (
                        "local"
                        if new_atom.source_chunk_id == resolved_target.source_chunk_id
                        else "global"
                    )
                    rel_weight = (
                        item.weight if item.weight is not None else item.confidence
                    )
                    rel = TheoryRelation(
                        source_id=new_atom.id,
                        target_id=resolved_target.id,
                        relation_type=rel_type,
                        confidence=item.confidence,
                        scope=rel_scope,
                        weight=rel_weight,
                    )
                    rkey = (rel.source_id, rel.relation_type, rel.target_id)
                    if rkey not in seen_rel_keys:
                        seen_rel_keys.add(rkey)
                        recovered_relations.append(rel)

            if self.arc_classifier is not None and recovered_atoms and target_atoms:
                reader = state.to_graph_reader()
                for atom in recovered_atoms:
                    reader.register_theory_atom(atom)

                target_id_set = {a.id for a in target_atoms}
                neighbor_ids: set[str] = set()
                for rel in all_relations:
                    if rel.source_id in target_id_set and rel.target_id in atoms_by_id:
                        neighbor_ids.add(rel.target_id)
                    if rel.target_id in target_id_set and rel.source_id in atoms_by_id:
                        neighbor_ids.add(rel.source_id)

                candidate_targets: list[TheoryAtom] = list(target_atoms) + [
                    atoms_by_id[nid]
                    for nid in sorted(neighbor_ids)
                    if nid not in target_id_set
                ]
                delta_pairs: list[tuple[TheoryAtom, TheoryAtom]] = [
                    (new_atom, cand)
                    for new_atom in recovered_atoms
                    for cand in candidate_targets
                    if new_atom.id != cand.id
                ]
                if delta_pairs:
                    arc_relations = await self.arc_classifier.classify_pairs(
                        delta_pairs,
                        reader,
                        schema=self.schema,
                        global_extractor=self.global_extractor,
                    )
                    for arc_rel in arc_relations:
                        rkey = (
                            arc_rel.source_id,
                            arc_rel.relation_type,
                            arc_rel.target_id,
                        )
                        if rkey not in seen_rel_keys:
                            seen_rel_keys.add(rkey)
                            recovered_relations.append(arc_rel)

            resolved_ids = (
                [deficit.deficit_id]
                if (recovered_atoms or recovered_relations)
                else []
            )
            delta = RefinementDelta(
                theory_atoms=recovered_atoms,
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
                        f"recovered_atoms={len(recovered_atoms)}, "
                        f"recovered_relations={len(recovered_relations)}"
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
    "DEFAULT_PREMISE_RECOVERY_PROMPT",
    "LLMTheoryGuidedPremiseRecoverer",
    "PremiseRecoveryOutput",
    "RecoveredImplicitPremise",
]
