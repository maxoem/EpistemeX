# [ISSUE-119] Monorepo `uv` Packaging Hygiene, Plugin Isolation & Architecture Fitness Tests

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-119` |
| **Domain / Category** | `13-Core Architecture & Docs Refactoring` (Workspace Packaging, CI Isolation, Architecture Governance) |
| **Target Package(s)** | Root [`pyproject.toml`](../../pyproject.toml), `packages/*`, `tests/architecture/` |
| **Priority** | **High** |
| **Status** | `Proposal` |
| **Roadmap Horizon** | Horizon 1 & 2 |
| **Prerequisites** | [ISSUE-116](ISSUE-116-extract-episteme-contracts-and-workspace-dependency-inversion.md) |
| **Governing ADR & Plan** | [ADR-0026 Proposal](ADR-0026-PROPOSAL-contract-first-workspace-modular-runtime-and-systems-first-framing.md) \| [Execution Plan (`WP-4`)](EXECUTION-PLAN.md) |

---

## 1. Current Packaging Inconsistencies Found on Disk

Inspection of the four existing `pyproject.toml` files reveals concrete drift across Python versions, build backends, and dependency scopes:

| Manifest File | Current State | Defect / Risk |
| :--- | :--- | :--- |
| Root [`pyproject.toml`](../../pyproject.toml) | `requires-python = ">=3.13"`; `members = ["packages/*"]`; mandatory root deps list all workspace packages. | If future packages (`episteme-formal`, `episteme-worldmodel`) are added to root `[project].dependencies`, `uv sync` breaks or pulls multi-GB PyTorch/Lean toolchains into every dev environment. |
| [`episteme-pipeline/pyproject.toml`](../../packages/episteme-pipeline/pyproject.toml) | Non-`src` layout (`episteme_pipeline/`); `requires-python = ">=3.13"`; setuptools backend. | Bundles contracts + 25+ heavy ML/Neo4j/LLM deps. |
| [`epistemetrics/pyproject.toml`](../../packages/epistemetrics/pyproject.toml#L13) | `src/` layout (`src/epistemetrics/`); **`requires-python = ">=3.11"`**; setuptools backend. | Python floor drifts from root workspace `>=3.13` and lacks explicit dependency on `episteme-contracts` adapter contracts. |
| [`episteme-studio/pyproject.toml`](../../packages/episteme-studio/pyproject.toml#L10) | `src/` layout (`src/episteme_studio/`); **`requires-python = ">=3.11"`**; hatchling backend; pulls full `episteme-pipeline`. | Version drift (`>=3.11` vs `>=3.13`) and unnecessary pipeline coupling in lightweight read views. |

---

## 2. Target Workspace Hygiene Rules

1. **Unify `requires-python = ">=3.13"` Everywhere:** Update [`epistemetrics/pyproject.toml`](../../packages/epistemetrics/pyproject.toml#L13) and [`episteme-studio/pyproject.toml`](../../packages/episteme-studio/pyproject.toml#L10) to match root `>=3.13` so Ruff (`target-version = "py313"`) and type annotations behave identically across every member.
2. **Standardize `src/` Layout for All New Packages:** `packages/episteme-contracts/`, `packages/episteme-formal/`, and `packages/episteme-worldmodel/` MUST use `src/<pkg_name>/` layout (matching `epistemetrics` and `episteme-studio`) so editable installs never accidentally resolve sibling directories.
3. **Strict Optional Plugin Rule in Root [`pyproject.toml`](../../pyproject.toml):**
   - `episteme-contracts` becomes a mandatory core dependency imported by `episteme-pipeline`, `episteme-studio`, and optional extension packages.
   - Heavy/platform-specific plugin packages (`episteme-formal` for Lean 4/SMT; `episteme-worldmodel` for neural triage/IR) remain in `members = ["packages/*"]` and `[tool.uv.sources]`, **MUST NOT** live in root `[project].dependencies`, and expose explicit optional groups (`[project.optional-dependencies] formal = [...]`, `worldmodel = [...]`). Inside `episteme-worldmodel`, PyTorch/PyG training packages live strictly inside `worldmodel[train]`.
4. **Automate Boundary Enforcement (Architecture Fitness Tests):** Add fast, non-LLM AST tests under workspace tests:
   - `test_package_boundaries.py`: Parse Python ASTs to verify:
     - `episteme_contracts` imports **only** Python stdlib + `pydantic` (zero imports from `episteme_pipeline`, `neo4j`, `torch`, `llama_index`, etc.),
     - `episteme_pipeline` contains **zero** imports from `episteme_formal` or `episteme_worldmodel` (strict dependency inversion via protocols),
     - `epistemetrics` contains **zero** imports from `episteme_pipeline`, `episteme_formal`, or `episteme_worldmodel`.
   - `test_no_getattr_dispatch.py`: Enforce `AGENTS.md` §2 zero-`getattr` policy across `episteme_contracts` and newly extracted runtime modules (`runtime/`, `artifacts/`).

---

## 3. Acceptance Criteria

- [ ] Align `requires-python = ">=3.13"` across all workspace `pyproject.toml` files.
- [ ] Configure root `pyproject.toml` so `episteme-contracts` is shared by core packages while optional neuro-symbolic/world-model plugins stay outside mandatory root `[project].dependencies`.
- [ ] Decouple `episteme-studio` response/domain models onto `episteme-contracts` directly where execution-engine internals are not required.
- [ ] Add `test_package_boundaries.py` and `test_no_getattr_dispatch.py` to pytest and verify full green execution via `rtk uv run pytest`.
