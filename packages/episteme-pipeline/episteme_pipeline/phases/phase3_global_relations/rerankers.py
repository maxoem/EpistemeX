"""Default reranker components for global relation extraction."""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any

from episteme_pipeline.contracts.domain import L2Entity, SubGraph
from episteme_pipeline.prompts.default_prompts import PAIR_GATING_DECISION_PROMPT
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.extractors import CrossEncoder, RelationReranker, normalize_scores
from episteme_pipeline.utils import format_envelope

_model_cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


def build_relation_reranker_inputs(
    entity_a: L2Entity,
    env_a: SubGraph,
    entity_b: L2Entity,
    env_b: SubGraph,
) -> tuple[str, str]:
    """Build the query/document pair consumed by the cross-encoder.

    In the SOTA T_A x T_B architecture, we bypass graph constraints (G)
    and directly evaluate contextual isomorphism between the two Textual
    Envelopes. The respective [ENT] markers act as the bridge.

    Parameters
    ----------
    entity_a
        Query-side entity.
    env_a
        Query-side subgraph envelope (no longer strictly necessary for text comparison, but kept for signature).
    entity_b
        Document-side entity.
    env_b
        Document-side subgraph envelope.

    Returns
    -------
    tuple[str, str]
        T_A and T_B passed to the cross-encoder.
    """
    # Use Textual Envelopes if available; fallback to legacy format otherwise.
    query = entity_a.textual_envelope if entity_a.textual_envelope else f"Entity: {entity_a.name}\nContext: {format_envelope(env_a, SubGraph(center_id='', nodes=[], triples=[], depth=0))}"
    
    doc_text = entity_b.textual_envelope if entity_b.textual_envelope else f"Entity: {entity_b.name}\nContext: {format_envelope(SubGraph(center_id='', nodes=[], triples=[], depth=0), env_b)}"
    
    return query, doc_text


def summarize_reranker_text_pair(
    query: str,
    doc_text: str,
    *,
    max_length: int | None = None,
) -> dict[str, object]:
    """Return lightweight size metadata for a reranker text pair.

    Parameters
    ----------
    query
        Query text passed to the reranker.
    doc_text
        Document text passed to the reranker.
    max_length
        Configured tokenizer truncation length for the cross-encoder.

    Returns
    -------
    dict[str, object]
        Character, byte, and line counts for each side and the combined pair.
    """
    query_bytes = len(query.encode("utf-8"))
    doc_bytes = len(doc_text.encode("utf-8"))
    return {
        "query_char_count": len(query),
        "query_byte_count": query_bytes,
        "query_line_count": query.count("\n") + 1 if query else 0,
        "document_char_count": len(doc_text),
        "document_byte_count": doc_bytes,
        "document_line_count": doc_text.count("\n") + 1 if doc_text else 0,
        "pair_char_count": len(query) + len(doc_text),
        "pair_byte_count": query_bytes + doc_bytes,
        "max_length": max_length,
    }


def _freeze_dict(d: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    """Convert a dictionary into a hashable sorted tuple for cache keys."""
    if not d:
        return ()
    return tuple(sorted((str(k), repr(v)) for k, v in d.items()))


def _model_cache_key(
    model_name: str,
    prompts: dict[str, str],
    default_prompt_name: str | None,
    max_length: int | None,
    device: str | None = None,
    trust_remote_code: bool = False,
    model_kwargs: dict[str, Any] | None = None,
    tokenizer_args: dict[str, Any] | None = None,
    config_args: dict[str, Any] | None = None,
) -> tuple[object, ...]:
    """Return a stable cache key for a configured reranker model."""
    return (
        model_name,
        tuple(sorted(prompts.items())),
        default_prompt_name,
        max_length,
        device,
        trust_remote_code,
        _freeze_dict(model_kwargs),
        _freeze_dict(tokenizer_args),
        _freeze_dict(config_args),
    )


class CrossEncoderRelationReranker(RelationReranker):
    """Lift a text :class:`CrossEncoder` into the :class:`RelationReranker` interface.

    The two interfaces are deliberately distinct — a ``RelationReranker`` scores
    domain objects and may be structural (e.g. a GNN), a ``CrossEncoder`` scores
    text pairs. When the caller only has a text cross-encoder, this adapter
    makes the conversion explicit and visible at the composition root instead of
    relying on one concrete class happening to implement both.

    Parameters
    ----------
    cross_encoder
        Any object satisfying the ``CrossEncoder`` protocol.
    """

    def __init__(self, cross_encoder: CrossEncoder) -> None:
        if not hasattr(cross_encoder, "predict"):
            raise TypeError(
                f"{type(cross_encoder).__name__} has no .predict(pairs) method; "
                "it does not satisfy the CrossEncoder protocol."
            )
        self.cross_encoder = cross_encoder

    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: SubGraph,
        entity_b: L2Entity,
        env_b: SubGraph,
    ) -> float:
        query, doc_text = build_relation_reranker_inputs(entity_a, env_a, entity_b, env_b)
        return normalize_scores(self.cross_encoder.predict([(query, doc_text)]))[0]


class SentenceTransformerCrossEncoderReranker(RelationReranker):
    """Relation reranker backed by a sentence-transformers cross encoder.

    The heavy ``sentence_transformers`` and ``torch`` dependencies are imported
    lazily so importing the pipeline package never loads a model or touches the
    Hugging Face cache.

    Parameters
    ----------
    model_name
        Hugging Face model identifier passed to ``CrossEncoder`` when ``model``
        is not provided.
    prompts
        Optional prompt mapping for reranker models that use named prompts.
    default_prompt_name
        Optional default prompt name passed to ``CrossEncoder``.
    model
        Preconstructed cross encoder. This is primarily useful for tests or
        callers that want to own model loading.
    activation_fn
        Optional activation function passed to ``CrossEncoder.predict``. When
        omitted, ``torch.nn.Sigmoid()`` is used.
    max_length
        Maximum input sequence length forwarded to the cross-encoder.
    cache_model
        Whether to cache the loaded model in memory for subsequent instances.
        When True, the model is cached using the model configuration as key.
        This can significantly reduce loading time when creating multiple
        reranker instances.
    device
        Target device for model inference (e.g., ``"cuda"``, ``"mps"``, ``"cpu"``).
    trust_remote_code
        Whether to allow execution of custom modeling code hosted on Hugging Face.
    model_kwargs
        Keyword arguments passed down to ``AutoModelForSequenceClassification.from_pretrained``.
    tokenizer_args
        Keyword arguments passed down to ``AutoTokenizer.from_pretrained``.
    config_args
        Keyword arguments passed down to ``AutoConfig.from_pretrained``.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Reranker-0.6B",
        *,
        prompts: dict[str, str] | None = None,
        default_prompt_name: str | None = "classification",
        model: Any | None = None,
        activation_fn: Callable[..., Any] | None = None,
        max_length: int | None = 1024,
        cache_model: bool = False,
        device: str | None = None,
        trust_remote_code: bool = False,
        model_kwargs: dict[str, Any] | None = None,
        tokenizer_args: dict[str, Any] | None = None,
        config_args: dict[str, Any] | None = None,
    ) -> None:
        self.prompt_name = default_prompt_name
        self.activation_fn = activation_fn
        self.max_length = max_length
        self.device = device
        self.trust_remote_code = trust_remote_code
        self.model_kwargs = model_kwargs
        self.tokenizer_args = tokenizer_args
        self.config_args = config_args
        effective_prompts = prompts or _qwen_reranker_prompts()
        cache_key = _model_cache_key(
            model_name=model_name,
            prompts=effective_prompts,
            default_prompt_name=default_prompt_name,
            max_length=max_length,
            device=device,
            trust_remote_code=trust_remote_code,
            model_kwargs=model_kwargs,
            tokenizer_args=tokenizer_args,
            config_args=config_args,
        )
        if model is not None:
            self.model = model
        elif cache_model and cache_key in _model_cache:
            self.model = _model_cache[cache_key]
        else:
            self.model = self._load_model(
                model_name=model_name,
                prompts=effective_prompts,
                max_length=max_length,
                device=device,
                trust_remote_code=trust_remote_code,
                automodel_args=model_kwargs,
                tokenizer_args=tokenizer_args,
                config_args=config_args,
            )
            if cache_model:
                _model_cache[cache_key] = self.model

    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: SubGraph,
        entity_b: L2Entity,
        env_b: SubGraph,
    ) -> float:
        """Score whether two entities likely participate in a relation.

        Parameters
        ----------
        entity_a
            First entity, represented as the query side of the pair.
        env_a
            Context envelope for ``entity_a``.
        entity_b
            Second entity, represented as the document side of the pair.
        env_b
            Context envelope for ``entity_b``.

        Returns
        -------
        float
            Cross-encoder score normalized by the configured activation
            function.
        """
        query, doc_text = build_relation_reranker_inputs(
            entity_a,
            env_a,
            entity_b,
            env_b,
        )

        score = self.model.predict(
            [(query, doc_text)],
            activation_fn=self.activation_fn or self._default_activation_fn(),
            prompt_name=self.prompt_name,
        )[0]

        return float(score)

    def predict(
        self,
        pairs: list[tuple[str, str]],
        batch_size: int = 32,
        show_progress_bar: bool | None = None,
        activation_fn: Callable[..., Any] | None = None,
        apply_softmax: bool | None = None,
        convert_to_numpy: bool = True,
        convert_to_tensor: bool = False,
    ) -> Any:
        """Predict cross-encoder similarity scores for a list of text pairs.

        Implements the ``CrossEncoder`` protocol signature directly.
        """
        return self.model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            activation_fn=activation_fn or self.activation_fn or self._default_activation_fn(),
            apply_softmax=apply_softmax,
            convert_to_numpy=convert_to_numpy,
            convert_to_tensor=convert_to_tensor,
            prompt_name=self.prompt_name,
        )


    def describe_relation_input(
        self,
        entity_a: L2Entity,
        env_a: SubGraph,
        entity_b: L2Entity,
        env_b: SubGraph,
    ) -> dict[str, object]:
        """Summarize the current reranker input without executing inference.

        Parameters
        ----------
        entity_a
            Query-side entity.
        env_a
            Query-side envelope.
        entity_b
            Document-side entity.
        env_b
            Document-side envelope.

        Returns
        -------
        dict[str, object]
            Size metadata for the reranker query/document pair.
        """
        query, doc_text = build_relation_reranker_inputs(
            entity_a,
            env_a,
            entity_b,
            env_b,
        )
        return summarize_reranker_text_pair(
            query,
            doc_text,
            max_length=self.max_length,
        )

    @staticmethod
    def _load_model(
        *,
        model_name: str,
        prompts: dict[str, str],
        max_length: int | None,
        device: str | None = None,
        trust_remote_code: bool = False,
        automodel_args: dict[str, Any] | None = None,
        tokenizer_args: dict[str, Any] | None = None,
        config_args: dict[str, Any] | None = None,
    ) -> Any:
        """Load a sentence-transformers cross encoder.

        Parameters
        ----------
        model_name
            Hugging Face model identifier.
        prompts
            Prompt mapping passed to the model constructor.
        max_length
            Maximum input sequence length forwarded to the cross-encoder.
        device
            Target device for model inference (e.g., ``"cuda"``, ``"mps"``, ``"cpu"``).
        trust_remote_code
            Whether to allow custom modeling code execution from Hugging Face.
        automodel_args
            Keyword arguments passed down to ``AutoModelForSequenceClassification.from_pretrained``.
        tokenizer_args
            Keyword arguments passed down to ``AutoTokenizer.from_pretrained``.
        config_args
            Keyword arguments passed down to ``AutoConfig.from_pretrained``.

        Returns
        -------
        Any
            Initialized ``sentence_transformers.CrossEncoder`` instance.
        """
        from sentence_transformers import CrossEncoder

        kwargs: dict[str, Any] = {
            "prompts": prompts,
            "max_length": max_length,
            "trust_remote_code": trust_remote_code,
        }
        if device is not None:
            kwargs["device"] = device
        if automodel_args is not None:
            kwargs["automodel_args"] = automodel_args
        if tokenizer_args is not None:
            kwargs["tokenizer_args"] = tokenizer_args
        if config_args is not None:
            kwargs["config_args"] = config_args

        return CrossEncoder(
            model_name,
            **kwargs,
        )

    @staticmethod
    def _default_activation_fn() -> Any:
        """Return the default sigmoid activation for cross-encoder scores.

        Returns
        -------
        Any
            ``torch.nn.Sigmoid`` instance.
        """
        import torch

        return torch.nn.Sigmoid()


def _qwen_reranker_prompts() -> dict[str, str]:
    """Return the default prompt mapping for Qwen reranker models.

    Returns
    -------
    dict[str, str]
        Prompt mapping keyed by prompt name.
    """
    return {
        "classification": (
            "Judge whether the Document meets the requirements based on the "
            "Query and the Instruct provided."
        )
    }

class JevRelationReranker(RelationReranker):
    """Relation reranker backed by the TypeSafe Jev Decision Engine.

    Evaluates relation plausibility and returns the empirical accuracy score.

    Parameters
    ----------
    decision_engine : Any
        The calibrated decision engine instance.
    prompts : StructuredPromptBundle or None, default None
        Optional prompt bundle carrying the decision question template.
    """

    def __init__(
        self,
        decision_engine: Any,
        prompts: StructuredPromptBundle | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts
        if prompts is not None:
            template = prompts.decision_template
        else:
            template = PAIR_GATING_DECISION_PROMPT

        if not template or not template.strip():
            raise ValueError("No decision prompt configured for JevRelationReranker.")
        self.decision_template = template.strip()

    async def score_relation(
        self,
        entity_a: L2Entity,
        env_a: SubGraph,
        entity_b: L2Entity,
        env_b: SubGraph,
    ) -> float:
        # Context window guard - limit tokens to < 800 (or characters approx 3200)
        # Using a simple character truncation for envelope
        query, doc_text = build_relation_reranker_inputs(entity_a, env_a, entity_b, env_b)
        
        # Simple truncation to stay within budget
        if len(query) > 1600:
            query = query[:1600] + "..."
        if len(doc_text) > 1600:
            doc_text = doc_text[:1600] + "..."

        context = f"Entity A:\n{query}\n\nEntity B:\n{doc_text}"
        question = self.decision_template.format(entity_a=entity_a.name, entity_b=entity_b.name)

        decision = await self.decision_engine.evaluate_noul(
            state=context,
            question=question,
        )
        
        # return calibrated probability or empirical accuracy
        return decision.probability if decision.passed else (1.0 - decision.probability) * 0.1

