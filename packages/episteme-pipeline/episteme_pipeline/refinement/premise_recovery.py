"""Theory-conditioned implicit premise recoverer for ``ENTHYMEME_GAP`` deficits.

Implements :class:`LLMTheoryGuidedPremiseRecoverer`, satisfying
:class:`~episteme_pipeline.protocols.refinement.TheoryGuidedPremiseRecoverer`.

When top-down Graph-of-Thought deficit detection flags an unwarranted or
:math:`Z_1`-disconnected theoretical component, this recoverer:

1. Applies a System 1 ``DecisionEngine.evaluate_noul`` triage gate (with
   deterministic false-negative auditing) before invoking System 2 extraction.
2. Re-reads strictly the targeted chunks via the managed ``premise_recovery``
   prompt bundle conditioned on ``deficit.theory_lens``.
3. Recovers implicit premises carrying full ADR-0023 scoping metadata
   (``scope_type``, ``epistemic_status``, ``intensional_mode``, ``attributed_to``)
   and links entities via ``EntityLinker`` + ``EpistemicCurationLedger``.
4. Resolves calibrated ``modal_prior`` via ``ModalStrengthResolver`` and runs
   ``ARCClassifier.classify_pairs`` strictly on delta pairs linking newly
   recovered premises to target claims and immediate 1-hop neighbors.
"""

from __future__ import annotations

import hashlib
import logging
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    EpistemicStateView,
)
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    L2Entity,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.llm.structured import (
    StructuredLLM,
    StructuredPredictable,
    normalize_structured_llm,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.argument_mining import ARCClassifier
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.extractors import (
    EntityLinker,
    GlobalRelationExtractor,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.modality import ModalStrengthResolver
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


class RecoveredImplicitPremise(BaseModel):
    """Single implicit premise or bridging warrant predicted by System 2 LLM.

    Parameters
    ----------
    local_id : str
        Transient identifier within one LLM response.
    text : str
        Recovered implicit premise or warrant statement.
    component_type : str, default "TheoreticalHypothesis"
        Schema component type label (e.g. ``TheoreticalHypothesis``, ``EmpiricalStatement``).
    source_chunk_id : str
        Originating chunk identifier strictly selected from target chunks.
    target_atom_id : str
        Target unwarranted claim identifier supported or attacked by this premise.
    relation_type : str, default "SUPPORTS_ARG"
        Argument relation type matching ``SchemaConfig.argument_relation_types``.
    confidence : float, default 0.8
        Extractor confidence in ``[0.0, 1.0]``.
    weight : float, default 0.8
        Estimated inferential link strength in ``[0.0, 1.0]``.
    scope_type : str or None, optional
        Optional quantifier/scope classification from ``SchemaConfig.scope_types``.
    epistemic_status : str or None, optional
        Optional epistemic classification (e.g., ``Analytisch`` vs ``Synthetisch``).
    intensional_mode : {"asserted", "attributed", "suppositional", "historical"}, default "asserted"
        ADR-0023 intensional scoping classification for this premise.
    attributed_to : str or None, optional
        Attributed theorist or school when ``intensional_mode`` is attributed/historical.
    entity_names : list of str, optional
        Surface concept names referenced by this premise for entity linking.
    """

    local_id: str = "P1"
    text: str
    component_type: str = "TheoreticalHypothesis"
    source_chunk_id: str = ""
    target_atom_id: str = ""
    relation_type: str = "SUPPORTS_ARG"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    weight: float = Field(default=0.8, ge=0.0, le=1.0)
    scope_type: str | None = None
    epistemic_status: str | None = None
    intensional_mode: Literal[
        "asserted", "attributed", "suppositional", "historical"
    ] = "asserted"
    attributed_to: str | None = None
    entity_names: list[str] = Field(default_factory=list)


class PremiseRecoveryOutput(BaseModel):
    """Structured batch of recovered implicit premises from System 2 extraction.

    Parameters
    ----------
    recovered_premises : list of RecoveredImplicitPremise
        Ordered list of recovered implicit premises or warrants.
    """

    recovered_premises: list[RecoveredImplicitPremise] = Field(default_factory=list)


def _stable_recovered_id(
    deficit_id: str, chunk_id: str, local_id: str, text: str
) -> str:
    """Compute a deterministic identifier for a recovered implicit premise atom."""
    payload = f"{deficit_id}:{chunk_id}:{local_id}:{text.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:14]
    return f"ac_enthymeme_{digest}"


class LLMTheoryGuidedPremiseRecoverer:
    """Theory-conditioned premise recoverer for ``ENTHYMEME_GAP`` deficits.

    Integrates System 1 ``DecisionEngine`` triage gating, managed prompt
    bundles, entity linking with ``EpistemicCurationLedger`` compliance,
    calibrated ``ModalStrengthResolver`` prior estimation, and localized
    ``ARCClassifier`` relation discovery.

    Parameters
    ----------
    llm : StructuredLLM or StructuredPredictable or Any or None, optional
        Structured LLM adapter or LlamaIndex LLM facade used for premise gleaning.
    arc_classifier : ARCClassifier or None, optional
        Optional argument relation classifier run strictly on delta pairs
        ``(recovered_premise, target_atom_and_neighbors)``.
    global_extractor : GlobalRelationExtractor or None, optional
        Optional global extractor forwarded to ``arc_classifier.classify_pairs``.
    entity_linker : EntityLinker or None, optional
        Optional entity linker associating premise mentions with L2 entities.
    modal_resolver : ModalStrengthResolver or None, optional
        Optional modal prior resolver applied to newly recovered atoms.
    decision_engine : DecisionEngine or None, optional
        Optional System 1 engine gating enthymeme recoverability before LLM calls.
    config : HermeneuticRefinementConfig or None, optional
        Configuration supplying prompt bundles, decoding strategy, and thresholds.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.
    prompts : StructuredPromptBundle or str or None, optional
        Optional prompt bundle override overriding ``config.premise_recovery_prompts``.
    strategy : Any, optional
        Optional decoding strategy override overriding
        ``config.premise_recovery_decoding_strategy``.
    confidence_threshold : float, default 0.5
        Minimum confidence required to retain a recovered implicit premise.
    """

    def __init__(
        self,
        llm: StructuredLLM | Any | None = None,
        *,
        arc_classifier: ARCClassifier | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
        entity_linker: EntityLinker | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        decision_engine: DecisionEngine | None = None,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        self.llm: StructuredPredictable | None = normalize_structured_llm(llm)
        self.arc_classifier = arc_classifier
        self.global_extractor = global_extractor
        self.entity_linker = entity_linker
        self.modal_resolver = modal_resolver
        self.decision_engine = decision_engine
        self.config = config or HermeneuticRefinementConfig()
        self.schema = schema

        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        elif isinstance(prompts, str):
            self.prompts = self.config.premise_recovery_prompts.model_copy(
                update={"direct_template": prompts}
            )
        else:
            self.prompts = self.config.premise_recovery_prompts

        self.strategy = (
            strategy
            if strategy is not None
            else self.config.premise_recovery_decoding_strategy
        )
        self.confidence_threshold = float(confidence_threshold)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            JSON-serializable snapshot of prompt, threshold, and sub-components.
        """
        strategy_str = (
            self.strategy.value
            if isinstance(self.strategy, Enum)
            else str(self.strategy)
        )
        return {
            "class": self.__class__.__name__,
            "schema_version": self.schema.version,
            "confidence_threshold": self.confidence_threshold,
            "strategy": strategy_str,
            "use_decision_engine_gating": self.config.use_decision_engine_gating,
            "decision_confidence_threshold": self.config.decision_confidence_threshold,
            "prompts": self.prompts.fingerprint(),
            "llm": (
                self.llm.fingerprint()
                if isinstance(self.llm, Fingerprintable)
                else fingerprint_method(self.llm)
            ),
            "arc_classifier": (
                self.arc_classifier.fingerprint()
                if isinstance(self.arc_classifier, Fingerprintable)
                else fingerprint_method(self.arc_classifier)
            ),
            "global_extractor": (
                self.global_extractor.fingerprint()
                if isinstance(self.global_extractor, Fingerprintable)
                else fingerprint_method(self.global_extractor)
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

    @property
    def is_available(self) -> bool:
        """Return True when an LLM adapter is wired for System 2 premise recovery.

        Returns
        -------
        bool
            True if ``self.llm`` is not None, False otherwise.
        """
        return self.llm is not None

    async def recover_premises(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Recover implicit premises for an ``ENTHYMEME_GAP`` deficit.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``ENTHYMEME_GAP`` deficit naming target chunks, atoms, and
            theory-lens expectations.
        state : EpistemicStateView
            Cumulative epistemic state view providing chunks, entities, and atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for event lineage and curation ledger.

        Returns
        -------
        RefinementDelta
            Delta containing newly recovered implicit ``TheoryAtom``s,
            ``TheoryRelation``s, optional linked ``L2Entity`` updates, and
            resolved deficit IDs.
        """
        if deficit.deficit_kind != EpistemicDeficitKind.ENTHYMEME_GAP:
            raise ValueError(
                f"LLMTheoryGuidedPremiseRecoverer only handles ENTHYMEME_GAP deficits "
                f"(got {deficit.deficit_kind.value})"
            )

        if self.llm is None:
            raise ValueError(
                "LLMTheoryGuidedPremiseRecoverer requires a configured StructuredLLM "
                "instance to recover implicit premises."
            )

        next_pass = resolve_refinement_pass(context, deficit)
        run_id = context.run_id if context is not None else "unknown"
        comp_name = type(self).__name__
        curation_ledger = resolve_curation_ledger(context)

        all_atoms = list(state.canonical_theory_atoms or state.theory_atoms)
        all_relations = list(state.canonical_theory_relations or state.theory_relations)
        atoms_by_id = {a.id: a for a in all_atoms}
        chunks_by_id = {c.id: c for c in state.chunks}
        entities_by_id = {e.id: e for e in state.entities}

        with refinement_component_scope(
            comp_name,
            context,
            input_description=f"deficit={deficit.deficit_id}",
        ) as outcome:
            if self.llm is None:
                logger.warning(
                    "LLMTheoryGuidedPremiseRecoverer invoked without LLM backend for %s",
                    deficit.deficit_id,
                )
                outcome.output_description = "skipped_no_llm"
                return RefinementDelta(refinement_pass=next_pass)

            target_atoms = [
                atoms_by_id[aid]
                for aid in deficit.target_atom_ids
                if aid in atoms_by_id
            ]
            target_chunk_ids = dedup_preserve_order(
                [
                    *deficit.target_chunk_ids,
                    *(a.source_chunk_id for a in target_atoms),
                ]
            )
            available_chunk_ids = [
                cid for cid in target_chunk_ids if cid in chunks_by_id
            ]
            if not available_chunk_ids or not target_atoms:
                outcome.output_description = "no_target_chunks_or_atoms"
                return RefinementDelta(refinement_pass=next_pass)

            target_chunk_set = set(available_chunk_ids)
            source_chunks_str = "\n\n".join(
                f"[{cid}]\n{chunks_by_id[cid].text}" for cid in available_chunk_ids
            )
            target_claims_str = "\n".join(
                f"- [{a.id}] ({a.component_type}, chunk={a.source_chunk_id}): {a.text}"
                for a in target_atoms
            )

            # System 1 DecisionEngine pre-gate before expensive System 2 LLM extraction.
            if self.prompts.decision_template:
                triage = await evaluate_binary_triage(
                    self.decision_engine,
                    state_payload=(
                        f"Theory: {deficit.theory_id or 'unspecified'}\n"
                        f"Rationale: {deficit.rationale}\n"
                        f"Target Claims:\n{target_claims_str}\n"
                        f"Passages:\n{source_chunks_str[:1600]}"
                    ),
                    question=self.prompts.decision_template,
                    run_id=run_id,
                    phase_key="refinement_premise_recovery",
                    item_id=deficit.deficit_id,
                    config=self.config,
                )
                if not triage.value:
                    outcome.output_description = "gated_out_by_decision_engine"
                    return RefinementDelta(refinement_pass=next_pass)

            existing_in_chunks = [
                a for a in all_atoms if a.source_chunk_id in target_chunk_set
            ]
            existing_atoms_str = (
                "\n".join(
                    f"- [{a.id}] ({a.component_type}, chunk={a.source_chunk_id}): {a.text}"
                    for a in existing_in_chunks
                )
                or "None."
            )
            scoped_entities = [
                ent
                for ent in state.entities
                if any(cid in target_chunk_set for cid in ent.source_chunk_ids)
                or ent.id in deficit.target_entity_ids
            ]
            chunk_entities_str = (
                "\n".join(f"- [{e.id}] ({e.label}) {e.name}" for e in scoped_entities)
                or "None."
            )

            result: PremiseRecoveryOutput = await self.llm.predict_structured(
                PremiseRecoveryOutput,
                self.prompts,
                strategy=self.strategy,
                theory_id=deficit.theory_id or "unspecified",
                theory_lens=compact_theory_lens(deficit.theory_lens),
                rationale=deficit.rationale or "Missing explicit premises.",
                target_claims=target_claims_str,
                existing_atoms=existing_atoms_str,
                chunk_entities=chunk_entities_str,
                component_types=self.schema.component_types_str(),
                argument_relation_types=self.schema.argument_relation_types_str(),
                source_chunks=source_chunks_str,
                target_chunk_ids=", ".join(available_chunk_ids),
            )

            primary_target_id = target_atoms[0].id
            target_id_set = {a.id for a in target_atoms}
            default_chunk_id = available_chunk_ids[0]
            default_comp_type = self.schema.default_hypothesis_component_type()

            norm_existing_texts = {
                " ".join(a.text.lower().split()) for a in existing_in_chunks
            }
            seen_rel_keys = {
                (r.source_id, r.relation_type, r.target_id) for r in all_relations
            }

            recovered_atoms: list[TheoryAtom] = []
            recovered_relations: list[TheoryRelation] = []
            recovered_entities: list[L2Entity] = []
            seen_entity_updates: set[str] = set()
            reader = state.to_graph_reader()

            for cand in result.recovered_premises:
                text = cand.text.strip()
                if not text or float(cand.confidence) < self.confidence_threshold:
                    continue
                norm_text = " ".join(text.lower().split())
                if norm_text in norm_existing_texts:
                    continue
                norm_existing_texts.add(norm_text)

                chunk_id = (
                    cand.source_chunk_id
                    if cand.source_chunk_id in target_chunk_set
                    else default_chunk_id
                )
                target_id = (
                    cand.target_atom_id
                    if cand.target_atom_id in target_id_set
                    else primary_target_id
                )
                comp_type = resolve_schema_component_type(
                    cand.component_type,
                    self.schema,
                    fallback=default_comp_type,
                )
                rel_type = resolve_schema_relation_type(cand.relation_type, self.schema)
                atom_id = _stable_recovered_id(
                    deficit.deficit_id, chunk_id, cand.local_id, text
                )
                chunk_text = (
                    chunks_by_id[chunk_id].text if chunk_id in chunks_by_id else ""
                )

                # Resolve entity links via EntityLinker / scoped entities.
                linked_entity_ids = entity_ids_matching_text(text, scoped_entities)
                for raw_ename in cand.entity_names:
                    clean_ename = raw_ename.strip()
                    if not clean_ename:
                        continue
                    ent_obj, should_emit = await resolve_grounding_entity(
                        name=clean_ename,
                        label=self.schema.node_types[0]
                        if self.schema.node_types
                        else "Concept",
                        description=None,
                        chunk_id=chunk_id,
                        chunk_text=chunk_text,
                        confidence=float(cand.confidence),
                        entities_by_id=entities_by_id,
                        entity_linker=self.entity_linker,
                        graph_reader=reader,
                        curation_ledger=curation_ledger,
                        schema=self.schema,
                    )
                    if ent_obj.id not in linked_entity_ids:
                        linked_entity_ids.append(ent_obj.id)
                    if should_emit and ent_obj.id not in seen_entity_updates:
                        seen_entity_updates.add(ent_obj.id)
                        recovered_entities.append(ent_obj)
                        reader.register_entity(ent_obj)

                atom_params: dict[str, Any] = {}
                if deficit.theory_id:
                    atom_params["theory_id"] = deficit.theory_id

                scope_val = (
                    cand.scope_type
                    if cand.scope_type in self.schema.scope_types
                    else None
                )
                status_val = (
                    cand.epistemic_status
                    if cand.epistemic_status in self.schema.epistemic_statuses
                    else None
                )

                new_atom = TheoryAtom(
                    id=atom_id,
                    text=text,
                    component_type=comp_type,
                    source_chunk_id=chunk_id,
                    confidence=float(cand.confidence),
                    modal_prior=max(0.0, min(1.0, float(cand.confidence))),
                    entity_ids=dedup_preserve_order(linked_entity_ids),
                    scope_type=scope_val,
                    epistemic_status=status_val,
                    intensional_mode=cand.intensional_mode,
                    attributed_to=cand.attributed_to,
                    parameters=atom_params,
                )
                new_atom = await resolve_atom_modal_prior(
                    new_atom,
                    self.modal_resolver,
                    context_text=chunk_text or None,
                )
                recovered_atoms.append(new_atom)
                reader.register_theory_atom(new_atom)

                edge_weight = max(0.0, min(1.0, float(cand.weight)))
                target_chunk = atoms_by_id[target_id].source_chunk_id
                rel_scope = "local" if target_chunk == chunk_id else "global"
                rel = TheoryRelation(
                    source_id=atom_id,
                    target_id=target_id,
                    relation_type=rel_type,
                    confidence=float(cand.confidence),
                    weight=edge_weight,
                    active_weight=edge_weight,
                    scope=rel_scope,
                )
                rkey = (rel.source_id, rel.relation_type, rel.target_id)
                if rkey not in seen_rel_keys:
                    seen_rel_keys.add(rkey)
                    recovered_relations.append(rel)

            # Run ARCClassifier strictly on delta pairs (new_premise, target & 1-hop neighbors).
            if self.arc_classifier is not None and recovered_atoms and target_atoms:
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
                [deficit.deficit_id] if (recovered_atoms or recovered_relations) else []
            )
            outcome.output_description = (
                f"atoms={len(recovered_atoms)}, relations={len(recovered_relations)}, "
                f"entities={len(recovered_entities)}"
            )
            return RefinementDelta(
                entities=recovered_entities,
                theory_atoms=recovered_atoms,
                theory_relations=recovered_relations,
                resolved_deficit_ids=resolved_ids,
                refinement_pass=next_pass,
            )


__all__ = [
    "LLMTheoryGuidedPremiseRecoverer",
    "PremiseRecoveryOutput",
    "RecoveredImplicitPremise",
]
