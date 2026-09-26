# Examples

This directory contains example scripts for running the Grund GLP pipeline.

## Available Examples

### `pipeline_full_run.py` (Recommended for Construction)
An example running the complete 7-runner pipeline pass across all 5 conceptual phases as defined in `docs/concepts/pipeline_architecture.md`. Uses `LiteLLM` for OpenAILike generation and embeddings, `SentenceTransformerCrossEncoderReranker` for HuggingFace cross-encoder relation reranking, and Neo4j graph stores via `Pipeline.for_task()`.

### `pipeline_evaluation_run.py` (Recommended for Evaluation)
A comprehensive, modular demonstration of the **Episteme Evaluation Feature**. Showcases all 5 evaluation pillars:
1. **Bourbaki Structuralist Decomposition**: Evaluates Model Component Completeness ($MCC \ge 1.0$), Axiomatic Omission Rate ($AOR = 0.0$), and Property Fidelity Score ($PFS$) using `epistemetrics`.
2. **Specialization Poset Verification**: Directed acyclic graph (DAG) integrity, root element conformity ($B(TN) = \{T_0\}$), and transitive reduction $F_1$.
3. **Schema-Driven Polarity Concordance**: Verifies epistemic polarity alignment and detects contradiction inversions (`polarity_accuracy`, `polarity_conflict_rate`) using `SchemaConfig`. Also demonstrates semantic soft matching (GM-GBS) and topological error tracking (OEP Hallucination & Omission Rates).
4. **Extrinsic Downstream Retrieval**: Evaluates competency queries against in-memory indexed theory graphs computing MRR, Hits@1/3/10, and nDCG.
5. **Comparative Baseline Benchmarking**: Side-by-side comparative benchmarking against `BaselineNaiveKG` with metric delta analysis ($\Delta F_1$, $\Delta MRR$, token cost, latency) and persisted Markdown/JSON reports.

```bash
# Run all evaluation scenarios
uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py

# Run specific scenarios
uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode structuralist
uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode polarity
uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode retrieval
uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode baseline
uv run python packages/episteme-pipeline/examples/pipeline_evaluation_run.py --mode manifest
```

### `kg_construction.py`
An example script demonstrating knowledge graph construction with customized extractor pipelines and Langfuse observability integration.

### `main_fixed.py`
A minimal working example that shows basic pipeline setup.

### `main.py` (Deprecated)
An outdated example that contains references to non-existent methods. This example should not be used.

## Running Examples

To run any example:

```bash
uv run python examples/[script_name].py
```

Make sure to set the required environment variables:
- `OPENAI_API_KEY` (or appropriate key for your LLM provider)
- `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`

You can also create a `.env` file in the project root with these variables.
