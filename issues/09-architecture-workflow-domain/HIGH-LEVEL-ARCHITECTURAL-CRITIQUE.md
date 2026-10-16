# High-Level Architectural Critique: Macro-Concepts, Epistemic Paradigms, and System Design

| Metadata | Details |
| :--- | :--- |
| **Document Role** | Macro-Architectural & Conceptual Critique (Researcher, Software Architect, and Domain Expert Evaluation) |
| **Domain / Category** | `09-Architecture, Workflow & Domain` |
| **Evaluated Scope** | [`docs/architecture/`](../../docs/architecture/overview.md), [`docs/adr/`](../../docs/adr/index.md) (`ADR-0001`–`0020`), [`docs/concepts/`](../../docs/concepts/formal_graph_model.md) |
| **Focus** | Identifying missing, structurally inverted, or flawed **high-level architectural concepts** prior to concrete refactoring design |

---

## Executive Summary

Stepping back from code-level mechanics, Episteme's current architecture exhibits a fundamental tension between its **scientific ambition** (a *Synergized Bidirectional Reasoning Engine* for contested philosophical and scientific theories) and its **structural realization** (a *unidirectional, batch-oriented, single-perspective NLP compilation pipeline*).

Below are the **seven macro-architectural concepts and paradigms** that are currently missing, structurally inverted, or flawed at the system design level.

---

## 1. The Feed-Forward "Waterfall" Fallacy vs. Bidirectional Hermeneutic Refinement

### Current Architectural Concept
[`docs/architecture/pipeline_architecture.md`](../../docs/architecture/pipeline_architecture.md) defines Episteme as a *"Synergized Bidirectional Reasoning Engine... combining LLMs and Knowledge Graphs in a mutually beneficial feedback loop."* However, the actual macro-topology is a **strictly unidirectional, one-pass feed-forward waterfall**:
$$\text{Phase 1 (Chunks)} \to \text{Phase 2 (Entities)} \to \text{Phase 3 (Relations)} \to \text{Phase 3b/4m} \to \text{Phase 4 (Arguments)} \to \text{Phase 5 (Clusters)} \to \text{Phase 6 (QBAF)} \to \text{Post-Processing}$$

### Why This Is Conceptually Flawed
- **Violation of the Hermeneutic Circle**: In scientific and philosophical texts, local parts (entity mentions, implicit premises, rhetorical roles) cannot be accurately interpreted without the global whole (the overarching theoretical framework $T = \langle K, I \rangle$), and the global whole is iteratively revised by local evidence.
- **Zero Top-Down Feedback (L4/L3 $\not\to$ L2/L1)**:
  - When Phase 6 (`D-QBAF`) or Post-Processing (`TheoreticalEnrichment`, [`ADR-0015`](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md)) discovers an ungrounded theoretical claim, a disconnected argument chain (missing **enthymeme** / unstated premise), or a tenability anomaly ($TS_{\text{local}} < 0.5$), the architecture has **no feedback path** to query Layer 1/Layer 2 for the missing bridge premise or to re-evaluate an upstream entity disambiguation decision.
  - "Gleaning" is currently conceived only as a *local, intra-chunk* loop during Phase 2/4 extraction, rather than a **graph-driven top-down epistemic search** triggered by structural gaps in the global TheoryNet.

### Missing Architectural Concept
- **Closed-Loop Iterative / Cyclic Epistemic Refinement**: A macro-architecture where higher layers (L3 Dialectical QBAF and L4 Structuralist Theory Cores) emit **Epistemic Deficit Signals** (e.g., *Unwarranted Claim*, *Contradictory Cluster*, *Polysemous Hub Entity*, *Missing Intended Application*) that route back to targeted L1/L2 re-extraction or splitting passes until a convergence criterion is met.

---

## 2. The "View from Nowhere" (Flat Epistemic Space) vs. Intensional & Perspectival Attribution

### Current Architectural Concept
Across Phase 2 (`ADR-0009`), Phase 3b (`ADR-0003`), Phase 4 Maturation, and Phase 6 (`ADR-0011`, `ADR-0020`), all extracted entities, descriptions, propositions (`TheoryAtom`), and stances (`TheoryRelation`) are merged into a **single, flat, globally shared epistemic space**:
- Phase 4 Entity Maturation computes a single geometric centroid $\boldsymbol{\mu}_e = \frac{1}{N} \sum E_{\text{ctx}}(T_i)$ across all mentions of an entity to synthesize *one* canonical description.
- `ADR-0020` assigns a single intrinsic base score $\tau_0(a) = M(\phi_a)$ ("Authorial Propositional Modality") to each `TheoryAtom`.
- `ADR-0016` (Attribute Alignment Deferred) preserves contradictions only as `ATTACKS` edges between flat Layer 3 claims.

### Why This Is Conceptually Flawed
1. **Blindness to Intensional Contexts, Exegesis, and *Reductio ad Absurdum***:
   - Philosophical and scientific authors spend vast portions of text reconstructing, quoting, or steelmanning **opposing or historical theories** before critiquing them (e.g., Kant reconstructing Hume's empiricism or Descartes' rational psychology; a modern paper summarizing a refuted 19th-century hypothesis), or developing **counterfactual suppositions** (*"Suppose $X$ were true; then $Y$ would follow..."*).
   - In a flat graph without **Intensional / Perspectival Scoping**, claims extracted from an author's reconstruction of an opponent's view (or inside a *reductio* block) enter the global QBAF with positive base scores $\tau_0(a)$ and `SUPPORTS` edges, actively distorting the equilibrium justification $\tau^*$ of the author's actual theory!
2. **Destruction of Meaning Variance via Centroid Averaging**:
   - In philosophy and history of science, core concepts (*"Space"*, *"Substance"*, *"A Priori"*, *"Fitness"*, *"Entropy"*) are **contested, theory-laden terms** whose definitions shift across authors, schools of thought, and epochs ($t_1 \to t_2$).
   - Averaging all mention envelopes into a single geometric centroid $\boldsymbol{\mu}_e$ (Phase 4 Maturation) and merging them via Union-Find (Phase 3b) creates an artificial "Frankenstein definition" that erases the exact doctrinal differences a Theory Graph is meant to study.

### Missing Architectural Concept
- **First-Class Epistemic Attribution & Perspectival Contexts (Intensional Scopes / Voice Envelopes)**:
  - Every proposition and conceptual definition must be indexed by an **Epistemic Perspective / Attribution Frame**: $\langle \text{AssertingAgent}, \text{EpistemicMode} \in \{\text{Asserted}, \text{Attributed/Exegetical}, \text{Suppositional/Reductio}, \text{Historical}(t)\}, \text{TheoryFrame} \rangle$.
  - Entities must separate **Referential Identity** (the shared topic/term across theories) from **Conception / Intensional Sense** (how Theory $T_A$ vs. Theory $T_B$ defines that entity), rather than collapsing all conceptions into a single centroid description.

---

## 3. Pairwise Graph Reductionism vs. Hypergraph / Reified Inference Topology

### Current Architectural Concept
The formal graph model ([`docs/concepts/formal_graph_model.md`](../../docs/concepts/formal_graph_model.md), [`ADR-0007`](../../docs/adr/0007-tf-structural-correspondence.md), [`ADR-0011`](../../docs/adr/0011-declarative-graph-metrics-and-qbaf-semantics.md)) restricts Layer 3 to a **directed pairwise multigraph** where relations are binary edges $r = (a_j \to a_i) \in \mathcal{A} \times \mathcal{A}$, and gradual semantics sum incoming energies linearly:
$$E_i(t) = \sum_{j} W_{ji} s_j(t) - \sum_{k} W_{ki} s_k(t)$$

### Why This Is Conceptually Flawed
1. **Inability to Distinguish Linked (Conjunctive) vs. Convergent Arguments**:
   - In scientific reasoning and formal epistemology (Freeman, 1991; Walton, 2006; Schurz, 2014), theoretical deductions require **conjunctive premises**: e.g., a universal law $L \in A$ combined with an empirical boundary condition $B_1 \in B$ jointly entails prediction $C$ ($\{L, B_1\} \vdash C$).
   - If $B_1$ is false ($s_{B_1} = 0$), $L$ alone provides **zero** support to $C$. Yet in a pairwise additive QBAF ($L \to C$ and $B_1 \to C$ as independent binary edges), even when $B_1$ is completely refuted ($s_{B_1} = 0$), the edge $L \to C$ still transmits full positive energy $W_{L,C} s_L$ to $C$!
2. **Inability to Represent Pollockian Undercutting Defeaters & Toulmin Backing**:
   - Epistemology distinguishes three types of defeat (Pollock, 1987; Prakken, 2020):
     1. *Undermining* (attacking a premise $a_j$),
     2. *Rebutting* (attacking a conclusion $a_i$), and
     3. *Undercutting* (attacking the **inferential link / warrant** between $a_j$ and $a_i$ without disputing $a_j$'s truth).
   - Similarly, Toulmin's (1958) *Backing* (referenced in `ADR-0020`) supports the *Warrant* (the inference rule), not the conclusion directly.
   - Because binary property-graph edges cannot be the source or target of other edges, pairwise `TheoryRelation` edges cannot represent undercutting defeaters, Toulmin backings, or multi-premise conjunctive deductions.

### Missing Architectural Concept
- **Bipartite Inference / Argumentation Hypergraph (Reified Warrant Nodes)**:
  - Modeling Layer 3 as a bipartite graph (or directed hypergraph) of **Proposition Nodes ($\mathcal{A}$)** and **Inference / Warrant Nodes ($\mathcal{W}$)** (analogous to Argument Interchange Format [AIF] or ASPIC+ inference applications).
  - Conjunctive premises $\{a_1, a_2\}$ feed into a single `InferenceNode` $w_k$ (evaluated via product/t-norm $\min(s_1, s_2)$ or $s_1 \cdot s_2$), while convergent arguments feed into separate `InferenceNode`s, and undercutting defeaters or Toulmin backings target $w_k$ directly.

---

## 4. Point-Estimate Collapse Across Phase Boundaries vs. End-to-End Uncertainty Propagation

### Current Architectural Concept
While [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md) and [`ADR-0018`](../../docs/adr/0018-decision-engine-architecture-and-contracts.md) critique scalar heuristic cutoffs within individual classification calls, the **macro-pipeline still collapses uncertainty into hard, irreversible point estimates at every phase boundary**:
- Phase 1 commits to a single static chunk segmentation.
- Phase 2 commits to hard entity link decisions.
- Phase 3b commits to hard transitive equivalence classes via Union-Find (`SAME_AS` with `confidence: 1.0`).
- Phase 5 commits to hard community partitions and cluster merges.

### Why This Is Conceptually Flawed
1. **Transitive Chaining Pathology in Hard Union-Find Consolidation**:
   - In Phase 3b and Phase 5, converting pairwise similarity/conformal checks into connected components via **Union-Find** enforces strict mathematical transitivity ($A \sim B \land B \sim C \implies A = C$). In philosophical corpora with polysemous bridge terms $B$, Union-Find suffers from catastrophic single-linkage chaining, collapsing distinct concepts $A$ and $C$ into a single canonical node before Phase 4 or Phase 6 ever sees them.
2. **Compounding Error Across Cascading Conformal Gates (Lack of Family-Wise Risk Control)**:
   - Split Conformal Prediction guarantees $P(Y \in C(X)) \ge 1 - \alpha$ for an **isolated, single-stage** prediction under exchangeability.
   - When a pipeline chains 6 to 8 sequential phases—where Phase $k$'s test distribution is generated by Phase $(k-1)$'s predictions—errors compound multiplicatively across stages, and upstream mistakes induce covariate shift downstream, invalidating naive per-phase $\alpha$ guarantees.

### Missing Architectural Concept
- **Soft Hypothesis Preservation & Compositional Risk Control**:
  - Delaying hard destructive merges (replacing transitive Union-Find node collapse with weighted similarity/subsumption edges or cluster correlation partitioning that prevents transitive chaining).
  - Adopting **Multi-Stage / Compositional Conformal Risk Control** (e.g., Bonferroni/sequence-level $\alpha$-investing or Risk-Controlling Prediction Sets [RCPS]) calibrated over end-to-end graph construction metrics rather than isolated local classifiers.

---

## 5. Conflation of "Execution Run Lineage" with "Epistemic Knowledge Base Evolution"

### Current Architectural Concept
[`docs/architecture/artifact_run_model.md`](../../docs/architecture/artifact_run_model.md) and [`invalidation_and_resume.md`](../../docs/architecture/invalidation_and_resume.md) organize all persistence around **Execution Runs (`run_id`)**:
- A run takes a static `PipelineInput` (list of files) and produces a run-scoped `.pipeline_artifacts/<run_id>/` snapshot.
- Resumption (`parent_run_id`) is designed for **cache recovery / hyperparameter tweaking on the same static input corpus** (since any change to `input_fingerprint` invalidates the entire run from Phase 1 onward!).

### Why This Is Conceptually Flawed
1. **No Incremental Corpus Growth ($\mathcal{G}_t + \Delta D \to \mathcal{G}_{t+1}$)**:
   - Research projects do not ingest a fixed corpus once. A researcher builds a Theory Graph over 20 works, curates it, and then adds 3 new papers ($\Delta D$).
   - Because `input_fingerprint` hashes the entire corpus file list, adding a single new document invalidates **Phase 1 through Phase 6 across all 20 existing documents**, forcing a full recomputation rather than incrementally ingesting $\Delta D$ and integrating its entities/arguments into the existing Theory Graph!
2. **One-Way Street for Human-in-the-Loop (HITL) Curation & Active Learning**:
   - [`ADR-0019`](../../docs/adr/0019-typesafe-jev-client-and-decision-observability.md) routes ambiguous conformal sets ($|C(X)| > 1$) to an Active Learning queue, and Studio issues envision human curation (merging nodes, splitting concepts, flipping edge polarities).
   - However, the architecture lacks a **Persistent Epistemic Overlay / Constraint Ledger** fed back as *input* into the pipeline. If a human expert curates a run's graph and then re-runs the pipeline with an updated prompt or adds a new document, all human curations are wiped out or orphaned on the old `run_id`.

### Missing Architectural Concept
- **Decoupling Compute Runs from Versioned Epistemic Corpora (Knowledge Base Lifecycle)**:
  - Separating **1. Corpus & Document-Level Artifacts** (content-addressed by *individual document hash* rather than monolithic corpus hash, enabling incremental document addition $\Delta D$), **2. Epistemic Curation & Constraint Ledgers** (human-verified merges, splits, and polarity overrides stored as first-class axiomatic priors that constrain future automated runs), and **3. Execution Runs** (compute transactions that transform $(G_{\text{prior}}, \Delta D, \text{CurationLedger}) \to G_{\text{next}}$).

---

## 6. Passive Post-Hoc Evaluation vs. Active Runtime Epistemic Falsification & Self-Regulation

### Current Architectural Concept
Across [`docs/architecture/overview.md`](../../docs/architecture/overview.md), [`ADR-0007 §4`](../../docs/adr/0007-tf-structural-correspondence.md), and [`ADR-0011`](../../docs/adr/0011-declarative-graph-metrics-and-qbaf-semantics.md), **Evaluation & Epistemetrics** (structural topology, coherence, calibration ECE, tenability) are architected as **passive, post-construction analytics** executed *after* the pipeline finishes.

### Why This Is Conceptually Flawed
- **Open-Loop Blindness During Construction**:
  - If an upstream phase suffers structural or epistemic pathology—for example, Phase 2 NER suffers schema collapse (95% of entities typed as a single class), Phase 3b cosine thresholding causes percolating giant-component collapse (merging 60% of the graph into one cluster), or System 1 Jev encounters severe out-of-distribution shift (80% of predictions returning empty conformal sets $|C(X)| = 0$ or multi-class sets $|C(X)| > 1$)—the pipeline has **no homeostatic feedback or epistemic circuit breakers**.
  - It blindly proceeds into downstream phases on top of a degenerated topology, wasting hours of LLM compute and producing meaningless TheoryNets.

### Missing Architectural Concept
- **Intrinsic Epistemic Quality Gates & Homeostatic Control**:
  - Embedding lightweight structural and distributional invariants (e.g., cluster size entropy bounds, percolation/giant-component thresholds, conformal ambiguity rate monitors, calibration shift detectors) as **Inter-Phase Epistemic Contracts** that can halt execution, dynamically recalibrate thresholds (e.g., tightening similarity cutoffs if percolation is detected), or escalate to human review before downstream phases execute.

---

## 7. Monolithic Orchestrator ("God Object") vs. Declarative Workflow & Dataflow Separation

### Current Architectural Concept
[`Pipeline`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py) is architected as a central procedural class that simultaneously owns:
1. **Composition Root & Factory Wiring** (`Pipeline.for_task` instantiating LLMs, caches, rerankers, Jev clients, modal resolvers).
2. **Workflow Topology Definition** (hardcoded sequential phase list for `task="knowledge_graph"`).
3. **Cache & Invalidation Policy** (manifest diffing, artifact hydration, prompt/method fingerprinting).
4. **Storage & Projection Orchestration** (driving `JsonArtifactStore`, `JsonRunManifestStore`, `checkpoint_store`, and `ArtifactGraphProjector`).
5. **Observability Scoping** (binding `contextvars` emitters, loggers, and building `RunReport`s).

### Why This Is Conceptually Flawed
- **Rigidity Against Research Workflow Diversity**:
  - A research platform for computational philosophy of science requires multiple distinct **macro-workflows**, not just a single monolithic batch ingestion pipeline:
    - *Workflow A*: Full Monograph Ingestion ($D \to \mathcal{G}$).
    - *Workflow B*: Incremental Literature Expansion ($\mathcal{G} + \Delta D \to \mathcal{G}'$).
    - *Workflow C*: Comparative / Diachronic Theory Alignment ($\mathcal{G}_{\text{Author A}} \times \mathcal{G}_{\text{Author B}} \to \mathcal{G}_{\text{Reduction/Conflict}}$).
    - *Workflow D*: Targeted Hypothesis / Competency Query Verification ($q \times \mathcal{G} \to \text{Targeted L1 Re-Extraction}$).
    - *Workflow E*: Parameter / Prompt Ablation Grid over a frozen upstream subgraph.
  - Because workflow topology, DI wiring, storage, and invalidation are tightly coupled inside `Pipeline`, expressing any workflow other than the linear 8-phase `knowledge_graph` sequence requires bypassing or duplicating the orchestrator.

### Missing Architectural Concept
- **Tripartite Separation of Concerns in Orchestration**:
  1. **Declarative Workflow / Dataflow Graph**: Pure specification of transformation nodes and typed artifact streams (supporting branching, cyclic refinement loops, multi-corpus inputs, and sub-workflow composition).
  2. **Composition Root / Dependency Container**: Pure construction and lifecycle management of models, engines, and adapters from configuration.
  3. **Dataflow Execution & Lineage Engine**: Agnostic runtime that schedules a declarative workflow graph, manages content-addressed artifact caching, enforces epistemic quality gates, and dispatches projection/telemetry hooks.

---

## Summary Matrix: Current Paradigm vs. Target Macro-Architecture

| Architectural Dimension | Current Paradigm (What is Wrong / Limiting) | Target Macro-Architectural Concept |
| :--- | :--- | :--- |
| **1. Reasoning Topology** | Unidirectional feed-forward waterfall (`L1 -> L2 -> L3 -> L4`) | **Closed-Loop Hermeneutic Refinement** (L3/L4 anomalies & missing enthymemes trigger targeted L1/L2 re-extraction) |
| **2. Epistemic Space** | Flat, single-perspective graph; centroid averaging erases conceptual polysemy | **Intensional & Perspectival Scoping** (Agent attribution, *Reductio*/counterfactual contexts, school-specific conceptions) |
| **3. Argument Structure** | Pairwise binary multigraph ($a_j \to a_i$); additive QBAF conflates linked & convergent premises | **Bipartite Inference Hypergraph** (Reified Warrant/Inference nodes supporting conjunctive premises & undercutting defeaters) |
| **4. Uncertainty Handling** | Local conformal sets collapsed into hard point decisions & transitive Union-Find at each phase | **Soft Hypothesis Preservation & Compositional Risk Control** (Non-transitive clustering + pipeline-wide risk bounds) |
| **5. Knowledge Lifecycle** | Ephemeral batch `run_id` snapshots; adding 1 doc invalidates entire corpus; HITL edits orphaned | **Versioned Incremental Knowledge Base** (Document-addressed caching $\mathcal{G} + \Delta D$, persistent HITL Curation Constraint Ledger) |
| **6. Evaluation Role** | Passive post-hoc metrics (`epistemetrics` / Studio overlays) after run completion | **Active Runtime Epistemic Falsification** (Homeostatic inter-phase quality gates & percolation/drift circuit breakers) |
| **7. Orchestration Model** | Monolithic `Pipeline` God Object hardcoded around a single sequential `knowledge_graph` task | **Declarative Dataflow Engine** (Decoupling Workflow Topology, DI Composition Root, and Cache/Execution Runtime) |
