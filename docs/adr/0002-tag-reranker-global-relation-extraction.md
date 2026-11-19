# [0002] TAG + LLM Reranker for Global Relation Extraction (not GNN)

Status: Accepted

## Context

Phase 3 must extract relations between entities that appear in different chunks or distant sections of a document — well
beyond the context window of a single LLM call. Two families of approaches were considered:

1. **GNN-based** — train a Graph Attention Network (GATv2, AGGCN, etc.) on the entity graph to embed entities into a
   shared vector space, then use cosine clustering to identify relations. Requires a training corpus with labelled
   philosophical relations.

2. **TAG + reranker** — represent the document as a Text-Attributed Graph (chunks as nodes, NEXT/CONTAINS edges,
   embeddings as node attributes). For each candidate entity pair, retrieve a local subgraph envelope via embedding
   similarity, then pass the envelope to an LLM for triple decoding.

`docs/feature/warnings.md` explicitly flagged the GNN approach as premature: "*Before any GNN
implementation/training/use a complete evaluation of surveys should be performed in order to identify the SOTA
approach.*"

## Decision

Use the **TAG + LLM reranker** approach as the default `GlobalRelationExtractor` implementation (`TAGRelationExtractor`
in `packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/tag_extractor.py`, alongside
`DenseRetrievalGlobalRelationExtractor` in `dense_retrieval_extractor.py`).

Candidate pair blocking is structural (shared `source_chunk_ids`), which reduces the O (N²) pair space to O (E·k) —
entities that co-occur in the same chunk. For each candidate pair the phase retrieves both entities' k-hop graph
neighbourhoods, formats them as a compact text envelope, and calls the LLM with `GLOBAL_RELATION_PROMPT` to decode a
typed triple. Relations below `Phase3Config.confidence_threshold` are discarded.

The `GlobalRelationExtractor(ABC)` interface is defined separately from the implementation so that a GNN-based extractor
can be substituted later without touching any phase runner code.

## Clarification: Zensical Tags vs. Pipeline TAG

- **Zensical Documentation Tags (`zensical.toml`):** Refers to the static site generator metadata tagging feature
  (`tags: [adr, phase-3, llm-reasoning]`) used to organize documentation pages across MkDocs.
- **Text-Attributed Graph (TAG):** Refers to the pipeline graph structure where nodes and edges hold rich textual
  attributes (chunk text, concept definitions, provenance metadata), which are fed into LLM prompts or rerankers.

## Roadmap Integrations (Pan et al., 2024)

1. **In-Context Graph2Text Prompting vs. Retraining:**
   Following Pan et al. (Sec 4.2.2 & 7.3), we prioritize **in-context Graph-to-Text prompting** (Mindmap, ChatRule, CoK
   style) over model fine-tuning/retraining. Base LLMs evolve rapidly, making parameter fine-tuning fragile, whereas
   in-context prompting allows zero-shot graph-guided reasoning across arbitrary provider models.

2. **Long-Tail Entity Handling (Dict-BERT Style In-Context Glossaries):**
   To address long-tail entities without causing Knowledge Noise in dense scientific texts, we prioritize **Selective
   In-Context Micro-Glossaries**—querying the graph store for mature concept node definitions and appending top-ranked
   1-line concept definitions to the LLM prompt. Exploring continuous pseudo-token vector injection (DKPLM / Graph-LLM
   style) remains a future research topic requiring trained projection adapters.

3. **Top-Down Refinement Re-Invocation ([ADR-0024](0024-closed-loop-hermeneutic-refinement.md)):**
   During bounded hermeneutic refinement cycles, `GlobalRelationExtractor.extract_pairs` and TAG neighborhood envelopes are re-invoked top-down strictly on targeted entity pairs—specifically by `ConceptionConceptSplitter` (`episteme_pipeline/refinement/concept_splitter.py`) after splitting a polysemous hub entity into sense-disambiguated nodes—to discover previously conflated inter-concept relations without re-running Phase 3 globally.

## Alternatives considered

- **GNN (GATv2 / AGGCN)** — pros: O (N log N) at scale, embedding-space generalisation; cons: requires labelled training
  data for philosophical texts (none exists), infrastructure (PyG, CUDA), and a contrastive loss strategy to keep
  embedding spaces isomorphic across documents. Deferred until a labelled corpus is available.
- **Full O (N²) LLM comparison** — reliable but prohibitively expensive for documents with hundreds of entities. The TAG
  blocking reduces call count by ~90 % in typical philosophical texts.
- **SPARQL/Cypher rule-based extraction** — fast, but cannot capture the semantic nuance of philosophical relations
  (IMPLIZIERT vs SETZT_VORAUS vs WIDERSPRICHT).

## Consequences

- The `GlobalRelationExtractor` instance wired in `PipelineFactory.resolve_components()` is **shared** between Phase 3 and Phase 4 ARC to avoid duplicate instantiation (see ADR 0004), and can be injected into localized refinement handlers (`ConceptionConceptSplitter`, `LLMTheoryGuidedPremiseRecoverer`) to execute targeted top-down pair extraction (`GlobalRelationExtractor.extract_pairs`) and TAG envelope formatting over refined subgraphs ([ADR-0024](0024-closed-loop-hermeneutic-refinement.md)).
- Blocking by shared chunks misses cross-chunk relations between entities that never co-occur. This is mitigated by dense retrieval (`DenseRetrievalGlobalRelationExtractor`), Phase 3b Latent Graph Consolidation (aliases sharing no common chunk), and localized top-down pair re-extraction during refinement passes.
- GNN transition path: implement `GNNRelationExtractor(GlobalRelationExtractor)` and inject via
  `Phase3Runner(global_extractor=GNNRelationExtractor(...))`.

## Related

- `packages/episteme-pipeline/episteme_pipeline/protocols/extractors.py` — `GlobalRelationExtractor(Fingerprintable, ABC)`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/tag_extractor.py` — TAG implementation
- `packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/dense_retrieval_extractor.py` — Dense retrieval implementation
- [ADR-0024: Closed-Loop Hermeneutic Refinement](0024-closed-loop-hermeneutic-refinement.md) — Top-down `extract_pairs` re-invocation after concept splitting
- `docs/research/future_research_goals.md` — Literature Analysis & Future Research Goals

