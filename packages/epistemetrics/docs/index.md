# Epistemetrics

Welcome to **Epistemetrics** (`epistemetrics`), a Python library dedicated to structural, argumentation, and formal epistemic evaluation of scientific theory graphs.

---

## What is Epistemetrics?

Modern knowledge graph pipelines extract entities and relations, but evaluating scientific and philosophical literature requires understanding **theories as systemic formal structures**. 

Epistemetrics operationalizes foundational concepts from philosophy of science (*Wissenschaftstheorie*), formal epistemology, and computational argumentation:

- **Gerhard Schurz's Structural Theory Analysis**: Operationalizing empirical creativity ($E(H_1 \wedge H_2) \supset E(H_1) \cup E(H_2)$), unification power, and homogeneity (prevention of the tacking paradox).
- **Imre Lakatos's Research Programmes**: Measuring hard-core resilience vs. protective belt shielding.
- **Phan Minh Dung's Abstract Argumentation**: Evaluating dialectical strength, attack-support ratios, and grounded extension acceptability.
- **Quantitative Bipolar Argumentation Frameworks (QBAF)**: Solving gradual semantics equilibrium degrees ($\tau$) under continuous calibrated modal weights vs unweighted binary baseline graphs.
- **Paul Thagard's Explanatory Coherence**: Coherence energy minimization and circularity detection.

---

## Architectural Principles

1. **Lightweight & Standalone**: Only depends on `networkx`, `numpy`, and `pydantic`. Zero heavy NLP/LLM runtimes required.
2. **NetworkX Native**: First-class interoperability with standard NetworkX graphs, GraphML, and JSON.
3. **Scientifically Rigorous**: Clear mathematical and formal specifications for all metric scores.

---

## Documentation Structure (Diátaxis)

- **[Getting Started](getting_started/installation.md)**: Setup, prerequisites, and quickstart guide.
- **[Tutorials](tutorials/evaluate_theory_graph.md)**: End-to-end walkthroughs evaluating theory graphs.
- **[Theoretical Foundations](concepts/epistemic_metrics.md)**: Formal mathematical definitions of epistemic, argumentation, and coherence metrics.
- **[API Reference](reference/core.md)**: Technical specifications and class documentation.
