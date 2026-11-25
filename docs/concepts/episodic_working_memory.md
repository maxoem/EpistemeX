# SOTA Dual-Memory Architecture & Episodic Working Memory

This document details the **formal theoretical concept** and **architecture** of the **SOTA Dual-Memory System** and
**Episodic Working Memory** (Stateful Context Tracking) within **Episteme**.

---

## Formal Concept & Motivation

In dense scientific and philosophical literature (e.g., Kant, Carnap, Hegel), foundational premises, definitions, or
methodological rules are established in early sections of a text. Subsequent chapters build upon these foundational
concepts, often using evolved terminology or implicit demonstratives (e.g., "this assumption", "the second premise").

Processing document chunks in complete isolation causes evidence fragmentation, pronoun ambiguity, and retrieval failure
in dense vector spaces. Modern state-of-the-art (SOTA) agentic architectures solve this by operating on a **dual-memory
structure**:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 DOCUMENT INGESTION                      │
                  └──────────────────────────┬──────────────────────────────┘
                                             │
                                             ▼
  ┌───────────────────────────────────────────────────────────────────────────────────────┐
  │                           SHORT-TERM MEMORY (STM / RAM)                               │
  │  • Global Structural Anchor (Global ToC / Chapter Outlines)                           │
  │  • Decoupled Structured State Machine (active_entities, unresolved_references, ...)  │
  │  • Transitional Episode Context                                                       │
  └──────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │
                       Local Variable        │  Canonical Identity
                       Resolution            │  Query / Flush
                                             ▼
  ┌───────────────────────────────────────────────────────────────────────────────────────┐
  │                            LONG-TERM MEMORY (LTM / DISK)                              │
  │  • Neo4j Heterogeneous Property Graph (L1 Chunks, L2 Entities, L3 Argument Components) │
  │  • Persistent Topological Storage & Provenance Tracking                               │
  └───────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Main Context / Short-Term Memory (STM):** Functions as the system's **RAM**. It maintains a rolling, structured
   state machine across sequential text chunks. This provides the local context necessary to decode implicit references
   (e.g., resolving "this assumption" locally into `Premise_4_Utilitarianism`) before querying LTM using a precise
   canonical identifier rather than a vague semantic vector.
2. **External Context / Long-Term Memory (LTM):** Functions as the system's **Disk**. It is the persistent property
   graph in Neo4j storing canonical entities, formal relations, and argument structures.

---

## Core Architectural Pillars

### A. Global Structural Anchor (Global Structure)

Before processing document chunks, the system supplies the LLM prompt with a **Global Structural Anchor**—the document's
overarching structural blueprint (Table of Contents, chapter outlines, or global summary).

- **Function:** Serves as a static, persistent coordinate system in the prompt.
- **Benefit:** When processing Chunk 50, knowing that the text currently resides under
  `"Chapter 3: The Critique of Pure Reason"` drastically reduces misinterpretation of localized arguments and prevents
  semantic disorientation across long texts.

### B. Decoupled Structured State Machine ("Write" Phase)

Naive memory prompting—asking an LLM to simply "summarize what was learned in these pages"—functions as a lossy
compression algorithm. Over long texts, critical nuances degrade and memory drifts into vague generalizations.

Instead, the STM operates as a **structured state machine**. At the end of each processed chunk, the model updates
explicit state variables:

- `active_entities`: Concepts, entities, or authors currently under active discussion.
- `unresolved_references`: Open demonstratives, pronouns, or unanchored claims awaiting formal definition.
- `current_argument_branch`: The specific premise or logical claim currently being constructed.

> **Design & Decoupling Requirement:** The state machine interface MUST be decoupled from specific serialization formats
> (e.g., JSON patches, Pydantic models, or key-value state dictionaries). Pipeline implementations should expose an
> abstract state interface, enabling empirical evaluation of different state representations without locking the pipeline
> to a single format.

### C. Boundary-Based Episodic Eviction ("Eviction & Reset" Phase)

Arbitrary sliding windows (FIFO token buffers) are mathematically arbitrary; they sever context based on token counts
rather than semantic logic. Episteme implements **Episodic Eviction**:

1. **Monitor State:** As chunks are sequentially processed, the LLM monitors for semantic boundaries (e.g., end of a
   sub-chapter, shift in primary argument, or topic transition).
2. **Commit Extracted Graph Elements:** Extracted domain entities, argument components, and relations ($\Delta G_i$)
   identified during the episode are committed to the Neo4j Long-Term Memory graph. The STM state itself is **never**
   committed to the graph.
3. **Reset Short-Term Memory:** Short-lived variables in the STM (`active_entities`, `unresolved_references`,
   `current_argument_branch`) are purged from runtime memory (RAM), retaining only the Global Structural Anchor (ToC)
   and immediate transitional context necessary to begin the next semantic episode.

---

## Phase Boundaries & Separation of Concerns

To preserve architectural modularity:

- **Phase 2 (Entity Discovery) & Phase 3 (Global Relations):** Rely exclusively on **Episodic Working Memory (STM)** as
  runtime context passed across sequential iterations ($S_{i-1} \rightarrow S_i$) for context tracking and
  pronoun/demonstrative resolution during chunk extraction.
- **Phase 5 (Alignment & Fusion):** Reserves **Leiden Community Detection** and macroscopic community summarization
  exclusively for post-processing graph fusion and global theory discovery. Community summaries do not replace local
  entity definitions during Phase 2/3 extraction.

---

## Formal State Transition Model

Let $C_i$ be document chunk $i$, $A_{\text{anchor}}$ be the static Global Structural Anchor (ToC outline), and $S_{i-1}$ be the structured STM
state from chunk $i-1$.

\[ (S_i, \Delta G_i, B_i) = \text{LLM\_Extract} (C_i, A_{\text{anchor}}, S_{i-1})
\]

Where:

- $S_i$: Updated short-term state variables (`active_entities`, `unresolved_references`, `current_argument_branch`)
  passed to the **next extraction iteration** in runtime memory.
- $\Delta G_i$: Domain entity nodes, argument components, and relations extracted from chunk $C_i$, which are committed
  to **Neo4j LTM**.
- $B_i \in \{0, 1\}$: Boolean indicator denoting whether a semantic boundary was detected.

Process per chunk iteration:

1. $\text{Commit} (\Delta G_i) \longrightarrow \text{Neo4j LTM}$
2. If $B_i = 1$ (Episodic Eviction triggered):
    - $S_i \longrightarrow \text{Reset} (S_i, A_{\text{anchor}})$  *(Purge short-lived variables from RAM; STM is never written to
      Neo4j)*

---

## Related Documentation

- **ADR**: [ADR 0009: SOTA Dual-Memory Architecture](../adr/0009-sota-dual-memory-episodic-working-memory.md)
- **Dense Alignment & Maturation**: [Dense Alignment & Grounding](dense_alignment.md)
- **Formal Graph Schema**: [Formal Graph Schema & Argumentation Semantics](formal_graph_model.md)
- **Topologies & Leiden Clustering**: [Theory-Nets, Posets & Topologies](theory_nets_and_topologies.md)
- **Pipeline Architecture**: [Pipeline Architecture](../architecture/pipeline_architecture.md)
- **Phase 2 Workflow**: [Phase 2: Entity Discovery Workflow](../workflow/2_entity_discovery/pipeline_explanation.md)
- **Terminology**: [Glossary](glossary.md)
