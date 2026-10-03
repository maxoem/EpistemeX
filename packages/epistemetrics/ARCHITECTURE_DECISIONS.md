# Architecture Decisions: Epistemetrics (v0.1.0)

## 1. Context, Core Philosophy & Package Boundaries

**Epistemetrics** is a sovereign Python library dedicated to the structural, argumentation, and formal epistemic evaluation of scientific theory graphs.

### Package Scope & Boundaries
- **Relationship to the Pipeline (`episteme-pipeline`):** The graph generation pipeline is an external consumer. Epistemetrics does **not** perform document ingestion, chunking, or raw text-to-graph extraction; **it assumes the theory graph is already available and constructed**.
- **Relationship to the Studio (`episteme-studio`):** The analytical frontend is an external consumer that visualizes theory graphs and requests rigorous mathematical, argumentation, and epistemic evaluations.
- **Core Domain:** Epistemetrics provides the formal theory graph domain model, mathematical graph representations, computational argumentation semantics (Phan Minh Dung), explanatory coherence networks (Paul Thagard), and philosophy-of-science metrics (Gerhard Schurz, Imre Lakatos).

To maintain theoretical integrity, the architecture strictly decouples the **formal ontology and epistemic evaluation engine** from external storage engines, pipeline ingestion mechanics, and frontend presentation layers.

---

## 2. Core Architectural Pattern: Hexagonal Architecture (Ports and Adapters)

**Decision:** The library follows a strict Hexagonal Architecture.  
**Rationale:** `epistemetrics` must remain sovereign and mathematically deterministic. It has zero coupling to specific databases, pipeline orchestrators, or LLM providers.

### Architectural Layers
1. **The Domain Core (Interior Hexagon):** Contains the formal ontology, semantic base classes, mathematical graph algorithms, and epistemic evaluation strategies. It has zero dependencies on external state, network, or storage I/O.
   - `core/`: Pure Pydantic boundary models (DTOs), semantic base classes, and domain exception hierarchy.
   - `graph/`: Runtime `TheoryGraph` (NetworkX-backed), builder, and domain query representations.
   - `analysis/`: Epistemic metrics, structural metrics, and argumentation algorithms (NumPy/NetworkX).
2. **Ports (`epistemetrics.io.ports`):** Pure abstract interfaces (`typing.Protocol`) defined entirely in domain terms that external systems must satisfy.
3. **Adapters (`epistemetrics.adapters`):** Concrete implementations of those interfaces (e.g., a Neo4j database repository or an in-memory test double).

### Hexagonal Boundary Rules
- **Exception-Translation Boundary:** Adapters **must** intercept all infrastructure-specific exceptions (e.g., `neo4j.exceptions.ServiceUnavailable`, Cypher syntax errors, connection timeouts) and re-raise them as strongly-typed domain exceptions defined in `core/exceptions.py` (e.g., `RepositoryConnectionError`, `GraphNotFoundError`, `AdapterError`). Infrastructure exceptions must never leak into the domain core or consumer code.
- **Optional Extras Boundary:** Base installation (`pip install epistemetrics`) requires only `networkx`, `numpy`, and `pydantic`. External adapters requiring third-party drivers (such as Neo4j) are packaged as optional dependencies (`pip install epistemetrics[neo4j]`) and are imported lazily/conditionally.

---

## 3. Data Structures & The Runtime / Boundary Seam

**Decision:** Maintain an explicit, bidirectional seam between Pydantic boundary DTOs and the NetworkX runtime domain object.

### The Seam: Boundary DTOs vs. Runtime Graph
- **Boundary DTOs (`epistemetrics.core.models`):**
  - Pure Pydantic v2 models (`TheoryGraphDTO`, `TheoryAtomDTO`, `TheoryRelationDTO`, `EpistemicStateDTO`).
  - Function as validated, immutable data transfer objects at all I/O boundaries (what the pipeline sends in, what the database persists, and what the Studio receives).
  - Pydantic models **never** hold a `networkx.Graph` instance as an internal field, eliminating serialization cliffs and `arbitrary_types_allowed` anti-patterns.
- **Runtime Domain Object (`epistemetrics.graph.theory_graph.TheoryGraph`):**
  - Encapsulates an in-memory `networkx.MultiDiGraph` (enabling parallel relations between the same pair of nodes, e.g., both attacking and specializing, or distinct evidential supports).
  - Provides domain-specific indexing, neighborhood queries, and epistemic graph operations.
- **Canonical Conversion Protocol:**
  - `TheoryGraph.from_dto(dto: TheoryGraphDTO) -> TheoryGraph`
  - `theory_graph.to_dto() -> TheoryGraphDTO`
  - Importers and exporters operate strictly on DTOs and `TheoryGraph` instances.

### Concurrency & Thread Safety
- NetworkX graphs are mutable and not thread-safe.
- **Architectural Policy:** Once constructed, a `TheoryGraph` is treated as effectively immutable during evaluation passes. Analysis routines must not mutate the underlying graph topology or node/edge attributes.
- Studio or parallel evaluation pipelines can safely execute concurrent analyses by sharing read access to frozen views (`nx.freeze`) or lightweight thread-isolated copies (`theory_graph.copy()`). Operations requiring hypothetical graph mutation (e.g., pruning defeaters or counterfactual analysis) must explicitly work on isolated copies.

### Identity & ID Mapping
- Domain entities use stable, canonical domain IDs (UUIDs or deterministic URI hashes).
- Database internal IDs (e.g., Neo4j `<id>` / `elementId`) are strictly forbidden across domain interfaces and ignored during ingestion/conversion.

---

## 4. Database Integration & Persistence (Neo4j)

**Decision:** Pure persistence repository in v0.1. Drop the premature "push-down / pull-up" split.

### Why Drop GDS Push-Down for v0.1?
- **The Reproducibility Hazard:** Neo4j Graph Data Science (GDS) and NetworkX implement algorithms like PageRank and centrality with different defaults (damping factors, convergence tolerances, normalization, tie-breaking). Delegating topology to GDS while running epistemology in NetworkX means the same theory graph produces different metric scores depending on whether a Neo4j adapter or an in-memory adapter is wired in.
- **Hexagonal Principle:** Swapping an adapter must never alter a domain-level epistemic evaluation.
- **Footprint:** Scientific theory graphs fit comfortably in local memory.
- **Policy:** In v0.1, Neo4j acts purely as a persistence store. All topological and epistemic calculations run in Python via NetworkX and NumPy, guaranteeing absolute reproducibility across environments. GDS push-down may be reintroduced in the future solely as an explicit, flagged performance optimization accompanied by strict parity benchmark test suites.

### Technology-Neutral Repository Port (`SubgraphQuery`)
To prevent leaky backend abstractions, the repository port accepts a domain-defined query object rather than backend-specific query strings (e.g., Cypher):

```python
from dataclasses import dataclass
from typing import Protocol
from epistemetrics.core.models import TheoryGraphDTO, EpistemicStateDTO

@dataclass(frozen=True)
class SubgraphQuery:
    """Domain specification for subgraph retrieval."""
    root_ids: set[str] | None = None
    depth: int | None = None
    node_types: set[str] | None = None
    relation_types: set[str] | None = None
    polarities: set[int] | None = None
    include_metadata: bool = True
    limit: int | None = None

class GraphRepository(Protocol):
    """Hexagonal port for theory graph persistence and retrieval."""
    def fetch_subgraph(self, query: SubgraphQuery) -> TheoryGraphDTO: ...
    def save_graph(self, graph: TheoryGraphDTO) -> None: ...
    def save_epistemic_state(self, graph_id: str, state: EpistemicStateDTO) -> None: ...
```

- **Neo4j Adapter (`adapters/neo4j.py`):** Compiles `SubgraphQuery` into parameterized Cypher queries, fetches records, and converts them to `TheoryGraphDTO`.
- **In-Memory Adapter (`adapters/inmemory.py`):** Translates `SubgraphQuery` into NetworkX graph traversals, providing a zero-dependency, ultra-fast test double for unit testing without spinning up Neo4j.

---

## 5. Domain Ontology: Extensible Schema with Normed Polarities

**Decision:** An open, extensible taxonomy anchored by normed semantic base classes, paired with a default schema aligned with `episteme-pipeline`.

### Extensibility Model
Scientific disciplines and extraction pipelines use diverse terminologies. Rather than enforcing a rigid closed enum, `epistemetrics` models relations through **normed epistemic base classes**:

1. **`AttackRelation` (`R_attack`, polarity = `-1`):** Adversarial and defeater relationships (e.g., rebuttal, undercutting, falsification, contradiction, inhibitory links).
2. **`SupportRelation` (`R_support`, polarity = `+1`):** Evidential, deductive, and inferential relationships (e.g., premise support, logical entailment, deduction, coherentist links).
3. **`StructuralRelation` (`R_structural`, polarity = `0`):** Mereological, taxonomic, and associative relationships (e.g., specialization, part-of, instance-of, constraint).

Custom domain schemas can define or register bespoke relation types, provided each relation declares its normed polarity class. Core epistemic algorithms (Dung grounded semantics, Thagard coherence relaxation, Schurz empirical creativity) operate against the normed polarities, insulating the evaluation engine from upstream naming variations.

### Default Working Schema (`epistemetrics.core.schema`)
Epistemetrics provides a built-in default schema matching the `episteme-pipeline` L2/L3 specification:

- **Component / Node Types:**
  - `ObservationUnit`: Empirical raw data nodes containing observational terms.
  - `EmpiricalStatement`: Statements containing empirical and logical concepts.
  - `TheoreticalHypothesis`: Core laws and theoretical scope statements.
  - `CoreExpansion`: Auxiliary hypotheses forming a protective superstructure.
  - *(L2 Context Entities: `Concept`, `Theory`, `Work`, `Person`, `Institution`)*
- **Relation Types & Polarities:**
  - **Negative (`-1`):** `ATTACKS`, `UNDERCUTS`, `REFUTES`, `CONTRADICTS`, `INHIBITS`.
  - **Positive (`+1`):** `SUPPORTS`, `ENTAILS`, `DEDUCES`, `COHERES_WITH`, `REDUCES_TO`.
  - **Neutral (`0`):** `SPECIALIZES`, `CONSTRAINS`, `PART_OF`, `INSTANCE_OF`, `RELATED_TO`.

### Cyclic Graph Semantics
- Theory graphs and argumentation networks are **directed cyclic graphs** (DiGraphs / MultiDiGraphs).
- In formal argumentation, mutual rebuttal (A attacks B, B attacks A) and cyclical argumentation are legitimate theoretical structures. In explanatory coherence, mutual reinforcement forms feedback loops.
- **Policy:** Acyclicity is **never** enforced as a global graph constraint.
  - Evaluators supporting cycles (Dung abstract argumentation, Thagard connectionist networks) handle directed cyclic graphs natively.
  - Evaluators requiring DAGs (such as strict deductive derivation hierarchies) operate on projected subgraphs (e.g., filtering on `DEDUCES`/`ENTAILS` edges) or report cycle anomalies in validation reports.

### Schema Versioning
All boundary DTOs include a `schema_version: str = "0.1.0"` attribute adhering to Semantic Versioning. Changes to schema contracts follow standard deprecation cycles.

---

## 6. Evaluative LLM Integration (Async-First)

**Decision:** Scoped strictly to qualitative epistemic evaluation, defined via an async-first protocol.

### Scope Demarcation
- Raw document extraction and graph construction belong to `episteme-pipeline`.
- Epistemetrics uses LLMs strictly for optional, downstream **evaluative tasks** (e.g., qualitative rubric grading, epistemic explanation synthesis, or assessing semantic premise plausibility).

### Async-First Protocol
Real-world evaluation pipelines require concurrent, batched LLM calls:

```python
from typing import Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class AsyncLLMProvider(Protocol):
    """Asynchronous protocol for evaluative LLM operations."""
    async def evaluate_structured(self, prompt: str, schema: type[T]) -> T: ...

class SyncLLMProvider(Protocol):
    """Synchronous convenience wrapper for scripts and notebooks."""
    def evaluate_structured(self, prompt: str, schema: type[T]) -> T: ...
```

### Validation & Error Boundary
The injected LLM provider handles low-level HTTP retries. If structured response validation fails after configured attempts, the provider must raise a domain-specific `EpistemicLLMError` rather than leaking vendor-specific exceptions.

---

## 7. Internal Design Patterns

### 1. Two-Tier Validation Strategy (`TheoryGraphBuilder`)
To eliminate performance cliffs when assembling large graphs (thousands of claims and relations):
- **Tier 1 (Syntactic & Local Validation):** Executed during iterative mutation (`add_node`, `add_edge`, `add_nodes_from`, `add_edges_from`). Runs $O(1)$ checks: ID uniqueness, endpoint existence, and polarity/type validity against the active schema. Batch ingestion runs at full NetworkX speed.
- **Tier 2 (Global & Epistemic Validation):** Executed on `.build(validate=True)` or explicitly via `GraphValidator.validate(graph)`. Performs higher-order checks: cycle categorization, disconnected component detection, Dung extension solvability, and constraint tension analysis. Produces a structured `ValidationReport` containing errors, warnings, and theoretical anomalies.

### 2. The Strategy Pattern (`epistemetrics.analysis`)
Epistemic evaluation is pluggable via an `EpistemicEvaluator` protocol:
- Consumers can invoke specific evaluators (`DungArgumentationEvaluator`, `ThagardCoherenceEvaluator`, `SchurzStructuralEvaluator`, `LakatosResilienceEvaluator`) independently or run an aggregate evaluation via `em.evaluate(graph)`.

### 3. The Facade Pattern (`epistemetrics.__init__.py`)
- High-level domain functions (`em.evaluate()`, `em.TheoryGraph`, `em.load_dto()`) are exposed at the package root.
- Optional adapter modules (e.g., Neo4j) are imported lazily to ensure `import epistemetrics` succeeds without optional extras installed.

---

## 8. Package Directory Structure

```text
packages/epistemetrics/
├── pyproject.toml               # Core deps: networkx, numpy, pydantic. Optional: [neo4j]
├── README.md
├── ARCHITECTURE_DECISIONS.md
├── src/
│   └── epistemetrics/
│       ├── __init__.py          # Public Facade (lazy optional imports)
│       ├── core/                # Domain Ontology & Contracts
│       │   ├── __init__.py
│       │   ├── models.py        # Boundary Pydantic DTOs (TheoryGraphDTO, etc.)
│       │   ├── schema.py        # Normed polarity classes (R_attack, etc.) & Default Schema
│       │   └── exceptions.py    # Domain error hierarchy
│       ├── graph/               # Runtime Mathematical Topology
│       │   ├── __init__.py
│       │   ├── theory_graph.py  # NetworkX MultiDiGraph wrapper & DTO conversion
│       │   ├── builder.py       # TheoryGraphBuilder (Two-tier validation)
│       │   ├── query.py         # SubgraphQuery domain specification
│       │   └── validation.py    # Global graph validator & ValidationReport
│       ├── analysis/            # Epistemic & Structural Evaluators (Strategy Pattern)
│       │   ├── __init__.py
│       │   ├── structural.py    # Topology: centrality, density, modularity (NetworkX)
│       │   ├── argumentation.py # Dung abstract argumentation semantics (NumPy)
│       │   ├── coherence.py     # Thagard explanatory coherence networks (NumPy)
│       │   └── philosophy.py    # Schurz empirical creativity, Lakatos hard-core
│       ├── io/                  # Hexagonal Ports & Serialization
│       │   ├── __init__.py
│       │   ├── ports.py         # GraphRepository & AsyncLLMProvider Protocols
│       │   ├── importers.py     # Pipeline & JSON/Dict DTO importers
│       │   └── exporters.py     # Cytoscape / React Flow / Markdown exporters
│       └── adapters/            # Infrastructure Adapters (Optional Extras)
│           ├── __init__.py
│           ├── inmemory.py      # Zero-dependency test double repository
│           └── neo4j.py         # Optional Neo4j persistence adapter
└── tests/                       # Unit and integration test suites
```