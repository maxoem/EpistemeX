"""
episteme-pipeline library.

Public API — import from here:

    from episteme_pipeline import Pipeline, PipelineConfig
    from episteme_pipeline import PipelineInput
    from episteme_pipeline.schema import SchemaConfig, DEFAULT_SCHEMA
    from episteme_pipeline.protocols import (
        PhaseRunner,
        EntityGraph,
    FusionGraph,
    GraphReader,
    GraphWriter,
    PhaseCheckpointStore,
    ProcessingGraph,
    ProjectionGraph,
        NERExtractor,
        GlobalRelationExtractor,
        EntityLinker,
        ADUSegmenter,
        ACCClassifier,
        ARCClassifier,
        InstanceFusion,
        ArgumentClustering,
        TheoryFusion,
    )
"""

import warnings

# Suppress SyntaxWarning from graspologic 3rd-party library
warnings.filterwarnings("ignore", category=SyntaxWarning, module="graspologic.*")

from episteme_pipeline.config import (
    Phase1Config,
    Phase2Config,
    Phase3Config,
    Phase4Config,
    Phase5Config,
    PipelineConfig,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.phases.phase2_entity_discovery import (
    CascadingEntityLinker,
    DenseEntityLinker,
    JevEntityLinker,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols import (
    ACCClassifier,
    ADUSegmenter,
    ARCClassifier,
    ArgumentClustering,
    DataSourceAdapter,
    EntityGraph,
    EntityLinker,
    FusionGraph,
    GlobalRelationExtractor,
    GraphReader,
    GraphWriter,
    InstanceFusion,
    NERExtractor,
    PhaseCheckpointStore,
    PhaseRunner,
    ProcessingGraph,
    ProjectionGraph,
    TheoryFusion,
)
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

__all__ = [
    "DEFAULT_SCHEMA",
    "ACCClassifier",
    "ADUSegmenter",
    "ARCClassifier",
    "ArgumentClustering",
    "CascadingEntityLinker",
    "DataSourceAdapter",
    # Linkers
    "DenseEntityLinker",
    "EntityGraph",
    "EntityLinker",
    "FusionGraph",
    "GlobalRelationExtractor",
    "GraphReader",
    "GraphWriter",
    "InstanceFusion",
    "JevEntityLinker",
    # Contracts
    "L1Chunk",
    "L1Document",
    "L2Entity",
    "L2Triple",
    "NERExtractor",
    "Phase1Config",
    "Phase2Config",
    "Phase3Config",
    "Phase4Config",
    "Phase5Config",
    "PhaseCheckpointStore",
    # Protocols (ABCs)
    "PhaseRunner",
    # Orchestration
    "Pipeline",
    "PipelineConfig",
    "PipelineInput",
    "ProcessingGraph",
    "ProjectionGraph",
    # Schema
    "SchemaConfig",
    "TheoryAtom",
    "TheoryFusion",
    "TheoryNet",
    "TheoryRelation",
]
