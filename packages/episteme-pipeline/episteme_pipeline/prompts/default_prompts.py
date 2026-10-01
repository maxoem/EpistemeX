"""
Default prompt templates for all pipeline phases.

Each template uses {placeholder} syntax for runtime injection.
Override any template via the corresponding PhaseNConfig field using StructuredPromptBundle.
"""

# ---------------------------------------------------------------------------
# Phase 2 — NER and Local Relation Extraction
# ---------------------------------------------------------------------------

NER_DIRECT_PROMPT = """\
You are an expert in formal logic and the history of philosophy.
Extract all entities and their local relations from the following text chunk.

{global_structural_anchor}

{working_memory_context}

### Entity Types (use exactly these labels)
{entity_types}

### Relation Types (use exactly these labels)
{relation_types}

### Instructions
1. First identify logical connectives and argument structure (chain-of-thought step).
2. Then classify each entity span and extract local triples.
3. Resolve pronouns or aliases using both local text and the provided active Short-Term Memory context.
4. Output strictly valid JSON matching the schema below. No text outside the JSON.

### Output Schema
{{
  "entities": [{{"id": "<str>", "label": "<entity_type>", "name": "<canonical name>", "text": "<span>"}}],
  "triples":  [{{"subject_id": "<str>", "predicate": "<relation_type>", "object_id": "<str>", "confidence": <float 0-1>}}],
  "working_memory": {{"state_delta": {{"active_entities": ["<str>"], "unresolved_references": ["<str>"], "current_argument_branch": "<str>"}}, "boundary_detected": false, "transitional_summary": null}}
}}

### Input Text
{chunk_text}
"""

NER_REASONING_PROMPT = """\
You are an expert in formal logic and the history of philosophy.
Analyze the following text chunk and identify all entities and their local relations.

{global_structural_anchor}

{working_memory_context}

### Entity Types
{entity_types}

### Relation Types
{relation_types}

### Instructions
1. First, identify logical connectives and argument structure.
2. Discuss potential entity spans and their classification.
3. Identify potential local relations between these entities.
4. Resolve pronouns or aliases using the active Short-Term Memory context.
Provide a detailed chain-of-thought reasoning step by step. Do NOT output JSON.

### Input Text
{chunk_text}
"""

NER_FORMAT_PROMPT = """\
You are an expert data extractor. Convert the provided reasoning into a strict JSON format.

### Entity Types
{entity_types}

### Relation Types
{relation_types}

### Reasoning Output
{reasoning_text}

### Instructions
Output strictly valid JSON matching the schema below based on the reasoning provided. No text outside the JSON.

### Output Schema
{{
  "entities": [{{"id": "<str>", "label": "<entity_type>", "name": "<canonical name>", "text": "<span>"}}],
  "triples":  [{{"subject_id": "<str>", "predicate": "<relation_type>", "object_id": "<str>", "confidence": <float 0-1>}}],
  "working_memory": {{"state_delta": {{"active_entities": ["<str>"], "unresolved_references": ["<str>"], "current_argument_branch": "<str>"}}, "boundary_detected": false, "transitional_summary": null}}
}}
"""

NER_GLEANING_PROMPT = """\
You previously extracted entities from the following text:
--------
{chunk_text}
--------
These were already extracted:
{prior_extractions}

Are there any OTHER entities or arguments in the text that were not extracted? Extract them using the exact same schema. If none, return empty lists.
"""

# ---------------------------------------------------------------------------
# Phase 2 — Entity Linking (cross-encoder reranking prompt)
# ---------------------------------------------------------------------------

ENTITY_LINKING_PROMPT = """\
You are resolving whether two entity mentions refer to the same real-world object.

### Mention A
Text: {mention_a_text}
Context chunk: {mention_a_context}

### Candidate B (from existing graph)
Name: {candidate_name}
Description: {candidate_description}
Related nodes: {candidate_neighborhood}

### Question
Do Mention A and Candidate B refer to the exact same entity?
Answer strictly: {{"same_entity": true/false, "confidence": <float 0-1>, "reasoning": "<one sentence>"}}
"""

# ---------------------------------------------------------------------------
# Phase 3 — Global Relation Extraction
# ---------------------------------------------------------------------------

GLOBAL_RELATION_DIRECT_PROMPT = """\
You are an expert in philosophy of science and formal argumentation.
Given two entities and their local subgraph context, determine whether
a meaningful semantic relation exists between them across document sections.

### Entity A
ID: {entity_a_id}
Name: {entity_a_name}
Type: {entity_a_type}
Local context: {entity_a_context}

### Entity B
ID: {entity_b_id}
Name: {entity_b_name}
Type: {entity_b_type}
Local context: {entity_b_context}

### Relation Types (use exactly these labels)
{relation_types}

### Subgraph Envelope
{subgraph_envelope}

### Instructions
Determine if a relation holds between Entity A and Entity B.
If no meaningful relation exists, set "relation" to null.
Output strictly valid JSON:
{{
  "relation": "<relation_type or null>",
  "confidence": <float 0-1>,
  "direction": "A_to_B or B_to_A",
  "reasoning": "<one sentence>"
}}
"""

GLOBAL_RELATION_REASONING_PROMPT = """\
You are an expert in philosophy of science and formal argumentation.
Analyze whether a meaningful semantic relation exists between two entities across document sections.

### Entity A
ID: {entity_a_id}
Name: {entity_a_name}
Type: {entity_a_type}
Local context: {entity_a_context}

### Entity B
ID: {entity_b_id}
Name: {entity_b_name}
Type: {entity_b_type}
Local context: {entity_b_context}

### Relation Types
{relation_types}

### Subgraph Envelope
{subgraph_envelope}

### Instructions
1. Consider the definitions and properties of Entity A and Entity B.
2. Analyze the provided subgraph envelope to find semantic connections.
3. Determine if one of the specified relation types holds between them.
4. Discuss the direction of the relationship (A_to_B or B_to_A) and confidence.
Provide detailed step-by-step reasoning. Do NOT output JSON.
"""

GLOBAL_RELATION_FORMAT_PROMPT = """\
You are an expert data extractor. Convert the provided reasoning into a strict JSON format.

### Relation Types
{relation_types}

### Reasoning Output
{reasoning_text}

### Instructions
Based on the reasoning provided, determine the relation between Entity A and Entity B.
If no meaningful relation exists, set "relation" to null.
Output strictly valid JSON:
{{
  "relation": "<relation_type or null>",
  "confidence": <float 0-1>,
  "direction": "A_to_B or B_to_A",
  "reasoning": "<one sentence summarizing the input>"
}}
"""

# ---------------------------------------------------------------------------
# Phase 4 — ADU Segmentation
# ---------------------------------------------------------------------------

ADU_SEGMENTATION_PROMPT = """\
You are an expert in argumentation theory.
Identify all Argumentative Discourse Units (ADUs) in the following text.

### Instructions
1. Identify argument vs. non-argument spans (remove "shell" language like "I think the lesson is...").
2. Wrap each ADU in markup tags: <AC1>text</AC1>, <AC2>text</AC2>, etc.
3. Return the full text with markup tags inserted. Do not alter the original wording.
4. Also return a list of identified AC IDs.

### Output Schema
{{
  "tagged_text": "<full text with <ACn>...</ACn> markup>",
  "adu_ids": ["AC1", "AC2", ...]
}}

### Input Text
{chunk_text}
"""

# ---------------------------------------------------------------------------
# Phase 4 — Argument Component Classification (ACC)
# ---------------------------------------------------------------------------

ACC_DIRECT_PROMPT = """\
You are an expert in argumentation theory and philosophy of science.
Given the following text with pre-identified Argumentative Discourse Units (ADUs),
classify each ADU and identify all support and attack relations between them.

### Available Entities
{chunk_entities}

### Component Types (use exactly these labels)
{component_types}

### Relation Types (use exactly these labels)
{argument_relation_types}

### Instructions
1. For each <ACn> tag, assign exactly one component type.
2. Identify all local support and attack relations between ADUs.
3. Determine which of the available entities are explicitly mentioned or primarily discussed in each ADU.
4. For each component, determine its Epistemic Status (Synthetisch or Analytisch) and Scope/Type (Essentieller Allsatz, Existenzsatz, Statistischer/probabilistischer Allsatz, Lokalisierter Existenzsatz, or Lokalisierter Allsatz).
5. Output strictly valid JSON. No text outside the JSON.
6. Validate: the number of classified components must equal the number of input AC tags.

### Output Schema
{{
  "components": [{{"id": "<ACn>", "component_type": "<type>", "text": "<original span>", "plausibility": <float 0-1>, "entity_ids": ["<entity_id>"], "epistemic_status": "<Synthetisch|Analytisch>", "scope_type": "<Essentieller Allsatz|Existenzsatz|Statistischer/probabilistischer Allsatz|Lokalisierter Existenzsatz|Lokalisierter Allsatz>"}}],
  "relations":  [{{"source_id": "<ACn>", "relation": "<relation_type>", "target_id": "<ACm>", "confidence": <float 0-1>, "weight": <float 0-1>}}]
}}

### Input Text (with ADU markup)
{tagged_text}
"""

ACC_REASONING_PROMPT = """\
You are an expert in argumentation theory and philosophy of science.
Analyze the following text with pre-identified Argumentative Discourse Units (ADUs) and reason about their classification and relations.

### Available Entities
{chunk_entities}

### Component Types
{component_types}

### Relation Types
{argument_relation_types}

### Instructions
1. For each <ACn> tag, discuss which component type it represents based on its content.
2. Discuss which of the available entities are mentioned or discussed in each ADU.
3. Analyze potential local support and attack relations between the ADUs.
4. Analyze the Epistemic Status (Synthetisch vs. Analytisch) and Scope/Type (Essentieller Allsatz, Existenzsatz, Statistischer/probabilistischer Allsatz, Lokalisierter Existenzsatz, Lokalisierter Allsatz) for each component.
5. Ensure every AC tag is discussed.
Provide a detailed chain-of-thought reasoning step by step. Do NOT output JSON.

### Input Text (with ADU markup)
{tagged_text}
"""

ACC_FORMAT_PROMPT = """\
You are an expert data extractor. Convert the provided argumentation reasoning into a strict JSON format.

### Component Types
{component_types}

### Relation Types
{argument_relation_types}

### Reasoning Output
{reasoning_text}

### Instructions
1. Output strictly valid JSON. No text outside the JSON.
2. Validate: the number of classified components must equal the number of input AC tags analyzed in the reasoning.

### Output Schema
{{
  "components": [{{"id": "<ACn>", "component_type": "<type>", "text": "<original span>", "plausibility": <float 0-1>, "entity_ids": ["<entity_id>"], "epistemic_status": "<Synthetisch|Analytisch>", "scope_type": "<Essentieller Allsatz|Existenzsatz|Statistischer/probabilistischer Allsatz|Lokalisierter Existenzsatz|Lokalisierter Allsatz>"}}],
  "relations":  [{{"source_id": "<ACn>", "relation": "<relation_type>", "target_id": "<ACm>", "confidence": <float 0-1>, "weight": <float 0-1>}}]
}}
"""

# ---------------------------------------------------------------------------
# Phase 4 — ARC: Global Argument Relation Classification
# ---------------------------------------------------------------------------

ARC_DIRECT_PROMPT = """\
You are an expert in argumentation theory and philosophy of science.
Given two argument components from different parts of a document, determine
whether one supports or attacks the other, using the surrounding graph context.

### Component A
ID: {component_a_id}
Type: {component_a_type}
Text: {component_a_text}

### Component B
ID: {component_b_id}
Type: {component_b_type}
Text: {component_b_text}

### Relation Types (use exactly these labels)
{argument_relation_types}

### Graph Context (subgraph envelope)
{subgraph_envelope}

### Instructions
Determine whether Component A and Component B are argumentatively related.
Consider: does A provide evidence for B? Does A contradict B?
If no meaningful relation exists, set "relation_type" to null.
Output strictly valid JSON:
{{
  "relation_type": "<relation_type or null>",
  "confidence": <float 0-1>,
  "weight": <float 0-1>,
  "direction": "A_to_B or B_to_A",
  "reasoning": "<one sentence>"
}}
"""

ARC_REASONING_PROMPT = """\
You are an expert in argumentation theory and philosophy of science.
Analyze whether two argument components from different parts of a document are argumentatively related.

### Component A
ID: {component_a_id}
Type: {component_a_type}
Text: {component_a_text}

### Component B
ID: {component_b_id}
Type: {component_b_type}
Text: {component_b_text}

### Relation Types
{argument_relation_types}

### Graph Context (subgraph envelope)
{subgraph_envelope}

### Instructions
1. Consider: does Component A provide evidence for Component B? Does A contradict B?
2. Analyze the surrounding graph context for additional clues.
3. Determine if one of the relation types holds between the components.
Provide detailed step-by-step reasoning. Do NOT output JSON.
"""

ARC_FORMAT_PROMPT = """\
You are an expert data extractor. Convert the provided argumentation reasoning into a strict JSON format.

### Relation Types
{argument_relation_types}

### Reasoning Output
{reasoning_text}

### Instructions
Based on the reasoning provided, determine whether the components are related or not (null).
Output strictly valid JSON:
{{
  "relation_type": "<relation_type or null>",
  "confidence": <float 0-1>,
  "weight": <float 0-1>,
  "direction": "A_to_B or B_to_A",
  "reasoning": "<one sentence summarizing the reasoning>"
}}
"""

# ---------------------------------------------------------------------------
# Phase 4 — Entity Maturation (Batch Epistemic Synthesis)
# ---------------------------------------------------------------------------

ENTITY_SYNTHESIS_PROMPT = """\
You are an expert in philosophy of science and formal ontology construction.
Your task is to synthesize a single, mature, and epistemically rich description for the following entity, based on its most representative mentions across the text.

### Entity Name
{entity_name}

### Representative Contexts (Top-k Envelopes)
{envelopes}

### Instructions
1. Read all the provided representative contexts carefully.
2. Synthesize these contexts into a cohesive, concise, and academic canonical description of the entity.
3. The description should capture the core logical subject as it is used in the text.
4. Output strictly valid JSON. No text outside the JSON.

### Output Schema
{{
  "description": "<synthesized description>"
}}
"""

# ---------------------------------------------------------------------------
# Theoretical Enrichment & Tenability Evaluation Post-Processor
# ---------------------------------------------------------------------------

THEORY_INDUCTION_DIRECT_PROMPT = """\
You are an expert in formal epistemology, philosophy of science, and structuralist metatheory (Sneed, Stegmüller, Balzer).
Analyze the extracted theoretical hypotheses and empirical observations from a scientific/philosophical text, and induce the formal Theory-Elements T = <K, I> operating within it.

Each Theory-Element must specify:
1. theory_id: A concise snake_case identifier (e.g. "psychoanalysis", "cellular_neurobiology", "rational_choice").
2. name: Full title of the theory.
3. description: Brief summary of the theoretical paradigm.
4. claimant_hypothesis_ids: IDs of the hypotheses in the text that belong to this theoretical framework.
5. required_dimensions: Theory-independent observable empirical dimensions (M_pp) required to test or apply the theory.
6. parameter_names: Latent, non-directly observable theoretical parameters (M_p) postulated by the theory.
7. laws: Core mathematical or relational axioms (M) relating the parameters, with normalized constraint formulas (e.g. "abs(param_a - param_b) * 0.5").

### Extracted Theoretical Hypotheses (Partition A)
{theoretical_hypotheses}

### Extracted Empirical Observations & Dimensions (Partition B)
{empirical_observations}

### Structural Relations
{structural_relations}

### Instructions
1. Induce up to {max_theories} distinct theories present in the text.
2. Ensure clear separation between observable dimensions (M_pp) and latent parameters (M_p).
3. Formulas in laws must reference the defined parameter names.
4. Output strictly valid JSON matching the schema.
"""

CLUSTER_PROJECTION_DIRECT_PROMPT = """\
You are an expert in epistemic data projection and structuralist metatheory.
Project the following empirical cluster (Intended Application I) through the lens of Theory Element "{theory_name}".

Theory Specification:
- Non-theoretical dimensions (M_pp): {required_dimensions}
- Postulated latent parameters (M_p): {parameter_names}
- Core laws (M): {theory_laws}

Cluster Observations:
{cluster_observations}

### Instructions
1. For each required empirical dimension, estimate or normalize its value in [0.0, 1.0] from the observations.
2. For each postulated theoretical parameter, estimate its value in [0.0, 1.0] based on the theoretical interpretation of the observations.
3. Provide a brief rationale for the fit.
4. Output strictly valid JSON matching the schema.
"""


# ---------------------------------------------------------------------------
# Decision Engine Prompts & Rubrics (System 1 Gating & Classification)
# ---------------------------------------------------------------------------

DECISION_EPISTEMIC_RELEVANCE_QUESTION = """\
Is this text chunk substantively relevant to philosophical, theoretical, or scientific arguments and concepts, as opposed to metadata, index, bibliography, acknowledgments, or administrative boilerplate?
"""

DECISION_EPISTEMIC_RELEVANCE_CRITERIA = {
    "relevant": (
        "Substantive content containing philosophical, theoretical, or scientific claims, "
        "premises, arguments, definitions, or conceptual analysis."
    ),
    "non_relevant": (
        "Bibliographic references, table of contents, index, copyright notices, "
        "author biographies, publication metadata, or administrative boilerplate text."
    ),
}

DECISION_ACC_QUESTION = """\
What is the functional argumentative component type of the following text unit?
"""

DECISION_ACC_CRITERIA = {
    "CLAIM": (
        "A central proposition, thesis, conclusion, or assertion put forward by an author "
        "that requires justification or evidence."
    ),
    "PREMISE": (
        "A statement, piece of evidence, reason, or assumption offered in support of "
        "or in opposition to a claim."
    ),
    "CONCLUSION": (
        "A statement derived logically from one or more premises within a reasoning chain."
    ),
    "MAJOR_CLAIM": (
        "The overarching, primary thesis or contention of the entire philosophical text or work."
    ),
    "NONE": (
        "Non-argumentative, expository, narrative, or background discourse without "
        "an inferential argumentative role."
    ),
}

DECISION_ARC_QUESTION = """\
What argumentative or dialectical relation holds from the source proposition to the target proposition?
"""

DECISION_ARC_CRITERIA = {
    "SUPPORTS": (
        "The source proposition provides evidence, justification, entailment, or logical backing "
        "for the target proposition."
    ),
    "ATTACKS": (
        "The source proposition directly refutes, contradicts, or rebuts the target proposition."
    ),
    "UNDERCUTS": (
        "The source proposition challenges the inferential link, premise applicability, or relevance "
        "between the target and its premises without necessarily denying the target directly."
    ),
    "NEUTRAL": (
        "No inferential, supporting, or defeating relation holds between source and target."
    ),
}

DECISION_BOUNDARY_QUESTION = """\
Does the current text segment mark a semantic or argumentative boundary indicating a shift in topic, argument branch, or structural section?
"""

DECISION_BOUNDARY_CRITERIA = {
    "BOUNDARY": (
        "A clear transition, topical break, conclusion of a proof or argument branch, "
        "or shift to a new dialectical context."
    ),
    "CONTINUATION": (
        "The text continues the active argument, elaboration, or logical deduction of "
        "the current context."
    ),
}

