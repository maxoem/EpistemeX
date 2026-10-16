from abc import ABC, abstractmethod

from episteme_pipeline.contracts.domain import (
    L2Entity,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.schema.default_schema import SchemaConfig


class ADUSegmenter(Fingerprintable, ABC):
    """
    Phase 4 Step 1: Identifies Argumentative Discourse Units (ADUs) in text,
    wrapping them in markup tags (<AC1>...<AC1>) for downstream ACC.
    """

    @abstractmethod
    async def segment(
        self,
        chunk_id: str,
        chunk_text: str,
    ) -> tuple[str, list[str]]:
        """
        Returns (tagged_text, list_of_adu_ids).
        tagged_text has <ACn>...</ACn> markup inserted.
        """
        ...


class ACCClassifier(Fingerprintable, ABC):
    """
    Phase 4 Step 2: Argument Component Classification.

    When the input already contains pre-identified ADUs (tagged_text),
    ACC classifies each component type AND identifies the local support/
    attack relations between them — returning both in a single pass.
    """

    @abstractmethod
    async def classify(
        self,
        chunk_id: str,
        tagged_text: str,
        adu_ids: list[str],
        schema: SchemaConfig,
        chunk_entities: list[L2Entity] | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]: ...


class ARIIdentifier(Fingerprintable, ABC):
    """
    Phase 4 Step 3 (optional): Standalone local Argument Relation Identification.

    In the default implementation this step is fused into ACCClassifier
    (which outputs both types and relations in one pass). This interface exists
    as an override point for implementations that separate the two tasks.
    """

    @abstractmethod
    async def identify(
        self,
        components: list[TheoryAtom],
        chunk_text: str,
    ) -> list[TheoryRelation]: ...


class ARCClassifier(Fingerprintable, ABC):
    """
    Phase 4 Step 4: Global Argument Relation Classification.

    Reuses GlobalRelationExtractor for TAG + reranker-based subgraph retrieval,
    then classifies the stance (SUPPORTS / ATTACKS) between distant argument
    components using LLM reasoning over the retrieved envelope.
    """

    @abstractmethod
    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor,
        schema: SchemaConfig,
    ) -> list[TheoryRelation]: ...
