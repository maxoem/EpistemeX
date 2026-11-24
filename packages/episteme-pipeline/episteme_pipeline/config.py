from __future__ import annotations

import os
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr

from episteme_pipeline.prompts.default_prompts import (
    ACC_DIRECT_PROMPT,
    ACC_FORMAT_PROMPT,
    ACC_REASONING_PROMPT,
    ADU_SEGMENTATION_PROMPT,
    ARC_DIRECT_PROMPT,
    ARC_FORMAT_PROMPT,
    ARC_REASONING_PROMPT,
    AXIOM_GROUNDING_PROMPT,
    CONCEPT_SPLIT_PROMPT,
    DECISION_ACC_CRITERIA,
    DECISION_ACC_QUESTION,
    DECISION_ARC_CRITERIA,
    DECISION_ARC_QUESTION,
    DECISION_ENTHYMEME_RECOVERABILITY_QUESTION,
    DECISION_GLEANING_QUESTION,
    DECISION_OBSERVATION_GROUNDING_QUESTION,
    DECISION_POLYSEMY_DISAMBIGUATION_CRITERIA,
    DECISION_POLYSEMY_DISAMBIGUATION_QUESTION,
    ENTITY_LINKING_PROMPT,
    ENTITY_SYNTHESIS_PROMPT,
    GLOBAL_RELATION_DIRECT_PROMPT,
    GLOBAL_RELATION_FORMAT_PROMPT,
    GLOBAL_RELATION_REASONING_PROMPT,
    NER_DIRECT_PROMPT,
    NER_FORMAT_PROMPT,
    NER_GLEANING_PROMPT,
    NER_REASONING_PROMPT,
    PAIR_GATING_DECISION_PROMPT,
    PREMISE_RECOVERY_PROMPT,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig


class StructuredDecodingStrategy(str, Enum):
    DIRECT = "direct_constrained"
    NL_TO_FORMAT = "nl_to_format"
    TRIGGER_TOKEN = "trigger_token"


class FallbackBehavior(str, Enum):
    RETRY_THEN_OMIT = "retry_then_omit"
    LOG_AND_RETRY = "log_and_retry"
    RAISE = "raise"


class ModelConfig(BaseModel):
    """Declarative record of which models a run uses.

    This block is the single place model selection is *declared*. It exists for
    two reasons, neither of which is invalidation:

    1. **Observability.** A run manifest's ``config_snapshot`` should record
       *which* models ran, by name. Today ``method_fingerprints`` records only an
       opaque hash of the live LLM/embedding objects, so a finished run cannot
       tell you what generated it.
    2. **Controllability.** The CLI, the example scripts and ``episteme-studio`` each
       need to choose models. Without this block each one reads ``os.environ``
       at its own call site and they drift apart.

    Notes
    -----
    Model identity already reaches phase invalidation through
    ``episteme_pipeline.runs.fingerprints.fingerprint_method``, which hashes the live
    model objects (``model_name``, ``temperature``, ``base_url``, …) and is
    compared per phase during resume. This block is therefore deliberately *not*
    folded into ``phase_config_fingerprints``: doing so would re-fingerprint
    every existing phase and invalidate all prior runs without adding coverage.

    Secrets never belong here — API keys stay in the environment, because this
    object is serialized verbatim into every run manifest.

    Attributes
    ----------
    llm_model
        Generative model identifier, e.g. ``openai/deepseek-v4-flash-sovereign``.
    embedding_model
        Embedding model identifier. Used as the fallback when a phase is
        constructed without an explicit embedding model.
    reranker_model
        Cross-encoder reranker identifier, used as the equivalent fallback.
    temperature, seed
        Decoding parameters that affect reproducibility.
    llm_api_base
        OpenAI-compatible endpoint the generative model is served from. Not a
        secret, and it changes outputs, so it is recorded.
    thinking_level
        Thinking budget or reasoning effort level for generative reasoning models
        (e.g. 'off', 'low', 'medium', 'high', or custom token budget).
    """

    llm_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "Alibaba-NLP/gte-reranker-modernbert-base"
    temperature: float = 0.0
    seed: int | None = None
    llm_api_base: str | None = None
    thinking_level: str = "off"

    @classmethod
    def from_env(cls, **overrides: Any) -> ModelConfig:
        """Resolve model selection from the environment, then apply overrides.

        Reads ``LLM_MODEL``, ``EMBED_MODEL``, ``RERANKER_MODEL``,
        ``LITELLM_API_BASE``, and ``LLM_THINKING_LEVEL`` (or ``THINKING_LEVEL``).
        Unset or empty variables fall back to the field defaults. Explicit
        ``overrides`` win over the environment, which is what lets a caller
        (or the Studio) pin a model without mutating the process.

        Examples
        --------
        >>> ModelConfig.from_env(temperature=0.2).temperature
        0.2
        """
        env_map = {
            "llm_model": "LLM_MODEL",
            "embedding_model": "EMBED_MODEL",
            "reranker_model": "RERANKER_MODEL",
            "llm_api_base": "LITELLM_API_BASE",
            "thinking_level": "LLM_THINKING_LEVEL",
        }
        values: dict[str, Any] = {}
        for field_name, env_name in env_map.items():
            raw = os.environ.get(env_name, "").strip()
            if not raw and field_name == "thinking_level":
                raw = os.environ.get("THINKING_LEVEL", "").strip()
            if raw:
                values[field_name] = raw
        values.update(overrides)
        return cls(**values)


class Phase1Config(BaseModel):
    chunk_size: int = 1024
    chunk_overlap: int = 128
    provenance_enabled: bool = True


class GleaningConfig(BaseModel):
    """Configuration for iterative extraction gleaning passes.

    Parameters
    ----------
    enabled : bool, default False
        Whether the objective Jev Actor-Critic gleaning stopping oracle is enabled.
    confidence_threshold : float, default 0.65
        Minimum confidence / empirical accuracy threshold P(unextracted) required to
        trigger an additional extraction pass.
    audit_rate : float, default 0.02
        Stochastic false-negative audit rate (e.g. 2%) forcing an extra pass on stopped
        extractions to monitor calibration.
    max_passes : int, default 3
        Maximum allowed gleaning iterations.
    """

    enabled: bool = False
    confidence_threshold: float = 0.65
    audit_rate: float = 0.02
    max_passes: int = 3


class Phase2Config(BaseModel):
    top_k_linking_candidates: int = 10
    linking_confidence_threshold: float = 0.85
    ner_confidence_threshold: float = 0.0
    local_relation_confidence_threshold: float = 0.0
    batch_size: int = 10
    ner_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=NER_DIRECT_PROMPT,
        reasoning_template=NER_REASONING_PROMPT,
        format_template=NER_FORMAT_PROMPT,
        gleaning_template=NER_GLEANING_PROMPT,
        decision_template=DECISION_GLEANING_QUESTION,
        name="ner_extraction",
    ))
    ner_decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.NL_TO_FORMAT
    entity_linking_prompt_template: str = ENTITY_LINKING_PROMPT
    entity_linking_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ENTITY_LINKING_PROMPT,
        name="entity_linking",
    ))
    jev_ooo_threshold: float = 0.75
    conformal_linking_alpha: float = 0.05
    max_concurrent_chapters: int = 4
    gleaning: GleaningConfig = Field(default_factory=GleaningConfig)



class Phase3Config(BaseModel):
    batch_size: int = 50
    global_relation_confidence_threshold: float = 0.7
    max_candidates_per_entity_pair: int = 200
    subgraph_depth: int = 2
    global_relation_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=GLOBAL_RELATION_DIRECT_PROMPT,
        reasoning_template=GLOBAL_RELATION_REASONING_PROMPT,
        format_template=GLOBAL_RELATION_FORMAT_PROMPT,
        decision_template=PAIR_GATING_DECISION_PROMPT,
        name="global_relation",
    ))
    global_relation_decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.NL_TO_FORMAT
    dense_similarity_threshold: float = 0.5
    reranker_threshold: float = 0.6
    trace_dense_retrieval: bool = True
    use_jev_reranker: bool = False
    use_jev_pair_gating: bool = False
    pair_gating_threshold: float = 0.60
    pair_gating_audit_rate: float = 0.02
    use_csls: bool = True
    csls_k_nearest: int = 10
    use_adaptive_k: bool = True
    adaptive_k_gamma: float = 2.0
    adaptive_k_min: int = 2
    z_score_threshold: float | None = None


class ConsolidationVerificationConfig(BaseModel):
    """Configuration for calibrated Phase 3b cluster verification.

    Parameters
    ----------
    enabled : bool, default False
        Whether Jev decision verification is enabled for borderline pairs.
    similarity_lower : float, default 0.75
        Lower bound of the borderline vector similarity band.
    similarity_upper : float, default 0.88
        Upper bound of the borderline vector similarity band.
    confidence_threshold : float, default 0.80
        Empirical accuracy threshold required to confirm a borderline merge.
    conformal_alpha : float, default 0.05
        Conformal significance level for borderline merge prediction sets.
    """

    enabled: bool = False
    similarity_lower: float = 0.75
    similarity_upper: float = 0.88
    confidence_threshold: float = 0.80
    conformal_alpha: float = 0.05
    borderline_merge_prompts: StructuredPromptBundle | None = None
    canonical_election_prompts: StructuredPromptBundle | None = None


class Phase3bConfig(BaseModel):
    """Configuration for Phase 3b: Latent Graph Consolidation.

    Attributes
    ----------
    enabled : bool, default True
        Whether Phase 3b latent consolidation is enabled.
    dense_similarity_threshold : float, default 0.85
        The minimum cosine similarity between L2 entity embeddings to consider
        them candidates for consolidation.
    relation_overlap_threshold : float, default 0.8
        The minimum Jaccard similarity of Phase 3 relation edges required to
        commit a SAME_AS edge between candidates. A conservative default
        ensures distinct but related entities are not incorrectly merged.
    use_csls : bool, default True
        Whether to compute Cross-Domain Similarity Local Scaling (CSLS) to penalize
        hub entities and correct for embedding anisotropy.
    csls_k_nearest : int, default 10
        Neighborhood size for mean nearest-neighbor cosine similarity in CSLS.
    min_internal_similarity : float, default 0.70
        Minimum internal pairwise similarity floor required across all nodes within
        a merged cluster, preventing non-transitive single-linkage bridge chaining.
    max_diameter : float | None, default None
        Optional maximum diameter constraint for merged clusters.
    verification : ConsolidationVerificationConfig
        Sub-configuration for calibrated borderline pair and cluster verification.
    """

    enabled: bool = True
    dense_similarity_threshold: float = 0.85
    relation_overlap_threshold: float = 0.8
    use_csls: bool = True
    csls_k_nearest: int = 10
    use_adaptive_k: bool = True
    adaptive_k_gamma: float = 2.0
    adaptive_k_min: int = 2
    max_candidates_per_entity: int = 50
    z_score_threshold: float | None = None
    min_internal_similarity: float = 0.70
    max_diameter: float | None = None
    verification: ConsolidationVerificationConfig = Field(default_factory=ConsolidationVerificationConfig)



class Phase4EntityMaturationConfig(BaseModel):
    """Configuration for Phase 4: Entity Maturation (epistemic synthesis).

    Attributes
    ----------
    maturation_top_k : int, default 5
        The number of representative textual envelopes to retrieve closest to the
        geometric centroid for LLM synthesis.
    batch_size : int, default 10
        The number of entities to synthesize concurrently via the LLM API.
    enable_conception_stratification : bool, default True
        Whether to detect multi-modal / high-variance entity mention envelopes
        across documents or theories and synthesize perspective-specific
        :class:`EntityConception` facets.
    polysemy_variance_threshold : float, default 0.15
        Spherical dispersion threshold :math:`\\tau_{\\text{polysemy}}` above which
        entity mention envelopes trigger multi-centroid conception stratification.
    min_silhouette_score : float, default 0.15
        Minimum cosine silhouette score required to accept a multi-centroid
        spherical k-means partition when explicit perspective separation is absent.
    max_conceptions_per_entity : int, default 4
        Maximum number of perspective-specific conceptions K synthesized per entity.
    min_envelopes_for_stratification : int, default 2
        Minimum number of mention envelopes required to test for polysemous variance.
    entity_synthesis_prompts : StructuredPromptBundle
        The prompt bundle used when calling the LLM to synthesize a mature
        entity description.
    entity_synthesis_decoding_strategy : StructuredDecodingStrategy
        Which decoding strategy the synthesis call routes through.
    """
    maturation_top_k: int = 5
    batch_size: int = 10
    enable_conception_stratification: bool = True
    polysemy_variance_threshold: float = Field(default=0.15, ge=0.0, le=2.0)
    min_silhouette_score: float = Field(default=0.15, ge=-1.0, le=1.0)
    max_conceptions_per_entity: int = Field(default=4, ge=2, le=10)
    min_envelopes_for_stratification: int = Field(default=2, ge=2)
    entity_synthesis_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ENTITY_SYNTHESIS_PROMPT,
        name="entity_synthesis",
    ))
    entity_synthesis_decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.DIRECT



class ModalResolverConfig(BaseModel):
    """Configuration for authorial propositional modal strength estimation.

    Parameters
    ----------
    mode : Literal["guardrail", "convex", "structural_only", "engine_only"], default "guardrail"
        Integration mode for combining structuralist syntax with linguistic scoring:
        - "guardrail": Clips decision engine score within structuralist syntax bounds.
        - "convex": Computes weighted average between structural prior and engine score.
        - "structural_only": Strictly evaluates structuralist syntax.
        - "engine_only": Strictly evaluates decision engine score.
    fusion_alpha : float, default 0.50
        Relative weight of structuralist syntax in convex fusion mode (in [0.0, 1.0]).
    default_base_score : float, default 0.60
        Default modal certainty fallback when attributes are absent.
    """

    mode: Literal["guardrail", "convex", "structural_only", "engine_only"] = "guardrail"
    fusion_alpha: float = 0.50
    default_base_score: float = 0.60


class Phase4Config(BaseModel):
    adu_segmentation_prompt_template: str = ADU_SEGMENTATION_PROMPT
    adu_segmentation_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ADU_SEGMENTATION_PROMPT,
        name="adu_segmentation",
    ))
    adu_confidence_threshold: float = 0.0
    acc_confidence_threshold: float = 0.0
    batch_size: int = 10
    modal_resolver: ModalResolverConfig = Field(default_factory=lambda: ModalResolverConfig())
    acc_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ACC_DIRECT_PROMPT,
        reasoning_template=ACC_REASONING_PROMPT,
        format_template=ACC_FORMAT_PROMPT,
        decision_template=DECISION_ACC_QUESTION,
        decision_criteria=DECISION_ACC_CRITERIA,
        name="acc_classification",
    ))
    acc_decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.NL_TO_FORMAT
    arc_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ARC_DIRECT_PROMPT,
        reasoning_template=ARC_REASONING_PROMPT,
        format_template=ARC_FORMAT_PROMPT,
        decision_template=DECISION_ARC_QUESTION,
        decision_criteria=DECISION_ARC_CRITERIA,
        name="arc_classification",
    ))
    arc_decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.NL_TO_FORMAT
    arc_confidence_threshold: float = 0.65
    arc_subgraph_depth: int = 2
    arc_max_candidates_per_component: int = 10
    arc_use_priority_rank: bool = False
    arc_use_csls: bool = True
    arc_csls_k_nearest: int = 10
    arc_use_adaptive_k: bool = True
    arc_adaptive_k_gamma: float = 2.0
    arc_adaptive_k_min: int = 2
    arc_z_score_threshold: float | None = None
    adu_markup_open: str = "<AC"
    adu_markup_close: str = ">"
    triage_confidence_threshold: float = 0.85
    conformal_alpha: float = 0.05
    stochastic_audit_rate: float = 0.02
    acc_infer_intensional_mode: bool = True
    require_multi_adu_relations: bool = False
    require_entity_binding: bool = False
    pass_priors_to_llm: bool = True
    gleaning: GleaningConfig = Field(default_factory=GleaningConfig)


class FusionGatingConfig(BaseModel):
    """Configuration for calibrated Phase 5 theory fusion gating.

    Parameters
    ----------
    enabled : bool, default False
        Whether inter-document theory fusion gating is enabled.
    confidence_threshold : float, default 0.85
        Calibrated empirical accuracy threshold for approving inter-document fusion.
    conformal_alpha : float, default 0.05
        Conformal error significance level for prediction set coverage.
    audit_rate : float, default 0.02
        Stochastic false-negative audit rate (e.g. 2%).
    """

    enabled: bool = False
    confidence_threshold: float = 0.85
    conformal_alpha: float = 0.05
    audit_rate: float = 0.02
    prompt_bundle: StructuredPromptBundle | None = None


class Phase5Config(BaseModel):
    """Configuration for Phase 5: Argument Web & Theory Fusion.

    Attributes
    ----------
    argument_clustering_enabled : bool, default True
        Whether to perform cross-document argument clustering.
    theory_fusion_enabled : bool, default False
        Whether theory fusion gating is enabled.
    fusion_similarity_threshold : float, default 0.85
        The minimum cosine similarity required for argument clustering merges.
    min_internal_similarity : float, default 0.75
        The minimum internal similarity floor across all node pairs in a cluster,
        preventing single-linkage bridge chaining.
    max_diameter : float | None, default None
        Optional maximum cluster diameter constraint.
    max_cluster_size : int, default 100
        Maximum allowed nodes in a single cluster.
    cluster_layer : Literal["theory_atoms", "l2_entities", "both"], default "theory_atoms"
        Target graph layer to cluster.
    gating : FusionGatingConfig
        Calibrated fusion gating sub-configuration.
    """

    argument_clustering_enabled: bool = True
    theory_fusion_enabled: bool = False
    fusion_similarity_threshold: float = 0.85
    min_internal_similarity: float = 0.75
    max_diameter: float | None = None
    max_cluster_size: int = 100
    cluster_layer: Literal["theory_atoms", "l2_entities", "both"] = "theory_atoms"
    gating: FusionGatingConfig = Field(default_factory=FusionGatingConfig)



class Phase6Config(BaseModel):
    """Configuration for Phase 6: TheoryNet Materialization & Projection.

    Attributes
    ----------
    enabled : bool, default True
        Whether Phase 6 TheoryNet materialization is executed.
    admissibility_threshold : float, default 0.0
        Calibrated empirical accuracy threshold (tau_admissibility) for filtering or
        flagging theoretical relations. Edges with empirical_accuracy below this
        threshold are pruned or assigned low tenability.
    prune_inadmissible : bool, default False
        Whether to discard inadmissible edges instead of retaining them with
        flagged tenability.
    iterations : int, default 20
        Maximum iteration limit for QBAF gradual semantics equilibrium solving.
    tolerance : float, default 1e-4
        Numerical convergence threshold epsilon for justification degrees.
    semantics_model : str, default "quadratic"
        Iterative semantics model ('quadratic', 'euler', 'categorizer', or 'linear').
    admissibility_mode : Literal["hard", "soft"], default "hard"
        Bivariate gating mode (normative hard database pruning vs. continuous sigmoidal relaxation).
    tau_p : float, default 0.0
        Perception stance probability threshold.
    tau_c : float, default 0.0
        Perception calibration confidence threshold.
    perspective : str or None, optional
        Optional epistemic perspective filter for QBAF evaluation ('author',
        agent name, or None for isolated authorial evaluation).
    isolate_suppositional : bool, default True
        Whether suppositional/Reductio premises are isolated from inflating
        authorial claim justification.
    isolate_attributed : bool, default True
        Whether attributed opponent summaries are isolated from directly inflating
        asserted authorial claims.
    conjunctive_t_norm : Literal["product", "godel"], default "product"
        Conjunctive t-norm operator applied over multi-premise inferences in QBAF
        gradual semantics evaluation (``"product"`` or ``"godel"``).
    """

    enabled: bool = True
    admissibility_threshold: float = 0.0
    prune_inadmissible: bool = False
    iterations: int = 20
    tolerance: float = 1e-4
    semantics_model: str = "quadratic"
    use_continuous: bool = True
    admissibility_mode: Literal["hard", "soft"] = "hard"
    tau_p: float = 0.0
    tau_c: float = 0.0
    perspective: str | None = None
    isolate_suppositional: bool = True
    isolate_attributed: bool = True
    conjunctive_t_norm: Literal["product", "godel"] = "product"
    modal_resolver: ModalResolverConfig = Field(default_factory=lambda: ModalResolverConfig())


class TheoreticalEnrichmentConfig(BaseModel):
    """Configuration for Theoretical Enrichment and Tenability Evaluation post-processor.

    Parameters
    ----------
    enabled : bool, optional
        Whether Theoretical Enrichment execution is enabled, by default True.
    induce_theories : bool, optional
        Whether to dynamically induce Theory-Elements from the graph via LLM when
        the registry is unseeded, by default True.
    max_theories : int, optional
        Maximum number of theories to induce from the text, by default 5.
    tenability_threshold : float, optional
        Threshold (default 0.5) below which nodes or edges are flagged as untenable anomalies.
    weight_local : float, optional
        Relative weight for local law adherence in aggregated tenability, by default 0.5.
    weight_edge : float, optional
        Relative weight for intertheoretical / constraint adherence in aggregated tenability, by default 0.5.
    decoding_strategy : StructuredDecodingStrategy, optional
        Decoding strategy for structured prediction passes, by default DIRECT.
    induction_prompts : StructuredPromptBundle | None, optional
        Custom prompt bundle for theory induction.
    projection_prompts : StructuredPromptBundle | None, optional
        Custom prompt bundle for cluster projection.
    """

    enabled: bool = True
    induce_theories: bool = True
    max_theories: int = 5
    tenability_threshold: float = 0.5
    weight_local: float = 0.5
    weight_edge: float = 0.5
    decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.DIRECT
    induction_prompts: StructuredPromptBundle | None = None
    projection_prompts: StructuredPromptBundle | None = None


class HermeneuticRefinementConfig(BaseModel):
    """Configuration for bounded closed-loop hermeneutic refinement (ISSUE-053).

    Controls top-down epistemic deficit detection (L4/L3 -> L2/L1), System 1
    ``DecisionEngine`` triage gating, managed prompt bundles, and localized
    re-extraction, concept splitting, and premise recovery cycles.

    Parameters
    ----------
    max_refinement_cycles : int, default 0
        Maximum top-down refinement cycles executed after the forward pass
        (``0`` preserves strictly feed-forward execution).
    enthymeme_min_centrality : float, default 0.0
        Minimum graph centrality required for an unwarranted claim or hypothesis
        to trigger an ``ENTHYMEME_GAP`` deficit.
    polysemy_edge_tenability_threshold : float, default 0.5
        Edge tenability floor ``TS_edge`` below which bridging concepts are
        candidates for ``POLYSEMY_COLLISION`` detection.
    polysemy_volatility_threshold : float, default 0.25
        Controversy volatility threshold ``V(a)`` above which bridging entities
        or atoms trigger ``POLYSEMY_COLLISION`` detection.
    polysemy_ambiguity_similarity_threshold : float, default 0.82
        Upper semantic cosine similarity threshold across contextual usages;
        pairs below this floor indicate true semantic divergence rather than
        univocal disagreement.
    ungrounded_local_tenability_threshold : float, default 0.5
        Local tenability floor ``TS_local`` below which empirical clusters or
        axioms trigger ``UNGROUNDED_AXIOM`` detection.
    max_deficits_per_cycle : int, default 20
        Maximum number of prioritized deficits processed in each refinement cycle.
    enable_theory_guided_premise_recovery : bool, default True
        Whether ``ENTHYMEME_GAP`` signals dispatch theory-guided premise recovery.
    enable_targeted_concept_split : bool, default True
        Whether ``POLYSEMY_COLLISION`` signals dispatch targeted L2 concept splitting.
    enable_localized_axiom_grounding : bool, default True
        Whether ``UNGROUNDED_AXIOM`` signals dispatch localized parameter and
        observation re-extraction.
    use_decision_engine_gating : bool, default True
        When True and a ``DecisionEngine`` is provided, applies System 1 triage
        gates (conformal/calibratable Noul & Choice checks with deterministic
        auditing) before invoking System 2 structured LLM handlers.
    decision_confidence_threshold : float, default 0.70
        Minimum System 1 confidence / positive likelihood required to accept
        or escalate a gated candidate without full bypass.
    conformal_alpha : float, default 0.10
        Significance level ``alpha`` for System 1 conformal prediction sets on
        polysemy disambiguation triage.
    stochastic_audit_rate : float, default 0.05
        Deterministic hash-based audit rate applied when System 1 recommends
        skipping a deficit handler, preventing silent false-negative suppression.
    concept_split_prompts : StructuredPromptBundle
        Managed prompt bundle for ``ConceptionConceptSplitter`` and System 1
        polysemy disambiguation.
    premise_recovery_prompts : StructuredPromptBundle
        Managed prompt bundle for ``LLMTheoryGuidedPremiseRecoverer`` and System 1
        enthymeme recoverability gating.
    axiom_grounding_prompts : StructuredPromptBundle
        Managed prompt bundle for ``TheoryGuidedAxiomGrounder`` and System 1
        observation grounding gating.
    concept_split_decoding_strategy : StructuredDecodingStrategy, default DIRECT
        Structured decoding strategy used for concept split extraction.
    premise_recovery_decoding_strategy : StructuredDecodingStrategy, default DIRECT
        Structured decoding strategy used for implicit premise recovery.
    axiom_grounding_decoding_strategy : StructuredDecodingStrategy, default DIRECT
        Structured decoding strategy used for observation and parameter grounding.
    """

    max_refinement_cycles: int = Field(default=0, ge=0, le=5)
    enthymeme_min_centrality: float = Field(default=0.0, ge=0.0)
    polysemy_edge_tenability_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    polysemy_volatility_threshold: float = Field(default=0.25, ge=0.0)
    polysemy_ambiguity_similarity_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    ungrounded_local_tenability_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_deficits_per_cycle: int = Field(default=20, ge=1)
    enable_theory_guided_premise_recovery: bool = True
    enable_targeted_concept_split: bool = True
    enable_localized_axiom_grounding: bool = True
    use_decision_engine_gating: bool = True
    decision_confidence_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    conformal_alpha: float = Field(default=0.10, gt=0.0, lt=1.0)
    stochastic_audit_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    concept_split_prompts: StructuredPromptBundle = Field(
        default_factory=lambda: StructuredPromptBundle(
            direct_template=CONCEPT_SPLIT_PROMPT,
            decision_template=DECISION_POLYSEMY_DISAMBIGUATION_QUESTION,
            decision_criteria=DECISION_POLYSEMY_DISAMBIGUATION_CRITERIA,
            name="concept_split",
        )
    )
    premise_recovery_prompts: StructuredPromptBundle = Field(
        default_factory=lambda: StructuredPromptBundle(
            direct_template=PREMISE_RECOVERY_PROMPT,
            decision_template=DECISION_ENTHYMEME_RECOVERABILITY_QUESTION,
            name="premise_recovery",
        )
    )
    axiom_grounding_prompts: StructuredPromptBundle = Field(
        default_factory=lambda: StructuredPromptBundle(
            direct_template=AXIOM_GROUNDING_PROMPT,
            decision_template=DECISION_OBSERVATION_GROUNDING_QUESTION,
            name="axiom_grounding",
        )
    )
    concept_split_decoding_strategy: StructuredDecodingStrategy = (
        StructuredDecodingStrategy.DIRECT
    )
    premise_recovery_decoding_strategy: StructuredDecodingStrategy = (
        StructuredDecodingStrategy.DIRECT
    )
    axiom_grounding_decoding_strategy: StructuredDecodingStrategy = (
        StructuredDecodingStrategy.DIRECT
    )


class QualityGatesConfig(BaseModel):
    """Configuration for inter-phase epistemic quality gates (ISSUE-058).

    Attributes
    ----------
    enabled : bool, default True
        Whether default inter-phase quality gates are attached at pipeline composition.
    on_violation : Literal["warn", "raise"], default "warn"
        Default policy when a quality gate threshold is violated ('warn' emits
        a ``QualityGateWarning`` and domain event; 'raise' halts the run with
        ``QualityGateViolationError``).
    min_entity_type_entropy : float, default 0.30
        Minimum Shannon entropy H(entity_types) in bits required post-Phase 2.
    max_dominant_type_ratio : float, default 0.90
        Maximum fraction of extracted entities assignable to a single ontological type.
    min_entities_for_entropy : int, default 5
        Minimum number of extracted entities before ontological entropy bounds are enforced.
    min_entity_density : float, default 0.0
        Minimum entity density per non-empty chunk required post-Phase 2.
    max_percolation_fraction : float, default 0.50
        Maximum fraction rho_max of total nodes allowed in a single merged equivalence
        class post-Phase 3b and Phase 5.
    min_population_for_percolation : int, default 4
        Minimum entity/atom count required before percolation fraction bounds are enforced.
    max_conformal_empty_rate : float, default 0.30
        Maximum allowed fraction of empty conformal prediction sets (|C(X)| == 0).
    max_conformal_ambiguous_rate : float, default 0.70
        Maximum allowed fraction of ambiguous multi-label prediction sets (|C(X)| > 1).
    max_conformal_ood_rate : float, default 0.70
        Maximum allowed combined conformal OOD rate (|C(X)| != 1).
    min_conformal_samples : int, default 1
        Minimum number of conformal evaluations required before OOD bounds are checked.
    """

    enabled: bool = True
    on_violation: Literal["warn", "raise"] = "warn"
    min_entity_type_entropy: float = 0.30
    max_dominant_type_ratio: float = 0.90
    min_entities_for_entropy: int = 5
    min_entity_density: float = 0.0
    require_nonzero_entity_density: bool = True
    max_percolation_fraction: float = 0.50
    min_population_for_percolation: int = 4
    max_conformal_empty_rate: float = 0.30
    max_conformal_ambiguous_rate: float = 0.70
    max_conformal_ood_rate: float = 0.70
    min_conformal_samples: int = 1


class ExecutionConfig(BaseModel):
    persist_run_manifests: bool = True
    persist_phase1_artifacts: bool = True
    persist_phase2_artifacts: bool = True
    persist_phase3_artifacts: bool = True
    persist_phase3b_artifacts: bool = True
    persist_phase4_maturation_artifacts: bool = True
    persist_phase4_artifacts: bool = True
    persist_phase5_artifacts: bool = True
    persist_phase6_artifacts: bool = True
    persist_theoretical_enrichment_artifacts: bool = True
    persist_refinement_artifacts: bool = True
    project_artifacts_to_graph: bool = False
    allow_phase_reuse: bool = Field(
        default=True,
        description=(
            "Permit phase-level reuse across runs when every fingerprint "
            "(schema, method, prompt, config, source) matches the parent run. "
            "Set False to force every phase to re-execute."
        ),
    )
    allow_artifact_hydration: bool = Field(
        default=True,
        description=(
            "Prefer reusing persisted artifacts over re-executing upstream phases. "
            "When True, the pipeline hydrates the prior phase's ArtifactCollection "
            "from the last successful run (artifact-native resume) and feeds it into "
            "the next phase instead of recomputing it. "
            "Requires persist_run_manifests=True and an artifacts_dir holding "
            "artifacts from a prior run over the same input. "
            "Trade-off: skips expensive LLM-heavy upstream work, but relies entirely "
            "on fingerprint invalidation for correctness — if a method or schema "
            "changed without changing its fingerprint, hydrated artifacts are stale."
        ),
    )
    runs_dir: str = ".pipeline_runs"
    artifacts_dir: str = ".pipeline_artifacts"

    def should_persist_artifacts(self, phase_key: str) -> bool:
        """Check whether artifacts should be persisted for a given phase key.

        Parameters
        ----------
        phase_key : str
            The phase identifier (e.g. 'phase1', 'phase2', etc.).

        Returns
        -------
        bool
            True if persistence is enabled for this phase, False otherwise.
        """
        mapping: dict[str, bool] = {
            "phase1": self.persist_phase1_artifacts,
            "phase2": self.persist_phase2_artifacts,
            "phase3": self.persist_phase3_artifacts,
            "phase3b": self.persist_phase3b_artifacts,
            "phase4_maturation": self.persist_phase4_maturation_artifacts,
            "phase4": self.persist_phase4_artifacts,
            "phase5": self.persist_phase5_artifacts,
            "phase6": self.persist_phase6_artifacts,
            "theoretical_enrichment": self.persist_theoretical_enrichment_artifacts,
            "refinement": self.persist_refinement_artifacts,
        }
        return mapping.get(phase_key, True)



class DecisionEngineConfig(BaseModel):
    """Configuration for the System 1 Decision Engine (e.g. TypeSafe Jev / Laya).

    Attributes
    ----------
    provider : str, default "none"
        Provider backend identifier ("none", "laya", "transformers", "mock").
    api_key : SecretStr or None, default None
        Optional API key or secret token for remote decision services.
    endpoint_url : str or None, default None
        Optional HTTP/gRPC endpoint for remote decision services.
    timeout_seconds : float, default 2.0
        Per-decision inference timeout in seconds.
    default_confidence_threshold : float, default 0.85
        Default empirical accuracy threshold for fast-exit routing.
    conformal_alpha : float, default 0.05
        Significance level for conformal prediction sets (guaranteeing 1 - alpha coverage).
    stochastic_audit_rate : float, default 0.02
        Proportion of fast-exit decisions randomly escalated to System 2 to audit calibration drift.
    fallback_to_llm : bool, default True
        Whether to fall back to generative LLM execution if the decision engine fails or has low confidence.
    model_checkpoint : str, default "aac6fef/laya-mlx"
        Local weight directory or Hugging Face repository identifier.
    device : str, default "auto"
        Target hardware compute accelerator ('auto', 'mps', 'mlx', 'cuda', 'cpu').
    fast_exit_threshold : float, default 0.92
        Calibrated score threshold for immediate System 1 exit without generative LLM.
    uncertainty_threshold : float, default 0.55
        Uncertainty cutoff below which execution escalates to generative LLM reasoning.
    phase_gates : dict of str to bool, optional
        Per-phase gating enablement toggles.
    """

    provider: str = "none"
    api_key: SecretStr | None = None
    endpoint_url: str | None = None
    timeout_seconds: float = 2.0
    default_confidence_threshold: float = 0.85
    conformal_alpha: float = 0.05
    stochastic_audit_rate: float = 0.02
    fallback_to_llm: bool = True
    model_checkpoint: str = "aac6fef/laya-mlx"
    device: str = "auto"
    fast_exit_threshold: float = 0.92
    uncertainty_threshold: float = 0.55
    global_alpha: float = 0.05
    default_task_id: str | None = None
    language: str | None = None
    risk_budget_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "phase2_entity_discovery": 0.25,
            "phase3b_consolidation": 0.10,
            "phase4_argument_mining": 0.25,
            "phase5_fusion": 0.25,
            "refinement": 0.15,
        }
    )
    phase_gates: dict[str, bool] = Field(
        default_factory=lambda: {
            "phase2_entity_discovery": True,
            "phase3_global_relations": True,
            "phase4_argument_mining": True,
            "phase4_entity_maturation": True,
            "phase5_fusion": True,
            "phase6_theorynet": True,
        }
    )

    def allocate_phase_alphas(self) -> dict[str, float]:
        """Allocate per-phase conformal significance levels from global risk budget.

        Uses weighted union bound allocation:
        :math:`\\alpha_m = \\alpha_{\\text{global}} \\cdot \\frac{w_m}{\\sum_k w_k}`
        guaranteeing :math:`\\sum_{m=1}^M \\alpha_m \\le \\alpha_{\\text{global}}`.

        Returns
        -------
        dict of str to float
            Mapping from phase key to allocated conformal significance level.
        """
        if not self.risk_budget_weights:
            return {}
        from episteme_pipeline.decision.conformal import ConformalCalibrator

        try:
            return ConformalCalibrator.allocate_risk_budget(
                global_alpha=self.global_alpha,
                weights=self.risk_budget_weights,
            )
        except ValueError:
            return {k: self.conformal_alpha for k in self.risk_budget_weights}

    def get_allocated_alpha(self, phase_or_task: Any) -> float:
        """Return the allocated alpha for a given PhaseRunner class, phase_key, or task.

        Parameters
        ----------
        phase_or_task : type of PhaseRunner, PhaseRunner, or str
            PhaseRunner subclass, instance, class name, ``phase_key``, or decision task.

        Returns
        -------
        float
            Allocated significance level, or default conformal_alpha if unweighted.
        """
        from episteme_pipeline.protocols.phase_runner import PhaseRunner

        allocated = self.allocate_phase_alphas()
        for candidate in PhaseRunner.related_identifiers(phase_or_task):
            if candidate in allocated:
                return allocated[candidate]
        return self.conformal_alpha


class PipelineConfig(BaseModel):
    """
    Top-level pipeline configuration. Each phase receives only its sub-config.

    Serialize to JSON/YAML for reproducible research runs:
        config.model_dump_json(indent=2)
    """

    models: ModelConfig = Field(default_factory=ModelConfig)

    graph_schema: SchemaConfig = Field(default_factory=lambda: DEFAULT_SCHEMA.model_copy())
    phase1: Phase1Config = Field(default_factory=Phase1Config)
    phase2: Phase2Config = Field(default_factory=Phase2Config)
    phase3: Phase3Config = Field(default_factory=Phase3Config)
    phase3b: Phase3bConfig = Field(default_factory=Phase3bConfig)
    phase4_maturation: Phase4EntityMaturationConfig = Field(default_factory=Phase4EntityMaturationConfig)
    phase4: Phase4Config = Field(default_factory=Phase4Config)
    phase5: Phase5Config = Field(default_factory=Phase5Config)
    phase6: Phase6Config = Field(default_factory=Phase6Config)
    theoretical_enrichment: TheoreticalEnrichmentConfig = Field(default_factory=TheoreticalEnrichmentConfig)
    refinement: HermeneuticRefinementConfig = Field(default_factory=HermeneuticRefinementConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    quality_gates: QualityGatesConfig = Field(default_factory=QualityGatesConfig)
    decision_engine: DecisionEngineConfig | None = Field(default=None)
    modal_resolver: ModalResolverConfig = Field(default_factory=ModalResolverConfig)

    @classmethod
    def from_env(cls, **overrides: Any) -> PipelineConfig:
        """Build a config whose model selection is resolved from the environment.

        This is the one supported way to turn ambient environment state into a
        config. Call it once at the edge (CLI, example script, Studio) and pass
        the result down; do not read ``os.environ`` inside phases.
        """
        return cls(models=ModelConfig.from_env(), **overrides)

    @property
    def default_embedding_model(self) -> str:
        """Deprecated alias for ``config.models.embedding_model``."""
        return self.models.embedding_model

    @property
    def default_reranker_model(self) -> str:
        """Deprecated alias for ``config.models.reranker_model``."""
        return self.models.reranker_model

    def get_phase_config(self, phase_key: str) -> BaseModel | None:
        """Retrieve the configuration model for a phase key without reflection.

        Parameters
        ----------
        phase_key : str
            The phase identifier.

        Returns
        -------
        BaseModel or None
            The corresponding phase config model, or None if unknown.
        """
        mapping: dict[str, BaseModel] = {
            "phase1": self.phase1,
            "phase2": self.phase2,
            "phase3": self.phase3,
            "phase3b": self.phase3b,
            "phase4_maturation": self.phase4_maturation,
            "phase4": self.phase4,
            "phase5": self.phase5,
            "phase6": self.phase6,
            "theoretical_enrichment": self.theoretical_enrichment,
            "refinement": self.refinement,
        }
        return mapping.get(phase_key)

    def sync_allocated_risk_budgets(self) -> None:
        """Synchronize per-phase conformal significance levels from DecisionEngineConfig.

        When a global risk budget is configured on ``decision_engine``, allocates
        per-phase significance levels via weighted union bounds and assigns them
        to the corresponding phase configurations:
        - ``phase2.conformal_linking_alpha``
        - ``phase3b.verification.conformal_alpha``
        - ``phase4.conformal_alpha``
        - ``phase5.gating.conformal_alpha``
        - ``refinement.conformal_alpha``
        """
        if self.decision_engine is None:
            return

        self.phase2.conformal_linking_alpha = self.decision_engine.get_allocated_alpha(
            "phase2_entity_discovery"
        )
        self.phase3b.verification.conformal_alpha = self.decision_engine.get_allocated_alpha(
            "phase3b_consolidation"
        )
        self.phase4.conformal_alpha = self.decision_engine.get_allocated_alpha(
            "phase4_argument_mining"
        )
        self.phase5.gating.conformal_alpha = self.decision_engine.get_allocated_alpha(
            "phase5_fusion"
        )
        self.refinement.conformal_alpha = self.decision_engine.get_allocated_alpha(
            "refinement"
        )

