"""Shared infrastructure helpers for closed-loop hermeneutic refinement handlers.

Consolidates component telemetry emission, System 1 ``DecisionEngine`` triage
gating (:class:`~episteme_pipeline.decision.cascade.TriageDecision`), shared
``EntityLinker`` + :class:`EpistemicCurationLedger` grounding, modal prior
resolution, and schema-driven component/relation resolution without duplicating
boilerplate across refinement handlers.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    EpistemicStateView,
)
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import EpistemicDeficit, L2Entity, TheoryAtom
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.decision.cascade import (
    TriageDecision,
    should_audit_deterministically,
)
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import ComponentCompleted, ComponentStarted
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.extractors import EntityLinker
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils.identifiers import dedup_preserve_order, stable_entity_id

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelemetryOutcome:
    """Mutable outcome description populated within :func:`refinement_component_scope`.

    Attributes
    ----------
    output_description : str
        Concise summary string emitted on :class:`ComponentCompleted`.
    """

    output_description: str = "completed"


@contextmanager
def refinement_component_scope(
    component_name: str,
    context: ArtifactExecutionContext | None,
    *,
    input_description: str,
) -> Iterator[TelemetryOutcome]:
    """Emit standardized ``ComponentStarted`` / ``ComponentCompleted`` telemetry events.

    Parameters
    ----------
    component_name : str
        Handler component class name.
    context : ArtifactExecutionContext or None
        Active execution context providing ``run_id``.
    input_description : str
        Summary string logged on :class:`ComponentStarted`.

    Yields
    ------
    TelemetryOutcome
        Mutable descriptor whose ``output_description`` is attached upon normal exit.
    """
    emitter = get_event_emitter()
    run_id = context.run_id if context is not None else "unknown"
    start_time = time.perf_counter()
    emitter.emit(
        ComponentStarted(
            run_id=run_id,
            phase="refinement",
            component_name=component_name,
            input_description=input_description,
        )
    )
    outcome = TelemetryOutcome()
    try:
        yield outcome
    except Exception as exc:
        emitter.emit(
            ComponentCompleted(
                run_id=run_id,
                phase="refinement",
                component_name=component_name,
                duration_seconds=time.perf_counter() - start_time,
                output_description="failed",
                success=False,
                error_message=f"{type(exc).__name__}: {exc}",
            )
        )
        raise
    else:
        emitter.emit(
            ComponentCompleted(
                run_id=run_id,
                phase="refinement",
                component_name=component_name,
                duration_seconds=time.perf_counter() - start_time,
                output_description=outcome.output_description,
                success=True,
            )
        )


def resolve_refinement_pass(
    context: ArtifactExecutionContext | None,
    deficit: EpistemicDeficit | None = None,
) -> int:
    """Compute the one-based active refinement pass index from ``context`` or ``deficit``.

    Parameters
    ----------
    context : ArtifactExecutionContext or None
        Active execution context.
    deficit : EpistemicDeficit or None, optional
        Fallback deficit providing zero-based detection pass when ``context`` is None.

    Returns
    -------
    int
        One-based refinement pass number (``>= 1``).
    """
    current = (
        context.manifest.refinement_pass
        if context is not None and context.manifest is not None
        else (deficit.refinement_pass if deficit is not None else 0)
    )
    return max(1, current + 1)


def resolve_curation_ledger(
    context: ArtifactExecutionContext | None,
) -> EpistemicCurationLedger:
    """Return the active :class:`EpistemicCurationLedger` or an empty default.

    Parameters
    ----------
    context : ArtifactExecutionContext or None
        Active execution context carrying optional ``pipeline_input``.

    Returns
    -------
    EpistemicCurationLedger
        Resolved curation ledger (empty ledger when none was supplied).
    """
    if context is not None and context.pipeline_input is not None:
        ledger = context.pipeline_input.resolved_curation_ledger()
        if ledger is not None:
            return ledger
    return EpistemicCurationLedger()


async def evaluate_binary_triage(
    decision_engine: DecisionEngine | None,
    *,
    state_payload: str | dict[str, Any],
    question: str,
    run_id: str,
    phase_key: str,
    item_id: str,
    config: HermeneuticRefinementConfig,
) -> TriageDecision[bool]:
    """Run System 1 calibrated binary triage via ``DecisionEngine.evaluate_noul``.

    Escalates to System 2 (``value=True``) when no engine is configured, when
    ``config.use_decision_engine_gating`` is False, when System 1 accepts or
    is uncertain below ``config.decision_confidence_threshold``, or when
    :func:`should_audit_deterministically` flags a high-confidence rejection
    for false-negative auditing.

    Parameters
    ----------
    decision_engine : DecisionEngine or None
        Calibrated System 1 decision engine.
    state_payload : str or dict
        Compact evidence state presented to System 1.
    question : str
        Managed binary proposition evaluated by the Noul head.
    run_id : str
        Deterministic audit seed identifier.
    phase_key : str
        Component namespace for audit sampling.
    item_id : str
        Deficit or item identifier being triaged.
    config : HermeneuticRefinementConfig
        Threshold and audit-rate configuration.

    Returns
    -------
    TriageDecision of bool
        Triage outcome with System 1 probability, ambiguity, and audit flags.
    """
    if decision_engine is None or not config.use_decision_engine_gating:
        return TriageDecision(value=True, is_ambiguous=False)

    noul_res = await decision_engine.evaluate_noul(
        state=state_payload,
        question=question,
    )
    prob_true = float(noul_res.probability)
    threshold = float(config.decision_confidence_threshold)

    if noul_res.passed and prob_true >= threshold:
        return TriageDecision(
            value=True,
            decision=noul_res,
            empirical_accuracy=float(noul_res.empirical_accuracy),
            is_ambiguous=False,
        )

    if (not noul_res.passed) and (1.0 - prob_true) >= threshold:
        is_audit = should_audit_deterministically(
            run_id,
            phase_key,
            item_id,
            config.stochastic_audit_rate,
        )
        return TriageDecision(
            value=is_audit,
            decision=noul_res,
            empirical_accuracy=float(noul_res.empirical_accuracy),
            is_ambiguous=False,
            is_audit=is_audit,
        )

    return TriageDecision(
        value=True,
        decision=noul_res,
        empirical_accuracy=float(noul_res.empirical_accuracy),
        is_ambiguous=True,
    )


def resolve_schema_relation_type(
    candidate: str | None,
    schema: SchemaConfig,
    *,
    fallback_polarity: int = 1,
) -> str:
    """Resolve a candidate dialectical relation label via ``schema``.

    Parameters
    ----------
    candidate : str or None
        Raw candidate label emitted by an LLM or classifier.
    schema : SchemaConfig
        Single source of truth for schema relations and polarities.
    fallback_polarity : int, default 1
        Positive (``+1``) or negative (``-1``) polarity fallback when
        ``candidate`` is absent or unmapped.

    Returns
    -------
    str
        Canonical schema argument relation label.
    """
    if candidate:
        resolved = schema.resolve_relation_type(candidate)
        if resolved is not None:
            return resolved
    return (
        schema.default_attack_relation()
        if fallback_polarity < 0
        else schema.default_support_relation()
    )


def resolve_schema_component_type(
    candidate: str | None,
    schema: SchemaConfig,
    *,
    preferred_types: Sequence[str] | None = None,
    fallback: str | None = None,
) -> str:
    """Resolve a candidate argument component type strictly via ``schema``.

    Parameters
    ----------
    candidate : str or None
        Raw candidate component type string.
    schema : SchemaConfig
        Active graph schema configuration.
    preferred_types : Sequence of str or None, optional
        Optional subset of allowed types (e.g., partition-B types). When set,
        only candidates belonging to ``preferred_types`` are accepted directly.
    fallback : str or None, optional
        Explicit schema-derived fallback if ``candidate`` is invalid.

    Returns
    -------
    str
        Canonical schema component type label.
    """
    allowed = (
        [t for t in preferred_types if t in schema.component_types]
        if preferred_types is not None
        else list(schema.component_types)
    )
    if candidate and candidate in allowed:
        return candidate
    if fallback is not None and (fallback in allowed or not allowed):
        return fallback
    if allowed:
        return allowed[0]
    return schema.default_hypothesis_component_type()


async def resolve_grounding_entity(
    *,
    name: str,
    label: str,
    description: str | None,
    chunk_id: str,
    chunk_text: str,
    confidence: float,
    entities_by_id: dict[str, L2Entity],
    entity_linker: EntityLinker | None,
    graph_reader: GraphReader | None,
    curation_ledger: EpistemicCurationLedger,
    schema: SchemaConfig,
) -> tuple[L2Entity, bool]:
    """Resolve or mint an ``L2Entity`` using existing state, ``EntityLinker``, and curation constraints.

    Parameters
    ----------
    name : str
        Extracted surface entity name.
    label : str
        Candidate node label.
    description : str or None
        Optional contextual entity description.
    chunk_id : str
        Source chunk identifier grounding this mention.
    chunk_text : str
        Passage prose used for contextual disambiguation.
    confidence : float
        Extraction confidence score.
    entities_by_id : dict of str to L2Entity
        Mutable registry of known and newly resolved entities in the current view.
    entity_linker : EntityLinker or None
        Optional pipeline entity linker (e.g., ``CascadingEntityLinker``).
    graph_reader : GraphReader or None
        Graph reader exposed to ``entity_linker``.
    curation_ledger : EpistemicCurationLedger
        Human/refinement constraints including ``cannot_link_entities``.
    schema : SchemaConfig
        Schema configuration validating node labels.

    Returns
    -------
    tuple of (L2Entity, bool)
        Resolved or created entity and a flag indicating whether an entity
        update or creation should be persisted in ``RefinementDelta.entities``.
    """
    clean_name = name.strip()
    valid_label = (
        label
        if label in schema.node_types
        else (schema.node_types[0] if schema.node_types else "Concept")
    )
    norm_key = clean_name.lower()

    def _merge_chunk(entity: L2Entity) -> tuple[L2Entity, bool]:
        """Attach ``chunk_id`` and fallback description to ``entity`` if missing."""
        if chunk_id in entity.source_chunk_ids and (
            description is None or entity.description
        ):
            return entity, False
        updated = entity.model_copy(
            update={
                "source_chunk_ids": dedup_preserve_order(
                    [*entity.source_chunk_ids, chunk_id]
                ),
                "description": entity.description or description,
            }
        )
        entities_by_id[updated.id] = updated
        return updated, True

    candidate_id = stable_entity_id(valid_label, clean_name)

    # 1. Exact/canonical lookup in active entities respecting cannot-link rules.
    for existing in entities_by_id.values():
        if existing.name.strip().lower() != norm_key:
            continue
        if curation_ledger.is_cannot_link(
            existing.id, candidate_id, existing.name, clean_name
        ):
            continue
        return _merge_chunk(existing)

    # 2. Pipeline EntityLinker (e.g., CascadingEntityLinker -> Dense -> JEV).
    mention = L2Entity(
        id=candidate_id,
        label=valid_label,
        name=clean_name,
        description=description,
        source_chunk_ids=[chunk_id],
        textual_envelope=chunk_text[:400] if chunk_text else None,
        confidence=float(confidence),
    )
    if entity_linker is not None and graph_reader is not None:
        linked = await entity_linker.link(mention, graph_reader)
        if linked is not None and not curation_ledger.is_cannot_link(
            linked.id, candidate_id, linked.name, clean_name
        ):
            existing = entities_by_id.get(linked.id)
            if existing is not None:
                return _merge_chunk(existing)
            entities_by_id[linked.id] = linked
            return linked, True

    # 3. Mint deterministic new entity, disambiguating ID if cannot-link collides.
    resolved_id = candidate_id
    while any(
        curation_ledger.is_cannot_link(other_id, resolved_id, other.name, clean_name)
        for other_id, other in entities_by_id.items()
        if other_id == resolved_id
    ):
        resolved_id = f"{resolved_id}_{chunk_id[:6]}"

    created = mention.model_copy(update={"id": resolved_id})
    entities_by_id[created.id] = created
    return created, True


async def resolve_atom_modal_prior(
    atom: TheoryAtom,
    modal_resolver: ModalStrengthResolver | None,
    *,
    context_text: str | None,
) -> TheoryAtom:
    """Resolve and attach calibrated ``modal_prior`` onto ``atom`` if a resolver is available.

    Parameters
    ----------
    atom : TheoryAtom
        Newly recovered or grounded argument atom.
    modal_resolver : ModalStrengthResolver or None
        Async modal strength resolver (e.g., ``HybridModalResolver``).
    context_text : str or None
        Source passage prose for epistemic modality assessment.

    Returns
    -------
    TheoryAtom
        Original atom or updated copy carrying resolved ``modal_prior``.
    """
    if modal_resolver is None:
        return atom
    resolved = await modal_resolver.resolve_modality(atom, context=context_text)
    clamped = max(0.0, min(1.0, float(resolved)))
    if abs(clamped - atom.modal_prior) <= 1e-6:
        return atom
    return atom.model_copy(update={"modal_prior": clamped})


def entity_ids_matching_text(
    text: str,
    entities: Sequence[L2Entity],
    *,
    limit: int = 5,
) -> list[str]:
    """Identify entity IDs whose canonical names appear in ``text`` when linking fails.

    Parameters
    ----------
    text : str
        Atom proposition prose.
    entities : Sequence of L2Entity
        Scoped candidate entities.
    limit : int, default 5
        Maximum linked entities attached to a single atom.

    Returns
    -------
    list of str
        Ordered matching entity identifiers.
    """
    lowered = text.lower()
    matched: list[str] = []
    for ent in entities:
        name = ent.name.strip().lower()
        if name and len(name) >= 2 and name in lowered:
            matched.append(ent.id)
        if len(matched) >= limit:
            break
    return dedup_preserve_order(matched)


def extract_chunk_lookup(
    state: EpistemicStateView,
) -> tuple[dict[str, str], dict[str, L2Entity]]:
    """Build chunk text and entity lookup maps from an ``EpistemicStateView``.

    Parameters
    ----------
    state : EpistemicStateView
        Current epistemic state view.

    Returns
    -------
    tuple of (dict of str to str, dict of str to L2Entity)
        ``(chunks_by_id, entities_by_id)``.
    """
    chunks_by_id = {c.id: c.text for c in state.chunks}
    entities_by_id = {e.id: e for e in state.entities}
    return chunks_by_id, entities_by_id


def compact_theory_lens(theory_lens: Mapping[str, Any], *, max_chars: int = 1200) -> str:
    """Format a compact deterministic summary of ``deficit.theory_lens`` for prompts.

    Parameters
    ----------
    theory_lens : Mapping of str to Any
        Arbitrary structured theory-lens dictionary attached to a deficit.
    max_chars : int, default 1200
        Maximum rendered string length.

    Returns
    -------
    str
        Readable compact representation for LLM/DecisionEngine context.
    """
    import json

    if not theory_lens:
        return "{}"
    rendered = json.dumps(dict(theory_lens), indent=2, ensure_ascii=False, sort_keys=True)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max_chars - 3] + "..."
