# [ISSUE-061] Proliferation of `getattr`/`hasattr` Reflection Anti-Patterns (`AGENTS.md` Violation) & Incomplete Port Protocols

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-061` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Clean Code, Static Typing, Hexagonal Ports & Protocols, SOLID / ISP / LSP) |
| **Target Package(s)** | `packages/episteme-pipeline` (`pipeline.py`, `runtime/runner.py`, `protocols/`, `phases/`, `post_processing/`) |
| **Priority** | **High** |
| **Status** | `Resolved` |
| **Evaluated Docs & ADRs** | [`AGENTS.md §2`](../../../AGENTS.md), [`docs/architecture/design_patterns_and_standards.md §4.1`](../../../docs/architecture/design_patterns_and_standards.md) |

---

## 1. Current State

[`AGENTS.md §2`](../../../AGENTS.md) explicitly mandates:
> *"Follow development best practices like SOLID, Hexagonal Architecture, ensure the use of dependency inversion and avoid `getattr`."*

Despite this directive, a codebase-wide audit revealed **50+ occurrences of `getattr(...)` and `hasattr(...)`** across the orchestrator (`pipeline.py`, `runtime/runner.py`), protocols (`protocols/fingerprint.py`), and phase implementations (`phases/`, `post_processing/`). As categorized in **[Design Patterns, Clean Code & Architectural Standards §4.1](../../../docs/architecture/design_patterns_and_standards.md)**, these reflection hacks mask four structural defects:

### Category A: Orchestrator Reflection & Silent Config Key Falsification (`pipeline.py`)
1. **String-Matching Runner Names & Falsifying `phase_key = "phase1"` (`pipeline.py#L131-L162`)**:
   ```python
   phase_key = getattr(runner, "phase_key", None)
   if not phase_key:
       name_str = getattr(runner, "name", str(runner))
       if "Phase 1" in name_str:
           phase_key = "phase1"
       ...
   if not hasattr(config, phase_key):
       phase_key = "phase1"
   ```
   If a custom `PhaseRunner` or post-processor defines a `phase_key` that is not a top-level attribute on `PipelineConfig` (e.g., `phase_key = "epistemic_audit"` as shown in `docs/workflow/post_processing/index.md#L230`), `if not hasattr(config, phase_key): phase_key = "phase1"` **silently overwrites its `phase_key` to `"phase1"`**, causing the orchestrator to fingerprint `config.phase1` as its configuration!
2. **Dynamic Attribute Probing on `ExecutionConfig` & `PhaseConfig` (`pipeline.py#L301,L614-L632,L935-L937,L980`)**:
   - Line 301: `use_jev_reranker = getattr(config.phase3, "use_jev_reranker", False)` (even though `use_jev_reranker: bool = False` is a declared field on `Phase3Config` at `config.py#L206`!).
   - Lines 622 & 631: `getattr(self.config.phase2, "entity_linking_prompts", ...)` inside `_prompt_fingerprints()`.
   - Lines 935–937: `store = getattr(entry.runner, "graph_store", None)` and `if hasattr(store, "clear_phase_checkpoints"):` instead of using the `PhaseCheckpointStore` protocol.
   - Line 980: `persist_flag = getattr(self.config.execution, f"persist_{entry.phase_key}_artifacts", True)`.

### Category B: Missing Methods on Port Protocols / ABCs (`protocols/` & `post_processing/`)
1. **`TheoryProjector` ABC Missing `async def aproject` (`post_processing/theoretical_enrichment/projectors.py#L26-L47`)**:
   Because `TheoryProjector` only declares synchronous `def project(...)`, callers in `runner.py#L233`, `projectors.py#L347`, and `solvers.py#L106` all resort to:
   ```python
   if hasattr(self.projector, "aproject"):
       proj_params = await self.projector.aproject(cluster, theory)
   else:
       proj_params = self.projector.project(cluster, theory)
   ```
2. **`Phase3Runner.graph_store` Typed as `ProcessingGraph | EntityGraph` (`phases/phase3_global_relations/__init__.py#L74,L180,L196`)**:
   Because `EntityGraph` does not include `PhaseCheckpointStore`, `Phase3Runner.run` probes `if hasattr(self.graph_store, "filter_unprocessed_items"):` and `if hasattr(self.graph_store, "commit_phase_batch"):`.
3. **Missing `Fingerprintable` Inheritance on Core Strategy Protocols**:
   Because `DecisionEngine`, `GleaningStoppingOracle`, `EntityLinker`, `RelationReranker`, and `CrossEncoder` do not inherit from `Fingerprintable` (or define `fingerprint() -> str` on their protocol), `ner_extractor.py#L111`, `jev_entity_linker.py#L100,L371,L376`, `dense_retrieval_extractor.py#L227,L232`, and `rerankers.py#L160,L524` all poll `if hasattr(self.reranker, "fingerprint") and callable(self.reranker.fingerprint):`.
4. **Hardcoded `_CORE_COMPONENT_NAMES` Allowlist in `protocols/fingerprint.py` (`#L24-L44,L96`)**:
   `is_component()` only recognizes non-`Fingerprintable` objects if their attribute name is in a hardcoded 19-string `frozenset`. As a result, `Phase1Runner.toc_parser`, `Phase1Runner.adapters`, `TheoreticalEnrichmentRunner.inducer`, `TheoreticalEnrichmentRunner.solver`, and `TheoreticalEnrichmentRunner.registry` are completely ignored by `find_components()`.
5. **`RelationReranker` Missing `describe_relation_input` (`dense_retrieval_extractor.py#L976,L989`)**:
   `_describe_reranker_pair_input` probes `getattr(reranker, "describe_relation_input", None)` and `getattr(reranker, "max_length", None)`.

### Category C: Redundant `getattr`/`hasattr` on Strongly-Typed Pydantic Models (`phases/`)
1. ** Undeclared `Phase5Config.max_cluster_size` (`phases/phase5_fusion/leiden_clustering.py#L116`)**:
   `LeidenTheoryClustering` reads `max_cluster_size=getattr(config, "max_cluster_size", 100)` because `max_cluster_size: int = 100` was never added to `Phase5Config` in `config.py#L373-L380`!
2. **Probing Declared Fields on `L1Chunk`, `L2Entity`, `Phase3Config`, `Phase3bConfig`, `Phase4Config`, `Phase4EntityMaturationConfig`**:
   - `working_memory.py#L303-L304`: `getattr(chunk, "metadata", {}) if hasattr(chunk, "metadata") ...` on `chunk: L1Chunk` (where `metadata: dict[str, Any]` is a required Pydantic field!).
   - `phase4_entity_maturation/__init__.py#L118,L136`: `getattr(e, "is_mature", False)` on `e: L2Entity` and `getattr(self.config, "batch_size", 10)` on `Phase4EntityMaturationConfig`—both are declared fields!
   - `phase3_global_relations/__init__.py#L165`: `getattr(self.config, "batch_size", 50)` on `Phase3Config`.
   - `phase3b_consolidation/clustering.py#L125` & `consolidation.py#L156`: `getattr(config, "borderline_merge_prompts", None)` and `getattr(config.verification, "canonical_election_prompts", None)` on `ConsolidationVerificationConfig`.
   - `phase4_argument_mining/classifiers.py#L221,L226,L609`: `getattr(config, "triage_confidence_threshold", ...)` and `getattr(config, "stochastic_audit_rate", ...)` on `Phase4Config`.
3. **Duck-Typing Union Nodes in `argument_clustering.py#L168-L184`**:
   Uses 8 consecutive `hasattr`/`getattr` checks to inspect `TheoryAtom | L2Entity` instead of `isinstance(node, TheoryAtom)` / `match node:`.

---

## 2. Why This Causes Problems

- **Defeats Static Type Checking & IDE Refactoring**: Renaming a config field or protocol method silently falls back to the default in `getattr(obj, "old_name", default)` instead of failing fast in `mypy`/`pytest` (as happened with `Phase5Config.max_cluster_size`).
- **Silent Cache Invalidation Bugs**: Custom post-processors have their `phase_key` rewritten to `"phase1"`, and components not listed in `_CORE_COMPONENT_NAMES` are silently excluded from run manifests.

---

## 3. Proposed Solution & Direct Fixes

Follow **[Design Patterns & Standards §3.1 & §4.1](../../../docs/architecture/design_patterns_and_standards.md)**:

### Step 1: Complete Port Protocols & ABC Contracts
1. In `TheoryProjector` (`post_processing/theoretical_enrichment/projectors.py#L26-L47`), add:
   ```python
   async def aproject(
       self, cluster: EmpiricalModelCluster, theory: TheoryElementDefinition
   ) -> dict[str, Any]:
       """Asynchronously project empirical cluster onto theoretical parameters."""
       return self.project(cluster, theory)
   ```
   and call `await self.projector.aproject(cluster, theory)` directly in `runner.py#L233`, `projectors.py#L347`, and `solvers.py#L106`.
2. Make all strategy protocols/ABCs (`NERExtractor`, `EntityLinker`, `GlobalRelationExtractor`, `RelationReranker`, `DecisionEngine`, `GleaningStoppingOracle`, `ADUSegmenter`, `ACCClassifier`, `ARCClassifier`, `ModalStrengthResolver`, `ArgumentClustering`, `TheoryFusion`, `TheoryInducer`, `TheoryProjector`, `TenabilitySolver`, `AutoToCParser`) inherit from `Fingerprintable` with a default `component_metadata()` implementation, and delete the fragile `_CORE_COMPONENT_NAMES` string set in `protocols/fingerprint.py`.
3. Add `describe_relation_input(self, entity_a: L2Entity, entity_b: L2Entity, env_a: str, env_b: str) -> dict[str, Any]` to `RelationReranker` (`protocols/extractors.py`).

### Step 2: Declare Missing Config Fields & Replace Dynamic Config Probing
1. Add `max_cluster_size: int = 100` to `Phase5Config` (`config.py#L373-L380`).
2. Add `def should_persist_artifacts(self, phase_key: str) -> bool:` on `ExecutionConfig` and `def get_phase_config(self, phase_key: str) -> BaseModel | None:` on `PipelineConfig` (using an explicit dict mapping rather than `getattr` or falling back to `"phase1"`).
3. Replace all 30+ redundant `getattr`/`hasattr` calls on `L1Chunk`, `L2Entity`, `Phase2Config`, `Phase3Config`, `Phase3bConfig`, `Phase4Config`, `Phase4EntityMaturationConfig`, and `Phase5Config` with direct typed attribute access.
4. In `argument_clustering.py#L168-L184`, replace the 8 `hasattr`/`getattr` calls with structural pattern matching (`match node: case TheoryAtom(): ... case L2Entity(): ...`).

---

## 4. Acceptance Criteria

- [x] `rtk grep "getattr\|hasattr" packages/episteme-pipeline/episteme_pipeline/` returns zero occurrences in `pipeline.py`, `runtime/`, `phases/`, and `post_processing/`.
- [x] Custom `PhaseRunner`s and post-processors retain their declared `phase_key` in `Pipeline.__init__` without ever being reassigned to `"phase1"`.
- [x] All phase strategy protocols inherit from `Fingerprintable`, and `find_components()` discovers `toc_parser`, `adu_segmenter`, `acc_classifier`, `inducer`, `projector`, and `solver` without relying on `_CORE_COMPONENT_NAMES`.
