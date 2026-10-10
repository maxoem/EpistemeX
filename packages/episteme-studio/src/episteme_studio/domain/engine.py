"""Domain models for engine settings, schema customization, and predicate mapping.

Per D-01, domain models must remain strictly decoupled from episteme_pipeline.* and epistemetrics.*.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PredicateMapping(BaseModel):
    """Specification for mapping an open-vocabulary predicate to schema rules.

    Parameters
    ----------
    predicate : str
        The raw predicate label extracted from literature (e.g. 'WIDERSPRICHT').
    polarity : Literal[-1, 0, 1]
        Argumentative charge: +1 (support), 0 (neutral), or -1 (attack/refute).
    canonical : str or None, optional
        Optional canonical schema relation target (e.g. 'ATTACKS' or 'SUPPORTS').
    definition : str or None, optional
        Optional prompt guidance or semantic description for this predicate.
    """

    predicate: str
    polarity: Literal[-1, 0, 1]
    canonical: str | None = None
    definition: str | None = None


class UnmappedPredicateInfo(BaseModel):
    """Telemetry report describing an open-vocabulary predicate discovered in runs.

    Parameters
    ----------
    predicate : str
        The unresolved predicate string.
    occurrences : int
        Number of times this predicate appeared across runs or graphs.
    sample_runs : list of str, default []
        IDs of runs where this predicate was observed.
    """

    predicate: str
    occurrences: int = 1
    sample_runs: list[str] = Field(default_factory=list)


class EngineModelConfig(BaseModel):
    """Domain model representing baseline LLM, embedding, and reranker choices.

    Parameters
    ----------
    llm_model : str, default 'openai/gpt-4o-mini'
        Identifier of the primary reasoning model.
    embedding_model : str, default 'sentence-transformers/all-MiniLM-L6-v2'
        Dense vector embedding model.
    reranker_model : str, default 'Alibaba-NLP/gte-reranker-modernbert-base'
        Cross-encoder reranker model.
    temperature : float, default 0.0
        Generation temperature.
    seed : int or None, optional
        Random seed.
    llm_api_base : str or None, optional
        Custom OpenAI-compatible API base URL.
    thinking_level : str, default 'off'
        Reasoning thinking token budget preset.
    """

    llm_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "Alibaba-NLP/gte-reranker-modernbert-base"
    temperature: float = 0.0
    seed: int | None = None
    llm_api_base: str | None = None
    thinking_level: str = "off"


class DecisionPhaseGates(BaseModel):
    """Per-phase switches controlling System 1 decision gating.

    Parameters
    ----------
    phase2_entity_discovery : bool, default True
        Enable mention filtering & entity class validation in Phase 2.
    phase3_global_relations : bool, default True
        Enable cross-document relation candidate gating in Phase 3.
    phase4_argument_mining : bool, default True
        Enable ADU segmentation & argument stance classification in Phase 4.
    phase4_entity_maturation : bool, default True
        Enable epistemic synthesis & confidence voting verification in Phase 4b.
    phase5_fusion : bool, default True
        Enable entity resolution & argument cluster equivalence in Phase 5.
    phase6_theorynet : bool, default True
        Enable QBAF node base scores & inferential warrants in Phase 6.
    """

    model_config = ConfigDict(extra="ignore")

    phase2_entity_discovery: bool = True
    phase3_global_relations: bool = True
    phase4_argument_mining: bool = True
    phase4_entity_maturation: bool = True
    phase5_fusion: bool = True
    phase6_theorynet: bool = True


class DecisionEngineSettings(BaseModel):
    """Configuration parameters for the System 1 Decision Engine.

    Parameters
    ----------
    provider : Literal['none', 'laya', 'transformers', 'mock'], default 'none'
        System 1 decision provider engine.
    device : Literal['auto', 'mlx', 'cuda', 'cpu'], default 'auto'
        Hardware execution device target.
    model_checkpoint : str, default 'aac6fef/laya-mlx'
        Hugging Face repository ID or local filesystem path for weights.
    endpoint_url : str or None, optional
        Remote microservice URL if running decoupled server.
    api_key : str or None, optional
        API authorization token for remote endpoint.
    timeout_seconds : float, default 2.0
        Per-decision timeout budget.
    default_confidence_threshold : float, default 0.85
        Default empirical accuracy cutoff threshold (tau).
    conformal_alpha : float, default 0.05
        Conformal prediction miscoverage rate (1 - alpha coverage).
    stochastic_audit_rate : float, default 0.02
        Sampling frequency for routing fast-exits to System 2 for validation.
    fallback_to_llm : bool, default True
        Whether to escalate low-confidence or ambiguous items to System 2.
    batch_size : int, default 16
        Batch size for vector evaluation.
    fast_exit_threshold : float, default 0.92
        Empirical accuracy threshold for fast-exit routing.
    uncertainty_threshold : float, default 0.55
        Uncertainty cutoff below which execution escalates to generative LLM reasoning.
    phase_gates : DecisionPhaseGates, optional
        Granular per-phase gating toggles.
    """

    provider: Literal["none", "laya", "transformers", "mock", "mlx", "onnx", "stub", "auto"] = "laya"
    device: Literal["auto", "mlx", "cuda", "cpu", "mps"] = "auto"
    model_checkpoint: str = "aac6fef/laya-mlx"
    endpoint_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 2.0
    default_confidence_threshold: float = 0.85
    fast_exit_threshold: float = 0.92
    uncertainty_threshold: float = 0.55
    conformal_alpha: float = 0.05
    stochastic_audit_rate: float = 0.02
    fallback_to_llm: bool = True
    batch_size: int = 16
    phase_gates: DecisionPhaseGates = Field(default_factory=DecisionPhaseGates)


class DecisionEngineStatusResponse(BaseModel):
    """Hardware capability and model cache inspection report.

    Parameters
    ----------
    available : bool
        Whether the selected decision provider is operational.
    provider : str
        Active provider identifier.
    device : str
        Active hardware device string.
    mlx_available : bool
        Whether Apple Silicon MLX is importable and functional.
    cuda_available : bool
        Whether NVIDIA CUDA is available.
    checkpoint_cached : bool
        Whether model weights are present in local disk cache.
    checkpoint_path : str or None, optional
        Absolute filesystem path to model directory if cached.
    vram_allocated_mb : float or None, optional
        Currently allocated GPU/unified memory in megabytes.
    benchmark_latency_p50_ms : float or None, optional
        Empirical P50 latency measured during warm-up ping.
    latency_benchmark_ms : float or None, optional
        Frontend compatibility alias for benchmark_latency_p50_ms.
    active : bool, default True
        Frontend compatibility alias for available.
    model_checkpoint : str, default "aac6fef/laya-mlx"
        Resolved model checkpoint repository or path.
    model_metadata : dict of str to Any, optional
        Additional model characteristics (parameter count, precision, etc.).
    """

    model_config = ConfigDict(extra="ignore")

    available: bool
    active: bool = True
    provider: str
    model_checkpoint: str = "aac6fef/laya-mlx"
    device: str
    mlx_available: bool
    cuda_available: bool
    checkpoint_cached: bool
    checkpoint_path: str | None = None
    vram_allocated_mb: float | None = None
    benchmark_latency_p50_ms: float | None = None
    latency_benchmark_ms: float | None = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionTestRequest(BaseModel):
    """Payload for testing an isolated decision in the Studio sandbox.

    Supports both low-level protocol parameters (``state``, ``question``,
    ``options``, ``levels``) and high-level playground UI parameters
    (``input_text``, ``hypothesis_text``, ``candidate_labels``).

    Parameters
    ----------
    primitive : Literal['noul', 'choice', 'score']
        Type of decision primitive being tested.
    state : str or dict or list or None, optional
        Input state passage or entity representation.
    question : str or None, optional
        Decision question or rubric criterion.
    input_text : str or None, optional
        Playground input passage (alias/fallback for state).
    hypothesis_text : str or None, optional
        Playground hypothesis or proposition (alias/fallback for question).
    candidate_labels : list of str or None, optional
        Playground candidate labels for choice primitive (alias for options).
    options : list of str or dict of str to str or None, optional
        Candidate choices for choice primitive.
    levels : list of int or str or None, optional
        Rating levels for score primitive.
    alpha : float or None, default 0.05
        Conformal prediction miscoverage parameter.
    """

    primitive: Literal["noul", "choice", "score"]
    state: str | dict[str, Any] | list[Any] | None = None
    question: str | None = None
    input_text: str | None = None
    candidate_labels: list[str] | None = None
    hypothesis_text: str | None = None
    options: list[str] | dict[str, str] | None = None
    levels: list[int | str] | None = None
    alpha: float | None = 0.05
    provider: str | None = None
    model_checkpoint: str | None = None
    device: str | None = None
    fast_exit_threshold: float | None = None
    uncertainty_threshold: float | None = None


class DecisionTestResponse(BaseModel):
    """Result from the isolated decision sandbox execution.

    Parameters
    ----------
    primitive : str
        Primitive executed.
    selected_option : str or int or bool or None
        Winning decision outcome.
    class_probability : float
        Softmax probability of top class.
    empirical_accuracy : float
        Calibrated empirical accuracy frequency P(correct).
    probabilities : dict of str to float
        Full class probability distribution.
    prediction_set : list of str or None
        Conformal prediction set C(x).
    tokens_saved_estimate : int, default 0
        Estimated LLM generation tokens saved by fast-exit.
    latency_ms : float
        Execution duration in milliseconds.
    is_mock : bool
        Whether result was generated by deterministic mock engine.
    decision_id : str or None, optional
        Identifier for the playground decision invocation.
    prediction : str or int or bool or None, optional
        Unified prediction value for the playground UI.
    confidence : float or None, optional
        Unified confidence score for the playground UI.
    conformal_set : list of str, default []
        Unified conformal prediction set for the playground UI.
    tier : str, default 'fast_exit'
        Routing tier ('fast_exit', 'system1', or 'system2').
    tokens_saved : int, default 0
        Estimated tokens saved for playground UI.
    """

    primitive: str
    selected_option: str | int | bool | None = None
    class_probability: float = 0.0
    empirical_accuracy: float = 0.0
    probabilities: dict[str, float] = Field(default_factory=dict)
    prediction_set: list[str] | None = None
    tokens_saved_estimate: int = 0
    latency_ms: float = 0.0
    is_mock: bool = True
    decision_id: str | None = None
    prediction: str | int | bool | None = None
    confidence: float | None = None
    conformal_set: list[str] = Field(default_factory=list)
    tier: str = "fast_exit"
    tokens_saved: int = 0
    engine_backend: str = "simulation"
    warning: str | None = None


class ModalResolverSettings(BaseModel):
    """Configuration for Propositional Modal Strength Resolution (ADR 0020).

    Parameters
    ----------
    mode : Literal['guardrail', 'convex', 'structural_only', 'engine_only'], default 'guardrail'
        Resolution strategy combining structuralist syntax with System 1 scoring.
    fusion_alpha : float, default 0.5
        Interpolation weight for convex mode: alpha * syntax + (1 - alpha) * engine.
    default_base_score : float, default 0.6
        Fallback baseline modality if both syntax and engine are indeterminate.
    """

    mode: Literal["guardrail", "convex", "structural_only", "engine_only"] = "guardrail"
    fusion_alpha: float = 0.5
    default_base_score: float = 0.6


class EngineSettings(BaseModel):
    """System-level engine settings governing pipeline execution and visualization.

    Parameters
    ----------
    schema_config : dict of str to Any
        The active pipeline ontology serialized dictionary.
    predicate_aliases : dict of str to Any, default {}
        Open-vocabulary predicate mappings (e.g. {'WIDERSPRICHT': {'polarity': -1, 'canonical': 'ATTACKS'}}).
    models : EngineModelConfig
        Default language model, embedding model, and reasoning thinking level presets.
    decision_engine : DecisionEngineSettings
        Configuration for the System 1 Decision Engine.
    modal_resolver : ModalResolverSettings
        Configuration for propositional modality resolution.
    updated_at : str or None, optional
        ISO 8601 timestamp of last mutation.
    """

    schema_config: dict[str, Any] = Field(default_factory=dict)
    predicate_aliases: dict[str, Any] = Field(default_factory=dict)
    models: EngineModelConfig = Field(default_factory=EngineModelConfig)
    decision_engine: DecisionEngineSettings = Field(default_factory=DecisionEngineSettings)
    modal_resolver: ModalResolverSettings = Field(default_factory=ModalResolverSettings)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EngineSettingsPatch(BaseModel):
    """Partial update payload for engine settings.

    Parameters
    ----------
    schema_config : dict of str to Any or None, optional
        Updated ontology schema dictionary.
    predicate_aliases : dict of str to Any or None, optional
        Updated predicate alias map.
    models : EngineModelConfig or None, optional
        Updated default model configuration.
    decision_engine : DecisionEngineSettings or None, optional
        Updated decision engine settings.
    modal_resolver : ModalResolverSettings or None, optional
        Updated modal resolver settings.
    """

    schema_config: dict[str, Any] | None = None
    predicate_aliases: dict[str, Any] | None = None
    models: EngineModelConfig | None = None
    decision_engine: DecisionEngineSettings | None = None
    modal_resolver: ModalResolverSettings | None = None
