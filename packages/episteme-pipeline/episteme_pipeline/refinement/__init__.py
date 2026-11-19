"""Closed-loop hermeneutic refinement subsystem (ISSUE-053).

Provides top-down epistemic deficit detection (L4/L3 -> L2/L1) and localized
refinement strategies covering enthymeme premise recovery, polysemy concept
splitting, empirical axiom grounding, and bounded closed-loop orchestration.
"""

from episteme_pipeline.refinement.axiom_grounder import TheoryGuidedAxiomGrounder
from episteme_pipeline.refinement.concept_splitter import ConceptionConceptSplitter
from episteme_pipeline.refinement.coordinator import ClosedLoopRefinementCoordinator
from episteme_pipeline.refinement.detector import TheoryNetDeficitDetector
from episteme_pipeline.refinement.premise_recovery import LLMTheoryGuidedPremiseRecoverer

__all__ = [
    "ClosedLoopRefinementCoordinator",
    "ConceptionConceptSplitter",
    "LLMTheoryGuidedPremiseRecoverer",
    "TheoryGuidedAxiomGrounder",
    "TheoryNetDeficitDetector",
]
