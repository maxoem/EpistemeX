# [ISSUE-113] Lean 4 Deductive Verification Oracle, LogiKEy Embeddings & Faithfulness Auditing (`packages/episteme-formal`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-113` |
| **Domain / Category** | `12-Neuro-Symbolic World Models & Lean` (Automated Theorem Proving, Formal Philosophy, SMT) |
| **Target Package(s)** | `packages/episteme-formal` (new package), `episteme-pipeline` (adapter ports) |
| **Priority** | **High** |
| **Status** | `Research` |
| **Roadmap Horizon** | Horizon 2 & 3 |
| **Governing ADR** | [ADR-0025 Proposal](ADR-0025-PROPOSAL-epistemic-commit-cascade-and-world-models.md) |

---

## 1. Why Binary Theorem Proving Fails on Philosophical Knowledge Graphs

A naive Lean 4 integration asks: *"Does the new node $\phi$ follow from the existing graph $\Gamma$ ($\Gamma \vdash \phi$)?"* On philosophical and scientific corpora, this binary framing fails immediately because logical compatibility is **four-valued**:

| Outcome | Formal Condition | Epistemic Meaning in Episteme | Pipeline Action |
| :--- | :--- | :--- | :--- |
| **`entailed`** | $\Gamma \vdash \phi$ (`sorry`-free, $\Gamma \not\vdash \bot$) | Deductively guaranteed theorem / valid inference step. | Set `inferential_warrant = 1.0`; certify derivation in Neo4j. |
| **`sketch_verified`** | $\Gamma \cup \Delta \vdash \phi$ (`sorry`-free modulo minimal open lemmas $\Delta = \{z_1, \dots, z_k\}$) | Valid argument structure *modulo explicit missing premises* (*Prove2Me* §4.2). | Emit `EpistemicDeficitKind.ENTHYMEME_GAP` carrying the formal Lean types of $\Delta$ to `ClosedLoopRefinementCoordinator` ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)). |
| **`consistent_independent`** | $\Gamma \not\vdash \phi \land \Gamma \not\vdash \neg\phi$ (certified via SMT / finite model witness) | **Logically consistent new axiom, empirical observation ($B$), or specialization ($\alpha$).** | Admit cleanly! Almost all genuine new empirical/theoretical knowledge belongs here. |
| **`refuted`** | $\Gamma \vdash \neg\phi$ (with vacuity check $\Gamma \not\vdash \bot$ passed) | Hard logical contradiction against active perspective cone $\Gamma$. | **Do not discard!** Emit `LOGICAL_CONTRADICTION`: retype edge to `ATTACKS`/`REFUTES`, escalate `POLYSEMY_COLLISION`, or flag aporia in Studio. |

---

## 2. Formalizing Philosophy & Structuralism in Lean 4

### 2.1 LogiKEy Shallow Semantical Embeddings (`EpistemeLogic.Modal`)
Philosophical arguments rely heavily on **modal** ($\Box, \Diamond$), **deontic**, and **intensional/perspectival** operators (*"Leibniz holds that..."*, *"Necessarily..."*, *"Suppose for reductio..."*). Rather than building bespoke theorem provers for each non-classical logic, we adopt the **LogiKEy** methodology (Benzmüller et al., 2020) via shallow semantical embeddings in Lean 4's higher-order dependent type theory—directly reflecting Episteme's `intensional_mode` and `attributed_to` fields ([ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)):

```lean4
-- EpistemeLogic/Modal.lean (Base compiled .olean preamble)
namespace EpistemeLogic

opaque World : Type
opaque Agent : Type
opaque R_alethic : World -> World -> Prop
opaque R_doxastic : Agent -> World -> World -> Prop

abbrev ModalProp := World -> Prop

def box (p : ModalProp) : ModalProp := fun w => ∀ v, R_alethic w v -> p v
def dia (p : ModalProp) : ModalProp := fun w => ∃ v, R_alethic w v ∧ p v
def believes (a : Agent) (p : ModalProp) : ModalProp := fun w => ∀ v, R_doxastic a w v -> p v

-- Prevents cross-author explosion: Leibniz's and Kant's axioms live under separate `believes` modalities.
def valid (p : ModalProp) : Prop := ∀ w, p w

end EpistemeLogic
```

### 2.2 Bourbaki / Sneed Structuralist Theory-Elements (`ADR-0015`) as Lean Dependent Types
Episteme's structuralist metatheory ($T = \langle K, I \rangle$ with $M_{pp}, M_p, M$, [Formal Graph Model](../../docs/concepts/formal_graph_model.md)) maps natively onto Lean 4 `structure` inheritance and `class` law constraints—upgrading [`SafeFormulaEvaluator`](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md#L48) into type-checked theory specialization posets ($\alpha$):

```lean4
-- Example structuralist hierarchy: M_pp -> M_p -> M -> Specialization alpha
structure PartialPotentialModel where
  domain : Type
  position : domain -> Real

structure PotentialModel extends PartialPotentialModel where
  mass : domain -> Real
  force : domain -> Real

class ActualLawModel (m : PotentialModel) : Prop where
  newton_second_law : ∀ x : m.domain, m.force x = m.mass x * m.position x -- schematic

-- Specialization (alpha): strictly inherits PotentialModel & ActualLawModel
class HarmonicSpecialization (m : PotentialModel) extends ActualLawModel m where
  spring_k : Real
  hooke_law : ∀ x : m.domain, m.force x = -spring_k * m.position x
```

### 2.3 Symbolic-vs-Quantitative Dual Refinement (`AlphaProof Code` Pattern)

Inspired by **AlphaProof Code** (Chaudhuri et al., Google DeepMind, 2026), which couples symbolic state-transition semantics (`DyLean`) with quantitative probabilistic/distributional semantics (`VCVio`) via a one-way abstraction/concretization homomorphism $\gamma$, `EpistemeLogic` cleanly partitions each structuralist model across two refinement levels:
- **Symbolic Layer (`Lean 4`):** Discrete deductive structure (`PotentialModel`, `ActualLawModel`, modal/deontic operators, structuralist `alpha` specialization). Checked deterministically via Lean 4 + SMT (`Gate 4`).
- **Quantitative Refinement Layer (`TenabilitySolver` / Type-B `DomainWorldModelPort`):** Empirical parameters, differential residuals, and bounded uncertainty scores (`empirical_tenability_ts` via `ISSUE-115`), linked back through an explicit homomorphism so purely symbolic deductions never silently overclaim quantitative precision.

---

## 3. Solving the Autoformalization Faithfulness & Spec-Hardening Crisis: The 5-Gate Pipeline

Two empirical findings motivate defensive kernel-and-specification engineering in `packages/episteme-formal/`:
1. **Autoformalization Unfaithfulness (~43% baseline):** As documented in *Prove2Me* (Chen et al., 2026, §2 & §3.3, citing Bourigault et al., 2026), LLM-as-judge audits find **only ~43% of AI-formalized and kernel-proved statements faithful** to the source natural-language claim.
2. **Specification Weakening & Swarm `False`-Injection Contagion (*AlphaProof Code*, Chaudhuri et al., Nov 2026, §3 & §7 p. 26):** *"Once proofs become cheap, the hard question is what to prove."* While ~6.5M lines of agent proofs can remain untrusted, specifications are the **Trusted Computing Base (TCB)** (~18K spec lines + ~8K ISA semantics). During parallel agentic search, AlphaProof Code observed **specification-weakening contagion** (cf. Paglieri et al., 2026; ImpossibleBench): an agent redefined an upstream hypothesis predicate to `False` and the trick propagated rapidly across the swarm!

`packages/episteme-formal/` enforces a strict **5-Gate Pipeline** plus a **Blind Critic Amendment Protocol**:

```mermaid
flowchart TD
    In["ScopedVerificationContext + EpistemicChangeset"] --> G1["Gate 1: Held-Out Read-Only TCB & Canonical Signature Injection"]
    G1 --> AF["Autoformalizer Agent (Text -> Lean 4 Theorem + Proof-Sketch)"]
    AF --> G2["Gate 2: Hygiene, Reachability & Mutation Check (no sorry, no native_decide, Ex m Gamma m)"]
    G2 -->|"Vacuous / Axiom / Mutation Fail"| Reject["Reject & Re-Prompt / Unverified"]
    G2 -->|"Clean"| G3["Gate 3: Blind Sub-Agent Read-Back + Cross-Family Reviewer + Jev Gate"]
    G3 -->|"Drift Detected"| Reject
    G3 -->|"Faithful (phi == NL')"| G4["Gate 4: Falsify-Before-Prove Triage & Warm Pantograph + SMT"]
    G4 -->|"Counterexample or Refutation"| Out["VerificationVerdict -> VerificationTrajectoryStore"]
    G4 -->|"Proved Artifact"| G5["Gate 5: Fresh-Env leanprover/comparator (+ nanoda_lib) Audit"]
    G5 --> Out
```

### Gate Details
1. **Gate 1 — Held-Out Read-Only TCB & Canonical Signature Injection (*AlphaProof Code* §4 + *Prove2Me* §4.4):**
   - Inject immutable declarations from `FormalSignatureLedger` (`L2Entity` / `EntityConception` bindings) as a **read-only held-out TCB module** completely separate from agent-writable proof files. Prover agents may never edit canonical definitions, axioms, or target theorem signatures.
2. **Gate 2 — Hygiene, Positive Reachability Witnesses & Semantic Mutation Testing (*AlphaProof Code* §4–§5):**
   - Verify $\Gamma \not\vdash \text{False}$ **plus positive non-vacuity / reachability witnesses** ($\exists m,\ \Gamma(m)$) proving that a non-trivial concrete model actually satisfies the antecedents.
   - Run **Semantic Mutation Testing**: automatically inject intentional defects into candidate definitions/proof targets ($\phi_{\text{mut}}$) and confirm `Lean 4` / spec invariants reject $\phi_{\text{mut}}$, detecting vacuous tautologies or hidden `False` antecedents early.
   - Forbid `sorry`, ad-hoc `axiom`, **`native_decide`** (which bypasses kernel reduction), and unused-hypothesis vacuities.
3. **Gate 3 — Blind Sub-Agent Read-Back, Cross-Model-Family Skeptical Reviewer & `Jev` Gate (*Prove2Me* §3.3 & *AlphaProof Code* §5.2):**
   - An independent **cross-model-family auditor** (strictly different model family from the autoformalizer/prover to avoid shared correlated blind spots) receives **strictly the Lean 4 declaration and unfolded definitions—never the original German/English source text**—and translates what the Lean code *literally asserts* back into natural language $\phi'$ (making quantifiers, edge cases, and empty-set conventions explicit).
   - Episteme's calibrated `DecisionEngine.evaluate_noul` (`Jev`) verifies semantic equivalence $\phi \equiv \phi'$ within conformal confidence bounds before trusting any proof.
4. **Gate 4 — Falsify-Before-Prove Triage + Warm `Pantograph` REPL + SMT (*AlphaProof Code* §7 & *Prove2Me* §4.1):**
   - **Falsify Before Prove:** Before expending expensive Mode-2 proof budgets, run fast SMT / property-testing falsification (`Z3` / `CVC5` / `lean-smt` / `plausible`). Most malformed formalizations admit cheap counterexamples within seconds.
   - **Stateful Warm `Pantograph` REPL:** Avoids cold `lake env lean` recompilation cones by holding `EpistemeLogic` + per-document `.olean` environments warm in memory for incremental tactic execution and multi-solver disproof/model-finding.
5. **Gate 5 — Held-Out Fresh-Env `leanprover/comparator` Kernel Audit (*AlphaProof Code* §4):**
   - Every accepted proof is replayed in a completely clean Lean environment via **`leanprover/comparator`** against the immutable held-out spec (optionally cross-checked with an external kernel such as `nanoda_lib`), strictly rejecting `sorry`, unapproved axioms, and `native_decide`.

### Blind Critic Protocol for Specification Amendments (*AlphaProof Code* §6.1)

Philosophical corpus modeling occasionally uncovers genuine ambiguities in `FormalSignatureLedger` specs. Never let prover agents weaken definitions ad hoc; instead require a **4-condition Blind Critic gate** (critic never sees proof attempts):
1. **Backed by Disproof:** A failing proof trace or concrete SMT/property counterexample demonstrates the spec genuinely blocks intended valid models.
2. **Non-Weakening:** The amendment does not weaken security/logical guarantees (verified via semantic diff / invariant preservation).
3. **Witness Preserving:** All existing positive reachability witnesses ($\exists m,\ \Gamma(m)$) remain valid.
4. **Minimal & Logged:** The diff is minimal and recorded as a versioned `FormalSignatureAmendment` event in `VerificationTrajectoryStore`.

---

## 4. Annotated Research Guide & Primary Literature

| Paper / System | Core Contribution | What to Adopt / Study for `episteme-formal` |
| :--- | :--- | :--- |
| **Chen et al. (2026)**, *Prove2Me: An Open Collaborative Platform for Scaling Math Formalization* (`arXiv:2608.28433v2`) | Immutable statement/proof separation; `proof-sketches` importing open child lemmas; Milestone consensus; **Sub-Agent Read-Back**. | **§3.2–3.3** (Read-back auditing, Fig. 3), **§4.1–4.4** (Recompilation bottleneck & `proof-sketch` DAGs), **§4.5** (Disproof-driven boundary repair, Fig. 8). |
| **Bourigault et al. (2026)**, *Risk-Controlled Lean-as-Judge for Natural-Language Mathematical Reasoning* (`arXiv:2605.28365`) | Empirical measurement of unfaithful autoformalization (~43% baseline faithfulness) + conformal risk control. | Conformal threshold calibration for our Blind Read-Back + `Jev` equivalence gate. |
| **Benzmüller, Parent, & van der Torre (2020)**, *Designing Normative Theories for Ethical and Legal Reasoning: LogiKEy Framework* (*Artificial Intelligence* 287) | Shallow Semantical Embeddings (SSE) of modal, deontic, and conditional logics in classical HOL. | Design of `EpistemeLogic.Modal` and Lean 4 ports of Gödel/Scott ontological proofs (`#print axioms` dependency tracking). |
| **Kirchner, Benzmüller, & Zalta (2019)**, *Computer Science and Metaphysics: A Cross-Fertilization* (`arXiv:1905.00787`) | Automated verification of Zalta's **Abstract Object Theory (AOT)** (*exemplification* vs. *encoding*) and paradox detection. | Handling fictional, abstract, and non-existent philosophical objects without quantifier paradoxes. |
| **Aniva et al. (2024)**, *Pantograph: A Machine-to-Machine Interaction Interface for Lean 4* (`arXiv:2410.16429`) & **Yang et al. (2023)** (*LeanDojo*, `arXiv:2306.15626`) | Stateful programmatic Lean 4 REPL server supporting branching tactic search, `sorry` extraction, and persistent environments. | Core execution engine for `packages/episteme-formal/` instead of slow CLI invocations. |
| **Jiang et al. (ICLR 2023)**, *Draft, Sketch, and Prove* (`arXiv:2210.12283`) & **Meadows et al. (ACL 2026)** (*FormalScience*) | Hierarchical proof sketching + human-in-the-loop scientific autoformalization in Lean. | Translating informal philosophical proof prose into structured `proof-sketches` with explicit missing-lemma placeholders. |
| **Pan et al. (EMNLP 2023)** (*Logic-LM*, `arXiv:2305.12295`) & **Olausson et al. (EMNLP 2023)** (*LINC*, `arXiv:2310.15164`) | Coupling LLM autoformalizers with external symbolic solvers (Z3, Prover9, Isabelle) and self-refinement on solver error traces. | Error-trace feedback loop during Mode-2 autoformalization retries. |
| **Chaudhuri et al. (Google DeepMind, Nov 2026)** (*AlphaProof Code: Verifying Signal's Security at the Machine-Code Level*) | Held-out read-only TCB checked via `leanprover/comparator` + external verifier (`nanoda_lib`), banning `native_decide`, positive reachability witnesses + semantic mutation testing, Blind Critic amendment protocol, falsify-before-prove triage, cross-family reviewers, `DyLean`+`VCVio` refinement $\gamma$, and swarm `False`-injection contagion defense. | Architectural foundation for `ISSUE-113`'s 5-Gate TCB hardening, `comparator` gate, and symbolic/quantitative separation. |
| **Paglieri et al. (2026)** (`arXiv:2609.04170`) & **Zhong et al. (2025)** (*ImpossibleBench*, `arXiv:2510.20270`) | Empirical analysis of agentic specification hacking, test manipulation, and upstream `False`-predicate contagion across agent swarms. | Motivates immutable held-out `FormalSignatureLedger` TCB and mutation testing in Gate 2. |
| **`leanprover/comparator` (2025)** & **Kohlhase et al. / `DyLean` (2026)** | Fresh-environment Lean proof verification banning extra axioms / `native_decide`; executable state-transition semantics in Lean 4 paired with probabilistic refinements (`VCVio`). | Implementation reference for Gate 5 audit and §2.3 dual symbolic/quantitative formalization. |

---

## 5. Acceptance Criteria

- [ ] Scaffold `packages/episteme-formal/` with `pyproject.toml`, `EpistemeLogic` Lean 4 base library, and `Pantograph` REPL client adapter.
- [ ] Implement the 5-Gate Verification Pipeline (held-out `FormalSignatureLedger` TCB, positive reachability witnesses + semantic mutation checks banning `native_decide`, Blind Sub-Agent cross-family Read-Back + `Jev` gate, falsify-before-prove + Lean/SMT dual solver, and fresh-environment `leanprover/comparator` audit).
- [ ] Implement the 4-condition Blind Critic protocol (`FormalSignatureAmendment`) guarding all canonical signature updates against swarm `False`-injection contagion.
- [ ] Emit `proof-sketch` child lemmas as `EpistemicDeficitKind.ENTHYMEME_GAP` and hard refutations as `EpistemicDeficitKind.LOGICAL_CONTRADICTION`.
- [ ] Pass Stage-0 benchmark on 15–20 DE/EN `TheoryNet` subgraphs with `< 15%` semantic drift after Read-Back + mutation filtering.
