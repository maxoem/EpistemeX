"""Theoretical Enrichment and Tenability Evaluation Post-Processor Module.

Provides model-theoretic enrichment (Phi_spec) and structuralist tenability evaluation
over extracted empirical clusters (Intended Applications I).
"""

from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    ClusterProjectionOutput,
    EmpiricalCluster,
    InducedTheoryElement,
    InducedTheoryLaw,
    TheoryElementDefinition,
    TheoryInductionOutput,
    TheoryLaw,
    TheoryRegistry,
)
from episteme_pipeline.post_processing.theoretical_enrichment.events import (
    TenabilityAnomalyDetected,
    TenabilityEvaluationCompleted,
    TheoreticalClusterIdentified,
    TheoreticalParametersProjected,
)
from episteme_pipeline.post_processing.theoretical_enrichment.inducer import (
    LLMTheoryInducer,
    TheoryInducer,
)
from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
    CompositeTheoryProjector,
    GenericTheoryProjector,
    LLMTheoryProjector,
    TheoryProjector,  # noqa: F401 baseline
)
from episteme_pipeline.post_processing.theoretical_enrichment.runner import (
    TheoreticalEnrichmentRunner,
)
from episteme_pipeline.post_processing.theoretical_enrichment.solvers import (
    SafeFormulaEvaluator,
    TenabilitySolver,
    evaluate_formula_safely,
)

__all__ = [
    "ClusterProjectionOutput",
    "CompositeTheoryProjector",
    "EmpiricalCluster",
    "GenericTheoryProjector",
    "InducedTheoryElement",
    "InducedTheoryLaw",
    "LLMTheoryInducer",
    "LLMTheoryProjector",
    "SafeFormulaEvaluator",
    "TenabilityAnomalyDetected",
    "TenabilityEvaluationCompleted",
    "TenabilitySolver",
    "TheoreticalClusterIdentified",
    "TheoreticalEnrichmentRunner",
    "TheoreticalParametersProjected",
    "TheoryElementDefinition",
    "TheoryInducer",
    "TheoryInductionOutput",
    "TheoryLaw",
    "TheoryRegistry",
    "evaluate_formula_safely",
]
