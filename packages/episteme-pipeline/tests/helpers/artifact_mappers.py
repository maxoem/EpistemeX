"""Test artifact mapper helpers for testing artifact-native pipelines and projection."""

from __future__ import annotations

from collections import defaultdict

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_chunk_artifact,
    build_document_artifact,
    build_entity_mention_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.models import ArtifactEnvelope
from episteme_pipeline.contracts.phase_contracts import (
    Phase1Output,
    Phase2Output,
    Phase3Output,
    Phase4Output,
)


def map_phase1_output_to_artifacts(
    output: Phase1Output,
    *,
    run_id: str,
    phase_name: str = "Phase 1: Data Foundation",
) -> list[ArtifactEnvelope]:
    """Map Phase 1 output into artifact envelopes for tests."""
    artifacts: list[ArtifactEnvelope] = []
    for document in output.documents:
        artifacts.append(
            build_document_artifact(
                document, run_id=run_id, phase_name=phase_name, method="phase1.mapper"
            )
        )
    for chunk in output.chunks:
        artifacts.append(
            build_chunk_artifact(
                chunk, run_id=run_id, phase_name=phase_name, method="phase1.mapper"
            )
        )
    return artifacts


def map_phase2_output_to_artifacts(
    output: Phase2Output,
    *,
    run_id: str,
    phase_name: str = "Phase 2: Entity & Local Relation Discovery",
) -> list[ArtifactEnvelope]:
    """Map Phase 2 output into artifact envelopes for tests."""
    artifacts: list[ArtifactEnvelope] = []
    for entity in output.entities:
        mention_artifact_ids: list[str] = []
        for chunk_id in entity.source_chunk_ids:
            mention = build_entity_mention_artifact(
                entity, chunk_id, run_id=run_id, phase_name=phase_name, method="phase2.mapper"
            )
            mention_artifact_ids.append(mention.artifact_id)
            artifacts.append(mention)
        artifacts.append(
            build_linked_entity_artifact(
                entity, mention_artifact_ids, run_id=run_id, phase_name=phase_name, method="phase2.mapper"
            )
        )
    for triple in output.local_triples:
        artifacts.append(
            build_local_relation_artifact(
                triple, run_id=run_id, phase_name=phase_name, method="phase2.mapper"
            )
        )
    return artifacts


def map_phase3_output_to_artifacts(
    output: Phase3Output,
    *,
    run_id: str,
    phase_name: str = "Phase 3: Global Relation Extraction",
) -> list[ArtifactEnvelope]:
    """Map Phase 3 output into artifact envelopes for tests."""
    relation_dist: dict[str, int] = defaultdict(int)
    for triple in output.global_triples:
        relation_dist[triple.predicate] += 1
    return [
        build_global_relation_artifact(
            triple, relation_dist, run_id=run_id, phase_name=phase_name, method="phase3.mapper"
        )
        for triple in output.global_triples
    ]


def map_phase4_output_to_artifacts(
    output: Phase4Output,
    *,
    run_id: str,
    phase_name: str = "Phase 4: Argument Mining",
) -> list[ArtifactEnvelope]:
    """Map Phase 4 output into artifact envelopes for tests."""
    artifacts: list[ArtifactEnvelope] = []
    for component in output.theory_atoms:
        artifacts.append(
            build_argument_component_artifact(
                component, run_id=run_id, phase_name=phase_name, method="phase4.mapper"
            )
        )
    for relation in output.theory_relations:
        artifacts.append(
            build_argument_relation_artifact(
                relation, run_id=run_id, phase_name=phase_name, method="phase4.mapper"
            )
        )
    return artifacts
