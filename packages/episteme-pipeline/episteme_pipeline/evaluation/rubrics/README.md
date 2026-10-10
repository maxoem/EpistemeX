# Human Review Rubrics (Pilot)

## Scope

Use for sampled cases in the domain review set (EN/DE scholarly texts) focusing on difficult global relations and ambiguous entity links.

## Rubric A — Global Relations
- Support Adequacy (0–2): 0 = unsupported; 1 = weak/implicit; 2 = explicit evidence.
- Directionality (0/1): correct arrow between source and target.
- Type Correctness (0/1): relation label matches schema intent.
- Grounding (0/1): evidence points to concrete spans/chunks.
- Notes: free‑text with span indices.

Scoring: Report per‑item scores and an aggregate adequacy distribution; compute inter‑annotator agreement (Cohen’s κ) on a 20% subset.

## Rubric B — Entity Linking
- KB Target Validity (0/1): correct canonical entity.
- Ambiguity Handling (0–2): 0 = wrong; 1 = plausible but incorrect; 2 = correct with disambiguation evidence.
- Cluster Consistency (0/1): mention assignments consistent within document.
- Notes: free‑text with anchors.

Agreement: compute accuracy agreement and κ on the subset.

## Instructions for Reviewers
- Work from the artifacts exported for the run; do not consult external sources unless the mode is explicitly retrieval‑assisted.
- Record decisions in the provided CSV/JSON template in `experiments/<run_id>/human_review/`.

