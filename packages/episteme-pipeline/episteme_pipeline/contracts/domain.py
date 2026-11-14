from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GlobalStructuralAnchor(BaseModel):
    """
    Static global structural coordinate system anchor for LLM prompts.

    Parameters
    ----------
    toc_structure : list[str] | str, optional
        Structural outline or Table of Contents of the document, by default "".
    document_summary : str | None, optional
        Global summary of the document, by default None.
    global_thesis : str | None, optional
        Primary theoretical thesis or domain scope, by default None.
    """

    toc_structure: list[str] | str = ""
    document_summary: str | None = None
    global_thesis: str | None = None

    def to_prompt_context(self) -> str:
        """
        Format structural anchor coordinates as textual prompt context.

        Returns
        -------
        str
            Formatted prompt context block.
        """
        lines = []
        if isinstance(self.toc_structure, list):
            toc_str = "\n".join(f"- {item}" for item in self.toc_structure if item)
        else:
            toc_str = str(self.toc_structure).strip()

        if toc_str:
            lines.append(f"Global Table of Contents / Outline:\n{toc_str}")

        if self.document_summary:
            lines.append(f"\nDocument Overview:\n{self.document_summary}")
        if self.global_thesis:
            lines.append(f"\nGlobal Thesis / Scope:\n{self.global_thesis}")

        return "\n".join(lines).strip()




class TextAnchor(BaseModel):
    """Multi-modal source evidence anchor supporting text, formulas, tables, and figures.

    Parameters
    ----------
    source_doc_id : str or None, optional
        Document identifier.
    char_start : int or None, optional
        0-indexed character start offset.
    char_end : int or None, optional
        0-indexed character end offset.
    verbatim_quote : str or None, optional
        Verbatim textual quote.
    bbox : list of float or None, optional
        Bounding box region [x0, y0, x1, y1] or [x0, y0, x1, y1, page].
    page : int or None, optional
        Document page number.
    formula_id : str or None, optional
        Unique formula identifier.
    table_id : str or None, optional
        Unique table identifier.
    figure_id : str or None, optional
        Unique figure identifier.
    """

    source_doc_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    verbatim_quote: str | None = None
    bbox: list[float] | None = None
    page: int | None = None
    formula_id: str | None = None
    table_id: str | None = None
    figure_id: str | None = None


class L1Chunk(BaseModel):
    id: str
    text: str
    source_doc_id: str
    chapter_id: str | None = None
    sequence_index: int
    token_count: int
    embedding: list[float] | None = None
    text_anchor: TextAnchor | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class L1Document(BaseModel):
    id: str
    title: str
    source_path: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    chapter_count: int
    chunk_count: int
    structural_anchor: GlobalStructuralAnchor | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class L2Entity(BaseModel):
    """Layer 2 (global/logical) entity representation.

    Attributes
    ----------
    id : str
        The unique identifier for the entity (typically a UUID or stable hash).
    label : str
        The entity category or class label (e.g., 'CONCEPT', 'PERSON', 'WORK').
    name : str
        The canonical name of the entity.
    description : str, optional
        A synthesized textual description of what the entity represents.
    textual_envelope : str, optional
        The original text context where this entity was first discovered.
    is_mature : bool, default False
        Flag indicating if the entity's description has gone through the Stage 2
        maturation protocol. If True, the description is stable, centroid-fused,
        and protected against further epistemic drift.
    source_chunk_ids : list of str, default []
        Identifiers of all the source chunks where this entity has been mentioned.
    """
    id: str
    label: str
    name: str
    description: str | None = None
    textual_envelope: str | None = None
    is_mature: bool = False
    confidence: float | None = None
    text_anchor: TextAnchor | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)


class L2Triple(BaseModel):
    subject_id: str
    predicate: str
    object_id: str
    confidence: float = Field(
        description="Heterogeneous metric: could be LLM probability, reranker tau, or hardcoded 1.0."
    )
    rerank_score: float | None = None
    scope: Literal["local", "global"]
    source_chunk_id: str | None = None


class Measurement(BaseModel):
    """Represents an empirical observation measurement dimension and value.

    Parameters
    ----------
    dimension : str
        The empirical measurement dimension (e.g., 'blood_flow', 'repetition_count').
    value : float | str
        The observed scalar or categorical value.
    unit : str | None, optional
        Measurement unit (e.g., 'Hz', 'ml/min'), by default None.
    """

    dimension: str
    value: float | str
    unit: str | None = None


class TheoreticalParameter(BaseModel):
    """Represents a theoretical parameter postulated by a theory-element.

    Parameters
    ----------
    name : str
        Parameter name (e.g., 'DopamineDepletion', 'RepressionMagnitude').
    value : float | str
        Calculated or estimated parameter value.
    theory_id : str | None, optional
        Identifier of the theory-element postulating the parameter, by default None.
    unit : str | None, optional
        Unit of the theoretical parameter, by default None.
    """

    name: str
    value: float | str
    theory_id: str | None = None
    unit: str | None = None


class TenabilityResult(BaseModel):
    """Tenability evaluation result for a theory application or hypothesis.

    Parameters
    ----------
    local_score : float
        Local tenability score (TS_local in [0, 1]).
    edge_scores : dict[str, float]
        Constraint/intertheoretical link tenability scores (TS_edge in [0, 1]).
    aggregated_score : float
        Combined tenability score for the theory-element.
    is_tenable : bool
        True if aggregated tenability is greater than or equal to threshold (default 0.5).
    tightest_blur : float
        Tightest admissible blur (delta) reconciling observations with theory laws.
    anomalies : list[str]
        Descriptions of any severe law violations or constraint tensions detected.
    """

    local_score: float
    edge_scores: dict[str, float] = Field(default_factory=dict)
    aggregated_score: float
    is_tenable: bool
    tightest_blur: float
    anomalies: list[str] = Field(default_factory=list)


class ScopeType(str, Enum):
    """Structuralist scope type taxonomy grounded in Schurz (2014).

    Classifies theoretical propositions by logical and empirical quantifier scope.
    """

    ESSENTIELLER_ALLSATZ = "Essentieller Allsatz"
    LOKALISIERTER_ALLSATZ = "Lokalisierter Allsatz"
    LOKALISIERTER_EXISTENZSATZ = "Lokalisierter Existenzsatz"
    STATISTISCHER_ALLSATZ = "Statistischer/probabilistischer Allsatz"
    EXISTENZSATZ = "Existenzsatz"

    @classmethod
    def from_str(cls, val: str | ScopeType | None) -> ScopeType | None:
        """Parse or normalize a string or existing ScopeType into a canonical ScopeType.

        Parameters
        ----------
        val : str or ScopeType or None
            Raw or candidate scope type string.

        Returns
        -------
        ScopeType or None
            Canonical ScopeType enum member, or None if unparseable/empty.
        """
        if val is None:
            return None
        if isinstance(val, cls):
            return val
        s = str(val).strip()
        if not s:
            return None
        for member in cls:
            if s.lower() == member.value.lower() or s.lower() == member.name.lower():
                return member
        norm = s.upper().replace(" ", "_").replace("-", "_").replace("/", "_")
        if "ESSENTIELL" in norm and "ALLSATZ" in norm:
            return cls.ESSENTIELLER_ALLSATZ
        if "LOKALISIERT" in norm and "ALLSATZ" in norm:
            return cls.LOKALISIERTER_ALLSATZ
        if "LOKALISIERT" in norm and "EXISTENZSATZ" in norm:
            return cls.LOKALISIERTER_EXISTENZSATZ
        if "STATISTISCH" in norm or "PROBABILISTISCH" in norm:
            return cls.STATISTISCHER_ALLSATZ
        if "EXISTENZSATZ" in norm:
            return cls.EXISTENZSATZ
        return None


class EpistemicStatus(str, Enum):
    """Structuralist epistemic status taxonomy grounded in Schurz (2014).

    Distinguishes analytic / nomological necessity from empirical / synthetic contingency.
    """

    ANALYTISCH = "Analytisch"
    SYNTHETISCH = "Synthetisch"

    @classmethod
    def from_str(cls, val: str | EpistemicStatus | None) -> EpistemicStatus | None:
        """Parse or normalize a string or existing EpistemicStatus into a canonical EpistemicStatus.

        Parameters
        ----------
        val : str or EpistemicStatus or None
            Raw or candidate epistemic status string.

        Returns
        -------
        EpistemicStatus or None
            Canonical EpistemicStatus enum member, or None if unparseable/empty.
        """
        if val is None:
            return None
        if isinstance(val, cls):
            return val
        s = str(val).strip()
        if not s:
            return None
        for member in cls:
            if s.lower() == member.value.lower() or s.lower() == member.name.lower():
                return member
        norm = s.upper().replace(" ", "_").replace("-", "_")
        if "ANALYT" in norm:
            return cls.ANALYTISCH
        if "SYNTHET" in norm:
            return cls.SYNTHETISCH
        return None


class TheoryAtom(BaseModel):
    """Propositional claim, hypothesis, axiom, or observation unit (Layer 3).

    Implements the node-level attributes of the Stratified Epistemic State Tuple:
    - Layer 1 (Propositional Prior): ``modal_prior`` (:math:`\\tau_0(a) \\equiv M(\\phi_a)`).
    - Layer 3 (Empirical Tenability): ``local_tenability`` (:math:`TS_{\\text{local}}(a)`) and ``tenability``.
    - Layer 4 (Dialectical Equilibrium): ``equilibrium_strength`` (:math:`\\tau^*(a)`)
      and ``controversy_volatility`` (:math:`\\mathcal{V}(a)`).

    Parameters
    ----------
    id : str
        Unique component identifier.
    text : str
        Raw span text of the argument component.
    component_type : str
        Ontological component type (e.g. ``ObservationUnit``, ``TheoreticalHypothesis``).
    source_chunk_id : str
        Source chunk identifier where this component was extracted.
    confidence : float or None, optional
        Raw extractor confidence.
    modal_prior : float, default 0.6
        Node-intrinsic propositional modal prior :math:`\\tau_0(a) = M(\\phi_a) \\in [0, 1]`.
    local_tenability : float or None, optional
        Empirical local tenability score :math:`TS_{\\text{local}}(a) \\in [0, 1]` from ADR-0015.
    equilibrium_strength : float or None, optional
        Dialectical equilibrium justification degree :math:`\\tau^*(a) \\in [0, 1]` from D-QBAF.
    controversy_volatility : float or None, optional
        Keynes-Gärdenfors epistemic weight volatility :math:`\\mathcal{V}(a) \\ge 0`.
    resolver_type : str or None, optional
        Modality resolver identifier (e.g. ``'structuralist_syntax'``, ``'decision_engine_llm'``, ``'hybrid'``).
    syntax_bounds : tuple of (float, float) or None, optional
        Deterministic syntax interval :math:`[L_{\\text{syn}}, U_{\\text{syn}}]` from ``StructuralistModalResolver``.
    entity_ids : list of str, optional
        Identifiers of L2Entities mentioned in this span.
    epistemic_status : str or None, optional
        Rhetorical/dialectical epistemic status.
    scope_type : str or None, optional
        Structuralist scope type.
    text_anchor : TextAnchor or None, optional
        Character offset grounding in the source chunk.
    measurements : list of Measurement, optional
        Quantitative empirical measurements extracted from the span.
    parameters : dict of str to Any, optional
        Projected theoretical parameters.
    tenability : TenabilityResult or None, optional
        Full empirical tenability evaluation result from Theoretical Enrichment.
    """

    id: str
    text: str
    component_type: str
    source_chunk_id: str
    confidence: float | None = None
    modal_prior: float = Field(default=0.6, ge=0.0, le=1.0, description="Node-intrinsic propositional modal prior tau_0(a) = M(phi_a)")
    local_tenability: float | None = Field(default=None, ge=0.0, le=1.0, description="Empirical local tenability TS_local(a) in [0, 1]")
    equilibrium_strength: float | None = Field(default=None, ge=0.0, le=1.0, description="Dialectical equilibrium justification degree tau*(a) in [0, 1]")
    controversy_volatility: float | None = Field(default=None, ge=0.0, description="Keynes-Gardenfors epistemic weight volatility V(a)")
    resolver_type: str | None = None
    syntax_bounds: tuple[float, float] | None = None
    entity_ids: list[str] = Field(default_factory=list)
    epistemic_status: str | None = None
    scope_type: str | None = None
    text_anchor: TextAnchor | None = None
    measurements: list[Measurement] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tenability: TenabilityResult | None = None

    @field_validator("scope_type", mode="before")
    @classmethod
    def normalize_scope_type(cls, v: Any) -> str | None:
        """Normalize scope_type via ScopeType enum."""
        st = ScopeType.from_str(v)
        return st.value if st is not None else (str(v).strip() if v else None)

    @field_validator("epistemic_status", mode="before")
    @classmethod
    def normalize_epistemic_status(cls, v: Any) -> str | None:
        """Normalize epistemic_status via EpistemicStatus enum."""
        es = EpistemicStatus.from_str(v)
        return es.value if es is not None else (str(v).strip() if v else None)

    @model_validator(mode="after")
    def sync_modal_and_base_scores(self) -> TheoryAtom:
        """Synchronize ``local_tenability`` and ``tenability.local_score``.

        Returns
        -------
        TheoryAtom
            Validated atom with synchronized local tenability metadata.
        """
        if self.tenability is not None and self.local_tenability is None:
            self.local_tenability = float(self.tenability.local_score)
        elif (
            self.local_tenability is not None
            and self.tenability is not None
            and "local_tenability" in self.model_fields_set
            and "tenability" not in self.model_fields_set
        ):
            self.tenability.local_score = float(self.local_tenability)
        return self

    def effective_base_prior(self) -> float:
        """Compute tenability-modulated prior :math:`\\tilde{\\tau}_0(a) = \\tau_0(a) \\cdot TS_{\\text{local}}(a)`.

        Returns
        -------
        float
            Effective D-QBAF prior in ``[0.0, 1.0]``.
        """
        prior = self.modal_prior if self.modal_prior is not None else 0.6
        ts_local = (
            self.local_tenability
            if self.local_tenability is not None
            else (self.tenability.local_score if self.tenability is not None else 1.0)
        )
        return max(0.0, min(1.0, float(prior) * float(ts_local)))


class TheoryRelation(BaseModel):
    """Dialectical and structural relationship between theoretical atoms (Layer 3).

    Models argumentative interactions (supports, attacks, undercuts, reductions)
    within a Quantitative Bipolar Argumentation Framework (QBAF). Explicitly decouples
    the author's propositional modality (exclusively on :class:`TheoryAtom` nodes) from
    inferential warrant force (on edges), perception extraction probability, and
    intertheoretical edge tenability:

    .. math::
        W_{ji} = I_{j \\to i} \\cdot \\mathcal{F}_{\\text{gate}}(P_{ji}, C_{ji}) \\cdot TS_{\\text{edge}}(e_{ji})

    Parameters
    ----------
    source_id : str
        Domain identifier of the source TheoryAtom.
    target_id : str
        Domain identifier of the target TheoryAtom.
    relation_type : str
        Relational taxonomy classification (e.g. 'SUPPORTS', 'ATTACKS').
    confidence : float
        Extraction confidence score in [0.0, 1.0].
    scope : Literal["local", "global"]
        Structural visibility scope ('local' intra-chunk vs 'global' cross-chunk).
    weight : float or None, optional
        Directed relational weight for QBAF semantics. If None, derived from
        ``effective_weight``.
    edge_tenability : float or None, optional
        Intertheoretical edge tenability :math:`TS_{\\text{edge}} \\in [0, 1]` from ADR-0015.
    structural_correspondence : float or None, optional
        :math:`\\kappa`-structural correspondence overlap score in [0.0, 1.0] from ADR-0007.
    perception_stance_prob : float or None, optional
        System 1 perception stance probability :math:`P(\\text{stance}) \\in [0, 1]`.
    perception_empirical_acc : float or None, optional
        System 1 calibrated empirical accuracy :math:`C \\in [0, 1]`.
    inferential_warrant : float, default 0.75
        Toulminian inferential warrant validity :math:`I_{j \\to i} \\in [0, 1]`.
    is_admissible : bool, default True
        Admissibility status under active bivariate thresholds.
    active_weight : float, default 0.75
        Net weight :math:`W_{ji}` ingested by gradual semantics solvers.
    effective_weight : float or None, optional
        Decoupled edge weight derived strictly from relational warrant, perception
        confidence, and edge tenability (free of node modality).
    decision_engine_provider : str or None, optional
        System 1 engine provider identifier (e.g. 'mock_jev', 'typesafe_jev').
    calibrated_confidence : float or None, optional
        Empirically calibrated confidence score for calibration evaluation and admissibility.
    weight_support : float or None, optional
        Directed support weight contribution in [0.0, 1.0].
    weight_attack : float or None, optional
        Directed attack weight contribution in [0.0, 1.0].
    """

    source_id: str
    target_id: str
    relation_type: str
    confidence: float
    scope: Literal["local", "global"]
    weight: float | None = None
    edge_tenability: float | None = Field(default=None, ge=0.0, le=1.0)
    structural_correspondence: float | None = Field(default=None, ge=0.0, le=1.0)
    perception_stance_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    perception_empirical_acc: float | None = Field(default=None, ge=0.0, le=1.0)
    inferential_warrant: float = Field(default=0.75, ge=0.0, le=1.0)
    is_admissible: bool = True
    active_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    effective_weight: float | None = None
    decision_engine_provider: str | None = None
    calibrated_confidence: float | None = None
    weight_support: float | None = None
    weight_attack: float | None = None

    @model_validator(mode="after")
    def compute_default_weights(self) -> TheoryRelation:
        """Compute decoupled effective weight, calibrated confidence, and active weight.

        Returns
        -------
        TheoryRelation
            Validated relation with populated default weights and calibrated
            confidence.
        """
        warrant_explicit = "inferential_warrant" in self.model_fields_set
        ts_edge = float(self.edge_tenability) if self.edge_tenability is not None else 1.0

        # Compute effective_weight strictly without node modality M(phi)
        if self.effective_weight is None:
            if self.weight is not None:
                self.effective_weight = float(self.weight)
            else:
                if warrant_explicit or self.perception_stance_prob is not None:
                    p_factor = (
                        float(self.perception_stance_prob)
                        if self.perception_stance_prob is not None
                        else 1.0
                    )
                    self.effective_weight = float(
                        self.inferential_warrant * p_factor * ts_edge
                    )
                else:
                    self.effective_weight = float(self.confidence * ts_edge)
        if self.weight is None:
            self.weight = self.effective_weight

        if "active_weight" not in self.model_fields_set:
            self.active_weight = abs(self.effective_weight)

        if self.calibrated_confidence is None:
            self.calibrated_confidence = (
                self.perception_empirical_acc
                if self.perception_empirical_acc is not None
                else (
                    self.perception_stance_prob
                    if self.perception_stance_prob is not None
                    else self.confidence
                )
            )
        return self

    def compute_effective_weight(
        self,
        gating_mode: Literal["hard", "soft"] = "hard",
        tau_p: float = 0.0,
        tau_c: float = 0.0,
    ) -> float:
        """Compute deterministic edge weight :math:`W_{ji}` free of node modality :math:`M(\\phi)`.

        .. math::
            W_{ji} = I_{j \\to i} \\cdot \\mathcal{F}_{\\text{gate}}(P_{ji}, C_{ji}) \\cdot TS_{\\text{edge}}(e_{ji})

        Parameters
        ----------
        gating_mode : Literal["hard", "soft"], default "hard"
            Admissibility gating mode (``"hard"`` indicator step vs ``"soft"`` product).
        tau_p : float, default 0.0
            Minimum stance probability threshold :math:`\\tau_p`.
        tau_c : float, default 0.0
            Minimum empirical accuracy / calibration threshold :math:`\\tau_c`.

        Returns
        -------
        float
            Effective non-negative edge weight :math:`W_{ji} \\in [0, 1]`.
        """
        warrant = self.inferential_warrant
        p_val = float(
            self.perception_stance_prob
            if self.perception_stance_prob is not None
            else (self.confidence if self.confidence is not None else 1.0)
        )
        c_val = float(
            self.perception_empirical_acc
            if self.perception_empirical_acc is not None
            else (
                self.calibrated_confidence
                if self.calibrated_confidence is not None
                else p_val
            )
        )
        if not self.is_admissible or p_val < tau_p or c_val < tau_c:
            return 0.0
        gate = 1.0 if gating_mode == "hard" else (p_val * c_val)
        ts_edge = float(self.edge_tenability) if self.edge_tenability is not None else 1.0
        return max(0.0, min(1.0, float(warrant) * gate * ts_edge))

    @property
    def from_id(self) -> str:
        """Alias for ``source_id``."""
        return self.source_id

    @property
    def to_id(self) -> str:
        """Alias for ``target_id``."""
        return self.target_id

    @property
    def polarity(self) -> int:
        """Epistemic polarity (+1 for support, -1 for attack, 0 for neutral).

        Returns
        -------
        int
            Sign of relational polarity (+1, -1, 0).
        """
        if self.weight_support is not None and self.weight_support > 0:
            return 1
        if self.weight_attack is not None and self.weight_attack > 0:
            return -1
        from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

        return DEFAULT_SCHEMA.relation_polarities.get(
            self.relation_type,
            1 if (self.weight or 0) > 0 else (-1 if (self.weight or 0) < 0 else 0),
        )


class SubGraph(BaseModel):
    """Depth-limited neighborhood returned by graph read operations.

    This model is the pipeline-level transport object for structural context.
    It intentionally does not expose backend-specific graph handles or third-
    party graph objects. Consumers should treat it as a compact, serializable
    snapshot of a local property-graph neighborhood.

    Parameters
    ----------
    center_id
        Identifier of the node around which the neighborhood was requested.
        The center node itself is referenced here and is not required to appear
        in ``nodes``.
    nodes
        Neighbor nodes materialized for the neighborhood. Implementations
        should return the reachable context nodes needed by downstream phases.
        Ordering is not semantically significant.
    triples
        Directed relations contained in the neighborhood snapshot. These are
        graph edges represented in the pipeline's canonical ``L2Triple`` shape
        so downstream components can inspect structure without depending on the
        persistence backend.
    depth
        Maximum traversal depth that was requested to construct the
        neighborhood.
    """
    center_id: str
    nodes: list[L2Entity]
    triples: list[L2Triple]
    depth: int


class SearchResult(BaseModel):
    node_id: str
    score: float
    node_label: str
    node_name: str


class TheoryNet(BaseModel):
    atoms: list[TheoryAtom]
    relations: list[TheoryRelation]


class PhaseItemRecord(BaseModel):
    """Execution checkpoint item tracking within a pipeline phase.

    Parameters
    ----------
    key : str
        Unique order-invariant item identifier.
    status : Literal["completed", "failed"], default "completed"
        Processing status of the item.
    error : str | None, optional
        Error summary if status is failed, by default None.
    """

    key: str
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None


class CandidatePair(BaseModel):
    """Candidate entity pair for global relation evaluation.

    Parameters
    ----------
    entity_a : L2Entity
        First candidate entity.
    entity_b : L2Entity
        Second candidate entity.
    dense_score : float | None, optional
        Bi-encoder dense cosine similarity score if computed, by default None.
    score : float | None, optional
        Alias for dense_score, by default None.
    """

    entity_a: L2Entity
    entity_b: L2Entity
    dense_score: float | None = None
    score: float | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.score is not None and self.dense_score is None:
            object.__setattr__(self, "dense_score", self.score)
        elif self.dense_score is not None and self.score is None:
            object.__setattr__(self, "score", self.dense_score)

    def __iter__(self):
        """Allow unpacking as (entity_a, entity_b)."""
        yield self.entity_a
        yield self.entity_b

    def __getitem__(self, item: int) -> L2Entity:
        """Allow positional indexing for tuple compatibility."""
        if item == 0:
            return self.entity_a
        elif item == 1:
            return self.entity_b
        raise IndexError("CandidatePair index out of range")

    @property
    def key(self) -> str:
        """Deterministic order-invariant pair key including entity content fingerprints.

        Returns
        -------
        str
            Canonical pair key.
        """
        from episteme_pipeline.runs.fingerprints import stable_fingerprint

        h_a = stable_fingerprint(self.entity_a.textual_envelope or self.entity_a.name)[:8]
        h_b = stable_fingerprint(self.entity_b.textual_envelope or self.entity_b.name)[:8]
        if self.entity_a.id <= self.entity_b.id:
            return f"{self.entity_a.id}::{self.entity_b.id}::{h_a}::{h_b}"
        return f"{self.entity_b.id}::{self.entity_a.id}::{h_b}::{h_a}"
