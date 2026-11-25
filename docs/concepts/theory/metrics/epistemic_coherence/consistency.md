---
status: needs_verification
tags:
  - Metrics
---

# Consistency

## Definition & Conceptual Goal

The **Consistency** metric evaluates whether theoretical concepts and relational definitions maintain logical and
semantic coherence across documents and argumentative contexts
([Balzer et al., 1987, p. xviii](../../../references.md#balzer-1987); [Schurz, 2014, sec. 5.2](../../../references.md#schurz-2014)).

It detects **semantic drift** and **polysemy**, ensuring that a theoretical term (e.g., "mass", "entropy", "utility")
does not implicitly switch definitions or adopt mutually conflicting axiomatizations within the same reconstructed
theory.

---
## Theoretical Grounding & Model Formulation

In structuralist philosophy, a concept's formal meaning is bound by its potential model class $M_p$ and
cross-application constraints $C$. If term $\tau$ appears in multiple theory-elements $T_1, T_2$, its semantic
interpretation must satisfy relational compatibility:

$$C (\tau) \subseteq \mathcal{P} (M_p (T_1) \times M_p (T_2))$$

In natural language text, polysemy or equivocation creates an illusion of logical derivation while violating underlying
formal consistency.

---
## Mathematical Specification & Graph Formulation

Let $E_t = \{e_1, e_2, \dots, e_k\}$ be the set of entity mentions / definitions associated with term $t \in V$ across
documents, with vector embeddings $\mathbf{v} (e_i) \in \mathbb{R}^d$.

### Semantic Embedding Coherence ($S_{\text{embed}}$)

The semantic consistency of $e_i$'s underlying concepts, represented by the graph node $t$, is measured by the average pairwise cosine similarity of its textual contextual
embeddings:

$$S_{\text{embed}} (t) = \frac{1}{\binom{k}{2}} \sum_{1 \le i < j \le k} \frac{\mathbf{v} (e_i) \cdot \mathbf{v} (e_j)}{\|\mathbf{v} (e_i)\| \|\mathbf{v} (e_j)\|}$$

### Polysemy / Drift Score

If contextual embeddings form multiple distinct clusters (evaluated via silhouette score $S_{\text{sil}}$ over $k$
-means), the polysemy score is:

$$\text{PolysemyDrift} (t) = S_{\text{sil}} (t)$$

---
## Measurement & Graph Implementation

1. **Contextual Embedding Extraction**: Extract token/sentence embeddings for all entity mentions associated with a
   given concept node.
2. **Cluster Analysis**: Compute pairwise cosine similarity and check for multi-modal embedding distributions.
3. **Graph Consistency Validation**: In the property graph, flag nodes with $S_{\text{embed}} < \theta_{\text{sim}}$ for
   human review or automated entity splitting.

---
## Diagnostic & Metascientific Value

| Consistency Score           | Semantic State                 | Metascientific Interpretation                                                               |
|:----------------------------|:-------------------------------|:--------------------------------------------------------------------------------------------|
| $S_{\text{embed}} \ge 0.85$ | Unambiguous / Monosemous       | Rigorous conceptual precision throughout corpus.                                            |
| $S_{\text{embed}} < 0.60$   | High Polysemy / Semantic Drift | Concept equivocates across contexts; requires splitting into distinct theoretical entities. |

---
## Grounding References

* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel
  Publishing, p. xviii.
* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, sec. 5.2.
