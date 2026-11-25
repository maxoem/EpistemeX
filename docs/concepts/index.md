# Theory & Concepts

This section contains the theoretical foundations, formal mathematical models, and epistemological justifications for **Episteme**.

## Purpose

These documents answer **why** architectural choices were made and **what** mathematical and metatheoretical models govern Epistemic Theory Graph construction. They are written for researchers, reviewers, and scientific data scientists who need to understand the formal underpinnings of the system.

For software implementation and engineering details, refer to the [System Architecture](../architecture/overview.md) and [Pipeline Architecture](../architecture/pipeline_architecture.md).

---

## Epistemic & Theoretical Foundations

### [From Factual Knowledge Graphs to Epistemic Theory Graphs](kg_vs_tg.md)

Conceptual comparison between factual-entity knowledge graphs (such as Wikidata and scholarly KGs like ORKG/AIFdb) and Epistemic Theory Graphs, explaining the role of doxastic pluralism, dialectical evaluation semantics, intensional scoping, and structuralist theory-net projections.
*Key topics: Doxastic & theoretical pluralism, related scholarly KGs, dialectical edges, taxonomic incommensurability, two-level argument-mining bridge.*

### [Epistemology & Philosophy of Science](epistemology.md)

Metatheoretical criteria governing empirical theories and qualified normative analogies (reflective equilibrium). Synthesizes Gerhard Schurz's formal philosophy of science, Imre Lakatos's methodology of scientific research programmes, structuralist metascience, Paul Thagard's Theory of Explanatory Coherence (TEC/ECHO), and historiographical rational reconstruction.
*Key topics: Domain scope, empirical creativity, unification vs. novel prediction, Duhem vs. Quine holisms, natural-axiomatization homogeneity, AGM ad-hoc₁ accommodation, bounded degeneration proxy, TEC/ECHO lens, rational reconstruction.*

### [Assumptions & Limitations](assumptions_limitations.md)

Rigorous documentation of foundational epistemic assumptions, technical scalability constraints, model biases, and methodological boundaries of the pipeline.
*Key topics: Textual theory representation, LLM competence bounds, compositional hierarchy, scalability constraints.*

---

## Formal Models & Mathematical Foundations

### [Formal Graph Schema & Argumentation Semantics](formal_graph_model.md)

Canonical mathematical specification of Episteme's four-layer Epistemic Theory Graph ($L_1\text{--}L_4$), cleanly separating Layer 3 Dialectical Argument Graphs ($\mathcal{D}$) from Layer 4 Structuralist Theory-Nets ($\mathcal{N}$). Establishes the bipartite D-QBAF gradual semantics, three-tier uncertainty ontology, DL-Lite$_R$ four-branch role hierarchy, object-level mapping laws (*Zuordnungsgesetze*), and BMS model-theoretic foundations.
*Key topics: Four-layer labeled multigraph, bipartite inference warrants, D-QBAF quadratic-energy dynamics, three-tier uncertainty ontology, ECHO/Dung analytical lenses, uniform spaces, admissible blurs.*

### [Epistemic Grounding & Dense Alignment](dense_alignment.md)

Formal mathematical model for grounding raw textual assertions into unified ontological entities across heterogeneous literature.
*Key topics: Heterogeneous Information Networks (HIN), symmetrical context envelopes, dual-space bi/cross-encoder alignment, two-stage centroid entity maturation.*

### [Theory-Nets, Posets & Topologies](theory_nets_and_topologies.md)

Structural and topological analysis of Layer 4 intra-theory nets ($\mathcal{N} = \langle N, \sigma \rangle$) and inter-theory **Theory-Holons**, statement-level sentence typologies, multi-scale **recursive Leiden community detection** (signed/support-projected), and orientation-aware centrality (Katz, PageRank, participation coefficient).
*Key topics: BMS specialization posets, Bourbaki structure species, Theory-Trees, global constraints vs. intertheoretical links, Theory-Holons, recursive Leiden scales, topological centrality.*

### [Theory Metrics Subsystem](theory/metrics/index.md)

Formal specification of the 5-pillar mathematical evaluation suite for measuring the structural, coherence, empirical, dynamic, and metatheoretical quality of constructed theory graphs.
*Key topics: Structural topology, epistemic coherence, empirical power, theory dynamics, metatheoretical framework.*

---

## Cognitive Context & Stateful Memory

### [Episodic Working Memory](episodic_working_memory.md)

Theoretical architecture for preserving conversational and epistemic context across sequential document chunks during extraction without quadratic token overhead.
*Key topics: Dual-memory architecture, chapter outline coordinates, decoupled state machine, boundary-based episodic eviction.*

---

## Reference, Notation & Bibliography

### [Canonical Notation & Symbol Reference](notation.md)

Single, collision-free symbol table governing all four core conceptual documents across Layers 1–4, D-QBAF semantics, formal epistemology, and BMS structuralism.

### [Consolidated References & Bibliography](references.md)

Complete, verified primary literature bibliography referenced across Episteme's conceptual corpus, organized by discipline.

### [Glossary](glossary.md)

Authoritative bilingual reference defining core technical, graph-theoretic, and epistemological terms with verified academic citations and anchors.
*Key topics: Epistemic terminology, structuralist taxonomy, graph metrics, formal concepts.*

---

## Navigation Matrix

| Document | Category | Primary Focus | Key Frameworks & Concepts |
| :--- | :--- | :--- | :--- |
| **[KG vs. Epistemic Theory Graphs](kg_vs_tg.md)** | Epistemic Foundations | Factual-entity KGs vs. Epistemic Theory Graphs | Doxastic pluralism, Wikidata/ORKG/AIFdb, two-level bridge |
| **[Epistemology](epistemology.md)** | Epistemic Foundations | Domain-scoped criteria for theory evaluation | Schurz, Lakatos, Thagard (TEC/ECHO), reflective equilibrium |
| **[Assumptions & Limitations](assumptions_limitations.md)** | Epistemic Foundations | Boundary conditions & constraints | Methodological & model bounds |
| **[Formal Graph Schema](formal_graph_model.md)** | Formal Models | Complete four-layer Epistemic Theory Graph | Multigraph $L_1\text{--}L_4$, bipartite D-QBAF, 3-tier uncertainty, BMS |
| **[Dense Alignment](dense_alignment.md)** | Formal Models | Coordinate grounding & entity linking | HIN, Bi/Cross-Encoders, Centroid maturation |
| **[Theory-Nets & Topologies](theory_nets_and_topologies.md)** | Formal Models | Posets, trees, holons, and community detection | BMS $\langle N, \sigma \rangle$, Theory-Holons, signed recursive Leiden, Katz/PageRank |
| **[Theory Metrics Subsystem](theory/metrics/index.md)** | Formal Models | Quantitative theory evaluation | 5-pillar epistemic metrics |
| **[Episodic Working Memory](episodic_working_memory.md)** | Cognitive Context | Chunk-to-chunk context tracking | Dual-memory, outline coordinates, eviction |
| **[Canonical Notation](notation.md)** | Reference | Collision-free cross-document symbol table | Unified mathematical symbols across $L_1\text{--}L_4$ |
| **[Consolidated References](references.md)** | Reference | Shared primary literature bibliography | Philosophy of science, argumentation, KGs, network science |
| **[Glossary](glossary.md)** | Reference | Bilingual terminology & citations | Canonical philosophical & formal terms |

---

## Related Documentation

- **System Architecture**: [System Architecture Overview](../architecture/overview.md) and [Pipeline Architecture](../architecture/pipeline_architecture.md)
- **Execution Workflow**: [Workflow Overview](../workflow/index.md)
- **Decisions**: [Architectural Decision Records](../adr/index.md)
- **Research & Benchmarks**: [Evaluation Methodology](../research/evaluation_methodology.md) and [Structuralist Theory-Net Benchmark](../research/structuralist_theory_benchmark.md)
