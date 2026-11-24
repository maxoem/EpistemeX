# Assumptions and Limitations

Understanding the foundational assumptions and inherent limitations of **Episteme** is crucial for appropriate
application, scholarly interpretation, and empirical verification.

---

## Executive Summary: Assumption & Risk Matrix

| Core Area / Assumption           | Inherent Risk or Limitation                                                       | Mitigation Strategy in Episteme                                                                                  |
|:---------------------------------|:----------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------|
| **Text as Theory Repository**    | Authorial ambiguity, informal prose, and unstated enthymemes.                     | Episodic working memory context, verbatim character span provenance, and confidence scoring.                      |
| **LLM Competence**               | Generative hallucination, self-affirmation bias, and reasoning drift.             | Optimal Edit Paths (OEP) error quantification, schema-constrained decoding, and human expert review rubrics.      |
| **Compositional Structure**      | Oversimplification or loss of emergent holism when theories are graph-decomposed. | Multi-layer stratification (Layers 1 & 2 for facts/triples, Layer 3 for TheoryNets and defeasible argument webs). |
| **Cross-Document Consistency**   | Polysemy, exegetical attribution, and conceptual drift across historical periods and schools of thought. | Spherical polysemy stratification into `EntityConception` facets (ADR 0023), Layer 3 `intensional_mode` / `attributed_to` scoping, and author-centric empirical bases ($B(t)$). |
| **Scalability vs. Expressivity** | Combinatorial explosion in global cross-document link candidate generation.       | Dense retrieval candidate pruning, cross-encoder reranking (ADR 0002), and asynchronous Neo4j driver pooling.     |

---

## Core Epistemic & Methodological Assumptions

### Text as Theory Repository

**Assumption:** Scholarly texts contain explicit or implicit theoretical frameworks that can be computationally
extracted, structured, and topologically represented.

**Implications & Constraints:**

- The pipeline is optimized for academic, peer-reviewed monographs and journal articles.
- Applicability to casual, purely descriptive, or narrative texts is limited.
- Extraction quality remains bounded by authorial clarity, argumentative rigor, and structural transparency.

### LLM Extraction Competence

**Assumption:** State-of-the-art Large Language Models possess sufficient semantic and syntactical competence to
identify technical philosophical concepts and reconstruct defeasible arguments.

**Implications & Constraints:**

- Quality is strictly dependent on underlying model pretraining distributions and instruction-following fidelity.
- Systematic training biases (e.g., preference for contemporary Western analytic philosophy over continental or
  non-Western traditions) can distort extraction.

### Compositional Theory Structure

**Assumption:** Theoretical frameworks can be decomposed into discrete entities, relations, axioms, and arguments
without destroying their essential scientific meaning.

**Implications & Constraints:**

- Risk of reductionism: Highly nuanced, holistic philosophical worldviews can lose subtle rhetorical interdependencies
  when forced into discrete nodes and edges.
- Mitigated by our multi-layer approach, which preserves continuous textual provenance for every assertion.

---

## Technical & Operational Limitations

### Scalability Constraints

* **Graph Database Traversal:** As the graph scales to millions of nodes, complex Cypher pattern matching across
  recursive argument paths incurs noticeable latency.
* **Vector Indexing Overhead:** Maintaining high-dimensional dense embeddings for every entity mention and argument
  component requires substantial RAM and vector storage.
* **Sequential Dependencies:** While individual chunk extraction is embarrassingly parallel, global relation discovery
  and community fusion (Leiden clustering) require synchronization barriers.

### Accuracy Boundaries Across Tasks

* **Entity Extraction & Disambiguation:** Fine-grained typing (distinguishing a *School of Thought* from a
  *Methodological Paradigm*)
  exhibits lower inter-annotator agreement than coarse named entity recognition.
* **Implicit Relation Discovery:** Relationships spanning distant book chapters or between different works are
  inherently harder to detect than local, intra-chunk triples.
* **Argument Component Classification:** Distinguishing a *Premise* from an *Intermediate Claim* often hinges on
  rhetorical context that exceeds single-chunk attention windows.

### Language & Domain Coverage

* **Primary Language Support:** Episteme is explicitly engineered for German and English scientific and philosophical
  literature.
* **Domain Adaptation:** While the underlying architecture is generalizable, prompt templates, schemas, and stop-words
  are heavily tuned to philosophy, sociology, and history of science.

---

## Practical Guidelines for Scholarly Interpretation

To ensure responsible scholarly use of pipeline outputs:

1. **Verify Evidence Spans:** Always trace extracted claims and relations back to their verbatim source character spans
   via the provenance metadata.
2. **Inspect Confidence & Calibration:** Pay close attention to relation confidence scores and calibration metrics.
3. **Account for Historical Context:** Avoid presentist bias by interpreting theoretical assertions relative to the
   author's contemporary empirical horizon ($B (t)$), rather than modern scientific consensus.
4. **Treat Graphs as Hypotheses:** Regard generated Theory Graphs as structured interpretative hypotheses that serve as
   starting points for human hermeneutic analysis.
5. **Inspect Intensional Scopes & Stratified Conceptions:** When reviewing multi-perspective debates or *Reductio* arguments, distinguish `asserted`, `suppositional`, and `attributed` Layer 3 propositions (`intensional_mode` / `attributed_to`) and inspect Layer 2 `EntityConception` facets rather than relying solely on the joined summary string ([ADR 0023](../adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)).

---

## Related Documentation

* **Epistemological Criteria**: [Epistemology & Wissenschaftstheorie](epistemology.md)
* **Knowledge Graphs vs. Theory Graphs**: [Knowledge Graphs vs Theory Graphs](kg_vs_tg.md)
* **Evaluation Methodology**: [Evaluation Methodology](../research/evaluation_methodology.md)
* **Empirical Construction Metrics**: [Empirical Metrics & Validation](../research/metrics.md)
* **Pipeline Runtime Analysis**: [Pipeline Runtime Analysis](../architecture/runtime_analysis.md)
* **Intensional Scoping & Conception Stratification**: [ADR 0023](../adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)
