# [ISSUE-120] Documentation, `README.md` & Terminology Redesign: "Systems-First Core, Epistemology-Scoped Domain"

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-120` |
| **Domain / Category** | `13-Core Architecture & Docs Refactoring` (Technical Documentation, Information Architecture, `README.md`, `zensical.toml`) |
| **Target Paths** | [`README.md`](../../README.md), [`zensical.toml`](../../zensical.toml), [`docs/index.md`](../../docs/index.md), [`docs/overview.md`](../../docs/overview.md), [`docs/architecture/overview.md`](../../docs/architecture/overview.md), [`docs/concepts/glossary.md`](../../docs/concepts/glossary.md) |
| **Priority** | **High** |
| **Status** | `Proposal` |
| **Roadmap Horizon** | Horizon 1 & 2 |
| **Prerequisites** | Coordinates with [ISSUE-116](ISSUE-116-extract-episteme-contracts-and-workspace-dependency-inversion.md) – [ISSUE-119](ISSUE-119-monorepo-uv-packaging-hygiene-and-plugin-isolation.md) |
| **Governing ADR & Plan** | [ADR-0026 Proposal](ADR-0026-PROPOSAL-contract-first-workspace-modular-runtime-and-systems-first-framing.md) \| [Execution Plan (`WP-5`)](EXECUTION-PLAN.md) |

---

## 1. Strategic Answer: Should We Shift Toward a Technological / Language-Engineering Perspective?

**Yes—at the entry points, runtime abstractions, and public positioning; NO—not at the expense of erasing our formal epistemological core.**

Right now, Episteme has a **framing inversion**: readers encounter heavy philosophy of science (*Structuralist Metatheory, Sneed/Balzer, Lakatos, Toulmin, Holons, Hermeneutic Refinement*) before seeing what the software actually *is* from an engineering standpoint (**a deterministic, content-addressed NLP & hypergraph compilation engine**). That creates three concrete costs:

1. **Obscured Transferability:** Engineers evaluating Episteme for legal contracts, clinical guidelines, policy analysis, or software/formal specifications dismiss it as a "philosophy-only tool," even though 80% of the runtime (`Span-Grounded Chunking`, `Context-Disambiguated Entity Resolution`, `Conformal System-1/2 LLM Cascades`, `Argument Hypergraph Construction`, `Artifact-Native Cache Invalidation`) is general language-engineering infrastructure.
2. **Contributor Onboarding Friction:** New developers looking at [`docs/architecture/overview.md`](../../docs/architecture/overview.md) or [`README.md`](../../README.md) must decode epistemic jargon to locate basic mechanics (pipeline orchestration, database projection, quality gates, conformal gating).
3. **Imprecise System Abstractions:** Mixing philosophical labels onto runtime infrastructure (calling general post-forward recovery `HermeneuticRefinementCoordinator` or homeostatic DAG circuit breakers `EpistemicQualityGate`) conflates *how the engine runs* with *what Layer-3 schema is modeled*.

The fix is a **Two-Tier Framing Architecture**:
- **Tier 1 (Technological, NLP & Systems Perspective):** Own `README.md`, onboarding guides, pipeline/orchestrator docs, package API references, and generic runtime abstractions. Speak clearly in CS, NLP, and distributed-systems terms.
- **Tier 2 (Formal Epistemology & Graph-Math Differentiator):** Own `docs/concepts/`, `docs/research/`, `packages/epistemetrics/`, and the Layer-3 `TheoryNet` metamodel—explaining *why* dialectical hypergraphs (`D-QBAF`), model-theoretic structuralism ($M_{pp}, M_p, M$), and coherence metrics solve where naive vector RAG and flat entity-relation KGs fail.

---

## 2. Concrete Audit of Current `README.md` & `docs/` Defects

Inspection of [`README.md`](../../README.md), [`zensical.toml`](../../zensical.toml), [`docs/index.md`](../../docs/index.md), [`docs/overview.md`](../../docs/overview.md), and [`docs/architecture/overview.md`](../../docs/architecture/overview.md) surfaced the following verified defects:

| Location | Concrete Defect Observed on Disk | Required Fix |
| :--- | :--- | :--- |
| [`zensical.toml#L24`](../../zensical.toml#L24) vs. [`docs/index.md`](../../docs/index.md) & [`docs/overview.md`](../../docs/overview.md) | Two nearly duplicate home pages exist (`docs/overview.md` titled `T-Episteme` mapped as Zensical `Home`, vs. `docs/index.md` titled `Episteme`), and `docs/overview.md#L59` links to non-existent `../paper/index.md`. | Consolidate into a single canonical `docs/index.md`, update `"Home" = "index.md"` in `zensical.toml`, remove `docs/overview.md` (`[NO LEGACY]`), and delete broken `../paper/` links. |
| [`README.md#L92`](../../README.md#L92) & [`docs/index.md#L82`](../../docs/index.md#L82) | Claims `"5-phase extraction engine"` while [`zensical.toml#L59-L68`](../../zensical.toml#L59-L68) and the codebase execute **8 forward phases** (`1, 2, 3, 3b, 4, 4b, 5, 6`) plus post-forward stages. | Update to accurate stage counts: **8-stage forward DAG + pluggable post-forward stages** (`Theoretical Enrichment`, `Closed-Loop Refinement`, and opt-in `Verification`). |
| [`docs/index.md#L69`](../../docs/index.md#L69) | Claims `"18 Architecture Decision Records (ADRs)"`, whereas [`docs/adr/index.md`](../../docs/adr/index.md#L33) already lists ADRs through `0024` (+ `0016a/b`, and proposed `0025`/`0026`). | Update count dynamically / use accurate range (`25+ ADRs`). |
| [`docs/architecture/overview.md#L21`](../../docs/architecture/overview.md#L21) | Claims `Python >= 3.12` while root [`pyproject.toml#L5`](../../pyproject.toml#L5) requires `>=3.13`; also still references `GraphReader` / `_run_refinement_stage()` pre-refactor contracts. | Update to `Python >= 3.13` and align diagrams/prose with `episteme-contracts`, 5-service runtime, `PostForwardStage`, and `PipelineBuilder`. |
| [`README.md#L1-L95`](../../README.md#L1-L95) & `docs/index.md` | Leads with philosophical terminology (`Structuralist Philosophy of Science`, `Holon Tree`) before introducing core NLP/LLM/Graph systems capabilities; `epistemetrics` & `episteme-studio` sit after long theoretical tables. | Adopt the Systems-First `README.md` structure and 5-pillar Zensical navigation below. |

---

## 3. Systems $\leftrightarrow$ Epistemology Rosetta Stone (Terminology Alignment Policy)

We do **not** strip away domain science from `TheoryAtom` or `epistemetrics`. Instead, we bridge the two vocabularies explicitly so neither audience is lost:

| NLP / CS / Systems Concept (Tier 1 — Front Door & Runtime) | Epistemological / Formal Concept (Tier 2 — Layer-3 & Research) | Where Each Term Belongs |
| :--- | :--- | :--- |
| **Content-Addressed Artifact DAG & Lineage Caching** | Immutable run provenance & structural lineage | `README.md`, `execution_engine` / `ManifestTracker`, `docs/architecture/` |
| **Calibrated System-1 / System-2 LLM Cascade (`ConformalCalibrator`)** | Neuro-symbolic perception gating (`Jev`, TypeSafe conformal risk) | `README.md`, `decision/`, `docs/reference/` |
| **Context-Scoped Entity & Sense Disambiguation** | `EntityConception` stratification & `POLYSEMY_COLLISION` splitting | `workflow/2_entity_discovery/`, `workflow/4_entity_maturation/`, `ADR-0023` |
| **Perspective & Conditional Scope Isolation** | Intensional scoping (`asserted`, `attributed`, `suppositional`, `historical`) | `workflow/4_argument_mining/`, `ADR-0023` |
| **Argument Hypergraph & Continuous Equilibrium Solver** | `TheoryNet`, Toulmin warrants & `D-QBAF` gradual semantics ($\tau^*$) | Both: intro in Systems terms in `README.md`, full math in `docs/concepts/` |
| **Closed-Loop Post-Forward Recovery (`PostForwardStage`)** | Top-down Hermeneutic Refinement ($L_4/L_3 \to L_2/L_1$) | Rename doc titles & `PostForwardStage` runtime port in Systems terms; keep domain concepts in `ADR-0024` & `docs/concepts/` |
| **Formal / Programmatic Claim Verifiers** | Opt-in Lean 4 / SMT deductive oracle & Type-B counterfactual models | `episteme-formal`, `episteme-worldmodel`, `Suite 12` |

---

## 4. Target Blueprint for Root `README.md` & `zensical.toml`

### 4.1 New [`README.md`](../../README.md) Narrative Flow (Systems-First)
1. **Hero & Concise Technical Definition:** *"Modular neuro-symbolic pipeline compiling unstructured scientific and technical text into span-grounded knowledge graphs, defeasible argument hypergraphs, and formally verifiable theory networks."*
2. **Why Stratified Argument Hypergraphs Beats Flat RAG / KG Triples:** Side-by-side comparison showing structural engineering wins (explicit contradiction/support polarity, conditional scoping, character-offset provenance, deterministic DAG caching, conformal LLM gating) alongside a compact 4-row **Systems $\leftrightarrow$ Epistemology Rosetta Stone**.
3. **Modular Workspace Package Matrix (Matching Post-`ISSUE-116` Architecture):**
   - `episteme-contracts`: Zero-heavy-dep Pydantic v2 domain & protocol contracts
   - `episteme-pipeline`: 8-stage forward DAG + `PostForwardStage` engine + Neo4j dual-graph projector
   - `epistemetrics`: Standalone graph topology, QBAF equilibrium & scientific-virtue evaluation library
   - `episteme-studio`: FastAPI + React/TS workbench for run DAG inspection, diffs, and HITL curation
   - Opt-in extensions (`episteme-formal`, `episteme-worldmodel`) clearly labeled as optional plugins
4. **Architecture Diagram:** Accurate 3-layer (`Span Provenance` $\to$ `Resolved Entity-Relation Graph` $\to$ `Argument Hypergraph / TheoryNet`) + decomposed runtime services (`PipelineBuilder`, `PostForwardRunner`, `Neo4j` / `ArtifactStore`).
5. **Quickstart & `PipelineBuilder` Python Example:** Replace legacy snippets with clean `PipelineBuilder` usage + `uv sync` + `episteme-studio` + standalone `epistemetrics` snippet.

### 4.2 Redesigned `zensical.toml` 5-Pillar Navigation (Extending [`ADR-0008`](../../docs/adr/0008-diataxis-documentation-framework.md))
Consolidate the current 6 slightly overlapping pillars into **5 crisp Diátaxis pillars**:
1. **Home (`docs/index.md`):** Unified landing page linking straight into Quickstart, Engineering Architecture, Reference, and Research.
2. **Getting Started:** Prerequisites (`Python >= 3.13`, `uv`), Quickstart, Studio Workbench, Docker Deployment, Tutorials, Task How-To Guides.
3. **Language & Pipeline Engineering:** 8-stage forward pipeline breakdown (`1, 2, 3, 3b, 4, 4b, 5, 6`), `PostForwardStage` post-processing, Constrained Decoding & Conformal Decision Cascades, Observability & Langfuse Events.
4. **Architecture & API Reference:** System Design (`ManifestTracker`, `PhaseExecutor`, `ArtifactRunModel`), `ADR Register (0001–0026)`, and **Per-Package Reference Trees** (`episteme-contracts`, `episteme-pipeline`, `epistemetrics`, `episteme-studio`, plus optional `episteme-formal`/`worldmodel`).
5. **Epistemology, Metrics & Research:** Conceptual Foundations (`kg_vs_tg`, `formal_graph_model`, `theory_nets_and_topologies`), complete **Epistemetrics Suite** (Structural Topology, Epistemic Coherence, Empirical Power, Theory Dynamics, Metatheoretical), Evaluation Methodology, Roadmap & Future Research.

---

## 5. Acceptance Criteria

- [ ] Consolidate `docs/index.md` and `docs/overview.md` into one canonical `docs/index.md`, update `zensical.toml` `"Home" = "index.md"`, and delete broken `../paper/index.md` references.
- [ ] Rewrite root [`README.md`](../../README.md) with accurate package table, 8-stage + post-forward diagram, Systems-First positioning, `PipelineBuilder` quickstart, and the Systems $\leftrightarrow$ Epistemology Rosetta Stone.
- [ ] Reorganize `zensical.toml` into the 5-pillar Diátaxis structure with per-package API reference subsections and fix all stale version/phase/ADR counts (`Python >= 3.13`, 8 forward stages, 25+ ADRs) across `docs/`.
- [ ] Verify clean documentation build via `rtk uv run zensical build --strict` with zero broken relative links.
