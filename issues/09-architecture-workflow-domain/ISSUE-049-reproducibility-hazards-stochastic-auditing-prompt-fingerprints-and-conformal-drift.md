# [ISSUE-049] Reproducibility & Cache Coherence Hazards: Unseeded Stochastic Auditing, Incomplete Prompt Fingerprinting, and Conformal Calibration Drift

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-049` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Scientific Reproducibility, Conformal Prediction, Fingerprinting) |
| **Target Package(s)** | `packages/episteme-pipeline` (`decision/`, `runs/fingerprints.py`, `llm/cache.py`, `pipeline.py`) |
| **Priority** | **High** |
| **Status** | `Completed` |
| **Evaluated Docs & ADRs** | [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md), [`docs/architecture/constrained_decoding.md`](../../docs/architecture/constrained_decoding.md), [`docs/architecture/invalidation_and_resume.md`](../../docs/architecture/invalidation_and_resume.md), [`ADR-0018`](../../docs/adr/0018-decision-engine-architecture-and-contracts.md), [`ADR-0019`](../../docs/adr/0019-typesafe-jev-client-and-decision-observability.md), [`ADR-0020`](../../docs/adr/0020-propositional-modal-strength-resolver.md) |

---

## 1. Current State

Episteme places a high premium on deterministic scientific reproducibility, relying on SHA-256 fingerprinting ([`docs/architecture/invalidation_and_resume.md`](../../docs/architecture/invalidation_and_resume.md)), disk-cached structured LLM calls (`DiskCachedStructuredLLM` in [`docs/architecture/cross_cutting_concerns.md`](../../docs/architecture/cross_cutting_concerns.md)), and Split Conformal Prediction ([`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md)).

However, an audit of the interaction between these subsystems reveals **four critical reproducibility and statistical validity defects**:

1. **Non-Deterministic Stochastic Auditing in `ObservableDecisionEngine`**:
   - Per [`docs/architecture/conformal_prediction.md §3.1`](../../docs/architecture/conformal_prediction.md) and [`ADR-0019 §3`](../../docs/adr/0019-typesafe-jev-client-and-decision-observability.md), `ObservableDecisionEngine` routes $p = 0.02$ ($2\%$) of System 1 fast-exit singletons to System 2 (generative LLM) via random sampling (`stochastic_audit_rate`).
   - Because decision evaluations occur concurrently across `asyncio.gather` / `Semaphore` worker tasks, drawing from a stateful or unseeded random number generator means task scheduling order determines *which* $2\%$ of candidate pairs or ADUs get escalated to System 2.
2. **Hardcoded, Incomplete Prompt Fingerprinting in `Pipeline._prompt_fingerprints()`**:
   - [`docs/architecture/invalidation_and_resume.md §Prompt Template Fingerprints`](../../docs/architecture/invalidation_and_resume.md) states that *"All 7 prompt task categories... are fingerprinted per run."*
   - In [`pipeline.py#L619-L635`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py#L619-L635), `_prompt_fingerprints()` is a hardcoded dictionary covering only `phase2`, `phase3`, `phase4_maturation`, and `phase4`.
   - It completely omits prompts and decision rubrics introduced in later ADRs:
     - `Phase 1`: Epistemic relevance gating prompt (`DECISION_EPISTEMIC_RELEVANCE_QUESTION`, `ADR-0018`).
     - `Phase 2`: Episodic Working Memory boundary detection prompt (`DECISION_BOUNDARY_QUESTION`, `ADR-0009`, `ADR-0018`).
     - `Phase 3b`: Borderline entity consolidation prompt/criteria (`verify_borderline_pair`, `ADR-0005`).
     - `Phase 5`: Inter-document theory cluster fusion prompt/criteria (`verify_inter_document_cluster`, `ADR-0005`).
     - `Phase 6 / ModalResolver`: Modal certainty evaluation question and criteria (`DecisionEngineModalResolver`, `ADR-0020`).
     - `TheoreticalEnrichment`: Dynamic theory induction and lens projection prompts (`LLMTheoryInducer`, `ADR-0015`).
3. **Unversioned & Unstratified Conformal Calibration ($\mathcal{D}_{\text{cal}}$ Exchangeability Violation)**:
   - [`docs/architecture/conformal_prediction.md §2`](../../docs/architecture/conformal_prediction.md) relies on the finite-sample marginal coverage theorem $P(Y_{n+1} \in C(X_{n+1})) \ge 1 - \alpha$, which holds **if and only if** the test instance $X_{n+1}$ is exchangeable with the calibration set $\mathcal{D}_{\text{cal}} = \{(x_1, y_1), \dots, (x_n, y_n)\}$.
   - Currently, `DecisionEngineConfig` (`ADR-0018`) defines a single global `conformal_alpha: float = 0.05`, and `ConformalCalibrator` state is neither stratified by task/language (German historical prose vs. English analytic philosophy; binary gating vs. 3-way consolidation vs. modal scoring) nor recorded as a versioned calibration artifact in `RunManifest`.
   - Furthermore, [`ADR-0019 §4`](../../docs/adr/0019-typesafe-jev-client-and-decision-observability.md) introduces an Active Learning Queue (`decision_engine_active_learning`) specifically sampling high-entropy borderline cases ($|C(X)| > 1$) to recalibrate/fine-tune the engine.
4. **Constrained Decoding & Schema Evolution vs. `DiskCachedStructuredLLM`**:
   - [`docs/architecture/constrained_decoding.md`](../../docs/architecture/constrained_decoding.md) introduces multiple decoding handlers (`direct_constrained`, `nl_to_format` two-pass Task Model $\to$ Schema Converter, and trigger-token `<schema_start>`). If `DiskCachedStructuredLLM` keys cache entries only on prompt text and model name without hashing the **target Pydantic JSON schema**, **decoding mode handler**, and **temperature/seed**, modifying a Pydantic contract field or switching from `direct_constrained` to `nl_to_format` returns stale or schema-incompatible cached payloads.

---

## 2. Why This Causes Problems

### A. Researcher & Statistical Validity Perspective
1. **Broken Run-to-Run Determinism under Concurrency**:
   - When a researcher runs the exact same configuration twice, `asyncio` network jitter changes the completion order of concurrent chunk/pair evaluations. A stateful RNG assigns `stochastic_audit = True` to different items in Run 1 vs. Run 2, causing different items to be evaluated by System 2 (LLM) vs. System 1 (Jev). Consequently, `output_fingerprint` diverges across identical runs!
2. **Breakdown of the $1 - \alpha$ Conformal Coverage Guarantee**:
   - **Task Heterogeneity**: Non-conformity score distributions $s_i = 1 - \hat{P}(y_i \mid x_i)$ for a 3-class entity merge task (`Phase 3b`) have fundamentally different entropy and tail behavior than a 4-class argument relation task (`Phase 4 ARC`) or a 6-level modal certainty task (`ADR-0020`). Applying a unstratified quantile $\hat{q}$ across tasks yields severe under-coverage on hard tasks and over-conservative wide prediction sets ($|C(X)| > 1$) on easy tasks.
   - **Selection Bias from Active Learning Recalibration**: In `ADR-0019`, active learning specifically selects high-entropy items ($|C(X)| > 1$). Directly appending active-learning-selected items into $\mathcal{D}_{\text{cal}}$ violates exchangeability (covariate shift toward hard examples), artificially inflating $\hat{q}$ until almost all future predictions produce $|C(X)| > 1$ and escalate to System 2!
   - **Silent Calibration Drift**: Because the empirical quantile $\hat{q}$ and $\mathcal{D}_{\text{cal}}$ dataset hash are not stored in `RunManifest`, updating calibration scores changes pipeline outputs without triggering `_choose_reuse_source()` invalidation.

### B. Software Engineering & Maintenance Perspective
3. **Silent Stale Cache Hits When Editing Prompts**:
   - Whenever a developer or researcher edits a prompt in `TheoreticalEnrichmentConfig`, `ModalResolverConfig`, or `Phase5Config` (either in code or via Langfuse Prompt Management per `ADR-0012`), `_prompt_fingerprints()` does not see it unless that specific config path is also fully serialized in `phase_config_fingerprints`—and any prompt resolved dynamically via `PromptProvider` outside those 4 hardcoded phases is completely invisible to invalidation.

---

## 3. Proposed Solution & Architectural Explanation

### Step 1: Stateless Cryptographic PRF for Deterministic Stochastic Auditing
Replace stateful `random.random() < self.stochastic_audit_rate` in `ObservableDecisionEngine` with a **Stateless Counter-Free Pseudo-Random Function (PRF)** derived from the run seed and the input's SHA-256 `state_hash`:

$$u(X) = \frac{\text{int}(\text{HMAC-SHA256}(\text{key}=\text{seed}, \text{msg}=\text{task\_id} \mathbin{\Vert} \text{state\_hash})[:8], 16)}{2^{64}} \in [0, 1)$$

$$\text{Audit}(X) = \mathbb{I}\big[u(X) < p_{\text{audit}}\big]$$

- **Why this works**: Because $u(X)$ is a pure mathematical function of `(config.seed, task_id, state_hash)`, it is **100% invariant to `asyncio` task scheduling order, concurrency level (`Semaphore`), or batch partitioning**, while maintaining an exact uniform $U(0, 1)$ marginal distribution for unbiased statistical auditing.

### Step 2: Automated Recursive Prompt Fingerprinting (`Fingerprintable` Protocol)
- Eliminate the hardcoded `prompts_by_phase` dictionary in `Pipeline._prompt_fingerprints()` (`pipeline.py#L619-L635`).
- Implement `Fingerprintable` directly on `StructuredPromptBundle` (and any registered `PromptProvider` resolution record), so `find_components(runner)` (`invalidation_and_resume.md §Recursive Component Tree`) automatically discovers and fingerprints **every** `StructuredPromptBundle` attached to any runner, extractor, linker, classifier, modal resolver, or post-processor.

### Step 3: Mondrian (Task- & Language-Stratified) Conformal Calibration with Manifest Lineage
- Upgrade `ConformalCalibrator` to implement **Mondrian Split Conformal Prediction** (Vovk et al., 2005), partitioning calibration sets $\mathcal{D}_{\text{cal}}^{(t, \ell)}$ by:
  - `task_id` $t \in \{\text{p1\_relevance}, \text{p2\_linking}, \text{p2\_boundary}, \text{p3\_rerank}, \text{p3b\_merge}, \text{p4\_acc}, \text{p4\_arc}, \text{p5\_fusion}, \text{modality}\}$
  - `language` $\ell \in \{\text{de}, \text{en}\}$ (to account for systematic confidence shift between German and English philosophical corpora).
- Keep active-learning fine-tuning data (` $\mathcal{D}_{\text{train}}$ `) strictly disjoint from the held-out exchangeable calibration split (` $\mathcal{D}_{\text{cal}}$ `), or apply **Weighted Conformal Prediction** (Tibshirani et al., 2019) using likelihood-ratio importance weights $w(x) = dP_{\text{test}}(x)/dP_{\text{cal}}(x)$ when incorporating queried samples.
- Implement `Fingerprintable` on `ConformalCalibrator` to emit `{task_id: {"q_hat": q_hat, "n_cal": n, "dataset_sha256": h}}` into `RunManifest.method_fingerprints`.

### Step 4: Schema- and Handler-Aware `DiskCachedStructuredLLM` Keys
- Ensure `DiskCachedStructuredLLM` computes its cache lookup key as:
  $$\text{CacheKey} = \text{SHA256}\big(\text{model\_id} \mathbin{\Vert} \text{decoding\_mode} \mathbin{\Vert} \text{temperature} \mathbin{\Vert} \text{seed} \mathbin{\Vert} \text{schema\_json\_hash} \mathbin{\Vert} \text{prompt\_bundle\_hash} \mathbin{\Vert} \text{rendered\_inputs}\big)$$
  where `schema_json_hash` is the canonical SHA-256 of `output_cls.model_json_schema()`.

---

## 4. Acceptance Criteria

- [x] `ObservableDecisionEngine` uses a deterministic HMAC-SHA256 PRF keyed by `(seed, task_id, state_hash)` for `stochastic_audit`, producing identical audit selections under arbitrary async concurrency schedules.
- [x] `StructuredPromptBundle` implements `Fingerprintable` and is discovered automatically via `find_components(runner)`, removing the hardcoded 4-phase dictionary in `Pipeline._prompt_fingerprints()`.
- [x] `ConformalCalibrator` supports per-task and per-language (`de`/`en`) quantile lookup $\hat{q}_{t, \ell}$ and exposes its calibration state hash to `RunManifest.method_fingerprints`.
- [x] `DiskCachedStructuredLLM` includes `model_json_schema()` hash and decoding strategy (`direct_constrained` vs. `nl_to_format`) in its cache key.

---

## 5. Key Target Files

- [`packages/episteme-pipeline/episteme_pipeline/decision/observable.py`](../../packages/episteme-pipeline/episteme_pipeline/decision/observable.py)
- [`packages/episteme-pipeline/episteme_pipeline/decision/conformal.py`](../../packages/episteme-pipeline/episteme_pipeline/decision/conformal.py)
- [`packages/episteme-pipeline/episteme_pipeline/pipeline.py`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py)
- [`packages/episteme-pipeline/episteme_pipeline/llm/cache.py`](../../packages/episteme-pipeline/episteme_pipeline/llm/cache.py)
- [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md)
