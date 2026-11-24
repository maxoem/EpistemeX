"""Deterministic contract, artifact, config, event, and protocol tests for ISSUE-053.

Covers Step 1 of Closed-Loop Hermeneutic Refinement:
1. Domain contracts: ``EpistemicDeficitKind``, ``EpistemicDeficit``, ``RefinementDelta``.
2. Artifact models, codecs, builders, provenance lineage (``refinement_pass``,
   ``deficit_id``), ``JsonArtifactStore`` persistence, ``ArtifactGraphProjector``
   no-op projection, and ``EpistemicStateView`` / ``EpistemicDeficitArtifactsView``
   hydration (without polluting forward Phases 1–4 ``_allowed_kinds``).
3. Run manifest and phase record ``refinement_pass`` persistence round-trips.
4. ``HermeneuticRefinementConfig``, ``PipelineConfig.get_phase_config("refinement")``,
   and ``ExecutionConfig.should_persist_artifacts("refinement")``.
5. Refinement domain events and exhaustive handling across ``LoggingObserver``,
   ``MetricsObserver``, ``JsonlRunObserver``, and ``LangfuseObserver``.
6. Hexagonal ``@runtime_checkable`` refinement protocols extending ``Fingerprintable``
   and recursive ``find_components()`` discovery.
7. Static AST audit verifying zero ``getattr``/``hasattr`` in Step 1 code and
   complete NumPy-style docstrings on new public symbols.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import textwrap
from pathlib import Path
from typing import Any, get_args
from unittest.mock import AsyncMock, MagicMock

import pytest
from episteme_pipeline.artifacts import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactProvenance,
    EpistemicDeficitArtifact,
    EpistemicDeficitCodec,
)
from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_epistemic_deficit_artifact,
    build_global_relation_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicDeficitArtifactsView,
    EpistemicStateView,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.invalidate import ArtifactDependencyGraph
from episteme_pipeline.artifacts.models import ArtifactPayload
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import (
    ExecutionConfig,
    HermeneuticRefinementConfig,
    PipelineConfig,
)
from episteme_pipeline.contracts import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    L2Triple,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events import (
    EpistemicDeficitDetected,
    JsonlRunObserver,
    LangfuseObserver,
    LoggingObserver,
    MetricsObserver,
    PipelineEvent,
    RefinementCycleCompleted,
    RefinementCycleStarted,
)
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
from episteme_pipeline.protocols import (
    EpistemicDeficitDetector,
    Fingerprintable,
    HermeneuticRefinementCoordinator,
    LocalizedAxiomGrounder,
    TargetedConceptSplitter,
    TargetedRefinementPort,
    TheoryGuidedPremiseRecoverer,
    ensure_deficit_detector,
    ensure_refinement_coordinator,
    find_components,
)
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# 1. Domain Contracts
# ---------------------------------------------------------------------------


def test_epistemic_deficit_kind_exact_values() -> None:
    """Verify EpistemicDeficitKind exposes the exact three ISSUE-053 string members."""
    assert EpistemicDeficitKind.ENTHYMEME_GAP == "enthymeme_gap"
    assert EpistemicDeficitKind.POLYSEMY_COLLISION == "polysemy_collision"
    assert EpistemicDeficitKind.UNGROUNDED_AXIOM == "ungrounded_axiom"
    assert [m.value for m in EpistemicDeficitKind] == [
        "enthymeme_gap",
        "polysemy_collision",
        "ungrounded_axiom",
    ]


def test_epistemic_deficit_and_refinement_delta_validation() -> None:
    """Verify field defaults and bounds on EpistemicDeficit and RefinementDelta."""
    deficit = EpistemicDeficit(
        deficit_id="def-enthymeme-1",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        severity=0.85,
        target_chunk_ids=["chunk-1", "chunk-2"],
        target_atom_ids=["atom-main"],
        theory_id="theory-kant-transcendental",
        theory_lens={"M_p": ["synthetic a priori"]},
        rationale="Major claim lacks incoming support edges or empirical path.",
        metrics={"pagerank": 0.42, "incoming_supports": 0.0},
        detected_in_phase="phase6",
        refinement_pass=0,
    )
    assert deficit.severity == 0.85
    assert deficit.refinement_pass == 0

    with pytest.raises(ValidationError):
        EpistemicDeficit(
            deficit_id="bad-sev",
            deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
            severity=1.2,
        )

    with pytest.raises(ValidationError):
        EpistemicDeficit(
            deficit_id="bad-pass",
            deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
            refinement_pass=-1,
        )

    empty_delta = RefinementDelta()
    assert empty_delta.is_empty is True

    populated_delta = RefinementDelta(
        entities=[
            L2Entity(
                id="ent-sense-1",
                label="Concept",
                name="Anschauung (empirical)",
                source_chunk_ids=["chunk-1"],
            ),
            L2Entity(
                id="ent-sense-2",
                label="Concept",
                name="Anschauung (pure)",
                source_chunk_ids=["chunk-2"],
            ),
        ],
        cannot_link_pairs=[("ent-sense-1", "ent-sense-2")],
        resolved_deficit_ids=["def-polysemy-1"],
        refinement_pass=1,
    )
    assert populated_delta.is_empty is False
    assert populated_delta.cannot_link_pairs == [("ent-sense-1", "ent-sense-2")]
    assert populated_delta.refinement_pass == 1


# ---------------------------------------------------------------------------
# 2. Artifacts, Codecs, Builders, Provenance & Views
# ---------------------------------------------------------------------------


def test_epistemic_deficit_codec_and_payload_roundtrip() -> None:
    """Verify EpistemicDeficitCodec is 100% lossless and payload is in ArtifactPayload."""
    assert ArtifactKind.EPISTEMIC_DEFICIT == "epistemic_deficit"
    assert EpistemicDeficitArtifact in get_args(ArtifactPayload)

    deficit = EpistemicDeficit(
        deficit_id="def-polysemy-42",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
        severity=0.91,
        target_chunk_ids=["chunk-7", "chunk-9"],
        target_entity_ids=["ent-substance"],
        target_atom_ids=["atom-12"],
        target_relation_ids=["rel-12-15"],
        theory_id="theory-spinoza",
        theory_lens={"core_law": "Deus sive Natura"},
        rationale="Hub concept bridges conflicting communities with TS_edge < 0.5.",
        metrics={"controversy_volatility": 0.62, "min_edge_tenability": 0.31},
        detected_in_phase="theoretical_enrichment",
        refinement_pass=1,
    )

    payload = EpistemicDeficitCodec.to_payload(deficit)
    assert isinstance(payload, EpistemicDeficitArtifact)
    assert EpistemicDeficitCodec.to_domain(payload) == deficit
    assert payload.to_domain() == deficit

    envelope = ArtifactEnvelope(
        artifact_id="artifact::epistemic_deficit::def-polysemy-42",
        identity_key="epistemic_deficit::def-polysemy-42",
        kind=ArtifactKind.EPISTEMIC_DEFICIT,
        run_id="run-rt",
        phase_name="Phase 6",
        method="detector",
        provenance=ArtifactProvenance(
            refinement_pass=1,
            deficit_id="def-polysemy-42",
            upstream_artifact_ids=["artifact::ent-substance"],
        ),
        payload=payload,
    )
    rehydrated_env = ArtifactEnvelope.model_validate_json(envelope.model_dump_json())
    assert isinstance(rehydrated_env.payload, EpistemicDeficitArtifact)
    assert rehydrated_env.payload.to_domain() == deficit
    assert rehydrated_env.provenance.refinement_pass == 1
    assert rehydrated_env.provenance.deficit_id == "def-polysemy-42"


@pytest.mark.asyncio
async def test_deficit_artifact_persistence_and_noop_projection(tmp_path: Path) -> None:
    """Verify JsonArtifactStore round-trip and no-op ArtifactGraphProjector behavior."""
    store = JsonArtifactStore(tmp_path / "artifacts")

    deficit_p0 = EpistemicDeficit(
        deficit_id="def-1",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        severity=0.7,
        target_chunk_ids=["chunk-1"],
        target_atom_ids=["atom-1"],
        refinement_pass=0,
    )
    env_p0 = build_epistemic_deficit_artifact(
        deficit_p0,
        run_id="run-53",
        phase_name="Phase 6: TheoryNet Materialization",
        method="EpistemicDeficitDetector",
    )
    assert env_p0.kind == ArtifactKind.EPISTEMIC_DEFICIT
    assert env_p0.identity_key == "epistemic_deficit::def-1"
    assert env_p0.provenance.refinement_pass == 0
    assert env_p0.provenance.deficit_id == "def-1"
    assert env_p0.provenance.upstream_artifact_ids == [
        "artifact::chunk-1",
        "artifact::atom-1",
    ]

    deficit_p1 = deficit_p0.model_copy(update={"refinement_pass": 1, "severity": 0.4})
    env_p1 = build_epistemic_deficit_artifact(
        deficit_p1,
        run_id="run-53",
        phase_name="Hermeneutic Refinement",
        method="EpistemicDeficitDetector",
    )
    assert env_p1.identity_key == env_p0.identity_key
    assert env_p1.artifact_id != env_p0.artifact_id
    assert env_p1.provenance.refinement_pass == 1

    await store.write_artifact(env_p0)
    await store.write_artifact(env_p1)
    loaded = await store.list_run_artifacts("run-53")
    assert len(loaded) == 2
    loaded_by_id = {art.artifact_id: art for art in loaded}
    assert loaded_by_id[env_p0.artifact_id].payload.to_domain() == deficit_p0
    assert loaded_by_id[env_p1.artifact_id].payload.to_domain() == deficit_p1

    # Explicit no-op graph projection
    mock_graph = AsyncMock()
    projector = ArtifactGraphProjector(graph_store=mock_graph, schema=DEFAULT_SCHEMA)
    await projector.project(env_p0)
    await projector.project_collection(ArtifactCollection([env_p0, env_p1]))
    mock_graph.upsert_node.assert_not_called()
    mock_graph.upsert_relation.assert_not_called()
    mock_graph.upsert_argument_components.assert_not_called()


def test_builders_refinement_pass_provenance_and_dag_acyclicity() -> None:
    """Verify refinement_pass/deficit_id provenance across builders and DAG acyclicity."""
    chunk = L1Chunk(
        id="chunk-1",
        text="Every cognition requires intuition and concept.",
        source_doc_id="doc-1",
        sequence_index=0,
        token_count=7,
    )
    ent = L2Entity(
        id="ent-1",
        label="Concept",
        name="Cognition",
        source_chunk_ids=["chunk-1"],
    )
    local_triple = L2Triple(
        subject_id="ent-1",
        predicate="REQUIRES",
        object_id="ent-2",
        confidence=0.9,
        scope="local",
        source_chunk_id="chunk-1",
    )
    global_triple = local_triple.model_copy(update={"scope": "global"})
    claim = TheoryAtom(
        id="atom-claim",
        text="Synthetic a priori cognition is possible.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk-1",
    )
    recovered_premise = TheoryAtom(
        id="atom-premise-recovered",
        text="Pure intuition supplies non-empirical form.",
        component_type="Premise",
        source_chunk_id="chunk-1",
    )
    support_rel = TheoryRelation(
        source_id="atom-premise-recovered",
        target_id="atom-claim",
        relation_type="SUPPORTS",
        confidence=0.88,
        scope="local",
    )

    chunk_env = build_chunk_artifact(
        chunk,
        run_id="run-1",
        phase_name="Phase 1",
        method="chunker",
        refinement_pass=1,
        deficit_id="def-g1",
    )
    ent_env = build_linked_entity_artifact(
        ent,
        ["artifact::mention::ent-1::chunk-1"],
        run_id="run-1",
        phase_name="Refine",
        method="split",
        refinement_pass=1,
        deficit_id="def-p1",
    )
    loc_env = build_local_relation_artifact(
        local_triple,
        run_id="run-1",
        phase_name="Refine",
        method="split",
        refinement_pass=1,
        deficit_id="def-p1",
    )
    glob_env = build_global_relation_artifact(
        global_triple,
        {"REQUIRES": 1},
        run_id="run-1",
        phase_name="Refine",
        method="split",
        refinement_pass=1,
        deficit_id="def-p1",
    )
    claim_env = build_theory_atom_artifact(
        claim, run_id="run-1", phase_name="Phase 4", method="acc"
    )
    deficit = EpistemicDeficit(
        deficit_id="def-g1",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        target_chunk_ids=["chunk-1"],
        target_atom_ids=["atom-claim"],
    )
    deficit_env = build_epistemic_deficit_artifact(
        deficit, run_id="run-1", phase_name="Phase 6", method="detector"
    )
    premise_env = build_theory_atom_artifact(
        recovered_premise,
        run_id="run-1",
        phase_name="Hermeneutic Refinement",
        method="TheoryGuidedPremiseRecoverer",
        upstream_artifact_ids=[chunk_env.artifact_id, deficit_env.artifact_id],
        refinement_pass=1,
        deficit_id="def-g1",
    )
    rel_env = build_theory_relation_artifact(
        support_rel,
        run_id="run-1",
        phase_name="Hermeneutic Refinement",
        method="TheoryGuidedPremiseRecoverer",
        upstream_artifact_ids=[premise_env.artifact_id, claim_env.artifact_id],
        refinement_pass=1,
        deficit_id="def-g1",
    )

    for env in (chunk_env, ent_env, loc_env, glob_env, premise_env, rel_env):
        assert env.provenance.refinement_pass == 1
    assert premise_env.provenance.deficit_id == "def-g1"
    assert rel_env.provenance.deficit_id == "def-g1"

    dag = ArtifactDependencyGraph.from_artifacts(
        [chunk_env, claim_env, deficit_env, premise_env, rel_env]
    )
    order = dag.topsort()
    assert order.index(deficit_env.identity_key) < order.index(premise_env.identity_key)
    assert order.index(premise_env.identity_key) < order.index(rel_env.identity_key)


def test_views_hydrate_deficits_and_preserve_forward_reads_kinds() -> None:
    """Verify EpistemicStateView and EpistemicDeficitArtifactsView hydrate deficits safely."""
    for forward_view in (
        Phase1ArtifactsView,
        Phase2ArtifactsView,
        Phase3ArtifactsView,
        Phase4ArtifactsView,
    ):
        assert ArtifactKind.EPISTEMIC_DEFICIT not in forward_view._allowed_kinds
        assert ArtifactKind.EPISTEMIC_DEFICIT not in forward_view.allowed_kinds

    assert (
        ArtifactKind.EPISTEMIC_DEFICIT in EpistemicDeficitArtifactsView._allowed_kinds
    )

    atom = TheoryAtom(
        id="atom-1",
        text="Space is a pure intuition.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk-1",
    )
    deficit = EpistemicDeficit(
        deficit_id="def-ungrounded-1",
        deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
        severity=0.8,
        target_chunk_ids=["chunk-1"],
        target_atom_ids=["atom-1"],
        refinement_pass=0,
    )
    collection = ArtifactCollection(
        [
            build_theory_atom_artifact(
                atom, run_id="run-v", phase_name="Phase 4", method="acc"
            ),
            build_epistemic_deficit_artifact(
                deficit, run_id="run-v", phase_name="Enrichment", method="detector"
            ),
        ]
    )

    state_view = EpistemicStateView.from_collection(collection)
    deficit_view = EpistemicDeficitArtifactsView.from_collection(collection)

    assert len(state_view.epistemic_deficits) == 1
    assert state_view.to_domain_deficits() == [deficit]
    assert len(deficit_view.epistemic_deficits) == 1
    assert deficit_view.to_domain_deficits() == [deficit]
    assert len(deficit_view.canonical_theory_atoms) == 1
    assert deficit_view.to_graph_reader() is not None


# ---------------------------------------------------------------------------
# 3. RunManifest & RunPhaseRecord Persistence
# ---------------------------------------------------------------------------


def test_run_manifest_and_phase_record_refinement_pass_roundtrip(
    tmp_path: Path,
) -> None:
    """Verify refinement_pass defaults, validation, and JsonRunManifestStore round-trip."""
    default_manifest = RunManifest(run_id="run-default")
    assert default_manifest.refinement_pass == 0

    default_record = RunPhaseRecord(phase_name="Phase 6", ordinal=6)
    assert default_record.refinement_pass == 0

    with pytest.raises(ValidationError):
        RunManifest(run_id="run-bad", refinement_pass=-1)

    with pytest.raises(ValidationError):
        RunPhaseRecord(phase_name="Phase 6", ordinal=6, refinement_pass=-1)

    store = JsonRunManifestStore(tmp_path / "runs")
    manifest = RunManifest(
        run_id="run-refine-2",
        status=RunStatus.COMPLETED,
        refinement_pass=2,
        phase_records=[
            RunPhaseRecord(
                phase_name="Hermeneutic Refinement",
                ordinal=9,
                phase_key="refinement",
                status=RunStatus.COMPLETED,
                refinement_pass=2,
                output_artifact_ids=["artifact::epistemic_deficit::def-1::pass2"],
            )
        ],
    )
    store.write_manifest(manifest)
    reloaded = store.read_manifest("run-refine-2")
    assert reloaded is not None
    assert reloaded.refinement_pass == 2
    assert reloaded.phase_records[0].refinement_pass == 2


# ---------------------------------------------------------------------------
# 4. Configuration
# ---------------------------------------------------------------------------


def test_hermeneutic_refinement_config_and_pipeline_wiring() -> None:
    """Verify HermeneuticRefinementConfig defaults, validation, and PipelineConfig access."""
    cfg = PipelineConfig()
    ref_cfg = cfg.refinement
    assert isinstance(ref_cfg, HermeneuticRefinementConfig)
    assert ref_cfg.max_refinement_cycles == 0
    assert ref_cfg.enthymeme_min_centrality == 0.0
    assert ref_cfg.polysemy_edge_tenability_threshold == 0.5
    assert ref_cfg.polysemy_volatility_threshold == 0.25
    assert ref_cfg.ungrounded_local_tenability_threshold == 0.5
    assert ref_cfg.max_deficits_per_cycle == 20
    assert ref_cfg.enable_theory_guided_premise_recovery is True
    assert ref_cfg.enable_targeted_concept_split is True
    assert ref_cfg.enable_localized_axiom_grounding is True

    assert cfg.get_phase_config("refinement") is ref_cfg
    assert isinstance(cfg.execution, ExecutionConfig)
    assert cfg.execution.persist_refinement_artifacts is True
    assert cfg.execution.should_persist_artifacts("refinement") is True

    cfg.execution.persist_refinement_artifacts = False
    assert cfg.execution.should_persist_artifacts("refinement") is False

    with pytest.raises(ValidationError):
        HermeneuticRefinementConfig(max_refinement_cycles=6)

    with pytest.raises(ValidationError):
        HermeneuticRefinementConfig(polysemy_edge_tenability_threshold=1.5)

    with pytest.raises(ValidationError):
        HermeneuticRefinementConfig(max_deficits_per_cycle=0)

    # Verify adding PipelineConfig.refinement does not alter existing phase fingerprints.
    from episteme_pipeline.runs.fingerprints import fingerprint_phase_config

    assert cfg.get_phase_config("phase6") is cfg.phase6
    assert fingerprint_phase_config(cfg.phase6) == fingerprint_phase_config(
        PipelineConfig(
            refinement=HermeneuticRefinementConfig(max_refinement_cycles=2)
        ).phase6
    )


# ---------------------------------------------------------------------------
# 5. Events & Observers
# ---------------------------------------------------------------------------


def test_refinement_events_and_all_observers(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify new refinement events belong to PipelineEvent and work in all observers."""
    union_members = get_args(PipelineEvent)
    for cls in (
        EpistemicDeficitDetected,
        RefinementCycleStarted,
        RefinementCycleCompleted,
    ):
        assert cls in union_members

    ev_detected = EpistemicDeficitDetected(
        run_id="run-ev",
        phase="phase6",
        deficit_id="def-e1",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        severity=0.82,
        target_chunk_ids=["chunk-1"],
        target_atom_ids=["atom-1"],
        theory_id="T1",
        refinement_pass=0,
        rationale="Missing support edge.",
    )
    ev_started = RefinementCycleStarted(
        run_id="run-ev",
        phase="refinement",
        refinement_pass=1,
        deficit_count=1,
        deficit_ids=["def-e1"],
        target_chunk_ids=["chunk-1"],
        target_entity_ids=[],
    )
    ev_completed = RefinementCycleCompleted(
        run_id="run-ev",
        phase="refinement",
        refinement_pass=1,
        resolved_deficit_count=1,
        remaining_deficit_count=0,
        resolved_deficit_ids=["def-e1"],
        delta_artifact_count=2,
        duration_seconds=0.125,
        converged=True,
    )

    # LoggingObserver & MetricsObserver
    logger = logging.getLogger("test.issue053.events")
    logging_obs = LoggingObserver(logger=logger)
    metrics_obs = MetricsObserver()
    jsonl_path = tmp_path / "events.jsonl"

    with caplog.at_level(logging.INFO, logger="test.issue053.events"):  # noqa: SIM117 baseline
        with JsonlRunObserver(jsonl_path) as jsonl_obs:
            for ev in (ev_detected, ev_started, ev_completed):
                logging_obs.on_event(ev)
                metrics_obs.on_event(ev)
                jsonl_obs.on_event(ev)

    assert "Epistemic deficit [enthymeme_gap] 'def-e1'" in caplog.text
    assert "Hermeneutic refinement cycle 1 started" in caplog.text
    assert "Hermeneutic refinement cycle 1 completed" in caplog.text

    assert metrics_obs.epistemic_deficits_detected["enthymeme_gap"] == 1
    assert metrics_obs.refinement_cycles_completed == 1
    assert metrics_obs.refinement_deficits_resolved == 1

    lines = [
        json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [entry["_event_type"] for entry in lines] == [
        "EpistemicDeficitDetected",
        "RefinementCycleStarted",
        "RefinementCycleCompleted",
    ]

    # LangfuseObserver
    mock_client = MagicMock()
    mock_client.get_current_trace_id.return_value = None
    mock_client.get_current_observation_id.return_value = None
    lf_obs = LangfuseObserver(client=mock_client)
    for ev in (ev_detected, ev_started, ev_completed):
        lf_obs.on_event(ev)

    span_names = [
        call.kwargs.get("name") for call in mock_client.start_observation.call_args_list
    ]
    assert "refinement.deficit.detected" in span_names
    assert "refinement.cycle.started" in span_names
    assert "refinement.cycle.completed" in span_names


# ---------------------------------------------------------------------------
# 6. Protocols & Fingerprintable Discovery
# ---------------------------------------------------------------------------


def test_refinement_protocols_and_fingerprintable_discovery() -> None:
    """Verify @runtime_checkable protocol conformance and find_components() discovery."""

    class StubDetector:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "StubDetector", "threshold": 0.5}

        def detect_deficits(
            self,
            state: EpistemicStateView,
            *,
            refinement_pass: int = 0,
            config: HermeneuticRefinementConfig | None = None,
            context: ArtifactExecutionContext | None = None,
        ) -> list[EpistemicDeficit]:
            return []

    class StubPremiseRecoverer:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "StubPremiseRecoverer"}

        async def recover_premises(
            self,
            deficit: EpistemicDeficit,
            state: EpistemicStateView,
            *,
            context: ArtifactExecutionContext | None = None,
        ) -> RefinementDelta:
            return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)

    class StubConceptSplitter:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "StubConceptSplitter"}

        async def split_concept(
            self,
            deficit: EpistemicDeficit,
            state: EpistemicStateView,
            *,
            context: ArtifactExecutionContext | None = None,
        ) -> RefinementDelta:
            return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)

    class StubAxiomGrounder:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "StubAxiomGrounder"}

        async def ground_axiom(
            self,
            deficit: EpistemicDeficit,
            state: EpistemicStateView,
            *,
            context: ArtifactExecutionContext | None = None,
        ) -> RefinementDelta:
            return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)

    class StubTargetedPort:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "StubTargetedPort"}

        async def refine_deficit(
            self,
            deficit: EpistemicDeficit,
            state: EpistemicStateView,
            *,
            context: ArtifactExecutionContext | None = None,
        ) -> RefinementDelta:
            return RefinementDelta(refinement_pass=deficit.refinement_pass + 1)

    class StubCoordinator:
        def __init__(self) -> None:
            self.detector = StubDetector()
            self.premise_recoverer = StubPremiseRecoverer()
            self.concept_splitter = StubConceptSplitter()
            self.axiom_grounder = StubAxiomGrounder()

        def fingerprint(self) -> dict[str, Any]:
            return {"class": "StubCoordinator", "max_cycles": 1}

        async def refine(
            self,
            collection: ArtifactCollection,
            context: ArtifactExecutionContext,
            *,
            config: HermeneuticRefinementConfig | None = None,
        ) -> ArtifactCollection:
            return collection

    detector = StubDetector()
    recoverer = StubPremiseRecoverer()
    splitter = StubConceptSplitter()
    grounder = StubAxiomGrounder()
    port = StubTargetedPort()
    coordinator = StubCoordinator()

    assert isinstance(detector, EpistemicDeficitDetector)
    assert isinstance(detector, Fingerprintable)
    assert isinstance(recoverer, TheoryGuidedPremiseRecoverer)
    assert isinstance(recoverer, Fingerprintable)
    assert isinstance(splitter, TargetedConceptSplitter)
    assert isinstance(splitter, Fingerprintable)
    assert isinstance(grounder, LocalizedAxiomGrounder)
    assert isinstance(grounder, Fingerprintable)
    assert isinstance(port, TargetedRefinementPort)
    assert isinstance(port, Fingerprintable)
    assert isinstance(coordinator, HermeneuticRefinementCoordinator)
    assert isinstance(coordinator, Fingerprintable)

    assert ensure_deficit_detector(None) is None
    assert ensure_deficit_detector(detector) is detector
    assert ensure_refinement_coordinator(None) is None
    assert ensure_refinement_coordinator(coordinator) is coordinator

    class MissingFingerprintDetector:
        def detect_deficits(self, state: EpistemicStateView) -> list[EpistemicDeficit]:
            return []

    assert not isinstance(MissingFingerprintDetector(), EpistemicDeficitDetector)
    with pytest.raises(TypeError, match="EpistemicDeficitDetector"):
        ensure_deficit_detector(MissingFingerprintDetector())
    with pytest.raises(TypeError, match="HermeneuticRefinementCoordinator"):
        ensure_refinement_coordinator(object())

    discovered = find_components(coordinator)
    assert set(discovered.keys()) == {
        "detector",
        "premise_recoverer",
        "concept_splitter",
        "axiom_grounder",
    }


# ---------------------------------------------------------------------------
# 7. Static AST Guard & Docstring Standards
# ---------------------------------------------------------------------------


def test_zero_reflection_and_docstrings_in_step1_files() -> None:
    """Verify zero getattr/hasattr in Step 1 files and docstrings on new symbols."""
    root_dir = Path(__file__).resolve().parent.parent / "episteme_pipeline"

    full_audit_files = [
        root_dir / "contracts" / "domain.py",
        root_dir / "contracts" / "__init__.py",
        root_dir / "artifacts" / "models.py",
        root_dir / "artifacts" / "__init__.py",
        root_dir / "artifacts" / "codecs.py",
        root_dir / "artifacts" / "builders.py",
        root_dir / "artifacts" / "execution.py",
        root_dir / "runs" / "models.py",
        root_dir / "config.py",
        root_dir / "events" / "models.py",
        root_dir / "events" / "__init__.py",
        root_dir / "events" / "observers.py",
        root_dir / "protocols" / "refinement.py",
        root_dir / "protocols" / "__init__.py",
    ]

    violations: list[str] = []
    for py_file in full_audit_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):  # noqa: SIM102 baseline
                if node.func.id in {"getattr", "hasattr"}:
                    violations.append(
                        f"{py_file.relative_to(root_dir)}:{node.lineno} calls {node.func.id}"
                    )

    # Also verify newly added LangfuseObserver event handling blocks contain zero reflection.
    lf_source = inspect.getsource(LangfuseObserver._handle_domain_event)
    lf_lifecycle = inspect.getsource(LangfuseObserver._handle_lifecycle_event)
    for name, src in (
        ("_handle_domain_event", lf_source),
        ("_handle_lifecycle_event", lf_lifecycle),
    ):
        tree = ast.parse(textwrap.dedent(src))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):  # noqa: SIM102 baseline
                if node.func.id in {"getattr", "hasattr"}:
                    violations.append(
                        f"events/langfuse_observer.py:{name} calls {node.func.id}"
                    )

    assert not violations, "Forbidden getattr/hasattr detected:\n" + "\n".join(
        violations
    )

    # Verify NumPy-style docstrings exist on new Step 1 public classes & functions
    documented_symbols = [
        EpistemicDeficitKind,
        EpistemicDeficit,
        RefinementDelta,
        EpistemicDeficitArtifact,
        EpistemicDeficitCodec,
        EpistemicDeficitCodec.to_payload,
        EpistemicDeficitCodec.to_domain,
        build_epistemic_deficit_artifact,
        EpistemicDeficitArtifactsView,
        HermeneuticRefinementConfig,
        EpistemicDeficitDetected,
        RefinementCycleStarted,
        RefinementCycleCompleted,
        EpistemicDeficitDetector,
        TheoryGuidedPremiseRecoverer,
        TargetedConceptSplitter,
        LocalizedAxiomGrounder,
        TargetedRefinementPort,
        HermeneuticRefinementCoordinator,
        ensure_deficit_detector,
        ensure_refinement_coordinator,
    ]
    missing_docs = [
        getattr_free_name
        for sym in documented_symbols
        if not (sym.__doc__ and sym.__doc__.strip())
        for getattr_free_name in (sym.__qualname__,)
    ]
    assert not missing_docs, f"Missing docstrings on: {missing_docs}"
