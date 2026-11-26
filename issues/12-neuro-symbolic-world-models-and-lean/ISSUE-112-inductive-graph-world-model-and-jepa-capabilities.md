# [ISSUE-112] Inductive Graph World Models (Graph-JEPA / EBM): Architecture, Capabilities & Research Guide

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-112` |
| **Domain / Category** | `12-Neuro-Symbolic World Models & Lean` (Representation Learning, JEPA, Energy-Based Models) |
| **Target Package(s)** | `episteme-formal` (world model module), `episteme-pipeline`, `episteme-studio` |
| **Priority** | **High** |
| **Status** | `Research` |
| **Roadmap Horizon** | Horizon 2 & 3 (connects to [Roadmap: World Models](../../docs/roadmap.md#L255-L271) & [Future Research Goals](../../docs/research/future_research_goals.md)) |
| **Governing ADR** | [ADR-0025 Proposal](ADR-0025-PROPOSAL-epistemic-commit-cascade-and-world-models.md) |

---

## 1. Critical Disambiguation: Three Incompatible Meanings of "Shallow Embeddings"

In designing a Graph World Model alongside Lean 4, two unrelated technical terms frequently collide under the phrase *"shallow embeddings"*:

| Concept | Domain & Key Reference | Mathematical Nature | Inductive on Unseen `Insert` Nodes? | Role in Episteme |
| :--- | :--- | :--- | :--- | :--- |
| **1. Shallow Semantical Embeddings (SSE)** | Formal Logic / LogiKEy (Benzmüller et al., 2020) | Symbolic HOL/Lean type-theory definitions encoding non-classical modalities (`□φ := λw. ∀v, R w v → φ v`). **Zero vectors, non-trainable.** | N/A (Symbolic macros) | **Lean 4 preamble** in [ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md); cannot feed a neural World Model. |
| **2. Transductive Shallow Graph Embeddings** | KGE Literature (TransE, RotatE, QuatE; [Future Goals §2.1](../../docs/research/future_research_goals.md#L121-L131)) | Fixed lookup matrix $\mathbf{E} \in \mathbb{R}^{|V| \times d}$ (or $\mathbb{H}^{|V| \times d}$) memorizing static entity IDs. | **NO (Fatal OOV flaw).** Newly inserted candidate atoms have no row in $\mathbf{E}$ without retraining. | Unsuitable as a standalone Active-Mode World Model; cannot handle zero-shot `Insert` episodes. |
| **3. Inductive Text-Graph Encoders & Graph-JEPA** | Deep Graph SSL (Skenderi et al., 2023; Galkin et al., 2024; LeCun, 2022) | Parameterized neural encoder $s_x = \text{Enc}_\theta(G_{\text{local}}, \mathbf{X}_{\text{text}})$ combining pretrained text embeddings with message-passing / Graph Transformers. | **YES (Zero-shot inductive).** Maps any unseen statement + local subgraph topology into latent state space immediately. | **Required architecture** for Episteme's Mode-1 World Model. Quaternion Hamilton products ($\mathbb{H}^d$) can serve as the *relational predictor head* inside this inductive encoder! |

---

## 2. Mathematical Formulation: TheoryNet Graph-JEPA / Latent-Variable EBM

Following Yann LeCun (*A Path Towards Autonomous Machine Intelligence*, 2022, §4.2–4.5), the World Model does **not** autoregressively generate raw text tokens or full JSON graphs (which wastes capacity on irrelevant rhetorical surface details). Instead, it evaluates compatibility and predicts missing structure inside an **abstract representation space**:

### 2.1 Architecture
Given a `ScopedVerificationContext` $x = G_{\text{local}}$ (including `L1`/`L2` text embeddings, `ScopeType`, `EpistemicStatus`, and `TheoryRelation` edge types) and a candidate `EpistemicChangeset` $y = \Delta_{\text{prop}}$:

1. **Dual Inductive Encoders:**
   $$s_x = \text{Enc}_\theta(G_{\text{local}}) \in \mathbb{R}^d \text{ (or } \mathbb{H}^{d/4}\text{)}, \qquad s_y = \text{Enc}_\psi(\Delta_{\text{prop}}) \in \mathbb{R}^d$$
   - Text features are initialized from Episteme's frozen `EmbeddingModel` (augmented with contrastive relation tuning, cf. SimKGC, Wang et al., 2022).
   - Structural features encode heterogeneous relation types (`SUPPORTS`, `ATTACKS`, `UNDERCUTS`, `SPECIALIZES`) via edge-conditioned Graph Transformer / GATv2 layers (e.g., GraphGPS, Rampášek et al., 2022) or relational-foundation message passing (ULTRA, Galkin et al., 2024).
   - Optional **Hypercomplex Predictor Head** (Nayyeri et al., 2022): models non-commutative inferential composition via 4D Hamilton products $q_1 \otimes q_2 \neq q_2 \otimes q_1$ in $\mathbb{H}^{d/4}$.

2. **Latent-Variable Predictor & Regularized Energy Function:**
   The latent variable $z \in \mathcal{Z}$ parameterizes unobserved inferential context—specifically **unrecovered bridging premises (enthymemes)** or **alternative valid specializations** (LeCun §4.2, Fig. 9 & Fig. 12):
   $$F_w(G_{\text{local}}, \Delta_{\text{prop}}) = \min_{z \in \mathcal{Z}} \Bigl( D\bigl(s_y, \text{Pred}_\phi(s_x, z)\bigr) + \lambda \, R(z) \Bigr)$$
   where $R(z)$ is an information-capacity regularizer (e.g., discrete VQ codebook or $L_1$ sparsity penalty) preventing **informational collapse** (where a high-capacity $z$ could trivially copy $s_y$ and flatten the energy surface to zero).

### 2.2 Hybrid Non-Contrastive (VICReg) + Verified Margin Hinge Objective
To prevent representation collapse without relying on naive random negative sampling (which suffers from the curse of dimensionality and false negatives in philosophy):
- **Non-Contrastive Regularization (LeCun §4.5.1, Bardes et al., 2022):** Apply VICReg **Variance** (std $> \gamma$ per dimension) and **Covariance** (off-diagonal covariance $\to 0$) terms over expander projections $v_x, v_y$ of $s_x, s_y$.
- **Verified Contrastive Hinge on Mode-2 Hard Negatives (LeCun Eq. 7):** Whenever the `VerificationTrajectoryStore` provides Lean-4-certified refutations ($\Gamma \vdash \neg\phi$) or verified non-sequiturs ($\Delta_{\text{neg}}$), apply a pairwise margin hinge pushing the energy of invalid derivations above valid ones:
  $$\mathcal{L}_{\text{hinge}} = \bigl[ F_w(x, y^+) - F_w(x, y^-) + m(y^+, y^-) \bigr]^+$$

---

## 3. Deep-Dive: The Four Strategic Capabilities for Episteme (Points 1–4)

### Capability 1 — Millisecond Mode-1 Compatibility & Anomaly Oracle
* **What it does:** Evaluates $E_{\text{WM}} = \sigma(F_w(G_{\text{local}}, \Delta_{\text{prop}})) \in [0, 1]$ in $< 20\text{ms}$ before invoking expensive agentic Lean 4 proof search (which takes seconds to minutes per episode) or LLM relation reranking.
* **Where it plugs in:**
  1. **Inside `EpistemicCommitInterceptor` (`CalibratedCascade`):** Low-energy, high-confidence insertions fast-exit without Lean 4 overhead (except deterministic SHA-256 audit samples); high-energy anomalies or borderline conformal prediction sets escalate to Mode 2.
  2. **Inside Phase 3 Global Relations:** Replaces pure cosine similarity (which conflates topical proximity with inferential validity, [Future Goals §2.2](../../docs/research/future_research_goals.md#L132-L150)) as a topological-relational filter.
* **Research Question:** How well does $E_{\text{WM}}$ calibrated via Conformal Prediction (mirroring `Jev`, [ADR-0018](../../docs/adr/0018-decision-engine-architecture-and-contracts.md)) predict Mode-2 Lean 4 `refuted` / `sketch_verified` outcomes across held-out philosophical works?

### Capability 2 — Latent Enthymeme Vector Prediction ($\text{Pred}(s_x, z) \to \tilde{\mathbf{s}}_z$) for Targeted Text Retrieval
* **What it does:** When a premise set $A$ and conclusion $B$ exhibit a deductive gap (high compatibility energy under $z = 0$, or `ENTHYMEME_GAP` deficit in [ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)), the JEPA predictor solves for the optimal bridging latent $\check{z}$ and emits the **predicted representation vector** $\tilde{\mathbf{s}}_z$ of the missing intermediate node—without hallucinating prose!
* **How it integrates with Layer 1/2:** Projecting $\tilde{\mathbf{s}}_z$ into the dense retrieval space of `ArtifactSubgraphReader` / Neo4j vector index queries the source corpus (`L1Chunk`) for the exact passage—potentially 50 pages earlier—where the author stated the suppressed premise, feeding directly into `LLMTheoryGuidedPremiseRecoverer` ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md#L47)).
* **Theoretical Link:** Directly operationalizes LeCun §4.4 (*"predictions in representation space, eschewing the need to predict every detail"*) + Reasoning on Graphs (RoG, Luo et al., 2023).

### Capability 3 — Counterfactual Belief Revision & Sensitivity Rollouts (`episteme-studio`)
* **What it does:** Extends single-step JEPA into a **Hierarchical / Multi-Step Transition World Model (`H-JEPA`, LeCun §4.6–4.7)** that simulates latent state trajectories $s_{t+1} = \text{Pred}(s_t, a_t)$ under hypothetical graph actions $a_t \in \{\text{retract}(v), \text{negate}(v), \text{split}(e), \text{specialize}(T_i)\}$.
* **Interactive Research Workflow in `episteme-studio`:**
  - A scholar asks: *"What happens to the coherence and stability of Kant's transcendental deduction if Axiom $A_3$ is retracted or negated?"*
  - Instead of re-running a 10-minute `D-QBAF` + Lean 4 pass for every slider drag or what-if probe, the World Model predicts downstream energy shifts across the `TheoryNet` hierarchy in milliseconds, identifying Lakatosian **hard-core** vs. **protective-belt** nodes.
* **Connection to Roadmap:** Operationalizes [`docs/roadmap.md`](../../docs/roadmap.md#L255-L271) (*World Models for Empirical Node Validation & Counterfactual Stress-Testing*).

### Capability 4 — Mode-2 $\to$ Mode-1 Amortized Inference Distillation (Solving the Philosophical Data Bottleneck)
* **The Data Bottleneck:** There is no "ImageNet for philosophical TheoryNets." Training a Graph World Model solely on raw LLM-extracted graphs merely distills LLM extraction biases and hallucinated edges.
* **The Solution (LeCun §3.1.3 Fig. 5 & §3.3 Fig. 7):** Every Mode-2 run of the Lean 4 oracle ([ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)) writes a **deterministically verified trajectory** into `VerificationTrajectoryStore`:
  - **Positive Anchors:** Certified `entailed` and `consistent_independent` subgraphs.
  - **Latent Supervision ($z^*$):** Minimal `proof-sketch` lemmas discovered by the Lean agent provide direct supervision for the JEPA latent space $\mathcal{Z}$.
  - **Hard Negatives ($y^-$):** Certified `refuted` contradictions ($\Gamma \vdash \neg\phi$) and rejected non-sequiturs provide the exact "most offending" negative examples (LeCun §4.3 Table 1) that random corruption cannot synthesize.
* **Result:** Mode-2 symbolic reasoning is continuously *amortized* into a fast, differentiable Mode-1 World Model.

---

## 4. Annotated Research Guide & Primary Literature

Use the following reading and experiment map to deepen the mathematical and empirical design of `ISSUE-112`:

| Paper / Source | Core Concepts for Episteme | Specific Sections / Mechanisms to Inspect |
| :--- | :--- | :--- |
| **LeCun (2022)**, *A Path Towards Autonomous Machine Intelligence* (v0.9.2) | Cognitive architecture (Configurator, STM, World Model, Actor, Critic); LVEBM, JEPA, H-JEPA, Mode-2 $\to$ Mode-1 amortized inference. | **§3.1.2–3.1.4** (Mode-2 MPC & Mode-1 skill compilation), **§3.3** (Critic training from associative STM), **§4.2–4.6** (LVEBM collapse, VICReg, H-JEPA), **§4.9** (Writable entity-state memory). |
| **Bardes, Ponce, & LeCun (ICLR 2022)**, *VICReg: Variance-Invariance-Covariance Regularization* (`arXiv:2105.04906`) | Non-contrastive collapse prevention without negative pairs or momentum encoders. | Expander MLP design ($v_x, v_y$) and variance/covariance hinge weights for heterogeneous graph embeddings. |
| **Skenderi et al. (2023)**, *Graph-JEPA: A Joint-Embedding Predictive Architecture for Graph-Level Representations* (`arXiv:2309.16014`) | Adapting JEPA masked-block prediction to non-Euclidean subgraphs + hyperbolic/hierarchical coordinate targets. | Subgraph partitioning & predictor conditioning; adapting hyperbolic unit-hyperbola targets to Sneed/Balzer **Poset Theory-Trees**. |
| **Galkin et al. (ICLR 2024)**, *Towards Foundation Models for Knowledge Graph Reasoning (ULTRA)* (`arXiv:2310.04562`) | Fully **inductive** zero-shot KG reasoning across unseen entities and unseen relation vocabularies via relative relation graphs. | Relation-interaction graph construction—critical when Episteme extracts new domain predicates or splits `EntityConception`s. |
| **Rampášek et al. (NeurIPS 2022)**, *Recipe for a General, Powerful, Scalable Graph Transformer (GraphGPS)* (`arXiv:2205.12454`) | Combining local MPNN message passing with global Transformer attention + structural positional encodings. | Random-walk / Laplacian positional encodings on directed TheoryNets to distinguish root axioms $T_0$ from leaves. |
| **Nayyeri et al. (2022)** & **Wang et al. (ACL 2022)** (*SimKGC*, `arXiv:2203.06478`) | 4D Hypercomplex Quaternion KG-Text fusion ($\mathbb{H}^d$) and Siamese InfoNCE text-graph alignment. | Using Hamilton products as the **relational predictor head** inside an inductive Graph-JEPA; see [Future Goals §1.1 & §1.3](../../docs/research/future_research_goals.md). |
| **Luo et al. (2023)**, *Reasoning on Graphs (RoG)* (`arXiv:2310.01061`) | Planning-retrieval-reasoning over KGs with faithful relation-path plans. | Aligning latent trajectory rollouts with explicit, auditable Neo4j relation paths. |

### Recommended First Research Experiments (Benchmarks)
1. **Inductive Zero-Shot Split:** Hold out 20% of documents/philosophers entirely during training (disjoint entity & claim vocabulary) to prove zero-shot generalization over unseen `Insert` nodes—verifying superiority over transductive TransE/QuatE baselines.
2. **Negation & Antinomy Sensitivity Probe:** Test whether $F_w(G_{\text{local}}, \phi)$ assigns sharply higher energy to $\neg\phi$ than $\phi$ when $\Gamma \vdash \phi$ (exposing standard cosine similarity's "negation blindness", cf. [ISSUE-089](../11-epistemetrics-formal-concept/epistemic_coherence/ISSUE-089-CONSISTENCY.md)).
3. **Latent Enthymeme Retrieval Recall@k:** Mask known intermediate premises in `TheoryNet` chains, solve for $\tilde{\mathbf{s}}_z$, and measure Recall@5 / MRR against actual `L1Chunk` ground-truth evidence spans vs. direct LLM query generation.

---

## 5. Acceptance Criteria

- [ ] Specify inductive `GraphWorldModelEncoder` + `JEPAWorldModelEvaluator(EpistemicEvaluator)` interface in `packages/episteme-formal/`.
- [ ] Implement offline training pipeline consuming `VerificationTrajectoryStore` with VICReg + Mode-2 verified margin hinge loss.
- [ ] Pass zero-shot unseen-document generalization and negation-sensitivity unit benchmarks before enabling Mode-1 fast-exit in `CalibratedCascade`.
