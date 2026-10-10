"""TypeSafe Jev & Laya Decision Engine client adapters.

This module provides concrete implementations of the
:class:`~episteme_pipeline.protocols.decision.DecisionEngine` protocol:

- :class:`LayaDecisionEngine`: High-performance local Apple Silicon MLX inference
  via ``laya_mlx`` ($7–15\\text{ms}$, 0 output tokens).
- :class:`TransformersDecisionEngine`: PyTorch/Transformers fallback for Linux/CUDA
  environments where MLX is unavailable.
- :class:`DecisionEngineError`: Standardized exception for decision engine failures.
"""

from __future__ import annotations

import asyncio
import logging
import platform
from typing import Any, Sequence, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from episteme_pipeline.config import DecisionEngineConfig
from episteme_pipeline.decision.mock import compute_conformal_prediction_set
from episteme_pipeline.decision.strategies import (
    estimate_tokens_saved,
    evaluate_questions_sequentially,
    get_question_strategy,
)
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionQuestion,
    DecisionScore,
    ensure_decision_question,
)

logger = logging.getLogger(__name__)


class DecisionEngineError(RuntimeError):
    """Standardized exception raised for System 1 decision engine runtime errors.

    Parameters
    ----------
    message : str
        Human-readable description of the failure.
    cause : Exception or None, default None
        Underlying root-cause exception, if any.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


_estimate_tokens_saved = estimate_tokens_saved


class LayaDecisionEngine:
    """High-performance Apple Silicon MLX decision engine client.

    Runs local bidirectional Transformer inference using ``laya_mlx``
    (ModernBERT / mmBERT backbone) to evaluate typed questions against state
    blocks with dual confidence metrics and zero output token generation.

    Parameters
    ----------
    checkpoint : str, default "aac6fef/laya-mlx"
        Hugging Face repository ID or local path to pre-converted MLX checkpoint.
    dtype : str, default "float16"
        Computation precision ("float16" or "float32").
    batch_size : int, default 16
        Maximum questions processed per MLX forward pass.
    timeout_seconds : float, default 2.0
        Per-request inference timeout in seconds.
    default_confidence_threshold : float, default 0.85
        Empirical accuracy threshold for fast-exit routing.
    conformal_alpha : float, default 0.05
        Default significance level for conformal prediction sets (guaranteeing
        1 - alpha coverage).
    agent : Any or None, default None
        Optional pre-loaded ``laya.Agent`` instance. If None, loaded lazily.
    embed_fn : Any or None, default None
        Optional bi-encoder embedding function for large choice set shortlisting.
    shortlist_threshold : int, default 5
        Option count threshold above which candidate shortlisting is applied.
    compile : bool, default False
        Whether to enable MLX graph compilation.
    cache_prompts : bool, default False
        Whether to cache prefix tokenizations across repetitive calls.
    """

    def __init__(
        self,
        checkpoint: str = "aac6fef/laya-mlx",
        dtype: str = "float16",
        batch_size: int = 16,
        timeout_seconds: float = 2.0,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
        agent: Any = None,
        embed_fn: Any = None,
        shortlist_threshold: int = 5,
        compile: bool = False,
        cache_prompts: bool = False,
    ) -> None:
        self.checkpoint = checkpoint
        self.dtype = dtype
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.default_confidence_threshold = default_confidence_threshold
        self.conformal_alpha = conformal_alpha
        self.embed_fn = embed_fn
        self.shortlist_threshold = shortlist_threshold
        self.compile = compile
        self.cache_prompts = cache_prompts
        self._agent = agent

    @property
    def name(self) -> str:
        """Return the engine name."""
        return f"LayaDecisionEngine({self.checkpoint})"

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic representation of engine configuration.

        Returns
        -------
        dict of str to Any
            Deterministic dictionary containing model checkpoint, precision,
            batch size, inference timeout, calibration thresholds, and flags.
        """
        return {
            "class": self.__class__.__name__,
            "checkpoint": self.checkpoint,
            "dtype": self.dtype,
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds,
            "default_confidence_threshold": self.default_confidence_threshold,
            "conformal_alpha": self.conformal_alpha,
            "shortlist_threshold": self.shortlist_threshold,
            "compile": self.compile,
            "cache_prompts": self.cache_prompts,
        }

    def _get_agent(self) -> Any:
        """Lazily load the underlying Laya MLX agent.

        Returns
        -------
        Any
            The loaded ``laya_mlx`` Agent instance.

        Raises
        ------
        DecisionEngineError
            If ``laya_mlx`` is not installed or the checkpoint fails to load.
        """
        if self._agent is not None:
            return self._agent

        try:
            import laya_mlx as laya
        except ImportError as exc:
            raise DecisionEngineError(
                "laya-mlx is not installed or unavailable in this environment. "
                "Install via 'pip install laya-mlx' on Apple Silicon macOS, or use "
                "TransformersDecisionEngine for Linux/CUDA environments.",
                cause=exc,
            ) from exc

        try:
            self._agent = laya.load(
                self.checkpoint,
                dtype=self.dtype,
                batch_size=self.batch_size,
                compile=self.compile,
                cache_prompts=self.cache_prompts,
            )
            return self._agent
        except Exception as exc:
            raise DecisionEngineError(
                f"Failed to load Laya checkpoint {self.checkpoint!r}: {exc}",
                cause=exc,
            ) from exc

    def _run_predict_sync(
        self,
        agent: Any,
        state: Any,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Synchronously execute MLX forward pass with shortlisting support.

        Parameters
        ----------
        agent : Any
            Active Laya Agent instance.
        state : Any
            State payload.
        questions : dict of str to dict
            Typed questions payload conforming to Laya API.

        Returns
        -------
        dict
            Laya prediction output dictionary containing answers and action metadata.
        """
        try:
            # Check if any choice question requires shortlist pruning
            has_large_choices = any(
                q.get("type") == "choice"
                and len(q.get("criteria", [])) > self.shortlist_threshold
                for q in questions.values()
            )

            if has_large_choices and self.embed_fn is not None:
                try:
                    from laya_mlx import predict_shortlist

                    return predict_shortlist(
                        agent,
                        state,
                        questions,
                        self.embed_fn,
                        k=self.shortlist_threshold,
                    )
                except (ImportError, AttributeError):
                    pass

            return agent.predict(state, questions)
        except Exception as exc:
            raise DecisionEngineError(
                f"Laya inference forward pass failed: {exc}",
                cause=exc,
            ) from exc

    async def _predict_async(
        self,
        state: Any,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Run MLX prediction asynchronously in worker thread with timeout guard.

        Parameters
        ----------
        state : Any
            State block.
        questions : dict of str to dict
            Questions dictionary.

        Returns
        -------
        dict
            Prediction result.
        """
        agent = self._get_agent()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._run_predict_sync, agent, state, questions),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise DecisionEngineError(
                f"Laya inference timed out after {self.timeout_seconds} seconds.",
                cause=exc,
            ) from exc

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate a binary yes/no statement via Laya Noul head.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Binary proposition or verification question.

        Returns
        -------
        DecisionNoulResult
            Evaluation outcome containing calibrated probability and empirical accuracy.
        """
        questions = {
            "noul_q": {
                "type": "noul",
                "instructions": question,
            }
        }
        res = await self._predict_async(state, questions)

        answer_val = res.get("answers", {}).get("noul_q", 0.0)
        probability = float(answer_val)
        act_p = float(res.get("action", {}).get("act_probability", probability))
        passed = probability >= self.default_confidence_threshold

        return DecisionNoulResult(
            probability=probability,
            empirical_accuracy=act_p,
            passed=passed,
        )

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate a categorical choice via Laya Choice head.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Categorical decision question.
        options : list of str or dict of str to str
            Candidate labels or rubric mapping label to description.
        alpha : float or None, default None
            Significance level for conformal prediction set (1 - alpha coverage).

        Returns
        -------
        DecisionScore
            Score containing selected option, class probability, empirical accuracy,
            and conformal prediction set.
        """
        criteria = options if isinstance(options, (dict, list)) else list(options)
        questions = {
            "choice_q": {
                "type": "choice",
                "instructions": question,
                "criteria": criteria,
            }
        }
        res = await self._predict_async(state, questions)

        raw_answers = res.get("answers", {}).get("choice_q", {})
        if isinstance(raw_answers, dict):
            probabilities = {str(k): float(v) for k, v in raw_answers.items()}
        elif isinstance(raw_answers, str):
            probabilities = {raw_answers: 1.0}
        else:
            probabilities = {}

        if probabilities:
            selected_option = max(probabilities, key=probabilities.get)
            class_probability = probabilities[selected_option]
        else:
            opt_list = list(options.keys()) if isinstance(options, dict) else list(options)
            selected_option = opt_list[0] if opt_list else "UNKNOWN"
            class_probability = 0.5
            probabilities = {selected_option: class_probability}

        act_p = float(res.get("action", {}).get("act_probability", class_probability))
        effective_alpha = alpha if alpha is not None else self.conformal_alpha
        prediction_set = compute_conformal_prediction_set(
            probabilities, alpha=effective_alpha
        )
        tokens_saved = _estimate_tokens_saved(state, question, options)

        return DecisionScore(
            selected_option=selected_option,
            class_probability=class_probability,
            empirical_accuracy=act_p,
            probabilities=probabilities,
            prediction_set=prediction_set,
            tokens_saved_estimate=tokens_saved,
        )

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate an ordered scale or score via Laya Score head.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Rubric or scoring question.
        levels : list of int or list of str
            Ordered score levels.

        Returns
        -------
        DecisionScore
            Result indicating expected level and distribution.
        """
        questions = {
            "score_q": {
                "type": "score",
                "instructions": question,
                "criteria": [str(lvl) for lvl in levels],
            }
        }
        res = await self._predict_async(state, questions)

        answer_val = res.get("answers", {}).get("score_q")
        if isinstance(answer_val, dict):
            probabilities = {str(k): float(v) for k, v in answer_val.items()}
            selected_option = max(probabilities, key=probabilities.get)
            class_prob = probabilities[selected_option]
        elif isinstance(answer_val, (int, float)):
            idx = min(int(round(answer_val)), len(levels) - 1)
            selected_option = levels[idx]
            class_prob = 0.80
            probabilities = {
                str(lvl): (class_prob if lvl == selected_option else round(0.20 / max(1, len(levels) - 1), 4))
                for lvl in levels
            }
        else:
            selected_option = levels[0] if levels else 1
            class_prob = 0.70
            probabilities = {str(lvl): round(1.0 / max(1, len(levels)), 4) for lvl in levels}

        act_p = float(res.get("action", {}).get("act_probability", class_prob))
        prediction_set = [str(selected_option)]
        tokens_saved = _estimate_tokens_saved(state, question, levels)

        return DecisionScore(
            selected_option=selected_option,
            class_probability=class_prob,
            empirical_accuracy=act_p,
            probabilities=probabilities,
            prediction_set=prediction_set,
            tokens_saved_estimate=tokens_saved,
        )

    async def evaluate(
        self,
        state: str | dict[str, Any] | list[Any],
        question: DecisionQuestion | dict[str, Any],
    ) -> DecisionScore | DecisionNoulResult:
        """Evaluate a single typed question against a state payload.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : DecisionQuestion or dict
            Typed decision question specification or dictionary.

        Returns
        -------
        DecisionScore or DecisionNoulResult
            Evaluation outcome.
        """
        typed_q = ensure_decision_question(question)
        strategy = get_question_strategy(typed_q.type)
        return await strategy.evaluate_single(self, state, typed_q)

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, DecisionQuestion | dict[str, Any]],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate multiple typed questions in a single forward pass.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        questions : dict of str to (DecisionQuestion or dict)
            Dictionary mapping question identifiers to specifications.

        Returns
        -------
        dict of str to (DecisionScore or DecisionNoulResult)
            Mapped results for all evaluated questions.
        """
        typed_questions = {q_id: ensure_decision_question(q_spec) for q_id, q_spec in questions.items()}
        laya_questions = {
            q_id: get_question_strategy(q_item.type).to_laya_spec(q_item)
            for q_id, q_item in typed_questions.items()
        }

        res = await self._predict_async(state, laya_questions)
        answers = res.get("answers", {})
        action_meta = res.get("action", {})
        default_act_p = float(action_meta.get("act_probability", 0.85))

        return {
            q_id: get_question_strategy(q_item.type).decode_laya_answer(
                question=q_item,
                raw_answer=answers.get(q_id),
                default_act_p=default_act_p,
                state=state,
                default_confidence_threshold=self.default_confidence_threshold,
                conformal_alpha=self.conformal_alpha,
            )
            for q_id, q_item in typed_questions.items()
        }


class TransformersDecisionEngine:
    """Hugging Face Transformers / PyTorch decision engine client.

    Serves as the cross-platform fallback for Linux/CUDA environments where
    MLX is unavailable, loading ModernBERT or mmBERT checkpoints via
    Hugging Face ``transformers``.

    Parameters
    ----------
    model_name : str, default "convaiinnovations/laya"
        Hugging Face checkpoint identifier or local directory.
    device : str or None, default None
        Inference execution device ('cuda', 'cpu', or None for auto-detection).
    batch_size : int, default 16
        Maximum questions processed per batch.
    timeout_seconds : float, default 2.0
        Per-request inference timeout in seconds.
    default_confidence_threshold : float, default 0.85
        Threshold for binary noul decisions.
    conformal_alpha : float, default 0.05
        Default significance level for conformal prediction sets.
    model : Any or None, default None
        Optional pre-loaded PyTorch model or callable runner.
    tokenizer : Any or None, default None
        Optional pre-loaded tokenizer.
    """

    def __init__(
        self,
        model_name: str = "convaiinnovations/laya",
        device: str | None = None,
        batch_size: int = 16,
        timeout_seconds: float = 2.0,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
        model: Any = None,
        tokenizer: Any = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.default_confidence_threshold = default_confidence_threshold
        self.conformal_alpha = conformal_alpha
        self._model = model
        self._tokenizer = tokenizer

    @property
    def name(self) -> str:
        """Return the engine name."""
        return f"TransformersDecisionEngine({self.model_name})"

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic representation of engine configuration.

        Returns
        -------
        dict of str to Any
            Deterministic dictionary containing model name, device, batch size,
            timeout, and calibration parameters.
        """
        return {
            "class": self.__class__.__name__,
            "model_name": self.model_name,
            "device": str(self.device) if self.device else None,
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds,
            "default_confidence_threshold": self.default_confidence_threshold,
            "conformal_alpha": self.conformal_alpha,
        }

    def _ensure_loaded(self) -> tuple[Any, Any]:
        """Lazily load PyTorch model and tokenizer.

        Returns
        -------
        tuple of (model, tokenizer)
            Loaded PyTorch model and tokenizer objects.

        Raises
        ------
        DecisionEngineError
            If loading fails or dependencies are missing.
        """
        if self._model is not None and self._tokenizer is not None:
            return self._model, self._tokenizer

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise DecisionEngineError(
                "transformers or torch is not installed. Install via 'pip install transformers torch'.",
                cause=exc,
            ) from exc

        try:
            dev = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            if self._tokenizer is None:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            if self._model is None:
                self._model = AutoModel.from_pretrained(self.model_name)
                self._model.to(dev)
                self._model.eval()
            self.device = dev
            return self._model, self._tokenizer
        except Exception as exc:
            raise DecisionEngineError(
                f"Failed to load Transformers model {self.model_name!r}: {exc}",
                cause=exc,
            ) from exc

    @staticmethod
    def _extract_model_logits(outputs: Any) -> Any:
        """Extract prediction logits from Hugging Face ModelOutput or PyTorch tensor.

        Supports sequence classification outputs (``logits``) and base transformer
        hidden states (using normalized pooled representation as similarity proxy).

        Parameters
        ----------
        outputs : Any
            Hugging Face ModelOutput or PyTorch tensor.

        Returns
        -------
        torch.Tensor
            Extracted logits tensor for candidate ranking.
        """
        try:
            return outputs.logits.squeeze(-1)
        except AttributeError:
            pass

        try:
            return outputs.last_hidden_state[:, 0, :].norm(dim=-1)
        except AttributeError:
            pass

        if isinstance(outputs, dict):
            if "logits" in outputs:
                return outputs["logits"].squeeze(-1)
            if "last_hidden_state" in outputs:
                return outputs["last_hidden_state"][:, 0, :].norm(dim=-1)

        return outputs.squeeze(-1)

    def _predict_with_model_sync(
        self,
        state: Any,
        question: str,
        options: Sequence[str] | dict[str, str],
    ) -> dict[str, float]:
        """Compute softmax probabilities across candidate options synchronously.

        Parameters
        ----------
        state : Any
            State block.
        question : str
            Evaluation question.
        options : Sequence of str or dict
            Candidate options.

        Returns
        -------
        dict of str to float
            Normalized probability distribution over candidate options.
        """
        model, tokenizer = self._ensure_loaded()
        opt_keys = list(options.keys()) if isinstance(options, dict) else list(options)
        if not opt_keys:
            return {"UNKNOWN": 1.0}

        import torch

        state_str = str(state)
        pairs = [(state_str, f"{question} {opt}") for opt in opt_keys]

        with torch.no_grad():
            inputs = tokenizer(
                [p[0] for p in pairs],
                [p[1] for p in pairs],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device or "cpu") for k, v in inputs.items()}
            outputs = model(**inputs)
            logits = self._extract_model_logits(outputs)

            probs = torch.softmax(logits, dim=0).tolist()
            if isinstance(probs, float):
                probs = [probs]

        return {opt: round(float(p), 4) for opt, p in zip(opt_keys, probs)}

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate a categorical choice using Transformers forward pass.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Categorical decision question.
        options : list of str or dict of str to str
            Available options.
        alpha : float or None, default None
            Significance level for conformal prediction set.

        Returns
        -------
        DecisionScore
            Categorical evaluation score.
        """
        try:
            probs = await asyncio.wait_for(
                asyncio.to_thread(
                    self._predict_with_model_sync, state, question, options
                ),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise DecisionEngineError(
                f"Transformers inference timed out after {self.timeout_seconds} seconds.",
                cause=exc,
            ) from exc
        except Exception as exc:
            raise DecisionEngineError(
                f"Transformers evaluation failed: {exc}",
                cause=exc,
            ) from exc

        selected = max(probs, key=probs.get) if probs else "UNKNOWN"
        class_prob = probs.get(selected, 0.5)
        effective_alpha = alpha if alpha is not None else self.conformal_alpha
        pred_set = compute_conformal_prediction_set(probs, alpha=effective_alpha)
        tokens_saved = _estimate_tokens_saved(state, question, options)

        return DecisionScore(
            selected_option=selected,
            class_probability=class_prob,
            empirical_accuracy=class_prob,
            probabilities=probs,
            prediction_set=pred_set,
            tokens_saved_estimate=tokens_saved,
        )

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate a binary yes/no statement.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Binary proposition or decision question.

        Returns
        -------
        DecisionNoulResult
            Evaluation outcome.
        """
        score = await self.evaluate_choice(state, question, ["true", "false"])
        prob = score.probabilities.get("true", 0.5)
        passed = prob >= self.default_confidence_threshold
        return DecisionNoulResult(
            probability=prob,
            empirical_accuracy=score.class_probability,
            passed=passed,
        )

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate an ordered scale or score against levels.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Scoring rubric question.
        levels : list of int or list of str
            Ordered scale levels.

        Returns
        -------
        DecisionScore
            Evaluation score.
        """
        level_strs = [str(lvl) for lvl in levels]
        return await self.evaluate_choice(state, question, level_strs)

    async def evaluate(
        self,
        state: str | dict[str, Any] | list[Any],
        question: DecisionQuestion | dict[str, Any],
    ) -> DecisionScore | DecisionNoulResult:
        """Evaluate a single typed question against a state payload.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : DecisionQuestion or dict
            Typed decision question specification or dictionary.

        Returns
        -------
        DecisionScore or DecisionNoulResult
            Evaluation outcome.
        """
        typed_q = ensure_decision_question(question)
        strategy = get_question_strategy(typed_q.type)
        return await strategy.evaluate_single(self, state, typed_q)

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, DecisionQuestion | dict[str, Any]],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate multiple questions against state sequentially via strategies.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        questions : dict of str to (DecisionQuestion or dict)
            Question definitions.

        Returns
        -------
        dict of str to (DecisionScore or DecisionNoulResult)
            Results for all questions.
        """
        return await evaluate_questions_sequentially(self, state, questions)

def _is_mlx_available() -> bool:
    """Check if MLX execution is supported on the current hardware.

    Returns
    -------
    bool
        True if running on Apple Silicon (macOS arm64) with ``laya_mlx`` installed.
    """
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import laya_mlx  # noqa: F401

            return True
        except ImportError:
            return False
    return False


def _map_transformers_checkpoint(checkpoint: str) -> str:
    """Map MLX checkpoint repository identifiers to PyTorch/Transformers equivalents.

    Parameters
    ----------
    checkpoint : str
        Source checkpoint identifier.

    Returns
    -------
    str
        PyTorch/Transformers compatible checkpoint repository identifier.
    """
    if "mlx" in checkpoint.lower():
        return "convaiinnovations/laya"
    return checkpoint


def _create_engine_backend(
    provider: str,
    checkpoint: str = "aac6fef/laya-mlx",
    default_confidence_threshold: float = 0.85,
    conformal_alpha: float = 0.05,
    timeout_seconds: float = 2.0,
    batch_size: int = 16,
    device: str | None = None,
    *args: Any,
    **kwargs: Any,
) -> DecisionEngine:
    """Instantiate a concrete DecisionEngine adapter based on provider and platform.

    Parameters
    ----------
    provider : str
        Backend selector ('laya', 'mlx', 'transformers', 'mock', 'stub', or 'auto').
    checkpoint : str, default "aac6fef/laya-mlx"
        Model repository or local path.
    default_confidence_threshold : float, default 0.85
        Threshold for binary and gating decisions.
    conformal_alpha : float, default 0.05
        Conformal significance level (1 - alpha coverage).
    timeout_seconds : float, default 2.0
        Per-request inference timeout in seconds.
    batch_size : int, default 16
        Batch processing size.
    device : str or None, default None
        Target compute device.
    *args : Any
        Positional arguments forwarded to backend.
    **kwargs : Any
        Keyword arguments forwarded to backend.

    Returns
    -------
    DecisionEngine
        Configured concrete decision engine instance.
    """
    provider_clean = provider.strip().lower()

    if provider_clean in ("mock", "stub"):
        from episteme_pipeline.decision.mock import MockJevDecisionEngine

        return MockJevDecisionEngine(
            default_confidence_threshold=default_confidence_threshold,
            conformal_alpha=conformal_alpha,
        )

    use_laya = False
    if provider_clean in ("laya", "mlx"):
        use_laya = True
    elif provider_clean == "transformers":
        use_laya = False
    else:  # auto or unspecified
        use_laya = _is_mlx_available()

    if use_laya:
        return LayaDecisionEngine(
            checkpoint=checkpoint,
            batch_size=batch_size,
            timeout_seconds=timeout_seconds,
            default_confidence_threshold=default_confidence_threshold,
            conformal_alpha=conformal_alpha,
            *args,
            **kwargs,
        )
    else:
        tf_model = _map_transformers_checkpoint(checkpoint)
        dev_val = str(device) if device and str(device) not in ("auto", "mlx") else None
        return TransformersDecisionEngine(
            model_name=tf_model,
            device=dev_val,
            batch_size=batch_size,
            timeout_seconds=timeout_seconds,
            default_confidence_threshold=default_confidence_threshold,
            conformal_alpha=conformal_alpha,
            *args,
            **kwargs,
        )


class AutoDecisionEngine:
    """Decision Engine adapter delegating to the best available backend.

    Prefers :class:`LayaDecisionEngine` on Apple Silicon when ``laya_mlx`` is
    installed; otherwise falls back to :class:`TransformersDecisionEngine`.

    Parameters
    ----------
    checkpoint : str, default "aac6fef/laya-mlx"
        Model checkpoint identifier (MLX format or Hugging Face repository ID).
    model_name : str or None, optional
        Alternative checkpoint identifier for Transformers.
    provider : str or None, optional
        Explicit backend selector ('laya', 'mlx', 'transformers', or 'auto').
    default_confidence_threshold : float, default 0.85
        Empirical accuracy threshold for fast-exit routing.
    conformal_alpha : float, default 0.05
        Significance level for conformal prediction sets.
    batch_size : int, default 16
        Maximum batch size for evaluation.
    timeout_seconds : float, default 2.0
        Per-decision call timeout in seconds.
    *args : Any
        Additional positional arguments passed to backend.
    **kwargs : Any
        Additional keyword arguments forwarded to backend engines.
    """

    def __init__(
        self,
        checkpoint: str = "aac6fef/laya-mlx",
        model_name: str | None = None,
        provider: str | None = None,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
        batch_size: int = 16,
        timeout_seconds: float = 2.0,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        target_checkpoint = model_name if model_name is not None else checkpoint
        self._inner: DecisionEngine = _create_engine_backend(
            provider=provider or "auto",
            checkpoint=target_checkpoint,
            default_confidence_threshold=default_confidence_threshold,
            conformal_alpha=conformal_alpha,
            batch_size=batch_size,
            timeout_seconds=timeout_seconds,
            *args,
            **kwargs,
        )

    @property
    def name(self) -> str:
        """Return the active underlying engine name.

        Returns
        -------
        str
            Engine identifier.
        """
        return self._inner.name

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic representation of engine configuration.

        Returns
        -------
        dict of str to Any
            Deterministic dictionary delegating to the underlying engine backend.
        """
        inner_fp = (
            self._inner.fingerprint()
            if hasattr(self._inner, "fingerprint") and callable(self._inner.fingerprint)
            else {"class": self._inner.__class__.__name__}
        )
        return {
            "class": self.__class__.__name__,
            "inner": inner_fp,
        }

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate a binary yes/no statement.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        question : str
            Proposition or question.

        Returns
        -------
        DecisionNoulResult
            Evaluation outcome.
        """
        return await self._inner.evaluate_noul(state, question)

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate a categorical choice question.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        question : str
            Categorical decision question.
        options : list of str or dict of str to str
            Candidate choices.
        alpha : float or None, default None
            Miscoverage significance level.

        Returns
        -------
        DecisionScore
            Scored categorical decision.
        """
        return await self._inner.evaluate_choice(state, question, options, alpha)

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate an ordered scale or rubric score.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        question : str
            Rubric or scoring question.
        levels : list of int or list of str
            Ordered score levels.

        Returns
        -------
        DecisionScore
            Score outcome.
        """
        return await self._inner.evaluate_score(state, question, levels)

    async def evaluate(
        self,
        state: str | dict[str, Any] | list[Any],
        question: DecisionQuestion | dict[str, Any],
    ) -> DecisionScore | DecisionNoulResult:
        """Evaluate a single typed question.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        question : DecisionQuestion or dict
            Proposition or question specification.

        Returns
        -------
        DecisionScore or DecisionNoulResult
            Evaluation outcome.
        """
        return await self._inner.evaluate(state, question)

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, DecisionQuestion | dict[str, Any]],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate multiple questions in batch.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        questions : dict of str to (DecisionQuestion or dict)
            Question specifications.

        Returns
        -------
        dict of str to (DecisionScore or DecisionNoulResult)
            Batch evaluation results.
        """
        return await self._inner.evaluate_batch(state, questions)


def resolve_decision_engine(
    config: DecisionEngineConfig | dict[str, Any] | BaseModel | DecisionEngine | None = None,
    *,
    fallback_to_mock: bool = False,
) -> DecisionEngine | None:
    """Instantiate and configure the appropriate DecisionEngine from configuration.

    Inspects configuration objects (such as ``DecisionEngineConfig``,
    ``DecisionEngineSettings``, or dictionaries) and constructs the matching
    concrete ``DecisionEngine`` implementation.

    Parameters
    ----------
    config : DecisionEngineConfig, dict, BaseModel, DecisionEngine, or None, default None
        Configuration object, dictionary, or existing DecisionEngine instance.
    fallback_to_mock : bool, default False
        Whether to instantiate a MockJevDecisionEngine if dependencies or weights
        fail to initialize.

    Returns
    -------
    DecisionEngine or None
        Resolved DecisionEngine instance, or None if provider is 'none' / unconfigured.

    Raises
    ------
    TypeError
        If config is not a recognized configuration shape.
    DecisionEngineError
        If an explicit non-mock provider cannot be instantiated and fallback_to_mock is False.
    """
    if config is None:
        return None

    if isinstance(config, DecisionEngine):
        return config

    from episteme_pipeline.config import DecisionEngineConfig

    if isinstance(config, DecisionEngineConfig):
        cfg = config
    elif isinstance(config, dict):
        cfg = DecisionEngineConfig.model_validate(config)
    elif isinstance(config, BaseModel):
        cfg = DecisionEngineConfig.model_validate(config.model_dump())
    else:
        raise TypeError(
            f"Expected DecisionEngineConfig, dict, or DecisionEngine, got {type(config).__name__}"
        )

    provider_clean = cfg.provider.strip().lower()
    if provider_clean in ("none", "disabled", ""):
        return None

    conf_thresh = cfg.fast_exit_threshold or cfg.default_confidence_threshold

    try:
        return _create_engine_backend(
            provider=provider_clean,
            checkpoint=cfg.model_checkpoint,
            default_confidence_threshold=conf_thresh,
            conformal_alpha=cfg.conformal_alpha,
            timeout_seconds=cfg.timeout_seconds,
            device=cfg.device,
        )
    except Exception:
        if fallback_to_mock:
            from episteme_pipeline.decision.mock import MockJevDecisionEngine

            return MockJevDecisionEngine(
                default_confidence_threshold=conf_thresh,
                conformal_alpha=cfg.conformal_alpha,
            )
        raise

