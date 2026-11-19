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

PAIR_GATING_DECISION_PROMPT = """Is there a direct theoretical or semantic relationship between {entity_a} and {entity_b}?"""

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
2. Identify all local support, attack, backing, and undercutting relations between ADUs (including optional conjunctive `premise_ids` when multiple premises must hold jointly to support/attack a target, and optional `id` / `undercuts_relation_id` when a relation backs or undercuts a specific inference rather than a node).
3. Determine which of the available entities are explicitly mentioned or primarily discussed in each ADU.
4. For each component, determine its Epistemic Status (Synthetisch or Analytisch) and Scope/Type (Essentieller Allsatz, Existenzsatz, Statistischer/probabilistischer Allsatz, Lokalisierter Existenzsatz, or Lokalisierter Allsatz).
5. Classify each component's `intensional_mode` ("asserted" = committed by author, "attributed" = opponent/prior thinker view, "suppositional" = Reductio ad absurdum / counterfactual premise, "historical" = archival background) and set `attributed_to` when attributed.
6. Output strictly valid JSON. No text outside the JSON.
7. Validate: the number of classified components must equal the number of input AC tags.

### Output Schema
{{
  "components": [{{"id": "<ACn>", "component_type": "<type>", "text": "<original span>", "plausibility": <float 0-1>, "entity_ids": ["<entity_id>"], "epistemic_status": "<Synthetisch|Analytisch>", "scope_type": "<Essentieller Allsatz|Existenzsatz|Statistischer/probabilistischer Allsatz|Lokalisierter Existenzsatz|Lokalisierter Allsatz>", "intensional_mode": "<asserted|attributed|suppositional|historical>", "attributed_to": "<agent_name_or_null>"}}],
  "relations":  [{{"id": "<optional_relation_id>", "source_id": "<ACn>", "premise_ids": ["<ACn>", "..."], "relation": "<relation_type>", "target_id": "<ACm>", "undercuts_relation_id": "<optional_target_relation_id>", "confidence": <float 0-1>, "weight": <float 0-1>}}]
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
3. Analyze potential local support, attack, backing, and undercutting relations between the ADUs, noting where multiple premises operate conjunctively (`premise_ids`) or where an ADU undercuts/backs an inference link (`undercuts_relation_id`).
4. Analyze the Epistemic Status (Synthetisch vs. Analytisch) and Scope/Type (Essentieller Allsatz, Existenzsatz, Statistischer/probabilistischer Allsatz, Lokalisierter Existenzsatz, Lokalisierter Allsatz) for each component, plus its intensional_mode ("asserted", "attributed", "suppositional", or "historical") and attributed_to agent if attributed.
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
  "components": [{{"id": "<ACn>", "component_type": "<type>", "text": "<original span>", "plausibility": <float 0-1>, "entity_ids": ["<entity_id>"], "epistemic_status": "<Synthetisch|Analytisch>", "scope_type": "<Essentieller Allsatz|Existenzsatz|Statistischer/probabilistischer Allsatz|Lokalisierter Existenzsatz|Lokalisierter Allsatz>", "intensional_mode": "<asserted|attributed|suppositional|historical>", "attributed_to": "<agent_name_or_null>"}}],
  "relations":  [{{"id": "<optional_relation_id>", "source_id": "<ACn>", "premise_ids": ["<ACn>", "..."], "relation": "<relation_type>", "target_id": "<ACm>", "undercuts_relation_id": "<optional_target_relation_id>", "confidence": <float 0-1>, "weight": <float 0-1>}}]
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

DECISION_INTENSIONAL_MODE_QUESTION = """\
What is the intensional epistemic mode and attribution status of the following argumentative unit?
"""

DECISION_INTENSIONAL_MODE_CRITERIA = {
    "asserted": (
        "A claim directly endorsed or asserted as true in the author's own primary voice."
    ),
    "attributed": (
        "A position, thesis, or objection attributed to another thinker, interlocutor, "
        "opponent, or school of thought rather than endorsed by the author."
    ),
    "suppositional": (
        "A hypothetical, counterfactual, or Reductio ad absurdum assumption entertained "
        "only provisionally for the sake of argument or derivation."
    ),
    "historical": (
        "Background historical context, established mathematical or empirical tradition, "
        "or general scholarly framing not tied to an unshared opponent position."
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
    "SUPPORTS_ARG": (
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

DECISION_GLEANING_QUESTION = """\
Does the source text contain salient theoretical assertions, definitions, or argument components that are missing from the current extraction list?
"""

DECISION_BORDERLINE_MERGE_QUESTION = """\
What is the ontological relationship between the following two concepts?
"""

DECISION_BORDERLINE_MERGE_CRITERIA = {
    "IDENTICAL_MERGE": (
        "The two entities refer to the identical underlying philosophical concept or term "
        "and should be merged into a single canonical node."
    ),
    "HIERARCHICAL_SUBSUMPTION": (
        "One entity is a subspecies, subconcept, or hierarchical variant of the other "
        "and must remain structurally distinct."
    ),
    "DISTINCT_SEPARATE": (
        "The entities are conceptually distinct, contrasting, or independent concepts "
        "and must not be merged."
    ),
}

DECISION_CANONICAL_ELECTION_QUESTION = """\
Which of the following candidate entity names is the standard canonical scholarly designation?
"""

DECISION_THEORY_FUSION_QUESTION = """\
Determine whether the theoretical constructs from different document contexts are semantically equivalent for knowledge graph fusion:
"""

DECISION_THEORY_FUSION_CRITERIA = {
    "EQUIVALENT_FUSION": (
        "The constructs express the same underlying theory, core thesis, or foundational framework "
        "across documents and should be fused."
    ),
    "COMPETING_THEORIES": (
        "The constructs represent competing, rival, or mutually incompatible philosophical theories "
        "and must remain separate in the knowledge graph."
    ),
    "DISTINCT_APPLICATIONS": (
        "The constructs represent distinct contextual applications or disparate concepts "
        "and must not be collapsed into a single macro-cluster."
    ),
}

# =============================================================================
# HERMENEUTIC REFINEMENT PROMPTS (CLOSED-LOOP DEFICIT RESOLUTION)
# =============================================================================

CONCEPT_SPLIT_PROMPT = """\
You are an expert in philosophical ontology, lexical semantics, and structuralist metatheory.
A hub entity appears to conflate two or more incompatible theoretical senses across contexts.
Partition ONLY the provided contexts of this entity into distinct conceptual senses.

### Target Entity
ID: {entity_id}
Name: {entity_name}
Type: {entity_label}
Description: {entity_description}

### Deficit Context
Theory ID: {theory_id}
Theory Lens: {theory_lens}
Rationale: {rationale}

### Conflicting Argument Atoms
{entity_atoms}

### Entity Source Chunks
{source_chunks}

### Instructions
1. Identify at least 2 distinct conceptual senses present in the provided chunks: {allowed_chunk_ids}.
2. Assign each sense a concise ``perspective`` label, a ``description``, and the exact subset of
   ``chunk_ids`` from [{allowed_chunk_ids}] that belong to that sense.
3. Do not invent chunk IDs outside [{allowed_chunk_ids}].
4. Output strictly valid JSON matching the schema.
"""

PREMISE_RECOVERY_PROMPT = """\
You are an expert in formal argumentation, philosophy of science, and structuralist metatheory.
An argument component lacks explicit supporting premises or a bridging warrant (an enthymeme gap).
Re-read ONLY the provided source chunk(s) through the supplied macro-theory lens and recover any
implicit premises or bridging warrants implied by the prose.

### Theory Context (Macro-Theory Lens)
Theory ID: {theory_id}
Theory Lens: {theory_lens}
Deficit Rationale: {rationale}

### Target Ungrounded Claim(s)
{target_claims}

### Existing Argument Components in Target Chunks
{existing_atoms}

### Scoped Entities
{chunk_entities}

### Allowed Component Types
{component_types}

### Allowed Argument Relation Types
{argument_relation_types}

### Source Chunk Text(s)
{source_chunks}

### Instructions
1. Identify implicit premises, unstated auxiliary assumptions, or bridging warrants present or
   presupposed in the source chunk(s) that directly support or attack the target claim(s).
2. Ground each recovered premise in its exact ``source_chunk_id`` from [{target_chunk_ids}].
3. Specify ``target_atom_id`` and ``relation_type`` (choosing from Allowed Argument Relation Types),
   plus optional scoping fields (``scope_type``, ``epistemic_status``, ``intensional_mode``,
   and ``attributed_to``) when the passage asserts counterfactual, historical, or attributed scope.
4. Do not duplicate components already listed in Existing Argument Components.
5. Output strictly valid JSON matching the schema.
"""

AXIOM_GROUNDING_PROMPT = """\
You are an expert in empirical epistemology, scientific measurement extraction, and structuralist metatheory.
A theoretical hypothesis or axiom lacks sufficient empirical grounding (an UNGROUNDED_AXIOM deficit).
Inspect ONLY the provided targeted and immediate neighbor source chunks conditioned on the macro-theory
lens to extract missed empirical observation units, quantitative measurements, and grounding entities.

### Theory Lens (M_pp / M_p / M)
Theory ID: {theory_id}
Required Empirical Dimensions (M_pp): {required_dimensions}
Postulated Theoretical Parameters (M_p): {parameter_names}
Theory Lens Details: {theory_lens}
Deficit Rationale: {rationale}

### Target Ungrounded Axiom(s) / Hypothesis(es)
{target_atoms}

### Allowed Component Types
{component_types}

### Partition-B (Empirical Observation) Types
{observation_component_types}

### Allowed Argument Relation Types
{argument_relation_types}

### Scoped Source Chunks
{source_chunks}

### Instructions
1. Extract concrete empirical observation propositions matching [{observation_component_types}]
   from the provided chunks: [{allowed_chunk_ids}].
2. Attach explicit ``measurements`` (``dimension``, ``value``, optional ``unit``) aligning with
   the required empirical dimensions where present.
3. Ground each observation in its exact ``source_chunk_id`` from [{allowed_chunk_ids}] and link
   it to the target atom via ``target_atom_id`` and ``relation_type`` from Allowed Argument Relation Types.
4. Optionally extract any missed domain entities within those chunks.
5. Output strictly valid JSON matching the schema.
"""

DECISION_POLYSEMY_DISAMBIGUATION_QUESTION = """\
Does the target concept exhibit genuinely distinct, incompatible lexical or theoretical senses across these passages, or do the passages express dialectical disagreement using the same univocal concept?
"""

DECISION_POLYSEMY_DISAMBIGUATION_CRITERIA = {
    "TRUE_POLYSEMY_SPLIT": (
        "The entity name denotes two or more distinct conceptual senses, definitions, or "
        "referents across the provided passages and must be split into stratified conceptions."
    ),
    "UNIVOCAL_DISAGREEMENT": (
        "The entity denotes a single shared concept about which authors make competing "
        "affirmative and critical claims; keep the entity unified."
    ),
    "INSUFFICIENT_EVIDENCE": (
        "The provided passages do not establish clear semantic divergence; keep the entity unified."
    ),
}

DECISION_ENTHYMEME_RECOVERABILITY_QUESTION = """\
Does the provided source context contain an implicit premise, unstated theoretical assumption, or bridging warrant that supports or critiques the target claim?
"""

DECISION_OBSERVATION_GROUNDING_QUESTION = """\
Does the provided source passage contain an empirical observation, measurement, or experimental finding relevant to grounding the target theoretical hypothesis?
"""

