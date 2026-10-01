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
from typing import Any, Sequence

from episteme_pipeline.decision.mock import compute_conformal_prediction_set
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
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


def _estimate_tokens_saved(
    state: Any,
    question: str,
    options: Sequence[Any] | dict[str, Any] | None = None,
) -> int:
    """Heuristic estimate of generative LLM tokens saved by System 1 fast-exit.

    Parameters
    ----------
    state : Any
        The input state block.
    question : str
        The evaluation question.
    options : Sequence or dict or None, default None
        Options or levels considered.

    Returns
    -------
    int
        Estimated tokens saved (input prompt + completion).
    """
    state_len = len(str(state))
    question_len = len(question)
    options_count = len(options) if options else 0
    prompt_tokens = (state_len // 4) + (question_len // 4) + (options_count * 8)
    completion_tokens = 50
    return prompt_tokens + completion_tokens


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
                import laya_mlx as laya

                if hasattr(laya, "predict_shortlist"):
                    return laya.predict_shortlist(
                        agent,
                        state,
                        questions,
                        self.embed_fn,
                        k=self.shortlist_threshold,
                    )

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

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate multiple typed questions in a single forward pass.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        questions : dict of str to dict
            Dictionary mapping question identifiers to specifications.

        Returns
        -------
        dict of str to (DecisionScore or DecisionNoulResult)
            Mapped results for all evaluated questions.
        """
        laya_questions: dict[str, dict[str, Any]] = {}
        for q_id, q_spec in questions.items():
            q_type = q_spec.get("type", "choice")
            instructions = q_spec.get("instructions", q_spec.get("question", ""))
            criteria = q_spec.get("criteria", q_spec.get("options", q_spec.get("levels")))
            entry: dict[str, Any] = {"type": q_type, "instructions": instructions}
            if criteria is not None:
                entry["criteria"] = criteria
            laya_questions[q_id] = entry

        res = await self._predict_async(state, laya_questions)
        answers = res.get("answers", {})
        action_meta = res.get("action", {})
        default_act_p = float(action_meta.get("act_probability", 0.85))

        results: dict[str, DecisionScore | DecisionNoulResult] = {}
        for q_id, q_spec in questions.items():
            q_type = q_spec.get("type", "choice")
            raw_ans = answers.get(q_id)

            if q_type == "noul":
                prob = float(raw_ans) if isinstance(raw_ans, (int, float)) else 0.5
                passed = prob >= self.default_confidence_threshold
                results[q_id] = DecisionNoulResult(
                    probability=prob,
                    empirical_accuracy=default_act_p,
                    passed=passed,
                )
            elif q_type == "score":
                levels = q_spec.get("criteria", q_spec.get("levels", [1, 2, 3]))
                if isinstance(raw_ans, (int, float)):
                    idx = min(int(round(raw_ans)), len(levels) - 1)
                    selected = levels[idx]
                    probs = {str(l): 0.8 if l == selected else 0.1 for l in levels}
                elif isinstance(raw_ans, dict):
                    probs = {str(k): float(v) for k, v in raw_ans.items()}
                    selected = max(probs, key=probs.get) if probs else levels[0]
                else:
                    selected = levels[0]
                    probs = {str(l): 0.5 for l in levels}
                results[q_id] = DecisionScore(
                    selected_option=selected,
                    class_probability=probs.get(str(selected), 0.8),
                    empirical_accuracy=default_act_p,
                    probabilities=probs,
                    prediction_set=[str(selected)],
                    tokens_saved_estimate=_estimate_tokens_saved(state, q_spec.get("instructions", ""), levels),
                )
            else:  # choice
                options = q_spec.get("criteria", q_spec.get("options", []))
                alpha = q_spec.get("alpha", self.conformal_alpha)
                if isinstance(raw_ans, dict):
                    probs = {str(k): float(v) for k, v in raw_ans.items()}
                    selected = max(probs, key=probs.get)
                else:
                    opt_list = list(options.keys()) if isinstance(options, dict) else list(options)
                    selected = opt_list[0] if opt_list else "UNKNOWN"
                    probs = {selected: 0.85}
                c_prob = probs.get(selected, 0.85)
                pred_set = compute_conformal_prediction_set(probs, alpha=alpha)
                results[q_id] = DecisionScore(
                    selected_option=selected,
                    class_probability=c_prob,
                    empirical_accuracy=default_act_p,
                    probabilities=probs,
                    prediction_set=pred_set,
                    tokens_saved_estimate=_estimate_tokens_saved(state, q_spec.get("instructions", ""), options),
                )

        return results


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

        # If model exposes a bespoke .predict or .score method (e.g. wrapper), delegate directly
        if hasattr(model, "predict"):
            res = model.predict(state, {question: {"type": "choice", "criteria": opt_keys}})
            ans = res.get("answers", {}).get(question, {})
            if isinstance(ans, dict):
                return {str(k): float(v) for k, v in ans.items()}

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

            if hasattr(outputs, "logits"):
                logits = outputs.logits.squeeze(-1)
            else:
                # Use pooled representation norm / similarity as scoring proxy
                hidden = outputs.last_hidden_state[:, 0, :]
                logits = hidden.norm(dim=-1)

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

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate multiple questions against state sequentially or in threads.

        Parameters
        ----------
        state : str or dict or list
            State payload.
        questions : dict of str to dict
            Question definitions.

        Returns
        -------
        dict of str to (DecisionScore or DecisionNoulResult)
            Results for all questions.
        """
        results: dict[str, DecisionScore | DecisionNoulResult] = {}
        for key, q_spec in questions.items():
            q_type = q_spec.get("type", "choice")
            q_text = q_spec.get("instructions", q_spec.get("question", ""))
            if q_type == "noul":
                results[key] = await self.evaluate_noul(state, q_text)
            elif q_type == "score":
                levels = q_spec.get("criteria", q_spec.get("levels", [1, 2, 3]))
                results[key] = await self.evaluate_score(state, q_text, levels)
            else:
                opts = q_spec.get("criteria", q_spec.get("options", []))
                alpha = q_spec.get("alpha")
                results[key] = await self.evaluate_choice(state, q_text, opts, alpha=alpha)
        return results

import platform

class AutoDecisionEngine:
    """Decision Engine that automatically selects the best available backend.
    
    It prefers LayaDecisionEngine on Apple Silicon if laya-mlx is installed,
    otherwise it falls back to TransformersDecisionEngine.
    """
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._inner: Any = None
        is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
        laya_available = False
        
        if is_apple_silicon:
            try:
                import laya_mlx  # noqa: F401
                laya_available = True
            except ImportError:
                pass
                
        if laya_available:
            self._inner = LayaDecisionEngine(*args, **kwargs)
        else:
            self._inner = TransformersDecisionEngine(*args, **kwargs)
            
    async def evaluate_noul(self, state: str | dict[str, Any] | list[Any], question: str) -> DecisionNoulResult:
        return await self._inner.evaluate_noul(state, question)
        
    async def evaluate_choice(
        self, state: str | dict[str, Any] | list[Any], question: str, options: list[str] | dict[str, str], alpha: float | None = None
    ) -> DecisionScore:
        return await self._inner.evaluate_choice(state, question, options, alpha)
        
    async def evaluate_score(self, state: str | dict[str, Any] | list[Any], question: str, levels: list[int | str]) -> DecisionScore:
        return await self._inner.evaluate_score(state, question, levels)
