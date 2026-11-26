# [ISSUE-116] Extract `packages/episteme-contracts/` & Break Workspace Dependency Inversion

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-116` |
| **Domain / Category** | `13-Core Architecture & Docs Refactoring` (Packaging, Dependency Inversion, Pure Domain Contracts) |
| **Target Package(s)** | `packages/episteme-contracts/` (new), `packages/episteme-pipeline/`, `packages/epistemetrics/`, `packages/episteme-studio/` |
| **Priority** | **High** (Blocking Prerequisite for `ISSUE-117`, `ISSUE-118`, and Suite 12 packages) |
| **Status** | `Proposal` |
| **Roadmap Horizon** | Horizon 1 & 2 |
| **Governing ADR & Plan** | [ADR-0026 Proposal](ADR-0026-PROPOSAL-contract-first-workspace-modular-runtime-and-systems-first-framing.md) \| [Execution Plan (`WP-1`)](EXECUTION-PLAN.md) |

---

## 1. Architectural Problem Statement

Currently, [`packages/episteme-pipeline/pyproject.toml`](../../packages/episteme-pipeline/pyproject.toml#L13-L43) bundles pure Pydantic schemas and `Protocol` ports alongside 25+ heavyweight infrastructure dependencies (`neo4j`, `mteb`, `ogb`, `sentence-transformers`, `langfuse`, `igraph`, `nltk`, and 8 `llama-index-*` packages). This creates three cascading problems:

1. **Transitive Bloat Across Consumers:** Any downstream tool—[`episteme-studio`](../../packages/episteme-studio/pyproject.toml#L19-L21), future `episteme-formal` (Lean 4/SMT), or future `episteme-worldmodel` (triage/IR)—inherits the full vector-embedding, Neo4j, and LlamaIndex stack simply to import `TheoryAtom` or `Fingerprintable`.
2. **Parallel Model Duplication:** [`epistemetrics`](../../packages/epistemetrics/src/epistemetrics/__init__.py#L24-L33) maintains standalone `TheoryNode` / `TheoryEdge` dataclasses separately from `TheoryAtom` / `TheoryRelation` because importing `episteme-pipeline` would invert dependencies.
3. **Upward Coupling Inside Pure Contracts:**
   - In [`contracts/domain.py`](../../packages/episteme-pipeline/episteme_pipeline/contracts/domain.py#L1037), `CandidatePair.key` imports `stable_fingerprint` upward from `episteme_pipeline.runs.fingerprints`.
   - In [`contracts/domain.py`](../../packages/episteme-pipeline/episteme_pipeline/contracts/domain.py#L912), `TheoryRelation.polarity` imports `DEFAULT_SCHEMA` from `episteme_pipeline.schema.default_schema`.
   - In [`protocols/refinement.py`](../../packages/episteme-pipeline/episteme_pipeline/protocols/refinement.py#L16-L23), pure protocols import `ArtifactCollection` and `ArtifactExecutionContext` under `TYPE_CHECKING` from runtime `artifacts/execution.py`.

---

## 2. Target Package Layout (`packages/episteme-contracts/`)

Create `packages/episteme-contracts/` with **`src/` layout**, `requires-python = ">=3.13"`, and **strictly `pydantic>=2.0` + Python stdlib** dependencies:

```text
packages/episteme-contracts/
├── pyproject.toml                  # Only runtime dependency: pydantic>=2.0
├── tests/
│   └── test_contracts_purity.py    # Fresh-namespace import & fingerprint round-trip tests
└── src/
    └── episteme_contracts/
        ├── __init__.py
        ├── fingerprint.py          # Fingerprintable, stable_fingerprint, is_component, find_components
        ├── schema.py               # SchemaConfig, DEFAULT_SCHEMA, COMPONENT_PARTITIONS, EPISTEMIC_STATUSES
        ├── domain.py               # L1*, L2*, TheoryAtom, TheoryRelation, TheoryNet, Deficits, RefinementDelta
        ├── curation.py             # EpistemicCurationLedger, RelationOverride (extracted from phase_contracts.py)
        ├── signatures.py           # FormalSignatureEntry, FormalSignatureLedger, FormalSignatureAmendment
        └── protocols/
            ├── __init__.py
            ├── query.py            # Read-only TheorySubgraphQuery (L3) & GraphReader contracts
            ├── decision.py         # DecisionEngine, ModalStrengthResolver
            ├── extractors.py       # EmbeddingModel, CrossEncoder, RelationReranker
            ├── phase.py            # PhaseRunner & PipelineInput pure protocol surface
            └── quality_gate.py     # EpistemicQualityGate, QualityGateResult
```

### Crucial Clean-Extraction Rules
1. **Relocate `stable_fingerprint` First:** Move deterministic SHA-256 canonical JSON serialization (`stable_fingerprint`) from `episteme_pipeline/runs/fingerprints.py` into `episteme_contracts/fingerprint.py`, eliminating `CandidatePair.key`'s upward import.
2. **Isolate Persistence from Protocols:** Keep `ArtifactCollection`, `JsonArtifactStore`, `RunManifest`, and neo4j codecs **inside `episteme-pipeline`**. Instead of leaking `ArtifactCollection` into protocol signatures, define a narrow read-only L3 query protocol (`TheorySubgraphQuery`) in `episteme_contracts/protocols/query.py` and implement it via `EpistemicStateView` inside `episteme-pipeline`.
3. **Zero Legacy Shims (`AGENTS.md` §2 `[NO LEGACY]`):** Migrate all internal imports cleanly in `episteme-pipeline` and `episteme-studio` rather than leaving forwarding stubs behind.

---

## 3. Core Read-Only Query & Fingerprint Contracts

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from episteme_contracts.domain import TheoryAtom, TheoryRelation


@runtime_checkable
class TheorySubgraphQuery(Protocol):
    """Read-only L3 query interface decoupling algorithms from artifact storage.

    Implemented by ``EpistemicStateView`` during batch runs in ``episteme-pipeline``
    and by live session snapshots in ``episteme-studio`` or extension plugins.
    """

    def poset_ancestors(self, atom_ids: tuple[str, ...]) -> list[TheoryAtom]:
        """Return root ``T_0`` and intermediate specialization ancestors for ``atom_ids``."""
        ...

    def k_hop_cone(
        self,
        atom_ids: tuple[str, ...],
        *,
        perspective: str,
        depth: int = 2,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation], tuple[str, ...]]:
        """Return perspective-filtered atoms, relations, and excluded suppositional IDs."""
        ...

    def contrastive_anchors(
        self,
        entity_ids: tuple[str, ...],
        *,
        perspective: str,
    ) -> list[TheoryAtom]:
        """Return polarity-opposed asserted atoms sharing canonical ``L2Entity`` referents."""
        ...
```

---

## 4. Downstream Consumers Unlocked

| Package | Old Dependency Pattern | New Clean Dependency Pattern |
| :--- | :--- | :--- |
| **`episteme-pipeline`** | Self-contained monolith | `episteme-pipeline -> episteme-contracts`, `epistemetrics` |
| **`episteme-studio`** | Forces full `episteme-pipeline` runtime install even for schema/view models | Reads domain contracts & response models from `episteme-contracts`; uses `episteme-pipeline` strictly in job runner service |
| **`epistemetrics`** | Maintains uncoupled `TheoryNode`/`TheoryEdge` copies | Can offer lightweight optional adapter mapping `TheoryNet` (`episteme-contracts`) $\leftrightarrow$ `TheoryGraph` (`epistemetrics`) without pulling ML deps |
| **`episteme-formal` & `episteme-worldmodel`** (Suite 12) | Blocked by pipeline coupling | Depend cleanly downward on `episteme-contracts` only |

---

## 5. Acceptance Criteria

- [ ] Scaffold `packages/episteme-contracts/` (`src/` layout, `requires-python = ">=3.13"`, only `pydantic>=2.0` dependency) and register in root [`pyproject.toml`](../../pyproject.toml).
- [ ] Move `Fingerprintable`, `stable_fingerprint`, `SchemaConfig` / `DEFAULT_SCHEMA`, pure L1–L4 Pydantic models, `EpistemicCurationLedger`, and narrow protocols into `episteme_contracts`.
- [ ] Verify `import episteme_contracts` succeeds in an isolated environment with zero `neo4j`, `torch`, `numpy`, or `llama_index` packages installed.
- [ ] Migrate all callers across `episteme-pipeline` and `episteme-studio` with zero legacy shims and verify full `rtk uv run pytest` pass.
