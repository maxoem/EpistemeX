# Future Research Goals & Literature Analysis

This document compiles prioritized research directions, literature benchmarks, and theoretical insights for **Grund
Episteme**, anchored in *Pan et al. (2024)* ("Unifying Large Language Models and Knowledge Graphs: A Roadmap", arXiv:
2306.08302) and related state-of-the-art publications.

---

## 1. Literature Notes & Evaluated Papers

### 1.1 Hypercomplex & Quaternion Embeddings for Knowledge Graphs (Nayyeri et al., 2022)

* **Source:** Nayyeri et al., *"Integrating Knowledge Graph Embedding and Pretrained Language Models in Hypercomplex
  Spaces"*, 2022. (Ref [132] in Pan et al.)
* **Direct Quote:**
  > *„Nayyeri et al. use LLMs to generate the word-level, sentence-level, and document-level representations. They are
  integrated with graph structure embeddings into a unified vector by Dihedron and Quaternion representations of 4D
  hypercomplex numbers.“*
* **Why Found Interesting:**
    - Standard translational embedding models in Euclidean space can struggle to model complex relational patterns
      (e.g., non-commutative composition, multi-relational rotations) across multiple text representation granularities
      without large parameter expansion.
    - Quaternion embeddings ($\mathbb{H}^d$, where elements are
      quaternions $q = a + b\mathbf{i} + c\mathbf{j} + d\mathbf{k}$) use Hamilton product operations to perform
      rotations and scalings in 4D hypercomplex space, enabling non-commutative relation composition and structured
      fusion of multi-scale textual features with graph structure.

### 1.2 Model-Agnostic Knowledge Loss Functions (CoDEx, 2022)

* **Source:** Alam et al., *"Language Model Guided Knowledge Graph Embeddings"*, 2022. (Ref [134] in Pan et al.)
* **Direct Quote:**
  > *„CoDEx presents a novel loss function empowered by LLMs that guides the KGE models in measuring the likelihood of
  triples by considering the textual information. The proposed loss function is agnostic to model structure that can be
  incorporated with any KGE model.“*
* **Why Found Interesting:**
    - Provides a model-agnostic loss function for scoring candidate triple plausibility in Neo4j using LLM textual
      guidance without requiring full model fine-tuning.

### 1.3 Contrastive Learning & Candidate Retrieval Analysis (SimKGC [144] & Justin et al. [187])

* **Source:**
    - Wang et al., *"SimKGC: Simple Contrastive Knowledge Graph Completion with Pre-trained Language Models"*, ACL 2022.
      (Ref [144])
    - Justin et al., *"A Comprehensive Analysis of KGC Methods Integrated with LLMs"*, EMNLP 2022. (Ref [187])
* **Direct Quote:**
  > *„Justin et al. provide a comprehensive analysis of KGC methods integrated with LLMs. Their research investigates
  the quality of LLM embeddings and finds that they are suboptimal for effective entity ranking... SimKGC applies
  contrastive learning techniques to these representations... maximizing similarity between positive samples and
  minimizing negative samples.“*
* **Why Found Interesting:**
    - **Critical Finding:** Raw LLM text embeddings (e.g. standard cosine similarity) are suboptimal for entity ranking
      and link prediction in KGs because they measure topical similarity rather than relational truth.
    - **SimKGC Solution:** Uses Siamese textual encoders trained via contrastive learning (InfoNCE loss) to separate
      plausible and implausible triples, significantly improving candidate retrieval in Phase 3 Global Relation
      Extraction.

### 1.4 Reasoning on Graphs & Path Generation (RoG, 2023)

* **Source:** Luo et al., *"Reasoning on Graphs: Faithful and Interpretable Large Language Model Reasoning"*, arXiv:
  2310.01061, 2023. (Ref [112])
* **Direct Quote:**
  > *„To better reason on graphs, RoG presents a planning-retrieval-reasoning framework. RoG is finetuned on KG
  structure to generate relation paths grounded by KGs as faithful plans. These plans are then used to retrieve valid
  reasoning paths from the KGs for LLMs to conduct faithful reasoning...“*
* **Why Found Interesting:**
    - Generates explicit relation paths grounded by KGs as faithful plans before executing reasoning steps, providing
      human-verifiable decision traces for scientific argument evaluation.

### 1.5 In-Context Graph-to-Text Prompting (Mindmap, ChatRule, CoK)

* **Source:**
    - Wen et al., *"Mindmap: Knowledge Graph Prompting Sparks Graph of Thoughts in LLMs"*, 2023. (Ref [65])
    - Luo et al., *"ChatRule: Mining Logical Rules with Large Language Models for Knowledge Graph Reasoning"*, 2023.
      (Ref [116])
    - Wang et al., *"Boosting Language Models Reasoning with Chain-of-Knowledge Prompting"*, 2023. (Ref [117])
* **Direct Quote:**
  > *„Mindmap designs a KG prompt to convert graph structure into a mind map... ChatRule samples several relation paths
  from KGs, which are verbalized and fed into LLMs... CoK proposes a chain-of-knowledge prompting that uses a sequence
  of triples to elicit the reasoning ability of LLMs...“*
* **Why Found Interesting & Planned Goals:**
    - Demonstrates that converting subgraphs into natural text, mindmaps, or chain-of-knowledge sequences via
      **in-context prompting at inference time** achieves state-of-the-art reasoning without expensive parameter
      retraining.
    - **Standardized Graph-to-Text Serializers:** Implement Mindmap-style and Chain-of-Knowledge (CoK) graph-to-text
      serializers for subgraphs retrieved from the graph store before passing to LLM rerankers.

### 1.6 Selective Dict-BERT Micro-Glossary Injection (In-Context Prompting)

* **Description:** Support maturity-gated retrieval of concept node definitions from the graph store and selectively
  append 1-line concept micro-glossaries into LLM prompts to disambiguate long-tail scientific terms.

### 1.7 Continuous Entity Vector Projection & Soft Prompting (DKPLM / Graph-LLMs)

* **Description:** Investigate the feasibility and training requirements (projection matrix / adapter tuning) for
  mapping dense concept graph embeddings into continuous LLM input spaces.

### 1.8 Synergized Bidirectional Reasoning

* **Description:** Support a mutual feedback loop where the Processing Graph mutates the Projection Graph, guiding
  global relation extraction via recursive graph-directed prompt context.

### 1.9 Long-Context Agentic Memory Benchmarking

* **Description:** Benchmark the dual-memory architecture against emerging research on long-context agentic memory
  (e.g., MemGPT/Letta, Generative Agents, stateful scratchpads).

### 1.10 Hybrid Constrained Decoding Strategy

* **Source:** [`Evaluation Constrained Decoding`](../research/constrained_decoding.md).
* **Description:** For local or supported inference the model switches into constrained decoding during generation task
  after certain trigger-tokens have been generated.

### 1.11 World Models for Empirical Node Validation & Simulation

* **Description:** Generative and neuro-symbolic simulation environments designed to evaluate the empirical adequacy and correctness of empirical nodes ($I \subseteq M_{pp}$) in TheoryNets. By simulating domain mechanics, causal dependencies, and dynamic state transitions, candidate empirical assertions are evaluated against executable environment rollouts rather than static text co-occurrence or subjective LLM plausibility scores ($p(i, x)$).

---

## 2. Theoretical Analysis & Formal Explanations

### 2.1 Theoretical Rationale for Hypercomplex Embeddings (Pan et al., Sec. 8.2)

* **Source:** Pan et al. (2024), *"Unifying Large Language Models and Knowledge Graphs: A Roadmap"*, Section 8.2. (Anchoring Bordes et al., 2013; Sun et al., 2019; Zhang et al., 2019; Nayyeri et al., 2022).
* **Description:** Knowledge Graph Embedding (KGE) models define algebraic scoring functions $f(h, r, t)$ to evaluate the plausibility of relational triples across distinct geometric spaces:
    - **Translational Models ($\mathbb{R}^d$):** e.g., TransE (Bordes et al., 2013). Model relations as translations in Euclidean space ($f(h, r, t) = \|\mathbf{h} + \mathbf{r} - \mathbf{t}\|$), capturing basic asymmetry ($\mathbf{h} + \mathbf{r} \approx \mathbf{t} \centernot\implies \mathbf{t} + \mathbf{r} \approx \mathbf{h}$), but struggling with 1-to-N, N-to-1, and symmetric relations.
    - **Rotational Models ($\mathbb{C}^d$):** e.g., RotatE (Sun et al., 2019). Model relations as element-wise 2D rotations in the complex plane ($\mathbf{h} \circ \mathbf{r} \approx \mathbf{t}$), capturing symmetry, antisymmetry, inversion, and composition.
    - **Hypercomplex / Quaternion Models ($\mathbb{H}^d$):** e.g., QuatE (Zhang et al., 2019), Nayyeri et al. (2022). Extend rotations to 4D hypercomplex space using the non-commutative Hamilton product ($q_1 \otimes q_2 \neq q_2 \otimes q_1$). Quaternion embeddings capture richer geometric interactions, multi-relational hierarchies, and non-commutative relation compositions across multiple planes without large parameter expansion.
* **Why Found Interesting & Relevance to Episteme:**
    - Scientific and philosophical argument graphs frequently exhibit non-commutative inferential chains (e.g., premise order in deductive arguments) and multi-relational hierarchies.
    - Quaternion representations provide a principled mathematical bridge for fusing multi-granular textual representations (word-, sentence-, and document-level) with topological graph embeddings into a unified representation space.

### 2.2 Formal Difference Between Natural Language Embeddings and Graph Structure Embeddings (Pan et al., Sec. 8.3)

* **Source:** Pan et al. (2024), *"Unifying Large Language Models and Knowledge Graphs: A Roadmap"*, Section 8.3; Carnap (1928, 1936).
* **Description:** A fundamental qualitative distinction exists between embedding natural language and embedding graph topology. While textual embeddings capture distributional semantic proximity across unstructured text, graph structure embeddings capture formal inferential topology and directional relational constraints.

| Dimension | Text / Natural Language Embedding | Graph Structure / Topological Embedding |
| :--- | :--- | :--- |
| **Primary Metric** | Topical and semantic proximity; vocabulary co-occurrence. | Logical distance, directionality, entailment paths, and hub centrality. |
| **Example** | *"Kant's Synthetic A Priori"* and *"Hegel's Dialectical Logic"* exhibit **high similarity** (both frequently co-occur in texts on 19th-century German philosophy). | *"Kant's Synthetic A Priori"* and *"Hegel's Dialectical Logic"* exhibit **low proximity** if separated by intermediate refutation nodes in the argument graph. |
| **Blind Spots** | Directionality, asymmetric entailment, and structural contradiction. | Distributional nuances and unstructured discursive context outside the graph. |
| **Relational Expressivity** | Symmetric semantic affinity across unstructured text corpora. | Asymmetric relations ($A \implies B \centernot\implies B \implies A$), cycle topologies, and inferential hierarchies. |

* **Theoretical Foundations & Epistemic Grounding:**
    - In *Der logische Aufbau der Welt* (1928), Rudolf Carnap explored how scientific concepts can be constituted through relational structural positions. Later, in *Testability and Meaning* (1936), he introduced *Reduktionssätze* (reduction sentences) to handle dispositional concepts that cannot be exhaustively reduced to closed explicit definitions, bridging formal structure with open empirical anchoring.
    - **Textual Embeddings** capture descriptive, informal linguistic co-occurrence (what domain or discursive context two terms share).
    - **Graph Structural Embeddings** capture formal relational positioning (where a concept sits in an axiomatic, inferential argument topology).
* **Why Found Interesting & Relevance to Episteme:**
    - **Dual Strategy:** Textual embeddings guide initial entity discovery, candidate retrieval, and synonym resolution; structural graph representations and LLM-guided rerankers enforce precise inferential relations and entailment hierarchies.

---

*Note: For tracking concrete implementation tasks resulting from these research goals,
see the [Issue & Feature Specification Registry](../../issues/README.md).*
