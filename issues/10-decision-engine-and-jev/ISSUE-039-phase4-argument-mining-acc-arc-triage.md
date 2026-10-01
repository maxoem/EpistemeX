# [ISSUE-039] Phase 4b Argument Mining: Jev ACC & ARC Triage Classifiers

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-039` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase4_argument_mining/classifiers.py`, `pipeline/protocols/argument_mining.py`, `pipeline/config.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Dialectical Modeling) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/roadmap.md` (§ JevACCClassifier, § JevARCClassifier), ADR 0004, ADR 0007 |

---

## 1. Problem Statement & Motivation
Phase 4b (Argument Mining) is responsible for extracting Argumentative Discourse Units (ADUs), classifying their functional types (Argument Component Classification, ACC: `CLAIM`, `PREMISE`, `CONCLUSION`), and identifying local and global defeasible stances (Argument Relation Classification, ARC: `SUPPORTS`, `ATTACKS`).

In the current implementation, ACC and ARC rely on heavy generative LLM prompts. Because scholarly scientific texts generate hundreds of ADUs per paper, running multi-token generative inference over every ADU and candidate stance pair is the primary bottleneck of pipeline execution. Furthermore, uncalibrated LLM stance scores distort downstream TheoryNet QBAF gradual semantics.

Introducing Jev-based typed classifiers with a **Confidence-Gated Cascading Triage** allows clear-cut arguments ($75\%–85\%$ of cases) to resolve in sub-second time ($70–150\text{ms}$), escalating only ambiguous, complex philosophical boundaries to deep LLM reasoning.

---

## 2. Technical & Architectural Specification

### What to Add
1. **`JevACCClassifier` (`pipeline/phases/phase4_argument_mining/classifiers.py`)**:
   - Subclass `ACCClassifier` ABC.
   - Accepts injected `DecisionEngine` and optional `StructuredPromptBundle` (sourced via `PromptProvider` / Langfuse).
   - Formulates question and criteria dynamically from `bundle.decision_template` and `bundle.decision_criteria`.
   - Uses Jev `Choice` primitive over argument component schema (`["CLAIM", "PREMISE", "CONCLUSION", "MAJOR_CLAIM"]`).
   - Maps classified components to `TheoryAtom` instances, attaching `class_probability` and `empirical_accuracy` to atom metadata.
2. **`JevARCClassifier` (`pipeline/phases/phase4_argument_mining/classifiers.py`)**:
   - Subclass `ARCClassifier` ABC.
   - Accepts injected `DecisionEngine` and prompt bundle sourced from Langfuse prompt management.
   - **Bipolar & Multiplex Stance Support**:
     - Standard mode (`arc_mode="cascading"`): Evaluates stance using Jev `Choice` over `["SUPPORTS", "ATTACKS", "UNDERCUTS", "NEUTRAL"]`.
     - Multiplex mode (`arc_mode="multiplex"`): Evaluates parallel independent Jev `Noul` questions (`is_support`, `is_attack`, `is_undercut`), allowing compound dialectical relations to project multiple distinct typed edges into TheoryNet.
   - Emits `TheoryRelation` instances with calibrated probabilities stored on edge attributes.
3. **Cascading Triage Composite (`CascadingACCClassifier`, `CascadingARCClassifier`)**:
   - Decorates both a `fast_engine: DecisionEngine` and an `llm_classifier: ACCClassifier` / `ARCClassifier`.
   - **Fast-Exit Condition**: Fast-exits if conformal prediction set is a singleton ($|C(X)| = 1$) or empirical accuracy satisfies $\text{empirical\_accuracy} \ge \tau_{\text{confidence}}$ and entropy $H(P) \le \epsilon$.
   - **Stochastic False-Negative Audit**: With probability $p_{\text{audit}} = 0.02$ (2%), fast-exit candidates are randomly escalated to the LLM classifier for continuous calibration drift monitoring and false-negative detection.
   - **Active Learning Queue Hook**: When prediction set contains multiple classes ($|C(X)| > 1$) or high entropy ($0.40 \le P \le 0.60$), tags telemetry with `active_learning: true` for Langfuse dataset curation.
   - If confidence is below threshold, escalates to the LLM classifier, passing Jev's probability distribution as an explicit prior in the prompt.
4. **Configuration Controls (`pipeline/config.py`)**:
   - Extend `Phase4Config` with:
     - `acc_mode: str = "llm_only"` (`"llm_only"` | `"cascading"` | `"jev_only"`) - defaults to `"llm_only"` for zero-regression baseline!
     - `arc_mode: str = "llm_only"` (`"llm_only"` | `"cascading"` | `"jev_only"` | `"multiplex"`)
     - `triage_confidence_threshold: float = 0.85`
     - `conformal_alpha: float = 0.05`
     - `stochastic_audit_rate: float = 0.02`
     - `pass_priors_to_llm: bool = True`

### What to Change
1. **`Phase4Runner`**:
   - Update runner to accept injected `ACCClassifier` and `ARCClassifier` instances.
   - If `decision_engine is None` or `acc_mode == "llm_only"`, default to standard `DefaultLLMACCClassifier` and `DefaultLLMARCClassifier` (exact current behavior).
2. **Composition Root (`Pipeline.for_task`)**:
   - Only wire `CascadingACCClassifier` and `CascadingARCClassifier` into `Phase4Runner` when `decision_engine` is explicitly provided and enabled in config.
3. **Prompt Resolution**:
   - Wire `config.phase4.acc_prompts` and `config.phase4.arc_prompts` from `LangfusePromptProvider` into the classifiers so decision templates and criteria sets are versioned in Langfuse.

### What to Remove
- Remove hardcoded within-runner LLM prompt envelopes for discrete ADU type classification when custom classifiers are injected.

---

## 3. Acceptance Criteria
- [ ] `JevACCClassifier` correctly categorizes ADUs into `TheoryAtom` models with calibrated confidence.
- [ ] `JevARCClassifier` correctly identifies `SUPPORTS` and `ATTACKS` stances between distant components.
- [ ] `CascadingACCClassifier` routes high-confidence instances to Jev fast-exit and ambiguous instances to the LLM.
- [ ] Escalate traces to Langfuse showing triage routing decisions via `DecisionGatingTriggered` events.
- [ ] Benchmarks demonstrate a $\ge 60\%$ reduction in LLM token usage and latency in Phase 4b.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py`
- `packages/episteme-pipeline/episteme_pipeline/protocols/argument_mining.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/runner.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/tests/test_phase4_cascading_classifiers.py`

---

## 5. Documentation Updates Required
- Update the Phase 4 Argument Mining workflow documentation (`docs/workflow/4_argument_mining/`) to explain the cascading triage model.
- Update ADR 0004 (ACC Outputs Triples Single Pass) and ADR 0007 (TF Structural Correspondence) to document non-generative classification paths.
- Add an architectural diagram illustrating the System 1 fast-exit vs. System 2 escalation workflow for argument discourse units.
