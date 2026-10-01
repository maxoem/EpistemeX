"""DecisionEngine-backed and Cascading Argument Mining Classifiers.

Provides System 1 fast triage and cascading classifiers for Argument Component
Classification (ACC) and Argument Relation Classification (ARC) using calibrated
DecisionEngine protocols.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import hashlib
import logging
import random
import re
from typing import Any

from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom, TheoryRelation
from episteme_pipeline.prompts.default_prompts import (
    DECISION_ACC_CRITERIA,
    DECISION_ACC_QUESTION,
    DECISION_ARC_CRITERIA,
    DECISION_ARC_QUESTION,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.argument_mining import ACCClassifier, ARCClassifier
from episteme_pipeline.protocols.decision import DecisionEngine, DecisionNoulResult, DecisionScore
from episteme_pipeline.protocols.extractors import EmbeddingModel, GlobalRelationExtractor
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


def _stable_component_id(chunk_id: str, ac_tag: str) -> str:
    """Generate a deterministic, content-addressable ID for an argument component.

    Parameters
    ----------
    chunk_id : str
        The unique ID of the source chunk.
    ac_tag : str
        The local tag identifier (e.g. "AC1").

    Returns
    -------
    str
        Stable component ID.
    """
    key = f"{chunk_id}:{ac_tag}"
    return f"ac_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:14]}"


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
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
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

            stable_id = _stable_component_id(chunk_id, adu_id)
            atoms.append(
                TheoryAtom(
                    id=stable_id,
                    text=adu_text,
                    component_type=selected_type,
                    source_chunk_id=chunk_id,
                    confidence=confidence,
                    plausibility=empirical_accuracy,
                )
            )

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
            getattr(config, "triage_confidence_threshold", triage_confidence_threshold)
            if config is not None
            else triage_confidence_threshold
        )
        self.stochastic_audit_rate = (
            getattr(config, "stochastic_audit_rate", stochastic_audit_rate)
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

        threshold = self.triage_confidence_threshold
        audit_rate = self.stochastic_audit_rate

        is_uncertain = any(a.confidence is None or a.confidence < threshold for a in atoms)
        is_audit = random.random() < audit_rate

        # When fast classifier produces uncertain results, or during stochastic audits,
        # or when no intra-chunk relations were extracted, fall back to LLM
        if is_uncertain or is_audit or not relations:
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
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
        self.arc_mode = arc_mode
        self.embedding_model = embedding_model
        self.confidence_threshold = confidence_threshold
        self.max_candidates_per_component = max_candidates_per_component

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
        state = f"Source: {source_atom.text}\nTarget: {target_atom.text}"

        if self.arc_mode == "multiplex":
            rels: list[TheoryRelation] = []
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
                if decision.passed and decision.probability >= self.confidence_threshold:
                    rels.append(
                        TheoryRelation(
                            source_id=source_atom.id,
                            target_id=target_atom.id,
                            relation_type=r_type,
                            confidence=decision.probability,
                            scope="global",
                            weight=decision.empirical_accuracy,
                        )
                    )
            return rels

        options: dict[str, str] = {}
        for r_type in schema.argument_relation_types:
            if isinstance(self.criteria, dict) and r_type in self.criteria:
                options[r_type] = self.criteria[r_type]
            elif r_type in schema.argument_relation_definitions:
                options[r_type] = schema.argument_relation_definitions[r_type]
            else:
                options[r_type] = f"Argumentative relation {r_type}"

        # Neutral option representing absence of direct dialectical link
        options["NEUTRAL"] = (
            self.criteria.get("NEUTRAL", "No direct argumentative relation between source and target.")
            if isinstance(self.criteria, dict)
            else "No direct argumentative relation between source and target."
        )

        decision: DecisionScore = await self.decision_engine.evaluate_choice(
            state=state,
            question=self.decision_template,
            options=options,
        )

        selected = str(decision.selected_option) if decision.selected_option else "NEUTRAL"
        if selected in schema.argument_relation_types and decision.class_probability >= self.confidence_threshold:
            return [
                TheoryRelation(
                    source_id=source_atom.id,
                    target_id=target_atom.id,
                    relation_type=selected,
                    confidence=decision.class_probability,
                    scope="global",
                    weight=decision.empirical_accuracy,
                )
            ]
        return []

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor,
        schema: SchemaConfig,
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
        global_extractor : GlobalRelationExtractor
            Extractor used for structural contexts.
        schema : SchemaConfig
            Schema taxonomy.

        Returns
        -------
        list of TheoryRelation
            Predicted global cross-chunk argument relations.
        """
        pairs = self._get_cross_chunk_pairs(local_components, schema)
        if not pairs:
            return []

        tasks = [self.classify_pair(a, b, schema) for a, b in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        relations: list[TheoryRelation] = []
        for res in results:
            if isinstance(res, list):
                relations.extend(res)
            elif isinstance(res, Exception):
                logger.warning("JevARC pair classification failed: %s", res)

        return relations

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
            getattr(config, "stochastic_audit_rate", stochastic_audit_rate)
            if config is not None
            else stochastic_audit_rate
        )

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor,
        schema: SchemaConfig,
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
        global_extractor : GlobalRelationExtractor
            Extractor for structural neighborhoods.
        schema : SchemaConfig
            Schema taxonomy.

        Returns
        -------
        list of TheoryRelation
            Extracted global argument relations.
        """
        fast_relations = await self.fast_classifier.classify_global(
            local_components=local_components,
            local_relations=local_relations,
            graph_store=graph_store,
            global_extractor=global_extractor,
            schema=schema,
        )

        audit_rate = self.stochastic_audit_rate
        is_audit = random.random() < audit_rate

        if fast_relations and not is_audit:
            return fast_relations

        return await self.llm_classifier.classify_global(
            local_components=local_components,
            local_relations=local_relations,
            graph_store=graph_store,
            global_extractor=global_extractor,
            schema=schema,
        )
