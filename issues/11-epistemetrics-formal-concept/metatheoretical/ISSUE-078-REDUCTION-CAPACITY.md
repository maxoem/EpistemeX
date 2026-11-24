# [ISSUE-078] Formal & Conceptual Evaluation: Reduction Capacity (`reduction_capacity.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-078` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 5: Metatheoretical Framework (listed under Pillar 4 in `index.md`) |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (morphism direction in $SPR$ contradicts structuralist reduction $p: M_p(T') \to M_p(T)$, `:REDUCES_TO` and `:SUBSUMES` have opposite directions, and $ECI$ takes a literal set intersection across distinct vocabularies instead of applying the reduction map) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-010`](../../04-diachronic-dynamics/ISSUE-010-theory-reduction-and-kuhn-loss-tracking.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Broken Mapping)** | Claims to formalize structuralist strict and approximative reduction ($p(M(T')) \subseteq M(T)$ / $p(M(T')) \approx_{\mathcal{A}} M(T)$ under limit conditions). However, $ECI(T_1, T_2) = \frac{\|I(T_1) \cap I(T_2)\|}{\|I(T_1)\|}$ computes a **raw set intersection** without applying the reduction translation morphism $\phi$, which evaluates to $0$ whenever predecessor and successor applications are distinct nodes or phrased in distinct vocabularies. Meanwhile, $SPR(T_1, T_2)$ ignores edge types, polarities, injectivity, and multi-hop derivations. |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) Reverses the morphism direction between L24 ($p: M_p(T') \to M_p(T)$, successor to predecessor) and L32 ($\phi: V(G_{T_1}) \to V(G_{T_2})$, predecessor to successor); (2) treats `:REDUCES_TO` and `:SUBSUMES` as synonymous (L51) despite having opposite source/target directions; (3) leaves $\phi$ unbound in $SPR(T_1, T_2)$ and lacks division-by-zero guards when $\|E(G_{T_1})\| = 0$ or $\|I(T_1)\| = 0$. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts across three incompatible definitions: (a) structuralist model-class translation with topological blurs $\approx_A$ and asymptotic limits $v/c \to 0$ (L16–27), (b) unweighted 1-hop graph homomorphism $SPR$ + node ID intersection $ECI$ with no blurs or limits (L32–46), and (c) gold-standard link-prediction Precision/Recall/F1 in `epistemetrics/epistemic/reduction_evaluation.py`. |
| **4. Valid & Scientifically Significant?** | **Yes (Core Concept)** | Inter-theoretic reduction and Kuhn-loss tracking (Stegmüller 1976; BMS 1987, Ch. V & VII) are essential for evaluating diachronic paradigm shifts (`ISSUE-010`), but `epistemetrics` currently lacks any intrinsic evaluator for $SPR$, $ECI$, or $RS$. |

---

## 1. Does the Metric Capture What It Claims It Does?

### RC-01 · Contradictory Morphism Directions ($p: M_p(T') \to M_p(T)$ vs. $\phi: V(G_{T_1}) \to V(G_{T_2})$) and Inverted `:REDUCES_TO` vs. `:SUBSUMES` Semantics — **Critical**

**Where.** [`reduction_capacity.md#L11-L17`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L11-L17), [`#L24`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L24), [`#L32-L40`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L32-L40), [`#L51`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L51).

**Finding.**
The document switches notation and reverses arrow directions three times across 40 lines:
1. **Unannounced Notation Switch ($T, T' \to E, E' \to T_1, T_2$):**
   - L11–12 defines $T'$ as the **successor** theory-net and $T$ as the **predecessor** theory-net.
   - L24 writes $\text{RED}(p, E, E')$ without defining $E$ or $E'$, and defines the structuralist reduction function $p: M_p(T') \to M_p(T)$ mapping **from the successor $T'$ to the predecessor $T$** (which is mathematically standard in BMS 1987, p. 256 & p. 372, because a more fine-grained successor model in $M_p(T')$ is projected/coarsened onto a predecessor model in $M_p(T)$ in the limit $v/c \to 0$).
   - L32 switches to $G_{T_1}$ and $G_{T_2}$ without stating which is the predecessor and which is the successor. Only on L40 (*"Let $I(T_1)$ be the intended applications of the predecessor theory"*) do we learn that **$T_1$ is the predecessor** and **$T_2$ is the successor**.
   - Yet L32 defines the translation morphism $\phi: V(G_{T_1}) \to V(G_{T_2})$ **from the predecessor $T_1$ to the successor $T_2$**—the exact opposite direction of $p: M_p(T') \to M_p(T)$ on L24!
2. **Conflation of Converse Relations `:REDUCES_TO` and `:SUBSUMES` (L51):**
   - L51 instructs: *"1. **Reduction Edge Detection**: Identify inter-theoretic `:REDUCES_TO` and `:SUBSUMES` relations between distinct `:TheoryNet` containers."*
   - `:REDUCES_TO` and `:SUBSUMES` are **relational converses**! If predecessor $T_1$ reduces to successor $T_2$ ($T_1 \xrightarrow{\text{REDUCES\_TO}} T_2$), then successor $T_2$ **subsumes** predecessor $T_1$ ($T_2 \xrightarrow{\text{SUBSUMES}} T_1$).
   - Even worse, in physics prose (L17: *"relativistic mechanics reducing to Newtonian mechanics as $v/c \to 0$"*), "reduces to" is used in the asymptotic limit sense ($T_{\text{successor}} \to T_{\text{predecessor}}$), whereas in Nagel/Stegmüller philosophy of science, "is reduced to" runs $T_{\text{predecessor}} \to T_{\text{successor}}$.
   - Because $SPR(T_1, T_2)$ and $ECI(T_1, T_2)$ are **asymmetric** (dividing by $|E(G_{T_1})|$ and $|I(T_1)|$), swapping source and target between `:REDUCES_TO` and `:SUBSUMES` completely corrupts the denominator (dividing by the successor's larger domain instead of the predecessor's domain!).

**Fix.**
1. Use consistent notation throughout: $T_{\text{old}}$ (predecessor) and $T_{\text{new}}$ (successor).
2. Fix the canonical edge direction in `epistemetrics` (`RelationType.REDUCES_TO`): specify explicitly that `(T_old)-[:REDUCES_TO]->(T_new)` has `source = T_old` (predecessor) and `target = T_new` (successor), while any `(T_new)-[:SUBSUMES]->(T_old)` edge must be inverted to `(T_old)-[:REDUCES_TO]->(T_new)` during canonicalization.
3. Explicitly distinguish the **syntactic/concept translation morphism** $\phi: V(G_{T_{\text{old}}}) \to V(G_{T_{\text{new}}})$ (mapping predecessor concepts/laws to their successor counterparts) from the **model-theoretic projection functor** $p: M_p(T_{\text{new}}) \to M_p(T_{\text{old}})$ (which is contravariant to the syntactic translation $\phi$, as standard in institution theory / categorical model theory!).

---

### RC-02 · $ECI(T_1, T_2)$ Uses Literal Set Intersection $I(T_1) \cap I(T_2)$ Instead of the Reduction Mapping Image — **Critical**

**Where.** [`reduction_capacity.md#L38-L43`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L38-L43) vs. [`ISSUE-010#L31`](../../04-diachronic-dynamics/ISSUE-010-theory-reduction-and-kuhn-loss-tracking.md#L31).

**Finding.**
Empirical Claim Invariance is defined on L42 as:
$$ECI(T_1, T_2) = \frac{|I(T_1) \cap I(T_2)|}{|I(T_1)|}$$
In both structuralist model theory (BMS 1987, p. 372) and Episteme's property graph:
1. $I(T_1) \subseteq M_{pp}(T_1)$ and $I(T_2) \subseteq M_{pp}(T_2)$ are formulated in the respective non-theoretical vocabularies of $T_1$ and $T_2$ (and in a Neo4j/NetworkX graph, each `:TheoryNet` container has its own application node instances or translated phenomenon descriptions).
2. Without applying the translation morphism $\phi$ (or reduction correspondence $\rho \subseteq I(T_1) \times I(T_2)$), the literal set intersection $I(T_1) \cap I(T_2)$ is **empty ($\emptyset$)** whenever the two theory-nets do not share identical node IDs!
3. Furthermore, this contradicts [`ISSUE-010`](../../04-diachronic-dynamics/ISSUE-010-theory-reduction-and-kuhn-loss-tracking.md#L31), which correctly defines Kuhn-Loss using the reduction mapping $\rho$:
   $$L_{\text{lost}}(T_{\text{old}}, T_{\text{new}}) = \frac{|I(T_{\text{old}}) \setminus \rho(I(T_{\text{new}}))|}{|I(T_{\text{old}})|}.$$
4. Finally, $ECI$ does not verify whether the translated application $\phi(i) \in I(T_{\text{new}})$ is actually **explained / empirically tenable** in $T_{\text{new}}$ (as opposed to being an unresolved anomaly of $T_{\text{new}}$).

**Fix.**
Define $ECI$ using the translation morphism $\phi$ (or correspondence $\rho$) restricted to **tenable / confirmed** applications of $T_{\text{new}}$:
$$ECI(T_{\text{old}}, T_{\text{new}}; \phi) = \frac{|\{i \in I(T_{\text{old}}) \mid \phi(i) \in I_{\text{confirmed}}(T_{\text{new}})\}|}{|I(T_{\text{old}})|} = 1 - L_{\text{lost}}(T_{\text{old}}, T_{\text{new}}).$$

---

### RC-03 · $SPR(T_1, T_2)$ Is Gameable by Degenerate (Non-Injective / Polarity-Blind) Homomorphisms and Penalizes Multi-Step Derivations — **Major**

**Where.** [`reduction_capacity.md#L34-L36`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L34-L36).

**Finding.**
The Structural Preservation Ratio is defined on L36 as:
$$SPR(T_1, T_2) = \frac{|\{(u, v) \in E(G_{T_1}) \mid (\phi(u), \phi(v)) \in E(G_{T_2})\}|}{|E(G_{T_1})|}$$
This formulation has three structural flaws:
1. **Degenerate Collapse via Non-Injective $\phi$:** Because $\phi: V(G_{T_1}) \to V(G_{T_2})$ is not required to be injective (or to prevent collapsing distinct axioms onto a single node/edge), mapping all nodes of $G_{T_1}$ onto a single connected pair $(x, y) \in E(G_{T_2})$ (or a self-loop) yields $SPR = 1.0$ even though $100\%$ of the internal differentiation of $T_1$ was destroyed.
2. **Blindness to Edge Relation Types and Polarities:** $(\phi(u), \phi(v)) \in E(G_{T_2})$ does not check whether the edge in $G_{T_2}$ has the same epistemic polarity or compatible `RelationType` as $(u, v) \in E(G_{T_1})$. If $(u, v)$ is an `:EXPLAINS` edge in $T_1$ and $(\phi(u), \phi(v))$ is an `:ATTACKS` edge in $T_2$ (i.e., $T_2$ *refutes* the relation of $T_1$!), $SPR$ counts it as $+1$ preserved structure!
3. **Failure on Multi-Step Micro-Reductions:** In genuine scientific reductions (e.g., deriving the macro Ideal Gas Law $P V = n R T$ in thermodynamics $T_1$ from statistical mechanics $T_2$, or Kepler's laws from Newton's laws), a direct 1-hop relation $(u, v) \in E(G_{T_1})$ becomes a **multi-step derivation path** $\phi(u) \xrightarrow{+}_{G_{T_2}} \phi(v)$ in the deeper successor theory $T_2$. Checking only direct edges $(\phi(u), \phi(v)) \in E(G_{T_2})$ assigns $0$ to multi-hop derivations!

**Fix.**
1. Require $\phi$ to be a **node-type-compatible, injective (or bounded-fiber) partial mapping** on core laws/concepts.
2. Evaluate preservation over the **typed transitive closure** (or damped shortest derivation path) of positive explanatory/deductive edges $E^+$:
   $$SPR(T_{\text{old}}, T_{\text{new}}; \phi) = \frac{1}{|E^+(G_{T_{\text{old}}})|} \sum_{(u, v) \in E^+(G_{T_{\text{old}}})} \mathbb{I}\!\left(\phi(u) \neq \phi(v) \land \phi(u) \xrightarrow{+}_{E^+(G_{T_{\text{new}}})} \phi(v)\right).$$

---

## 2. Is the Metric Formally & Mathematically Correct?

### RC-04 · Unbound Morphism $\phi$ and Division-by-Zero Traps — **Major**

**Where.** [`reduction_capacity.md#L32-L46`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L32-L46).

**Finding.**
1. **Free Variable $\phi$:** In $SPR(T_1, T_2)$ (L36), $\phi$ appears on the right-hand side without appearing as an argument on the left-hand side or being quantified (e.g. $\max_{\phi \in \Phi_{\text{adm}}}$).
2. **Division by Zero:** When $|E(G_{T_1})| = 0$ (an axiomatic theory without extracted internal edges) or $|I(T_1)| = 0$ (a formal theory without extracted application nodes), $SPR$ and $ECI$ divide by zero.

**Fix.**
Parameterize $SPR(T_{\text{old}}, T_{\text{new}}; \phi)$ and $ECI(T_{\text{old}}, T_{\text{new}}; \phi)$ explicitly by $\phi$ (or define $RS(T_{\text{old}}, T_{\text{new}}) = \max_{\phi \in \Phi_{\text{adm}}} \frac{1}{2}(SPR + ECI)$), and guard empty denominators by returning $0.0$.

---

### RC-05 · Undefined Diagnostic Interval for $0.4 \le RS < 0.8$ — **Minor**

**Where.** [`reduction_capacity.md#L60-L63`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L60-L63).

**Finding.**
The diagnostic table defines only two regimes:
- $RS \ge 0.8 \implies$ *Genuine Intersubjective Reduction*
- $RS < 0.4 \implies$ *Incommensurability / Paradigm Break*

The entire intermediate interval $0.4 \le RS < 0.8$—which represents **Partial / Approximative Reduction with Kuhn-Loss** (where part of the predecessor's domain or structure is retained while another part is abandoned)—has no diagnostic label.

**Fix.**
Add the middle row $0.4 \le RS < 0.8$: **Partial Reduction with Kuhn-Loss** (*Successor subsumes core applications of predecessor but abandons peripheral explanatory domains or mechanisms*).

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### RC-06 · Triple Semantic Shift Between Approximative Model Reduction, Unweighted Graph Overlap, and Benchmark Link-Prediction F1 — **Major**

**Where.** [`reduction_capacity.md#L22-L28`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L22-L28) $\to$ [`#L32-L55`](../../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md#L32-L55) $\to$ [`packages/epistemetrics/src/epistemetrics/epistemic/reduction_evaluation.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/reduction_evaluation.py).

**Finding.**
1. **§Theoretical Grounding (L24–28):** Defines both *Strict Reduction* ($p(M(T')) \subseteq M(T)$) and *Approximative Direct Reduction* ($p(M(T')) \approx_A M(T)$ within admissible blurs, Formula DVII-22 of BMS 1987).
2. **§Mathematical Specification (L32–46) & §Implementation (L50–55):** Completely drops blurs $\approx_A$ and limit conditions (`limit: "c -> infinity"` on L54 never enters any equation in §Mathematical Specification!).
3. **Codebase Implementation (`reduction_evaluation.py`):** In `epistemetrics`, `reduction_evaluation.py` does not compute $SPR$, $ECI$, or $RS$ at all; it only computes benchmark link-prediction Precision, Recall, and F1 of `:REDUCES_TO` and `:PRESUPPOSES` triples against a ground-truth reference graph.

**Fix.**
1. Incorporate an approximative fidelity weight $w_{\text{approx}}(e) \in [0, 1]$ (from tenability blurs or limit-condition validity) into $SPR$ so that approximative reductions ($p(M(T')) \approx_A M(T)$) are reflected in the formula.
2. Implement an intrinsic `evaluate_reduction_capacity(pred_net, succ_net, phi)` function in `epistemetrics/epistemic/reduction_evaluation.py` alongside the extrinsic benchmark link evaluator `evaluate_intertheoretical_links`.

---

## 4. Is the Metric Valid and Scientifically Significant?

### RC-07 · Cross-Pillar Taxonomy Placement Conflict (Pillar 4 vs. Pillar 5) — **Minor**

**Where.** [`docs/concepts/theory/metrics/index.md#L108`](../../../docs/concepts/theory/metrics/index.md#L108) vs. `docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md`.

**Finding.**
In `docs/concepts/theory/metrics/index.md` (L108), **Reduction Capacity** is categorized under **Pillar 4: Theory Dynamics (Diachronic Evolution)** and is absent from the Pillar 5 table (L114–123), yet the file itself resides in `docs/concepts/theory/metrics/metatheoretical/` (Pillar 5) rather than `docs/concepts/theory/metrics/theory_dynamics/`.

**Fix.**
Either move `reduction_capacity.md` to `docs/concepts/theory/metrics/theory_dynamics/` to match `index.md` and `ISSUE-010`, or cross-list it in `index.md` with a note explaining its dual role.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Corrupted Zotero Key (L13):** Links `[Balzer et al., 1987, p. 372](zotero://select/library/items/24SNSW2B)` to `24SNSW2B`, which is the Zotero key for **Schurz (2024)** in all other files.
2. **Unregistered Labels (L51):** Uses `:TheoryNet` and `:SUBSUMES`. In `epistemetrics/core/models.py`, the canonical types are `NodeType.THEORY_ELEMENT` and `RelationType.REDUCES_TO`.
