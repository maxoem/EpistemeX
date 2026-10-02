# [ISSUE-045] Phase 3b Latent Graph Consolidation: Borderline Cluster Merge & Canonical Election

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-045` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase3b_consolidation/runner.py`, `pipeline/phases/phase3b_consolidation/clustering.py`, `pipeline/config.py`) |
| **Roadmap Horizon** | **Horizon 2** (Knowledge Graph Fusion & Topological Invariance) |
| **Priority** | Medium |
| **Status** | Completed |
| **Source Ref** | `docs/workflow/3b_consolidation/index.md`, ADR 0005 (`0005-two-pass-fusion-strategy.md`) |

---

## 1. Problem Statement & Motivation
Phase 3b (Latent Graph Consolidation) performs a non-generative mathematical sweep over dense entity embeddings and 1-hop relational signatures to merge parallel entity duplicates. It computes pairwise cosine similarities and Jaccard relation overlaps to form Union-Find clusters, electing a canonical entity for each cluster.

However, two major challenges arise:
1. **The Borderline Similarity Band ($0.75 \le \text{cosine} \le 0.88$)**:
   - Entities in this grey zone (e.g. *"Categorical Imperative"* vs. *"Hypothetical Imperative"*, or *"Transcendental Aesthetic"* vs. *"Transcendental Analytic"*) exhibit high embedding similarity and overlapping relational neighborhoods, but are conceptually distinct or hierarchically related.
   - Relying solely on vector distance thresholds leads to catastrophic over-merging of antonymous or distinct concepts.
2. **Canonical Entity Election**:
   - Currently, canonical entity election uses simple heuristic criteria (e.g. mention count or string length), which often elects an overly specific or colloquial surface form rather than the standard philosophical terminology.

TypeSafe Jev provides the ideal decision oracle to verify borderline clusters and elect canonical entities with calibrated confidence.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Jev Borderline Cluster Verifier (`pipeline/phases/phase3b_consolidation/clustering.py`)**:
   - Add `async def verify_borderline_pair(entity_a: L2Entity, entity_b: L2Entity, decision_engine: DecisionEngine, alpha: float = 0.05) -> tuple[str, float]`:
     - Calls Jev `Choice`:
       - `state`: Names, descriptions, and salient 1-hop relation signatures of both entities (budgeted to $\le 800$ tokens to fit within ModernBERT 1,024 limit).
       - `options`: `["IDENTICAL_MERGE", "HIERARCHICAL_SUBSUMPTION", "DISTINCT_SEPARATE"]`.
     - Returns selected relationship and `empirical_accuracy`.
     - **Conformal Merge Guard**: Entities are only merged in Union-Find if the conformal prediction set $C(X)$ is strictly singleton $\{\text{"IDENTICAL\_MERGE"}\}$ (or $\text{empirical\_accuracy} \ge \tau_{\text{merge}}$). If the prediction set contains multiple labels (e.g. `{"IDENTICAL_MERGE", "HIERARCHICAL_SUBSUMPTION"}`), merging is aborted to prevent collapsing hierarchical distinctions.
2. **Jev Canonical Representative Election**:
   - Add `async def elect_canonical_representative(cluster_entities: list[L2Entity], decision_engine: DecisionEngine) -> L2Entity`:
     - Uses Jev `Choice` over candidate entity names in the cluster to select the most standard, canonical academic surface form.
3. **Configuration Flags (`pipeline/config.py`)**:
   - Extend `Phase3bConfig` with:
     - `enable_jev_cluster_verification: bool = False`
     - `borderline_similarity_lower: float = 0.75`
     - `borderline_similarity_upper: float = 0.88`
     - `merge_confidence_threshold: float = 0.80`
     - `conformal_merge_alpha: float = 0.05`

### What to Change
1. **`Phase3bLatentConsolidationRunner`**:
   - Inject `DecisionEngine` during initialization and invoke borderline verification prior to finalizing Union-Find sets.

### What to Remove
- Remove blind threshold merging within the ambiguous vector similarity band.

---

## 3. Acceptance Criteria
- [x] Entities in the borderline similarity band are verified via Jev `Choice` in $<150\text{ms}$.
- [x] Antonymous and hierarchically distinct concepts with high vector proximity are protected from incorrect merges.
- [x] The elected canonical entity name consistently matches the standard scholarly designation.
- [x] Deterministic unit tests verify that borderline distinct pairs remain separate in the final graph.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/runner.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/clustering.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/tests/test_phase3b_jev_consolidation.py`

---

## 5. Documentation Updates Required
- Update the Phase 3b Latent Graph Consolidation workflow documentation (`docs/workflow/3b_consolidation/`) with the Jev borderline verification protocol.
- Update ADR 0005 (Two-Pass Fusion Strategy) to document semantic merge protection.
