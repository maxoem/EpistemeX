# [0003] Coreference Resolution Absorbed into Phase 3b Latent Graph Consolidation

Status: Accepted (Amended to reflect Phase 3b Latent Graph Consolidation)

## Context

Traditional NLP pipelines include a dedicated coreference resolution step early in processing — typically a bi-LSTM or
SpanBERT model that clusters mentions into entity chains before NER. The original workflow diagrams (
`2_entity_discovery/2_coreference_resolution.puml`) reflect this architecture.

For a philosophy-domain pipeline processing dense German and English academic prose, classical coreference models face
two problems:

1. They are trained on general-domain text (OntoNotes, etc.) and transfer poorly to philosophical argumentation.
2. Cross-document coreference (e.g., "Kant" in one chapter = "I. Kant" in another = "the Königsberg philosopher" in a
   third) cannot be resolved by within-document models.

Modern LLM-powered KG construction (EntGPT, LLM-Align, 2024–2025 literature) treats entity unification as a
post-KG-build graph operation rather than a pre-NER text operation.

## Decision

**No standalone coreference resolution step.** Instead:

- **Local coreferences** (pronouns, aliases within a single chunk) are resolved implicitly by the LLM during Phase 2 NER
  extraction. The `NER_EXTRACTION_PROMPT` instructs: *"Resolve pronouns or aliases that are clearly identifiable within
  this chunk."* The LLM canonicalises the entity name it writes into the extraction output, so "he" → "Kant" never
  enters the graph as a separate node.

- **Cross-chunk alias resolution** is handled by **Phase 3b Latent Graph Consolidation** (`LatentGraphConsolidation` /
  `Phase3bLatentConsolidationRunner`), which runs *after* Phase 3 global relation extraction and *before* Phase 4
  Argument Mining. It uses dense vector embedding similarity combined with Jaccard overlap of 1-hop relation edge
  signatures to identify duplicate entity pairs, merges them using clique-constrained clustering, and emits canonicalization
  artifacts.

## Alternatives considered

- **SpanBERT coreference** — pros: fast, no LLM calls; cons: poor out-of-domain performance on philosophical text, no
  cross-document capability, adds a training/fine-tuning dependency.
- **Standalone LLM Cross-Encoder pass (Phase 5a)** — pros: high-precision disambiguation; cons: computationally
  expensive with redundant LLM calls for large graphs where dense vector + topological overlap achieves equivalent or
  superior precision without LLM overhead.
- **Leaving aliases unresolved** — acceptable only for L2 KG queries where SAME_AS traversal compensates; unacceptable
  for L3 argument mining where "Kant's claim" and "the author's claim" referencing the same entity must unify before ADU
  extraction.

## Consequences

- `2_entity_discovery/2_coreference_resolution.puml` is superseded and kept only as a historical artefact. The effective
  implementation is in `LatentGraphConsolidation` (`Phase3bLatentConsolidationRunner`).
- Phase 2 NER relies on the LLM to handle within-chunk aliases well. Prompts must include the alias-resolution
  instruction (see `docs/workflow/2_entity_discovery/prompting.md`).
- Entities that are never co-extracted in the same chunk but are actually the same will be unified in Phase 3b prior to
  Phase 4 Argument Mining.

## Related

- `pipeline/phases/phase3b_consolidation/consolidation.py` — `LatentGraphConsolidation`
- `docs/workflow/3b_consolidation/index.md` — Phase 3b Latent Graph Consolidation Workflow
- `docs/concepts/dense_alignment.md` — Epistemic Grounding and Dense Alignment
- ADR 0005 — Pipeline runner sequence and fusion architecture

