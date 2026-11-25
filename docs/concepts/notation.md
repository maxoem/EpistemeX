# Canonical Notation & Symbol Reference

This reference establishes the notation across the four core conceptual documents of **Episteme**:

- [From Factual Knowledge Graphs to Epistemic Theory Graphs](kg_vs_tg.md)
- [Epistemology & Philosophy of Science](epistemology.md)
- [Formal Graph Schema & Argumentation Semantics](formal_graph_model.md)
- [Theory-Nets, Posets & Topologies](theory_nets_and_topologies.md)

Every mathematical symbol below has a **unique meaning** across all layers. Where standard literature traditions collide (for instance, Balzer, Moulines, & Sneed's $\mathcal{A}$ for admissible blurs vs. argumentation theory's $\mathcal{A}$ for argument sets, or $E$ for graph edges vs. empirical content vs. node energy), distinct symbols are assigned here and mapped to source conventions.

---

## 1. Multi-Layer Epistemic Theory Graph ($G$)

| Symbol | Meaning | Type / Domain |
|:---|:---|:---|
| $G$ | Stratified Epistemic Theory Graph | $G = (V, E, \mathrm{src}, \mathrm{tgt}, \lambda_v, \lambda_e)$ |
| $V$ | Global finite vertex set (disjoint union of layers) | $V = V_1 \uplus V_2 \uplus V_3 \uplus V_4$ |
| $V_1, V_2, V_3, V_4$ | Layer vertex sets (L1 Source, L2 Entity, L3 Dialectical, L4 Structuralist) | Pairwise disjoint finite sets |
| $E$ | Global finite multigraph edge token set | $E = E_{\text{intra}} \uplus E_{\text{inter}}$ |
| $\mathrm{src}, \mathrm{tgt}$ | Multigraph incidence functions | $\mathrm{src}, \mathrm{tgt}: E \to V$ |
| $\lambda_v, \lambda_e$ | Ontological type labellings | $\lambda_v: V \to \mathcal{T}_v$, $\lambda_e: E \to \mathcal{T}_e$ |
| $\mathcal{T}_v, \mathcal{T}_e$ | Vertex and edge ontological type hierarchies | Finite posets of types |
| $G(t)$ | Diachronic snapshot of $G$ at chronological epoch $t$ | Time-indexed multigraph |
| $\operatorname{Pot}(X)$ | Power set of a set $X$ (BMS convention; avoids collision with $\mathcal{P}$) | $\{Y : Y \subseteq X\}$ |

---

## 2. Layer 1 ($L_1$, Source & Provenance) and Layer 2 ($L_2$, Entity ABox)

| Symbol | Meaning | Type / Domain |
|:---|:---|:---|
| $C$ | Finite set of document chunks ($V_1 = C$) | $\{c_1, \dots, c_m\}$ |
| $\lambda_c$ | Structural document metadata map (work, chapter, section, page) | $\lambda_c: C \to \mathrm{DocMeta}$ |
| $\pi$ | Verbatim character-sequence map over alphabet $\Sigma$ | $\pi: C \to \Sigma^*$ |
| $\mathrm{Span}$ | Set of verbatim character spans inside chunks | $\{(c, i, j) \in C \times \mathbb{N}^2 : 0 \le i < j \le \lvert \pi(c) \rvert\}$ |
| $E_2$ | Layer 2 directed multigraph edge tokens | $\mathrm{src}, \mathrm{tgt}: E_2 \to V_2$ |
| $\gamma_v, \gamma_e$ | Layer 2 extraction confidences (Tier 1: perception) | $\gamma_v: V_2 \to [0,1]$, $\gamma_e: E_2 \to [0,1]$ |
| $\mathrm{prov}_2$ | Layer 2 exegetical provenance map (non-epistemic) | $\mathrm{prov}_2: V_2 \cup E_2 \to \operatorname{Pot}(\mathrm{Span})$ |
| $e_{\text{th}}$ | Canonical `Theory` entity node carrying the canonical theory identifier | $e_{\text{th}} \in V_2$ |
| $v_{\text{poly}}(e)$ | Spherical conception dispersion of canonical L2 referent $e$ | $v_{\text{poly}}(e) = 1 - \lVert \frac{1}{N}\sum_i \hat{\mathbf{e}}_i \rVert_2 \in [0, 1]$ |

---

## 3. Layer 3 ($L_3$, Dialectical Argument Graph $\mathcal{D}$ & D-QBAF $\mathcal{Q}$)

| Symbol | Meaning | Type / Domain |
|:---|:---|:---|
| $\mathcal{D}$ | Layer 3 Dialectical Argument Graph (bipartite inference hypergraph) | Induced subgraph on $V_3 = \mathcal{A} \uplus \mathcal{W}$ |
| $\mathcal{A}$ | Finite set of propositional argument atoms (ADUs) | $\mathcal{A} = B \uplus H$ |
| $B$ | Evidential base (pre-theoretical relative to $T$; domain-generalized) | $B \subseteq \mathcal{A}$ |
| $H$ | Theoretical hypotheses, principles, axioms, and mixed mapping laws | $H = \mathcal{A} \setminus B$ |
| $\mathcal{W}$ | Finite set of reified inference warrants (`:TheoryInference` nodes) | $\xi_k \in \mathcal{W}$ |
| $\mathrm{Prem}(\xi_k), \mathrm{Conc}(\xi_k)$ | Conjunctive premise set and conclusion of warrant $\xi_k$ | $\mathrm{Prem}(\xi_k) \subseteq \mathcal{A}$ (non-empty), $\mathrm{Conc}(\xi_k) \in \mathcal{A}$ |
| $\mathrm{pol}(\xi_k)$ | Dialectical polarity of inference $\xi_k$ toward its conclusion | $\{+1, -1\}$ (support / attack) |
| $\mathcal{R}_{\text{sup}}, \mathcal{R}_{\text{att}}, \mathcal{R}_{\text{str}}, \mathcal{R}_{\text{fac}}$ | DL-Lite$_R$ top-level role classes (support, attack, structural, factual) | Pairwise disjoint edge-type super-classes |
| $\iota(a)$ | Intensional / speech-act mode of atom $a \in \mathcal{A}$ | $\{\text{asserted}, \text{attributed}, \text{suppositional}, \text{historical}\}$ |
| $\mathrm{agent}(a)$ | Attributing author, thinker, or school (when $\iota(a) = \text{attributed}$) | $V_2 \cup \mathrm{Agent} \cup \{\bot\}$ |
| $\mathrm{rd}(a)$ | Exegetical reading / interpretation index | $\mathrm{rd}(a) \in \mathcal{R}_{\text{int}}$ |
| $M_{\text{mod}}(\phi_a)$ | Authorial assertoric commitment / modal hedging strength (Tier 2) | $M_{\text{mod}}: \mathcal{A} \to [0, 1]$ |
| $\beta(a)$ | Configured base prior score of atom $a$ (normative or descriptive policy) | $\beta: \mathcal{A} \to [0, 1]$ |
| $\tilde{\beta}(a)$ | Effective tenability- and perspective-modulated base prior | $\tilde{\beta}(a) = \beta(a) \cdot TS_{\text{local}}(a) \in [0, 1]$ |
| $\mathcal{I}(r), \omega_0(\xi_k)$ | Intrinsic inferential warrant force of edge $r$ or warrant $\xi_k$ (Tier 2/3) | $[0, 1]$ |
| $\mathcal{P}(r), \mathcal{C}_{\text{cal}}(r)$ | Perception stance probability and calibrated empirical precision (Tier 1) | $[0, 1]$ |
| $\theta_P, \theta_C$ | Bivariate admissibility gating thresholds on $\mathcal{P}$ and $\mathcal{C}_{\text{cal}}$ | $[0, 1]$ |
| $\mathcal{F}_{\text{hard}}, \mathcal{F}_{\text{soft}}$ | Hard binary gate ($\in \{0, 1\}$) and smooth sigmoidal surrogate ($\in (0, 1)$) | $\mathcal{R}_{\text{arg}} \to [0, 1]$ |
| $g_k, W_{ji}$ | Effective gating factor $g_k = \mathcal{F}(\xi_k) \cdot TS_{\text{edge}}(\xi_k)$ and effective pairwise edge weight $W_{ji} = \mathcal{I}(r) \cdot \mathcal{F}(r) \cdot TS_{\text{edge}}(r)$ | $[0, 1]$ |
| $\Phi_{\text{conj}}(\mathrm{Prem}(\xi_k), t)$ | Conjunctive premise aggregation t-norm (`product` $\prod$ or `godel` $\min$) | $[0, 1]$ |
| $s_i(t), s_i^*$ | Dynamic and equilibrium D-QBAF acceptability of atom $a_i$ (Tier 3) | $[0, 1]$ |
| $s_{\mathcal{W}}(\xi_k, t), s_{\mathcal{W}}^*(\xi_k)$ | Dynamic and equilibrium warrant validity of reified warrant $\xi_k$ | $[0, 1]$ |
| $\eta_i(t), \eta_{\xi_k}(t)$ | Net continuous dialectical energy of atom $a_i$ or warrant $\xi_k$ | $\mathbb{R}$ |
| $h(x)$ | Potyka quadratic-energy impact function | $h(x) = \max\{x, 0\}^2 / (1 + \max\{x, 0\}^2)$ |
| $\operatorname{sig}(x), \Theta_H(x)$ | Logistic sigmoid $(1 + e^{-x})^{-1}$ and Heaviside step function | $\mathbb{R} \to (0, 1)$, $\mathbb{R} \to \{0, 1\}$ |
| $h_\Delta, \rho_{\text{spec}}(J)$ | Numerical ODE step size and Jacobian spectral radius | $\mathbb{R}_{>0}, \mathbb{R}_{\ge 0}$ |
| $S^+_i, S^-_i$ | Equilibrium aggregated support mass and attack mass incident to $a_i$ | $\mathbb{R}_{\ge 0}$ |
| $\mathrm{Wt}(a_i), \mathrm{Controv}(a_i), \mathcal{V}(a_i)$ | Gross weight of evidence, evidentiary controversy, and volatility index | $[0, 1)$ |

---

## 4. Epistemology, Logic & Theory Dynamics

| Symbol | Meaning | Type / Domain |
|:---|:---|:---|
| $L_E, L_T$ | Pre-theoretical ($T$-non-theoretical) and $T$-theoretical sub-languages | Formal sub-languages of $L$ |
| $\vdash, \models$ | Syntactic derivability and semantic entailment | Standard logical turnstiles |
| $\operatorname{Cn}(X)$ | Classical deductive Tarskian consequence closure of sentence set $X$ | $\{\varphi \in L : X \vdash \varphi\}$ |
| $E_{\text{emp}}(X)$ | Empirical content of sentence set $X$ | $\operatorname{Cn}(X) \cap L_E$ |
| $\mathrm{Ax}(T)$ | Natural (relevant, non-redundant) axiomatization of theory $T$ | Finite subset of $L$ |
| $\mathbf{HC}$ | Constant Lakatosian hard core of a research programme | Fixed set of axioms |
| $\Pi^{(j)}, T^{(j)}$ | Protective belt and full theory version at step $j$ | $T^{(j)} = \mathbf{HC} \cup \Pi^{(j)}$ |
| $\div$ | AGM belief contraction operator | Sentence set $\times$ sentence $\to$ sentence set |
| $\mathsf{Succ}, \mathsf{Succ}^{\text{nov}}, \mathsf{Succ}^{\text{acc}}$ | Empirical successes: total, corroborated novel predictions, accommodated explanations | $\mathsf{Succ} = \mathsf{Succ}^{\text{nov}} \uplus \mathsf{Succ}^{\text{acc}}$ |
| $\mathsf{Fail}, \mathsf{Fail}_a, \mathsf{Fail}_b$ | Empirical failures: total, direct refutations (Type a), ad-hoc₁ immunizations (Type b) | $\mathsf{Fail} = \mathsf{Fail}_a \uplus \mathsf{Fail}_b$ |
| $\succ_{\text{emp}}$ | Comparative empirical-success strict partial order | Strict partial order on theories |
| $D_{\text{deg}}(T^{(j)}), R_{\text{fail}}(T^{(j)})$ | Bounded Lakatosian degeneration proxy and empirical failure rate | $[0, 1]$ |
| $\mathcal{B}_{\text{hist}}(t)$ | Historical evidential horizon available at epoch $t$ | Time-indexed evidential base |
| $a_i^{\text{echo}}(t), w_{ij}^{\text{echo}}, \mathcal{H}_{\text{echo}}(t)$ | ECHO activations ($\in [-1, 1]$), symmetric weights ($w_{ij}^{\text{echo}} = w_{ji}^{\text{echo}}$), and global harmony | Alternative coherence lens |

---

## 5. Layer 4 ($L_4$, Structuralist Theory-Nets $\mathcal{N}$) & Network Topology

| Symbol | Meaning | Type / Domain |
|:---|:---|:---|
| $\mathcal{N} = \langle N, \sigma \rangle$ | Structuralist Theory-Net (BMS convention): finite set of theory-elements $N$ with specialization partial order $\sigma$ | Finite poset ($V_4 = N$) |
| $T = \langle K, I \rangle$ | Structuralist theory-element: formal core $K$ and intended applications $I$ | $T \in N$ |
| $K = \langle M_p, M, M_{pp}, GC, GL \rangle$ | BMS formal theory core: potential models, actual models ($M \subseteq M_p$), partial potential models, global constraints, global links | 5-tuple of model-theoretic structures |
| $r, \bar{r}$ | Restriction (forgetful) map $r: M_p \to M_{pp}$ removing $T$-theoretical components, and its set lift $\bar{r}(X) = \{r(x) : x \in X\}$ | $M_{pp} = \{r(x) : x \in M_p\}$ |
| $\operatorname{Cn}_{\text{str}}(K)$ | Structuralist empirical content of core $K$ | $\{\bar{r}(X) : X \in \operatorname{Pot}(M) \cap GC \cap GL\} \subseteq \operatorname{Pot}(M_{pp})$ |
| $\mathrm{Basic}(\mathcal{N})$ | Set of greatest (basic) elements of $\langle N, \sigma \rangle$ | $\{T_0 \in N : \forall T \in N,\; T_0 \,\sigma\, T \implies T = T_0\}$ |
| $(M_p, \mathcal{U}), u \in \mathcal{U}$ | Bourbaki uniform space on $M_p$ and entourage relation $u \subseteq M_p \times M_p$ | Uniformity satisfying all 5 axioms |
| $\mathfrak{A} \subseteq \mathcal{U}, \tilde{u}$ | Family of admissible blurs and induced entourage $\tilde{u} \subseteq \operatorname{Pot}(M_{pp}) \times \operatorname{Pot}(M_{pp})$ | Approximative adequacy apparatus |
| $TS_{\text{local}}, TS_{\text{edge}}$ | Operational local and constraint-edge tenability scores (ADR-0015 / ADR-0022) | $[0, 1]$ |
| $Q_{\text{mod}}, Q_{\text{signed}}, \gamma_{\text{res}}$ | Graph modularity (unsigned / signed) and resolution parameter | Community-detection objective |
| $q_c$ | Additive per-community contribution to global modularity ($Q_{\text{mod}} = \sum_c q_c$) | $\mathbb{R}$ |
| $\mathrm{emb}_{\text{ctx}}(\cdot), \theta_{\cos}$ | Contextual dense embedding vector and cosine similarity threshold | $\mathbb{R}^d$, $[-1, 1]$ |

---

## Related Documentation

- [Consolidated References & Bibliography](references.md)
- [From Factual Knowledge Graphs to Epistemic Theory Graphs](kg_vs_tg.md)
- [Epistemology & Philosophy of Science](epistemology.md)
- [Formal Graph Schema & Argumentation Semantics](formal_graph_model.md)
- [Theory-Nets, Posets & Topologies](theory_nets_and_topologies.md)
