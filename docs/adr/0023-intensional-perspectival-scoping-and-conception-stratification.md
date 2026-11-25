# [0023] Intensional & Perspectival Scoping and Conception Stratification

Status: Accepted  
Date: 2026-11-14  
Extends: ADR-0003 (Coreference Absorbed into Fusion), ADR-0011 (D-QBAF Gradual Semantics), ADR-0016 (Attribute Alignment Deferred), ADR-0020 (Propositional Modal Strength Resolver), ADR-0022 (Unified Stratified Epistemic Metamodel)

---

## Context

Scientific monographs and philosophical treatises interleave three rhetorically distinct registers alongside the author's positive assertions:

1. **Suppositional / Counterfactual / *Reductio ad Absurdum* Premises** (Layer 3): Hypothetical premises introduced strictly to derive an absurdity or test an implication before refutation (*"Suppose for the sake of argument that space is merely an empirical abstraction..."*).
2. **Exegetical / Opponent Attributions** (Layer 3): Extended reconstructions of another thinker's or school's commitments (*"According to Leibniz, space is merely an order of coexistences..."*) preceding critique, as well as competing scholarly readings of the same primary passage.
3. **Theory-Laden Doctrinal Polysemy Across Texts** (Layer 2): Foundational theoretical terms (*Space*, *Substance*, *Causality*, *Entropy*) sharing a canonical referential topic (`L2Entity`) across works or epochs while receiving incompatible intensional definitions across distinct frameworks.

Without intensional scoping and conception stratification, *Reductio* assumptions and opponent summaries pollute authorial D-QBAF equilibrium acceptability $s^*(a)$, and averaging all mention embeddings into one centroid per `L2Entity` erases doctrinal shifts across frameworks.

---

## Decision

We implement **Layer 3 Intensional & Perspectival Scoping** and **Layer 2 Referent-vs-Conception Stratification** (symbols follow [`docs/concepts/notation.md`](../concepts/notation.md)):

### 1. Intensional Mode, Attribution & Exegetical Reading Index on Layer 3 Atoms

- `TheoryAtom`, `TheoryAtomArtifact`, `ExtractedComponent`, and `epistemetrics.core.models.TheoryNode` carry:
  - `intensional_mode` ($\iota(a) \in \{\text{asserted}, \text{attributed}, \text{suppositional}, \text{historical}\}$, canonicalized via `IntensionalMode.from_str`).
  - `attributed_to` ($\operatorname{agent}(a) \in \mathcal{P} \cup \{\bot\}$) identifying the cited author or school when `intensional_mode == "attributed"`.
  - `reading_id` ($\operatorname{rd}(a)$, optional) indexing competing exegetical readings of the same primary passage. Alternative interpretations are linked via structural relation `ALTERNATIVE_READING_OF` (polarity `0`, in $\mathcal{R}_{\text{str}}$ and excluded from $\mathcal{R}_{\text{att}}$) so interpretive pluralism is not fabricated into dialectical attacks.
- `LLMACCClassifier`, `ACC_*_PROMPT` templates, lossless `TheoryAtomCodec`, dependency fingerprinting in `build_theory_atom_artifact`, and Neo4j mappers (`theory_atom_to_graph_properties`, `Neo4jStore.get_theory_atoms`) preserve and index these fields end-to-end.

### 2. Perspective-Filtered & Supposition-Aware D-QBAF Evaluation

- `TheoryAtom.effective_base_prior(include_suppositional=..., perspective=..., base_prior_policy=...)` and `epistemetrics.epistemic.qbaf.QBAFGradualSemanticsSolver` (including `solve_qbaf_gradual_semantics`, `solve_continuous_qbaf`, `TheoryNetProjector`, and `Phase6Config` / `Phase6Runner`) support:
  - `perspective`: `"author"` (or `None`), `"<Agent>"`, `"all"`, or `"suppositional"`.
  - `isolate_suppositional: bool = True`: Isolates `suppositional` nodes from contributing unconditioned prior mass ($\tilde{\beta}(a) = 0$) or spurious support/attack weight into non-suppositional claims.
  - `isolate_attributed: bool = True`: Prevents cross-perspective `attributed` nodes from contaminating authorial claims unless explicitly evaluating `"all"` or the matching `perspective="<Agent>"` subgraph $\mathcal{D}_{\text{agent}}$.
- `QBAFSolverResult` reports `perspective`, `suppositional_isolated_count`, and `perspective_filtered_count` for auditability.

### 3. Referent-vs-Conception Stratification in Phase 4 Entity Maturation

- `EntityConception` (`id`, `entity_id`, `perspective`, `description`, `representative_envelopes`, `source_chunk_ids`, `centroid_dispersion`, `confidence`) alongside `L2Entity.conceptions` and `L2Entity.polysemy_variance` (persisted in `LinkedEntityArtifact`, `LinkedEntityCodec`, and Neo4j `upsert_entities` / `_entity_from_row`).
- `ConceptionClusterer(Fingerprintable)` inside `Phase4EntityMaturationRunner`:
  - Normalizes contextual mention embeddings onto the unit hypersphere and measures spherical dispersion $v_{\text{poly}}(e) = 1 - \|\frac{1}{N} \sum_{i=1}^N \hat{\mathbf{e}}_i\|_2$.
  - When $v_{\text{poly}}(e) > \tau_{\text{polysemy}}$ (`Phase4EntityMaturationConfig.polysemy_variance_threshold`), partitions envelopes along explicit document/theory perspectives (when centroids diverge beyond threshold) or via deterministic farthest-first spherical $k$-means scored by cosine silhouette coherence (`min_silhouette_score`).
  - Preserves the single unified `L2Entity` as the canonical **Referential Topic** while synthesizing separate `EntityConception` facets per coherent cluster and emitting `EntityConceptionStratified`. Uni-modal entities synthesize a single canonical description with zero overhead.

---

## Alternatives Considered

- **Splitting polysemous entities into disconnected `L2Entity` nodes in Phase 3b**: Rejected because cross-document co-reference on the shared topic (e.g., *Space* debated by Kant and Leibniz) is essential for linking debates across works ([ADR-0003](0003-coreference-absorbed-into-fusion.md)); splitting referents would break cross-theory argumentation graphs.
- **Handling *Reductio* and attributions solely via edge-level negation weights**: Rejected because assigning negative or reduced scalar weights conflates inferential warrant (`TheoryRelation`) with speech-act / intensional mode ([ADR-0022](0022-unified-stratified-epistemic-metamodel.md)) and fails when exegesis contains valid internal `SUPPORTS` chains inside an opponent's system.

---

## Consequences

### Positive

- **Unpolluted Authorial Justification**: *Reductio* premises and opponent reconstructions no longer inflate asserted claims in authorial D-QBAF convergence while remaining queryable inside agent-specific subgraphs $\mathcal{G}_{\text{agent}}$.
- **Doctrinal Fidelity in Layer 2**: Competing theory-laden conceptions coexist as structured `EntityConception` facets anchored to one shared canonical `L2Entity` referent, operationalizing multi-perspective representation compatible with [ADR-0016](0016-attribute-alignment-deferred.md).
- **Full Reproducibility & Observability**: `ConceptionClusterer` and `TheoryNetProjector` implement `Fingerprintable`, and maturation stratification emits `EntityConceptionStratified`.

### Negative / Trade-offs

- **Additional Structured Synthesis Calls for Stratified Entities**: Entities exceeding `polysemy_variance_threshold` invoke one structured LLM synthesis call per coherent conception cluster (capped by `max_conceptions_per_entity`) rather than one call globally. Uni-modal entities incur no extra LLM calls.
- **Prompt Calibration Dependence**: Accurate separation of `suppositional` and `attributed` ADUs depends on Phase 4 ACC classification fidelity.

---

## Related

- [ISSUE-054: Intensional & Perspectival Scoping](../../issues/archived/09-architecture-workflow-domain/resolved/ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md)
- [Formal Graph Schema & Argumentation Semantics](../concepts/formal_graph_model.md)
- [Assumptions and Limitations](../concepts/assumptions_limitations.md)
- [ADR-0003: Coreference Resolution Absorbed into Phase 3b](0003-coreference-absorbed-into-fusion.md)
- [ADR-0016: Attribute Alignment Deferred](0016-attribute-alignment-deferred.md)
- [ADR-0020: Propositional Modal Strength Resolver](0020-propositional-modal-strength-resolver.md)
- [ADR-0022: Unified Stratified Epistemic Metamodel](0022-unified-stratified-epistemic-metamodel.md)
- [ADR-0024: Closed-Loop Hermeneutic Refinement](0024-closed-loop-hermeneutic-refinement.md) — Escalates `EntityConception` stratification to targeted post-hoc L2 concept splitting (`ConceptionConceptSplitter` with `cannot_link` guards) when `POLYSEMY_COLLISION` deficits arise.
