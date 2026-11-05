# [0007] TF as Target Representation — Structural Correspondence Classification

Status: Accepted  
Supersedes: ADR-0006 (QBAF Weight Computation Deferred)

---

## Context

ADR-0006 deferred QBAF weight computation and identified three unresolved research questions about weight semantics. The
formal chapter (`/paper/chapters/1_formal_aspects_tf.tex`) has since been revised: the target representation is now
the **Theoriennetz** (TF), not the Quantified Bipolar Argumentation Framework (QBAF).

### Why TF, not QBAF

| Property             | QBAF                                         | TF                                                                 |
|----------------------|----------------------------------------------|--------------------------------------------------------------------|
| Node domain          | Arguments only                               | All atom types (At: KONZEPT, AXIOM, BEOBACHTUNGSSATZ, CLAIM, ...)  |
| Relations            | Fixed binary R⁻ (attack) / R⁺ (support)      | Typed, heterogeneous R ⊆ At × At                                   |
| Weights              | Required by definition (w: A → ℝ)            | Optional; structural correspondence on specific R subtypes         |
| Grounding            | Argumentation theory                         | Δ = (B, P): knowledge base of empirical sentences and premises     |
| Evaluation semantics | Extension semantics (stable, preferred, ...) | Maximal B-consistent subsets of P (Definition 1 in formal chapter) |

QBAF fixes the relation ontology to a binary attack/support split. TF makes relation types a configurable schema
parameter — the same principle applied to L2 entities in `SchemaConfig.node_types` and `SchemaConfig.relation_types` now
extends to L3. The QBAF is a special case of TF where R is partitioned into exactly two typed subsets and every argument
atom carries a base weight.

### Structural correspondence

The formal chapter defines a *corresponding valuation* κ: At → ε as admissible only when there is sufficient *structural
overlap* (strukturelle Überlagerung) between an atom a ∈ At and its entity image κ (a) ∈ ε. This admissibility criterion
is a **construction-time** property: it determines whether a proposed relation (a, b) ∈ R is valid given the
descriptions and graph positions of the two nodes.

Structural correspondence is not a post-construction evaluation metric — it is part of the graph's construction and
should be stored as a property on relation edges.

---

## Decision

### 1. TF replaces QBAF as the target L3 representation

- The `QBAF` struct in `pipeline/contracts/domain.py` is deprecated. It will be replaced by a `TF` struct:
  `TF(atoms: list[AtomNode], relations: list[TypedRelation])`.
- `QBAFMapper` → `TFMapper`. The mapper receives the full `SchemaConfig` and builds the TF over all relation types, not
  just SUPPORTS/ATTACKS.
- L3 node labels remain `ArgumentComponent`; they are one kind of atom in TF alongside L2 nodes (AXIOM,
  BEOBACHTUNGSSATZ, ZUORDNUNGSGESETZ) when structural correspondence is computed across layers.
- The `qbaf_weight` property on nodes and edges is renamed `structural_correspondence: float | null`. The semantics
  change: this is not an argumentative weight but a confidence score that the structural overlap condition
  κ-admissibility holds for this edge.

### 2. Structural Correspondence Classification is a new injectable construction step

A new step — **Structural Correspondence Classification** — is inserted into the pipeline between Phase 3 and Phase 5a.
It is user-configured and optional (disabled by default; enabled by populating `StructuralCorrespondenceConfig.pairs`).

**Configuration:**

```python
class AtomTypePair(BaseModel):
    source_type: str   # source node label (e.g., "AXIOM")
    target_type: str   # target node label (e.g., "BEOBACHTUNGSSATZ")
    relation_type: str # which edge type to score (e.g., "BESTAETIGT")

class StructuralCorrespondenceConfig(BaseModel):
    pairs: list[AtomTypePair] = []           # empty = step disabled
    prompt_template: str = SC_PROMPT         # default + overrideable
    confidence_threshold: float = 0.0        # store all scores by default
    subgraph_depth: int = 1                  # neighbourhood depth for context
```

**Step behaviour for each configured pair:**

1. Load all relation edges of type `pair.relation_type` from the graph where source label = `pair.source_type` and
   target label = `pair.target_type`.
2. For each edge (node_a, node_b): retrieve both nodes' descriptions and `subgraph_depth`-hop neighbourhoods.
3. LLM call (default prompt): given node_a's description + neighbourhood, node_b's description + neighbourhood, and the
   relation type — does this pair exhibit sufficient structural overlap for the relation to be κ-admissible? Respond
   with `{"score": float 0-1, "reasoning": str}`.
4. Write `structural_correspondence: score` onto the edge. Edges below `confidence_threshold` are not updated (score
   remains `null`).

**Pluggability:**

- Implement `StructuralCorrespondenceClassifier(ABC)` and inject via
  `PipelineConfig.structural_correspondence_classifier=MyClassifier()`.
- Override `prompt_template` per pair or globally.

### 3. Pipeline ordering update

```
Phase 1 → Phase 2 → Phase 3 → [SC] → Phase 3b → Phase 4 Maturation → Phase 4 → Phase 5b
```

SC runs after Phase 3 so that global relation edges exist before scoring. SC results are available to Phase 3b entity
consolidation and Phase 4 (where ARC can use correspondence scores as a prior).

SC may optionally be re-run after Phase 4 to score L3 edges (SUPPORTS/ATTACKS between ArgumentComponents), treating each
ArgumentComponent as an atom of type `CLAIM`, `MAJOR_CLAIM`, or `PREMISE`. This is enabled by including L3 atom-type
pairs in `StructuralCorrespondenceConfig.pairs`.

### 4. Evaluation remains post-construct (complemented by inter-phase quality gates)

The three full theory evaluation dimensions — empirical content, internal coherence, external compatibility — are
offline analyses run against the completed property graph via `epistemetrics`. `structural_correspondence`
scores stored on edges provide input data for coherence and compatibility evaluation, while during construction the
`ArtifactExecutionEngine` evaluates lightweight inter-phase `EpistemicQualityGate` circuit breakers (`OntologyEntropyGate`,
`PercolationQualityGate`, and `ConformalCalibrationGate`, see `ISSUE-058`) to detect ontological collapse, giant-component
percolation, or conformal OOD spikes before downstream LLM compute is expended.

---

## Default Prompt Template (SC_PROMPT)

```
You are an expert in {domain}.

You are evaluating whether two nodes in a knowledge graph have sufficient
structural overlap (strukturelle Überlagerung) to justify the relation
"{relation_type}" between them.

### Node A
Label: {source_type}
Name: {node_a_name}
Description: {node_a_description}
Neighbourhood: {node_a_neighbourhood}

### Node B
Label: {target_type}
Name: {node_b_name}
Description: {node_b_description}
Neighbourhood: {node_b_neighbourhood}

### Task
Score the structural correspondence between Node A and Node B for the
relation "{relation_type}" on a scale from 0.0 (no correspondence) to 1.0
(strong structural overlap). Explain your reasoning briefly.

Output strictly valid JSON:
{{"score": <float 0.0-1.0>, "reasoning": "<one sentence>"}}
```

Override via `StructuralCorrespondenceConfig.prompt_template`.

---

## Consequences

- `QBAF`, `QBAFMapper`, and all `qbaf_weight` fields are deprecated and will be removed once `TF` and `TFMapper` are
  implemented.
- `pipeline/contracts/domain.py` may gain a `TF(BaseModel)` struct alongside the deprecated `QBAF`. If introduced,
  QBAF/TF should remain optional projections over argument artifacts rather than mandatory runtime contracts.
- `schema.md` is updated to replace the QBAF mapping table with TF terminology and to document
  `structural_correspondence` as a standard edge property.
- `Phase4Config` gains a `tf_mapper` field replacing `qbaf_mapper`.
- `PipelineConfig` gains a `structural_correspondence: StructuralCorrespondenceConfig` field (default: disabled).
- ADR-0006's three open questions about weight semantics are dissolved: weights are replaced by
  `structural_correspondence` scores, which have a well-defined interpretation (κ-admissibility per the formal chapter).

---

## Related

- `../../paper/chapters/1_formal_aspects_tf.tex` — formal definition of TF, κ, structural overlap
- `../../review/formal_chapter_analysis.md` — analysis of Definition 3 in the formal chapter; the SC step implements the
  construction-time component of the formalism
- ADR-0002 — TAG retrieval for global relation extraction (SC uses the same neighbourhood retrieval mechanism)
- ADR-0005 — Pipeline consolidation and fusion sequence
- `pipeline/contracts/domain.py` — `QBAF` (deprecated), `TF` (to add)
- `pipeline/phases/phase4_argument_mining/qbaf_mapper.py` — `QBAFMapper` (to be replaced by `TFMapper`)

