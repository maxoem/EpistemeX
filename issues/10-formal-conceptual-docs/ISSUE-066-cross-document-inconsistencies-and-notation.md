# [ISSUE-066] Cross-Document Inconsistencies, Incoherence & Notation Collisions in the Conceptual Corpus

| Metadata                | Details                                                                                                                                                                                                                                                                                         |
|:------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Issue ID**            | `ISSUE-066`                                                                                                                                                                                                                                                                                     |
| **Domain / Category**   | `10-Formal & Conceptual Docs` — (a) Inconsistencies & Incoherence                                                                                                                                                                                                                               |
| **Evaluated Docs**      | [`kg_vs_tg.md`](../../docs/concepts/kg_vs_tg.md), [`epistemology.md`](../../docs/concepts/epistemology.md), [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md), [`theory_nets_and_topologies.md`](../../docs/concepts/theory_nets_and_topologies.md)                             |
| **Priority**            | **Critical** (blocks publication: the four documents currently describe *different* objects under the same names)                                                                                                                                                                              |
| **Status**              | `Open`                                                                                                                                                                                                                                                                                          |
| **Related**             | [`ISSUE-067`](ISSUE-067-mathematical-errors-in-formalisms.md) (math), [`ISSUE-068`](ISSUE-068-conceptual-and-domain-errors.md) (domain), [`ISSUE-069`](ISSUE-069-philosophical-errors.md) (philosophy), [`ISSUE-070`](ISSUE-070-bibliography-and-attribution-audit.md) (citations)                |

Severity legend: **Critical** = contradicts a core claim / would be rejected in review · **Major** = must be fixed before
publishing · **Minor** = precision, style, presentation.

---

## A-01 · "TheoryNet" names two unrelated mathematical objects — **Critical**

**Where.** [`formal_graph_model.md#L1`](../../docs/concepts/formal_graph_model.md#L1), [`#L24-L35`](../../docs/concepts/formal_graph_model.md#L24-L35); [`theory_nets_and_topologies.md#L19-L20`](../../docs/concepts/theory_nets_and_topologies.md#L19-L20), [`#L51`](../../docs/concepts/theory_nets_and_topologies.md#L51); [`kg_vs_tg.md#L195-L196`](../../docs/concepts/kg_vs_tg.md#L195-L196).

**Finding.**

- In `formal_graph_model.md`, the **TheoryNet** is $TF = (At, R)$: a graph of *propositional argument atoms* with
  argumentative relations (statement view, argumentation theory).
- In `theory_nets_and_topologies.md`, the **Theory-Net** $TN$ is a poset $(TN, \alpha)$ of *theory-elements*
  $T = \langle K, I \rangle$ (structuralist non-statement view, where each node is a class of set-theoretic models plus
  intended applications).
- `kg_vs_tg.md` then says that L3 "materializes the formal TheoryNet—modeling axioms, claims, warrants, dialectical
  attacks, **and poset hierarchies**", which merges both.

These are different kinds of thing. Nodes of $TF$ are sentences or propositions. Nodes of $TN$ are tuples of model
classes. Edges of $TF$ are support and attack. Edges of $TN$ are specialization, defined by inclusion of model classes.
No mapping between the two is given anywhere. The abbreviation `TF` is never expanded either; German *Theoriennetz*
would give `TN`, which is already taken by the structuralist net.

**Fix.** Rename one of them, e.g. **Argument Graph / Dialectical Layer $\mathcal{D}$** for $(At, R)$ and
**Theory-Net $\mathcal{N} = \langle N, \sigma \rangle$** (BMS notation) for the structuralist poset. Then add a short
section defining the *bridge relation*, i.e. which atoms in $\mathcal{D}$ formulate laws or applications of which
theory-element in $\mathcal{N}$ (see C-12 in [`ISSUE-068`](ISSUE-068-conceptual-and-domain-errors.md)).

---

## A-02 · The layer model differs between documents — **Critical**

**Where.** [`kg_vs_tg.md#L190-L196`](../../docs/concepts/kg_vs_tg.md#L190-L196) vs.
[`formal_graph_model.md#L54-L133`](../../docs/concepts/formal_graph_model.md#L54-L133) vs.
[`theory_nets_and_topologies.md#L144-L149`](../../docs/concepts/theory_nets_and_topologies.md#L144-L149).

| Aspect                     | `kg_vs_tg.md`                                                 | `formal_graph_model.md`                                                                                | `theory_nets_and_topologies.md`                                       |
|:---------------------------|:--------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------|
| L2                         | "factual, entity-relational scaffold (`Person`, `Work`, `Concept`)" | "Deterministic Ontology" with confidences $\gamma, \delta$; includes *Theory* nodes                      | `L2Entity` pooled with L3 nodes for Leiden                            |
| L3                         | axioms, claims, warrants, attacks **and poset hierarchies**   | only a (D-)QBAF over claims and premises                                                               | Theory-Net poset, holons and communities (no layer assigned)          |
| Structuralist objects      | part of L3                                                    | separate section ("Structuralist Model-Theoretic Foundations"), **no layer**                           | primary object                                                        |
| Communities                | —                                                             | —                                                                                                      | mix L2 and L3 nodes in one undirected graph                           |

The global graph $G = (V, E, \lambda_v, \lambda_e)$ ([`formal_graph_model.md#L12-L22`](../../docs/concepts/formal_graph_model.md#L12-L22))
is said to contain "entities, concepts, premises, and claims". It is also said to be *isomorphic* to the argument
graph $(At, R)$ ([`#L34-L35`](../../docs/concepts/formal_graph_model.md#L34-L35)) and to be partitioned into $B \cup A$
([`#L50`](../../docs/concepts/formal_graph_model.md#L50)). These three statements cannot all hold: entities such as
*Person* nodes are neither argument atoms nor observation sentences or hypotheses.

**Fix.** Give a single **typed multi-layer definition**, e.g.
$G = (V_1 \uplus V_2 \uplus V_3 \uplus V_N,\; E_{\text{intra}} \uplus E_{\text{inter}},\; \dots)$, with one vertex set per
layer and explicitly typed inter-layer edges (`MENTIONED_IN`, `FORMULATES`, `INSTANTIATES` …). State in which layer the
structuralist net $\mathcal{N}$ lives (a fourth layer, or a projection). Apply the partition $B \uplus A$ **only to
$V_3$**.

---

## A-03 · Systematic notation collisions — **Major**

Across the four documents, many symbols carry 2–6 meanings, sometimes inside one file. A reader cannot type-check
any formula without resolving these.

| Symbol            | Meanings (file → line)                                                                                                                                                                                                                                                                                                                                                                                                         |
|:------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| $E$               | edge set (FGM L20); empirical content $E(H)$ (EPI L26); empirical **successes** $E(T)$ (EPI L62, L176); node energy $E_i(t)$ (FGM L225); $E_{\text{total}}$ (FGM L249); entity counts $E_{\text{correct}}$ (FGM L401); embedding $E_{\text{ctx}}$ (FGM L403)                                                                                                                                                               |
| $A$ / $\mathcal{A}$ | hypotheses in $\Delta=(B,A)$ (FGM L45); QBAF arguments "Claims or Premises" (FGM L127); "theoretical antecedents" only (FGM L161); all atoms $\mathcal{A}=B\cup A$ (FGM L185); Dung arguments $A\subseteq\mathcal{V}_{L3}$ (FGM L258); **admissible blurs** $\mathcal{A}\subseteq\mathcal{U}$ (FGM L323)                                                                                                                       |
| $B$               | observation base (FGM L43); minimal/root elements $B(TN)$ (TN L62); historical base $B(t)$ (EPI L232)                                                                                                                                                                                                                                                                                                                         |
| $M$               | failures $M(T)$ (EPI L62); models $M \subseteq M_p$ (FGM L309); modal strength $M(\phi_a)$ (FGM L189)                                                                                                                                                                                                                                                                                                                         |
| $\tau$            | base score $\tau$ (FGM L131); $\tau_0$ (FGM L188); thresholds $\tau_P, \tau_C$ (FGM L216); equilibrium $\tau^*$ (FGM L248); generic threshold in Prop. 1 (FGM L237); cosine threshold (FGM L403)                                                                                                                                                                                                                             |
| $w$, $W$          | base score $w(i)$ (FGM L231); edge weight $W_{ji}$ (FGM L210); ECHO weight $w_{ij}$ (EPI L204)                                                                                                                                                                                                                                                                                                                                |
| $\delta$          | L2 edge certainty function (FGM L115); disbelief score (FGM L367); RK4 step size (FGM L241)                                                                                                                                                                                                                                                                                                                                   |
| $\phi$            | edge weight function of $\Lambda$ (FGM L132); proposition $\phi_a$ in $M(\phi_a)$ (FGM L189)                                                                                                                                                                                                                                                                                                                                  |
| $\rho$            | gradual semantics $\rho: A\to[0,1]$ (FGM L133); spectral radius $\rho(J)$ (FGM L241)                                                                                                                                                                                                                                                                                                                                          |
| $\sigma$          | structural overlap (FGM L282); logistic sigmoid (FGM L237); BMS's standard symbol for specialization (not used; $\alpha$ is used instead, TN L42)                                                                                                                                                                                                                                                                         |
| $H$, $\mathcal{H}$ | ECHO harmony $H(t)$ (EPI L217); Heaviside $H$ (FGM L237); modularity $\mathcal{H}$ (TN L150)                                                                                                                                                                                                                                                                                                                                 |
| $\mathcal{P}$     | power set $\mathcal{P}(L1)$ (FGM L115); stance probability function (FGM L191); undefined codomain of $Z_1$ (FGM L277)                                                                                                                                                                                                                                                                                                      |
| $I$, $\mathcal{I}$ | intended applications $I$ (FGM L304, TN L17); inferential warrant $\mathcal{I}$ (FGM L190)                                                                                                                                                                                                                                                                                                                                  |
| $C$, $\mathcal{C}$ | chunk set (FGM L96); constraints $C$ (TN L37, L105); calibration $\mathcal{C}$ (FGM L192); consequence set $C(T)$ in the diagram vs. $\operatorname{Cn}(T)$ in the text (EPI L110 vs L142)                                                                                                                                                                                                                                |
| $K$               | structuralist core (FGM L304, TN L17); Lakatosian hard core $K_i$ (EPI L120, L159); "hard core $(K_0)$" = structuralist root core (TN L87)                                                                                                                                                                                                                                                                                  |
| $V$, $V_j$        | vertex set (FGM L19); **protective belt** $V_j$ (EPI L121, L161); **theory version** $V_j$ (EPI L174, L185)                                                                                                                                                                                                                                                                                                                  |
| $\lambda$         | type labellings $\lambda_v,\lambda_e$ (FGM L21-22), then **re-used as numeric** score functions $\tau=\lambda_v$, $\phi=\lambda_e$ (FGM L164-166); chunk metadata $\lambda_c$ (FGM L97)                                                                                                                                                                                                                                    |
| $S$ / $E$, $F$ / $M$ | successes and failures each given **two** symbols in parallel (EPI L176-189)                                                                                                                                                                                                                                                                                                                                               |

(FGM = `formal_graph_model.md`, EPI = `epistemology.md`, TN = `theory_nets_and_topologies.md`.)

**Fix.** Add one shared **Notation** section (or a `notation.md` appendix that all four documents reference) with one
symbol per concept. Suggested choices: $\mathsf{Succ}/\mathsf{Fail}$ for successes and failures; $E_{\mathrm{emp}}(\cdot)$
for empirical content; $\beta(a)$ for the base score; $\theta_P, \theta_C$ for thresholds; $s^*$ for equilibrium
strength; $h_\Delta$ for step size; $\sigma$ for specialization (BMS) and $\operatorname{sig}$ for the sigmoid; $\Pi$ for
the protective belt; $T^{(j)}$ for versions; $\mathfrak{A}$ for admissible blurs.

---

## A-04 · The base score is defined three incompatible ways — **Major**

**Where.** [`formal_graph_model.md#L131`](../../docs/concepts/formal_graph_model.md#L131), [`#L164`](../../docs/concepts/formal_graph_model.md#L164), [`#L188-L189`](../../docs/concepts/formal_graph_model.md#L188-L189); [`epistemology.md#L213-L214`](../../docs/concepts/epistemology.md#L213-L214); [`theory_nets_and_topologies.md#L79-L81`](../../docs/concepts/theory_nets_and_topologies.md#L79-L81).

1. $\tau$ = "prior plausibility base score". This is the standard QBAF reading of intrinsic strength (Baroni, Rago &
   Toni 2019).
2. $\tau$ = "vertex labeling $\lambda_v$". This is a type error, since $\lambda_v$ maps into a type hierarchy $T_v$, not into $[0,1]$.
3. $\tau_0(a) \equiv M(\phi_a)$ = "authorial modal certainty asserted in the text", i.e. hedging.

Meanwhile, observation nodes are said to have **intrinsic acceptability** under "Data Priority" (EPI, TN). The documents
never say how a $b \in B$ obtains its $\tau_0$ when the author does not hedge it, or whether Data Priority overrides
$M(\phi_b)$. For the philosophical problem with reading (3) as a prior, see D-15 in [`ISSUE-069`](ISSUE-069-philosophical-errors.md).

**Fix.** Pick one reading. If (3) is kept, rename the concept (e.g. *assertoric strength*). Then add an explicit rule
deriving $\beta(a)$ from assertoric strength, layer membership ($B$ vs. $A$) and, optionally, Data Priority.

---

## A-05 · "Theory graphs are DAGs" contradicts the dialectical and coherentist parts — **Critical**

**Where.** [`kg_vs_tg.md#L93`](../../docs/concepts/kg_vs_tg.md#L93) ("Graph Topology: DAGs, Theory-Posets, QBAF
networks"); [`theory_nets_and_topologies.md#L128`](../../docs/concepts/theory_nets_and_topologies.md#L128) vs.
[`#L132`](../../docs/concepts/theory_nets_and_topologies.md#L132) ("Coherentist: a **cyclical** network");
[`formal_graph_model.md#L239`](../../docs/concepts/formal_graph_model.md#L239) ("mixed cyclic networks converge
empirically").

Dialectical opposition is **inherently cyclic**. Mutual rebuttal $a \rightleftarrows b$ is the textbook case (Dung 1995;
in ASPIC+ rebuttal between contradictory conclusions is symmetric; Modgil & Prakken 2014). The `kg_vs_tg` example
"Utilitarianism ATTACKS Kantian deontology" would naturally be answered by a counter-attack. `formal_graph_model.md`
spends a whole convergence discussion on cyclic graphs. Only the **specialization order** of a structuralist net is
acyclic, and only in its strict or Hasse form (see B-24 in [`ISSUE-067`](ISSUE-067-mathematical-errors-in-formalisms.md)).

**Fix.** State: *"The specialization sub-structure $\langle N, \sigma\rangle$ is a finite poset (its Hasse diagram is a
DAG); the dialectical layer is a general directed graph that admits cycles."*

---

## A-06 · "Counting is invalid" vs. metrics that count — **Major**

**Where.** [`epistemology.md#L45-L49`](../../docs/concepts/epistemology.md#L45-L49) ("unification cannot be operationalized merely by counting … reflected in high **out-degree** centrality"); [`#L69-L71`](../../docs/concepts/epistemology.md#L69-L71) ("Merely counting raw numbers of successes is epistemologically invalid"); [`#L187-L189`](../../docs/concepts/epistemology.md#L187-L189) (Degeneration Index = ratio of **cardinalities**); [`theory_nets_and_topologies.md#L178-L179`](../../docs/concepts/theory_nets_and_topologies.md#L178-L179).

The same document rejects counting as a measure of unification and of progress. It then measures unification by
out-degree, which is a count, and degeneration by $\lvert M_b\rvert / (\lvert E\rvert + \lvert M_a\rvert)$, which is a
ratio of counts.

**Fix.** Either (i) keep the set-inclusion order as the *normative* criterion and present cardinality indices
explicitly as *heuristic proxies*, with their known failure modes (individuation of phenomena, equal weighting), or
(ii) drop the "counting is invalid" claim. Replace out-degree by a diversity-sensitive measure (see C-16).

---

## A-07 · Novel-prediction requirement vs. success definition — **Major**

**Where.** [`epistemology.md#L45-L48`](../../docs/concepts/epistemology.md#L45-L48) (unification measured by **novel predictions**, not post-hoc explanations) vs. [`#L176`](../../docs/concepts/epistemology.md#L176) (successes = "phenomena correctly predicted **or explained**") vs. [`#L191-L192`](../../docs/concepts/epistemology.md#L191-L192).

The Degeneration Index rewards post-hoc explanations equally with novel predictions, which is exactly what the
globality section rules out. For Lakatos, a problem shift is *theoretically progressive* only if it predicts novel facts,
and *empirically progressive* only if some of them are corroborated (Lakatos 1970, pp. 118 ff.).

**Fix.** Split $\mathsf{Succ}$ into $\mathsf{Succ}^{\text{nov}}$ (temporally or use-novel; Zahar 1973) and
$\mathsf{Succ}^{\text{acc}}$ (accommodated), and define progressiveness over $\mathsf{Succ}^{\text{nov}}$.

---

## A-08 · Empirical creativity and homogeneity contradict each other — **Critical**

**Where.** [`epistemology.md#L29-L31`](../../docs/concepts/epistemology.md#L29-L31) vs. [`#L83-L89`](../../docs/concepts/epistemology.md#L83-L89).

The creativity test compares $E(H_1 \wedge H_2)$ with the **plain union** $E(H_1)\cup E(H_2)$. The homogeneity test
uses $\operatorname{Cn}(E_1 \cup E_2)$. With the union version, the tacked theory $T \wedge H$, which the homogeneity
section rules out, **passes** the creativity test: $e_T \wedge e_H \in E(T\wedge H)$ but
$e_T \wedge e_H \notin E(T)\cup E(H)$. The two criteria therefore classify the paradigm counter-example in opposite ways.
Full proof and correction: B-01 / B-02 in [`ISSUE-067`](ISSUE-067-mathematical-errors-in-formalisms.md).

---

## A-09 · Three different definitions of "empirical / non-theoretical" vocabulary — **Major**

| Document                                                                                                                                 | Definition                                                                                                                                                                   |
|:-----------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`epistemology.md#L131-L132`](../../docs/concepts/epistemology.md#L131-L132)                                                             | $L_E$: "presupposed as already understood … observation terms **or terms established by unproblematic background theories**" (pre-theoretical, close to Schurz)            |
| [`formal_graph_model.md#L311-L312`](../../docs/concepts/formal_graph_model.md#L311-L312)                                                 | $M_{pp}$: "non-theoretical, **directly observable** terms"                                                                                                                |
| [`theory_nets_and_topologies.md#L79-L80`](../../docs/concepts/theory_nets_and_topologies.md#L79-L80)                                     | "**exclusively empirical** terms ($L_E$)"                                                                                                                                  |
| [`formal_graph_model.md#L43-L44`](../../docs/concepts/formal_graph_model.md#L43-L44)                                                     | $B$: "**verifiable**, minimally contested empirical data"                                                                                                                  |

Sneed's $T$-theoreticity is *relative to a theory* and explicitly **not** an observability criterion (see D-05). Treating
these as one distinction is the central conceptual bridge between Schurz and structuralism, and right now it is
inconsistent.

**Fix.** Adopt Schurz's *pre-theoretical relative to $T$* as the general notion. State that Sneed's
$T$-non-theoretical is a special case of it, not "observable". Remove "verifiable" and "directly observable".

---

## A-10 · Hard core vs. structuralist core vs. version indices — **Major**

**Where.** [`epistemology.md#L119-L122`](../../docs/concepts/epistemology.md#L119-L122), [`#L159-L163`](../../docs/concepts/epistemology.md#L159-L163), [`#L181`](../../docs/concepts/epistemology.md#L181); [`theory_nets_and_topologies.md#L86-L87`](../../docs/concepts/theory_nets_and_topologies.md#L86-L87); [`formal_graph_model.md#L304`](../../docs/concepts/formal_graph_model.md#L304).

- `epistemology.md` indexes the hard core as $K_i$, which suggests several cores. The ad-hoc definition at L181 then
  compares $K_{i+1}$ with $K_i$, i.e. it **changes the hard core** between versions. By Lakatos's definition the hard
  core is constant within a programme (negative heuristic); only the belt changes.
- `theory_nets_and_topologies.md` calls the structuralist root core "the hard core $(K_0)$".
- `formal_graph_model.md` uses $K$ for the structuralist formal core $\langle M_p, M, M_{pp}, \dots\rangle$.

The identification of Lakatos's hard core with the core of the basic theory-element *is* a known thesis (Stegmüller
1976, ch. on Lakatos/Kuhn). But it is a substantive philosophical claim and is used here silently (see D-06).

**Fix.** Use $\mathbf{HC}$ (constant) and $\Pi^{(j)}$ (belt of version $j$) for Lakatos. Use $K(T)$ for structuralist
cores. Add one sentence citing Stegmüller (1976) for the bridge thesis and noting where it is contested.

---

## A-11 · Hard filter "never diluted" vs. soft filter that dilutes — **Major**

**Where.** [`formal_graph_model.md#L176-L178`](../../docs/concepts/formal_graph_model.md#L176-L178), [`#L217`](../../docs/concepts/formal_graph_model.md#L217), [`#L219-L221`](../../docs/concepts/formal_graph_model.md#L219-L221).

The D-QBAF is motivated by the claim that multiplying an inferential quantity by a perception probability "couples
orthogonal dimensions". Mode 2 then sets $W = \mathcal{I}\cdot\operatorname{sig}(k(\mathcal{P}-\tau_P))\cdot\operatorname{sig}(k(\mathcal{C}-\tau_C))$,
which is again a multiplicative coupling of $\mathcal{I}$ with $\mathcal{P}$. With $k=20$ and $\mathcal{P}=\tau_P+0.05$,
$\mathcal{C}\gg\tau_C$: $W \approx 0.73\,\mathcal{I}$. An edge that is admitted with confidence still loses 27 % of its
warrant. See B-10 for why the stated justification (Filippov) is also wrong.

---

## A-12 · ECHO coherence links do not fit the QBAF typing — **Major**

**Where.** [`theory_nets_and_topologies.md#L114-L117`](../../docs/concepts/theory_nets_and_topologies.md#L114-L117) vs. [`formal_graph_model.md#L132`](../../docs/concepts/formal_graph_model.md#L132), [`#L186-L187`](../../docs/concepts/formal_graph_model.md#L186-L187); [`epistemology.md#L203-L204`](../../docs/concepts/epistemology.md#L203-L204).

- ECHO links are **symmetric** ($w_{pq}=w_{qp}$, TEC Principle 1). $\mathcal{R}_{sup}, \mathcal{R}_{att}$ are
  **directed** relations.
- Inhibitory links carry **negative** weight ($\approx -0.20$). $\phi, \mathcal{I}, W \in [0,1]$, with the sign carried
  by the relation type.
- $H(t)=\sum_{ij} w_{ij}a_ia_j$ is a Lyapunov-type quantity only for **symmetric** weights (Hopfield 1982), so it is not
  the quantity the directed D-QBAF dynamics optimise.

Yet the metrics table ([`formal_graph_model.md#L405`](../../docs/concepts/formal_graph_model.md#L405)) uses $H(t)$ as
"Structural Coherence" of the same graph.

**Fix.** Define an explicit **symmetrisation map** $\mathcal{D}\to\text{ECHO}$ (e.g.
$w_{ij}=w_{ji}=\epsilon^{+}\cdot\max(W_{ij},W_{ji})$ for support and $-\epsilon^{-}$ for attack) and state that ECHO and
the D-QBAF are *alternative* semantics (see C-10).

---

## A-13 · "Isolated axioms cannot be falsified" vs. falsification edges on single laws — **Minor**

**Where.** [`epistemology.md#L12-L13`](../../docs/concepts/epistemology.md#L12-L13), [`#L56-L61`](../../docs/concepts/epistemology.md#L56-L61) vs. [`theory_nets_and_topologies.md#L112-L113`](../../docs/concepts/theory_nets_and_topologies.md#L112-L113), [`#L93-L94`](../../docs/concepts/theory_nets_and_topologies.md#L93-L94).

Falsification schemata of the form "evidence $\Vdash \neg$(Universal Law)" are correct for **empirical generalisations**
but, by the documents' own Duhem–Quine thesis, not for theoretical laws. The text should restrict the schemata to
$L_E$-laws. Separately, TN L93-94 equates "synthetic contingent" with "genuine empirical content", which contradicts
EPI L12 (a contingent theoretical axiom such as $F=ma$ has *no* empirical content in isolation).

---

## A-14 · Interpretation variance is promised but not formalised — **Major**

**Where.** [`kg_vs_tg.md#L104-L109`](../../docs/concepts/kg_vs_tg.md#L104-L109) ("must represent contested readings") vs. the whole of [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md).

Nothing in $G$, $\Lambda$ or $\mathcal{Q}$ carries an **interpretation / reading / perspective index**. Two incompatible
readings of the same passage can only appear as two atoms that attack each other. That conflates *exegetical*
disagreement (what Kant meant) with *substantive* disagreement (whether Kant is right).

**Fix.** Add a reading parameter, e.g. atoms $a = \langle p, \text{src}, \text{reading } r\rangle$ with readings forming a
set $\mathcal{R}_{\text{int}}$, and a distinct relation `ALTERNATIVE_READING_OF` that is **not** a sub-role of
$\mathcal{R}_{att}$.

---

## A-15 · Broken internal anchors and self-containedness gaps — **Minor**

- `kg_vs_tg.md` links three times to `epistemology.md#lakatos-research-programmes`
  ([L54](../../docs/concepts/kg_vs_tg.md#L54), [L141](../../docs/concepts/kg_vs_tg.md#L141), [L166](../../docs/concepts/kg_vs_tg.md#L166)).
  **No such heading exists.** The nearest is "Lakatosian Theory Dynamics & The Degeneration Index".
- **Undefined symbols / terms** in documents declared self-contained: `Jev` (FGM L192, L205), `epistemetrics` (FGM L220),
  $\mathcal{V}_{L3}$ (FGM L127, L258), $\text{Bound}(\mathcal{A})$ (FGM L325), $RED(p,E,E')$ (TN L109), $CL$ (TN L105),
  $\mathcal{P}$ in $Z_1$ (FGM L277), "Phase 5" vs. "Phase 5b" (TN L140 vs L144).
- **Internal documents used as bibliographic citations**: e.g. "(Balzer, Moulines, & Sneed, 1987)" links to
  `theory_nets_and_topologies.md` and "(Schurz, 2014)" links to `epistemology.md`
  ([kg_vs_tg.md#L23](../../docs/concepts/kg_vs_tg.md#L23)); Kuhn and Stegmüller link to the glossary
  ([L116](../../docs/concepts/kg_vs_tg.md#L116)). Neither `kg_vs_tg.md`, `formal_graph_model.md` nor
  `theory_nets_and_topologies.md` has a reference list. See [`ISSUE-070`](ISSUE-070-bibliography-and-attribution-audit.md).

---

## A-16 · Presentation-level inconsistencies — **Minor**

1. Product name: "**Grund Episteme**" ([FGM L3-L4](../../docs/concepts/formal_graph_model.md#L3-L4)) vs. "Episteme" everywhere else.
2. `epistemology.md` announces "**four** primary methodological criteria" ([L16](../../docs/concepts/epistemology.md#L16))
   but presents four sections that bundle six notions (system character, creativity, globality, unification, two holisms,
   homogeneity).
3. "**Theory statics**" ([EPI L96](../../docs/concepts/epistemology.md#L96)) includes "Epistemic Status (**Lakatosian
   Dynamics**)" as dimension 4. The mermaid diagram also draws the four *dimensions* as a sequential pipeline `D1 → D2 → D3 → D4`.
4. German/English mixing without glossing: subscripts "$F_{\text{Typ a}}$" in English formulas; "i.e.S." / "i.w.S."
   undefined (TN L79-84); *Haltbarkeit*, *Adäquatheit* as labels for non-standard notions.
5. Math delimiters mix `$$…$$` and `\[…\]`. Several display formulas inside list items break indentation
   ([FGM L276-L283](../../docs/concepts/formal_graph_model.md#L276-L283), [L325-L326](../../docs/concepts/formal_graph_model.md#L325-L326), [L336](../../docs/concepts/formal_graph_model.md#L336), [L341](../../docs/concepts/formal_graph_model.md#L341)).
6. **Broken table row**: [FGM L401](../../docs/concepts/formal_graph_model.md#L401). The pipes in `|E_correct|` split the
   cell. Use `\lvert … \rvert`.
7. Implementation and history in conceptual docs: Neo4j/Cypher (FGM L32, L217), NetworkX & "Phase 5b" (TN L144-147),
   `solve_ivp` RK45/Radau (FGM L241), "earlier theory graph implementations" (FGM L176). These belong in ADRs or
   architecture docs.
8. Register: "fatal logical trap", "mathematically mandatory", "explosive numerical divergence", "foundational
   vulnerability" are not publication register.
9. `kg_vs_tg.md` assigns `Concept` to the **KG** layer L2 ([L194](../../docs/concepts/kg_vs_tg.md#L194)), while the
   same document's table says TGs, unlike KGs, focus on "abstract concepts" ([L88](../../docs/concepts/kg_vs_tg.md#L88)).
