# Closed-Loop Refinement & Deficit Analysis Reference

API specification for deterministic epistemic deficit graph analysis, localized refinement handlers, loop coordination, and pass-aware artifact overlays (`episteme_pipeline/refinement/`, `episteme_pipeline/artifacts/refinement_overlay.py`, and `episteme_pipeline/utils/graph_algorithms.py`).

## Deficit Detector & Graph Analysis

### TheoryNetDeficitDetector

Orchestrates the three deterministic deficit sub-detectors and emits prioritized `EpistemicDeficit` signals.

::: episteme_pipeline.refinement.detector.TheoryNetDeficitDetector
    options:
      show_root_heading: false
      show_root_toc_entry: false

### DetectorStateAnalysis & Graph Metrics

Precomputes single-source schema partitions, Schurz–Lakatos $Z_1$ reachability, NetworkX projection, `epistemetrics` centralities, Louvain communities, cluster evidence maps, and chunk neighborhoods.

::: episteme_pipeline.refinement._detector_analysis.DetectorStateAnalysis
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.refinement._detector_analysis.analyze_detector_state
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.refinement._detector_analysis.build_theory_nx_graph
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.refinement._detector_analysis.compute_centralities
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.refinement._detector_analysis.compute_louvain_communities
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Sub-Detectors

::: episteme_pipeline.refinement._sub_detectors.EnthymemeGapSubDetector
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.refinement._sub_detectors.PolysemyCollisionSubDetector
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.refinement._sub_detectors.UngroundedAxiomSubDetector
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Shared $Z_1$ Empirical Grounding

::: episteme_pipeline.utils.graph_algorithms.compute_z1_grounding
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.utils.graph_algorithms.Z1GroundingResult
    options:
      show_root_heading: false
      show_root_toc_entry: false

---

## Refinement Coordinator & Localized Handlers

### ClosedLoopRefinementCoordinator

::: episteme_pipeline.refinement.coordinator.ClosedLoopRefinementCoordinator
    options:
      show_root_heading: false
      show_root_toc_entry: false

### LLMTheoryGuidedPremiseRecoverer

::: episteme_pipeline.refinement.premise_recovery.LLMTheoryGuidedPremiseRecoverer
    options:
      show_root_heading: false
      show_root_toc_entry: false

### ConceptionConceptSplitter

::: episteme_pipeline.refinement.concept_splitter.ConceptionConceptSplitter
    options:
      show_root_heading: false
      show_root_toc_entry: false

### TheoryGuidedAxiomGrounder

::: episteme_pipeline.refinement.axiom_grounder.TheoryGuidedAxiomGrounder
    options:
      show_root_heading: false
      show_root_toc_entry: false

---

## Refinement Overlays & Connected-Component Slicing

::: episteme_pipeline.artifacts.refinement_overlay.build_deficit_envelope
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.refinement_overlay.build_delta_envelopes
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.refinement_overlay.overlay_collection
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.refinement_overlay.slice_phase4_component_view
    options:
      show_root_heading: false
      show_root_toc_entry: false
