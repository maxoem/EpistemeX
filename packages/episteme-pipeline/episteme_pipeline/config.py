from __future__ import annotations

import os
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, SecretStr, model_validator

from episteme_pipeline.prompts.default_prompts import (
    ACC_DIRECT_PROMPT, ACC_REASONING_PROMPT, ACC_FORMAT_PROMPT,
    ADU_SEGMENTATION_PROMPT,
    ARC_DIRECT_PROMPT, ARC_REASONING_PROMPT, ARC_FORMAT_PROMPT,
    ENTITY_LINKING_PROMPT,
    GLOBAL_RELATION_DIRECT_PROMPT, GLOBAL_RELATION_REASONING_PROMPT, GLOBAL_RELATION_FORMAT_PROMPT,
    NER_DIRECT_PROMPT, NER_REASONING_PROMPT, NER_FORMAT_PROMPT, NER_GLEANING_PROMPT,
    ENTITY_SYNTHESIS_PROMPT,
    PAIR_GATING_DECISION_PROMPT,
    DECISION_ACC_QUESTION, DECISION_ACC_CRITERIA,
    DECISION_ARC_QUESTION, DECISION_ARC_CRITERIA,
    DECISION_GLEANING_QUESTION,
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
    def from_env(cls, **overrides: Any) -> "ModelConfig":
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
    verification : ConsolidationVerificationConfig
        Sub-configuration for calibrated borderline pair and cluster verification.
    """

    enabled: bool = True
    dense_similarity_threshold: float = 0.85
    relation_overlap_threshold: float = 0.8
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
    entity_synthesis_prompts : StructuredPromptBundle
        The prompt bundle used when calling the LLM to synthesize a mature
        entity description.
    entity_synthesis_decoding_strategy : StructuredDecodingStrategy
        Which decoding strategy the synthesis call routes through.
    """
    maturation_top_k: int = 5
    batch_size: int = 10
    entity_synthesis_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ENTITY_SYNTHESIS_PROMPT,
        name="entity_synthesis",
    ))
    entity_synthesis_decoding_strategy: StructuredDecodingStrategy = StructuredDecodingStrategy.DIRECT



class Phase4Config(BaseModel):
    adu_segmentation_prompt_template: str = ADU_SEGMENTATION_PROMPT
    adu_segmentation_prompts: StructuredPromptBundle = Field(default_factory=lambda: StructuredPromptBundle(
        direct_template=ADU_SEGMENTATION_PROMPT,
        name="adu_segmentation",
    ))
    adu_confidence_threshold: float = 0.0
    acc_confidence_threshold: float = 0.0
    batch_size: int = 10
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
    adu_markup_open: str = "<AC"
    adu_markup_close: str = ">"
    triage_confidence_threshold: float = 0.85
    conformal_alpha: float = 0.05
    stochastic_audit_rate: float = 0.02
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
    """Configuration for Phase 5: Argument Web & Theory Fusion."""

    argument_clustering_enabled: bool = True
    theory_fusion_enabled: bool = False
    fusion_similarity_threshold: float = 0.85
    cluster_layer: Literal["theory_atoms", "l2_entities", "both"] = "theory_atoms"
    gating: FusionGatingConfig = Field(default_factory=FusionGatingConfig)


class Phase6Config(BaseModel):
    enabled: bool = True


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
    """

    provider: str = "none"
    api_key: SecretStr | None = None
    endpoint_url: str | None = None
    timeout_seconds: float = 2.0
    default_confidence_threshold: float = 0.85
    conformal_alpha: float = 0.05
    stochastic_audit_rate: float = 0.02
    fallback_to_llm: bool = True


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
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    decision_engine: DecisionEngineConfig | None = Field(default=None)

    @classmethod
    def from_env(cls, **overrides: Any) -> "PipelineConfig":
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
