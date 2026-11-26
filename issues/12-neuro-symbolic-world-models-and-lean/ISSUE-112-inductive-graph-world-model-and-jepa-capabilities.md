# [ISSUE-112] Type-A World Models: Supervised Inductive Triage, Exact D-QBAF Counterfactuals & Graph-JEPA Research Track

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-112` |
| **Domain / Category** | `12-Neuro-Symbolic World Models & Lean` (Inductive Triage, Counterfactual Rollouts, JEPA Research) |
| **Target Package(s)** | `episteme-worldmodel` (new package), `epistemetrics`, `episteme-studio` |
| **Priority** | **Medium** (Phased: Pragmatic Baseline First, JEPA Research Track in Horizon 3) |
| **Status** | `Research` |
| **Roadmap Horizon** | Horizon 2 (Triage + Exact D-QBAF Rollouts) & Horizon 3 (Graph-JEPA) |
| **Governing ADR & Plan** | [ADR-0025 Proposal](ADR-0025-PROPOSAL-epistemic-commit-cascade-and-world-models.md) \| [Execution Plan](EXECUTION-PLAN.md) |

---

## 1. Pragmatic Engineering Principle: Beat Deterministic Baselines First

A full `GraphGPS + ULTRA + Quaternion + VQ-H-JEPA` model trained with VICReg requires large batch sizes (typically 256–2048) and $10^4$–$10^5$ diverse labeled subgraphs to avoid representation collapse and severe overfitting. On Day 1—or even at $10^3$ Mode-2 Lean trajectories—attempting end-to-end JEPA pretraining is data-starved.

Therefore, `ISSUE-112` structures Type-A capabilities in **two disciplined tiers**:
1. **Tier 1 (Immediate, Low-Data, High-Reliability — Horizon 2):**
   - **Mode-1 Fast Triage:** `DecisionEngine` ([ADR-0018](../../docs/adr/0018-decision-engine-architecture-and-contracts.md)) + a compact **supervised 4-class inductive verifier** (frozen text embeddings + lightweight edge-typed GNN / MLP) calibrated with Episteme's existing [`ConformalCalibrator`](../../packages/episteme-pipeline/episteme_pipeline/decision/conformal.py).
   - **Interactive Counterfactual Rollouts (`episteme-studio`):** **Exact deterministic `D-QBAF` rollouts** using `epistemetrics`'s `QBAFGradualSemanticsSolver` / `WeightedQuadraticEnergySolver` on affected connected components—already running in milliseconds with zero training data and 100% mathematical fidelity!
2. **Tier 2 (Long-Term Research Track — Horizon 3, Gated by $\ge 10^4$ Diverse Trajectories):**
   - **Inductive Graph-JEPA / Latent-Variable EBM:** Explores representation-space compatibility and latent enthymeme vector prediction ($\tilde{\mathbf{s}}_z$) only once `VerificationTrajectoryStore` reaches sufficient corpus diversity and outperforms Tier 1 on held-out works.

---

## 2. Critical Disambiguation: Three Incompatible Meanings of "Shallow Embeddings"

| Concept | Domain & Key Reference | Mathematical Nature | Inductive on Unseen Nodes? | Role in Episteme |
| :--- | :--- | :--- | :--- | :--- |
| **1. Shallow Semantical Embeddings (SSE)** | Formal Logic / LogiKEy (Benzmüller et al., 2020) | Symbolic HOL/Lean type-theory definitions (`box p := fun w => ∀ v, R w v -> p v`). **Zero vectors, non-trainable.** | N/A (Symbolic macros) | **Lean 4 preamble** in `packages/episteme-formal/` ([ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)). |
| **2. Transductive Shallow Graph Embeddings** | KGE Literature (TransE, RotatE, QuatE; [Future Goals §2.1](../../docs/research/future_research_goals.md#L121-L131)) | Fixed lookup matrix $\mathbf{E} \in \mathbb{R}^{|V| \times d}$ memorizing static entity IDs. | **NO (Fatal OOV flaw).** Newly inserted atoms have no row in $\mathbf{E}$. | Unsuitable for zero-shot verification over unseen documents. |
| **3. Inductive Text-Graph Encoders** | Deep Graph Learning (SimKGC, ULTRA, GraphGPS, Graph-JEPA) | Parameterized encoder $s_x = \text{Enc}_\theta(G_{\text{local}}, \mathbf{X}_{\text{text}})$ over frozen text embeddings + local message passing. | **YES (Zero-shot inductive).** | **Required inductive family** for `packages/episteme-worldmodel/`. |

---

## 3. Tier 1: Supervised 4-Class Inductive Triage & Exact Counterfactuals (Horizon 2)

### 3.1 Why 4-Class Calibrated Probabilities Beat a Single Scalar Energy for Triage
In philosophy and science, **`consistent_independent` is the majority valid class** ([ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)). If a scalar energy places `entailed` near `0.0`, `consistent_independent` at `0.5`, and `refuted` at `1.0`, then `0.5` lands directly inside `CalibratedCascade`'s ambiguity band—triggering Mode-2 Lean escalation on almost every valid new claim!

Instead, Tier 1 predicts a calibrated 4-class distribution over:
$$P(c \mid G_{\text{local}}, \Delta_{\text{prop}}), \qquad c \in \{\text{entailed},\; \text{sketch\_verified},\; \text{consistent\_independent},\; \text{refuted}\}$$
using [`ConformalCalibrator`](../../packages/episteme-pipeline/episteme_pipeline/decision/conformal.py):
- **Fast-Exit Accept:** Conformal prediction set $\mathcal{C}_\alpha \subseteq \{\text{entailed}, \text{consistent\_independent}\}$ with low incompatibility probability $P(\text{refuted}) < \tau_{\text{refute}}$ (subject to deterministic SHA-256 auditing).
- **Mode-2 Escalation:** `refuted` or `sketch_verified` is inside $\mathcal{C}_\alpha$, $|\mathcal{C}_\alpha| > 1$ across incompatible actions, or high centrality / user-requested formal check.
- **Scalar Compatibility Summary:** When a single scalar `world_model_energy` is displayed in Studio, define it strictly as **incompatibility risk** $E_{\text{WM}} = P(\text{refuted}) + 0.5\, P(\text{sketch\_verified}) \in [0, 1]$, so *both* `entailed` and `consistent_independent` remain low-energy!

### 3.2 Exact Millisecond Counterfactual Rollouts (`epistemetrics` + `episteme-studio`)
When a scholar in `episteme-studio` asks *"What happens to the stability of Kant's deduction if Axiom $A_3$ is retracted, weakened, or negated?"*:
- **Do NOT approximate with a neural transition model (`H-JEPA`)**—`VerificationTrajectoryStore` does not even contain retraction/negation transition supervision.
- Instead, slice the affected connected component (`slice_phase4_component_view`) and run **`epistemetrics`'s `WeightedQuadraticEnergySolver` / `QBAFGradualSemanticsSolver`** directly on the perturbed subgraph. This computes exact $\Delta \tau^*(a)$ shifts across the `TheoryNet` in milliseconds, deterministically identifying Lakatosian **hard-core** vs. **protective-belt** nodes with zero training data.

---

## 4. Tier 2: Inductive Graph-JEPA / LVEBM Research Track (Horizon 3)

Once `VerificationTrajectoryStore` accumulates sufficient multi-corpus diversity ($\ge 10^4$ verified trajectories across disjoint works), `packages/episteme-worldmodel/` can evaluate LeCun's Joint-Embedding Predictive Architecture (2022, §4.2–4.5):

1. **Dual Inductive Encoders:**
   $$s_x = \text{Enc}_\theta(G_{\text{local}}) \in \mathbb{R}^d, \qquad s_y = \text{Enc}_\psi(\Delta_{\text{prop}}) \in \mathbb{R}^d$$
   initialized from Episteme's frozen `EmbeddingModel` with heterogeneous edge-conditioned message passing (`SUPPORTS`, `ATTACKS`, `UNDERCUTS`, `SPECIALIZES`) and optional hypercomplex quaternion predictor head ($\mathbb{H}^{d/4}$).
2. **Latent-Variable Predictor (Enthymeme Retrieval):**
   $$F_w(G_{\text{local}}, \Delta_{\text{prop}}) = \min_{z \in \mathcal{Z}} \Bigl( D\bigl(s_y, \text{Pred}_\phi(s_x, z)\bigr) + \lambda \, R(z) \Bigr)$$
   - *Indexing prerequisite for Capability 2:* To retrieve suppressed premises via predicted latent $\tilde{\mathbf{s}}_z$, index **ADU / sentence-level embeddings** rather than 300–500 token `L1Chunk` paragraph averages, and benchmark Recall@5 against standard LLM query generation (`LLMTheoryGuidedPremiseRecoverer`).
3. **Hybrid VICReg + Importance-Weighted Margin Hinge:**
   Combine VICReg variance/covariance regularization (only at adequate batch sizes) with importance-weighted margin hinge loss over certified Mode-2 hard negatives (`refuted` / non-sequiturs) using `propensity_score` from `VerificationTrajectoryRecord` to correct off-policy selection bias.

---

## 5. Annotated Research Guide & Primary Literature

| Paper / Source | Core Concepts for Episteme | Specific Mechanisms to Inspect |
| :--- | :--- | :--- |
| **LeCun (2022)**, *A Path Towards Autonomous Machine Intelligence* (v0.9.2) | Cognitive architecture (Configurator, STM, World Model, Critic); LVEBM, JEPA, amortized inference. | **§3.1.2–3.1.4** (Mode-2 $\to$ Mode-1 skill compilation), **§4.2–4.5** (LVEBM collapse, VICReg). |
| **Bardes, Ponce, & LeCun (ICLR 2022)**, *VICReg* (`arXiv:2105.04906`) | Non-contrastive collapse prevention via variance/covariance regularization. | Minimum batch-size sensitivity and expander MLP design for heterogeneous graph embeddings. |
| **Skenderi et al. (2023)**, *Graph-JEPA* (`arXiv:2309.16014`) | Adapting JEPA masked-block prediction to subgraphs + hyperbolic coordinates. | Subgraph partitioning & hyperbolic targets for Sneed/Balzer Poset Theory-Trees. |
| **Galkin et al. (ICLR 2024)**, *ULTRA* (`arXiv:2310.04562`) | Fully inductive zero-shot KG reasoning across unseen entities and relations. | Relation-interaction graphs when Episteme extracts new domain predicates or splits `EntityConception`s. |
| **Rampášek et al. (NeurIPS 2022)**, *GraphGPS* (`arXiv:2205.12454`) | Local MPNN + global Transformer attention + structural positional encodings. | Directed positional encodings distinguishing root axioms $T_0$ from leaves. |
| **Nayyeri et al. (2022)** & **Wang et al. (ACL 2022)** (*SimKGC*, `arXiv:2203.06478`) | 4D Hypercomplex Quaternion KG-Text fusion ($\mathbb{H}^d$) and Siamese text-graph alignment. | Relational predictor head design; see [Future Goals §1.1 & §1.3](../../docs/research/future_research_goals.md). |

### Recommended Benchmarks (Must Beat Baselines Before Promotion)
1. **Inductive Zero-Shot Document Split:** Hold out 20% of works completely (disjoint entity/claim vocabulary) to verify generalization over unseen nodes.
2. **Negation & Antinomy Sensitivity Probe:** Verify incompatibility risk rises sharply for $\neg\phi$ when $\Gamma \vdash \phi$ (fixing cosine similarity's negation blindness, cf. [ISSUE-089](../11-epistemetrics-formal-concept/epistemic_coherence/ISSUE-089-CONSISTENCY.md)).
3. **Latent Enthymeme Retrieval vs. LLM Query Baseline:** Compare ADU-indexed $\tilde{\mathbf{s}}_z$ Recall@5 against `LLMTheoryGuidedPremiseRecoverer` before adopting JEPA retrieval.

---

## 6. Acceptance Criteria

- [ ] Scaffold `packages/episteme-worldmodel/` depending solely on `episteme-contracts` (zero Lean/Pantograph dependencies), kept **out of mandatory root `pyproject.toml` dependencies**, with heavy PyTorch/PyG training wheels isolated in `[project.optional-dependencies] train`.
- [ ] Implement exact millisecond `D-QBAF` counterfactual sensitivity rollout endpoint/service using `epistemetrics` for `episteme-studio`.
- [ ] Implement Tier-1 supervised 4-class inductive triage evaluator calibrated via `ConformalCalibrator` emitting sidecar `ArtifactKind.VERIFICATION_VERDICT` / `EpistemicVerificationMetadata` with low incompatibility risk $E_{\text{WM}}$ for both `entailed` and `consistent_independent`.
- [ ] Gate Tier-2 Graph-JEPA experiments behind trajectory scale ($\ge 10^4$ episodes) and zero-shot AUROC improvement over Tier-1 baselines.
