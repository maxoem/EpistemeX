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
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]: ...

    async def classify_pairs(
        self,
        pairs: list[tuple[TheoryAtom, TheoryAtom]],
        graph_store: GraphReader,
        schema: SchemaConfig | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
    ) -> list[TheoryRelation]:
        """Classify cross-chunk argument relations for specific candidate pairs.

        Parameters
        ----------
        pairs : list of tuple of (TheoryAtom, TheoryAtom)
            Candidate argument component pairs to evaluate.
        graph_store : GraphReader
            Reader for graph context and subgraphs.
        schema : SchemaConfig or None, default None
            Schema taxonomy.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional extractor for structural neighborhoods.

        Returns
        -------
        list of TheoryRelation
            Extracted argument relations for the specified pairs.
        """
        return []

    async def classify_global_with_triage(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
        audit_rate: float = 0.0,
        run_seed: str = "phase4_arc",
    ) -> tuple[list[TheoryRelation], list[tuple[TheoryAtom, TheoryAtom]]]:
        """Classify cross-chunk relations and return triage escalation pairs.

        Default implementation executes full global classification with no escalation.
        Subclasses with conformal/calibrated fast triage override this method to partition
        fast accepted vs. escalated candidate pairs.

        Parameters
        ----------
        local_components : list of TheoryAtom
            All argument components available.
        local_relations : list of TheoryRelation
            Intra-chunk relations previously extracted.
        graph_store : GraphReader
            Reader for graph context.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional extractor for structural neighborhoods.
        schema : SchemaConfig or None, default None
            Schema taxonomy.
        audit_rate : float, default 0.0
            Deterministic stochastic audit rate.
        run_seed : str, default "phase4_arc"
            Deterministic seed for audit hashing.

        Returns
        -------
        tuple of (list of TheoryRelation, list of tuple of (TheoryAtom, TheoryAtom))
            Tuple of (confirmed_relations, escalated_candidate_pairs).
        """
        relations = await self.classify_global(
            local_components, local_relations, graph_store, global_extractor, schema
        )
        return relations, []
