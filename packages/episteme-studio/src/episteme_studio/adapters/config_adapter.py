"""Configuration adapter wrapping PipelineConfig serialization and phase fingerprinting."""

from __future__ import annotations

import copy
from typing import Any
from pydantic import ValidationError

from episteme_studio.domain.errors import InvalidConfigPatchError
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.runs.fingerprints import fingerprint_phase_config

PHASE_INDEX_TO_NAME: dict[int, str] = {
    1: "Phase 1: Data Foundation",
    2: "Phase 2: Entity & Local Relation Discovery",
    3: "Phase 3: Global Relation Extraction",
    4: "Phase 3b: Latent Graph Consolidation",
    5: "Phase 4: Entity Maturation",
    6: "Phase 4: Argument Mining",
    7: "Phase 5: Inter-Document Argument Web",
    8: "Phase 6: Epistemic Consolidation",
}

PHASE_INDEX_TO_ATTR: dict[int, str] = {
    1: "phase1",
    2: "phase2",
    3: "phase3",
    4: "phase3b",
    5: "phase4_maturation",
    6: "phase4",
    7: "phase5",
    8: "phase6",
}

DEFAULT_PHASE_ARTIFACT_ESTIMATES: dict[int, int] = {
    1: 5,
    2: 14,
    3: 8,
    4: 6,
    5: 4,
    6: 3,
    7: 2,
    8: 1,
}


class ConfigAdapter:
    """Bridges GLP Studio domain services to pipeline configuration models."""

    @staticmethod
    def get_default_config() -> PipelineConfig:
        """Create a default PipelineConfig instance.

        Returns
        -------
        PipelineConfig
            Default pipeline configuration object.
        """
        return PipelineConfig()

    @staticmethod
    def get_config_from_env(**overrides: Any) -> PipelineConfig:
        """Create a PipelineConfig resolved from environment and overrides.

        Parameters
        ----------
        overrides : Any
            Keyword overrides to apply on top of environment values.

        Returns
        -------
        PipelineConfig
            Resolved pipeline configuration.
        """
        return PipelineConfig.from_env(**overrides)

    @staticmethod
    def compute_phase_fingerprints(config: PipelineConfig) -> dict[int, str]:
        """Compute configuration fingerprints for all sequential phases.

        Parameters
        ----------
        config : PipelineConfig
            Pipeline configuration instance to fingerprint.

        Returns
        -------
        dict of int to str
            Mapping from phase ordinal (1-8) to SHA-256 fingerprint string.
        """
        fingerprints: dict[int, str] = {}
        for ordinal, attr in PHASE_INDEX_TO_ATTR.items():
            sub_config = getattr(config, attr, None)
            if sub_config is not None:
                fingerprints[ordinal] = fingerprint_phase_config(sub_config)
            else:
                fingerprints[ordinal] = ""
        return fingerprints

    @staticmethod
    def apply_patch(
        config: PipelineConfig,
        patch: dict[str, Any],
    ) -> PipelineConfig:
        """Apply dot-notation key overrides to a PipelineConfig instance.

        Parameters
        ----------
        config : PipelineConfig
            Base configuration instance.
        patch : dict of str to Any
            Dictionary of dot-delimited path updates.

        Returns
        -------
        PipelineConfig
            New PipelineConfig instance with validated updates applied.

        Raises
        ------
        InvalidConfigPatchError
            If a path is nonexistent or cannot be validated against schema models.
        """
        raw_dict = config.model_dump(mode="python")

        for key_path, new_value in patch.items():
            parts = key_path.split(".")
            target: Any = raw_dict
            for i, part in enumerate(parts[:-1]):
                if not isinstance(target, dict) or part not in target:
                    raise InvalidConfigPatchError(
                        f"Unknown configuration path '{key_path}' (invalid segment '{part}')."
                    )
                if part == "decision_engine" and target.get(part) is None:
                    target[part] = {}
                elif part == "phase_gates" and target.get(part) is None:
                    target[part] = {}
                elif part == "modal_resolver" and target.get(part) is None:
                    target[part] = {}
                target = target[part]

            leaf = parts[-1]
            if not isinstance(target, dict) or (
                leaf not in target
                and "decision_engine" not in key_path
                and "modal_resolver" not in key_path
            ):
                raise InvalidConfigPatchError(
                    f"Unknown configuration path '{key_path}' (unknown property '{leaf}')."
                )
            target[leaf] = new_value

        try:
            return PipelineConfig(**raw_dict)
        except ValidationError as err:
            raise InvalidConfigPatchError(
                f"Configuration patch validation failed: {err}"
            ) from err

    @staticmethod
    def flatten_dict(
        d: dict[str, Any],
        prefix: str = "",
    ) -> dict[str, Any]:
        """Flatten a nested dictionary into dot-separated paths.

        Parameters
        ----------
        d : dict of str to Any
            Nested dictionary.
        prefix : str, default ""
            Parent key prefix.

        Returns
        -------
        dict of str to Any
            Flattened dot-path dictionary.
        """
        result: dict[str, Any] = {}
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if k == "graph_schema" and isinstance(v, dict):
                # Flatten first level of graph_schema (e.g. graph_schema.node_types, graph_schema.node_definitions)
                # while keeping inner mapping dictionaries intact
                result[full_key] = v
                for schema_k, schema_v in v.items():
                    result[f"{full_key}.{schema_k}"] = schema_v
            elif isinstance(v, dict):
                result.update(ConfigAdapter.flatten_dict(v, prefix=full_key))
            else:
                result[full_key] = v
        return result
