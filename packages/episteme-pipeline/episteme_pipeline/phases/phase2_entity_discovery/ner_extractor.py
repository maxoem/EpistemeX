"""
LLMNERExtractor — Named Entity Recognition and local relation extraction.

Uses LlamaIndex's astructured_predict to call the LLM with a typed Pydantic
output schema. The NER prompt (from pipeline/prompts/default_prompts.py) is
injected with {entity_types} and {relation_types} from SchemaConfig at runtime.

On parsing failure (malformed LLM output) the extractor logs and returns empty
lists — the chunk is NOT marked as processed so it will be retried on re-run.

CoT strategy (from docs/workflow/2_entity_discovery/prompting.md):
  The prompt instructs the model to first identify logical connectives and
  argument structure before classifying, which improves relation extraction
  accuracy for dense philosophical prose.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from llama_index.core import PromptTemplate

from episteme_pipeline.config import StructuredPromptBundle
from episteme_pipeline.contracts.domain import L2Entity, L2Triple
from episteme_pipeline.decision.gleaning import FixedPassGleaningOracle
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.prompts import (
    NER_DIRECT_PROMPT,
    NER_REASONING_PROMPT,
    NER_FORMAT_PROMPT,
    NER_GLEANING_PROMPT,
)
from episteme_pipeline.phases.phase2_entity_discovery.models import NERExtractionOutput
from episteme_pipeline.phases.phase2_entity_discovery.mention_context_injector import DefaultMentionContextInjector
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.decision import GleaningStoppingOracle
from episteme_pipeline.protocols.extractors import NERExtractor
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


def _stable_entity_id(label: str, name: str) -> str:
    """
    Deterministic entity ID from label + normalized name.
    Same entity name + label across chunks → same ID → MERGE deduplicates.
    """
    key = f"{label.upper()}::{name.strip().lower()}"
    return f"entity_{hashlib.sha256(key.encode()).hexdigest()[:14]}"


DEFAULT_NER_PROMPTS = StructuredPromptBundle(
    direct_template=NER_DIRECT_PROMPT,
    reasoning_template=NER_REASONING_PROMPT,
    format_template=NER_FORMAT_PROMPT,
    gleaning_template=NER_GLEANING_PROMPT,
)


class LLMNERExtractor(NERExtractor):
    """Default NERExtractor using LlamaIndex LLM structured prediction.

    Accepts any LlamaIndex BaseLLM (LiteLLM, OpenAI, Ollama, etc.).

    Parameters
    ----------
    llm : Any
        Underlying LLM instance.
    prompts : StructuredPromptBundle or None, default None
        Prompt bundle for direct, reasoning, format, and gleaning templates.
    max_gleanings : int, default 0
        Maximum extraction iterations if no dynamic stopping oracle is supplied.
    mention_context_injector : Any, default None
        Textual context injector for mentions.
    strategy : Any, default "direct_constrained"
        Decoding strategy.
    stopping_oracle : GleaningStoppingOracle or None, default None
        Stopping oracle evaluating whether additional passes are warranted.
    """

    def __init__(
        self, 
        llm: Any, 
        prompts: StructuredPromptBundle | None = None,
        max_gleanings: int = 0, 
        mention_context_injector: Any = None,
        strategy: Any = "direct_constrained",
        stopping_oracle: GleaningStoppingOracle | None = None,
    ) -> None:
        self.llm = ensure_structured_llm(llm)
        self.max_gleanings = max_gleanings
        self.mention_context_injector = mention_context_injector or DefaultMentionContextInjector()
        self.prompts = prompts or DEFAULT_NER_PROMPTS
        self.strategy = strategy
        self.stopping_oracle = stopping_oracle or FixedPassGleaningOracle(max_passes=max_gleanings)

    @classmethod
    def from_config(
        cls,
        llm: Any,
        config: Any,
        decision_engine: DecisionEngine | None = None,
        mention_context_injector: Any = None,
    ) -> LLMNERExtractor:
        """Construct LLMNERExtractor with dependencies wired from Phase2Config.

        Parameters
        ----------
        llm : Any
            LlamaIndex BaseLLM instance.
        config : Phase2Config
            Phase 2 configuration.
        decision_engine : DecisionEngine or None, default None
            Optional decision engine for stopping oracle.
        mention_context_injector : Any, default None
            Optional custom mention context injector.

        Returns
        -------
        LLMNERExtractor
            Configured extractor instance.
        """
        from episteme_pipeline.decision.gleaning import JevGleaningGate

        stopping_oracle = JevGleaningGate.create(
            decision_engine=decision_engine,
            config=config.gleaning,
            prompts=config.ner_prompts,
        )

        return cls(
            llm=llm,
            prompts=config.ner_prompts,
            max_gleanings=config.gleaning.max_passes,
            mention_context_injector=mention_context_injector,
            strategy=config.ner_decoding_strategy,
            stopping_oracle=stopping_oracle,
        )

    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: Any | None = None,
        anchor: Any | None = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]:
        global_structural_anchor_str = anchor.to_prompt_context() if anchor and hasattr(anchor, "to_prompt_context") else ""
        working_memory_str = memory.to_prompt_context() if memory and hasattr(memory, "to_prompt_context") else ""

        all_raw_entities = []
        all_raw_triples = []
        memory_update: dict | None = None
        boundary_detected = False
        transitional_summary: str | None = None

        try:
            raw: NERExtractionOutput = await self.llm.predict_structured(
                NERExtractionOutput,
                self.prompts,
                strategy=self.strategy,
                global_structural_anchor=global_structural_anchor_str,
                working_memory_context=working_memory_str,
                entity_types=schema.node_types_str(),
                relation_types=schema.relation_types_str(),
                chunk_text=chunk_text,
            )
            raw = raw.validate_references()
            all_raw_entities.extend(raw.entities)
            all_raw_triples.extend(raw.triples)
            if raw.working_memory:
                memory_update = raw.working_memory.state_delta
                boundary_detected = raw.working_memory.boundary_detected
                transitional_summary = raw.working_memory.transitional_summary

            # Unified gleanings loop via stopping oracle
            gleaning_prompt = self.prompts.gleaning_template or NER_GLEANING_PROMPT
            pass_count = 0
            while True:
                should_continue, _ = await self.stopping_oracle.should_glean(
                    chunk_text=chunk_text,
                    current_extractions=all_raw_entities,
                    pass_count=pass_count,
                )
                if not should_continue:
                    break
                pass_count += 1
                prior_text = ", ".join([e.name for e in all_raw_entities])
                raw_glean: NERExtractionOutput = await self.llm.predict_structured(
                    NERExtractionOutput,
                    gleaning_prompt,
                    chunk_text=chunk_text,
                    prior_extractions=prior_text,
                )
                raw_glean = raw_glean.validate_references()
                if not raw_glean.entities and not raw_glean.triples:
                    break  # model found nothing new

                all_raw_entities.extend(raw_glean.entities)
                all_raw_triples.extend(raw_glean.triples)

        except Exception as exc:
            logger.warning(
                "NER extraction failed for chunk %s: %s", chunk_id, exc
            )
            return [], [], None, False, None

        # Validate labels against schema (drop unknown types silently)
        valid_node_types = set(schema.node_types)
        valid_rel_types = set(schema.relation_types)

        valid_entities = [
            e for e in all_raw_entities if e.label in valid_node_types
        ]
        if len(valid_entities) < len(all_raw_entities):
            logger.debug(
                "Dropped %d entities with unknown labels for chunk %s",
                len(all_raw_entities) - len(valid_entities),
                chunk_id,
            )

        # local_id -> stable graph ID
        id_map: dict[str, str] = {}
        entities: list[L2Entity] = []

        for ext in valid_entities:
            stable_id = _stable_entity_id(ext.label, ext.name)
            id_map[ext.id] = stable_id
            
            # Topologically inject the textual envelope bounds
            textual_envelope = self.mention_context_injector.inject(
                chunk_text=chunk_text, 
                mention_name=ext.name, 
                mention_quote=ext.mention_quote, 
                chunk_id=chunk_id
            )
            
            entities.append(
                L2Entity(
                    id=stable_id,
                    label=ext.label,
                    name=ext.name,
                    description=ext.mention_quote if ext.mention_quote != ext.name else None,
                    textual_envelope=textual_envelope,
                    confidence=ext.confidence,
                    source_chunk_ids=[chunk_id],
                )
            )

        triples: list[L2Triple] = []
        for t in all_raw_triples:
            if t.predicate not in valid_rel_types:
                continue
            subj_id = id_map.get(t.subject_id)
            obj_id = id_map.get(t.object_id)
            if subj_id is None or obj_id is None:
                continue
            triples.append(
                L2Triple(
                    subject_id=subj_id,
                    predicate=t.predicate,
                    object_id=obj_id,
                    confidence=t.confidence,
                    scope="local",
                    source_chunk_id=chunk_id,
                )
            )

        return entities, triples, memory_update, boundary_detected, transitional_summary
