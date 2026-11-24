# [0004] ACC Outputs Component Types AND Local Relations in a Single LLM Pass

Status: Accepted

## Context

Classical argument mining pipelines have three discrete steps:

1. **ADU Segmentation** — identify argument spans
2. **ACC** (Argument Component Classification) — label each span as Claim / MajorClaim / Premise
3. **ARI** (Argument Relation Identification) — identify which components support or attack which

Traditional implementations treat ACC and ARI as separate models (e.g., two separate BERT classifiers). This requires
the output of ACC to be passed to ARI as a second LLM call per chunk.

The `docs/feature/warnings.md` question: *"The Phase 4 - Step 3: Local ARI must be evaluated. How relevant is it still?
Must it be merged with ACC-ARC?"*

## Decision

**ACC classifies ADU types AND extracts local support/attack relations in a single LLM structured-prediction call.**

When a chunk's ADUs have already been tagged with `<ACn>` markup (by the preceding ADU Segmentation step), a single
prompt (`ACC_CLASSIFICATION_PROMPT`) instructs the LLM to:

- Assign a `component_type` (CLAIM / MAJOR_CLAIM / PREMISE) to each `<ACn>` tag
- Identify all local `SUPPORTS` and `ATTACKS` relations between ADUs
- Return both in a single JSON object

This collapses what would have been two LLM calls per chunk into one. The `ACCOutput` Pydantic model captures both
`components` and `relations`.

**ARI as a standalone step** is preserved as an abstract interface (`ARIIdentifier(ABC)` in
`pipeline/protocols/argument_mining.py`) so that implementations requiring a separate relation-identification pass can
plug in. In the default pipeline, this interface is not instantiated — ACC covers it.

## Alternatives considered

- **Separate ACC + ARI calls** — more modular and easier to fine-tune independently; doubles LLM call count per chunk;
  the additional latency is not justified when a single structured-prediction prompt handles both tasks reliably.
- **Full joint segmentation + classification + relation** — possible but makes the prompt too complex and degrades
  performance on long chunks. Keeping ADU Segmentation as a separate prior step (with simpler markup output) maintains
  tractability.

## Consequences

- `docs/workflow/4_argument_mining/3_ari.puml` documents the ARI step as defined; in the default implementation it is
  fused into ACC. The diagram is retained as a reference for alternative implementations.
- The `ACCOutput.validate_references()` method performs fixed-point validation: it drops relations whose `source_id`, conjunctive `premise_ids`, or `target_id` does not reference a classified component or valid local inference `id` (for `undercuts_relation_id` / undercutter targets), cascading removal cleanly across dependent undercutters.
- `ExtractedTheoryRelation` accepts optional local `id`, `premise_ids` (conjunctive premise sets for linked argumentation), and `undercuts_relation_id` (`ISSUE-055`), which `LLMACCClassifier.classify()` maps to deterministic chunk-scoped atom IDs and resolved local `TheoryRelation.relation_id` targets in fixed-point order regardless of LLM relation ordering.
- Global argument relations (cross-chunk SUPPORTS/ATTACKS) are handled by ARC (Phase 4 Step 4), which uses the shared
  `GlobalRelationExtractor` — not by ACC.

## Related

- `pipeline/protocols/argument_mining.py` — `ACCClassifier`, `ARIIdentifier` ABCs
- `pipeline/phases/phase4_argument_mining/acc_classifier.py` — `LLMACCClassifier`
- `pipeline/phases/phase4_argument_mining/models.py` — `ACCOutput`
- `pipeline/prompts/default_prompts.py` — `ACC_CLASSIFICATION_PROMPT`
- `docs/workflow/4_argument_mining/2_acc.puml`, `3_ari.puml`
