# Formal Graph Schema (TheoryNet)

This document establishes the unified formal mathematical architecture of the **Theory Graph (TheoryNet)** in **Grund
Episteme**. It synthesizes epistemological theory, structuralist philosophy of science, abstract argumentation, and
graph-theoretic models into a single, mathematically rigorous framework designed to represent, extract, and evaluate
contested scientific literature.

---

## Mathematical Foundations & Graph Representation

The Theory Graph is formally defined as a labeled, directed multigraph:

$$G = (V, E, \lambda_v, \lambda_e)
$$

Where:

- $V$ is the finite set of vertices (entities, concepts, premises, and claims).
- $E \subseteq V \times V$ is the finite set of directed edges (semantic relationships, support, or attack vectors).
- $\lambda_v: V \to T_v$ assigns vertex types from an ontology type hierarchy $T_v$.
- $\lambda_e: E \to T_e$ assigns edge types from a relationship hierarchy $T_e$.

### Isomorphism to the Logical TheoryNet ($TF$)

The logical framework of the scientific theory—the **TheoryNet**—is defined as a relational tuple:

$$ TF = (At, R)
$$

where $At$ denotes the set of argumentative atoms and $R$ denotes the set of argumentative relations. To unify
computational graph storage (in Neo4j) with model-theoretic argumentation, we enforce a strict **isomorphism**:

- The vertex set $V$ maps directly to the set of argumentation atoms $At$ ($V \cong At$).
- The edge set $E$ maps directly to the argumentative relations $R$ ($E \cong R$).

### Epistemic Partitioning ($\Delta = (B, A)$)

Scientific theories are not flat assertions of fact; they fundamentally differentiate between empirical observations and
abstract theoretical hypotheses. We formally partition the vertex set $V$ via the underlying knowledge
base $\Delta = (B, A)$:

* **$B$ (Empirical Observation Base / *Beobachtungssätze*):** The foundation of verifiable, minimally contested
  empirical data points, localized existential assertions, and raw evidentiary units.
* **$A$ (Theoretical Antecedents / Hypotheses):** Abstract theoretical statements, core axioms, and hypotheses accepted
  as tenable only under specific inferential conditions.

Consequently, the global vertex set satisfies:

$$ V = B \cup A \quad \text{where} \quad B \cap A = \emptyset $$

---

## Layered Architecture Model (L1, L2, L3)

To maintain epistemic purity and prevent semantic drift across processing steps, the theory graph is stratified into
three distinct structural layers:

```mermaid
flowchart TD
    subgraph L3 ["Layer 3: Abstract Argumentation / Theory Core (L3)"]
        direction TB
        QBAF["Quantitative Bipolar Argumentation Framework (QBAF)<br/>Λ = ⟨A, R_att, R_sup, τ, ϕ⟩"]
        ATOMS["TheoryAtoms (At) & TheoryRelations (R)"]
        QBAF --- ATOMS
    end

    subgraph L2 ["Layer 2: Deterministic Ontology / Knowledge Base (L2)"]
        direction TB
        ENT["Typed Entities e ∈ V_L2 (Concepts, Persons, Works)"]
        TRIPLES["Factual Relational Triples r ∈ E_L2"]
        ENT --- TRIPLES
    end

    subgraph L1 ["Layer 1: Empirical Manifold / Source Grounding (L1)"]
        direction TB
        CHUNKS["Document Chunks C = (t_1, ..., t_N)"]
        PROV["Textual Envelopes T_n & Provenance Maps"]
        CHUNKS --- PROV
    end

    L2 -->|" MENTIONED_IN / EXTRACTED_FROM "| L1
    L3 -->|" Zuordnungsgesetze Z(a,b) / Epistemic Grounding "| L2
    L3 -.->|" Traversals terminating in B "| L1
```

### Layer 1: Empirical Manifold / Source Grounding ($L1$)

Represents raw document chunks, unstructured token sequences $S \in \Sigma^*$, and exact provenance offsets:

$$ L1 = (C, \lambda_c, \pi)
$$

Where:

- $C = \{c_1, c_2, \dots, c_m\}$ is the set of document chunks.
- $\lambda_c: C \to \text{DocumentMetadata}$ assigns structural coordinates (e.g., Table of Contents section, chapter,
  author, page number).
- $\pi: C \to \text{Text}$ provides the verbatim character substring sequence $(t_1, t_2, \dots, t_N)$.

### Layer 2: Deterministic Ontology / Knowledge Base ($L2$)

Captures entity-centric factual relationships extracted directly from the literature:

$$ L2 = (\mathcal{V}_{\text{L2}}, \mathcal{E}_{\text{L2}}, \gamma, \delta)
$$

Where:

- $\mathcal{V}_{\text{L2}}$ is the set of typed entity nodes ($e \in \mathcal{V}_{\text{L2}}$), such as *Concept*, *Person*, *Theory*, or
  *Work*.
- $\mathcal{E}_{\text{L2}} \subseteq \mathcal{V}_{\text{L2}} \times \mathcal{V}_{\text{L2}}$ is the set of directed relationship edges ($r \in \mathcal{E}_{\text{L2}}$), such as
  `INFLUENCED`, `DEFINES`, or `ASSOCIATED_WITH`.
- $\gamma: \mathcal{V}_{\text{L2}} \to [0, 1]$ assigns extraction confidence scores.
- $\delta: \mathcal{E}_{\text{L2}} \to [0, 1] \times \mathcal{P} (L1)$ assigns relationship certainty paired with explicit evidentiary text
  snippets from $L1$.

### Layer 3: Abstract Argumentation Framework ($L3$)

Encodes argumentative, defeasible, and theoretical dependencies as a Quantitative Bipolar Argumentation Framework (QBAF):

$$ L3 \equiv \Lambda = \langle A, \mathcal{R}_{att}, \mathcal{R}_{sup}, \tau, \phi \rangle
$$

Where:

- $A$ is the set of argument components / theoretical hypotheses ($a \in \mathcal{V}_{\text{L3}}$), formally categorized as *Claims* or
  *Premises*.
- $\mathcal{R}_{att} \subseteq A \times A$ is the class of attacking/undermining relations.
- $\mathcal{R}_{sup} \subseteq A \times A$ is the class of supporting/warranting relations.
- $\tau: A \to [0, 1]$ is the prior plausibility base score.
- $\phi: \mathcal{R}_{att} \cup \mathcal{R}_{sup} \to [0, 1]$ assigns continuous structural relationship weights.
- Continuous gradual semantics $\rho: A \to [0, 1]$ subsequently updates and evaluates node acceptability.

---

## Argumentation Framework & Gradual Semantics

Scientific reasoning is rarely binary; theoretical statements carry varying degrees of warrant and face conditional
objections. We model the logical interaction over theoretical nodes $A$ as a **Quantitative Bipolar Argumentation
Framework (QBAF)**.

### Super-Role Inclusion (DL-LiteR)

Drawing upon Description Logics (specifically DL-LiteR), argumentative interactions are not restricted to monolithic
primitives. Instead, "attack" and "support" are formalized as broad **super-role classes**, denoted
as $\mathcal{R}_{att}$ and $\mathcal{R}_{sup}$:

Any fine-grained relational predicate identified in the scientific text
(e.g., $r_k \in \{\text{REFUTES}, \text{CRITICIZES}, \text{UNDERMINES}\}$) is treated as a role inclusion inheriting the
formal semantics of its parent super-class:

$$ r_k \sqsubseteq \mathcal{R} _{att} \quad \text{or} \quad r_k \sqsubseteq \mathcal{R}_{sup} $$

The complete argumentation space is defined as the tuple:

$$ \Lambda = \langle A, \mathcal{R} _{att}, \mathcal{R}_{sup}, \tau, \phi \rangle $$

Where:

- $A$ is the set of theoretical antecedents.
- $\mathcal{R}_{att} \subseteq A \times A$ is the class of all attacking/undermining relations.
- $\mathcal{R}_{sup} \subseteq A \times A$ is the class of all supporting/warranting relations.
- $\tau: A \to [0, 1]$ is the prior plausibility function (vertex labeling $\lambda_v$).
- $\phi: \mathcal{R}_{att} \cup \mathcal{R}_{sup} \to [0, 1]$ is the continuous edge weight function (edge
  labeling $\lambda_e$).

### Continuous State Computation & Gradual Semantics

The ultimate acceptability of any scientific premise within the Theory Graph is calculated via an update
function $\rho: A \to [0, 1]$ that combines its prior plausibility $\tau (a_i)$ with the aggregated strengths of
incoming relations.

#### Decoupled Quantitative Bipolar Argumentation Framework (D-QBAF)

A foundational vulnerability in earlier theory graph implementations was conflating the model's **epistemic extraction confidence** with the author's **propositional modal strength**:
1. **The Pseudo-Decoupling Contradiction ($w = M \times P$):** Multiplying propositional modal strength $M(\phi)$ by perception classifier probability $P(\text{stance})$ into a single scalar edge weight algebraically coupled orthogonal dimensions. A deductive proof ($M = 1.0$) extracted with moderate confidence ($P = 0.5$) received $w = 0.5$, identical to a tentative conjecture ($M = 0.5$) extracted with certainty ($P = 1.0$).
2. **Double-Penalization of Premise Uncertainty:** Placing modal strength on the edge penalized conjectural premises twice: once when computing the premise's own standing ($s_j \le 0.3$), and a second time by scaling the outgoing edge $w = 0.3 \times P$, yielding an artificial compounding penalty ($0.3 \times 0.3 = 0.09$).

To resolve this, the dialectical theory graph layer is formalized as a **Decoupled Quantitative Bipolar Argumentation Framework (D-QBAF)**:

$$\mathcal{Q} = \langle \mathcal{A}, \mathcal{R}_{att}, \mathcal{R}_{sup}, \tau_0, \mathcal{I}, \mathcal{P}, \mathcal{C} \rangle$$

where:
1. $\mathcal{A} = \{a_1, a_2, \dots, a_n\}$ is a finite set of theoretical argument atoms, formally partitioned into empirical observations $B$ and theoretical hypotheses $A$ such that $\mathcal{A} = B \cup A$ and $B \cap A = \emptyset$ (Schurz, 2014).
2. $\mathcal{R}_{att} \subseteq \mathcal{A} \times \mathcal{A}$ is a binary relation representing dialectical attack, rebuttal, or undercutting.
3. $\mathcal{R}_{sup} \subseteq \mathcal{A} \times \mathcal{A}$ is a binary relation representing dialectical warrant, verification, or inductive support, with $\mathcal{R}_{att} \cap \mathcal{R}_{sup} = \emptyset$.
4. $\tau_0: \mathcal{A} \to [0, 1]$ is the **intrinsic propositional base score function**, mapping each claim $a \in \mathcal{A}$ to the authorial modal certainty asserted in the text:
   $$\tau_0(a) \equiv M(\phi_a)$$
5. $\mathcal{I}: \mathcal{R} \to [0, 1]$ is the **inferential warrant force function**, quantifying the conditional validity of the inferential link under Toulminian argument schemes (deductive entailment vs. empirical corroboration vs. defeasible analogy).
6. $\mathcal{P}: \mathcal{R} \to [0, 1]$ is the **stance class probability function**, mapping an edge $r \in \mathcal{R}$ to the perception engine's softmax probability $P(\text{stance} \mid \text{text})$.
7. $\mathcal{C}: \mathcal{R} \to [0, 1]$ is the **perception calibration confidence score**, representing the expected empirical precision under calibrated temperature buckets (e.g., Conformal Prediction / Jev).

```
                      ONTOLOGICAL STRATIFICATION OF UNCERTAINTY

  Epistemic Layer           Entity / Target              Formal Metric       Literature Grounding
  ───────────────────────────────────────────────────────────────────────────────────────────────
  Claim / Proposition       TheoryAtom (Node a)          M(φ_a) ∈ [0, 1]     Toulmin (1958) Modal Qualifier
                                                         τ_0(a) ∈ [0, 1]     Schurz (2014) Epistemic Status
  
  Inferential Warrant       TheoryRelation (Edge j -> i) I_(j->i) ∈ [0, 1]   Toulmin (1958) Warrant & Backing
  
  Perception Extraction     Classifier Output (j -> i)   P(stance) ∈ [0, 1]  Prakken (2020) Constellations
                                                         C ∈ [0, 1]          Conformal Prediction / Jev
```

##### Admissibility Gating Modes

The effective edge weight $W_{ji} = \mathcal{W}(a_j \xrightarrow{r} a_i)$ is modulated via an admissibility filter $\mathcal{F}: \mathcal{R} \to [0, 1]$:

$$W_{ji} = \mathcal{I}(a_j \xrightarrow{r} a_i) \cdot \mathcal{F}(a_j \xrightarrow{r} a_i)$$

1. **Mode 1: Hard Bivariate Admissibility Filter (Normative Pipeline Standard)**  
   For database subgraph projection and normative dialectical evaluation, admissibility is strictly binary:
   $$\mathcal{F}_{\text{hard}}(r) = \begin{cases} 1 & \text{if } \mathcal{P}(r) \ge \tau_P \quad \land \quad \mathcal{C}(r) \ge \tau_C \\ 0 & \text{otherwise} \end{cases}$$
   Inferential warrant force $\mathcal{I}$ is never diluted by perception probability. Unadmitted edges are pruned at database level via Cypher filtering.

2. **Mode 2: Continuous Sigmoidal Relaxation (Numerical Optimization Regularizer)**  
   To prevent discontinuous Filippov vector fields and bifurcation catastrophes during continuous optimization, `epistemetrics` provides an opt-in smooth relaxation ($k_1 = k_2 = 20$):
   $$\mathcal{F}_{\text{soft}}(r) = \left( \frac{1}{1 + e^{-k_1 (\mathcal{P}(r) - \tau_P)}} \right) \cdot \left( \frac{1}{1 + e^{-k_2 (\mathcal{C}(r) - \tau_C)}} \right)$$

##### Continuous Quadratic Energy Dynamical System

Let $\mathbf{s}(t) = (s_1(t), \dots, s_n(t))^T \in [0, 1]^n$ denote the justification degree vector. For any claim $a_i \in \mathcal{A}$, the net continuous energy $E_i(t) \in \mathbb{R}$ is:

$$E_i(t) = \sum_{j:(a_j, a_i) \in \mathcal{R}_{sup}} W_{ji} \cdot s_j(t) - \sum_{k:(a_k, a_i) \in \mathcal{R}_{att}} W_{ki} \cdot s_k(t)$$

With rational impact function $h(x) = \frac{\max\{x, 0\}^2}{1 + \max\{x, 0\}^2}$, justification degrees evolve via the continuous autonomous ODE:

$$\frac{ds_i}{dt} = w(i) - s_i(t) + (1 - w(i)) \cdot h(E_i(t)) - w(i) \cdot h(-E_i(t))$$

initialized at $s_i(0) = w(i) = \tau_0(a_i)$.

##### Theoretical Guarantees and Propositions

1. **Proposition 1 (Heaviside Asymptotics):** $\lim_{k \to \infty} \sigma(k(x - \tau)) = H(x - \tau)$ almost everywhere.
2. **Proposition 2 (Positive Forward Invariance of $[0, 1]^n$):** By Nagumo's subtangential condition, $\left. \frac{ds_i}{dt} \right|_{s_i=1} \le 0$ and $\left. \frac{ds_i}{dt} \right|_{s_i=0} \ge 0$, guaranteeing that all trajectories initialized in $[0, 1]^n$ remain strictly bounded in $[0, 1]^n$ for all $t \ge 0$.  
   *Note on Convergence:* Forward invariance guarantees boundedness in the state space, not the non-existence of limit cycles on arbitrary cyclic networks. Convergence is analytically proven for DAGs (Proposition 5) and support-only graphs (Hirsch's Monotone Flow Theorem), while mixed cyclic networks converge empirically.
3. **Proposition 3 (Balance & Epistemic Duality):** If incoming support exactly cancels attack ($E_i(t) = 0$), $h(E_i) = h(-E_i) = 0$, so $s_i(t) = w(i)$ identically for all $t \ge 0$.
4. **Proposition 4 (Jacobian Spectral Radius & Correction to Potyka 2018):** By Gershgorin's Circle Theorem, the Jacobian spectral radius satisfies $\rho(J) \le 1 + 0.65 \cdot \text{indegree}(i) \cdot \bar{W}$. Potyka (2018) claimed fixed-step RK4 ($\delta = 0.01$) is unconditionally safe because $|\dot{s}_i| \le 1$. Proposition 4 refutes this: high-degree citation hubs ($\text{indegree} \gg 50$) cause $\delta \cdot \rho(J) > 2.78$, producing explosive numerical divergence. Adaptive-step solvers (`solve_ivp` RK45 / Radau fallback) with root-finding stationary termination events are mathematically mandatory.
5. **Proposition 5 (Exact Closed-Form Solution on DAGs):** On any directed acyclic graph, predecessors reach constant equilibrium $s_j^*$. The ODE yields exact stationary closed form:
   $$s_i^* = w(i) + (1 - w(i)) \cdot h(E_i^*) - w(i) \cdot h(-E_i^*)$$
   evaluating in $O(|\mathcal{A}| + |\mathcal{R}|)$ time along a topological sort without numerical ODE integration.

##### Orthogonal Epistemic Dimensions (Keynes-Gärdenfors Formulation)

To distinguish heavily contested scientific controversies from unevidenced claims having identical justification $\tau^* = 0.5$:
- **Gross Epistemic Weight ($E_{\text{total}} \ge 0$):** Total evidentiary volume:
  $$E_{\text{total}}(a_i) = \sum_{j:(a_j, a_i) \in \mathcal{R}_{sup}} W_{ji} \cdot \tau^*(a_j) + \sum_{k:(a_k, a_i) \in \mathcal{R}_{att}} W_{ki} \cdot \tau^*(a_k)$$
- **Epistemic Volatility Index ($\mathcal{V}(a_i) \in [0, 1]$):** Evidentiary controversy:
  $$\mathcal{V}(a_i) = \left( \frac{E_{\text{total}}(a_i)}{1 + E_{\text{total}}(a_i)} \right) \cdot \left( 1 - 2 \cdot |\tau^*(a_i) - 0.5| \right)$$

### Dung Abstract Argumentation Mapping

In discrete evaluation contexts, the graph can be reduced to Dung's classical abstract argumentation framework:

- **Arguments**: $A \subseteq \mathcal{V}_{\text{L3}}$.
- **Attack Relations**: $\leadsto \; \subseteq A \times A$, where $u \leadsto v \iff (u, v) \in \mathcal{R}_{att}$.
- **Extensions**: Evaluated under standard grounded, preferred, and stable extension semantics.

---

## Zuordnungsgesetze (Mapping Laws) & Epistemic Grounding

For an abstract theory core ($A$) to possess empirical creativity rather than remaining purely speculative, it must
anchor to the empirical base ($B$). This anchoring is mediated by formal **Mapping Laws** (*Zuordnungsgesetze*, Schurz,
2014):

$$ Z: A \times B \to [0, 1]
$$

Between an empirical observation $b \in B$ and a theoretical antecedent $a \in A$, the mapping law is governed by two
complementary functions:

1. **Correlational Mapping ($Z_1$):**
$$ Z_1: A \times B \to \mathcal{P} $$ Models the probabilistic correlation between theoretical constructs and
   observable indicators, mapped to the continuous $[0, 1]$ interval of the QBAF.
2. **Structural Isomorphism ($Z_2$):**
$$ Z_2: A \times B \to \sigma (\kappa (a), \kappa (b))
$$
Measures the structural overlap $\sigma$ between the theoretical model structure $\kappa (a)$ and the empirical
   domain $\kappa (b)$.

### Epistemic Justification Paths ($J (at)$)

Rather than storing justifications as static, ungrounded node attributes, the set of epistemic justifications $J (at)$
for any atom $at \in At$ is **dynamically inferred** via directed graph traversal through supportive and mapping edges
terminating in $B$:

$$ J (at) = \{ p = (a_0, e_1, a_1, \dots, e_k, b) \mid a_0 = at, \; b \in B, \; e_i \in \mathcal{R}_{sup} \cup Z \} $$

This ensures that logical inferences remain provably grounded in empirical textual evidence.

---

## Structuralist Model-Theoretic Foundations

Complementing abstract argumentation, the pipeline integrates the **Structuralist Theory of Science** (Sneed, 1971;
Stegmüller, 1976; Balzer et al., 1987). Theories are model-theoretic entities rather than syntactic statement lists.

### The Model-Theoretic Triad: $M_p$, $M$, and $M_{pp}$

A theory-element is defined as a pair $T = \langle K, I \rangle$, where $K$ is the formal theory core and $I$ is the
domain of intended applications. The formal core relies on three nested classes of set-theoretic structures:

1. **Potential Models ($M_p$):** Defines the mathematical vocabulary and conceptual framework (e.g., coordinate frames,
   mass functions, force vectors), regardless of whether empirical laws hold.
2. **Actual Models ($M \subseteq M_p$):** The subset of potential models satisfying the substantive natural laws or
   mathematical axioms of the theory.
3. **Partial Potential Models ($M_{pp}$):** The empirical substructure obtained by stripping away all $T$-theoretical
   functions, leaving only non-theoretical, directly observable terms.

### Uniform Space $(M_p, \mathcal{U})$ & Admissible Blurs ($\mathcal{A}$)

Real-world scientific applications inevitably involve measurement noise and observational tolerances. Rather than
requiring absolute mathematical exactness, closeness between empirical observations and theoretical models is formalized
via a **Uniform Space** $(M_p, \mathcal{U})$:

- **Uniformity ($\mathcal{U}$):** A family of entourage relations $u \subseteq M_p \times M_p$ satisfying diagonal
  containment ($\Delta (M_p) \subseteq u$), filter intersection ($u_1 \cap u_2 \in \mathcal{U}$), and triangular
  composition ($v \circ v \subseteq u$).
- **Admissible Blurs ($\mathcal{A} \subseteq \mathcal{U}$):** A pragmatically restricted sub-collection of entourages
  bounded by an upper tolerance limit:
$$ \text{Bound} (\mathcal{A})
$$
If observational discrepancy exceeds $\text{Bound} (\mathcal{A})$, the theory is falsified; conversely,
  if $\mathcal{A}$ were allowed to be arbitrarily large, the theory would become empirically vacuous.

### Tenability and Adequacy

These model-theoretic structures define two critical validity conditions:

* **Tenability (*Haltbarkeit*):** The requirement that intended applications can be formulated in the non-theoretical
  empirical vocabulary:
$$ I \subseteq M_{pp} $$ If an intended application cannot be expressed within $M_{pp}$, the theory is conceptually
  untenable for that domain.
* **Approximative Empirical Adequacy (*Adäquatheit*):** The condition that empirical observations $I$ can be enriched
  with theoretical functions such that the resulting model lies within an admissible blur $u \in \mathcal{A}$ of an
  actual model $M$:
$$ \exists X \in M \quad \text{such that} \quad (I, X) \in u, \quad u \in \mathcal{A} $$

---

## Temporal Evolution & Uncertainty

Scientific knowledge is non-static; theories evolve, revise hypotheses, and encounter anomalies.

### Temporal Graph Evolution

The graph evolves over chronological time $t$:

$$ G (t) = (V (t), E (t), \lambda_v (t), \lambda_e (t))
$$

* **Description Versioning:** When an entity or premise matures into a more specialized conceptualization, earlier
  descriptions are not overwritten. Instead, the graph retains an immutable historical semantic trace. This ensures that
  early, less sophisticated terminology remains matchable in vector space during cross-document alignment.
* **Dynamic Refinement:** Relations strengthen, weaken, or undergo modal retraction when confronted with empirical
  counterexamples.

### Probabilistic Semantics

To capture extraction and inferential uncertainty, each element carries belief-theoretic scores:

- **Belief Score**: $\beta \in [0, 1]$
- **Disbelief Score**: $\delta \in [0, 1]$
- **Epistemic Uncertainty**: $u = 1 - \beta - \delta \quad (\beta + \delta \le 1)$

For composite argument structures:

- **Conjunction**: $c (A \land B) = \min (c (A), c (B))$
- **Disjunction**: $c (A \lor B) = \max (c (A), c (B))$
- **Implication**: $c (A \to B)$ weighted by evidentiary support and conditional transfer confidence.

---

## Computational Tractability & Search Heuristics

Evaluating the global structural coherence of a scientific theory requires determining maximal $B$-consistent
subsets $\Sigma \subseteq A$, such that $\Sigma \cup B$ is free of logical contradictions, while any
superset $\Sigma' \cup B$ introduces an inconsistency.

Because computing admissible extensions in abstract argumentation and verifying constraint satisfaction over posets is
**NP-hard**, the pipeline avoids exhaustive combinatorial search. Instead, it employs:

1. **Dense Vector Retrieval (Bi-Encoder MIPS):** Constrains cross-chunk candidate generation to top-$K$ semantic
   neighbors.
2. **Cross-Encoder Attention Filtering:** Reranks relation candidates using fine-grained multi-head cross-attention.
3. **Machine-Learning Guided Solvers:** structural predictors guide search-based solvers to approximate stable
   extensions in polynomial time.

---

## Quality & Validation Metrics

The formalized theory graph is evaluated across multiple structural and empirical quality dimensions:

| Metric                            | Target Layer          | Formal Definition                                                                 | Purpose                                                                       |
|:----------------------------------|:----------------------|:----------------------------------------------------------------------------------|:------------------------------------------------------------------------------|
| **Entity Precision & Recall**     | Layer 2               | $\frac{                                                                           | E_{\text{correct}}                                                            |}{|E_{\text{extracted}}|}, \quad \frac{|E_{\text{correct}}|}{|E_{\text{gold}}|}$ | Evaluates extraction faithfulness against gold-standard literature. |
| **Evidence Precision & Coverage** | Layer 1 $\to$ Layer 2 | Ratio of accurately localized verbatim text spans grounding entities and triples  | Prevents hallucinated relationships and guarantees source auditability.       |
| **Semantic Soft Matching**        | Layer 2 / Layer 3     | $\cos(E_{\text{ctx}}(a_{\text{pred}}), E_{\text{ctx}}(a_{\text{gold}})) \ge \tau$ | Accommodates paraphrasing and terminological variation in philosophy.         |
| **Empirical Content Ratio**       | Layer 3 $\to$ Layer 1 | Ratio of theoretical antecedents grounded via $Z(a, b)$ into $B$                  | Penalizes ungrounded metaphysical baggage.                                    |
| **Structural Coherence**          | Layer 3               | Parallel constraint satisfaction score ($H(t)$ via ECHO)                          | Assesses the absence of unmitigated circularities or internal contradictions. |

---

## Related Documentation

- **Philosophy of Science**: [Epistemology & Wissenschaftstheorie](epistemology.md)
- **Topologies & Community Structure**: [Theory-Nets, Posets & Topologies](theory_nets_and_topologies.md)
- **Dense Alignment & Maturation**: [Dense Alignment & Grounding](dense_alignment.md)
- **Evaluation Taxonomy**: [Theory Metrics Subsystem](theory/metrics/index.md)
- **Software Implementation**: [Pipeline Architecture](../architecture/pipeline_architecture.md)
- **Contracts & Schemas**: [Schema Reference](../reference/schema.md)
  and [Phase Contracts](../reference/phase_contracts.md)
