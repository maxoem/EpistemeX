"""Propositional modal strength resolvers for theoretical atoms.

Provides symbolic (structuralist), empirical (System 1 DecisionEngine), and
neuro-symbolic hybrid implementations of the ``ModalStrengthResolver`` protocol.

Grounding:
- Toulmin (1958): Modal Qualifier Q on scientific propositions.
- Schurz (2014): Structuralist Scope Types (Allsatz, Existenzsatz) and Epistemic Status (Analytisch vs Synthetisch).
- Episteme D-QBAF: Decoupled prior base score tau_0(a) = M(phi_a).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from episteme_pipeline.contracts.domain import EpistemicStatus, ScopeType, TheoryAtom
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import ModalStrengthResolved
from episteme_pipeline.protocols.decision import DecisionEngine, DecisionScore

if TYPE_CHECKING:
    from episteme_pipeline.config import ModalResolverConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModalSyntaxProfile:
    """Evaluated structuralist modal profile for a theoretical atom.

    Parameters
    ----------
    score : float
        Deterministic authorial modal certainty M(phi) in [0.0, 1.0].
    bounds : tuple of (float, float)
        Admissible certainty interval [M_min, M_max] for guardrail clipping.
    """

    score: float
    bounds: tuple[float, float]


class StructuralistModalResolver:
    """Symbolic modal strength resolver grounded in Schurz's structuralist philosophy.

    Evaluates the authorial propositional modality M(phi) deterministically from
    structuralist syntax attributes (ScopeType, EpistemicStatus, ComponentType).

    Parameters
    ----------
    default_base_score : float, default 0.60
        Fallback modal certainty when no structuralist dimensions match.
    """

    def __init__(self, default_base_score: float = 0.60) -> None:
        self.default_base_score = default_base_score

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic structuralist modal resolver configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing class identifier and default base score.
        """
        return {
            "class": self.__class__.__name__,
            "default_base_score": self.default_base_score,
        }

    def _classify_component(self, comp: str) -> str:
        """Classify component type string into coarse epistemological category.

        Parameters
        ----------
        comp : str
            Sanitized component type string.

        Returns
        -------
        str
            Category: 'axiomatic', 'empirical', 'theoretical', 'speculative', or 'unknown'.
        """
        if any(k in comp for k in ("AXIOM", "LAW", "DEFINITION")):
            return "axiomatic"
        if any(k in comp for k in ("OBSERVATION", "EMPIRICAL")):
            return "empirical"
        if "THEORETICAL" in comp or "HYPOTHESIS" in comp:
            return "theoretical"
        if any(k in comp for k in ("CONJECTURE", "SPECULATION")):
            return "speculative"
        return "unknown"

    def _extract_syntax(
        self, atom: TheoryAtom
    ) -> tuple[ScopeType | None, str, EpistemicStatus | None]:
        """Extract and normalize structuralist syntax attributes from an atom.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.

        Returns
        -------
        tuple of (ScopeType or None, str, EpistemicStatus or None)
            Canonical scope enum, component category, and epistemic status enum.
        """
        comp_raw = (atom.component_type or "").upper().replace(" ", "_").replace("-", "_")
        return (
            ScopeType.from_str(atom.scope_type),
            self._classify_component(comp_raw),
            EpistemicStatus.from_str(atom.epistemic_status),
        )

    def evaluate_syntax_profile(self, atom: TheoryAtom) -> ModalSyntaxProfile:
        """Derive deterministic modal score and guardrail interval from atom syntax.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.

        Returns
        -------
        ModalSyntaxProfile
            Evaluated score and guardrail interval bounds.
        """
        scope, comp_kind, status = self._extract_syntax(atom)

        # Unified pattern matching switch across ScopeType, ComponentKind, and EpistemicStatus
        match (scope, comp_kind, status):
            # 1. Structuralist ScopeType hierarchy (Schurz 2014)
            case (ScopeType.ESSENTIELLER_ALLSATZ, _, EpistemicStatus.ANALYTISCH):
                return ModalSyntaxProfile(score=1.00, bounds=(0.85, 1.00))
            case (ScopeType.ESSENTIELLER_ALLSATZ, _, _):
                return ModalSyntaxProfile(score=0.90, bounds=(0.75, 1.00))
            case (ScopeType.LOKALISIERTER_ALLSATZ, _, _):
                return ModalSyntaxProfile(score=0.85, bounds=(0.70, 0.95))
            case (ScopeType.LOKALISIERTER_EXISTENZSATZ, _, _):
                return ModalSyntaxProfile(score=0.85, bounds=(0.70, 0.95))
            case (ScopeType.STATISTISCHER_ALLSATZ, _, _):
                return ModalSyntaxProfile(score=0.75, bounds=(0.55, 0.85))
            case (ScopeType.EXISTENZSATZ, _, _):
                return ModalSyntaxProfile(score=0.55, bounds=(0.35, 0.70))

            # 2. ComponentType and EpistemicStatus fallback
            case (_, "axiomatic", _):
                return ModalSyntaxProfile(score=1.00, bounds=(0.85, 1.00))
            case (_, "empirical", _):
                return ModalSyntaxProfile(score=0.85, bounds=(0.70, 0.95))
            case (_, "theoretical", EpistemicStatus.ANALYTISCH):
                return ModalSyntaxProfile(score=0.75, bounds=(0.60, 0.85))
            case (_, "theoretical", _):
                return ModalSyntaxProfile(score=0.60, bounds=(0.40, 0.80))
            case (_, "speculative", _):
                return ModalSyntaxProfile(score=0.35, bounds=(0.10, 0.50))

            # 3. Default fallback
            case _:
                return ModalSyntaxProfile(score=self.default_base_score, bounds=(0.30, 0.85))

    def get_syntax_bounds(self, atom: TheoryAtom) -> tuple[float, float]:
        """Compute admissible modal certainty interval [M_min, M_max] for guardrail clipping.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.

        Returns
        -------
        tuple of (float, float)
            Lower and upper bounds for authorial propositional certainty in [0.0, 1.0].
        """
        return self.evaluate_syntax_profile(atom).bounds

    def resolve_modality_sync(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Synchronously derive deterministic modal certainty from structuralist syntax.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.
        context : str or None, optional
            Ignored for purely symbolic syntactic evaluation.

        Returns
        -------
        float
            Propositional modal strength M(phi) in [0.0, 1.0].
        """
        return self.evaluate_syntax_profile(atom).score

    async def resolve_modality(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Asynchronously derive deterministic modal certainty (delegates to sync).

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.
        context : str or None, optional
            Ignored for symbolic evaluation.

        Returns
        -------
        float
            Propositional modal strength M(phi) in [0.0, 1.0].
        """
        return self.resolve_modality_sync(atom, context)


class DecisionEngineModalResolver:
    """Empirical modal strength resolver backed by a System 1 DecisionEngine.

    Evaluates linguistic hedging, modal auxiliaries, and assertiveness directly
    on the claim and surrounding sentence context.

    Parameters
    ----------
    decision_engine : DecisionEngine
        System 1 calibrated decision engine.
    question_template : str, default "Assess the author's propositional certainty / modal qualification for this claim."
        Evaluative prompt question for the decision engine.
    levels : list of float, optional
        Ordinal certainty levels in [0.0, 1.0]. Defaults to [0.2, 0.4, 0.6, 0.8, 1.0].
    """

    def __init__(
        self,
        decision_engine: DecisionEngine,
        question_template: str = "Assess the author's propositional certainty / modal qualification for this claim.",
        levels: list[float] | None = None,
    ) -> None:
        from episteme_pipeline.prompts.models import StructuredPromptBundle

        self.decision_engine = decision_engine
        self.question_template = question_template
        self.levels = levels or [0.2, 0.4, 0.6, 0.8, 1.0]
        self.prompt_bundle = StructuredPromptBundle(
            direct_template=self.question_template,
            decision_template=self.question_template,
            decision_criteria={f"Level_{i}": f"Certainty {lvl:.2f}" for i, lvl in enumerate(self.levels)},
            name="modal_strength_resolution",
        )
        self._fallback_resolver = StructuralistModalResolver()

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic decision engine modal resolver configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing class identifier, question template, levels,
            and underlying decision engine fingerprint.
        """
        from episteme_pipeline.protocols.fingerprint import Fingerprintable

        eng_fp = (
            self.decision_engine.fingerprint()
            if isinstance(self.decision_engine, Fingerprintable)
            else {"class": self.decision_engine.__class__.__name__}
        )
        return {
            "class": self.__class__.__name__,
            "question_template": self.question_template,
            "levels": list(self.levels),
            "prompt_bundle": self.prompt_bundle.fingerprint(),
            "decision_engine": eng_fp,
        }

    async def resolve_modality(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Evaluate linguistic hedging via System 1 DecisionEngine.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.
        context : str or None, optional
            Surrounding context text.

        Returns
        -------
        float
            Calibrated expected propositional modal strength M(phi) in [0.0, 1.0].
        """
        claim_text = atom.text or ""
        state_str = f"Claim: {claim_text}\nContext:\n{context or claim_text}"

        level_options = {f"Level_{i}": f"Certainty {lvl:.2f}" for i, lvl in enumerate(self.levels)}
        try:
            score: DecisionScore = await self.decision_engine.evaluate_choice(
                state=state_str,
                question=self.question_template,
                options=level_options,
            )

            # Compute expected value over probability distribution if available
            probs = score.probabilities or {}
            if probs:
                expected_m = 0.0
                total_p = 0.0
                for i, lvl in enumerate(self.levels):
                    opt_key = f"Level_{i}"
                    p = probs.get(opt_key, 0.0)
                    expected_m += lvl * p
                    total_p += p
                if total_p > 0:
                    return float(max(0.0, min(1.0, expected_m / total_p)))

            # Fall back to selected option index
            sel = str(score.selected_option)
            for i, lvl in enumerate(self.levels):
                if f"Level_{i}" in sel:
                    return lvl

            return float(score.class_probability) if score.class_probability is not None else 0.60
        except Exception as e:
            logger.warning("DecisionEngineModalResolver failed (%s); falling back to syntax", e)
            return self._fallback_resolver.resolve_modality_sync(atom, context)

    def resolve_modality_sync(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Synchronous fallback delegating to structuralist syntax.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.
        context : str or None, optional
            Textual context.

        Returns
        -------
        float
            Fallback modal strength M(phi) in [0.0, 1.0].
        """
        return self._fallback_resolver.resolve_modality_sync(atom, context)


class HybridModalResolver:
    """Neuro-symbolic hybrid modal strength resolver.

    Harmonizes symbolic structuralist properties (ScopeType, EpistemicStatus) with
    calibrated linguistic assertiveness scoring from the System 1 DecisionEngine.

    Parameters
    ----------
    structural_resolver : StructuralistModalResolver or None, optional
        Symbolic resolver instance. If None, initialized with default settings.
    decision_resolver : DecisionEngineModalResolver or None, optional
        Empirical decision engine resolver. If None, runs in pure structuralist mode.
    mode : Literal["guardrail", "convex", "structural_only", "engine_only"], default "guardrail"
        Integration mode:
        - "guardrail": Clips decision engine score into structuralist syntax bounds.
        - "convex": Computes weighted average between structural prior and engine score.
        - "structural_only": Strictly evaluates structuralist syntax.
        - "engine_only": Strictly evaluates decision engine score.
    fusion_alpha : float, default 0.50
        Relative weight of structuralist syntax in convex fusion mode (in [0.0, 1.0]).
    """

    def __init__(
        self,
        structural_resolver: StructuralistModalResolver | None = None,
        decision_resolver: DecisionEngineModalResolver | None = None,
        mode: Literal["guardrail", "convex", "structural_only", "engine_only"] = "guardrail",
        fusion_alpha: float = 0.50,
    ) -> None:
        self.structural_resolver = structural_resolver or StructuralistModalResolver()
        self.decision_resolver = decision_resolver
        self.mode = mode
        self.fusion_alpha = max(0.0, min(1.0, fusion_alpha))

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic hybrid modal resolver configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing mode, fusion alpha, and component resolver fingerprints.
        """
        from episteme_pipeline.protocols.fingerprint import Fingerprintable

        return {
            "class": self.__class__.__name__,
            "mode": self.mode,
            "fusion_alpha": self.fusion_alpha,
            "structural_resolver": (
                self.structural_resolver.fingerprint()
                if isinstance(self.structural_resolver, Fingerprintable)
                else {"class": self.structural_resolver.__class__.__name__}
            ),
            "decision_resolver": (
                self.decision_resolver.fingerprint()
                if isinstance(self.decision_resolver, Fingerprintable)
                else None
            ),
        }

    @classmethod
    def create(
        cls,
        config: ModalResolverConfig | dict[str, Any] | None = None,
        decision_engine: DecisionEngine | None = None,
        structural_resolver: StructuralistModalResolver | None = None,
        decision_resolver: DecisionEngineModalResolver | None = None,
    ) -> HybridModalResolver:
        """Construct a fully configured HybridModalResolver from config and dependencies.

        Parameters
        ----------
        config : ModalResolverConfig or dict or None, optional
            Modal resolver configuration. If None or empty, default settings are used.
        decision_engine : DecisionEngine or None, optional
            Calibrated System 1 decision engine. If provided and decision_resolver is None,
            constructs DecisionEngineModalResolver automatically.
        structural_resolver : StructuralistModalResolver or None, optional
            Custom structuralist resolver. If None, initialized using config.default_base_score.
        decision_resolver : DecisionEngineModalResolver or None, optional
            Custom decision resolver. If None and decision_engine is provided, constructed automatically.

        Returns
        -------
        HybridModalResolver
            Configured neuro-symbolic hybrid modal strength resolver.
        """
        from episteme_pipeline.config import ModalResolverConfig

        if isinstance(config, dict):
            cfg_dict = config.get("modal_resolver", config)
            cfg = ModalResolverConfig.model_validate(cfg_dict) if isinstance(cfg_dict, dict) else ModalResolverConfig()
        elif isinstance(config, ModalResolverConfig):
            cfg = config
        else:
            cfg = ModalResolverConfig()

        structural = structural_resolver or StructuralistModalResolver(
            default_base_score=cfg.default_base_score
        )
        dec_res = decision_resolver or (
            DecisionEngineModalResolver(decision_engine) if decision_engine is not None else None
        )
        mode = cfg.mode if dec_res is not None else "structural_only"

        return cls(
            structural_resolver=structural,
            decision_resolver=dec_res,
            mode=mode,
            fusion_alpha=cfg.fusion_alpha,
        )

    async def resolve_modality(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Resolve propositional modal strength with event emission and observability.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.
        context : str or None, optional
            Surrounding context text.

        Returns
        -------
        float
            Resolved modal certainty M(phi) in [0.0, 1.0].
        """
        syntax_profile = self.structural_resolver.evaluate_syntax_profile(atom)
        syntax_score = syntax_profile.score
        raw_engine_score: float | None = None
        clamped = False

        if self.mode == "structural_only" or self.decision_resolver is None:
            final_score = syntax_score
            resolver_type = "structural"
        elif self.mode == "engine_only":
            raw_engine_score = await self.decision_resolver.resolve_modality(atom, context)
            final_score = raw_engine_score
            resolver_type = "decision_engine"
        elif self.mode == "convex":
            raw_engine_score = await self.decision_resolver.resolve_modality(atom, context)
            final_score = (self.fusion_alpha * syntax_score) + ((1.0 - self.fusion_alpha) * raw_engine_score)
            resolver_type = "hybrid_convex"
        else:
            # Mode "guardrail": evaluate engine score and clamp within structural bounds
            raw_engine_score = await self.decision_resolver.resolve_modality(atom, context)
            bounds = syntax_profile.bounds
            clamped_score = max(bounds[0], min(bounds[1], raw_engine_score))
            clamped = clamped_score != raw_engine_score
            final_score = clamped_score
            resolver_type = "hybrid_guardrail"

        final_score = float(max(0.0, min(1.0, final_score)))

        # Emit observability domain event
        try:
            emitter = get_event_emitter()
            emitter.emit(
                ModalStrengthResolved(
                    atom_id=atom.id,
                    modal_strength=final_score,
                    resolver_type=resolver_type,
                    scope_type=atom.scope_type,
                    epistemic_status=atom.epistemic_status,
                    raw_engine_score=raw_engine_score,
                    clamped=clamped,
                )
            )
        except Exception as e:
            logger.debug("Failed to emit ModalStrengthResolved event: %s", e)

        logger.debug(
            "Resolved modality for atom %s (%s, %s): %.3f [mode=%s, raw=%.3f, clamped=%s]",
            atom.id,
            atom.scope_type,
            atom.epistemic_status,
            final_score,
            self.mode,
            raw_engine_score or 0.0,
            clamped,
        )
        return final_score

    def resolve_modality_sync(
        self,
        atom: TheoryAtom,
        context: str | None = None,
    ) -> float:
        """Synchronously resolve propositional modal strength via structuralist fallback.

        Parameters
        ----------
        atom : TheoryAtom
            Target theoretical atom.
        context : str or None, optional
            Surrounding context text.

        Returns
        -------
        float
            Resolved modal certainty M(phi) in [0.0, 1.0].
        """
        return self.structural_resolver.resolve_modality_sync(atom, context)
