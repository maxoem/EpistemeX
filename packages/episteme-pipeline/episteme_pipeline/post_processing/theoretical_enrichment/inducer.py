"""Theory-Element induction module for Theoretical Enrichment.

Implements structuralist metatheory induction (Sneed, 1971; Stegmüller, 1976;
Balzer et al., 1987) discovering candidate Theory-Elements T = <K, I>, their non-theoretical
base M_pp, potential models M_p, and core laws M directly from extracted graph partitions.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.llm.structured import StructuredLLM, ensure_structured_llm
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    TheoryElementDefinition,
    TheoryInductionOutput,
)
from episteme_pipeline.prompts.default_prompts import THEORY_INDUCTION_DIRECT_PROMPT
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

logger = logging.getLogger(__name__)


class TheoryInducer(Fingerprintable, Protocol):
    """Protocol for dynamic Theory-Element induction."""

    async def induce_theories(
        self,
        atoms: list[TheoryAtom],
        relations: list[TheoryRelation],
        schema: SchemaConfig | None = None,
        max_theories: int = 5,
    ) -> list[TheoryElementDefinition]:
        """Induce Theory-Elements from epistemic graph atoms and relations.

        Parameters
        ----------
        atoms : list[TheoryAtom]
            Input graph nodes across partitions A and B.
        relations : list[TheoryRelation]
            Structural relations connecting atoms.
        schema : SchemaConfig | None, optional
            Graph schema defining component partitions, by default None.
        max_theories : int, optional
            Upper bound on induced theories, by default 5.

        Returns
        -------
        list[TheoryElementDefinition]
            List of induced formal Theory-Element specifications.
        """
        ...


class LLMTheoryInducer:
    """LLM-backed inducer for discovering Theory-Elements from epistemic graphs.

    Parameters
    ----------
    llm : Any
        Underlying LLM facade or StructuredLLM instance.
    prompts : StructuredPromptBundle | str | None, optional
        Custom prompt bundle or template string, by default None.
    strategy : Any, optional
        Decoding strategy for structured prediction, by default "direct_constrained".
    """

    def __init__(
        self,
        llm: Any,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = "direct_constrained",
    ) -> None:
        self.llm: StructuredLLM = ensure_structured_llm(llm)
        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        else:
            self.prompts = StructuredPromptBundle(
                direct_template=prompts or THEORY_INDUCTION_DIRECT_PROMPT,
                name="theory_induction",
            )
        self.strategy = strategy

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint representation of the inducer.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        llm_fp = (
            self.llm.fingerprint()
            if isinstance(self.llm, Fingerprintable)
            else str(self.llm)
        )
        prompts_fp = (
            self.prompts.fingerprint()
            if isinstance(self.prompts, Fingerprintable)
            else str(self.prompts)
        )
        return {
            "type": self.__class__.__name__,
            "strategy": str(self.strategy),
            "llm": llm_fp,
            "prompts": prompts_fp,
        }

    async def induce_theories(
        self,
        atoms: list[TheoryAtom],
        relations: list[TheoryRelation],
        schema: SchemaConfig | None = None,
        max_theories: int = 5,
    ) -> list[TheoryElementDefinition]:
        """Induce Theory-Elements using structured LLM prediction.

        Parameters
        ----------
        atoms : list[TheoryAtom]
            Input graph nodes across partitions A and B.
        relations : list[TheoryRelation]
            Structural relations connecting atoms.
        schema : SchemaConfig | None, optional
            Graph schema defining component partitions, by default None.
        max_theories : int, optional
            Upper bound on induced theories, by default 5.

        Returns
        -------
        list[TheoryElementDefinition]
            List of induced formal Theory-Element specifications.
        """
        graph_schema = schema or DEFAULT_SCHEMA

        # Partition atoms into Theoretical (A) and Empirical (B)
        hypotheses: list[TheoryAtom] = []
        observations: list[TheoryAtom] = []

        for atom in atoms:
            part = graph_schema.component_partitions.get(atom.component_type, "")
            if part == "A" or "hypothesis" in atom.component_type.lower() or "claim" in atom.component_type.lower():
                hypotheses.append(atom)
            else:
                observations.append(atom)

        if not hypotheses:
            logger.info("LLMTheoryInducer: No TheoreticalHypothesis nodes found to induce theories from.")
            return []

        # Format prompt context
        hyp_lines = [f"- [{h.id}] {h.text}" for h in hypotheses[:30]]
        hyp_str = "\n".join(hyp_lines) if hyp_lines else "None identified."

        obs_lines = []
        for o in observations[:30]:
            dims = [f"{m.dimension}={m.value}" for m in o.measurements]
            dim_str = f" (measurements: {', '.join(dims)})" if dims else ""
            obs_lines.append(f"- [{o.id}] {o.text}{dim_str}")
        obs_str = "\n".join(obs_lines) if obs_lines else "None identified."

        rel_lines = [
            f"- {r.source_id} -[{r.relation_type}]-> {r.target_id} (conf={r.confidence})"
            for r in relations[:40]
        ]
        rel_str = "\n".join(rel_lines) if rel_lines else "None identified."

        logger.info(
            "LLMTheoryInducer: Prompting LLM on %d hypotheses and %d observations...",
            len(hypotheses),
            len(observations),
        )

        try:
            raw_output: TheoryInductionOutput = await self.llm.predict_structured(
                TheoryInductionOutput,
                self.prompts,
                strategy=self.strategy,
                theoretical_hypotheses=hyp_str,
                empirical_observations=obs_str,
                structural_relations=rel_str,
                max_theories=max_theories,
            )
        except Exception as err:
            logger.error("LLMTheoryInducer failed structured induction: %s", err)
            return []

        definitions: list[TheoryElementDefinition] = [
            item.to_definition() for item in raw_output.theories
        ]

        logger.info(
            "LLMTheoryInducer: Successfully induced %d Theory-Elements: %s",
            len(definitions),
            [d.theory_id for d in definitions],
        )
        return definitions
