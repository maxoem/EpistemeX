# Evaluation Pipeline Example Walkthrough

This guide documents [`pipeline_evaluation_run.py`](../../packages/episteme-pipeline/examples/pipeline_evaluation_run.py), demonstrating how to verify constructed theory graphs across formal model-theoretic, structural, semantic, and extrinsic dimensions.

---

## 1. Overview & Capabilities

The evaluation script exercises all five core pillars of the **Episteme Evaluation Framework**:

| Scenario | Focus | Key Metrics |
| :--- | :--- | :--- |
| **1. Bourbaki Structuralist Evaluation** | Model component decomposition & Specialization posets ($\alpha$) | $MCC \ge 1.0$, $AOR = 0.0$, $PFS \ge 0.4$, DAG strict partial order |
| **2. Schema-Driven Polarity Concordance** | Epistemic alignment & topological error tracking | `polarity_accuracy`, `polarity_conflict_rate`, GM-GBS alignment, OEP $HR$ & $OR$ |
| **3. Extrinsic Downstream Retrieval** | In-memory competency query resolution | MRR, Hits@1, Hits@3, Hits@10, nDCG |
| **4. Comparative Baseline Benchmarking** | Side-by-side comparative benchmarking | $\Delta F_1$, $\Delta MRR$, token cost, latency deltas |
| **5. Manifest-Driven Batch Evaluation** | Declarative YAML execution & report persistence | Structured JSON & Markdown reports in `evaluation/reports/` |

---

## 2. Zero-Dependency Offline Execution

In accordance with Dependency Inversion (DIP), the evaluation script operates by default in **pure in-memory mode**:
- **Zero Database Connectivity**: Uses `InMemoryGraphStore` instead of requiring a live Neo4j instance.
- **Zero API Tokens / Credentials**: Uses deterministic hash embeddings (`default_deterministic_embedder`) for competency retrieval and GM-GBS matching.
- **Pure Symbolic Logic**: Formal Bourbaki structuralist decomposition and specialization poset verification rely on `epistemetrics` graph theory algorithms rather than non-deterministic LLM judge calls.

---

## 3. Running the Example

### Run All Scenarios (Default)

```bash
rtk uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py
```

### Run Specific Scenarios

```bash
# Scenario 1: Formal Bourbaki structuralist decomposition & posets
rtk uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode structuralist

# Scenario 2: Polarity concordance and OEP hallucination/omission rates
rtk uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode polarity

# Scenario 3: Extrinsic information retrieval competency benchmarking
rtk uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode retrieval

# Scenario 4: Comparative baseline evaluation (Pipeline vs BaselineNaiveKG)
rtk uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode baseline --baseline naive_kg

# Scenario 5: Declarative manifest execution & report persistence
rtk uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode manifest --manifest packages/episteme-pipeline/episteme_pipeline/evaluation/manifests/eval_stnb.yaml
```

---

## 4. Programmatic In-Memory Evaluation

You can invoke the evaluation harness directly in code or tests:

```python
import asyncio
from episteme_pipeline.evaluation.harness import EvaluationHarness
from episteme_pipeline.contracts.domain import TheoryNet

harness = EvaluationHarness()

# Evaluate predicted TheoryNet against gold standard JSON-LD
report = asyncio.run(
    harness.evaluate_in_memory(
        predicted=my_theory_net,
        gold="packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld",
        run_id="principia_cpm_eval",
        strategy="structuralist",
    )
)

print(f"Evaluation outcome: {report.evaluation_id}")
print(report.summary)
```

---

## 5. Related Documentation

- [Evaluation Harness Specification](../research/evaluation_harness.md)
- [Structuralist Theory Benchmark (STNB)](../research/structuralist_theory_benchmark.md)
- [Evaluation Methodology](../research/evaluation_methodology.md)
- [Empirical Metrics & Validation](../research/metrics.md)
