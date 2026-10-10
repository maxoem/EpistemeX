# LLM-as-a-Judge Reference-Free Evaluation Prompts

This document provides the standard zero-shot prompts to evaluate the extracted knowledge graph against the original source text when a gold standard is unavailable. 

These rubrics are designed to evaluate structural extraction without relying on rigid mapping tables, evaluating Faithfulness (Hallucinations) and Comprehensiveness (Omissions).

## Prompt 1: Faithfulness (Hallucination Detection)

**Objective:** Verify that every triple in the extracted graph is entirely supported by the source text.

**Prompt Template:**
```text
You are an expert evaluator of Knowledge Graphs constructed from scholarly scientific text.
Your task is to evaluate the Faithfulness of an extracted graph.

Here is the Original Text:
<text>
{{SOURCE_TEXT}}
</text>

Here is the Extracted Graph (represented as triples):
<graph>
{{EXTRACTED_TRIPLES}}
</graph>

For each triple in the Extracted Graph, determine if it is "Faithful" or a "Hallucination".
A triple is Faithful if the relationship it describes is explicitly stated or strongly implied by the Original Text.
A triple is a Hallucination if it invents information, infers a relationship that is not in the text, or significantly distorts the meaning of the text.

Output your evaluation in JSON format:
{
  "evaluations": [
    {
      "triple": "(head, relation, tail)",
      "status": "Faithful | Hallucination",
      "reasoning": "Brief explanation of why"
    }
  ],
  "faithfulness_score": <float between 0.0 and 1.0 (number of faithful triples / total triples)>
}
```

## Prompt 2: Comprehensiveness (Omission Detection)

**Objective:** Verify that the extracted graph captures all major claims and theoretical relationships from the source text.

**Prompt Template:**
```text
You are an expert evaluator of Knowledge Graphs constructed from scholarly scientific text.
Your task is to evaluate the Comprehensiveness of an extracted graph.

Here is the Original Text:
<text>
{{SOURCE_TEXT}}
</text>

Here is the Extracted Graph (represented as triples):
<graph>
{{EXTRACTED_TRIPLES}}
</graph>

Read the Original Text and identify the core theoretical claims, arguments, and entities.
Then, examine the Extracted Graph.

Did the graph miss any major relationships or entities that are critical to understanding the text's core argument?
If yes, list them as "Omissions". If the graph successfully captures the core meaning, state that there are no major omissions.

Output your evaluation in JSON format:
{
  "missed_key_points": [
    {
      "description": "Description of the missing claim/relationship",
      "severity": "High | Medium | Low"
    }
  ],
  "comprehensiveness_score": <float between 0.0 and 1.0, where 1.0 means no major omissions, scaling down based on severity of missed points>
}
```
