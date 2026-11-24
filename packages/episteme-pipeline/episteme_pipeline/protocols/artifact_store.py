from abc import ABC, abstractmethod

from episteme_pipeline.artifacts.models import ArtifactEnvelope, ArtifactPayload


class ArtifactStoreProtocol(ABC):
    """Durable storage for run-scoped artifacts, independent of graph projection."""

    @abstractmethod
    async def write_artifact(
        self, artifact: ArtifactEnvelope[ArtifactPayload]
    ) -> None: ...

    @abstractmethod
    async def get_artifact(
        self, artifact_id: str
    ) -> ArtifactEnvelope[ArtifactPayload] | None: ...

    @abstractmethod
    async def list_run_artifacts(
        self, run_id: str
    ) -> list[ArtifactEnvelope[ArtifactPayload]]: ...
