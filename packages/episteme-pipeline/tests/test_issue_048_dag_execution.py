"""Deterministic tests for ISSUE-048: Topological DAG Execution, Sub-DAG Reuse & Invalidation.

Validates:
1. `Pipeline.__init__` raises explicit `TypeError`/`ValueError` on missing, invalid,
   or duplicate `phase_key`.
2. `RunManifest.phase_config_fingerprints` keys by semantic `phase_key` and supports
   custom `PhaseRunner.config_fingerprint()` implementations.
3. Appending/toggling `TheoreticalEnrichmentRunner` or custom post-processors reuses
   all completed upstream phases without triggering full-pipeline invalidation.
4. Independent branches in the phase DAG (e.g. Phase 5/6 vs Theoretical Enrichment)
   do not transitively invalidate each other.
5. `ArtifactHydrator` resolves phase config fingerprints by semantic `phase_key`
   rather than positional ordinal (`phase_4` vs `phase4`).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactEnvelope, ArtifactKind, ArtifactProvenance
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus


class StubMissingPhaseKey:
    name = "Phase Missing Key"

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


class StubEmptyPhaseKey:
    name = "Phase Empty Key"
    phase_key = "   "

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


class StubValidPhase(PhaseRunner[object]):
    def __init__(
        self,
        name: str,
        phase_key: str,
        reads_kinds: frozenset[ArtifactKind] = frozenset(),
        writes_kinds: frozenset[ArtifactKind] = frozenset(),
        custom_fp: str | None = None,
        dependencies: tuple[str, ...] | None = None,
    ) -> None:
        self.name = name
        self.phase_key = phase_key
        self.reads_kinds = reads_kinds
        self.writes_kinds = writes_kinds
        self._custom_fp = custom_fp
        self.dependencies = dependencies

    def config_fingerprint(self) -> str | None:
        return self._custom_fp

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


def test_pipeline_init_validates_phase_key_presence(tmp_path: Path, graph_store) -> None:
    """Verify Pipeline.__init__ raises TypeError/ValueError on missing or duplicate phase_key."""
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    # Missing phase_key attribute
    with pytest.raises(TypeError, match="must define a non-empty 'phase_key' attribute"):
        Pipeline(
            phases=[StubMissingPhaseKey()],  # type: ignore[list-item]
            config=cfg,
            graph_reader=graph_store,
            projection_graph=graph_store,
            checkpoint_store=graph_store,
        )

    # Empty phase_key
    with pytest.raises(TypeError, match="has invalid 'phase_key'"):
        Pipeline(
            phases=[StubEmptyPhaseKey()],  # type: ignore[list-item]
            config=cfg,
            graph_reader=graph_store,
            projection_graph=graph_store,
            checkpoint_store=graph_store,
        )

    # Duplicate phase_key
    p1 = StubValidPhase("Phase A", "phase_duplicate")
    p2 = StubValidPhase("Phase B", "phase_duplicate")
    with pytest.raises(ValueError, match="Duplicate phase_key 'phase_duplicate'"):
        Pipeline(
            phases=[p1, p2],
            config=cfg,
            graph_reader=graph_store,
            projection_graph=graph_store,
            checkpoint_store=graph_store,
        )


def test_manifest_phase_config_fingerprints_semantic_keying(tmp_path: Path, graph_store) -> None:
    """Verify phase_config_fingerprints keys by semantic phase_key and supports custom runner fingerprints."""
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    p1 = StubValidPhase("Phase 1", "phase1", writes_kinds=frozenset({ArtifactKind.DOCUMENT}))
    p_custom = StubValidPhase(
        "Custom Post-Processor",
        "custom_eval",
        reads_kinds=frozenset({ArtifactKind.DOCUMENT}),
        custom_fp="sha256-custom-config-v1",
    )

    pipeline = Pipeline(
        phases=[p1, p_custom],
        config=cfg,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    fps = pipeline._phase_config_fingerprints()
    assert fps["custom_eval"] == "sha256-custom-config-v1"
    assert "phase1" in fps

    manifest = pipeline._build_manifest(
        run_id="run-test",
        pipeline_input=pytest.importorskip("episteme_pipeline.contracts.phase_contracts").PipelineInput(
            source_paths=[], bib_paths=[]
        ),
    )
    assert manifest.phase_config_fingerprints["custom_eval"] == "sha256-custom-config-v1"
    assert "phase1" in manifest.phase_config_fingerprints
    assert set(manifest.phase_config_fingerprints.keys()) == {"phase1", "custom_eval"}


@pytest.mark.asyncio
async def test_appending_post_processor_reuses_all_upstream_phases(
    tmp_path: Path, graph_store
) -> None:
    """Verify appending a post-processor to a completed run reuses phases 1-4 without phase-list-changed."""
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    p1 = StubValidPhase("Phase 1", "phase1", writes_kinds=frozenset({ArtifactKind.DOCUMENT, ArtifactKind.CHUNK}))
    p2 = StubValidPhase(
        "Phase 2", "phase2",
        reads_kinds=frozenset({ArtifactKind.DOCUMENT, ArtifactKind.CHUNK}),
        writes_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
    )
    p3 = StubValidPhase(
        "Phase 3", "phase3",
        reads_kinds=frozenset({ArtifactKind.LINKED_ENTITY}),
        writes_kinds=frozenset({ArtifactKind.GLOBAL_RELATION}),
    )
    p4 = StubValidPhase(
        "Phase 4", "phase4",
        reads_kinds=frozenset({ArtifactKind.CHUNK, ArtifactKind.GLOBAL_RELATION}),
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
    )
    p_enrichment = StubValidPhase(
        "Theoretical Enrichment", "theoretical_enrichment",
        reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
        writes_kinds=frozenset({ArtifactKind.THEORETICAL_ENRICHMENT}),
    )

    # Initial pipeline with Phases 1-4
    pipeline_initial = Pipeline(
        phases=[p1, p2, p3, p4],
        config=cfg,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    prior = RunManifest(
        run_id="run-prior-completed",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input-fp",
        phase_config_fingerprints={
            "phase1": "fp_p1",
            "phase2": "fp_p2",
            "phase3": "fp_p3",
            "phase4": "fp_p4",
        },
        phase_records=[
            RunPhaseRecord(phase_name="Phase 1", ordinal=1, phase_key="phase1", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 2", ordinal=2, phase_key="phase2", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 3", ordinal=3, phase_key="phase3", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 4", ordinal=4, phase_key="phase4", status=RunStatus.COMPLETED),
        ],
    )
    pipeline_initial._manifest_store.write_manifest(prior)

    # New pipeline with Phases 1-4 + Theoretical Enrichment appended (5 phases)
    pipeline_with_enrichment = Pipeline(
        phases=[p1, p2, p3, p4, p_enrichment],
        config=cfg,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )
    pipeline_with_enrichment._phase_config_fingerprints = lambda: {
        "phase1": "fp_p1",
        "phase2": "fp_p2",
        "phase3": "fp_p3",
        "phase4": "fp_p4",
        "theoretical_enrichment": "fp_enrichment",
    }  # type: ignore[assignment]

    current_manifest = RunManifest(
        run_id="run-with-enrichment",
        status=RunStatus.RUNNING,
        input_fingerprint="same-input-fp",
        phase_config_fingerprints={
            "phase1": "fp_p1",
            "phase2": "fp_p2",
            "phase3": "fp_p3",
            "phase4": "fp_p4",
            "theoretical_enrichment": "fp_enrichment",
        },
    )

    decision = await pipeline_with_enrichment._choose_reuse_source(current_manifest)

    # Phases 1-4 MUST be reused; only Theoretical Enrichment (ordinal 5) executes!
    assert decision.reused_phase_ordinals == [1, 2, 3, 4]
    assert decision.invalidated_phase_ordinals == [5]
    assert decision.reason != "phase-list-changed"
    assert decision.reason == "phase-not-in-prior:Theoretical Enrichment"
    assert decision.resume_point.run_id == "run-prior-completed"


@pytest.mark.asyncio
async def test_independent_dag_branches_do_not_transitively_invalidate(
    tmp_path: Path, graph_store
) -> None:
    """Verify modifying Phase 5 (Fusion branch) does NOT invalidate Theoretical Enrichment branch."""
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    # Common trunk
    p4 = StubValidPhase(
        "Phase 4", "phase4",
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
    )
    # Branch A: Phase 5 (Fusion) -> Phase 6 (TheoryNet)
    p5 = StubValidPhase(
        "Phase 5", "phase5",
        reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
        writes_kinds=frozenset({ArtifactKind.FUSION_DECISION}),
    )
    p6 = StubValidPhase(
        "Phase 6", "phase6",
        reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION, ArtifactKind.FUSION_DECISION}),
        writes_kinds=frozenset({ArtifactKind.THEORY_ATOM}),
    )
    # Branch B: Theoretical Enrichment (orthogonal to Branch A)
    p_te = StubValidPhase(
        "Theoretical Enrichment", "theoretical_enrichment",
        reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
        writes_kinds=frozenset({ArtifactKind.THEORETICAL_ENRICHMENT}),
        dependencies=("phase4",),
    )

    pipeline = Pipeline(
        phases=[p4, p5, p6, p_te],
        config=cfg,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    # Prior run had all 4 phases completed
    prior = RunManifest(
        run_id="run-prior-branches",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input-fp",
        phase_config_fingerprints={
            "phase4": "same",
            "phase5": "old-fusion-config",
            "phase6": "same",
            "theoretical_enrichment": "same",
        },
        phase_records=[
            RunPhaseRecord(phase_name="Phase 4", ordinal=1, phase_key="phase4", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 5", ordinal=2, phase_key="phase5", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 6", ordinal=3, phase_key="phase6", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Theoretical Enrichment", ordinal=4, phase_key="theoretical_enrichment", status=RunStatus.COMPLETED),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)

    # Current run: only Phase 5 config changed!
    current = RunManifest(
        run_id="run-branch-a-changed",
        status=RunStatus.RUNNING,
        input_fingerprint="same-input-fp",
        phase_config_fingerprints={
            "phase4": "same",
            "phase5": "new-fusion-config",
            "phase6": "same",
            "theoretical_enrichment": "same",
        },
    )

    decision = await pipeline._choose_reuse_source(current)

    # Phase 4 is reused (trunk)
    # Phase 5 is invalidated (config changed)
    # Phase 6 is invalidated (depends on Phase 5 FUSION_DECISION)
    # Phase 4 and Theoretical Enrichment (Branch B) are REUSED!
    assert 1 in decision.reused_phase_ordinals  # Phase 4
    assert 4 in decision.reused_phase_ordinals  # Theoretical Enrichment
    assert 2 in decision.invalidated_phase_ordinals  # Phase 5
    assert 3 in decision.invalidated_phase_ordinals  # Phase 6


@pytest.mark.asyncio
async def test_modifying_branch_b_does_not_invalidate_branch_a(
    tmp_path: Path, graph_store
) -> None:
    """Verify modifying Theoretical Enrichment does NOT invalidate Phase 5 or Phase 6."""
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    p4 = StubValidPhase("Phase 4", "phase4", writes_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}))
    p5 = StubValidPhase("Phase 5", "phase5", reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}), writes_kinds=frozenset({ArtifactKind.FUSION_DECISION}))
    p6 = StubValidPhase("Phase 6", "phase6", reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION, ArtifactKind.FUSION_DECISION}), writes_kinds=frozenset({ArtifactKind.THEORY_ATOM}))
    p_te = StubValidPhase(
        "Theoretical Enrichment", "theoretical_enrichment",
        reads_kinds=frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}),
        writes_kinds=frozenset({ArtifactKind.THEORETICAL_ENRICHMENT}),
        dependencies=("phase4",),
    )

    pipeline = Pipeline(
        phases=[p4, p5, p6, p_te],
        config=cfg,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    prior = RunManifest(
        run_id="run-prior",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input-fp",
        phase_config_fingerprints={"phase4": "same", "phase5": "same", "phase6": "same", "theoretical_enrichment": "old-te-config"},
        phase_records=[
            RunPhaseRecord(phase_name="Phase 4", ordinal=1, phase_key="phase4", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 5", ordinal=2, phase_key="phase5", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 6", ordinal=3, phase_key="phase6", status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Theoretical Enrichment", ordinal=4, phase_key="theoretical_enrichment", status=RunStatus.COMPLETED),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)

    current = RunManifest(
        run_id="run-te-changed",
        status=RunStatus.RUNNING,
        input_fingerprint="same-input-fp",
        phase_config_fingerprints={"phase4": "same", "phase5": "same", "phase6": "same", "theoretical_enrichment": "new-te-config"},
    )

    decision = await pipeline._choose_reuse_source(current)

    # Phase 4, Phase 5, and Phase 6 are ALL reused!
    # ONLY Theoretical Enrichment (ordinal 4) is invalidated!
    assert decision.reused_phase_ordinals == [1, 2, 3]
    assert decision.invalidated_phase_ordinals == [4]
    assert decision.reason == "config-changed:Theoretical Enrichment"


def test_artifact_hydrator_uses_semantic_phase_key_over_hardcoded_ordinal() -> None:
    """Verify ArtifactHydrator checks semantic phase_key ('phase4') instead of ordinal ('phase_4' = phase3b)."""
    from episteme_pipeline.contracts.domain import L1Chunk, TheoryAtom
    from episteme_pipeline.artifacts.builders import build_theory_atom_artifact
    from episteme_pipeline.contracts.phase_contracts import PipelineInput

    chunk_unchanged = L1Chunk(
        id="chunk-1", text="Unchanged chunk", source_doc_id="doc-1", sequence_index=0, token_count=3
    )
    prior_atom = TheoryAtom(
        id="atom-1", text="Prior claim", component_type="claim", source_chunk_id="chunk-1", confidence=0.9
    )
    prior_collection = ArtifactCollection(
        [
            build_theory_atom_artifact(
                prior_atom, run_id="run-prior", phase_name="Phase 4: Argument Mining", method="test"
            )
        ]
    )

    # In the full pipeline:
    # phase_4 (ordinal 4) is Phase 3b (Consolidation)
    # phase_6 (ordinal 6) is Phase 4 (Argument Mining, phase_key="phase4")
    # Case A: Phase 3b ("phase_4") config changed, but Phase 4 ("phase4") config is UNCHANGED.
    prior_manifest = RunManifest(
        run_id="run-prior",
        status=RunStatus.COMPLETED,
        document_fingerprints={"doc-1": "hash-same"},
        phase_config_fingerprints={
            "phase3b": "old-3b-fp",
            "phase_4": "old-3b-fp",
            "phase4": "same-p4-fp",
            "phase_6": "same-p4-fp",
        },
    )
    curr_manifest_p4_unchanged = RunManifest(
        run_id="run-curr-a",
        status=RunStatus.RUNNING,
        document_fingerprints={"doc-1": "hash-same"},
        phase_config_fingerprints={
            "phase3b": "NEW-3b-fp",
            "phase_4": "NEW-3b-fp",
            "phase4": "same-p4-fp",
            "phase_6": "same-p4-fp",
        },
    )
    ctx_a = ArtifactExecutionContext(
        run_id="run-curr-a",
        manifest=curr_manifest_p4_unchanged,
        pipeline_input=PipelineInput(source_paths=["doc1.md"]),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )
    hydrator_a = ctx_a.hydrator("phase4", "Phase 4: Argument Mining")
    assert hydrator_a.can_hydrate is True
    res_a = hydrator_a.hydrate_phase4([chunk_unchanged])
    assert res_a.delta_chunks == []
    assert [c.id for c in res_a.components] == ["atom-1"]

    # Case B: Phase 3b ("phase_4") is unchanged, but Phase 4 ("phase4") config CHANGED.
    curr_manifest_p4_changed = RunManifest(
        run_id="run-curr-b",
        status=RunStatus.RUNNING,
        document_fingerprints={"doc-1": "hash-same"},
        phase_config_fingerprints={
            "phase3b": "old-3b-fp",
            "phase_4": "old-3b-fp",
            "phase4": "NEW-p4-fp",
            "phase_6": "NEW-p4-fp",
        },
    )
    ctx_b = ArtifactExecutionContext(
        run_id="run-curr-b",
        manifest=curr_manifest_p4_changed,
        pipeline_input=PipelineInput(source_paths=["doc1.md"]),
        prior_artifacts=prior_collection,
        prior_manifest=prior_manifest,
    )
    hydrator_b = ctx_b.hydrator("phase4", "Phase 4: Argument Mining")
    assert hydrator_b.can_hydrate is False
    res_b = hydrator_b.hydrate_phase4([chunk_unchanged])
    assert len(res_b.delta_chunks) == 1
    assert res_b.components == []

