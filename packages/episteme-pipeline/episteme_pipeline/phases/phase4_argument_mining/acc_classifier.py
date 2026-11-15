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

import logging
from enum import Enum
from typing import Any

from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom, TheoryRelation
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.phases.phase4_argument_mining.models import ACCOutput
from episteme_pipeline.phases.phase4_argument_mining.pairing import stable_component_id
from episteme_pipeline.protocols.argument_mining import ACCClassifier
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)

_stable_component_id = stable_component_id


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

        strategy_str = (
            self.strategy.value if isinstance(self.strategy, Enum) else str(self.strategy)
        )
        return {
            "class": self.__class__.__name__,
            "strategy": strategy_str,
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
        raw: ACCOutput = await self.llm.predict_structured(
            ACCOutput,
            self.prompts,
            strategy=self.strategy,
            component_types=", ".join(schema.component_types),
            argument_relation_types=", ".join(schema.argument_relation_types),
            tagged_text=tagged_text,
            chunk_entities=chunk_entities_str,
        )

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
            prior_val = ext.plausibility
            components.append(
                TheoryAtom(
                    id=stable_id,
                    text=ext.text,
                    component_type=ext.component_type,
                    source_chunk_id=chunk_id,
                    confidence=ext.confidence,
                    **({"modal_prior": prior_val} if prior_val is not None else {}),
                    entity_ids=ext.entity_ids,
                    epistemic_status=ext.epistemic_status,
                    scope_type=ext.scope_type,
                    intensional_mode=ext.intensional_mode,
                    attributed_to=ext.attributed_to,
                )
            )

        valid_arg_rel_types = set(schema.argument_relation_types)
        pending: list[Any] = [
            r for r in raw.relations if r.relation in valid_arg_rel_types
        ]
        for r in raw.relations:
            if r.relation not in valid_arg_rel_types:
                logger.warning(
                    "Dropped unknown argument relation type %r in chunk %s",
                    r.relation,
                    chunk_id,
                )

        # Fixed-point resolution so local relation references (undercuts_relation_id / target_id)
        # resolve deterministically regardless of relation order in ACCOutput.relations.
        relations: list[TheoryRelation] = []
        local_rel_id_map: dict[str, str] = {}
        while pending:
            progressed = False
            next_pending: list[Any] = []
            for r in pending:
                raw_premises = (
                    r.premise_ids
                    if r.premise_ids
                    else ([r.source_id] if r.source_id else [])
                )
                mapped_premises: list[str] = []
                missing_premise = False
                for pid in raw_premises:
                    mapped_pid = id_map.get(pid)
                    if mapped_pid is None:
                        missing_premise = True
                        break
                    mapped_premises.append(mapped_pid)
                if missing_premise or not mapped_premises:
                    continue

                source_id = mapped_premises[0]
                premise_tuple = (
                    tuple(mapped_premises) if len(mapped_premises) > 1 or r.premise_ids else ()
                )

                undercuts_rel_id: str | None = None
                if r.undercuts_relation_id is not None:
                    if r.undercuts_relation_id in local_rel_id_map:
                        undercuts_rel_id = local_rel_id_map[r.undercuts_relation_id]
                    else:
                        next_pending.append(r)
                        continue

                if r.target_id in id_map:
                    target_id = id_map[r.target_id]
                elif r.target_id in local_rel_id_map:
                    target_id = local_rel_id_map[r.target_id]
                elif undercuts_rel_id is not None and not r.target_id:
                    target_id = undercuts_rel_id
                else:
                    # Wait in case r.target_id references a local relation ID not yet resolved
                    if any(other.id == r.target_id for other in pending):
                        next_pending.append(r)
                        continue
                    continue

                rel = TheoryRelation(
                    source_id=source_id,
                    target_id=target_id,
                    premise_ids=premise_tuple,
                    undercuts_relation_id=undercuts_rel_id,
                    relation_type=r.relation,
                    confidence=r.confidence,
                    scope="local",
                    weight=r.weight if r.weight is not None else r.confidence,
                )
                relations.append(rel)
                if r.id:
                    local_rel_id_map[r.id] = rel.relation_id
                progressed = True

            if not progressed:
                break
            pending = next_pending

        return components, relations
