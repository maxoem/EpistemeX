# [ISSUE-094] Formal & Conceptual Evaluation: Tenability (`tenability.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-094` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 2: Epistemic Coherence & Parsimony |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/epistemic_coherence/tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md) |
| **Target Package(s)** | `episteme-pipeline` (`post_processing/theoretical_enrichment/solvers.py`, `runner.py`), `epistemetrics` |
| **Priority** | **Critical** (decouples pointwise law optimization from global constraint satisfaction, awards a perfect $1.0$ score to empty parameter sets / lawless theories / edgeless clusters in `solvers.py`, subtracts unaligned parameters across incompatible domains via `zip()` when `shared_keys` is empty, and contradicts `formal_graph_model.md` and `empirical_adequacy.md`) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-071`](../empirical_power/ISSUE-071-EMPIRICAL-ADEQUACY.md), [`ISSUE-095`](../ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-004`](../../02-structuralist-engine/ISSUE-004-interactive-tenability-blur-slider.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially (Broken Optimization & Vacuous Defaults)** | Claims to evaluate the Sneed-Stegmüller empirical claim $I \in \operatorname{Cn}(K)$ by optimizing theoretical parameter enrichments $\Phi(y)$ to simultaneously satisfy local laws $M$, global constraints $GC$, and links $GL$ under uniform-space blurs $\mathcal{A}$. In reality: (1) $\Phi(y)$ is fixed *a priori* by an LLM prompt without optimizing over $M$ or $GC$; (2) $TS_{\text{local}}$ and $TS_{\text{edge}}$ are evaluated separately rather than jointly; and (3) `solvers.py` awards a **perfect $1.0$ score** whenever `parameters == {}`, `laws == []`, or `edge_scores == {}`! |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) Division by zero in $\text{Tenability}(T)$ (L180) when $\|I\| = 0$ or $\|E_{GC}\| = 0$; (2) Indexing entourages $u_\delta$ by a single scalar $\delta \in [0, 1]$ reduces the uniform space to a single pseudo-metric ($\ell_\infty$ norm in `solvers.py`), contradicting §The Topology of Uniform Spaces vs. Metric Spaces (L73–86); (3) When two theories share no parameter names (`not shared_keys`), `solvers.py` (L254–260) zips arbitrary parameter values by dictionary order and subtracts them! |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts from (a) Bourbaki non-metrizable uniformities $U$ over set-theoretic models $M_p$ (L73–86) to (b) scalar $[0, 1]$ parameter dictionaries evaluated by AST arithmetic (`SafeFormulaEvaluator`) on Phase 1 text chunks (`cluster-{chunk_id}` in `runner.py` L508), and contradicts the definition of *Tenability* in `formal_graph_model.md` (L334) and `empirical_adequacy.md` (L18). |
| **4. Valid & Scientifically Significant?** | **Scientifically Central, Needs Solver & Boundary Fixes** | Sneedian/Stegmüllerian approximative empirical claims under admissible blurs are a cornerstone of Episteme (ADR 0015), but must be reconciled with `empirical_adequacy.md` (`ISSUE-071`) and fixed in `solvers.py` / `runner.py`. |

---

## 1. Does the Metric Capture What It Claims It Does?

### TN-01 · Vacuous Perfection Trap: Empty Parameter Projections, Lawless Theories, and Edgeless Clusters Score $\text{Tenability} = 1.0$ — **Critical**

**Where.** [`tenability.md#L130`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L130), [`#L153-L155`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L153-L155), [`#L180`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L180) and [`packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L75-L81`](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L75-L81), [`#L192-L193`](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L192-L193), [`#L300-L304`](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L300-L304).

**Finding.**
In `tenability.md` (L153–155 & L209), a failure to enrich an empirical domain with valid theoretical parameters or a domain mismatch (category error) must drop the tenability score to $0.0$ ($< 0.5$, **"Category Error / Untenable"**).
However, in the mathematical specification and its reference implementation `TenabilitySolver` (`solvers.py`), three boundary defects invert this behavior and award **$\text{Tenability} = 1.0$ ("High Tenability")** to completely unenriched or vacuous inputs:
1. **Unprojected / Missing Parameters Default to `0.0`, Satisfying Homogeneous Laws (`solvers.py` L75–81):**
   In `SafeFormulaEvaluator._eval_node` (L75–81), any parameter name in a law formula (e.g., `"abs(Force - Mass * Acceleration)"` from `docs/reference/theoretical_enrichment.md` L109) that is missing from `parameters` evaluates to **`0.0`**.
   Consequently, if an empirical cluster is a complete category error (e.g. a passage on Kantian ethics evaluated under Classical Mechanics, yielding `parameters = {}`), `SafeFormulaEvaluator` computes:
   $$\text{abs}(0.0 - 0.0 \times 0.0) = 0.0 \implies \delta^* = 0.0 \implies TS_{\text{local}} = 1.0!$$
2. **Lawless Theories Return $TS_{\text{local}} = 1.0$ (`solvers.py` L192–193):**
   If `LLMTheoryInducer` induces a theory with no valid law expressions (`not theory.laws`), `solve_local_tenability` returns `1.0, 0.0, []`.
3. **Missing Constraint Edges Return $\overline{TS}_{\text{edge}} = 1.0$ (`tenability.md` L180 vs. `solvers.py` L254–261, L300–304):**
   - In `tenability.md` L180, $\frac{1}{|E_{GC}|} \sum_{e \in E_{GC}} TS_{\text{edge}}(e)$ **divides by zero** when $|E_{GC}| = 0$ (or when $|I| = 0$).
   - In `solvers.py` L261, if `deltas` is empty (because neither `source_params` nor `target_params` has numeric values), `delta_c = 0.0` and `ts_edge = 1.0`.
   - In `solvers.py` L300–304, if `edge_scores` is empty (`|E_{GC}| = 0`), `avg_edge` defaults to `1.0`.
   Thus, an empty parameter dict `{}` with zero constraint edges receives `local_score = 1.0`, `avg_edge = 1.0`, and `aggregated_score = 1.0` (`is_tenable = True`)!

**Fix.**
1. In `tenability.md` (L130, L180), explicitly specify the boundary guards:
   - If $\text{dom}(\Phi(y)) \not\supseteq \text{vars}(M)$ (required theoretical parameters cannot be projected for application $y$), then $\Phi(y)$ fails theoretical enrichment and $TS_{\text{local}}(y, M) := 0.0$.
   - If $|I| = 0$, $\text{Tenability}(T) := 0.0$.
   - If $|E_{GC}| = 0$, re-normalize the weight onto $TS_{\text{local}}$ ($\text{Tenability}(T) = \frac{1}{|I|}\sum_{y \in I} TS_{\text{local}}(y, M)$) rather than hallucinating a perfect constraint score `avg_edge = 1.0`.
2. In `solvers.py` (`SafeFormulaEvaluator` and `TenabilitySolver`), verify that all `law.involved_parameters` are present as numeric values in `parameters` before evaluating `law.formula_expression`; if any required parameter is missing, record an anomaly and set `dev = theory.max_admissible_blur` ($TS_{\text{local}} = 0.0$).

---

### TN-02 · Decoupled Pointwise Evaluation Violates the Joint Sneed–Ramsey Empirical Claim $I \in \operatorname{Cn}(K)$ — **Critical**

**Where.** [`tenability.md#L41-L46`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L41-L46) vs. [`#L125-L183`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L125-L183).

**Finding.**
1. **No Optimization Over Enrichments in $TS_{\text{local}}(y, M)$ (L130 vs. L134–151):**
   In §Rationale for the Supremum over Blurs (L134–145), the document explains that theoretical parameters are estimated post-factum via an optimization problem (analogous to least squares, Stegmüller 1976, p. 61).
   However, in the formula on L130:
   $$TS_{\text{local}}(y, M) = \sup \{ 1 - \delta \mid \exists x^* \in M : (\Phi(y), x^*) \in u_\delta \}$$
   the enrichment $\Phi(y) \in M_p$ is **already fixed** to a single point before the $\sup$ is taken! And in `runner.py` (L288–290) and `solvers.py` (L198–208), `LLMTheoryProjector.aproject(cluster, theory)` guesses a single dictionary `projected_params` without solving any optimization problem over the non-theoretical fiber $r^{-1}(y) \subseteq M_p$, and `solve_local_tenability` simply plugs `projected_params` directly into `law.compute_deviation(projected_params)` (never even searching for the closest model $x^* \in M$!).
2. **Decoupling of $TS_{\text{local}}$ ($M$) from $TS_{\text{edge}}$ ($GC$):**
   In structuralism (Stegmüller 1976, pp. 78, 94; Balzer et al. 1987, p. 91), the Ramsey-Sneed empirical claim $I \in \operatorname{Cn}(K)$ requires that **the same** theoretical enrichment $X = \{x_y\}_{y \in I} \subseteq M_p$ (with $r(x_y) = y$) satisfies **both** $x_y \in M$ (up to blur) **and** $X \in GC \cap GL$.
   In L130 and L165, however:
   - $TS_{\text{local}}(y_a, M)$ allows $\Phi(y_a)$ to be approximated by an arbitrary witness $x_a^* \in M$,
   - while $TS_{\text{edge}}(e)$ evaluates $(\Phi(y_a), \Phi(y_b)) \in v_{\delta_C}$ on the **un-adjusted** $\Phi(y_a), \Phi(y_b)$ rather than requiring $(x_a^*, x_b^*) \in v_{\delta_C}$!
   Thus, $\Phi(y_a) = \Phi(y_b)$ can satisfy the equality constraint $GC$ perfectly ($TS_{\text{edge}} = 1.0$) only because both are far from $M$, or $x_a^*, x_b^* \in M$ can be chosen close to $\Phi(y_a), \Phi(y_b)$ only by violating $(x_a^*, x_b^*) \in GC$.

**Fix.**
Formulate the joint tenability optimization over the enriched model assignment $\mathbf{x} = (x_y)_{y \in I} \in \prod_{y \in I} U_\delta(r^{-1}(y))$:
$$\text{Tenability}(T) = \sup_{\mathbf{x} \in M_p^I} \left[ w_{\text{local}} \cdot \frac{1}{|I|} \sum_{y \in I} \big(1 - \delta_M(x_y, y)\big) + w_{\text{edge}} \cdot \frac{1}{|E_{GC}|} \sum_{(y_a, y_b) \in E_{GC}} \big(1 - \delta_{GC}(x_{y_a}, x_{y_b})\big) \right]$$
where the same parameter assignment $x_y = \Phi(y)$ is evaluated in both the law residual $\delta_M(x_y) = \max_{l \in M} \text{dev}_l(x_y)$ and the constraint residual $\delta_{GC}(x_{y_a}, x_{y_b})$.

---

## 2. Is the Metric Formally & Mathematically Correct?

### TN-03 · Cross-Dimensional Parameter Subtraction Bug in `solvers.py` (`not shared_keys`) Violates Uniform-Space Invariance — **Critical**

**Where.** [`tenability.md#L73-L86`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L73-L86), [`#L157-L165`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L157-L165) vs. [`packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L246-L260`](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L246-L260).

**Finding.**
1. **Cross-Dimensional Subtraction in `solvers.py` (L254–260):**
   In `tenability.md` (L77–81) and ADR 0015 (L54), the primary justification for Bourbaki uniform spaces is that *"scientific theories routinely deal with heterogeneous physical quantities... There is no single, natural, universal metric distance function $d(x, y)$ that can combine these different dimensions"*.
   Yet in `TenabilitySolver.solve_edge_tenability` (`solvers.py` L254–260), when two clusters or two theories linked by an intertheoretical edge have **no shared parameter names** (`not shared_keys`, e.g., Neurology with `{"DopamineDepletion": 0.8, "AmygdalaHyperactivity": 0.2}` and Psychoanalysis with `{"RepressionMagnitude": 0.3, "UnconsciousResistance": 0.9}` as in ADR 0015 L27–29):
   ```python
   if not shared_keys:
       num_source = [float(v) for v in source_params.values() if isinstance(v, (int, float))]
       num_target = [float(v) for v in target_params.values() if isinstance(v, (int, float))]
       if num_source and num_target:
           for s, t in zip(num_source, num_target):
               deltas.append(abs(s - t))
   ```
   The solver iterates over the two disjoint dictionaries in **insertion order** via `zip()` and subtracts unrelated parameters across incompatible ontologies (e.g., `abs(DopamineDepletion - RepressionMagnitude)` and `abs(AmygdalaHyperactivity - UnconsciousResistance)`)! Reordering the keys in either dictionary changes the computed `TS_edge` score!
2. **Scalar Blur Parameter $\delta \in [0, 1]$ Collapses Uniform Space to a Pseudo-Metric (L130, L165):**
   Although L75–86 rejects metric distances in favor of a uniformity $U$, L130 and L165 parameterize the entourages $u_\delta \in \mathcal{A}$ by a single scalar $\delta \in [0, 1]$ and maximize $1 - \delta$. By the Birkhoff–Kakutani theorem, a nested 1-parameter family of entourages $\{u_\delta\}_{\delta \in [0, 1]}$ is simply the $\delta$-ball family of the pseudo-metric $d(x, x') = \inf\{\delta \mid (x, x') \in u_\delta\}$ (which `solvers.py` L207 implements as the $\ell_\infty$ max-deviation over $[0, 1]$-normalized parameters). The prose on L75–86 should clarify that uniform spaces are rendered computationally tractable by normalizing each theoretical dimension into a dimensionless $[0, 1]$ blur coordinate and taking the product-uniformity supremum ($\ell_\infty$ entourage $u_\delta = \{(x, x') \mid \forall k : |x_k - x'_k| / \sigma_k \le \delta\}$).

**Fix.**
In `solvers.py` (`solve_edge_tenability`), **remove the `if not shared_keys: zip(num_source, num_target)` block**. For intertheoretical links ($GL$) between theories with distinct parameter vocabularies, evaluate an explicit link-constraint expression $GL(x_a, x_b)$ if defined on the relation/registry; if no shared keys and no intertheoretical link law exist, return `ts_edge = 0.0` (for `CONSTRAINS` / `EQUIVALENT_TO` edges requiring shared parameters) or skip unconnected parameter pairs.

---

### TN-04 · Propagated Tenability Formula $\text{Tenability}_{\text{pred}}(y_b) = TS_{\text{local}}(y_a, M) \cdot TS_{\text{edge}}(e)$ Is Unused and Path-Dependent — **Minor**

**Where.** [`tenability.md#L167-L174`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L167-L174).

**Finding.**
L167–174 defines `Propagated Tenability`:
$$\text{Tenability}_{\text{pred}}(y_b) = TS_{\text{local}}(y_a, M) \cdot TS_{\text{edge}}(e)$$
1. If $y_b$ is connected via constraint edges $e_1 = (y_{a_1}, y_b)$ and $e_2 = (y_{a_2}, y_b)$ to multiple source nodes $y_{a_1}, y_{a_2}$, the formula does not specify whether $\text{Tenability}_{\text{pred}}(y_b)$ takes the $\max$, $\min$, or mean over incoming constraint edges.
2. This formula is never used in $\text{Tenability}(T)$ (L180), in the 5-step workflow (L187–200), or in `solvers.py`.

**Fix.**
Define $\text{Tenability}_{\text{pred}}(y_b) = \max_{e=(y_a, y_b) \in E_{GC}} \big(TS_{\text{local}}(y_a, M) \cdot TS_{\text{edge}}(e)\big)$ (or $\min$ when multiple constraints jointly bind $y_b$) and clarify its role as a predictive diagnostic for unmeasured application nodes $y_b \in A(I)$ (`progressiveness.md`).

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### TN-05 · Chunk-Grouping Bug & Partition-`A` Target Inversion in `TheoreticalEnrichmentRunner` (`runner.py`) — **Major**

**Where.** [`tenability.md#L37-L39`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L37-L39), [`#L92-L94`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L92-L94) vs. [`packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py#L420-L426`](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py#L420-L426), [`#L478-L520`](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py#L478-L520) (cf. [`ISSUE-064`](../../09-architecture-workflow-domain/resolved/ISSUE-064-phase4-to-postprocessing-domain-bugs-and-hardcoded-heuristics.md)).

**Finding.**
1. **Intended Applications $I \subseteq M_{pp}$ Shifted to Raw Phase 1 Text Chunks (`source_chunk_id`):**
   `tenability.md` (L37–39, L92) defines an intended application $y \in I \subseteq M_{pp}$ as an empirical observation subsystem in Partition $B$.
   In `runner.py` (`_identify_empirical_clusters`, L495–518), however, clusters are formed simply by grouping **all** `TheoryAtom` nodes (both Partition $A$ and Partition $B$) by `atom.source_chunk_id` (`cluster-{chunk_id}`). A Phase 1 token chunk is an arbitrary 500-token pagination slice of a document, not a coherent empirical application domain $I_k \subseteq M_{pp}$!
2. **Tenability Scores Attached to Partition $A$ Instead of Partition $B$, and Overwritten Across Claimant Theories (`runner.py` L421–426):**
   - In `tenability.md` (L127–130), $TS_{\text{local}}(y, M)$ is a property of the empirical application node $y \in I \subseteq B$.
   - In `runner.py` (L421–426), the runner only updates nodes where `self.schema.component_partitions.get(obs.component_type) == "A"` (Theoretical Hypotheses), ignoring all Partition-$B$ empirical observation nodes! If a chunk contains only observation nodes ($B$), `atoms_to_update` is empty.
   - Worse, because the loop `for theory_id in cluster.claimant_theory_ids:` (L353) mutates and appends `obs_updated` for every claimant theory, each hypothesis node's `obs_updated.tenability` is overwritten by whichever claimant theory happens to run last in the loop!

**Fix.**
Group empirical observation nodes ($B$) by semantic/topological application cluster (e.g. connected components or Leiden communities of $B$-nodes linked to a `TheoryElement` / `TheoreticalHypothesis`), attach $(theory\_id \mapsto \text{TenabilityResult})$ on both the application cluster and the claiming hypothesis without overwriting multi-theory evaluations, and persist the scores into `TheoryGraph` attributes so `epistemetrics` (`progressiveness.md` $PTM$) can consume them.

---

### TN-06 · Three-Way Contradiction in the Definition of "Tenability" Across `tenability.md`, `formal_graph_model.md`, and `empirical_adequacy.md` — **Major**

**Where.** [`tenability.md#L14-L28`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L14-L28) vs. [`formal_graph_model.md#L334-L341`](../../../docs/concepts/formal_graph_model.md#L334-L341) and [`empirical_adequacy.md#L18-L19`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L18-L19) (cf. [`ISSUE-067` B-25](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md), [`ISSUE-071` EA-09](../empirical_power/ISSUE-071-EMPIRICAL-ADEQUACY.md)).

**Finding.**
1. **`formal_graph_model.md` (L334–337):** Defines **Tenability (*Haltbarkeit*)** as the purely definitional vocabulary condition $I \subseteq M_{pp}$, and defines **Approximative Empirical Adequacy (*Adäquatheit*)** (L338–341) as the uniform-space blur condition.
2. **`empirical_adequacy.md` (L18–19):** Claims Tenability only checks $I \subseteq M_{pp}$, and then re-defines the uniform-space blur optimization as Adequacy Score ($AS$) and $BMCR$.
3. **`tenability.md` (L14–28, L43, L130–180):** Defines **Tenability (*Haltbarkeit*)** as the full uniform-space blur optimization $I \in \operatorname{Cn}(K)$ over $M$, $GC$, and $GL$ (which matches Stegmüller 1976, pp. 120, 270: *Haltbarkeit der empirischen Behauptung*).

**Fix.**
Align `formal_graph_model.md` (L334–341) and `empirical_adequacy.md` with `tenability.md` (see [`ISSUE-071` EA-09](../empirical_power/ISSUE-071-EMPIRICAL-ADEQUACY.md)): reserve **Tenability (*Haltbarkeit*)** for the structuralist enrichment & blur-satisfaction metric in `tenability.md` (ADR 0015), and restrict `empirical_adequacy.md` to Layer 3 evidentiary grounding ($GR$) or merge the two specifications.

---

## 4. Is the Metric Valid and Scientifically Significant?

### TN-07 · Applicability to Non-Parametric / Philosophical Corpora ($\Phi_{\text{gen}}$ vs. $\Phi_{\text{spec}}$) — **Minor**

**Where.** [`tenability.md#L96-L118`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L96-L118).

**Finding.**
The dual-enrichment architecture $\Phi(y) = \Phi_{\text{spec}}(\Phi_{\text{gen}}(y))$ (L100–118) thoughtfully notes that $\Phi_{\text{gen}}$ captures topological, causal, and monotonic relations while $\Phi_{\text{spec}}$ projects into quantitative parametric spaces. However, in `TenabilitySolver` (`solvers.py`), evaluation relies exclusively on arithmetic formula evaluation over `[0, 1]` floats (`SafeFormulaEvaluator`). For philosophical or qualitative scientific texts where laws are relational/logical rather than algebraic equations, `LLMTheoryInducer` is forced to invent artificial pseudo-equations (e.g., `abs(Repression - Resistance * 0.5)`). Providing a first-class **relational/monotonic constraint evaluator** on $\Phi_{\text{gen}}$ alongside `SafeFormulaEvaluator` on $\Phi_{\text{spec}}$ would fulfill the promise of the dual-enrichment architecture.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Broken Desktop Zotero Links (L16, L18, L21, L24, L26, L28, L35, L37, L42, L46, L53, L65, L67, L69, L71, L76, L79, L81, L84, L94, L121, L123, L136, L138, L141, L143, L147, L150, L155, L160):** Contains 30+ local desktop `zotero://select/library/items/...` URIs, and links both `[Schurz, 2024]` and `[Balzer et al., 1987]` to the same Zotero key `24SNSW2B` (L53).
2. **Stale Import Path in Reference Example (`docs/reference/theoretical_enrichment.md` L98):** Uses `from pipeline.post_processing.theoretical_enrichment import ...` instead of `from episteme_pipeline.post_processing.theoretical_enrichment import ...`.
3. **Unregistered Labels in Workflow Step 1 (L190):** Refers to `:PotentialModelClass` ($M_p$), whereas `epistemetrics/core/models.py` uses `NodeType.POTENTIAL_MODEL`.
