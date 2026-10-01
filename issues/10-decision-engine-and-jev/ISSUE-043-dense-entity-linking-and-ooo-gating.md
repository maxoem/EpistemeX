# [ISSUE-043] Dense Entity Linking: Jev Candidate Disambiguation & Out-of-Ontology Gating

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-043` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase2_entity_discovery/sota_entity_linker.py`, `pipeline/protocols/extractors.py`, `pipeline/config.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Low Latency Inference) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/concepts/dense_alignment.md` (§ Dual-Space Dense Alignment) |

---

## 1. Problem Statement & Motivation
In Phase 2, when an entity mention $m$ with symmetrical textual envelope $T_n$ is extracted, Episteme aligns it to existing canonical graph nodes $G_k \in \mathcal{V}_{\text{L2}}$ using a dual-funnel architecture:
1. **MIPS Bi-Encoder Retrieval**: Retrieves top-$K$ nearest canonical entity candidates.
2. **Cross-Encoder Verification**: Scores the joint probability of identity $\text{score}_{\text{cross}}(T_n, G_k)$.
3. **Out-of-Ontology (OoO) Fallback**: If $\max_k \text{score}_{\text{cross}} < \tau_{\text{OoO}}$, a novel entity $e_{\text{new}}$ is minted.

The cross-encoder verification step requires heavy batch matrix operations or joint attention passes over all candidate pairs. Furthermore, because standard cross-encoders output raw uncalibrated logits that must be passed through a logistic sigmoid, setting a stable, universally applicable $\tau_{\text{OoO}}$ threshold across disparate philosophical vocabularies is notoriously difficult, leading to either entity over-merging or duplicate node proliferation.

TypeSafe Jev's `Choice` primitive directly evaluates a candidate set against the mention envelope in a single sub-second pass, returning a calibrated confidence score and explicit support for an `OUT_OF_ONTOLOGY` option.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Jev Entity Disambiguator (`pipeline/phases/phase2_entity_discovery/sota_entity_linker.py`)**:
   - `class JevEntityLinker`:
     - Accepts injected `DecisionEngine`.
     - Method `async def link_mention(mention_envelope: str, candidates: list[L2Entity]) -> tuple[L2Entity | None, float, bool]`:
       - If `candidates` is empty, immediately declare Out-of-Ontology.
       - Formulates Jev `Choice` query:
         - `state`: Mention span, local sentence envelope $T_n$, and candidate descriptions $G_k$.
         - `options`: `[c.name for c in candidates] + ["OUT_OF_ONTOLOGY"]`.
       - Returns `(matched_entity, confidence, is_out_of_ontology)`.
2. **Configuration Support (`pipeline/config.py`)**:
   - Add to `Phase2Config`:
     - `entity_linking_mode: str = "cross_encoder"` (`"cross_encoder"` | `"jev"` | `"cascading"`)
     - `jev_ooo_threshold: float = 0.75`

### What to Change
1. **`SOTAEntityLinker`**:
   - Support substituting or cascading the local PyTorch cross-encoder with `JevEntityLinker`.
   - In cascading mode: use Jev for fast disambiguation ($70–120\text{ms}$); escalate to cross-encoder/LLM only when Jev confidence is borderline.

### What to Remove
- Remove arbitrary sigmoid normalization heuristics on uncalibrated cross-encoder logits when Jev linking is selected.

---

## 3. Acceptance Criteria
- [ ] `JevEntityLinker` disambiguates top-$K$ candidate entities with calibrated confidence.
- [ ] Out-of-Ontology decisions trigger cleanly when a mention represents a genuinely novel concept.
- [ ] Entity linking latency drops by $\ge 60\%$ compared to local PyTorch cross-encoders on CPU/GPU.
- [ ] Unit tests with `MockJevDecisionEngine` verify candidate matching and OoO fallback branches.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/sota_entity_linker.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/entity_linker.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/tests/test_jev_entity_linker.py`

---

## 5. Documentation Updates Required
- Update the Dense Alignment conceptual documentation (`docs/concepts/dense_alignment.md`) to include Jev-based typed candidate disambiguation.
- Update Phase 2 workflow documentation regarding entity linking strategies.
