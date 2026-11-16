# Pipeline API Reference

The main pipeline orchestrator and core execution interfaces.

## Pipeline Class

::: episteme_pipeline.pipeline.Pipeline
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Pipeline Construction

Pipelines are constructed by providing all required components explicitly, allowing for maximum flexibility in
configuration.

### Example Usage

```python
from episteme_pipeline import Pipeline
from episteme_pipeline.graph import (
    Neo4jGraphReader,
    Neo4jGraphWriter,
    Neo4jProcessingGraph,
)

# Configure graph stores
graph_reader = Neo4jGraphReader(url, username, password, database)
projection_graph = Neo4jGraphWriter(url, username, password, database)
checkpoint_store = Neo4jProcessingGraph(url, username, password, database)

# Configure LLM components
llm = LiteLLM(model="openai/gpt-4o-mini", api_key=api_key)
embed_model = LiteLLMEmbedding(model_name="openai/text-embedding-3-small", api_key=api_key)

# Build phases
phases = [
    Phase1Runner(cfg.phase1, llm=llm, embed_model=embed_model, graph_store=projection_graph),
    Phase2Runner(cfg.phase2, cfg.graph_schema, llm=llm, embed_model=embed_model, graph_store=checkpoint_store),
    # ... additional phases
]

# Create pipeline
pipeline = Pipeline(
    phases=phases,
    config=cfg,
    graph_reader=graph_reader,
    projection_graph=projection_graph,
    checkpoint_store=checkpoint_store,
)
```

## Core Methods

### run

::: episteme_pipeline.pipeline.Pipeline.run
    options:
      show_root_heading: false
      show_root_toc_entry: false

### run_from_phase

::: episteme_pipeline.pipeline.Pipeline.run_from_phase
    options:
      show_root_heading: false
      show_root_toc_entry: false

### resume_from_run

::: episteme_pipeline.pipeline.Pipeline.resume_from_run
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Utility Methods

### phase_boundaries

::: episteme_pipeline.pipeline.Pipeline.phase_boundaries
    options:
      show_root_heading: false
      show_root_toc_entry: false

### get_run_report

::: episteme_pipeline.pipeline.Pipeline.get_run_report
    options:
      show_root_heading: false
      show_root_toc_entry: false

### get_run_artifacts

::: episteme_pipeline.pipeline.Pipeline.get_run_artifacts
    options:
      show_root_heading: false
      show_root_toc_entry: false
