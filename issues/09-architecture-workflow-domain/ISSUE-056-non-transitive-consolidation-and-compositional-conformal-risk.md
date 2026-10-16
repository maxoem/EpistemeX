# [ISSUE-056] Non-Transitive Consolidation & Compositional End-to-End Conformal Risk Control

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-056` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Uncertainty Propagation, Clustering Topology, Statistical Guarantees) |
| **Target Package(s)** | `packages/episteme-pipeline` (`phases/phase3b_consolidation/`, `phases/phase5_fusion/`, `decision/conformal.py`) |
| **Priority** | **Medium** |
| **Status** | `Open` |
| **Evaluated Docs & ADRs** | [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md), [`docs/architecture/pipeline_architecture.md`](../../docs/architecture/pipeline_architecture.md), [`ADR-0003`](../../docs/adr/0003-coreference-absorbed-into-fusion.md), [`ADR-0005`](../../docs/adr/0005-two-pass-fusion-strategy.md), [`ADR-0018`](../../docs/adr/0018-decision-engine-architecture-and-contracts.md) |

---

## 1. Current State

1. **Transitive Union-Find Clustering in Phase 3b & Phase 5**:
   - In [`docs/architecture/pipeline_architecture.md`](../../docs/architecture/pipeline_architecture.md) (§Phase 3b and §Phase 5) and [`ADR-0005`](../../docs/adr/0005-two-pass-fusion-strategy.md), both entity consolidation (`Phase3bLatentConsolidationRunner`) and argument clustering (`EmbeddingArgumentClustering`) evaluate pairwise similarity/conformal gates and merge accepted pairs using **Union-Find (Disjoint-Set) connected components**, emitting hard `CanonicalizationArtifact`s (`confidence: 1.0`).
2. **Isolated Per-Stage Conformal $\alpha$ Budgets**:
   - [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md) applies Split Conformal Prediction with a uniform significance level $\alpha$ (e.g., $\alpha = 0.05$) independently at each decision stage (Phase 2 linking, Phase 3 reranking, Phase 3b consolidation, Phase 4 ACC/ARC, Phase 5 fusion).

---

## 2. Why This Causes Problems

### A. Researcher & Mathematical Topology Perspective
1. **Single-Linkage Chaining Pathology in Union-Find**:
   - Semantic similarity and philosophical concept overlap are **not transitive relations**: Concept $A$ may share context with polysemous bridge concept $B$ ($A \sim B$), and $B$ may share context with $C$ ($B \sim C$), while $A$ and $C$ are distinct or mutually opposing concepts ($A \not\sim C$).
   - Union-Find computes connected components over accepted pairs, enforcing strict transitive closure. A single false-positive link (which occurs with probability $\le \alpha = 0.05$ even under perfect conformal calibration!) acts as a bridge that merges two entire concept clusters into a single giant component.
2. **Multiplicative Error Compounding Across Sequential Phases**:
   - Conformal prediction's $1 - \alpha$ guarantee applies to a single decision step. Across $M$ sequential pipeline gates ($M \approx 5\text{--}7$), if each stage commits hard point decisions at level $\alpha = 0.05$, the family-wise probability that a downstream TheoryNet subgraph is free of upstream gating errors degrades to $(1 - \alpha)^M \approx 0.95^6 \approx 73.5\%$.

---

## 3. Proposed Solution & Architectural Explanation

### Step 1: Replace Transitive Union-Find with Correlation Clustering / Clique-Constrained Consolidation
- In Phase 3b (`LatentGraphConsolidation`) and Phase 5 (`EmbeddingArgumentClustering`), replace unconstrained Union-Find connected components with **Complete-Linkage / Correlation Clustering (Bansal et al., 2004)** or **Minimum Cut / Diameter-Bounded Clique Merging**:
  - A candidate node $u$ is merged into an existing cluster $C$ if and only if:
    1. Its similarity / conformal agreement holds with the **cluster centroid / canonical representative** $c^* \in C$, **AND**
    2. $\min_{v \in C} \text{sim}(u, v) \ge \tau_{\text{floor}}$ (no internal pair inside the merged cluster falls into the `DISTINCT_SEPARATE` or `COMPETING_THEORIES` conformal zone).
  - This mathematically prevents single-linkage bridge chaining ($A \sim B \sim C$) from collapsing distinct concepts $A$ and $C$.

### Step 2: Compositional Conformal Risk Control ($\alpha$-Allocation Across Pipeline Stages)
- Introduce a pipeline-level **Global Epistemic Risk Budget ($\alpha_{\text{global}}$)** in `DecisionEngineConfig` that allocates per-phase conformal significance levels $(\alpha_1, \dots, \alpha_M)$ via sequence-level risk budgeting (e.g., weighted union bound $\sum_{m=1}^M w_m \alpha_m \le \alpha_{\text{global}}$ or Conformal Risk Control [Angelopoulos et al., 2022]), assigning tighter $\alpha_m$ thresholds to irreversible structural phases (such as Phase 3b entity consolidation) and more permissive thresholds to soft-weighted edges.

---

## 4. Acceptance Criteria

- [ ] Phase 3b and Phase 5 enforce diameter / minimum-internal-similarity constraints during cluster formation instead of unconstrained transitive Union-Find.
- [ ] `DecisionEngineConfig` supports per-phase / per-task $\alpha_m$ allocation derived from a global pipeline risk budget $\alpha_{\text{global}}$.
