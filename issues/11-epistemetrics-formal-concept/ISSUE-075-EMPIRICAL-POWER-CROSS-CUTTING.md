# [ISSUE-075] Cross-Cutting Evaluation: Pillar 3 Empirical Power Metrics (`empirical_power/*`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-075` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Cross-Cutting (Pillar 3: Empirical Power) |
| **Evaluated Docs** | [`empirical_adequacy.md`](../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md), [`empirical_content.md`](../../docs/concepts/theory/metrics/empirical_power/empirical_content.md), [`explanatory_breadth.md`](../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md), [`theoretical_achievements.md`](../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (the four metrics assume four incompatible graph models, duplicate overlap with other pillars, and leave `epistemetrics` without an executable Pillar 3 implementation) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-071`](empirical_power/ISSUE-071-EMPIRICAL-ADEQUACY.md), [`ISSUE-072`](empirical_power/ISSUE-072-EMPIRICAL-CONTENT.md), [`ISSUE-073`](empirical_power/ISSUE-073-EXPLANATORY-BREADTH.md), [`ISSUE-074`](empirical_power/ISSUE-074-THEORETICAL-ACHIEVEMENTS.md), [`ISSUE-066`](../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md), [`ISSUE-069`](../10-formal-conceptual-docs/ISSUE-069-philosophical-errors.md) |

Severity legend: **Critical** = invalidates the metric suite's architectural/mathematical coherence · **Major** = significant cross-file conflict, redundancy, or domain mismatch · **Minor** = notation, alignment, or presentation issue.

---

## 1. Four Metrics, Four Incompatible Underlying Graph Formalisms — **Critical**

**Where.** Across all four files in `docs/concepts/theory/metrics/empirical_power/`.

**Finding.**
Although all four metrics belong to **Pillar 3: Empirical Power** and are intended to evaluate the same `TheoryGraph` produced by `episteme-pipeline` and analyzed by `epistemetrics`, each document defines its own incompatible mathematical graph formalism:

| Metric Document | Assumed Graph Formalism | Representation of "Theory" | Representation of "Empirical Data" |
| :--- | :--- | :--- | :--- |
| **`empirical_adequacy.md`** | Structuralist metric space $(\mathcal{M}_{pp}, d)$ + Neo4j property graph (`:TheoryElement`, `:Application`, `:Dataset`, `:ErrorMargin`) | Theory-element $T = \langle K, I \rangle$ with model sets $X \in \operatorname{Cn}(K)$ | Intended applications $i \in I \subseteq M_{pp}$ evidenced by `:Dataset` nodes |
| **`empirical_content.md`** | Attributed Hypergraph $H = (V_T \uplus V_O, E, P)$ with $E \subseteq \mathcal{P}(V) \setminus \{\emptyset\}$ + causal DAG ($d$-separation) | Theoretical node partition $V_T$ (cardinality $k_T = \|V_T\|$) generating core $K$ | Empirical nodes $v \in V_O$ with syntactic class $S_v$ & inferential distance $d_v$, quotiented by $\sim_{\text{eq}}$ |
| **`explanatory_breadth.md`** | Directed Bipartite Knowledge/Coherence Graph $G = (V_H \cup V_E, R_{\text{sup}} \cup \mathcal{R}_{\text{att}})$ + Leiden partition $\mathcal{C}$ | Set of hypothesis nodes $V_H(T) \subseteq V_H$ | Established evidence nodes $E \in V_E$ with directed edges $E \to H$ |
| **`theoretical_achievements.md`** | Application Subgraphs $G_{A_1}, \dots, G_{A_m}$ bridged by theoretical concept node $\tau$ via constraint relations $C$ | Individual theoretical term/concept node $\tau$ | State space $\text{PermissibleStates}(M_{pp})$ and domain observations $Obs(D_j)$ |

**Why this is a critical blocker for `epistemetrics`.**
In `packages/epistemetrics/src/epistemetrics/core/models.py` and `graph/theory_graph.py`, a `TheoryGraph` is a **single directed multigraph** $(V, E)$ with typed `TheoryNode` (`NodeType`) and `TheoryEdge` (`RelationType`). Because the four Pillar 3 specifications do not share a common formal signature $(V, E, \lambda_v, \lambda_e)$:
1. An empirical fact is simultaneously an `:Application` / `:Dataset` (`empirical_adequacy.md`), a hypergraph vertex $v \in V_O$ inside forbidden hyperedges $e \in \mathcal{P}(V_O)$ (`empirical_content.md`), an evidence node $E \in V_E$ with outgoing support edges $E \to H$ (`explanatory_breadth.md`), and a domain observation $Obs(D_j) \subseteq M_{pp}$ (`theoretical_achievements.md`).
2. Currently, **none of the four Pillar 3 metrics is implemented as a runtime evaluator in `packages/epistemetrics/`** (which only implements `model_evaluation.py` for gold-reference comparison, `poset_evaluation.py`, `reduction_evaluation.py`, `dynamics.py`, and `qbaf.py`).

**Fix.**
Establish a **Unified Pillar 3 Graph Signature** over `TheoryGraph` before implementing the evaluators in `epistemetrics`:
- Partition L3 propositional nodes into $V_H$ (`AXIOM`, `HYPOTHESIS`, `THEOREM`, `CLAIM`) and $V_E$ (`EVIDENCE`, `OBSERVATION`, `PHENOMENON`, `PARADIGM`), with L2/L3 theoretical concepts $V_{\tau}$ (`CONCEPT`, `THEORETICAL_TERM`) linked to $V_H \cup V_E$, and domain/application clusters $\mathcal{D} = \{D_1, \dots, D_m\}$ partitioning $V_E$.
- Express all four Pillar 3 metrics as functions of this single tuple $\mathcal{G} = (V_H, V_E, V_\tau, R_{\text{sup}}, R_{\text{att}}, R_{\text{const}}, \mathcal{D})$.

---

## 2. Unacknowledged Overlap and Contradictions Between Pillar 3 Metrics and Other Pillars — **Major**

**Where.** `empirical_power/*` vs. `epistemic_coherence/tenability.md`, `epistemic_coherence/elegance_and_economy.md`, `theory_dynamics/degeneration_index.md`, and `metatheoretical/unification.md`.

**Finding.**
While `docs/concepts/theory/metrics/index.md` (§Metric Overlap, Redundancy, & Consolidation Analysis, L126–170) documents several overlaps, **three major cross-pillar conflicts inside `empirical_power/` are omitted or mischaracterized**:

1. **`empirical_adequacy.md` $\leftrightarrow$ `tenability.md` (Pillar 2):**
   - Both formalize $I \in \operatorname{Cn}(K)$ under admissible blurs $\mathcal{A}$ in uniform spaces (Stegmüller 1976; BMS 1987).
   - `tenability.md` is already implemented in `post_processing/theoretical_enrichment/` (ADR 0015) using uniformities $u_\delta$ and explicitly rejects a metric distance $d(i, x)$.
   - `empirical_adequacy.md` re-defines the same concept using a metric distance $d(i, x)$ and misstates what `tenability.md` computes (see [`ISSUE-071` EA-09](empirical_power/ISSUE-071-EMPIRICAL-ADEQUACY.md)).
2. **Parsimony Regularizer $\text{DoF}_w = \exp(-\lambda k_T / M_w)$ in `empirical_content.md` $\leftrightarrow$ `unification.md` (Pillar 5) & `elegance_and_economy.md` (Pillar 2):**
   - In `empirical_content.md` (L139), $\frac{k_T}{M_w}$ is the ratio of theoretical constructs/postulates ($k_T$) to independent empirical mass ($M_w$).
   - This is the exact inverse of the **Schurz Unification Ratio** $U_{\text{ratio}} = \frac{|D|}{|B|}$ (`unification.md`) and directly duplicates the **Axiom Parsimony Score ($APS$)** and **MDL** ($L(M) + L(D \mid M)$) in `elegance_and_economy.md`.
   - Baking an exponential parsimony penalty directly into `Effective Empirical Content (EEC)` conflates **empirical content** (how much a theory forbids) with **parsimony/unification** (how compactly it is axiomatized). Under Popper's and Schurz's definitions, conjoining an independent testable law *increases* empirical content even though it increases $k_T$; penalizing $k_T$ inside EEC means a comprehensive 10-axiom physics textbook can score lower in "Empirical Content" than a 1-axiom toy hypothesis!
3. **Lakatos Delta ($\Delta_{\text{EEC}}$) in `empirical_content.md` $\leftrightarrow$ `degeneration_index.md` (Pillar 4):**
   - `empirical_content.md` (L141–152) defines $\Delta_{\text{EEC}} = \text{EEC}(K_{\text{core}}) - \text{EEC}(K_{\text{core}} \cup \{B'\})$ to measure ad-hoc immunization.
   - `degeneration_index.md` (L38–40) and `packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py` already define the **Node-Level Immunization Index ($II$)** and **Degeneration Index ($D$ / $DI$)** using a different formula. Neither document cross-references the other.
4. **Empirical Focus Index ($EFI$) in `theoretical_achievements.md` $\leftrightarrow$ Relative Restriction Grammar ($\Gamma_{\text{relative}}$) in `empirical_content.md`:**
   - Both measure the fraction of observable state space excluded by theoretical constraints ($1 - \frac{|\text{Permissible}|}{|\text{Total}|}$ vs. $\frac{\sum_{E_{\text{forbidden}}} W(e)}{\sum_{E_{\text{local}}} W(e)}$), one at the term level ($\tau$) and one at the theory level ($K$), without noting their mathematical duality:
     $$\text{ForbiddenFraction} = 1 - \text{PermissibleFraction}.$$

**Fix.**
1. Document these four mathematical relationships explicitly in `docs/concepts/theory/metrics/index.md` (§Comprehensive Overlap & Redundancy Map).
2. Report both **unregularized Empirical Content** ($\Gamma_{\text{relative}}(K)$) and **Parsimony-Regularized Effective Empirical Content** ($\text{EEC}(K)$) so that empirical falsifiability and axiomatic parsimony are not confounded in downstream Pareto-frontier analyses (`ISSUE-007`, `ISSUE-030`).
3. Express $EFI(\tau)$ in `theoretical_achievements.md` as the **marginal $\Gamma_{\text{relative}}$ contribution** (or constraint overdetermination ratio) of term $\tau$: $\Delta \Gamma_{\text{relative}}(\tau) = \Gamma_{\text{relative}}(K) - \Gamma_{\text{relative}}(K \setminus \{\tau\})$.

---

## 3. Domain Applicability Crisis: Positivist Collapse on Philosophical & Normative Corpora — **Major**

**Where.** All four files in `docs/concepts/theory/metrics/empirical_power/` (cf. [`ISSUE-069` D-01](../10-formal-conceptual-docs/ISSUE-069-philosophical-errors.md)).

**Finding.**
Episteme's primary target domain is **German and English scientific and philosophical literature** (`AGENTS.md` §1).
Across all four Pillar 3 metrics, any theory lacking physical measurements, laboratory datasets, or sensory observations is diagnosed with pejorative metascientific labels:
- `empirical_adequacy.md` (L81): $GR = 0 \implies$ **"Pure Formal Speculation"**
- `empirical_content.md` (L75, L166, L190): $d_v \to \infty$ (no direct physical instrumentation) $\implies R_v = e^{-\beta d_v} \to 0 \implies M_w \to 0 \implies \text{EEC} \to 0 \implies$ **"Degenerative/Pseudoscience"** / **"Metaphysical speculation"**
- `explanatory_breadth.md` (L114): $REB < 0.1 \implies$ **"Isolated / Cherry-Picking"**
- `theoretical_achievements.md` (L67): $TAS < 0.2 \implies$ **"Idle Term / Surplus Baggage"**

If a scholar runs Episteme on Kant's *Critique of Pure Reason*, Rawls's *A Theory of Justice*, or formal logic/mathematics:
- There are no physical instruments or `:Dataset` nodes, so $R_v \to 0$, $GR = 0$, and $TAS = 0$.
- The workbench will classify Kantian ethics or Rawlsian justice as **"Degenerative/Pseudoscience"**, **"Pure Formal Speculation"**, and **"Surplus Baggage"**.

**Fix.**
Generalize the **Evidential Base ($V_E / I$)** by corpus regime:
1. **Empirical Science Mode:** $V_E$ = physical observations, experimental measurements, datasets.
2. **Philosophical / Normative / Analytic Mode (Reflective Equilibrium):** $V_E$ = considered judgments, intuitive case verdicts, textual/exegetical anchor phenomena, or lower-level theorems explained by the axiomatic system (Goodman 1955; Rawls 1971; Daniels 1979).
3. Replace positivist diagnostic labels ("Degenerative/Pseudoscience" for $\text{EEC} \to 0$) with neutral descriptive diagnostics (e.g., *"Low Empirical Restriction / Non-Empirical Formal or Normative System"* when $V_E^{\text{physical}} = \emptyset$, reserving *"Degenerative / Overfitted"* for theories that *claim* an empirical domain $I \neq \emptyset$ yet fail $k_T \ll M_w$ or $\Gamma_{\text{relative}} > 0$).

---

## 4. Non-Threatening Cross-File Inconsistencies & Notation Misalignments

The following inconsistencies do not threaten the core mathematical integrity of individual metrics on their own, but should be standardized across `docs/concepts/theory/metrics/empirical_power/` and `index.md`:

| Issue | Locations | Details & Recommended Standardization |
| :--- | :--- | :--- |
| **1. Four Different Symbols for Empirical Observations** | `empirical_adequacy.md` ($I, i \in I \subseteq M_{pp}$)<br>`empirical_content.md` ($V_O, v \in V_O$)<br>`explanatory_breadth.md` ($V_E, E \in V_E$)<br>`theoretical_achievements.md` ($Obs(D_j), G_{A_k}$) | Standardize on $V_E$ (or $B$) for statement-view observation nodes and $I \subseteq M_{pp}$ for structuralist model-theoretic intended applications, with an explicit bridge mapping between them. |
| **2. Four Different Symbols for Theoretical Claims / Core** | `empirical_adequacy.md` ($K, X \in \operatorname{Cn}(K)$)<br>`empirical_content.md` ($V_T, k_T = \|V_T\|, K$)<br>`explanatory_breadth.md` ($V_H(T), H \in V_H$)<br>`theoretical_achievements.md` ($\tau$, constraints $C$) | Distinguish clearly between **propositional hypotheses/axioms** $V_H$ (statement view), **theoretical terms/concepts** $V_\tau$ (vocabulary $L_T$), and the **model-theoretic core** $K = \langle M_p, M, M_{pp}, GC, GL \rangle$. |
| **3. Broken Zotero URI Schemes in Published Docs** | `empirical_adequacy.md` (L11)<br>`explanatory_breadth.md` (L13)<br>`theoretical_achievements.md` (L13) | Contains local desktop links `zotero://select/library/items/24SNSW2B`, `zotero://select/library/items/2WXH9HSL`, `zotero://select/library/items/8F6MW586` that do not resolve for external readers and map two different authors (Balzer et al. 1987 and Schurz 2024) to the **exact same Zotero item key** `24SNSW2B`! Replace with standard anchors to `#grounding-references` or DOIs. |
| **4. Schurz Publication Year Drift (2014 vs. 2024 vs. 2026)** | `glossary.md` (Schurz 2014)<br>`empirical_power/*` (Schurz 2024)<br>`index.md` (Schurz 2014 / 2024 / 2026) | Standardize the edition cited (Routledge 2014 is the 1st English edition of *Philosophy of Science: A Unified Approach*; verify if 2024 refers to a reprint or 2nd edition). |
| **5. Template & Frontmatter Divergence** | All 4 files in `empirical_power/` | Standardize the 6-section template across all 4 files (`Definition & Conceptual Goal`, `Theoretical Grounding & Model Formulation`, `Mathematical Specification & Graph Formulation`, `Measurement & Graph Implementation`, `Diagnostic & Metascientific Value`, `Grounding References`). |
