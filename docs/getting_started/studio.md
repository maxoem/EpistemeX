# Episteme Studio Workbench

**Episteme Studio** is an interactive visual workbench, orchestration pipeline, and analytical environment for computational epistemology, structuralist philosophy of science, and argument mining.

---

## Quick Launch & Operating Modes

Episteme Studio can be launched immediately via the monorepo CLI.

### Instant Demo Mode (Zero Setup Required)
To explore theory graphs and interface features without connecting to Neo4j or an LLM gateway, launch the canned demonstration server:

```bash
uv run episteme-studio serve --demo
```

Once running, navigate to **`http://127.0.0.1:8000`** in your browser. Demo mode populates the explorer with pre-computed scientific runs, epistemic metrics, and graph diffs.

### Production Mode (Live Database Binding)
To inspect your actual pipeline runs and query your live Neo4j 5.x database:

```bash
uv run episteme-studio serve --host 127.0.0.1 --port 8000
```

### CLI Command Options
```text
options:
  -h, --help            show this help message and exit
  --host HOST           Host interface to bind (default: 127.0.0.1)
  --port PORT           Port to listen on (default: 8000)
  --demo                Launch with canned demonstration runs and mock dependencies
  --read-only           Disallow disk/database write mutations and sandbox execution
  --runs-dir DIR        Path to directory containing run manifests (default: .pipeline_runs)
  --artifacts-dir DIR   Path to directory containing artifact envelopes (default: .pipeline_artifacts)
  --dev [URL]           Proxy frontend requests to Vite dev server (default: http://127.0.0.1:5173)
  --token TOKEN         Authentication token (required when binding to external hosts)
```

All flags can alternatively be configured via environment variables prefixed with `EPISTEME_STUDIO_`:
* `EPISTEME_STUDIO_DEMO_MODE=true`
* `EPISTEME_STUDIO_READ_ONLY=true`

### Operating Modes & Security Model

| Mode | Trigger | Mutation Policy | System 1 Decision Engine Behavior |
| :--- | :--- | :--- | :--- |
| **Development / Local** | Default (`serve`) | Full read/write access. Pipeline runs can be triggered; settings persisted. | Runs local inference backend (Apple MLX on macOS, PyTorch on CUDA/Linux, or ONNX). |
| **Canned Demo** | `--demo` | Canned runs loaded into UI without external databases or LLM API keys. | Interactive Decision Playground routes to deterministic simulation stub. |
| **Hardened Public Sandbox** | `--demo --read-only` | All write endpoints (`POST /api/runs`, `PUT /api/engine/settings`, file uploads) return `403 Forbidden`. | Strictly forced to offline simulation stub (~12ms latency, 0 tokens, 0 network requests, no model weights downloaded). |

---

## Core Workbench Views

Episteme Studio organizes epistemic analysis into five primary views:

```mermaid
flowchart TD
    Workbench[Episteme Studio Workbench] --> Explorer[1. Explorer View]
    Workbench --> Execution[2. Execution View]
    Workbench --> CypherConsole[3. Cypher Console]
    Workbench --> Comparison[4. Run Comparison Engine]
    Workbench --> Engine[5. Decision Engine & Settings]

    Explorer -->|Visualize| Layers[L1 Sources, L2 Concepts, L3 TheoryNet]
    Execution -->|Compose & Launch| DAG[Pre-Flight Checks & Cost Forecasting]
    CypherConsole -->|Query| Sandbox[Read-Only Ad-Hoc Cypher Playground]
    Comparison -->|Diff Runs| Deltas[Set-Theoretic Deltas & KDE Shifts]
    Engine -->|Tune & Test| Dual[System 1/2 Calibration & Conformal Sandbox]
```

---

### View 1: Multi-Layer Theory Canvas (`Explorer`)

The main canvas renders the generated theory graph using a GPU-accelerated force-directed layout:

| Graph Element | Visual Encoding | Epistemic Function |
| :--- | :--- | :--- |
| **Layer 1 (L1 Sources)** | Blue nodes | Ground-truth academic sources and text chunk anchors. |
| **Layer 2 (L2 Concepts)** | Green nodes | Extracted domain concepts, named entities, and empirical terms. |
| **Layer 3 (L3 TheoryNet)** | Purple nodes | Higher-level theoretical constructs, latent hypotheses, and structural laws. |
| **Dialectical Support** | Green directed vectors | Formal argumentative warrant: `SUPPORT` relations. |
| **Dialectical Attack** | Red directed vectors | Formal argumentative objections: `ATTACK` relations. |
| **Unscoped / Drift** | Orange nodes | Entities or assertions operating outside axiomatic boundaries. |

#### Canvas Controls
* **Global Entity Search (`⌘K`)**: Instant fuzzy lookup across all extracted concepts and theoretical terms.
* **Epistemic Lenses**: Filter the visible canvas according to structuralist partitions:
  - **Empirical Base ($M_{pp}$)**: Isolates non-theoretical observations, empirical data, and grounded claims.
  - **Theoretical Postulates ($M$)**: Isolates abstract axioms, latent variables, and structural laws (Stegmüller 1976 / Balzer 1987).

---

### View 2: Pipeline Orchestrator (`Execution`)

The Execution view provides interactive DAG composition:
* **Thinking Level Switch**: Regulate model reasoning compute (`Off`, `Low`, `Medium`, `High`, `Custom`) for complex relation extraction.
* **Pre-Flight Readiness Inspection**: Static configuration validator verifying Neo4j index status and endpoint responsiveness prior to dispatch.
* **Cost & Latency Forecasting**: Real-time pre-execution estimates calculating anticipated compute duration and API invocation costs.
* **Reproducible CLI Generator**: Generates headless bash commands corresponding to active UI configurations for remote compute cluster execution.

---

### View 3: Safe Database Playground (`Cypher Console`)

* **Safety Sandbox**: Enforces a strict **Read-Only** mode to protect generated theoretical structures, embeddings, and relations from accidental deletion during exploratory queries.
* **Sample Queries Catalog**: Quick-insert templates for centrality, bridging concepts, and argument chain inspection.
* **Keyboard Shortcut Dispatch (`⌘↩`)**: Execute ad-hoc structural queries directly against the active graph namespace.

---

### View 4: Run Comparison & Set-Theoretic Deltas (`Comparison`)

Evaluate how varying prompt strategies, temperature settings, or underlying model architectures alter theory reconstruction:

* **Visual Canvas Diff**: Color-coded node and edge highlighting showing structural growth, retention, and pruning between Run A and Run B.
* **Kernel Density Estimation (KDE)**: Overlapping density curves visualizing shifts in semantic extraction confidence across runs.
* **Set-Theoretic Delta Cardinality**:
  - **Intersection ($A \cap B$)**: Invariant entities and edges verified across both configurations.
  - **Pruned Set ($A \setminus B$)**: Baseline structural elements omitted by the candidate configuration.
  - **Discovered Set ($B \setminus A$)**: Novel entities and dialectical relations introduced by the candidate run.

---

### View 5: System 1 Decision Engine & Playground (`Engine Settings`)

Configure the neuro-symbolic dual-process architecture (System 1 vs. System 2) and tune confidence gating:

* **Dual-Process Configuration**: Regulate confidence threshold ($\tau$), conformal coverage significance ($\alpha$), and stochastic audit sampling rates.
* **Granular Phase Gates**: Toggle fast-exit bypasses across Phase 1 noise gating, Phase 2 entity linking, Phase 3 pair pre-gating, Phase 4 gleaning oracles, and Phase 5 theory fusion.
* **Interactive Decision Playground**: Live evaluation sandbox to test categorical choices, binary noul gates, and continuous scores against scientific or philosophical text spans.
* **Demo Sandbox Protection**: When running in `--demo` or `--read-only` mode:
  - Hyperparameter modifications are locked in read-only mode (`PUT /api/engine/settings` returns `403 Forbidden`).
  - The Playground executes safely via an in-memory, deterministic simulation stub (`POST /api/engine/decision/test`), yielding calibrated conformal sets and token savings metrics in ~12ms without downloading model weights or invoking external APIs.

---

## Next Steps

- Execute a headless extraction pass: [First Run Tutorial](first_run.md)
- Explore quantitative epistemic evaluation: [Epistemetrics Suite](../concepts/theory/metrics/index.md)