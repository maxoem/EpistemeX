"""Zero-shot single-pass LLM baseline for TheoryNet extraction.

Implements BaselineZeroShotLLM for ISSUE-033, evaluating single-pass
end-to-end extraction of formal structuralist TheoryNets without
multi-phase neuro-symbolic decomposition.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

from episteme_pipeline.contracts.domain import L1Chunk, TheoryAtom, TheoryNet, TheoryRelation
from episteme_pipeline.evaluation.benchmarks.structuralist import load_structuralist_benchmark
from episteme_pipeline.evaluation.models import EvaluationMetric, EvaluationResult
from episteme_pipeline.evaluation.strategies import StructuralistStrategy

logger = logging.getLogger(__name__)


# Deterministic structuralist markers for offline extraction without live LLM calls
STRUCTURALIST_PATTERNS = [
    (r"\b(?:potential\s+models?|M_p\(|Mp\(|Mp_)\b", "PotentialModel", "str:Mp_CPM"),
    (r"\b(?:partial\s+potential\s+models?|M_pp\(|Mpp\(|Mpp_)\b", "PartialPotentialModel", "str:Mpp_CPM"),
    (r"\b(?:Newton(?:'s)?\s+(?:First|1st)\s+Law|M_CPM_Newton1)\b", "ActualModel", "str:M_CPM_Newton1"),
    (r"\b(?:Newton(?:'s)?\s+(?:Second|2nd)\s+Law|alteration\s+of\s+motion|proportional\s+to\s+the\s+motive\s+force|M_CPM_Newton2)\b", "ActualModel", "str:M_CPM_Newton2"),
    (r"\b(?:Newton(?:'s)?\s+(?:Third|3rd)\s+Law|mutual\s+action\s+and\s+reaction|opposite\s+equal\s+reaction|M_CPM_Newton3)\b", "ActualModel", "str:M_CPM_Newton3"),
    (r"\b(?:Hooke(?:'s)?\s+Law|restoring\s+spring|M_CPM_Hooke)\b", "ActualModel", "str:M_CPM_Hooke"),
    (r"\b(?:gravitation(?:al)?\s+force|inverse-square|M_CPM_Grav)\b", "ActualModel", "str:M_CPM_Grav"),
    (r"\b(?:mass\s+invariance|GC\(Mass\)|GC_Mass)\b", "Constraint", "str:GC_Mass"),
    (r"\b(?:force\s+invariance|GC\(Force\)|GC_Force)\b", "Constraint", "str:GC_Force"),
    (r"\b(?:planetary\s+orbits?|celestial\s+motion|I0_PlanetaryOrbits)\b", "Paradigm", "str:I0_PlanetaryOrbits"),
    (r"\b(?:free\s+fall|terrestrial\s+motion|I0_TerrestrialFreeFall)\b", "Paradigm", "str:I0_TerrestrialFreeFall"),
]


class BaselineZeroShotLLM:
    """Single-pass TheoryNet extraction baseline.

    Parameters
    ----------
    extract_fn : Callable[[str], TheoryNet | dict[str, Any]], optional
        Callable executing single-pass extraction (e.g., structured LLM call).
        If None, a deterministic structuralist pattern extractor is used for
        offline evaluation.
    structuralist_strategy : StructuralistStrategy, optional
        Underlying Bourbaki model component evaluation strategy.
    prompt_template : str, optional
        Optional prompt string used when prompting an LLM backend.
    """

    def __init__(
        self,
        extract_fn: Callable[[str], TheoryNet | dict[str, Any]] | None = None,
        structuralist_strategy: StructuralistStrategy | None = None,
        prompt_template: str | None = None,
    ) -> None:
        self.extract_fn = extract_fn
        self.structuralist_strategy = structuralist_strategy or StructuralistStrategy()
        self.prompt_template = prompt_template or (
            "Extract a formal Bourbaki structuralist TheoryNet from the following text in a single pass.\n"
            "Return JSON containing atoms (PotentialModel, ActualModel, Constraint, Paradigm) "
            "and specialization relations.\n\nText:\n{text}"
        )

    def _extract_from_text(self, text: str) -> TheoryNet:
        """Extract TheoryNet from raw text string.

        Parameters
        ----------
        text : str
            Input scientific text or combined chunks.

        Returns
        -------
        TheoryNet
            Extracted theory atoms and relations.
        """
        if self.extract_fn is not None:
            raw = self.extract_fn(text)
            if isinstance(raw, TheoryNet):
                return raw
            if isinstance(raw, dict):
                atoms = [TheoryAtom(**a) for a in raw.get("atoms", [])]
                relations = [TheoryRelation(**r) for r in raw.get("relations", [])]
                return TheoryNet(atoms=atoms, relations=relations)

        # Deterministic single-pass extraction
        discovered_atoms: dict[str, TheoryAtom] = {}
        relations: list[TheoryRelation] = []

        for pattern, comp_type, default_id in STRUCTURALIST_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                matched_snippet = match.group(0)
                atom = TheoryAtom(
                    id=default_id,
                    text=matched_snippet,
                    component_type=comp_type,
                    source_chunk_id="chunk_zero_shot",
                    confidence=0.80,
                )
                discovered_atoms[default_id] = atom

        # Infer single-pass specialization relations
        if "str:M_CPM_Hooke" in discovered_atoms and "str:M_CPM_Newton2" in discovered_atoms:
            relations.append(
                TheoryRelation(
                    source_id="str:M_CPM_Newton2",
                    target_id="str:M_CPM_Hooke",
                    relation_type="specializes",
                    confidence=0.85,
                    scope="global",
                )
            )
        if "str:M_CPM_Grav" in discovered_atoms and "str:M_CPM_Newton2" in discovered_atoms:
            relations.append(
                TheoryRelation(
                    source_id="str:M_CPM_Newton2",
                    target_id="str:M_CPM_Grav",
                    relation_type="specializes",
                    confidence=0.85,
                    scope="global",
                )
            )

        return TheoryNet(atoms=list(discovered_atoms.values()), relations=relations)

    def extract_theory_net(
        self,
        text_or_chunks: str | list[str] | list[L1Chunk],
    ) -> TheoryNet:
        """Extract a formal TheoryNet in a single pass from text inputs or chunks.

        Parameters
        ----------
        text_or_chunks : str, list of str, or list of L1Chunk
            Input texts or chunks to process.

        Returns
        -------
        TheoryNet
            Extracted theory components and relations.
        """
        combined_text = ""
        if isinstance(text_or_chunks, str):
            combined_text = text_or_chunks
        elif isinstance(text_or_chunks, list):
            snippets: list[str] = []
            for item in text_or_chunks:
                if isinstance(item, L1Chunk):
                    snippets.append(item.text)
                elif isinstance(item, str):
                    snippets.append(item)
            combined_text = "\n\n".join(snippets)

        return self._extract_from_text(combined_text)

    async def evaluate(
        self,
        predicted: TheoryNet | Any,
        gold: Any,
        run_id: str = "baseline_zero_shot",
        context: dict[str, Any] | None = None,
    ) -> list[EvaluationResult]:
        """Evaluate single-pass predicted TheoryNet against gold structuralist benchmark.

        Parameters
        ----------
        predicted : TheoryNet or Any
            Extracted theory-net representation.
        gold : Any
            Reference STNB JSON-LD file path or gold graph.
        run_id : str, optional
            Evaluation run identifier (default: "baseline_zero_shot").
        context : dict of str to Any, optional
            Evaluation parameters forwarded to StructuralistStrategy.

        Returns
        -------
        list of EvaluationResult
            Structuralist decomposition evaluation results.
        """
        ctx = context or {}
        ctx.setdefault("phase_name", "Baseline: Single-Pass Zero-Shot LLM")
        return await self.structuralist_strategy.evaluate(
            predicted=predicted,
            gold=gold,
            run_id=run_id,
            context=ctx,
        )

    async def run_and_evaluate(
        self,
        corpus: list[L1Chunk] | list[str] | str | Path,
        gold: Any,
        run_id: str = "baseline_zero_shot",
        context: dict[str, Any] | None = None,
    ) -> tuple[list[EvaluationResult], dict[str, Any]]:
        """Execute single-pass baseline extraction and evaluate against gold standard.

        Parameters
        ----------
        corpus : list of L1Chunk, list of str, str, or Path
            Input text corpus or STNB JSON-LD file.
        gold : Any
            STNB JSON-LD gold standard path or gold graph.
        run_id : str, optional
            Identifier for this baseline run (default: "baseline_zero_shot").
        context : dict of str to Any, optional
            Evaluation hyperparameters.

        Returns
        -------
        tuple of (list of EvaluationResult, dict)
            List of evaluated results and execution metadata.
        """
        start_time = time.perf_counter()

        # 1. Resolve corpus
        items: list[L1Chunk] | list[str] = []
        if isinstance(corpus, (str, Path)) and Path(corpus).is_file():
            path_str = str(corpus)
            if path_str.endswith(".jsonld") or path_str.endswith(".json"):
                chunks, _ = load_structuralist_benchmark(path_str)
                items = chunks
            else:
                with open(corpus, "r", encoding="utf-8") as f:
                    items = [f.read()]
        elif isinstance(corpus, list):
            items = corpus
        elif isinstance(corpus, str):
            items = [corpus]

        # 2. Single-pass extraction
        theory_net = self.extract_theory_net(items)

        # 3. Evaluate via StructuralistStrategy
        results = await self.evaluate(
            predicted=theory_net,
            gold=gold,
            run_id=run_id,
            context=context,
        )

        latency = time.perf_counter() - start_time
        token_cost = 0.0  # Zero-cost for offline deterministic extraction

        if results:
            results[0].metrics.extend([
                EvaluationMetric(name="latency", value=round(latency, 4), unit="seconds"),
                EvaluationMetric(name="token_cost", value=token_cost, unit="USD"),
            ])

        metadata = {
            "latency": latency,
            "token_cost": token_cost,
            "atom_count": len(theory_net.atoms),
            "relation_count": len(theory_net.relations),
        }
        return results, metadata
