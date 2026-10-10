# Docker Deployment Guide

Episteme Studio is distributed as a multi-architecture container image via the **GitHub Container Registry (GHCR)**.

```text
ghcr.io/maxoem/episteme-studio:latest
```

Supported architectures: `linux/amd64`, `linux/arm64` (Apple Silicon, ARM servers).

---

## 1. Quick Start: Interactive Demo Mode

To explore Episteme Studio without installing Node, Python, or external databases, launch the container in `--demo` mode:

```bash
docker run -d --rm \
  --name episteme-studio \
  -p 8000:8000 \
  ghcr.io/maxoem/episteme-studio:latest
```

Open your browser at [http://localhost:8000](http://localhost:8000).

In `--demo` mode:
* Packaged demonstration datasets (*Festinger 1959*, *Physics*, *Psychology*) are automatically loaded into the workspace.
* Graph projection runs directly from canned artifact envelopes.
* All epistemic metrics (QBAF gradual semantics, PageRank, Leiden communities) run deterministically in-memory via `epistemetrics`.
* No Neo4j instance or LLM API keys are required.

---

## 2. Inspecting Your Own Pipeline Runs

If you have executed pipeline runs on your host machine, mount your local manifest and artifact directories into the container:

```bash
docker run -d --rm \
  --name episteme-studio \
  -p 8000:8000 \
  -v $(pwd)/.pipeline_runs:/app/.pipeline_runs \
  -v $(pwd)/.pipeline_artifacts:/app/.pipeline_artifacts \
  -v $(pwd)/evaluation/reports:/app/evaluation/reports \
  ghcr.io/maxoem/episteme-studio:latest \
  serve --host 0.0.0.0 --port 8000
```

---

## 3. Full Stack with Neo4j & Langfuse (`docker-compose`)

For users who want the complete local development and evaluation environment (Episteme Studio workbench, Neo4j graph database, and local Langfuse LLM observability with PostgreSQL), use the provided `docker-compose.yml`:

```bash
docker compose up -d
```

This launches the full integrated stack:
1. **Neo4j Community** on ports `7474` (browser) and `7687` (Bolt) with persistent volume `neo4j_data`.
2. **Langfuse Server (v2)** on port `3000` backed by **PostgreSQL 16** with persistent volume `langfuse_db_data`.
   - **Headless Auto-Provisioning**: Automatically bootstraps the organization (`Episteme`), project (`Episteme`), admin account, and API keys on first launch.
   - **Web UI**: Access at [http://localhost:3000](http://localhost:3000) using email `admin@episteme.local` and password `episteme_password`.
3. **Episteme Studio** on port `8000` connected to Neo4j via Bolt and pre-authenticated to Langfuse for immediate trace streaming.
   - **Workbench UI**: Access at [http://localhost:8000](http://localhost:8000).

To stop the services:
```bash
docker compose down
```

To wipe persistent database volumes when resetting:
```bash
docker compose down -v
```

---

## 4. Public Hosting & Hardened Sandbox Mode

When hosting Studio publicly as an online demonstration, enable `--read-only` mode and run the container with zero-trust flags:

```bash
docker run -d \
  --name episteme-studio-public \
  -p 8000:8000 \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --memory=512m \
  --cpus=1.0 \
  -e EPISTEME_STUDIO_DEMO_MODE=true \
  -e EPISTEME_STUDIO_READ_ONLY=true \
  ghcr.io/maxoem/episteme-studio:latest \
  episteme-studio --host 0.0.0.0 --port 8000 --demo --read-only
```

Additionally consider creating a separate docker network:

```bash
docker network create --internal demo-isolated
docker run ... --network demo-isolated ...
```

### Configuration Flags & Environment Variables

| Setting | CLI Flag | Environment Variable | Default | Purpose in Public Hosting |
| :--- | :--- | :--- | :--- | :--- |
| `demo_mode` | `--demo` | `EPISTEME_STUDIO_DEMO_MODE` | `false` | Binds canned demonstration runs, disables mandatory Neo4j connection. |
| `read_only` | `--read-only` | `EPISTEME_STUDIO_READ_ONLY` | `false` | Rejects all disk/database write mutations; forces offline sandbox execution. |

### Security & Sandboxing Guarantees

* **Endpoint Mutation Blocking (`403 Forbidden`)**:
  - `POST /api/runs`: Run triggering is rejected with RFC 7807 problem type `read-only-mode`.
  - `POST /api/config/inputs/upload`: File uploading is forbidden.
  - `PUT /api/engine/settings`: Modifying ontology schemas, aliases, and engine parameters is blocked (`.pipeline_engine_settings.json` cannot be altered).
  - `POST /api/engine/map-predicate`: Open-vocabulary predicate mapping is locked.
  - `POST /api/evaluation/adjudicate`: Human adjudication writes to disk/database are rejected.
* **Decision Engine Sandboxing (`POST /api/engine/decision/test`)**:
  - On public demo or read-only instances, real model loading (`AutoDecisionEngine`, PyTorch, Transformers, Apple MLX) is **strictly bypassed**.
  - No Hugging Face Hub weight checkpoints are downloaded; no neural network models are loaded into RAM.
  - Playground requests are automatically routed to the in-memory, deterministic simulation stub (`is_mock = True`).
  - Inputs are bounded (`state[:10000]`, `question[:2000]`) to protect container memory.
  - Visitors can still interactively test premises, candidate labels, conformal prediction sets, and fast-exit routing in ~12ms with **zero tokens, zero network requests, and zero disk writes**.
* **Filesystem & Container Hardening**:
  - **`--read-only` Docker flag**: Mounts root container filesystem as read-only.
  - **Dropped Capabilities**: `--cap-drop=ALL` strips all Linux capabilities.
  - **Non-Root Execution**: Runs as unprivileged user `episteme` (UID `10001`).
  - **Zero Egress Required**: The demo container needs no outbound internet access, eliminating data exfiltration and SSRF risks.

