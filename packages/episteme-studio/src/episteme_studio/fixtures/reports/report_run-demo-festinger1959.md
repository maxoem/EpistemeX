# Formal Structuralist Model Evaluation Report

**Capability Subsumption ($G_{pred} \succeq_{cap} G_{ref}$):** ✅ PASSED (Subsumes Capabilities)

## Quantitative Benchmark Metrics
- **Model Component Completeness (MCC):** 1.0000
- **Axiomatic Omission Rate (AOR):** 0.0000 (Zero Omission ✅)
- **Property Fidelity Score (PFS):** 0.9583
- **Text Anchor Grounding IoU ($AG_{IoU}$):** 1.0000
- **Relational Edge Fidelity:** 1.0000

## Model Class Decomposition Breakdown
| Model Class | Symbol | Reference Count | Predicted Count | Matched | Completeness |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `potential_models` | $\mathcal{M}_p$ | 1 | 1 | 1 | 100.00% |
| `actual_models` | $\mathcal{M}$ | 5 | 5 | 5 | 100.00% |
| `partial_potential_models` | $\mathcal{M}_{pp}$ | 0 | 0 | 0 | 100.00% |
| `constraints` | $GC$ | 0 | 0 | 0 | 100.00% |
| `paradigms` | $I_0$ | 1 | 1 | 1 | 100.00% |
| `theory_elements` | $T$ | 2 | 2 | 2 | 100.00% |

# Specialization Poset Hierarchy Evaluation Report

- **DAG Property & Strict Partial Order:** ✅ PASSED (Acyclic DAG)
- **Root Element Conformity ($B(TN) = \{T_0\}$):** ✅ PASSED (Root: `str:TE_DissF`)
- **Hierarchical Model Inheritance Subsumption:** ✅ PASSED (100.00%)

## Quantitative Benchmark Metrics
- **Poset Transitive Reduction F1:** 1.0000 (Precision: 1.0000, Recall: 1.0000)
- **Specialization Reachability F1:** 1.0000 (Precision: 1.0000, Recall: 1.0000)
- **Specialization Edge Counts:** Predicted = 1, Reference = 1