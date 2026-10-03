# Epistemetrics

**Epistemetrics** (`epistemetrics`) is a lightweight, scientifically grounded Python library for the structural, argumentation, and epistemic evaluation of scientific theory graphs.

Built on top of **NetworkX**, `epistemetrics` operationalizes formal principles from the philosophy of science (Wissenschaftstheorie)—including Gerhard Schurz's static theory structuralism, Karl Popper's empirical content, Imre Lakatos's research programmes, Paul Thagard's explanatory coherence, and Phan Minh Dung's abstract argumentation frameworks.

---

## Key Features

- **Theory Graph Data Structures**: Typed node & edge containers for scientific theories (Axioms, Hypotheses, Claims, Concepts, Phenomena, Evidence).
- **Epistemic Metrics**:
  - *Empirical Creativity & Deductive Excess*: Measuring $E(H_1 \wedge H_2) \setminus (E(H_1) \cup E(H_2))$.
  - *Theoretical Unification / Global Scope*: Quantifying explanatory breadth from foundational principles.
  - *Homogeneity & Tacking-Paradox Checks*: Detecting ad-hoc conjunctions and factorizability.
  - *Lakatosian Hard-Core Resilience*: Centrality and protection of theoretical hard-cores vs. auxiliary belts.
- **Argumentation & Coherence Analysis**:
  - *Dung Abstract Argumentation*: Grounded extension detection, attack/support ratios, dispute density.
  - *Thagard Explanatory Coherence*: Coherence scoring and cycle/circularity detection.
  - *QBAF Gradual Semantics Solvers*: Quantitative Bipolar Argumentation Framework equilibrium convergence under continuous calibrated modal weights vs unweighted binary graphs (Quadratic Energy, Eulerian, Categorizer, Linear).
- **Structural Graph Properties**:
  - Hierarchical derivation depth, modularity, clustering, reciprocity, and component connectivity.
- **Interoperability**: Seamless conversion to and from standard `networkx.Graph`, `networkx.DiGraph`, and `networkx.MultiDiGraph`.

---

## Installation

```bash
pip install epistemetrics
```

Or using `uv`:
```bash
uv add epistemetrics
```

---

## Quickstart

```python
import epistemetrics as em

# Initialize a Theory Graph
tg = em.TheoryGraph()

# Add theoretical components
tg.add_node("A1", name="Newtonian Mechanics", node_type=em.NodeType.AXIOM, epistemic_status=em.EpistemicStatus.HARD_CORE)
tg.add_node("H1", name="Gravitational Constant", node_type=em.NodeType.HYPOTHESIS, epistemic_status=em.EpistemicStatus.PROTECTIVE_BELT)
tg.add_node("P1", name="Planetary Orbits", node_type=em.NodeType.PHENOMENON)
tg.add_node("P2", name="Tidal Motion", node_type=em.NodeType.PHENOMENON)

# Add theoretical and explanatory relations
tg.add_edge("A1", "P1", relation_type=em.RelationType.EXPLAINS)
tg.add_edge("A1", "P2", relation_type=em.RelationType.EXPLAINS)
tg.add_edge("H1", "P1", relation_type=em.RelationType.SUPPORTS)

# Run full epistemic evaluation
report = em.analyze_theory_graph(tg)
print(report.to_markdown())

# QBAF Gradual Semantics with Calibrated Modal Weights
from epistemetrics.epistemic.qbaf import solve_qbaf_gradual_semantics, GradualSemanticsModel

qbaf_result = solve_qbaf_gradual_semantics(
    tg,
    model=GradualSemanticsModel.QUADRATIC,
    max_iterations=25,
)
print("justification degrees:", qbaf_result.final_values)
```

---

## Theoretical Foundations

1. **Schurz, G. (2014).** *Philosophy of Science: A Unified Approach.* Routledge.
2. **Lakatos, I. (1978).** *The Methodology of Scientific Research Programmes.* Cambridge University Press.
3. **Thagard, P. (1989).** *Explanatory Coherence.* Behavioral and Brain Sciences, 12(3), 435–467.
4. **Dung, P. M. (1995).** *On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games.* Artificial Intelligence, 77(2), 321–357.

---

## License

MIT License.
