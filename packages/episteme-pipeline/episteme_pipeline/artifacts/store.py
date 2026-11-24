"""JSON-based artifact store for durable, independent artifact persistence."""

from __future__ import annotations

import json
from pathlib import Path

from episteme_pipeline.artifacts.models import ArtifactEnvelope, ArtifactPayload
from episteme_pipeline.protocols.artifact_store import ArtifactStoreProtocol


class JsonArtifactStore(ArtifactStoreProtocol):
    """
    File-based artifact store that persists artifacts as JSON files.

    Directory structure:
        artifacts_dir/
            {run_id}/
                {artifact_id}.json
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        # artifact_id -> path, filled as artifacts are written or looked up, so a
        # repeat lookup does not re-scan every run directory (O-16).
        self._path_index: dict[str, Path] = {}

    async def write_artifact(self, artifact: ArtifactEnvelope[ArtifactPayload]) -> None:
        """Write artifact to JSON file."""
        run_dir = self.root_dir / artifact.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        path = run_dir / f"{artifact.artifact_id}.json"
        path.write_text(
            json.dumps(artifact.model_dump(mode="json", by_alias=True), indent=2),
            encoding="utf-8",
        )
        self._path_index[artifact.artifact_id] = path

    async def get_artifact(
        self, artifact_id: str
    ) -> ArtifactEnvelope[ArtifactPayload] | None:
        """Read an artifact by id, searching every run directory if need be.

        Artifacts are stored under ``{run_id}/{artifact_id}.json`` and the run id
        is not recoverable from the artifact id, so the first lookup for an id
        written by another process has to scan. The resolved path is cached.
        """
        cached = self._path_index.get(artifact_id)
        if cached is not None and cached.exists():
            return ArtifactEnvelope.model_validate_json(
                cached.read_text(encoding="utf-8")
            )

        for run_dir in self.root_dir.iterdir():
            if not run_dir.is_dir():
                continue
            path = run_dir / f"{artifact_id}.json"
            if path.exists():
                self._path_index[artifact_id] = path
                return ArtifactEnvelope.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
        return None

    async def list_run_artifacts(
        self, run_id: str
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """List all artifacts for a given run."""
        run_dir = self.root_dir / run_id
        if not run_dir.exists():
            return []

        artifacts = []
        for path in run_dir.glob("*.json"):
            try:
                artifact = ArtifactEnvelope.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                artifacts.append(artifact)
            except Exception:  # noqa: BLE001, S112 baseline
                # Skip corrupted files
                continue
        return artifacts

    async def list_phase_artifacts(
        self, run_id: str, phase_name: str
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        """List all artifacts for a given run and phase."""
        all_artifacts = await self.list_run_artifacts(run_id)
        return [a for a in all_artifacts if a.phase_name == phase_name]


class InMemoryArtifactStore(ArtifactStoreProtocol):
    """In-memory artifact store for testing."""

    def __init__(self) -> None:
        self._store: dict[str, ArtifactEnvelope[ArtifactPayload]] = {}

    async def write_artifact(self, artifact: ArtifactEnvelope[ArtifactPayload]) -> None:
        self._store[artifact.artifact_id] = artifact

    async def get_artifact(
        self, artifact_id: str
    ) -> ArtifactEnvelope[ArtifactPayload] | None:
        return self._store.get(artifact_id)

    async def list_run_artifacts(
        self, run_id: str
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        return [a for a in self._store.values() if a.run_id == run_id]

    async def list_phase_artifacts(
        self, run_id: str, phase_name: str
    ) -> list[ArtifactEnvelope[ArtifactPayload]]:
        return [
            a
            for a in self._store.values()
            if a.run_id == run_id and a.phase_name == phase_name
        ]
