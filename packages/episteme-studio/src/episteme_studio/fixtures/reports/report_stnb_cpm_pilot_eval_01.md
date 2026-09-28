# Evaluation Report: eval_stnb_cpm_pilot_eval_01

- **Manifest:** `/Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/evaluation/manifests/eval_stnb.yaml`
- **Dataset:** `packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld`

# Formal Structuralist Model Evaluation Report

**Capability Subsumption ($G_{pred} \succeq_{cap} G_{ref}$):** ❌ FAILED (Capability Deficit)

## Quantitative Benchmark Metrics
- **Model Component Completeness (MCC):** 0.0000
- **Axiomatic Omission Rate (AOR):** 1.0000 (Laws Omitted ❌)
- **Property Fidelity Score (PFS):** 0.5000
- **Text Anchor Grounding IoU ($AG_{IoU}$):** 1.0000
- **Relational Edge Fidelity:** 0.0000

## Model Class Decomposition Breakdown
| Model Class | Symbol | Reference Count | Predicted Count | Matched | Completeness |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `potential_models` | $\mathcal{M}_p$ | 3 | 0 | 0 | 0.00% |
| `actual_models` | $\mathcal{M}$ | 6 | 0 | 0 | 0.00% |
| `partial_potential_models` | $\mathcal{M}_{pp}$ | 1 | 0 | 0 | 0.00% |
| `constraints` | $GC$ | 2 | 0 | 0 | 0.00% |
| `paradigms` | $I_0$ | 3 | 0 | 0 | 0.00% |
| `theory_elements` | $T$ | 4 | 0 | 0 | 0.00% |

## Omitted Reference Components
- ❌ Missing: `str:T_CPM_Base`
- ❌ Missing: `str:T_CPM_Grav`
- ❌ Missing: `str:T_CPM_Harmonic`
- ❌ Missing: `str:T_CPM_Free`
- ❌ Missing: `str:Mp_CPM`
- ❌ Missing: `str:Mp_Grav`
- ❌ Missing: `str:Mp_Harmonic`
- ❌ Missing: `str:Mpp_CPM`
- ❌ Missing: `str:M_CPM_Newton1`
- ❌ Missing: `str:M_CPM_Newton2`
- ❌ Missing: `str:M_CPM_Newton3`
- ❌ Missing: `str:M_CPM_Grav`
- ❌ Missing: `str:M_CPM_Hooke`
- ❌ Missing: `str:M_CPM_Free`
- ❌ Missing: `str:GC_Mass`
- ❌ Missing: `str:GC_Force`
- ❌ Missing: `str:I0_PlanetaryOrbits`
- ❌ Missing: `str:I0_TerrestrialFreeFall`
- ❌ Missing: `str:I0_HarmonicSpring`

# Specialization Poset Hierarchy Evaluation Report

- **DAG Property & Strict Partial Order:** ✅ PASSED (Acyclic DAG)
- **Root Element Conformity ($B(TN) = \{T_0\}$):** ❌ FAILED (Root: `None`)
- **Hierarchical Model Inheritance Subsumption:** ✅ PASSED (100.00%)

## Quantitative Benchmark Metrics
- **Poset Transitive Reduction F1:** 0.0000 (Precision: 0.0000, Recall: 0.0000)
- **Specialization Reachability F1:** 0.0000 (Precision: 0.0000, Recall: 0.0000)
- **Specialization Edge Counts:** Predicted = 0, Reference = 3

## Extrinsic Retrieval Evaluation Report

- **MRR:** 0.0000
- **Hits@1:** 0.0000
- **Hits@3:** 0.0000
- **Hits@10:** 0.0000
- **nDCG:** 0.0000


## Comparative Baseline Evaluation: ZERO_SHOT vs Pipeline

- **ΔF1:** +0.0000 (Pipeline: 0.0000 vs Baseline: 0.0000)
- **ΔMRR:** +0.0000 (Pipeline: 0.0000 vs Baseline: 0.0000)
- **Token Cost:** Pipeline $0.0000 vs Baseline $0.0000 (Δ $+0.0000)
- **Latency:** Pipeline 0.0025s vs Baseline 0.0015s (Δ +0.0010s)

### Side-by-Side Metrics (zero_shot)

| Metric | Baseline (`baseline_zero_shot_stnb_cpm_pilot_eval_01`) | Pipeline (`stnb_cpm_pilot_eval_01`) | Delta | Winner |
| :--- | :--- | :--- | :--- | :--- |
| `ag_iou` | 0.0000 | 1.0000 | +1.0000 | Pipeline |
| `aor` | 0.8333 | 1.0000 | +0.1667 | Baseline |
| `edge_fidelity` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `f1` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `hits@1` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `hits@10` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `hits@3` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `is_dag` | 1.0000 | 1.0000 | 0.0000 | Tie |
| `latency` | 0.0015 | 0.0025 | +0.0010 | Baseline |
| `mcc` | 0.0667 | 0.0000 | -0.0667 | Baseline |
| `mrr` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `ndcg` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `pfs` | 0.3750 | 0.5000 | +0.1250 | Pipeline |
| `poset_f1` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `poset_reachability_f1` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `root_conformity` | 0.0000 | 0.0000 | 0.0000 | Tie |
| `token_cost` | 0.0000 | 0.0000 | 0.0000 | Tie |