"""Data source connection adapters for engine settings persistence."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Protocol

from episteme_studio.domain.engine import EngineSettings

logger = logging.getLogger(__name__)


class EngineSettingsStorage(Protocol):
    """Protocol defining the data source connection interface for engine settings."""

    async def load(self) -> EngineSettings:
        """Load the persisted engine settings, or return factory defaults if uninitialized.

        Returns
        -------
        EngineSettings
            Loaded or initialized engine settings.
        """
        ...

    async def save(self, settings: EngineSettings) -> None:
        """Persist engine settings to the underlying data source.

        Parameters
        ----------
        settings : EngineSettings
            Settings state to persist.
        """
        ...

    async def reset(self) -> EngineSettings:
        """Reset the data source to factory defaults.

        Returns
        -------
        EngineSettings
            Clean factory settings instance.
        """
        ...


class FileEngineSettingsStorage:
    """File-backed storage adapter persisting engine settings as a JSON document.

    Implements EngineSettingsStorage using safe atomic writes (temp file + replace).

    Parameters
    ----------
    storage_path : Path or str or None, optional
        Path to the JSON persistence file. Defaults to '.pipeline_engine_settings.json'.
    """

    def __init__(self, storage_path: Path | str | None = None) -> None:
        if storage_path is None:
            # Default to repo root or cwd
            self.storage_path = Path(".pipeline_engine_settings.json")
        else:
            self.storage_path = Path(storage_path)

    async def load(self) -> EngineSettings:
        """Load settings from the JSON file or instantiate default settings.

        Returns
        -------
        EngineSettings
            Deserialized engine settings or clean defaults.
        """
        if not self.storage_path.is_file():
            return EngineSettings()

        try:
            content = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return EngineSettings.model_validate(data)
        except Exception as exc:  # noqa: BLE001 baseline
            logger.warning(
                "Failed to deserialize engine settings from %s (%s). Falling back to defaults.",
                self.storage_path,
                exc,
            )
            return EngineSettings()

    async def save(self, settings: EngineSettings) -> None:
        """Safely persist settings via atomic file replacement.

        Parameters
        ----------
        settings : EngineSettings
            The settings model to write.
        """
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.storage_path.with_suffix(".tmp")

        try:
            json_str = settings.model_dump_json(indent=2)
            temp_path.write_text(json_str, encoding="utf-8")
            # Atomic replacement
            os.replace(temp_path, self.storage_path)
            logger.info("Persisted engine settings to %s", self.storage_path)
        except Exception as exc:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:  # noqa: BLE001, S110 baseline
                    pass
            logger.error(
                "Failed to persist engine settings to %s: %s", self.storage_path, exc
            )
            raise

    async def reset(self) -> EngineSettings:
        """Delete persisted custom file and return default settings.

        Returns
        -------
        EngineSettings
            Factory settings instance.
        """
        if self.storage_path.is_file():
            try:
                self.storage_path.unlink()
                logger.info("Deleted custom engine settings file %s", self.storage_path)
            except Exception as exc:  # noqa: BLE001 baseline
                logger.warning("Could not delete %s: %s", self.storage_path, exc)

        clean = EngineSettings()
        return clean
