# [ISSUE-063] Phase 1–3 Domain & Concurrency Defects: LaTeX ToC Post-Conversion Bug, Word-Count Token Overwrite, Concurrent Working Memory Race Condition, Unchecked `CrossEncoder`, and Missing Confidence Filter

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-063` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Phase 1–3 Workflow Bugs, Concurrency Safety, Domain Correctness) |
| **Target Package(s)** | `packages/episteme-pipeline` (`phases/phase1_foundation/`, `phases/phase2_entity_discovery/`, `phases/phase3_global_relations/`) |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **Evaluated Docs & ADRs** | [`docs/workflow/1_data_foundation/index.md`](../../docs/workflow/1_data_foundation/index.md), [`docs/workflow/2_entity_discovery/index.md`](../../docs/workflow/2_entity_discovery/index.md), [`docs/workflow/3_relation_extraction/index.md`](../../docs/workflow/3_relation_extraction/index.md), [`docs/architecture/design_patterns_and_standards.md §3.6`](../../docs/architecture/design_patterns_and_standards.md) |

---

## 1. Current State & Identified Defects

Auditing Phases 1, 2, and 3 against their specifications in `docs/workflow/` uncovered five concrete domain and concurrency bugs:

### Defect 1 (Phase 1): `AutoToCParser` Runs `LaTeXToCParser` on Already-Converted Markdown Text
In [`Phase1Runner._process_document()` (`phases/phase1_foundation/__init__.py#L183-L187`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase1_foundation/__init__.py#L183-L187):
```python
adapter = find_adapter(path, self.adapters)
markdown = adapter.convert(path, bib_paths=bib_paths or None)

# Extract document structural anchor via ToC Parser
toc_anchor = self.toc_parser.parse(text=markdown, document_title=path.stem, path=path)
```
When `path` is a `.tex` file (e.g., `kant_critique.tex`):
1. `TexAdapter.convert(path)` invokes Pandoc and converts the LaTeX source into **Markdown** (`# Transcendental Aesthetic`, `## Section 1`).
2. `self.toc_parser.parse(text=markdown, document_title=path.stem, path=path)` passes both `text=markdown` and `path=Path("kant_critique.tex")`.
3. In [`LaTeXToCParser.can_handle()` (`phases/phase1_foundation/toc_parser.py#L118-L122`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase1_foundation/toc_parser.py#L118-L122), the first strategy checks `if p.suffix.lower() in (".tex", ".latex", ".sty"): return True`.
4. `LaTeXToCParser` wins because `path.suffix == ".tex"`, and then searches `text` (which is already converted to Markdown!) for `\section{...}` regexes (`_LATEX_SECTION_RE`), finding **zero matches** and returning `[f"{document_title} (No LaTeX section commands detected)"]` on every `.tex` file!
Additionally, `TexAdapter.convert()` (`adapters/tex_adapter.py#L53`) runs a synchronous blocking `subprocess.run(["pandoc", ...])` directly on the `asyncio` event loop inside `asyncio.gather`.

### Defect 2 (Phase 1): `L1Chunk.token_count` Overwritten with Naive Whitespace `len(raw.text.split())`
In [`Phase1Runner._process_document()` (`phases/phase1_foundation/__init__.py#L255`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase1_foundation/__init__.py#L255):
```python
chunk = L1Chunk(
    ...
    token_count=len(raw.text.split()),
)
```
Although `chunk_section()` in `phases/phase1_foundation/chunker.py#L68-L88` computes accurate BPE token counts via `tiktoken` (`cl100k_base`), `RawChunk` (`chunker.py#L112-L129`) does not store `token_count`. `Phase1Runner` therefore overwrites `L1Chunk.token_count` with `len(raw.text.split())` (whitespace word count, undercounting German/English philosophical BPE tokens by ~35%), contradicting [`docs/workflow/1_data_foundation/index.md#L36`](../../docs/workflow/1_data_foundation/index.md#L36).

### Defect 3 (Phase 2): Concurrent `asyncio.gather` Data Race on Shared `EpisodicWorkingMemoryManager` & Duplicate Batch Entities
In [`Phase2Runner._process_batch()` (`phases/phase2_entity_discovery/__init__.py#L279-L280,L335-L352`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/__init__.py#L279-L280):
```python
# _process_batch:
tasks = [self._process_chunk(chunk, anchor=anchor) for chunk in chunks]
results = await asyncio.gather(*tasks, return_exceptions=True)

# _process_chunk:
entities, triples, memory_update, boundary_detected, transitional_summary = await self.ner_extractor.extract(
    chunk_id=chunk.id,
    chunk_text=chunk.text,
    schema=self.schema,
    memory=self.working_memory_manager.state,
    anchor=effective_anchor,
)
self.working_memory_manager.process_step(
    chunk=chunk,
    state_delta=memory_update,
    semantic_boundary_detected=boundary_detected,
    transitional_summary=transitional_summary,
)
```
- **Working Memory Race Condition**: All `batch_size=10` concurrent chunk tasks read the **exact same stale `self.working_memory_manager.state`** ($S_{t_0}$) before any LLM request finishes. Then, as the 10 requests complete in arbitrary network latency order (e.g., chunk 8 finishes before chunk 1), each mutates `self.working_memory_manager.state` and `self.eviction_handler._last_section_path` out of document order—triggering false section-boundary evictions (`self.state.reset()`) mid-chapter!
- **Intra-Batch Duplicate `LinkedEntityArtifact`s**: When the same entity appears in multiple chunks within the same batch, `all_entities` (`phase2_entity_discovery/__init__.py#L209,L228-L235`) accumulates multiple `L2Entity` instances with the same `entity.id` (each carrying only a single chunk's `source_chunk_ids = [chunk_id]`), emitting duplicate `LinkedEntityArtifact` envelopes with identical `artifact_id`s instead of merging their `source_chunk_ids`.

### Defect 4 (Phase 2): `DenseEntityLinker.link` Crashes with `AttributeError` When `cross_encoder` Is `None` (Default)
In [`Phase2Runner.__init__()` (`phases/phase2_entity_discovery/__init__.py#L164-L170`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/__init__.py#L164-L170), `DenseEntityLinker` is selected as the default linker whenever `embedding_model` is provided, with `cross_encoder: CrossEncoder | None = None`.
Yet in [`DenseEntityLinker.link()` (`phases/phase2_entity_discovery/sota_entity_linker.py#L291-L294`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/sota_entity_linker.py#L291-L294):
```python
cross_inputs = [(T_n, G_k_struct) for G_k_struct in top_G_structs]
cross_scores = normalize_scores(self.cross_encoder.predict(cross_inputs))
```
`self.cross_encoder.predict(cross_inputs)` is called unconditionally without checking `if self.cross_encoder is not None:`! Whenever `cross_encoder` is `None`, linking crashes on the second batch with `AttributeError: 'NoneType' object has no attribute 'predict'`. Additionally, `self.cross_encoder.predict(...)` is synchronous CPU/GPU inference called directly on the async event loop without `asyncio.to_thread`.

### Defect 5 (Phase 3): `DenseRetrievalGlobalRelationExtractor` Ignores `global_relation_confidence_threshold` & Zero-Norm Guard
In [`DenseRetrievalGlobalRelationExtractor` (`phases/phase3_global_relations/dense_retrieval_extractor.py`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/dense_retrieval_extractor.py):
1. **Missing Confidence Threshold Check (`#L758-L799`)**: Unlike `TAGRelationExtractor._extract_pair()` (`tag_extractor.py#L247`), `DenseRetrievalGlobalRelationExtractor._extract_pair()` never checks `if raw.confidence < self.config.global_relation_confidence_threshold: return None`! Any LLM relation with `has_relation=True` (even `confidence=0.05`) is accepted.
2. **Missing Zero-Norm Guard in Cosine Similarity (`#L412-L413`)**:
   ```python
   norms = np.linalg.norm(entity_vectors, axis=1, keepdims=True)
   normalized_vectors = entity_vectors / norms
   ```
   Omits `norms[norms == 0] = 1e-10`, causing `NaN` propagation if any entity vector is all zeros.

---

## 2. Proposed Solution & Direct Fixes

### Fix 1 (Phase 1 ToC & Token Count):
1. In `Phase1Runner._process_document()` (`phases/phase1_foundation/__init__.py#L183-L188`), either parse the raw file before `adapter.convert` when `path.suffix == ".tex"`, or pass `path=None` to `self.toc_parser.parse(text=markdown, document_title=path.stem, path=None)` because `markdown` is already normalized Markdown text! Also run `await asyncio.to_thread(adapter.convert, path, bib_paths=bib_paths or None)`.
2. In `phases/phase1_foundation/chunker.py#L112-L129`, add `token_count: int` to `RawChunk` (populated with `current_tokens` inside `chunk_section`), and in `phases/phase1_foundation/__init__.py#L255`, set `token_count=raw.token_count` and `"section_path": raw.chapter_title` in `chunk.metadata`.

### Fix 2 (Phase 2 Working Memory Ordering & Entity Deduplication):
1. Scope `EpisodicWorkingMemoryManager` per `source_doc_id` (or chapter) and process sequential state updates deterministically in `chunk.sequence_index` order (see **[Design Patterns & Standards §3.6](../../docs/architecture/design_patterns_and_standards.md)**).
2. In `Phase2Runner` (`phases/phase2_entity_discovery/__init__.py#L220-L235`), deduplicate `all_entities` by `entity.id`—merging `source_chunk_ids` across all chunks in which the entity appeared—before upserting and building `LinkedEntityArtifact`s.

### Fix 3 (Phase 2 `DenseEntityLinker.link` Null-Safe Cross-Encoder):
In [`phases/phase2_entity_discovery/sota_entity_linker.py#L291-L297`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/sota_entity_linker.py#L291-L297):
```python
if self.cross_encoder is not None:
    cross_inputs = [(T_n, G_k_struct) for G_k_struct in top_G_structs]
    raw_scores = await asyncio.to_thread(self.cross_encoder.predict, cross_inputs)
    final_scores = normalize_scores(raw_scores)
else:
    final_scores = [float(s) for s in top_scores]
```

### Fix 4 (Phase 3 Confidence Threshold & Zero-Norm Guard):
1. In `DenseRetrievalGlobalRelationExtractor._extract_pair()` (`dense_retrieval_extractor.py#L761`), add:
   ```python
   if not raw.has_relation or not raw.relation_type or raw.confidence < self.config.global_relation_confidence_threshold:
       return None
   ```
2. In `DenseRetrievalGlobalRelationExtractor._generate_dense_candidates()` (`dense_retrieval_extractor.py#L412-L413`), use `norms[norms == 0] = 1e-10` (or the shared `cosine_similarity_matrix` utility from `ISSUE-065`).

---

## 3. Acceptance Criteria

- [ ] Ingesting a `.tex` document in Phase 1 produces a valid Markdown-parsed `GlobalStructuralAnchor` rather than `"(No LaTeX section commands detected)"`.
- [ ] `L1Chunk.token_count` matches `chunker._count_tokens(chunk.text)` rather than `len(chunk.text.split())`.
- [ ] `EpisodicWorkingMemoryManager` state transitions execute deterministically in `sequence_index` order without `asyncio.gather` data races, and `Phase2Runner` emits at most one `LinkedEntityArtifact` per unique `entity.id` with merged `source_chunk_ids`.
- [ ] `DenseEntityLinker.link()` succeeds when `cross_encoder=None` by falling back to bi-encoder cosine scores, and offloads `cross_encoder.predict` via `asyncio.to_thread`.
- [ ] `DenseRetrievalGlobalRelationExtractor._extract_pair()` enforces `self.config.global_relation_confidence_threshold` and guards against zero-norm embeddings.
