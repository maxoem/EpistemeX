# Run Report — ${RUN_ID}

Date: ${DATE}
Evaluation Mode: ${EVAL_MODE}
Corpus: ${CORPUS_NAME} (${VERSION}/${SPLIT})
Model: ${MODEL_PROVIDER}/${MODEL_NAME} (${MODEL_VERSION})
Prompts: ${PROMPT_IDS}
Schema: ${SCHEMA_ID}@${SCHEMA_VERSION}
Code: ${CODE_VERSION}

---

## 1. Summary
- Objective: ${OBJECTIVE}
- Key Findings:
  - ${HIGHLIGHT_1}
  - ${HIGHLIGHT_2}
  - ${HIGHLIGHT_3}
- Costs: tokens_prompt=${TOK_P}, tokens_completion=${TOK_C}, time=${TIME_S}s, memory=${MEM_MB}MB

---

## 2. Datasets
- Graph Extraction Gold Standards (EN): ${GRAPH_DATASETS_EN}
- Graph Extraction Gold Standards (DE): ${GRAPH_DATASETS_DE}
- Domain Review Set: ${REVIEWSET_INFO}

---

## 3. Methods and Settings
- Chunking: ${CHUNK_PARAMS}
- Retrieval: ${RETRIEVAL_PARAMS}
- Linking: ${LINK_PARAMS}
- Fusion: ${FUSION_PARAMS}
- Seeds: ${SEEDS}

---

## 4. Results

*(Note: Results are reported globally and broken down by EN/DE where applicable).*

### 4.1 Graph Structural Matching (Soft Metrics)
- Graph BERTScore (GM-GBS) @ 95% threshold: ${GM_GBS_SCORE}
- Graph Edit Distance (GED): ${GED_SCORE}
- Error Buckets: ${GM_GBS_ERRORS}

### 4.2 Hallucination & Omission (Optimal Edit Paths)
- Hallucination Rate (Fabricated Edges): ${OEP_HALLUCINATION_RATE}
- Omission Rate (Missed Edges): ${OEP_OMISSION_RATE}
- Error Buckets: ${OEP_ERRORS}

### 4.3 Reference-Free Evaluation (LLM-as-a-Judge)
- Faithfulness Score: ${LLM_FAITHFULNESS}
- Comprehensiveness Score: ${LLM_COMPREHENSIVENESS}
- Notable Hallucinations Detected: ${LLM_DETECTED_HALLUCINATIONS}

### 4.4 Graph Integrity (Neo4j)
- Constraints (unique/existence/type/key): ${CONSTRAINT_STATUS}
- Provenance Coverage: ${PROV_COVERAGE}
- Store Consistency: ${STORE_CONSISTENCY}

### 4.5 Stability
- Cross‑run variance (GM-GBS/OEP): ${STABILITY_STATS}

---

## 5. Qualitative Review
- Human Review Summary: ${HUMAN_REVIEW_SUMMARY}
- LLM‑as‑Judge Correlation: ${LLM_JUDGE_CORR}
- Notable Cases: ${CASE_LINKS}

---

## 6. Ablations and Baselines
- Baselines Compared: ${BASELINES}
- Prompt/Model Ablations: ${ABLATIONS}
- Observed Pipeline Lift: ${LIFT_SUMMARY}

---

## 7. Discussion
- Interpretation: ${INTERPRETATION}
- Limitations: ${LIMITATIONS}
- Next Actions: ${NEXT_ACTIONS}

---

## 8. Artifacts
- Manifest: ${MANIFEST_PATH}
- Phase Artifacts:
  - Chunking: ${ART_CHUNK}
  - Extracted Graphs: ${ART_EXTRACTED_GRAPHS}
  - OEP Diagnostics: ${ART_OEP_DIAGNOSTICS}
  - LLM Judge Transcripts: ${ART_LLM_JUDGE_TRANSCRIPTS}
  - Fusion: ${ART_FUSION}

