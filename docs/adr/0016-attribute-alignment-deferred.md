# [0016] Attribute Alignment Deferred — Representing Contradictions via Graph Edges

Status: Accepted

## Context

Initially, Phase 5 of the pipeline was designated as "Alignment Fusion" and scoped to include **Attribute Alignment** —
a process for schema normalization, conflict resolution, and attribute fusion across multi-document theoretical corpora.

In conventional Knowledge Graph construction (e.g., enterprise KGs or factual entity resolution), encountering differing attribute values (such as differing birthdates or addresses) is treated as an engineering "fusion" or deduplication problem, typically resolved by heuristic voting, source-authority scoring, or recency weighting.

However, scientific literature and philosophical discourse operate under fundamentally different dynamics. Disagreements in theoretical texts are not noisy measurement defects to be averaged out; they represent substantive doctrinal conflicts, competing hypotheses, or alternative definitions.

## Decision

During the pipeline consolidation review (W-06), **Attribute Alignment and automated conflict resolution were marked as considered-and-deferred**.

Under the formal model of the Theory Graph (TheoryNet $TF = (At, R)$ grounded in $\Delta = (B, A)$), encountering contradictory attribute values across different documents is not an engineering fusion defect to be reconciled automatically by "picking a winner". Instead, genuine theoretical disagreement is modeled as a first-class relation:

- Contradictory claims are preserved as distinct nodes in Layer 3.
- The conflict is modeled explicitly via an inhibitory or refutational relation edge (e.g., `WIDERSPRICHT` / `ATTACKS` $\in \mathcal{R}_{att}$).

Building an automated conflict resolver would obscure real-world disagreements in the source literature, contradicting the intended purpose of the theory graph. Therefore, automated attribute fusion is deferred indefinitely until a theoretically sound method for capturing both consensus and contradiction is modeled.

> **Extension ([ADR 0023](0023-intensional-perspectival-scoping-and-conception-stratification.md)):** While incompatible doctrinal descriptions are still never flattened via destructive attribute merging, Phase 4 Entity Maturation now stratifies divergent entity mention envelopes into coexisting, perspective-scoped `EntityConception` facets attached to the shared canonical `L2Entity` referential topic.

## Consequences

### Positive
- Prevents artificial consensus and semantic distortion of contested philosophical theories.
- Preserves the dialectical structure of scientific disputes for downstream epistemic evaluation (e.g., Thagard coherence or Dung extension resolution).
- Avoids brittle ad-hoc attribute resolution heuristics in Phase 5.

### Negative
- Consumers of the graph must query relational edges rather than expecting a single flattened attribute value per entity.

## Related Documents
- [Formal Graph Schema (TheoryNet)](../concepts/formal_graph_model.md)
- [ADR 0006: QBAF Weight Computation Deferred](0006-qbaf-mapping-deferred.md)
- [ADR 0005: Two-Pass Fusion Strategy](0005-two-pass-fusion-strategy.md)
- [ADR 0023: Intensional & Perspectival Scoping and Conception Stratification](0023-intensional-perspectival-scoping-and-conception-stratification.md)
