# [ISSUE-080] Formal & Conceptual Evaluation: T-Theoreticity (`t_theoreticity.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-080` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 5: Metatheoretical Framework |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (vacuous universal quantification over $M(\tau) = \emptyset$ classifies every unmeasured/observational term as $TI = 1$ [$T$-theoretical], simple graph paths treat conjunctive law dependencies as disjunctive alternatives, and Balzer–Gähde criterion contradicts `glossary.md`) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-005`](../../02-structuralist-engine/ISSUE-005-sneedian-theoreticity-and-ramseyification.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md), [`ISSUE-069`](../../10-formal-conceptual-docs/ISSUE-069-philosophical-errors.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted on $M(\tau)=\emptyset$ & Conjunctive Paths)** | Claims to operationalize Sneed's functional criterion for $T$-theoreticity. However: (1) whenever a term $\tau$ has no extracted measurement pathways ($M(\tau) = \emptyset$, which holds for almost all basic observational/pre-theoretical terms in text corpora), the universal quantifier $\forall p \in M(\tau)$ is **vacuously true**, assigning $TI(\tau, T) = 1$ ($T$-theoretical!) to every unmeasured empirical term; (2) modeling $M(\tau)$ as simple graph paths $p_i$ treats a **conjunctive** measurement requirement (needing both pre-theory $T^*$ AND law $l \in T$) as two independent paths, falsely classifying $T$-theoretical terms as $TI(\tau, T) = 0$. |
| **2. Formally & Mathematically Correct?** | **No (Critical/Major Flaws)** | (1) Vacuous truth trap at $M(\tau) = \emptyset$; (2) AND/OR hyperpath confusion in $\text{Presupposes}(p_i)$; (3) structuralist type error writing $\tau \in M_p \setminus M_{pp}$ and $\tau \in M_{pp}$ (confusing signature symbols $\tau$ with model tuples and assuming $M_{pp} \subseteq M_p$). |
| **3. Free of Semantic Shifts?** | **No** | Shifts from physical/experimental measurement procedures in intended applications (L28–36) to undefined property-graph edge labels (`:MEASURED_BY`, `:DETERMINED_BY`, `:MEASURED_VIA`, `:LINKED_TO`) absent from the Episteme schema (L52–78). |
| **4. Valid & Scientifically Significant?** | **Yes (Foundational for Structuralism)** | Sneed's $T$-theoreticity partition ($L_T$ vs. $L_{NT}$) is the cornerstone of structuralist philosophy of science (`ISSUE-005`), required before Ramsey-Sneed empirical claims $\operatorname{Cn}(K)$ or Tenability (`tenability.md`) can be defined. |

---

## 1. Does the Metric Capture What It Claims It Does?

### TT-01 · Vacuous Universal Quantification Trap When $M(\tau) = \emptyset$ Inverts the $T$-Theoreticity Partition — **Critical**

**Where.** [`t_theoreticity.md#L52-L65`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L52-L65).

**Finding.**
Let $M(\tau) = \{p_1, p_2, \dots, p_k\}$ be the set of incoming `:MEASURED_BY` or `:DETERMINED_BY` pathways for term $\tau$. The Theoreticity Index is defined on L61 as:
$$TI(\tau, T) = \begin{cases} 1 & \text{if } \forall p \in M(\tau), \, \text{Laws}(T) \cap \text{Presupposes}(p) \neq \emptyset \\ 0 & \text{if } \exists p \in M(\tau) \text{ s.t. } \text{Laws}(T) \cap \text{Presupposes}(p) = \emptyset. \end{cases}$$

Consider what happens when $M(\tau) = \emptyset$ (i.e. node $\tau$ has $0$ incoming `:MEASURED_BY` / `:DETERMINED_BY` edges in the extracted graph):
1. In first-order logic, for the empty set $M(\tau) = \emptyset$, the universal condition $\forall p \in \emptyset \, (\text{Laws}(T) \cap \text{Presupposes}(p) \neq \emptyset)$ is **vacuously TRUE**, while the existential condition $\exists p \in \emptyset \, (\dots)$ is **FALSE**!
2. Therefore, **every term $\tau$ with $M(\tau) = \emptyset$ evaluates to $TI(\tau, T) = 1$ ($T$-theoretical, $\tau \in M_p \setminus M_{pp}$)**!
3. In real scientific and philosophical corpora, authors explicitly state how *derived theoretical quantities* (e.g., gravitational mass, entropy, utility) are determined from the theory's laws, but almost **never** write explicit measurement-apparatus derivation chains for primitive observational or pre-theoretical terms (e.g., *time*, *position*, *color*, *word count*, *promise*)!
4. Consequently, on any text-extracted `TheoryGraph`, all primitive observational terms have $M(\tau) = \emptyset$ and are classified as **$T$-theoretical** ($TI = 1$), leaving the non-theoretical empirical basis $M_{pp}$ empty! Conversely, genuinely unmeasurable metaphysical terms ($M(\tau) = \emptyset$) are also classified as valid $T$-theoretical constructs ($TI = 1$) instead of ungrounded terms.

**Fix.**
Require $M(\tau) \neq \emptyset$ for $TI(\tau, T) = 1$, and distinguish three epistemic states (or treat terms with $M(\tau) = \emptyset$ that are not constrained by $\text{Laws}(T)$ as pre-theoretical / unmeasured):
$$TI(\tau, T) = \begin{cases} 1 \quad (\text{$T$-Theoretical}) & \text{if } M(\tau) \neq \emptyset \land \forall m \in M(\tau), \, \text{Laws}(T) \cap \text{Presupposes}(m) \neq \emptyset \\ 0 \quad (\text{$T$-Non-Theoretical}) & \text{if } (\exists m \in M(\tau) : \text{Laws}(T) \cap \text{Presupposes}(m) = \emptyset) \lor \big(M(\tau) = \emptyset \land \tau \in \text{Voc}(M_{pp})\big) \\ \text{undefined / ungrounded} & \text{if } M(\tau) = \emptyset \land \tau \notin \text{Voc}(\text{Laws}(T)). \end{cases}$$

---

### TT-02 · Simple Graph Paths Confuse Conjunctive Law Presuppositions (AND) with Alternative Measurement Methods (OR) — **Critical**

**Where.** [`t_theoreticity.md#L52-L61`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L52-L61), [`#L76-L78`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L76-L78).

**Finding.**
On L52–57 and L76–78, each element $p_i \in M(\tau)$ is modeled as an incoming **dependency chain / path** in the graph (`:DETERMINED_BY` or `:MEASURED_VIA` edge sequence), and $\tau$ is declared $T$-non-theoretical ($TI = 0$) if **there exists at least one path $p \in M(\tau)$** such that $\text{Laws}(T) \cap \text{Presupposes}(p) = \emptyset$.

**Counterexample showing why simple paths break Sneed's criterion.**
Consider measuring **force** ($\tau = f$) in Classical Particle Mechanics ($T = \text{CPM}$) via a dynamical spring balance or collision experiment $m_1$.
To determine force $f$ in experiment $m_1$, the experimenter must measure spatial displacement $s$ using Euclidean optical geometry ($l_{\text{geom}} \in \text{Laws}(T^*)$, a pre-theory) **AND** apply Newton's second law ($l_{\text{Newton}} \in \text{Laws}(T)$) to convert displacement/acceleration into force:
$$l_{\text{geom}} \longrightarrow m_1 \longrightarrow f \qquad \text{and} \qquad l_{\text{Newton}} \longrightarrow m_1 \longrightarrow f.$$
In a standard directed graph, this single measurement procedure $m_1$ creates **two simple directed paths** terminating at $f$:
- Path $p_1 = (l_{\text{geom}} \to m_1 \to f)$, which traverses only $l_{\text{geom}} \in \text{Laws}(T^*)$, so $\text{Laws}(T) \cap V(p_1) = \emptyset$!
- Path $p_2 = (l_{\text{Newton}} \to m_1 \to f)$, which traverses $l_{\text{Newton}} \in \text{Laws}(T)$.

Because Path $p_1$ does not intersect $\text{Laws}(T)$, the path-based formula on L61 finds $\exists p_1 \in M(f)$ with $\text{Laws}(T) \cap \text{Presupposes}(p_1) = \emptyset$ and outputs:
$$TI(f, \text{CPM}) = 0 \quad (\text{CPM-non-theoretical!})$$
even though the measurement method $m_1$ **cannot determine $f$ without Newton's second law $l_{\text{Newton}} \in \text{Laws}(\text{CPM})$**!
Every measurement of a $T$-theoretical quantity relies *conjunctively* on both pre-theoretical observations ($M_{pp}$, e.g. positions/times from $T^*$) AND laws of $T$. In a simple graph, those pre-theoretical inputs form paths into $\tau$ that bypass $\text{Laws}(T)$, causing **every $T$-theoretical term in science to be misclassified as $TI(\tau, T) = 0$**!

**Fix.**
Model $M(\tau)$ as an **AND-OR dependency structure** (bipartite hypergraph):
- Let $M(\tau) = \{m_1, \dots, m_k\}$ be the set of distinct **measurement methods / determination rules** (OR-nodes) that output $\tau$.
- Each method $m_i \in M(\tau)$ conjunctively presupposes the **entire ancestor cone** (AND-set) of laws required by $m_i$:
  $$\text{Presupposes}(m_i) = \{ l \in \text{Laws}(G) \mid l \xrightarrow{+}_{\text{requires}} m_i \}.$$
- Then $TI(\tau, T) = 1$ iff $M(\tau) \neq \emptyset$ and for **every** measurement method $m_i \in M(\tau)$, its conjunctive prerequisite set intersects $\text{Laws}(T)$ ($\text{Laws}(T) \cap \text{Presupposes}(m_i) \neq \emptyset$).

---

### TT-03 · Contradiction with `glossary.md` and Misstatement of the Balzer–Gähde Invariance Criterion — **Major**

**Where.** [`t_theoreticity.md#L38-L46`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L38-L46) vs. [`docs/concepts/glossary.md#L28-L29`](../../../docs/concepts/glossary.md#L28-L29).

**Finding.**
1. **Direct Contradiction Between `t_theoreticity.md` and `glossary.md`:**
   - `t_theoreticity.md` (L40–41) defines the Balzer–Gähde Invariance Criterion as establishing when a term $\tau$ is **$T$-theoretical**:
     *"A term $\tau$ is formally **$T$-theoretical** if there exists a $T$-admissible measurement method invariant under $T$-compatible transformations ([Balzer et al., 1987, DII-9])."*
   - `docs/concepts/glossary.md` (L28–29) defines the exact same Balzer–Gähde Invariance Criterion as establishing when a term is **$T$-non-theoretical**:
     *"A formal structuralist criterion stating that a concept $t$ is **non-theoretical** with respect to a theory $T$ if it remains invariant under arbitrary theoretical modifications as long as the fundamental laws are preserved ([Balzer et al., 1987])."*
2. **Inaccurate Rendering of BMS (1987, DII-9, pp. 69–75) and Schurz (2014, p. 252):**
   In Balzer (1985), Gähde (1983), and BMS (1987, Ch. II, §4, DII-9), the formal criterion characterizes $T$-theoretical functions by the property that in designated subclasses of actual models $M(T)$, the $T$-non-theoretical functions uniquely determine the $T$-theoretical functions up to scale/invariance transformations preserving $M(T)$. Schurz (2014, p. 252) critiques this because any empirically deterministic law $y = f(x)$ between two purely observational variables $x, y$ also uniquely determines $y$ from $x$ within $M(T)$, which would falsely classify the observational variable $y$ as $T$-theoretical.

**Fix.**
Reconcile `t_theoreticity.md` (L40–46) and `docs/concepts/glossary.md` (L28–29) so both accurately state the BMS unique-determination/invariance criterion for $T$-theoreticity and Schurz's (2014, p. 252) counterexample.

---

## 2. Is the Metric Formally & Mathematically Correct?

### TT-04 · Structuralist Type Error: $\tau \in M_p \setminus M_{pp}$ and $\tau \in M_{pp}$ — **Major**

**Where.** [`t_theoreticity.md#L63-L64`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L63-L64), [`#L79-L80`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L79-L80), [`#L88-L89`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L88-L89) (cf. [`ISSUE-067` B-22](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md)).

**Finding.**
On L63–64, the specification writes:
- $TI(\tau, T) = 1 \implies \tau \in M_p \setminus M_{pp}$
- $TI(\tau, T) = 0 \implies \tau \in M_{pp}$

This commits two distinct set-theoretic type errors in structuralist metatheory (BMS 1987, Ch. I–II):
1. **Symbol vs. Model Structure:** $\tau$ is a *function or relation symbol* (a component slot in the signature $\Sigma$), whereas elements $x \in M_p$ and $y \in M_{pp}$ are *full model structures* (tuples of base sets and interpreted relations/functions $x = \langle D_1, \dots, D_k; n_1, \dots, n_m, t_1, \dots, t_r \rangle$). A function $\tau$ is never an element of $M_p$ or $M_{pp}$.
2. **Disjoint Tuple Arities ($M_{pp} \not\subseteq M_p$):** Because $M_{pp} = r(M_p)$ is obtained by applying the projection functor $r$ that strips the $r$ theoretical components from $(k+m+r)$-tuples to yield $(k+m)$-tuples, $M_{pp}$ is **not a subset** of $M_p$. Rather, $M_p \cap M_{pp} = \emptyset$ and $M_p \setminus M_{pp} = M_p$!

**Fix.**
Write $\tau \in \text{Voc}_T(K)$ (or $\tau \in \Sigma(M_p) \setminus \Sigma(M_{pp}) \equiv L_T$, the $T$-theoretical vocabulary) for $TI(\tau, T) = 1$, and $\tau \in \text{Voc}_{NT}(K)$ (or $\tau \in \Sigma(M_{pp}) \equiv L_{NT}$, the $T$-non-theoretical vocabulary) for $TI(\tau, T) = 0$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### TT-05 · Shift Between Physical Measurement Procedures and Unregistered Property-Graph Edge Labels — **Major**

**Where.** [`t_theoreticity.md#L28-L36`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L28-L36) $\to$ [`#L52-L57`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L52-L57) $\to$ [`#L69-L78`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L69-L78).

**Finding.**
1. Within `t_theoreticity.md` itself, the edge types change from section to section:
   - L53 uses `:MEASURED_BY` or `:DETERMINED_BY`
   - L69 uses `:LINKED_TO`
   - L76 uses `:DETERMINED_BY` or `:MEASURED_VIA`
   - L77 uses `:TheoryCore`
2. **None** of `:MEASURED_BY`, `:DETERMINED_BY`, `:MEASURED_VIA`, `:LINKED_TO`, or `:TheoryCore` exists in `epistemetrics/core/models.py` (`NodeType`, `RelationType`) or `episteme-pipeline`'s schema!
3. Furthermore, in humanities and philosophical corpora (`AGENTS.md` §1), concepts (e.g., *autonomy*, *categorical imperative*, *reflective equilibrium*) do not have physical measurement instruments (`:MEASURED_BY`). In those domains, the analogue of $T$-theoreticity is **definitional/explicative dependency**: whether a concept's semantic determination presupposes the axioms of the author's system $T$ (`RelationType.PRESUPPOSES` / `CONSTRAINS`), or whether it is taken from pre-theoretical discourse.

**Fix.**
Map the dependency traversal onto canonical `epistemetrics` types (`NodeType.CONCEPT`, `NodeType.AXIOM`, `NodeType.ACTUAL_MODEL`, `NodeType.PARTIAL_POTENTIAL_MODEL`, and `RelationType.PRESUPPOSES`, `RelationType.CONSTRAINS`, `RelationType.HAS_PARTIAL_POTENTIAL_MODEL`), or register `DETERMINED_BY` in `RelationType`.

---

## 4. Is the Metric Valid and Scientifically Significant?

### TT-06 · Fragility of Hard Boolean Quantification ($\forall$ vs. $\exists$) Under Noisy LLM Extraction — **Minor**

**Where.** [`t_theoreticity.md#L61`](../../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L61).

**Finding.**
Because $TI(\tau, T) \in \{0, 1\}$ flips from $1$ to $0$ if **even a single** pathway $m \in M(\tau)$ omits a link to $\text{Laws}(T)$, one noisy LLM extraction (or one incomplete chunk where the author mentions measuring $\tau$ without repeating the law $l \in \text{Laws}(T)$ used to calibrate the instrument) will misclassify a core $T$-theoretical concept as $T$-non-theoretical ($TI = 0$).

**Fix.**
Alongside the binary Sneedian classification $TI(\tau, T) \in \{0, 1\}$, define a continuous **Confidence-Weighted Theoreticity Degree** $\widetilde{TI}(\tau, T) \in [0, 1]$ measuring the confidence-weighted fraction of admissible determination methods $m \in M(\tau)$ that presuppose $\text{Laws}(T)$:
$$\widetilde{TI}(\tau, T) = \frac{\sum_{m \in M(\tau)} c(m) \cdot \mathbb{I}\big(\text{Laws}(T) \cap \text{Presupposes}(m) \neq \emptyset\big)}{\sum_{m \in M(\tau)} c(m)}.$$

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Symbol Collision on $\tau$ and $H$ (L11, L52):** Uses $\tau$ for a scientific term/function (which collides with QBAF justification degree $\tau(a)$ in `qbaf.py`) and $H$ for a "theory-holon" (L52, L69, which collides with hypothesis $H \in V_H$ in `higher_level_warrant.md` and `analogical_support.md`, and Harmony $H(t)$ in `system_coherence.md`).
2. **Unformatted Citation Brackets (L14):** `([Balzer et al., 1987, pp. 49–78, 391–393]; [Stegmüller, 1976, pp. 40–56]; [Schurz, 2024, pp. 251–252])` uses raw square brackets without Markdown link targets.
