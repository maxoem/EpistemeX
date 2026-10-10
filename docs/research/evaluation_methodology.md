# Evaluation Methodology

This document establishes the theoretical grounding and formal specification of the evaluation strategy for the **Grund
Episteme** pipeline. It defines *what* we measure, *why* we measure it, how we address the unique challenges of evaluating
LLM-driven Knowledge Graph (KG) and Theory Graph construction, and the operational contracts governing reproducible
research reports.

---

## The Challenge of Evaluating LLM-Driven Theory Graphs

Constructing a multi-layered theory graph from academic literature requires a multi-dimensional evaluation strategy.
Traditional exact-match metrics (such as strict token-level Precision, Recall, and F1 on string triples) are
fundamentally insufficient:

1. **Paraphrase and Lexical Synonymy:** Exact-match metrics penalize Large Language Models (LLMs) for generating valid
   synonyms, paraphrased relationship predicates, or structurally equivalent graph topologies.
2. **Hallucination vs. Omission:** LLMs are prone to ungrounded assertions. Evaluation must separate fabricated
   information (spurious triples) from missed information (omissions).
3. **Multi-Layer Abstraction:** A scientific graph spans from ground-level entity mentions and factual relations (Layers
   1 & 2)
   to defeasible argument structures and metatheoretical axioms (Layer 3). Each layer demands distinct evaluation
   protocols.

To address these challenges, our methodology strictly stratifies evaluation into four distinct evaluation levels:

| Evaluation Level                 | Target Pipeline Layer            | Focus & Grounding                                                   | Primary Metrics                                                   | Primary Tooling                            |
|:---------------------------------|:---------------------------------|:--------------------------------------------------------------------|:------------------------------------------------------------------|:-------------------------------------------|
| **1. Intrinsic Evaluation**      | Layer 1 & 2 (Entities & Triples) | Structural and semantic alignment against Gold Standard graphs.     | GM-GBS (Soft F1), OEP (Hallucination Rate, Omission Rate).        | NetworkX Scorers (`gm_gbs.py`, `oep.py`).  |
| **2. Extrinsic Evaluation**      | Layer 2 & Downstream Graph       | Downstream utility in information retrieval and question answering. | MRR, Hits@k, nDCG@k, Mean Average Precision (MAP).                | Retrieval Scorer (`retrieval_scorer.py`).  |
| **3. Reference-Free Evaluation** | Layer 1 & 2 (Extraction Quality) | Direct alignment between extracted triples and source text chunks.  | Faithfulness (% supported), Comprehensiveness (% major claims).   | Calibrated LLM-as-a-Judge (`run_eval.py`). |
| **4. Theory Layer Evaluation**   | Layer 3 & Level 4 (TheoryNet)    | Bourbaki model decomposition ($\mathcal{M}_p, \mathcal{M}, \mathcal{M}_{pp}, GC, I_0$) & capability subsumption ($G_{\text{pred}} \succeq_{\text{cap}} G_{\text{ref}}$). | $MCC$, $AOR$ (Zero Omission), $PFS$, $AG_{\text{IoU}}$, Lakatosian resilience. | `epistemetrics` sovereign evaluator, [STNB](structuralist_theory_benchmark.md). |

---

## Intrinsic Evaluation: Graph Structural Matching (Layers 1 & 2)

Intrinsic evaluation measures the structural and semantic fidelity of the extracted knowledge graph against a curated
Gold Standard, independent of downstream tasks.

### Graph BERTScore (GM-GBS)

Instead of rigid string equality, we utilize **Graph Matching using Graph BERTScore (GM-GBS)**. This metric embeds the
predicate labels of predicted and gold edges into a shared contextual vector space:

* **Soft Matching:** We apply a configurable cosine similarity threshold (default $\tau = 0.95$). If a predicted edge
  predicate achieves $\text{similarity} (E_{\text{pred}}, E_{\text{gold}}) \ge 0.95$, it is accepted as a semantic
  match. This accommodates synonymy and cross-lingual alignment.
* **Metric Formulation:**
  \[ \text{Soft Precision} = \frac{|E_{\text{matched, pred}}|}{|E_{\text{pred}}|}, \quad \text{Soft Recall} = \frac{|E_
  {\text{matched, gold}}|}{|E_{\text{gold}}|}, \quad \text{GM-GBS} = \frac{2 \cdot \text{Soft Precision} \cdot
  \text{Soft Recall}}{\text{Soft Precision} + \text{Soft Recall}} \]

### Optimal Edit Paths (OEP)

To diagnose the nature of structural errors, we compute **Optimal Edit Paths (OEP)** by calculating the insertion and
deletion operations required to reconcile the predicted graph with the gold standard:

* **Hallucination Rate ($HR$):** The proportion of predicted edges with no semantic match in the gold standard:
  \[ HR = \frac{|E_{\text{pred}} \setminus E_{\text{matched, pred}}|}{|E_{\text{pred}}|} \]
* **Omission Rate ($OR$):** The proportion of gold-standard edges omitted by the pipeline:
  \[ OR = \frac{|E_{\text{gold}} \setminus E_{\text{matched, gold}}|}{|E_{\text{gold}}|} \]

---

## Extrinsic Evaluation: Downstream Retrieval Utility

Extrinsic evaluation quantifies the operational value of the constructed graph when queried by downstream tasks such as
Semantic Search, Question Answering, and Argument Retrieval.

Benchmark queries paired with gold-standard target node/document IDs are executed against the Neo4j graph using the
`GraphReader` protocol:

* **Mean Reciprocal Rank (MRR):** Evaluates the reciprocal rank of the first relevant node retrieved:
  $\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$.
* **Hits@k:** Binary indicator of whether at least one relevant node appears in the top $k$ retrieved results.
* **Normalized Discounted Cumulative Gain (nDCG@k):** Evaluates graded ranking quality, heavily penalizing relevant
  constructs ranked lower in the result list.
* **Mean Average Precision (MAP):** Evaluates precision across the entire recall spectrum for multi-target queries.

---

## Reference-Free Evaluation & The LLM-as-a-Judge Policy

When curated gold standards are unavailable or unfeasible to construct for large corpora, reference-free evaluation
assesses graph quality directly against the source text.

### The Dual-Stance Policy on LLM-as-a-Judge

Episteme maintains an explicit, bifurcated policy on the use of LLMs as evaluators:

!!! tip "Important"
    **Policy on LLM-as-a-Judge:**
    
    1. **Permitted for Layer 1 & 2 Extraction Quality (Secondary Signal):** LLM-as-a-judge is permitted to assess
        *Faithfulness* (whether an extracted triple is grounded in its source chunk) and *Comprehensiveness* (whether
         major
        entities were omitted). However, this automated judge must be statistically calibrated against human review
         samples.
    
    2. **Strictly Prohibited for Layer 3 Argument & Theory Quality:** LLM-as-a-judge is **strictly forbidden** from
        evaluating argumentative validity, cogency, or theoretical tenability.

### Rationale: Preventing Circular Evaluation Bias

Applying an LLM judge to evaluate high-level philosophical arguments extracted by an LLM introduces severe **circular
evaluation and self-affirmation bias**. Language models exhibit systematic preference for arguments, rhetorical
structures, and stylistic patterns that match their own generative priors. Relying on an LLM to validate the theoretical
coherence of its own extractions destroys the scientific validity of the evaluation.

### Human Review Baseline for Layer 3

Before automated proxies can be considered for higher-level theory layers, evaluation must be anchored in a **Human
Review Baseline**:

* Annotations must be conducted by domain scholars (e.g., in philosophy and history of science).
* Inter-annotator agreement must be quantified using **Krippendorff's $\alpha$** (or Cohen's $\kappa$ for pairwise
  ratings).
* Automated methods are evaluated based on their mathematical correlation with this human ground truth.

---

## Evaluation Scaffolding & Operational Contracts

To ensure scientific rigor and reproducible benchmarks, the evaluation subsystem implements strict contracts (codified
in `pipeline/evaluation/` and `evaluation/`).

### Run-Linked Evaluation (Section 8 Contract)

Every evaluation report must be immutably linked to a concrete run manifest (`run_manifest.schema.yaml`). At minimum,
every evaluation report must reference:

* `run_id`: The unique execution identifier.
* `corpus_id` & `language`: The exact corpus and language split evaluated.
* `method_ids`: Configuration fingerprints of chunkers, extractors, linkers, and fusion algorithms.
* `prompt_ids` & versions: Checksums and IDs of all LLM prompts used.
* `schema_snapshot`: Checksum of the entity and relationship schema active during the run.
* `code_version`: Git commit SHA of the pipeline code.
* `artifact_references`: Content-addressed references to intermediate phase artifacts.

Without complete run linkage, evaluation outputs are treated as non-authoritative.

### Human Review Workflows (Section 9 Contract)

Because theoretical discourse is conceptually subtle, human review follows a structured workflow:

1. **Stratified Sampling:** Sample artifacts, ambiguous entity links, and candidate global relations from a completed
   run.
2. **Rubric-Based Assessment:** Domain experts evaluate sampled items against standardized, reusable rubrics
   (`EvaluationRubric`, `RubricCriterion`).
3. **Structured Persistence:** Review judgments are recorded as immutable evaluation artifacts (`EvaluationJudgment`)
   stored under `experiments/<run_id>/review/`.
4. **Iterative Feedback:** Error patterns from review artifacts are fed directly into prompt and algorithm refinement.

### Error Analysis & Buckets (Section 10 Contract)

Evaluation must not rely exclusively on scalar summary scores. The pipeline categorizes failures into explicit error
buckets (`EvaluationErrorBucket`):

* `source_normalization_error`: Corrupted text extraction or encoding failures.
* `chunk_boundary_error`: Splitting theoretical arguments across arbitrary token boundaries.
* `missed_entity_mention`: Entity present in source text but missed during discovery.
* `type_confusion`: Assigning an incorrect taxonomy label to an entity or relation.
* `false_link`: Incorrect resolution of an entity to an unrelated canonical node.
* `false_merge`: Erroneous fusion of two distinct theoretical concepts.
* `unsupported_global_relation`: Hallucinated cross-document or cross-chunk relationship lacking source evidence.
* `missed_long_range_relation`: Failure to identify an evidential link spanning distant chunks.
* `argumentative_overgeneration`: Spurious claim or premise extraction from purely descriptive text.
* `theory_overformalization`: Forcing an informal philosophical passage into an overly rigid, distorted formal schema.

### Comparative Evaluation (Section 11 Contract)

To justify architectural decisions, the pipeline natively supports multi-run comparative evaluations
(`EvaluationComparison`, `RunComparison`) across standardized comparison axes:

* `ComparisonAxis.METHOD`: Baseline extraction vs. Dense Retrieval vs. Working Memory.
* `ComparisonAxis.PROMPT`: Zero-shot vs. Few-shot vs. Structured JSON decoding.
* `ComparisonAxis.SCHEMA`: Minimalist schema vs. Rich multi-type schema.
* `ComparisonAxis.CHUNKING`: Fixed token windows vs. Section-aware structural chunking.
* `ComparisonAxis.THRESHOLD`: Cosine similarity cutoffs for linking and GM-GBS matching.
* `ComparisonAxis.CLUSTERING`: Leiden vs. HDBSCAN for entity and argument fusion.

### Minimum Viable Evaluation Setup (Section 13 Contract)

Every release candidate of Episteme must validate against the minimum viable evaluation setup:

* One active benchmark corpus (`SciERC`, `SciFact`, or `Arg-Microtexts`) and one domain review corpus.
* One validated run manifest adhering to `run_manifest.schema.yaml`.
* Automated scoring of intrinsic (GM-GBS, OEP) and extrinsic (MRR, nDCG) metrics.
* One structured human review rubric for global relations and one for theory-layer constructs.
* Complete artifact persistence and schema integrity validation in Neo4j.

---

## What Evaluation Should Not Do

To maintain research integrity, evaluation in Episteme must **never**:

1. **Collapse layers into a single score:** Construction quality (Layers 1 & 2) and theoretical analysis quality (Layer
   3) must remain strictly decoupled.
2. **Rely on anecdotal examples:** Claims of pipeline lift must be substantiated across full dataset splits with
   reported confidence intervals or run variance.
3. **Equate passing unit tests with research validation:** Unit tests verify software correctness; research validation
   requires empirical scoring against benchmarks and human baselines.
4. **Omit reproducibility metadata:** Any metric reported without an immutable run manifest is invalid.

---

## Related Documentation

* **Evaluation Harness Architecture**: [Evaluation Harness](evaluation_harness.md)
* **Structuralist Benchmark (STNB)**: [Structuralist Theory-Net Benchmark](structuralist_theory_benchmark.md)
* **Dataset Portfolio & Strategies**: [Datasets Strategy](datasets.md)
* **Empirical Construction Metrics**: [Empirical Metrics & Validation](metrics.md)
* **Epistemic Metrics Suite (5 Pillars)**: [Theory Metrics Overview](../concepts/theory/metrics/index.md)
* **Philosophical Grounding**: [Epistemology & Wissenschaftstheorie](../concepts/epistemology.md)
* **Knowledge Graphs vs. Theory Graphs**: [Knowledge Graphs vs Theory Graphs](../concepts/kg_vs_tg.md)
