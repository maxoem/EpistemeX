"""DecisionEngine-backed and Cascading Argument Mining Classifiers.

Provides System 1 fast triage and cascading classifiers for Argument Component
Classification (ACC) and Argument Relation Classification (ARC) using calibrated
DecisionEngine protocols.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Literal, Protocol, runtime_checkable

from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom, TheoryRelation
from episteme_pipeline.decision.cascade import (
    TriageDecision,
    should_audit_deterministically,
)
from episteme_pipeline.phases.phase4_argument_mining.pairing import (
    build_cross_chunk_candidate_pairs,
    stable_component_id,
)
from episteme_pipeline.prompts.default_prompts import (
    DECISION_ACC_CRITERIA,
    DECISION_ACC_QUESTION,
    DECISION_ARC_CRITERIA,
    DECISION_ARC_QUESTION,
    DECISION_INTENSIONAL_MODE_CRITERIA,
    DECISION_INTENSIONAL_MODE_QUESTION,
)
from episteme_pipeline.prompts.input_formatters import format_arc_decision_pair_state
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.argument_mining import ACCClassifier, ARCClassifier
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
)
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    GlobalRelationExtractor,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class PairTriageARCClassifier(Protocol):
    """Protocol for System 1 ARC classifiers supporting per-pair conformal triage."""

    async def classify_pairs_with_triage(
        self,
        pairs: list[tuple[TheoryAtom, TheoryAtom]],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
        audit_rate: float = 0.0,
        run_seed: str = "phase4_arc",
    ) -> tuple[list[TheoryRelation], list[tuple[TheoryAtom, TheoryAtom]]]:
        """Classify candidate pairs and return confirmed edges plus escalated pairs.

        Parameters
        ----------
        pairs : list of tuple of (TheoryAtom, TheoryAtom)
            Candidate argument component pairs to evaluate.
        graph_store : GraphReader
            Reader for graph context.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional extractor for structural neighborhoods.
        schema : SchemaConfig or None, default None
            Schema taxonomy.
        audit_rate : float, default 0.0
            Deterministic stochastic audit rate.
        run_seed : str, default "phase4_arc"
            Deterministic seed for audit hashing.

        Returns
        -------
        tuple of (list of TheoryRelation, list of tuple of (TheoryAtom, TheoryAtom))
            Confirmed System 1 relations and pairs escalated to System 2.
        """
        ...


def _extract_adu_text(tagged_text: str, adu_id: str) -> str:
    """Extract the plain text content of an Argumentative Discourse Unit from tagged text.

    Parameters
    ----------
    tagged_text : str
        The text containing `<ACn>...</ACn>` markup.
    adu_id : str
        The tag identifier (e.g. "AC1").

    Returns
    -------
    str
        Extracted plain text span of the component, or fallback placeholder.
    """
    pattern = rf"<{adu_id}>(.*?)(?:</{adu_id}>|</AC>|<AC|\Z)"
    match = re.search(pattern, tagged_text, re.DOTALL)
    if match and match.group(1).strip():
        return match.group(1).strip()
    return f"[{adu_id}]"


class JevACCClassifier(ACCClassifier):
    """Argument Component Classifier backed by a System 1 DecisionEngine.

    Evaluates each pre-segmented Argumentative Discourse Unit (ADU) against
    the configured schema component types using calibrated categorical choice.

    Parameters
    ----------
    decision_engine : DecisionEngine
        The calibrated decision engine instance.
    prompts : StructuredPromptBundle or None, default None
        Optional prompt bundle carrying classification instructions or rubrics.
    modal_resolver : ModalStrengthResolver or None, default None
        Optional resolver for proposition modal prior strength.
    infer_intensional_mode : bool, default False
        Whether to evaluate an additional ``DecisionEngine`` prompt to classify
        intensional framing (``asserted``, ``suppositional``, ``historical``,
        ``attributed``). Raises ``ValueError`` on ``"attributed"`` so cascading
        orchestrators escalate to an LLM capable of extracting speaker identity.
    intensional_prompts : StructuredPromptBundle or None, default None
        Optional prompt bundle supplying custom intensional mode decision templates
        and criteria; defaults to ``DECISION_INTENSIONAL_MODE_QUESTION`` and
        ``DECISION_INTENSIONAL_MODE_CRITERIA``.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        prompts: StructuredPromptBundle | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
        infer_intensional_mode: bool = False,
        intensional_prompts: StructuredPromptBundle | None = None,
        conformal_alpha: float = 0.05,
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
        self.modal_resolver = modal_resolver
        self.conformal_alpha = conformal_alpha
        self.intensional_prompts = intensional_prompts
        if prompts is not None:
            question = prompts.decision_template
            criteria = prompts.decision_criteria
        else:
            question = DECISION_ACC_QUESTION
            criteria = DECISION_ACC_CRITERIA

        if not question or not question.strip():
            raise ValueError("No decision prompt configured for JevACCClassifier.")
        self.decision_template = question.strip()
        self.criteria = criteria or DECISION_ACC_CRITERIA

        self.infer_intensional_mode = infer_intensional_mode or (
            intensional_prompts is not None
        )
        int_question = (
            intensional_prompts.decision_template
            if intensional_prompts and intensional_prompts.decision_template
            else DECISION_INTENSIONAL_MODE_QUESTION
        )
        self.intensional_question = int_question.strip()
        raw_int_criteria = (
            intensional_prompts.decision_criteria
            if intensional_prompts and intensional_prompts.decision_criteria
            else DECISION_INTENSIONAL_MODE_CRITERIA
        )
        self.intensional_criteria: dict[str, str] = (
            dict(raw_int_criteria)
            if isinstance(raw_int_criteria, dict)
            else dict(DECISION_INTENSIONAL_MODE_CRITERIA)
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic Jev ACC classifier configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing prompt template, intensional mode flags,
            conformal alpha, and sub-component fingerprints.
        """
        de_fp = (
            self.decision_engine.fingerprint()
            if isinstance(self.decision_engine, Fingerprintable)
            else fingerprint_method(self.decision_engine)
        )
        modal_fp = (
            self.modal_resolver.fingerprint()
            if self.modal_resolver is not None
            and isinstance(self.modal_resolver, Fingerprintable)
            else fingerprint_method(self.modal_resolver)
        )
        prompts_fp = (
            self.prompts.fingerprint()
            if self.prompts is not None and isinstance(self.prompts, Fingerprintable)
            else None
        )
        int_prompts_fp = (
            self.intensional_prompts.fingerprint()
            if self.intensional_prompts is not None
            and isinstance(self.intensional_prompts, Fingerprintable)
            else None
        )
        return {
            "class": self.__class__.__name__,
            "decision_template": self.decision_template,
            "infer_intensional_mode": self.infer_intensional_mode,
            "intensional_question": (
                self.intensional_question if self.infer_intensional_mode else None
            ),
            "conformal_alpha": self.conformal_alpha,
            "decision_engine": de_fp,
            "modal_resolver": modal_fp,
            "prompts": prompts_fp,
            "intensional_prompts": int_prompts_fp,
        }

    @staticmethod
    def _bind_chunk_entities(
        adu_text: str,
        chunk_entities: list[L2Entity] | None,
    ) -> list[str]:
        """Bind chunk entities whose surface name appears in the ADU text."""
        if not chunk_entities:
            return []
        adu_lower = adu_text.lower()
        bound_ids: list[str] = []
        seen: set[str] = set()
        for entity in chunk_entities:
            name_clean = (entity.name or "").strip().lower()
            if name_clean and name_clean in adu_lower and entity.id not in seen:
                bound_ids.append(entity.id)
                seen.add(entity.id)
        return bound_ids

    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: SchemaConfig,
        chunk_entities: list[L2Entity] | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        """Classify ADUs into TheoryAtom nodes.

        Parameters
        ----------
        chunk_id : str
            Source chunk identifier.
        tagged_text : str
            Full chunk text with `<ACn>...</ACn>` markup.
        adu_ids : list of str
            List of ADU identifiers to classify.
        schema : SchemaConfig
            Schema taxonomy containing allowable component types.
        chunk_entities : list of L2Entity or None, default None
            Entities discovered in the chunk for mention binding.

        Returns
        -------
        tuple of (list of TheoryAtom, list of TheoryRelation)
            Extracted theory atoms and local relations.
        """
        atoms: list[TheoryAtom] = []
        options: dict[str, str] = {}
        for t in schema.component_types:
            if isinstance(self.criteria, dict) and t in self.criteria:
                options[t] = self.criteria[t]
            elif t in schema.component_definitions:
                options[t] = schema.component_definitions[t]
            else:
                options[t] = f"Argumentative component of type {t}"

        for adu_id in adu_ids:
            adu_text = _extract_adu_text(tagged_text, adu_id)
            state = f"Unit: {adu_text}\nContext:\n{tagged_text}"

            decision: DecisionScore = await self.decision_engine.evaluate_choice(
                state=state,
                question=f"{self.decision_template} Unit ID: {adu_id}",
                options=options,
                alpha=self.conformal_alpha,
            )

            selected_type = str(decision.selected_option) if decision.selected_option in options else schema.component_types[0]
            confidence = decision.class_probability
            if decision.prediction_set is not None and len(decision.prediction_set) != 1:
                confidence = 0.0
            empirical_accuracy = decision.empirical_accuracy
            intensional_mode: Literal[
                "asserted", "attributed", "suppositional", "historical"
            ] = "asserted"
            if self.infer_intensional_mode:
                mode_decision: DecisionScore = (
                    await self.decision_engine.evaluate_choice(
                        state=state,
                        question=f"{self.intensional_question} Unit ID: {adu_id}",
                        options=self.intensional_criteria,
                        alpha=self.conformal_alpha,
                    )
                )
                candidate_mode = str(mode_decision.selected_option).strip().lower()
                if candidate_mode == "attributed":
                    raise ValueError(
                        "JevACCClassifier cannot extract open-ended speaker attribution "
                        "('attributed_to') for attributed claims; use LLMACCClassifier or "
                        "CascadingACCClassifier with an LLM fallback."
                    )
                if (
                    mode_decision.prediction_set is not None
                    and len(mode_decision.prediction_set) != 1
                ):
                    confidence = 0.0
                elif mode_decision.class_probability is not None:
                    confidence = min(confidence, mode_decision.class_probability)
                if candidate_mode == "suppositional":
                    intensional_mode = "suppositional"
                elif candidate_mode == "historical":
                    intensional_mode = "historical"

            bound_entity_ids = self._bind_chunk_entities(adu_text, chunk_entities)
            stable_id = stable_component_id(chunk_id, adu_id)
            atom = TheoryAtom(
                id=stable_id,
                text=adu_text,
                component_type=selected_type,
                source_chunk_id=chunk_id,
                confidence=confidence,
                entity_ids=bound_entity_ids,
                **(
                    {"modal_prior": empirical_accuracy}
                    if empirical_accuracy is not None
                    else {}
                ),
                intensional_mode=intensional_mode,
            )
            if self.modal_resolver:
                resolved_mod = await self.modal_resolver.resolve_modality(atom, context=state)
                atom.modal_prior = resolved_mod
            atoms.append(atom)

        return atoms, []


class CascadingACCClassifier(ACCClassifier):
    """Cascading ACC classifier combining fast System 1 triage with generative LLM fallback.

    Executes the fast decision engine first. If calibrated empirical accuracy falls
    below the triage threshold, or if random stochastic audit triggers, escalates
    to the full generative LLM classifier for multi-unit relational inference.

    Parameters
    ----------
    fast_classifier : ACCClassifier
        The fast decision engine classifier.
    llm_classifier : ACCClassifier
        The fallback generative LLM classifier.
    config : Phase4Config or None, default None
        Optional Phase 4 configuration.
    triage_confidence_threshold : float, default 0.85
        Minimum confidence required to accept fast triage results.
    stochastic_audit_rate : float, default 0.02
        Rate at which fast triage results are audited by the LLM classifier.
    require_multi_adu_relations : bool or None, default None
        When True, multi-ADU chunks short-circuit directly to ``llm_classifier``
        before calling ``fast_classifier`` if intra-chunk relations are required.
        Defaults to ``config.require_multi_adu_relations`` (False).
    require_entity_binding : bool or None, default None
        When True, chunks carrying ``chunk_entities`` short-circuit directly to
        ``llm_classifier`` before calling ``fast_classifier``. Defaults to
        ``config.require_entity_binding`` (False).
    """

    def __init__(
        self,
        fast_classifier: ACCClassifier,
        llm_classifier: ACCClassifier,
        config: Phase4Config | None = None,
        triage_confidence_threshold: float = 0.85,
        stochastic_audit_rate: float = 0.02,
        require_multi_adu_relations: bool | None = None,
        require_entity_binding: bool | None = None,
    ) -> None:
        self.fast_classifier = fast_classifier
        self.llm_classifier = llm_classifier
        self.config = config
        self.triage_confidence_threshold = (
            config.triage_confidence_threshold
            if config is not None
            else triage_confidence_threshold
        )
        self.stochastic_audit_rate = (
            config.stochastic_audit_rate
            if config is not None
            else stochastic_audit_rate
        )
        self.require_multi_adu_relations = (
            require_multi_adu_relations
            if require_multi_adu_relations is not None
            else (
                config.require_multi_adu_relations
                if config is not None
                else False
            )
        )
        self.require_entity_binding = (
            require_entity_binding
            if require_entity_binding is not None
            else (
                config.require_entity_binding
                if config is not None
                else False
            )
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic cascading ACC classifier configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing triage confidence threshold, audit rate,
            escalation flags, and fingerprints of fast and LLM classifiers.
        """
        fast_fp = (
            self.fast_classifier.fingerprint()
            if isinstance(self.fast_classifier, Fingerprintable)
            else fingerprint_method(self.fast_classifier)
        )
        llm_fp = (
            self.llm_classifier.fingerprint()
            if isinstance(self.llm_classifier, Fingerprintable)
            else fingerprint_method(self.llm_classifier)
        )
        return {
            "class": self.__class__.__name__,
            "triage_confidence_threshold": self.triage_confidence_threshold,
            "stochastic_audit_rate": self.stochastic_audit_rate,
            "require_multi_adu_relations": self.require_multi_adu_relations,
            "require_entity_binding": self.require_entity_binding,
            "fast_classifier": fast_fp,
            "llm_classifier": llm_fp,
        }

    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: SchemaConfig,
        chunk_entities: list[L2Entity] | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        """Classify ADUs using calibrated cascade routing.

        Parameters
        ----------
        chunk_id : str
            Source chunk identifier.
        tagged_text : str
            Full chunk text with `<ACn>...</ACn>` markup.
        adu_ids : list of str
            List of ADU identifiers to classify.
        schema : SchemaConfig
            Schema taxonomy containing allowable component types.
        chunk_entities : list of L2Entity or None, default None
            Entities discovered in the chunk for mention binding.

        Returns
        -------
        tuple of (list of TheoryAtom, list of TheoryRelation)
            Extracted theory atoms and relations.
        """
        # Short-circuit before System 1 evaluation if policy mandates System 2
        # for multi-ADU relational extraction or LLM entity binding.
        if (self.require_multi_adu_relations and len(adu_ids) > 1) or (
            self.require_entity_binding and bool(chunk_entities)
        ):
            return await self.llm_classifier.classify(
                chunk_id, tagged_text, adu_ids, schema, chunk_entities
            )

        try:
            atoms, relations = await self.fast_classifier.classify(
                chunk_id, tagged_text, adu_ids, schema, chunk_entities
            )
        except ValueError as exc:
            logger.info(
                "CascadingACCClassifier escalating chunk %s to LLM: %s",
                chunk_id,
                exc,
            )
            return await self.llm_classifier.classify(
                chunk_id, tagged_text, adu_ids, schema, chunk_entities
            )

        if not atoms:
            return await self.llm_classifier.classify(
                chunk_id, tagged_text, adu_ids, schema, chunk_entities
            )

        threshold = self.triage_confidence_threshold
        audit_rate = self.stochastic_audit_rate

        is_uncertain = any(a.confidence is None or a.confidence < threshold for a in atoms)
        missing_attribution = any(
            a.intensional_mode == "attributed" and not a.attributed_to
            for a in atoms
        )
        is_audit = (
            should_audit_deterministically(chunk_id, "phase4_acc", chunk_id, audit_rate)
            if audit_rate > 0.0
            else False
        )

        if is_uncertain or is_audit or missing_attribution:
            return await self.llm_classifier.classify(
                chunk_id, tagged_text, adu_ids, schema, chunk_entities
            )

        return atoms, relations


class JevARCClassifier(ARCClassifier):
    """Global Argument Relation Classifier backed by a System 1 DecisionEngine.

    Evaluates cross-chunk component pairs against support and attack relations.

    Parameters
    ----------
    decision_engine : DecisionEngine
        The calibrated decision engine instance.
    prompts : Any or None, default None
        Optional prompt bundle carrying dialectical criteria.
    arc_mode : str, default "cascading"
        Execution mode ("cascading", "jev_only", or "multiplex").
    embedding_model : EmbeddingModel or None, default None
        Optional embedding model for candidate pair blocking.
    confidence_threshold : float, default 0.65
        Minimum confidence required to accept a predicted relation.
    max_candidates_per_component : int, default 10
        Maximum number of cross-chunk candidate partners per component.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        prompts: StructuredPromptBundle | None = None,
        arc_mode: str = "cascading",
        embedding_model: EmbeddingModel | None = None,
        confidence_threshold: float = 0.65,
        max_candidates_per_component: int = 10,
        default_inferential_warrant: float = 1.0,
        conformal_alpha: float = 0.05,
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
        self.arc_mode = arc_mode
        self.embedding_model = embedding_model
        self.confidence_threshold = confidence_threshold
        self.max_candidates_per_component = max_candidates_per_component
        self.default_inferential_warrant = default_inferential_warrant
        self.conformal_alpha = conformal_alpha

        if prompts is not None:
            question = prompts.decision_template
            criteria = prompts.decision_criteria
        else:
            question = DECISION_ARC_QUESTION
            criteria = DECISION_ARC_CRITERIA

        if not question or not question.strip():
            raise ValueError("No decision prompt configured for JevARCClassifier.")
        self.decision_template = question.strip()
        self.criteria = criteria or DECISION_ARC_CRITERIA

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic Jev ARC classifier configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing mode, thresholds, prompt template, and sub-component
            fingerprints.
        """
        de_fp = (
            self.decision_engine.fingerprint()
            if isinstance(self.decision_engine, Fingerprintable)
            else fingerprint_method(self.decision_engine)
        )
        emb_fp = (
            self.embedding_model.fingerprint()
            if self.embedding_model is not None and isinstance(self.embedding_model, Fingerprintable)
            else fingerprint_method(self.embedding_model)
        )
        return {
            "class": self.__class__.__name__,
            "arc_mode": self.arc_mode,
            "confidence_threshold": self.confidence_threshold,
            "max_candidates_per_component": self.max_candidates_per_component,
            "default_inferential_warrant": self.default_inferential_warrant,
            "conformal_alpha": self.conformal_alpha,
            "decision_template": self.decision_template,
            "decision_engine": de_fp,
            "embedding_model": emb_fp,
        }

    def _resolve_inferential_warrant(
        self,
        source_atom: TheoryAtom,
        target_atom: TheoryAtom,
    ) -> float:
        """Resolve Toulminian inferential warrant strength for a candidate relation edge.

        In Quantitative Bipolar Argumentation Frameworks (D-QBAF), mathematical edge
        weights decouple perception extraction certainty from relational warrant validity
        without conflating node-level modal strength:
        W = I(inferential_warrant) * P(stance).

        Parameters
        ----------
        source_atom : TheoryAtom
            Source premise or hypothesis component.
        target_atom : TheoryAtom
            Target claim or conclusion component.

        Returns
        -------
        float
            Inferential warrant multiplier in [0.0, 1.0].
        """
        return self.default_inferential_warrant

    def _resolve_relation_criterion(self, r_type: str, schema: SchemaConfig) -> str:
        """Resolve prompt criterion text for a relation type using schema and polarity alignment.

        Parameters
        ----------
        r_type : str
            Canonical relation type identifier.
        schema : SchemaConfig
            Schema configuration providing relation definitions and polarities.

        Returns
        -------
        str
            Descriptive criterion text for decision engine choice prompts.
        """
        if isinstance(self.criteria, dict) and r_type in self.criteria:
            return self.criteria[r_type]
        if r_type in schema.argument_relation_definitions:
            return schema.argument_relation_definitions[r_type]
        if isinstance(self.criteria, dict):
            r_pol = schema.relation_polarities.get(r_type, 0)
            if r_pol != 0:
                for crit_key, crit_text in self.criteria.items():
                    if schema.relation_polarities.get(crit_key, 0) == r_pol:
                        return crit_text
        return f"Argumentative relation {r_type}"

    def _resolve_neutral_criterion(self) -> str:
        """Resolve prompt text for the neutral non-relation option.

        Returns
        -------
        str
            Criterion description for dialectical neutrality.
        """
        if isinstance(self.criteria, dict) and "NEUTRAL" in self.criteria:
            return self.criteria["NEUTRAL"]
        return "No direct argumentative relation between source and target."

    def _build_choice_options(self, schema: SchemaConfig) -> dict[str, str]:
        """Build decision engine choice options and definitions for candidate schema relations.

        Parameters
        ----------
        schema : SchemaConfig
            Schema configuration defining argument relations and polarities.

        Returns
        -------
        dict[str, str]
            Mapping from relation type (and NEUTRAL) to criterion description text.
        """
        options: dict[str, str] = {
            r_type: self._resolve_relation_criterion(r_type, schema)
            for r_type in schema.argument_relation_types
        }
        options["NEUTRAL"] = self._resolve_neutral_criterion()
        return options

    async def classify_pair_decision(
        self,
        source_atom: TheoryAtom,
        target_atom: TheoryAtom,
        schema: SchemaConfig,
        audit_rate: float = 0.0,
        run_seed: str = "phase4_arc",
    ) -> TriageDecision[list[TheoryRelation]]:
        """Evaluate dialectical stance for a pair as a calibrated :class:`TriageDecision`.

        Parameters
        ----------
        source_atom : TheoryAtom
            The source argument component.
        target_atom : TheoryAtom
            The target argument component.
        schema : SchemaConfig
            Schema configuration defining allowable relation types.
        audit_rate : float, default 0.0
            Deterministic stochastic audit rate.
        run_seed : str, default "phase4_arc"
            Deterministic seed for audit hashing.

        Returns
        -------
        TriageDecision of list of TheoryRelation
            Calibrated triage decision envelope containing predicted relations,
            empirical accuracy, prediction set, ambiguity status, and audit flag.
        """
        state = format_arc_decision_pair_state(source_atom, target_atom)
        pair_key = f"{source_atom.id}:{target_atom.id}"
        is_audit = (
            should_audit_deterministically(run_seed, "phase4_arc", pair_key, audit_rate)
            if audit_rate > 0.0
            else False
        )

        if self.arc_mode == "multiplex":
            rels: list[TheoryRelation] = []
            is_ambiguous = False
            acc_vals: list[float] = []
            for r_type in schema.argument_relation_types:
                rel_def = schema.argument_relation_definitions.get(
                    r_type, f"relation {r_type.lower()}"
                )
                if "{relation_type}" in self.decision_template:
                    question = self.decision_template.format(relation_type=r_type.lower())
                else:
                    question = (
                        f"Does the source statement have the following relation to the "
                        f"target statement: '{r_type}' ({rel_def})?"
                    )

                noul_decision: DecisionNoulResult = await self.decision_engine.evaluate_noul(
                    state=state,
                    question=question,
                )
                acc_vals.append(float(noul_decision.empirical_accuracy))
                if (
                    noul_decision.probability < self.confidence_threshold
                    and noul_decision.probability > (1.0 - self.confidence_threshold)
                ):
                    is_ambiguous = True
                elif noul_decision.passed and noul_decision.probability >= self.confidence_threshold:
                    warrant = self._resolve_inferential_warrant(source_atom, target_atom)
                    eff_w = float(warrant * noul_decision.probability)
                    rels.append(
                        TheoryRelation(
                            source_id=source_atom.id,
                            target_id=target_atom.id,
                            relation_type=r_type,
                            confidence=noul_decision.probability,
                            scope="global",
                            weight=eff_w,
                            perception_stance_prob=noul_decision.probability,
                            perception_empirical_acc=noul_decision.empirical_accuracy,
                            inferential_warrant=warrant,
                            effective_weight=eff_w,
                            decision_engine_provider="jev",
                        )
                    )
            return TriageDecision(
                value=[] if (is_ambiguous or is_audit) else rels,
                decision=None,
                empirical_accuracy=min(acc_vals) if acc_vals else 1.0,
                prediction_set=[r.relation_type for r in rels],
                is_ambiguous=is_ambiguous,
                is_audit=is_audit,
            )

        options = self._build_choice_options(schema)
        decision: DecisionScore = await self.decision_engine.evaluate_choice(
            state=state,
            question=self.decision_template,
            options=options,
            alpha=self.conformal_alpha,
        )

        pred_set = decision.prediction_set
        is_ambiguous = (
            (len(pred_set) != 1 or decision.class_probability < self.confidence_threshold)
            if pred_set is not None
            else decision.class_probability < self.confidence_threshold
        )

        if is_ambiguous or is_audit:
            return TriageDecision(
                value=[],
                decision=decision,
                empirical_accuracy=decision.empirical_accuracy,
                prediction_set=list(pred_set) if pred_set is not None else [],
                is_ambiguous=is_ambiguous,
                is_audit=is_audit,
            )

        selected = str(decision.selected_option) if decision.selected_option else "NEUTRAL"
        resolved_type = schema.resolve_relation_type(selected)

        if resolved_type and decision.class_probability >= self.confidence_threshold:
            warrant = self._resolve_inferential_warrant(source_atom, target_atom)
            eff_w = float(warrant * decision.class_probability)
            rels = [
                TheoryRelation(
                    source_id=source_atom.id,
                    target_id=target_atom.id,
                    relation_type=resolved_type,
                    confidence=decision.class_probability,
                    scope="global",
                    weight=eff_w,
                    perception_stance_prob=decision.class_probability,
                    perception_empirical_acc=decision.empirical_accuracy,
                    inferential_warrant=warrant,
                    effective_weight=eff_w,
                    decision_engine_provider="jev",
                    calibrated_confidence=decision.empirical_accuracy or decision.class_probability,
                )
            ]
            return TriageDecision(
                value=rels,
                decision=decision,
                empirical_accuracy=decision.empirical_accuracy,
                prediction_set=list(pred_set) if pred_set is not None else [selected],
                is_ambiguous=False,
                is_audit=False,
            )

        return TriageDecision(
            value=[],
            decision=decision,
            empirical_accuracy=decision.empirical_accuracy,
            prediction_set=list(pred_set) if pred_set is not None else [selected],
            is_ambiguous=False,
            is_audit=False,
        )

    async def classify_pair_with_triage(
        self,
        source_atom: TheoryAtom,
        target_atom: TheoryAtom,
        schema: SchemaConfig,
        audit_rate: float = 0.0,
        run_seed: str = "phase4_arc",
    ) -> tuple[list[TheoryRelation], bool]:
        """Classify dialectical stance for a pair, returning relations and escalation flag.

        Parameters
        ----------
        source_atom : TheoryAtom
            The source argument component.
        target_atom : TheoryAtom
            The target argument component.
        schema : SchemaConfig
            Schema configuration defining allowable relation types.
        audit_rate : float, default 0.0
            Deterministic stochastic audit rate.
        run_seed : str, default "phase4_arc"
            Deterministic seed for audit hashing.

        Returns
        -------
        tuple of (list of TheoryRelation, bool)
            Extracted relations and boolean flag indicating whether the pair was escalated
            to System 2 (due to conformal ambiguity, low confidence, or deterministic audit).
        """
        triage = await self.classify_pair_decision(
            source_atom,
            target_atom,
            schema,
            audit_rate=audit_rate,
            run_seed=run_seed,
        )
        return triage.value, (triage.is_ambiguous or triage.is_audit)

    async def classify_pair(
        self,
        source_atom: TheoryAtom,
        target_atom: TheoryAtom,
        schema: SchemaConfig,
    ) -> list[TheoryRelation]:
        """Classify the dialectical stance between a candidate pair of atoms.

        Parameters
        ----------
        source_atom : TheoryAtom
            The source argument component.
        target_atom : TheoryAtom
            The target argument component.
        schema : SchemaConfig
            Schema configuration defining allowable relation types.

        Returns
        -------
        list of TheoryRelation
            Predicted relations between the atoms.
        """
        rels, _ = await self.classify_pair_with_triage(source_atom, target_atom, schema)
        return rels

    async def classify_pairs_with_triage(
        self,
        pairs: list[tuple[TheoryAtom, TheoryAtom]],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
        audit_rate: float = 0.0,
        run_seed: str = "phase4_arc",
    ) -> tuple[list[TheoryRelation], list[tuple[TheoryAtom, TheoryAtom]]]:
        """Classify specific candidate pairs with System 1 triage and escalation.

        Parameters
        ----------
        pairs : list of tuple of (TheoryAtom, TheoryAtom)
            Candidate argument component pairs to evaluate.
        graph_store : GraphReader
            Reader for graph context.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional extractor for structural neighborhoods.
        schema : SchemaConfig or None, default None
            Schema taxonomy.
        audit_rate : float, default 0.0
            Deterministic stochastic audit rate.
        run_seed : str, default "phase4_arc"
            Deterministic seed for audit hashing.

        Returns
        -------
        tuple of (list of TheoryRelation, list of tuple of (TheoryAtom, TheoryAtom))
            Confirmed System 1 relations and pairs escalated to System 2.
        """
        del graph_store, global_extractor
        if not pairs:
            return [], []

        effective_schema = schema or SchemaConfig()
        tasks = [
            self.classify_pair_decision(
                a,
                b,
                effective_schema,
                audit_rate=audit_rate,
                run_seed=run_seed,
            )
            for a, b in pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        confirmed_relations: list[TheoryRelation] = []
        escalated_pairs: list[tuple[TheoryAtom, TheoryAtom]] = []

        for (a, b), res in zip(pairs, results):
            if isinstance(res, Exception):
                logger.warning(
                    "JevARC pair classification failed for (%s, %s): %s", a.id, b.id, res
                )
                escalated_pairs.append((a, b))
            elif isinstance(res, TriageDecision):
                if res.is_ambiguous or res.is_audit:
                    escalated_pairs.append((a, b))
                else:
                    confirmed_relations.extend(res.value)

        return confirmed_relations, escalated_pairs

    async def classify_pairs(
        self,
        pairs: list[tuple[TheoryAtom, TheoryAtom]],
        graph_store: GraphReader,
        schema: SchemaConfig | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
    ) -> list[TheoryRelation]:
        """Classify specific candidate component pairs using the decision engine.

        Parameters
        ----------
        pairs : list of tuple of (TheoryAtom, TheoryAtom)
            Candidate argument component pairs to evaluate.
        graph_store : GraphReader
            Reader for graph context.
        schema : SchemaConfig or None, optional
            Schema taxonomy. If None, defaults to ``SchemaConfig()``.
        global_extractor : GlobalRelationExtractor or None, optional
            Optional extractor for structural neighborhoods.

        Returns
        -------
        list of TheoryRelation
            Predicted argument relations for the specified pairs.
        """
        confirmed, _ = await self.classify_pairs_with_triage(
            pairs=pairs,
            graph_store=graph_store,
            global_extractor=global_extractor,
            schema=schema,
            audit_rate=0.0,
        )
        return confirmed

    async def classify_global_with_triage(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
        audit_rate: float = 0.0,
        run_seed: str = "phase4_arc",
    ) -> tuple[list[TheoryRelation], list[tuple[TheoryAtom, TheoryAtom]]]:
        """Classify cross-chunk pairs using System 1 triage, returning confirmed relations and escalated pairs.

        Parameters
        ----------
        local_components : list of TheoryAtom
            All argument components available.
        local_relations : list of TheoryRelation
            Intra-chunk relations previously extracted.
        graph_store : GraphReader
            Reader for graph context.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional extractor for structural neighborhoods.
        schema : SchemaConfig or None, default None
            Schema taxonomy.
        audit_rate : float, default 0.0
            Deterministic stochastic audit rate.
        run_seed : str, default "phase4_arc"
            Deterministic seed for audit hashing.

        Returns
        -------
        tuple of (list of TheoryRelation, list of tuple of (TheoryAtom, TheoryAtom))
            (confirmed_relations, escalated_pairs).
        """
        del local_relations
        effective_schema = schema or SchemaConfig()
        pairs = self._get_cross_chunk_pairs(local_components, effective_schema)
        return await self.classify_pairs_with_triage(
            pairs=pairs,
            graph_store=graph_store,
            global_extractor=global_extractor,
            schema=effective_schema,
            audit_rate=audit_rate,
            run_seed=run_seed,
        )

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]:
        """Classify cross-chunk argument relations using the decision engine.

        Parameters
        ----------
        local_components : list of TheoryAtom
            All argument components available in the corpus.
        local_relations : list of TheoryRelation
            Intra-chunk relations previously extracted.
        graph_store : GraphReader
            Reader for graph context.
        global_extractor : GlobalRelationExtractor | None, optional
            Optional extractor for structural contexts.
        schema : SchemaConfig | None, optional
            Schema taxonomy. If None, defaults to SchemaConfig().

        Returns
        -------
        list of TheoryRelation
            Predicted global cross-chunk argument relations.
        """
        confirmed, _ = await self.classify_global_with_triage(
            local_components=local_components,
            local_relations=local_relations,
            graph_store=graph_store,
            global_extractor=global_extractor,
            schema=schema,
            audit_rate=0.0,
        )
        return confirmed

    def _get_cross_chunk_pairs(
        self, components: list[TheoryAtom], schema: SchemaConfig
    ) -> list[tuple[TheoryAtom, TheoryAtom]]:
        """Pair argument components across different source chunks."""
        return build_cross_chunk_candidate_pairs(
            components, schema, self.max_candidates_per_component
        )


class CascadingARCClassifier(ARCClassifier):
    """Cascading ARC classifier combining fast pair evaluation with LLM subgraph reasoning.

    Executes the fast JevARCClassifier first. If no relations are predicted or stochastic
    auditing triggers, delegates the pair candidates to the full TAGARCClassifier.

    Parameters
    ----------
    fast_classifier : ARCClassifier
        Fast decision engine ARC classifier.
    llm_classifier : ARCClassifier
        Generative TAG ARC classifier.
    config : Phase4Config or None, default None
        Optional Phase 4 configuration.
    stochastic_audit_rate : float, default 0.02
        Rate at which fast triage results are audited by the LLM classifier.
    """

    def __init__(
        self,
        fast_classifier: ARCClassifier,
        llm_classifier: ARCClassifier,
        config: Phase4Config | None = None,
        stochastic_audit_rate: float = 0.02,
    ) -> None:
        self.fast_classifier = fast_classifier
        self.llm_classifier = llm_classifier
        self.config = config
        self.stochastic_audit_rate = (
            config.stochastic_audit_rate
            if config is not None
            else stochastic_audit_rate
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic cascading ARC classifier configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing audit rate and fingerprints of fast and LLM classifiers.
        """
        fast_fp = (
            self.fast_classifier.fingerprint()
            if isinstance(self.fast_classifier, Fingerprintable)
            else fingerprint_method(self.fast_classifier)
        )
        llm_fp = (
            self.llm_classifier.fingerprint()
            if isinstance(self.llm_classifier, Fingerprintable)
            else fingerprint_method(self.llm_classifier)
        )
        return {
            "class": self.__class__.__name__,
            "stochastic_audit_rate": self.stochastic_audit_rate,
            "fast_classifier": fast_fp,
            "llm_classifier": llm_fp,
        }

    async def classify_pairs(
        self,
        pairs: list[tuple[TheoryAtom, TheoryAtom]],
        graph_store: GraphReader,
        schema: SchemaConfig | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
    ) -> list[TheoryRelation]:
        """Classify specific candidate pairs via per-item System 1 -> System 2 cascade.

        Executes ``fast_classifier`` over ``pairs`` without re-scanning the corpus,
        escalating only ambiguous, low-confidence, or deterministically audited
        pairs to ``llm_classifier.classify_pairs(...)``.

        Parameters
        ----------
        pairs : list of tuple of (TheoryAtom, TheoryAtom)
            Candidate argument component pairs to evaluate.
        graph_store : GraphReader
            Reader for graph context.
        schema : SchemaConfig or None, optional
            Schema taxonomy. If None, defaults to ``SchemaConfig()``.
        global_extractor : GlobalRelationExtractor or None, optional
            Optional extractor for structural neighborhoods.

        Returns
        -------
        list of TheoryRelation
            Merged argument relations confirmed by System 1 or System 2.
        """
        if not pairs:
            return []

        effective_schema = schema or SchemaConfig()

        if isinstance(self.fast_classifier, PairTriageARCClassifier):
            fast_relations, escalated_pairs = (
                await self.fast_classifier.classify_pairs_with_triage(
                    pairs=pairs,
                    graph_store=graph_store,
                    global_extractor=global_extractor,
                    schema=effective_schema,
                    audit_rate=self.stochastic_audit_rate,
                )
            )
        else:
            raw_fast = await self.fast_classifier.classify_pairs(
                pairs=pairs,
                graph_store=graph_store,
                schema=effective_schema,
                global_extractor=global_extractor,
            )
            rels_by_pair: dict[tuple[str, str], list[TheoryRelation]] = {}
            for rel in raw_fast:
                ukey = (min(rel.source_id, rel.target_id), max(rel.source_id, rel.target_id))
                rels_by_pair.setdefault(ukey, []).append(rel)

            fast_relations = []
            escalated_pairs = []
            for a, b in pairs:
                ukey = (min(a.id, b.id), max(a.id, b.id))
                pair_key = f"{a.id}:{b.id}"
                is_audit = (
                    should_audit_deterministically(
                        "phase4_arc", "phase4_arc", pair_key, self.stochastic_audit_rate
                    )
                    if self.stochastic_audit_rate > 0.0
                    else False
                )
                matched = rels_by_pair.get(ukey, [])
                if is_audit or not matched:
                    escalated_pairs.append((a, b))
                else:
                    fast_relations.extend(matched)

        if not escalated_pairs:
            return fast_relations

        llm_relations = await self.llm_classifier.classify_pairs(
            pairs=escalated_pairs,
            graph_store=graph_store,
            schema=effective_schema,
            global_extractor=global_extractor,
        )

        merged: dict[tuple[str, str], TheoryRelation] = {
            (r.source_id, r.target_id): r for r in fast_relations
        }
        for r in llm_relations:
            merged[(r.source_id, r.target_id)] = r

        return list(merged.values())

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]:
        """Classify cross-chunk argument relations using the cascade.

        Parameters
        ----------
        local_components : list of TheoryAtom
            All argument components available.
        local_relations : list of TheoryRelation
            Intra-chunk relations previously extracted.
        graph_store : GraphReader
            Reader for graph context.
        global_extractor : GlobalRelationExtractor | None, optional
            Optional extractor for structural neighborhoods.
        schema : SchemaConfig | None, optional
            Schema taxonomy. If None, defaults to SchemaConfig().

        Returns
        -------
        list of TheoryRelation
            Extracted global argument relations.
        """
        effective_schema = schema or SchemaConfig()
        fast_relations, escalated_pairs = await self.fast_classifier.classify_global_with_triage(
            local_components=local_components,
            local_relations=local_relations,
            graph_store=graph_store,
            global_extractor=global_extractor,
            schema=effective_schema,
            audit_rate=self.stochastic_audit_rate,
        )

        if not escalated_pairs:
            return fast_relations

        llm_relations = await self.llm_classifier.classify_pairs(
            pairs=escalated_pairs,
            graph_store=graph_store,
            schema=effective_schema,
            global_extractor=global_extractor,
        )

        merged: dict[tuple[str, str], TheoryRelation] = {
            (r.source_id, r.target_id): r for r in fast_relations
        }
        for r in llm_relations:
            merged[(r.source_id, r.target_id)] = r

        return list(merged.values())
