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
    id: str
    text: str
    component_type: str
    source_chunk_id: str
    confidence: float | None = None
    plausibility: float | None = None
    modal_strength: float = Field(default=0.6, ge=0.0, le=1.0, description="Author propositional modal certainty M(phi)")
    base_score: float = Field(default=0.6, ge=0.0, le=1.0, description="Prior plausibility tau_0 for QBAF")
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
        st = ScopeType.from_str(v)
        return st.value if st is not None else (str(v).strip() if v else None)

    @field_validator("epistemic_status", mode="before")
    @classmethod
    def normalize_epistemic_status(cls, v: Any) -> str | None:
        es = EpistemicStatus.from_str(v)
        return es.value if es is not None else (str(v).strip() if v else None)

    @model_validator(mode="after")
    def sync_modal_and_base_scores(self) -> TheoryAtom:
        """Synchronize modal_strength and base_score priors."""
        if "base_score" in self.model_fields_set and "modal_strength" not in self.model_fields_set:
            self.modal_strength = self.base_score
        elif "modal_strength" in self.model_fields_set and "base_score" not in self.model_fields_set:
            self.base_score = self.modal_strength
        elif self.plausibility is not None and "base_score" not in self.model_fields_set and "modal_strength" not in self.model_fields_set:
            self.base_score = float(self.plausibility)
            self.modal_strength = float(self.plausibility)
        return self


class TheoryRelation(BaseModel):
    """Dialectical and structural relationship between theoretical atoms (Layer 3).

    Models argumentative interactions (supports, attacks, undercuts, reductions)
    within a Quantitative Bipolar Argumentation Framework (QBAF). Explicitly decouples
    the author's propositional modality (on nodes) from inferential warrant force (on edges)
    and perception extraction probability:

    .. math::
        W_{ji} = \\mathcal{I}(a_j \\to a_i) \\cdot \\mathcal{F}(r)

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
    weight : float | None, optional
        Directed relational weight for QBAF semantics. If None, derived from
        active_weight.
    tenability : float | None, optional
        Epistemic tenability score in [0.0, 1.0].
    class_probability : float | None, optional
        Softmax probability P(stance) of the predicted relation type.
    stance_probability : float | None, optional
        Canonical perception class probability P(stance).
    empirical_accuracy : float | None, optional
        Calibrated empirical accuracy frequency from System 1 decision engine
        (e.g. Laya action.act_probability) used for admissibility gating.
    model_confidence : float | None, optional
        Canonical calibrated confidence score C for perception gating.
    inferential_force : float, default 0.75
        Toulminian inferential warrant validity I_(j->i) in [0.0, 1.0].
    is_admissible : bool, default True
        Admissibility status under active bivariate thresholds.
    active_weight : float, default 0.75
        Net weight W_ji ingested by gradual semantics solvers.
    modal_strength : float, default 1.0
        Legacy propositional modality score on edges (deprecated in favor of
        TheoryAtom.modal_strength and TheoryRelation.inferential_force).
    effective_weight : float | None, optional
        Legacy decoupled edge weight.
    decision_engine_provider : str | None, optional
        System 1 engine provider identifier (e.g. 'mock_jev', 'typesafe_jev').
    calibrated_confidence : float | None, optional
        Empirically calibrated confidence score for calibration evaluation and admissibility.
    weight_support : float | None, optional
        Directed support weight contribution in [0.0, 1.0].
    weight_attack : float | None, optional
        Directed attack weight contribution in [0.0, 1.0].
    """

    source_id: str
    target_id: str
    relation_type: str
    confidence: float
    scope: Literal["local", "global"]
    weight: float | None = None
    tenability: float | None = None
    class_probability: float | None = None
    stance_probability: float | None = None
    empirical_accuracy: float | None = None
    model_confidence: float | None = None
    inferential_force: float = Field(default=0.75, ge=0.0, le=1.0)
    is_admissible: bool = True
    active_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    modal_strength: float = 1.0
    effective_weight: float | None = None
    decision_engine_provider: str | None = None
    calibrated_confidence: float | None = None
    weight_support: float | None = None
    weight_attack: float | None = None

    @model_validator(mode="after")
    def compute_default_weights(self) -> TheoryRelation:
        """Compute decoupled effective weight, calibrated confidence, and align relation weight."""
        # Align stance_probability and class_probability
        if self.stance_probability is not None and self.class_probability is None:
            self.class_probability = self.stance_probability
        elif self.class_probability is not None and self.stance_probability is None:
            self.stance_probability = self.class_probability

        # Align model_confidence and calibrated_confidence
        if self.model_confidence is not None and self.calibrated_confidence is None:
            self.calibrated_confidence = self.model_confidence
        elif self.calibrated_confidence is not None and self.model_confidence is None:
            self.model_confidence = self.calibrated_confidence

        # Backward compatibility: if modal_strength was set on TheoryRelation but inferential_force was not
        if "modal_strength" in self.model_fields_set and "inferential_force" not in self.model_fields_set:
            self.inferential_force = self.modal_strength

        if self.effective_weight is None:
            if self.weight is not None:
                self.effective_weight = self.weight
            else:
                p_stance = (
                    self.stance_probability
                    if self.stance_probability is not None
                    else (
                        self.class_probability
                        if self.class_probability is not None
                        else self.confidence
                    )
                )
                self.effective_weight = float(
                    self.modal_strength * (p_stance if p_stance is not None else 1.0)
                )
        if self.weight is None:
            self.weight = self.effective_weight

        # Compute active_weight
        if "active_weight" not in self.model_fields_set:
            self.active_weight = abs(self.effective_weight)

        if self.calibrated_confidence is None:
            self.calibrated_confidence = (
                self.empirical_accuracy
                if self.empirical_accuracy is not None
                else (
                    self.stance_probability
                    if self.stance_probability is not None
                    else (
                        self.class_probability
                        if self.class_probability is not None
                        else self.confidence
                    )
                )
            )
        if self.model_confidence is None:
            self.model_confidence = self.calibrated_confidence
        return self

    def to_graph_properties(self, polarity: int | None = None) -> dict[str, Any]:
        """Convert TheoryRelation into a serialized projection property dictionary.

        Parameters
        ----------
        polarity : int | None, optional
            Epistemic polarity (+1, -1, 0). If omitted, inferred from relation weight.

        Returns
        -------
        dict of str to Any
            Graph edge properties conforming to the projection schema.
        """
        eff_w = (
            self.effective_weight
            if self.effective_weight is not None
            else (self.weight if self.weight is not None else 1.0)
        )
        pol = (
            polarity
            if polarity is not None
            else (1 if (self.weight or 0) > 0 else (-1 if (self.weight or 0) < 0 else 0))
        )
        w_supp = (
            self.weight_support
            if self.weight_support is not None
            else (eff_w if pol > 0 else 0.0)
        )
        w_att = (
            self.weight_attack
            if self.weight_attack is not None
            else (eff_w if pol < 0 else 0.0)
        )

        props: dict[str, Any] = {
            "scope": self.scope,
            "confidence": self.confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "class_probability": self.class_probability,
            "stance_probability": self.stance_probability,
            "empirical_accuracy": self.empirical_accuracy,
            "model_confidence": self.model_confidence,
            "inferential_force": self.inferential_force,
            "is_admissible": self.is_admissible,
            "active_weight": self.active_weight,
            "modal_strength": self.modal_strength,
            "effective_weight": eff_w,
            "weight": self.weight if self.weight is not None else eff_w,
            "decision_engine_provider": self.decision_engine_provider,
            "weight_support": w_supp,
            "weight_attack": w_att,
        }
        if self.tenability is not None:
            props["tenability"] = self.tenability
        return props

    @property
    def from_id(self) -> str:
        """Alias for source_id."""
        return self.source_id

    @property
    def to_id(self) -> str:
        """Alias for target_id."""
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

    @classmethod
    def from_graph_properties(
        cls,
        source_id: str,
        relation_type: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> TheoryRelation:
        """Reconstruct a TheoryRelation from serialized graph properties.

        Parameters
        ----------
        source_id : str
            Source atom/component identifier.
        relation_type : str
            Canonical relation type identifier.
        target_id : str
            Target atom/component identifier.
        properties : dict of str to Any, optional
            Serialized graph edge property map.

        Returns
        -------
        TheoryRelation
            Validated domain relation instance.
        """
        props = properties or {}
        raw_scope = props.get("scope", "global")
        scope_val: Literal["local", "global"] = "local" if raw_scope == "local" else "global"
        weight_val = (
            float(props["weight"])
            if "weight" in props and props["weight"] is not None
            else None
        )
        eff_weight_val = (
            float(props["effective_weight"])
            if "effective_weight" in props and props["effective_weight"] is not None
            else None
        )
        modal_val = float(props.get("modal_strength", 1.0) or 1.0)
        confidence_val = float(props.get("confidence", 1.0) or 1.0)
        inferential_val = float(props.get("inferential_force", modal_val) or 0.75)
        stance_prob_val = props.get("stance_probability", props.get("class_probability"))
        model_conf_val = props.get("model_confidence", props.get("calibrated_confidence", props.get("empirical_accuracy")))
        is_admissible_val = bool(props.get("is_admissible", True))
        active_weight_val = float(props.get("active_weight", eff_weight_val or inferential_val) or inferential_val)

        return cls(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            confidence=confidence_val,
            scope=scope_val,
            weight=weight_val,
            class_probability=props.get("class_probability"),
            stance_probability=stance_prob_val,
            empirical_accuracy=props.get("empirical_accuracy"),
            model_confidence=model_conf_val,
            inferential_force=inferential_val,
            is_admissible=is_admissible_val,
            active_weight=active_weight_val,
            modal_strength=modal_val,
            effective_weight=eff_weight_val,
            decision_engine_provider=props.get("decision_engine_provider"),
            tenability=props.get("tenability"),
            calibrated_confidence=props.get("calibrated_confidence"),
            weight_support=props.get("weight_support"),
            weight_attack=props.get("weight_attack"),
        )

    @classmethod
    def is_theory_edge(
        cls,
        relation_type: str,
        properties: dict[str, Any] | None = None,
        schema: Any | None = None,
        source_is_atom: bool = False,
        target_is_atom: bool = False,
    ) -> bool:
        """Determine whether candidate graph edge attributes define a TheoryRelation.

        Parameters
        ----------
        relation_type : str
            Relationship type name.
        properties : dict of str to Any, optional
            Edge properties dictionary.
        schema : SchemaConfig, optional
            Schema configuration providing dialectical relation definitions.
        source_is_atom : bool, default False
            Whether the source node is known to be a TheoryAtom.
        target_is_atom : bool, default False
            Whether the target node is known to be a TheoryAtom.

        Returns
        -------
        bool
            True if the edge represents a dialectical TheoryRelation.
        """
        # 1. Topological match (Neo4j equivalent: (a:TheoryAtom)-[r]->(b:TheoryAtom))
        if source_is_atom and target_is_atom:
            return True

        # 2. Schema taxonomy match
        from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA

        effective_schema = schema or DEFAULT_SCHEMA
        if (
            effective_schema.is_dialectical_relation(relation_type)
            or relation_type in effective_schema.argument_relation_types
        ):
            return True

        # 3. Signature theory properties
        props = properties or {}
        theory_markers = {
            "calibrated_confidence",
            "effective_weight",
            "modal_strength",
            "weight_support",
            "weight_attack",
        }
        if any(marker in props for marker in theory_markers):
            return True

        # 4. Partial atom match (one endpoint is an atom and edge is not structural)
        return bool((source_is_atom or target_is_atom) and relation_type not in ("CONTAINS", "EXTRACTED_FROM", "SAME_AS", "MENTIONS"))


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
