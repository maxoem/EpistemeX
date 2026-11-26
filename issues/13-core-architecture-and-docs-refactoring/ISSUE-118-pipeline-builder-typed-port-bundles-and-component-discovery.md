# [ISSUE-118] Replace 23-Argument `Pipeline.for_task` with `PipelineBuilder` Port Bundles & Fix `find_components()`

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-118` |
| **Domain / Category** | `13-Core Architecture & Docs Refactoring` (Composition Root, Dependency Injection, Fingerprinting) |
| **Target Package(s)** | `packages/episteme-pipeline` (`pipeline.py`, `runtime/pipeline_factory.py`), `packages/episteme-contracts` (`fingerprint.py`) |
| **Priority** | **High** |
| **Status** | `Proposal` |
| **Roadmap Horizon** | Horizon 1 & 2 |
| **Prerequisites** | [ISSUE-116](ISSUE-116-extract-episteme-contracts-and-workspace-dependency-inversion.md), [ISSUE-117](ISSUE-117-execution-engine-decomposition-and-post-forward-stage-port.md) |
| **Governing ADR & Plan** | [ADR-0026 Proposal](ADR-0026-PROPOSAL-contract-first-workspace-modular-runtime-and-systems-first-framing.md) \| [Execution Plan (`WP-3`)](EXECUTION-PLAN.md) |

---

## 1. Architectural Problem Statement

Inspection of [`pipeline.py`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py#L239-L264), [`pipeline_factory.py`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L353-L384), and [`protocols/fingerprint.py`](../../packages/episteme-pipeline/episteme_pipeline/protocols/fingerprint.py#L120-L125) reveals three coupled Composition Root defects:

1. **Constructor Parameter Explosion:** `Pipeline.for_task` already accepts **23 keyword arguments** (`llm`, `relation_reranker`, `cross_encoder`, `entity_linker`, `embedding_model`, `config`, `graph_reader`, `projection_graph`, `checkpoint_store`, `event_emitter`, `extra_phases`, `post_processors`, `working_memory_manager`, `decision_engine`, `acc_classifier`, `arc_classifier`, `ner_extractor`, `modal_resolver`, `quality_gates`, `deficit_detector`, `refinement_coordinator`, `task`, plus adding future router/verifier/trajectory ports). Every new subsystem widens the facade constructor and every helper forwarding layer.
2. **Reflective Phase-Scraping in `build_standalone_refinement`:** When `Pipeline(...)` is instantiated directly, `PipelineFactory.build_standalone_refinement` ([`pipeline_factory.py#L353-L384`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L353-L384)) loops over `phases` calling `find_components(phase)` and inspecting attribute names (`comp_key.split(".")[-1] == "llm"`) to scavenge `llm`, `arc_classifier`, `entity_linker`, and `ner_extractor`.
3. **Silent Fingerprint Loss on Slotted Dataclasses (`@dataclass(slots=True)`):** In [`fingerprint.py#L120-L125`](../../packages/episteme-pipeline/episteme_pipeline/protocols/fingerprint.py#L120-L125), `find_components()` inspects objects via `vars(root)`. In Python, `@dataclass(slots=True)` instances have **no `__dict__`**, causing `vars(root)` to raise `TypeError`, which `find_components()` catches and turns into `{}`—**silently erasing nested model/prompt fingerprints from `RunManifest`!**

---

## 2. Typed Port Bundles, `PipelineBuilder` & Dataclass-Safe Discovery

### 2.1 Fix `find_components()` for Dataclasses First (`episteme_contracts/fingerprint.py`)

Extend `find_components()` before introducing dataclass port bundles so attributes on both `__dict__` objects and `dataclasses.is_dataclass(root)` (including `slots=True`) are traversed deterministically without `getattr`:
- Check `dataclasses.is_dataclass(root)` and iterate `dataclasses.fields(root)` using safe dictionary/descriptor access rather than falling into `except TypeError: return {}`.
- Add explicit unit tests verifying nested `StructuredPromptBundle` and `Fingerprintable` components inside `@dataclass(frozen=True, slots=True)` bundles appear in `find_components()` output.

### 2.2 Cohesive Frozen Port-Bundle Dataclasses

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from episteme_contracts.fingerprint import Fingerprintable


@dataclass(frozen=True)
class ModelPorts:
    """Foundational generative, embedding, and candidate-reranking model collaborators."""

    llm: Any
    embedding_model: Any | None = None
    cross_encoder: Any | None = None
    relation_reranker: Any | None = None


@dataclass(frozen=True)
class ExtractionPorts:
    """Phase 2 and Phase 3 entity discovery, linking, and working-memory ports."""

    entity_linker: Any | None = None
    ner_extractor: Any | None = None
    working_memory_manager: Any | None = None


@dataclass(frozen=True)
class ArgumentMiningPorts:
    """Phase 4 argument component/relation classifiers and modal resolvers."""

    acc_classifier: Any | None = None
    arc_classifier: Any | None = None
    modal_resolver: Any | None = None


@dataclass(frozen=True)
class DecisionPorts:
    """System-1 decision engine and inter-phase quality gates."""

    decision_engine: Any | None = None
    quality_gates: Sequence[Any] | None = None


@dataclass(frozen=True)
class RefinementPorts:
    """Top-down closed-loop refinement collaborators and workflow extensions."""

    deficit_detector: Any | None = None
    refinement_coordinator: Any | None = None
    extra_phases: Sequence[Any] = field(default_factory=tuple)
    post_processors: Sequence[Any] = field(default_factory=tuple)
    post_forward_stages: Sequence[Any] = field(default_factory=tuple)


@dataclass(frozen=True)
class StoragePorts:
    """Graph stores, within-phase checkpointing, and domain telemetry ports."""

    graph_reader: Any | None = None
    projection_graph: Any | None = None
    checkpoint_store: Any | None = None
    event_emitter: Any | None = None
```

### 2.3 Fluent `PipelineBuilder` & Explicit `PipelineFactory` Wiring

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from episteme_pipeline.config import PipelineConfig
    from episteme_pipeline.pipeline import Pipeline


class PipelineBuilder:
    """Fluent composition-root builder replacing the 23-parameter ``Pipeline.for_task``.

    Groups optional subsystem overrides into typed port bundles while keeping
    mandatory configuration and primary LLM collaborators explicit.
    """

    def __init__(self, *, config: PipelineConfig, models: ModelPorts) -> None:
        self._config = config
        self._models = models
        self._extraction = ExtractionPorts()
        self._argument_mining = ArgumentMiningPorts()
        self._decision = DecisionPorts()
        self._refinement = RefinementPorts()
        self._storage = StoragePorts()
        self._extensions: dict[str, Any] = {}

    def with_extraction(self, ports: ExtractionPorts) -> PipelineBuilder:
        """Bind Phase 2/3 entity and working-memory overrides."""
        self._extraction = ports
        return self

    def with_argument_mining(self, ports: ArgumentMiningPorts) -> PipelineBuilder:
        """Bind Phase 4 ACC/ARC and modal strength overrides."""
        self._argument_mining = ports
        return self

    def with_decision(self, ports: DecisionPorts) -> PipelineBuilder:
        """Bind System-1 DecisionEngine and quality-gate overrides."""
        self._decision = ports
        return self

    def with_refinement(self, ports: RefinementPorts) -> PipelineBuilder:
        """Bind closed-loop refinement and custom post-forward stages."""
        self._refinement = ports
        return self

    def with_storage(self, ports: StoragePorts) -> PipelineBuilder:
        """Bind graph persistence, checkpointing, and observability ports."""
        self._storage = ports
        return self

    def with_extension(self, key: str, bundle: Any) -> PipelineBuilder:
        """Register an optional capability bundle (e.g., ``'verification'`` ports)."""
        self._extensions[key] = bundle
        return self

    def build(self, *, task: str = "knowledge_graph") -> Pipeline:
        """Construct and wire a complete ``Pipeline`` via ``PipelineFactory``."""
        ...
```

- Notice how clean this makes Suite 12 (`VerificationPorts`): verification/world-model bundles attach via `with_extension("verification", verification_ports)` (or a typed `VerificationPorts` parameter on `PipelineBuilder`) without ever changing existing callers when disabled.
- `PipelineFactory.resolve_components()` wires shared collaborators directly from the bundles—eliminating `build_standalone_refinement`'s reflective scraping over `phases`.

---

## 3. Acceptance Criteria

- [ ] Update `find_components()` in `episteme_contracts/fingerprint.py` to traverse dataclass fields safely (verified for `@dataclass(frozen=True, slots=True)`).
- [ ] Introduce `ModelPorts`, `ExtractionPorts`, `ArgumentMiningPorts`, `DecisionPorts`, `RefinementPorts`, `StoragePorts`, and `PipelineBuilder` in `episteme_pipeline`.
- [ ] Remove the 23-argument `Pipeline.for_task` signature and reflective phase-scraping in `PipelineFactory.build_standalone_refinement` (`[NO LEGACY]`), migrating all tests, examples, and `episteme-studio` callers.
- [ ] Verify manifest `method_fingerprints` capture identical component trees before and after refactoring (`rtk uv run pytest`).
