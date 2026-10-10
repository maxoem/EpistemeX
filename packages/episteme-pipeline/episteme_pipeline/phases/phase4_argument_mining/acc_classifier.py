"""
LLMACCClassifier — default ACCClassifier implementation.

Classifies each pre-tagged ADU as ANTECEDENT / EMPIRICAL_OBSERVATION and identifies
local SUPPORTS / ATTACKS / Z1_CORRELATION relations between them in a single LLM pass.

Stable component IDs are generated as:
  ac_{sha256(chunk_id + ":" + ac_tag_id)[:14]}

This ensures idempotent MERGE writes: re-processing the same chunk produces
the same IDs, so Neo4j deduplicates automatically.
"""

from __future__ import annotations

import hashlib
import logging

from llama_index.core import PromptTemplate

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation, L2Entity
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.phases.phase4_argument_mining.models import ACCOutput
from episteme_pipeline.protocols.argument_mining import ACCClassifier
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


def _stable_component_id(chunk_id: str, ac_tag: str) -> str:
    key = f"{chunk_id}:{ac_tag}"
    return f"ac_{hashlib.sha256(key.encode()).hexdigest()[:14]}"


class LLMACCClassifier(ACCClassifier):
    """
    Default ACCClassifier using LlamaIndex LLM structured prediction.
    Accepts any LlamaIndex BaseLLM.
    """

    def __init__(self, llm, prompts: Any = None, strategy: Any = "direct_constrained") -> None:
        self.llm = ensure_structured_llm(llm)
        self.prompts = prompts
        self.strategy = strategy

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic ACC classifier configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing strategy and LLM fingerprint.
        """
        from episteme_pipeline.runs.fingerprints import fingerprint_method

        return {
            "class": self.__class__.__name__,
            "strategy": str(getattr(self.strategy, "value", self.strategy)),
            "llm": fingerprint_method(self.llm),
        }

    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: SchemaConfig,
        chunk_entities: list[L2Entity] | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        chunk_entities_str = "\n".join([f"- {e.id}: {e.name} ({e.label})" for e in chunk_entities]) if chunk_entities else "None"
        try:
            raw: ACCOutput = await self.llm.predict_structured(
                ACCOutput,
                self.prompts,
                strategy=self.strategy,
                component_types=", ".join(schema.component_types),
                argument_relation_types=", ".join(schema.argument_relation_types),
                tagged_text=tagged_text,
                chunk_entities=chunk_entities_str,
            )
        except Exception as exc:
            logger.warning("ACC classification failed for chunk %s: %s", chunk_id, exc)
            return [], []

        raw = raw.validate_references()

        # Map LLM-local AC tags to stable graph IDs
        id_map: dict[str, str] = {}
        components: list[TheoryAtom] = []

        for ext in raw.components:
            if ext.component_type not in schema.component_types:
                logger.warning(
                    "Dropped unknown component type %r in chunk %s",
                    ext.component_type,
                    chunk_id,
                )
                continue
            stable_id = _stable_component_id(chunk_id, ext.id)
            id_map[ext.id] = stable_id
            components.append(
                TheoryAtom(
                    id=stable_id,
                    text=ext.text,
                    component_type=ext.component_type,
                    source_chunk_id=chunk_id,
                    confidence=ext.confidence,
                    plausibility=ext.plausibility if ext.plausibility is not None else ext.confidence,
                    entity_ids=ext.entity_ids,
                    epistemic_status=ext.epistemic_status,
                    scope_type=ext.scope_type,
                )
            )

        valid_arg_rel_types = set(schema.argument_relation_types)
        relations: list[TheoryRelation] = []
        for r in raw.relations:
            if r.relation not in valid_arg_rel_types:
                logger.warning(
                    "Dropped unknown argument relation type %r in chunk %s",
                    r.relation,
                    chunk_id,
                )
                continue
            source_id = id_map.get(r.source_id)
            target_id = id_map.get(r.target_id)
            if source_id is None or target_id is None:
                continue
            relations.append(
                TheoryRelation(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=r.relation,
                    confidence=r.confidence,
                    scope="local",
                    weight=r.weight if r.weight is not None else r.confidence,
                )
            )

        return components, relations
