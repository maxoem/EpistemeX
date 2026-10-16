"""Domain-specific theory projectors (Phi_spec).

Projects empirical clusters (intended applications I) into bespoke theoretical
parametric spaces (M_p) according to structuralist theory-element definitions.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from episteme_pipeline.llm.structured import StructuredLLM, ensure_structured_llm
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    ClusterProjectionOutput,
    EmpiricalCluster,
    TheoryElementDefinition,
)
from episteme_pipeline.prompts.default_prompts import CLUSTER_PROJECTION_DIRECT_PROMPT
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.fingerprint import Fingerprintable

logger = logging.getLogger(__name__)


class TheoryProjector(Fingerprintable, ABC):
    """Abstract base protocol for theory-specific projectors (Phi_spec)."""

    @abstractmethod
    def project(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Project an empirical cluster into candidate theoretical parameters.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster (intended application).
        theory : TheoryElementDefinition
            Theory-element specifying M_pp and M_p signatures.

        Returns
        -------
        dict[str, Any]
            Dictionary of parameter name to postulated value.
        """
        ...

    async def aproject(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Asynchronously project an empirical cluster into candidate theoretical parameters.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster.
        theory : TheoryElementDefinition
            Theory-element specifying M_pp and M_p signatures.

        Returns
        -------
        dict[str, Any]
            Dictionary of parameter name to postulated value.
        """
        return self.project(cluster, theory)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint dictionary for caching.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        return {"type": self.__class__.__name__}


def extract_matching_measurements(
    cluster: EmpiricalCluster,
    param_name: str,
    required_dimensions: list[str],
    param_index: int | None = None,
) -> list[float]:
    """Extract numeric measurements matching a theoretical parameter.

    Bridges empirical observation dimensions ($M_{pp}$) to theoretical parameter
    spaces ($M_p$) according to the structuralist metatheory of science (Stegmüller, 1976;
    Balzer et al., 1987; ADR 0015). Matches measurements using direct token overlap,
    semantic alignment with specified required dimensions, or ordinal positional alignment
    when dimension names and parameter names are disjoint.

    Parameters
    ----------
    cluster : EmpiricalCluster
        Target empirical cluster containing observation units.
    param_name : str
        Target theoretical parameter name (e.g. 'DopamineDepletion').
    required_dimensions : list[str]
        Non-theoretical observation dimensions specified by the theory element.
    param_index : int | None, optional
        Ordinal index of the parameter in the theory element's parameter list, by default None.

    Returns
    -------
    list of float
        Numeric values of measurements that align with the parameter.
    """
    p_clean = param_name.lower().replace("_", "")
    tokens = [t.lower() for t in re.findall(r"[A-Z]?[a-z]+|[a-z]+", param_name) if len(t) > 3]
    matching_req_dims = [
        rd.lower().replace("_", "")
        for rd in required_dimensions
        if any(t in rd.lower().replace("_", "") for t in tokens)
        or rd.lower().replace("_", "") in p_clean
        or p_clean in rd.lower().replace("_", "")
    ]
    matched_vals: list[float] = []

    for obs in cluster.observations:
        for m in obs.measurements:
            m_clean = m.dimension.lower().replace("_", "")
            # 1. Direct match against parameter name or sub-tokens
            if m_clean in p_clean or p_clean in m_clean or any(t in m_clean for t in tokens) or matching_req_dims and any(rd in m_clean or m_clean in rd for rd in matching_req_dims):
                if isinstance(m.value, (int, float)):
                    matched_vals.append(float(m.value))
            # 3. Ordinal positional fallback when parameter and dimension vocabularies are disjoint
            elif not matching_req_dims and param_index is not None and param_index < len(required_dimensions):
                req_dim = required_dimensions[param_index].lower().replace("_", "")
                if req_dim in m_clean or m_clean in req_dim:
                    if isinstance(m.value, (int, float)):
                        matched_vals.append(float(m.value))

    return matched_vals


class GenericTheoryProjector(TheoryProjector):
    """Domain-agnostic fallback projector for dynamically registered theories.

    Parameters
    ----------
    fallback_default : float, optional
        Default parameter value when no observation data matches, by default 0.5.
    """

    def __init__(self, fallback_default: float = 0.5) -> None:
        self.fallback_default = fallback_default

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint dictionary for caching.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        return {
            "type": self.__class__.__name__,
            "fallback_default": self.fallback_default,
        }

    def project(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Project by matching parameter names to measurements or textual tokens.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster (intended application I).
        theory : TheoryElementDefinition
            Theory-element specifying non-theoretical dimensions M_pp and parameters M_p.

        Returns
        -------
        dict[str, Any]
            Dictionary of parameter names to postulated numeric values.
        """
        params: dict[str, Any] = {}
        for i, param_name in enumerate(theory.parameter_names):
            matched_vals = extract_matching_measurements(
                cluster, param_name, theory.required_dimensions, param_index=i
            )

            # Match parameter tokens and potential numeric indicators in text if no measurements found
            if not matched_vals:
                tokens = [t.lower() for t in re.findall(r"[A-Z]?[a-z]+|[a-z]+", param_name) if len(t) > 3]
                for obs in cluster.observations:
                    obs_text = obs.text.lower()
                    for token in tokens:
                        if token in obs_text:
                            match = re.search(
                                rf"(\d+(?:\.\d+)?)%?\s*(?:[a-z]+\s*){{0,3}}{token}|{token}(?:\s*[a-z]+){{0,3}}\s*(\d+(?:\.\d+)?)%?",
                                obs_text,
                            )
                            if match:
                                num_str = match.group(1) or match.group(2)
                                if num_str:
                                    val = float(num_str)
                                    matched_vals.append(val / 100.0 if val > 1.0 else val)
                            elif not matched_vals:
                                matched_vals.append(0.7)

            if matched_vals:
                params[param_name] = round(sum(matched_vals) / len(matched_vals), 3)
            else:
                params[param_name] = self.fallback_default

        return params


class LLMTheoryProjector(TheoryProjector):
    """LLM-backed projector estimating empirical dimensions and theoretical parameters.

    Prompts the LLM to project an empirical cluster through the specific formal lens
    of a Theory-Element, extracting observed dimension values and postulating
    candidate latent parameter values (M_p).

    Parameters
    ----------
    llm : Any
        Underlying LLM facade or StructuredLLM instance.
    prompts : StructuredPromptBundle | str | None, optional
        Custom prompt bundle or template string, by default None.
    strategy : Any, optional
        Decoding strategy for structured prediction, by default "direct_constrained".
    """

    def __init__(
        self,
        llm: Any,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = "direct_constrained",
    ) -> None:
        self.llm: StructuredLLM = ensure_structured_llm(llm)
        self.prompts = prompts or CLUSTER_PROJECTION_DIRECT_PROMPT
        self.strategy = strategy
        self._fallback = GenericTheoryProjector()

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint dictionary for caching.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        llm_fp = self.llm.fingerprint() if isinstance(self.llm, Fingerprintable) else str(self.llm)
        prompts_fp = self.prompts.fingerprint() if isinstance(self.prompts, Fingerprintable) else str(self.prompts)
        return {
            "type": self.__class__.__name__,
            "strategy": str(self.strategy),
            "llm": llm_fp,
            "prompts": prompts_fp,
        }

    async def aproject(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Asynchronously project empirical cluster into theoretical parameters via LLM.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster.
        theory : TheoryElementDefinition
            Theory-element definition specifying M_pp and M_p.

        Returns
        -------
        dict[str, Any]
            Dictionary of parameter name to postulated value.
        """
        # Fast path: check if cluster has exact structured measurements matching all parameters
        fast = self._try_measurement_fast_path(cluster, theory)
        if fast and len(fast) == len(theory.parameter_names):
            return fast

        obs_lines = []
        for o in cluster.observations:
            dims = [f"{m.dimension}={m.value} {m.unit}" for m in o.measurements]
            dim_str = f" [measurements: {', '.join(dims)}]" if dims else ""
            obs_lines.append(f"- [{o.id}] ({o.component_type}) {o.text}{dim_str}")
        obs_str = "\n".join(obs_lines) if obs_lines else "No observations."

        laws_str = "; ".join([f"{law.law_id}: {law.description}" for law in theory.laws]) or "None"

        try:
            raw: ClusterProjectionOutput = await self.llm.predict_structured(
                ClusterProjectionOutput,
                self.prompts,
                strategy=self.strategy,
                theory_name=theory.name,
                required_dimensions=", ".join(theory.required_dimensions) or "None specified",
                parameter_names=", ".join(theory.parameter_names) or "None specified",
                theory_laws=laws_str,
                cluster_observations=obs_str,
            )
            result = dict(raw.projected_parameters)
            for p in theory.parameter_names:
                if p not in result:
                    result[p] = 0.5
            return result
        except Exception as err:
            logger.warning("LLMTheoryProjector failed structured projection: %s. Using fallback.", err)
            return self._fallback.project(cluster, theory)

    def project(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Synchronously project cluster using fast-path or fallback.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster.
        theory : TheoryElementDefinition
            Theory-element definition.

        Returns
        -------
        dict[str, Any]
            Postulated parameters dictionary.
        """
        fast = self._try_measurement_fast_path(cluster, theory)
        if fast:
            return fast
        return self._fallback.project(cluster, theory)

    def _try_measurement_fast_path(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Extract parameters if structured measurements directly match.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Empirical cluster containing candidate measurements.
        theory : TheoryElementDefinition
            Theory-element definition specifying parameters and required dimensions.

        Returns
        -------
        dict[str, Any]
            Extracted parameters dictionary, or empty if none matched.
        """
        params: dict[str, Any] = {}
        for i, param in enumerate(theory.parameter_names):
            vals = extract_matching_measurements(
                cluster, param, theory.required_dimensions, param_index=i
            )
            if vals:
                params[param] = round(sum(vals) / len(vals), 3)
        return params


class CompositeTheoryProjector(TheoryProjector):
    """Router that delegates to specialized domain projectors or dynamic LLM projector.

    Parameters
    ----------
    default_projector : TheoryProjector | None, optional
        Fallback projector to use when no specialized projector matches, by default None.
    custom_projectors : dict[str, TheoryProjector] | None, optional
        Pre-registered mapping of theory_id -> TheoryProjector.
    """

    def __init__(
        self,
        default_projector: TheoryProjector | None = None,
        custom_projectors: dict[str, TheoryProjector] | None = None,
    ) -> None:
        self._projectors: dict[str, TheoryProjector] = dict(custom_projectors or {})
        self._default: TheoryProjector = default_projector or GenericTheoryProjector()

    def register(self, theory_id: str, projector: TheoryProjector) -> None:
        """Register a custom domain projector for a theory id.

        Parameters
        ----------
        theory_id : str
            Unique identifier of the target theory element.
        projector : TheoryProjector
            Specialized domain projector to delegate to.
        """
        self._projectors[theory_id] = projector

    async def aproject(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Asynchronously project cluster using registered or default projector.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster.
        theory : TheoryElementDefinition
            Theory-element schema definition.

        Returns
        -------
        dict[str, Any]
            Postulated parameter values.
        """
        projector = self._projectors.get(theory.theory_id, self._default)
        return await projector.aproject(cluster, theory)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint dictionary for caching.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        return {
            "type": self.__class__.__name__,
            "default": self._default.fingerprint(),
            "projectors": {
                k: p.fingerprint() for k, p in sorted(self._projectors.items())
            },
        }

    def project(
        self, cluster: EmpiricalCluster, theory: TheoryElementDefinition
    ) -> dict[str, Any]:
        """Synchronously project cluster using registered or default projector.

        Parameters
        ----------
        cluster : EmpiricalCluster
            Target empirical cluster.
        theory : TheoryElementDefinition
            Theory-element schema definition.

        Returns
        -------
        dict[str, Any]
            Postulated parameter values.
        """
        projector = self._projectors.get(theory.theory_id, self._default)
        return projector.project(cluster, theory)
