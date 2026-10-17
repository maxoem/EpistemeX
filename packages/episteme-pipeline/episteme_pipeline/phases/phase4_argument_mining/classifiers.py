"""DecisionEngine-backed and Cascading Argument Mining Classifiers.

Provides System 1 fast triage and cascading classifiers for Argument Component
Classification (ACC) and Argument Relation Classification (ARC) using calibrated
DecisionEngine protocols.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import defaultdict

from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom, TheoryRelation
from episteme_pipeline.decision.cascade import should_audit_deterministically
from episteme_pipeline.phases.phase4_argument_mining.pairing import stable_component_id
from episteme_pipeline.prompts.default_prompts import (
    DECISION_ACC_CRITERIA,
    DECISION_ACC_QUESTION,
    DECISION_ARC_CRITERIA,
    DECISION_ARC_QUESTION,
)
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
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.protocols.modality import ModalStrengthResolver
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


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
    prompts : Any or None, default None
        Optional prompt bundle carrying classification instructions or rubrics.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        prompts: StructuredPromptBundle | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
        self.modal_resolver = modal_resolver
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
            )

            selected_type = str(decision.selected_option) if decision.selected_option in options else schema.component_types[0]
            confidence = decision.class_probability
            empirical_accuracy = decision.empirical_accuracy

            stable_id = stable_component_id(chunk_id, adu_id)
            atom = TheoryAtom(
                id=stable_id,
                text=adu_text,
                component_type=selected_type,
                source_chunk_id=chunk_id,
                confidence=confidence,
                plausibility=empirical_accuracy,
            )
            if self.modal_resolver:
                atom.modal_strength = await self.modal_resolver.resolve_modality(atom, context=state)
                atom.base_score = atom.modal_strength
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
    """

    def __init__(
        self,
        fast_classifier: ACCClassifier,
        llm_classifier: ACCClassifier,
        config: Phase4Config | None = None,
        triage_confidence_threshold: float = 0.85,
        stochastic_audit_rate: float = 0.02,
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
        atoms, relations = await self.fast_classifier.classify(
            chunk_id, tagged_text, adu_ids, schema, chunk_entities
        )

        if not atoms:
            return await self.llm_classifier.classify(
                chunk_id, tagged_text, adu_ids, schema, chunk_entities
            )

        threshold = self.triage_confidence_threshold
        audit_rate = self.stochastic_audit_rate

        is_uncertain = any(a.confidence is None or a.confidence < threshold for a in atoms)
        is_audit = (
            should_audit_deterministically(chunk_id, "phase4_acc", chunk_id, audit_rate)
            if audit_rate > 0.0
            else False
        )

        # When fast classifier produces uncertain results, or during deterministic audits,
        # fall back to LLM
        if is_uncertain or is_audit:
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
        default_modal_strength: float = 1.0,
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
        self.arc_mode = arc_mode
        self.embedding_model = embedding_model
        self.confidence_threshold = confidence_threshold
        self.max_candidates_per_component = max_candidates_per_component
        self.default_modal_strength = default_modal_strength

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

    def _resolve_modal_strength(
        self,
        source_atom: TheoryAtom,
        target_atom: TheoryAtom,
    ) -> float:
        """Resolve propositional modal strength for a candidate relation edge.

        In Quantitative Bipolar Argumentation Frameworks (QBAF), mathematical edge
        weights decouple epistemic extraction certainty from propositional modal necessity:
        w = M(modal_strength) * P(stance).

        Parameters
        ----------
        source_atom : TheoryAtom
            Source premise or hypothesis component.
        target_atom : TheoryAtom
            Target claim or conclusion component.

        Returns
        -------
        float
            Modal strength multiplier in [0.0, 1.0]. Defaults to `default_modal_strength` (1.0)
            unless modulated by atom epistemic status or modality.
        """
        return self.default_modal_strength

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
        state = f"Source: {source_atom.text}\nTarget: {target_atom.text}"
        pair_key = f"{source_atom.id}:{target_atom.id}"
        is_audit = (
            should_audit_deterministically(run_seed, "phase4_arc", pair_key, audit_rate)
            if audit_rate > 0.0
            else False
        )

        if self.arc_mode == "multiplex":
            rels: list[TheoryRelation] = []
            should_escalate = is_audit
            for r_type in schema.argument_relation_types:
                rel_def = schema.argument_relation_definitions.get(r_type, f"relation {r_type.lower()}")
                if "{relation_type}" in self.decision_template:
                    question = self.decision_template.format(relation_type=r_type.lower())
                else:
                    question = f"Does the source statement have the following relation to the target statement: '{r_type}' ({rel_def})?"

                decision: DecisionNoulResult = await self.decision_engine.evaluate_noul(
                    state=state,
                    question=question,
                )
                if decision.probability < self.confidence_threshold and decision.probability > (1.0 - self.confidence_threshold):
                    should_escalate = True
                elif decision.passed and decision.probability >= self.confidence_threshold:
                    modal = self._resolve_modal_strength(source_atom, target_atom)
                    eff_w = float(modal * decision.probability)
                    rels.append(
                        TheoryRelation(
                            source_id=source_atom.id,
                            target_id=target_atom.id,
                            relation_type=r_type,
                            confidence=decision.probability,
                            scope="global",
                            weight=eff_w,
                            class_probability=decision.probability,
                            empirical_accuracy=decision.empirical_accuracy,
                            modal_strength=modal,
                            effective_weight=eff_w,
                            decision_engine_provider="jev",
                        )
                    )
            return rels, should_escalate

        options = self._build_choice_options(schema)
        decision: DecisionScore = await self.decision_engine.evaluate_choice(
            state=state,
            question=self.decision_template,
            options=options,
        )

        pred_set = decision.prediction_set
        is_ambiguous = (
            len(pred_set) != 1
            if pred_set is not None
            else decision.class_probability < self.confidence_threshold
        )
        should_escalate = is_ambiguous or is_audit

        if should_escalate:
            return [], True

        selected = str(decision.selected_option) if decision.selected_option else "NEUTRAL"
        resolved_type = schema.resolve_relation_type(selected)

        if resolved_type and decision.class_probability >= self.confidence_threshold:
            modal = self._resolve_modal_strength(source_atom, target_atom)
            eff_w = float(modal * decision.class_probability)
            return [
                TheoryRelation(
                    source_id=source_atom.id,
                    target_id=target_atom.id,
                    relation_type=resolved_type,
                    confidence=decision.class_probability,
                    scope="global",
                    weight=eff_w,
                    class_probability=decision.class_probability,
                    empirical_accuracy=decision.empirical_accuracy,
                    modal_strength=modal,
                    effective_weight=eff_w,
                    decision_engine_provider="jev",
                    calibrated_confidence=decision.empirical_accuracy or decision.class_probability,
                )
            ], False

        return [], False

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
        effective_schema = schema or SchemaConfig()
        pairs = self._get_cross_chunk_pairs(local_components, effective_schema)
        if not pairs:
            return [], []

        tasks = [
            self.classify_pair_with_triage(
                a, b, effective_schema, audit_rate=audit_rate, run_seed=run_seed
            )
            for a, b in pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        confirmed_relations: list[TheoryRelation] = []
        escalated_pairs: list[tuple[TheoryAtom, TheoryAtom]] = []

        for (a, b), res in zip(pairs, results):
            if isinstance(res, Exception):
                logger.warning("JevARC pair classification failed for (%s, %s): %s", a.id, b.id, res)
                escalated_pairs.append((a, b))
            elif isinstance(res, tuple):
                rels, should_escalate = res
                if should_escalate:
                    escalated_pairs.append((a, b))
                else:
                    confirmed_relations.extend(rels)

        return confirmed_relations, escalated_pairs

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
        partner_count: dict[str, int] = defaultdict(int)
        seen: set[tuple[str, str]] = set()
        pairs: list[tuple[TheoryAtom, TheoryAtom]] = []

        priority_rank = {ctype: idx for idx, ctype in enumerate(schema.component_types)}
        sorted_components = sorted(
            components, key=lambda c: priority_rank.get(c.component_type, 99)
        )

        for i, a in enumerate(sorted_components):
            for b in sorted_components[i + 1 :]:
                if a.source_chunk_id == b.source_chunk_id:
                    continue
                key = (min(a.id, b.id), max(a.id, b.id))
                if key in seen:
                    continue
                if (
                    partner_count[a.id] >= self.max_candidates_per_component
                    or partner_count[b.id] >= self.max_candidates_per_component
                ):
                    continue
                seen.add(key)
                pairs.append((a, b))
                partner_count[a.id] += 1
                partner_count[b.id] += 1

        return pairs


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
