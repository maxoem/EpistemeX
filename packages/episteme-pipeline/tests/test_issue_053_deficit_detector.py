"""Deterministic unit and integration tests for ISSUE-053 Step 2 deficit detection.

Covers:
1. ``EpistemicStateView`` and ``EpistemicDeficitArtifactsView`` hydration of
   ``theoretical_enrichments`` without altering forward ``Phase1..4ArtifactsView``
   allowed kinds.
2. ``TheoryNetDeficitDetector`` detection of ``ENTHYMEME_GAP`` (via
   ``epistemetrics.page_rank`` + zero incoming support / broken :math:`Z_1` path),
   ``POLYSEMY_COLLISION`` (via high controversy volatility :math:`\\mathcal{V}`
   and/or ``TS_edge < 0.5`` bridging incompatible clusters/conceptions), and
   ``UNGROUNDED_AXIOM`` (via ``TS_local < 0.5``, ``is_tenable == False``,
   missing ``M_pp`` dimensions, or missing empirical base :math:`B`).
3. Deterministic ranking, ``max_deficits_per_cycle`` capping, ``refinement_pass``
   stamping, ``Fingerprintable`` discovery, and ``EpistemicDeficitDetected`` events.
4. End-to-end deterministic integration in ``Phase6Runner`` and
   ``TheoreticalEnrichmentRunner`` without LLM or Neo4j dependencies.
5. Static AST verification of zero ``getattr``/``hasattr`` and NumPy docstrings.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from episteme_pipeline.artifacts.builders import (
    build_epistemic_deficit_artifact,
    build_theory_atom_artifact,
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
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    TheoreticalEnrichmentArtifact,
)
from episteme_pipeline.config import (
    HermeneuticRefinementConfig,
    Phase6Config,
    TheoreticalEnrichmentConfig,
)
from episteme_pipeline.contracts.domain import (
    EntityConception,
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    Measurement,
    TenabilityResult,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import (
    EpistemicDeficitDetected,
    MetricsObserver,
    SimpleEventEmitter,
    use_event_emitter,
)
from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner
from episteme_pipeline.post_processing.theoretical_enrichment import (
    GenericTheoryProjector,
    TheoreticalEnrichmentRunner,
    TheoryElementDefinition,
    TheoryLaw,
    TheoryRegistry,
)
from episteme_pipeline.protocols import (
    EpistemicDeficitDetector,
    Fingerprintable,
    ensure_deficit_detector,
    find_components,
)
from episteme_pipeline.refinement.detector import TheoryNetDeficitDetector
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


class _RecordingObserver:
    """Minimal event observer collecting emitted events for assertions."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def on_event(self, event: Any) -> None:
        """Record a pipeline event."""
        self.events.append(event)

    def flush(self) -> None:
        """No-op flush."""


def _make_context(
    run_id: str = "run-det", refinement_pass: int = 0
) -> ArtifactExecutionContext:
    """Create a deterministic execution context for tests."""
    return ArtifactExecutionContext(
        run_id=run_id,
        manifest=RunManifest(run_id=run_id, refinement_pass=refinement_pass),
        pipeline_input=PipelineInput(source_paths=[]),
    )


# ---------------------------------------------------------------------------
# 1. View Hydration & Allowed Kinds
# ---------------------------------------------------------------------------


def test_views_hydrate_theoretical_enrichments_and_preserve_forward_kinds() -> None:
    """Verify EpistemicStateView hydrates theoretical_enrichments cleanly."""
    for forward_view in (
        Phase1ArtifactsView,
        Phase2ArtifactsView,
        Phase3ArtifactsView,
        Phase4ArtifactsView,
    ):
        assert ArtifactKind.EPISTEMIC_DEFICIT not in forward_view._allowed_kinds
        assert ArtifactKind.EPISTEMIC_DEFICIT not in forward_view.allowed_kinds

    assert (
        ArtifactKind.THEORETICAL_ENRICHMENT
        in EpistemicDeficitArtifactsView._allowed_kinds
    )
    assert (
        ArtifactKind.EPISTEMIC_DEFICIT in EpistemicDeficitArtifactsView._allowed_kinds
    )

    atom = TheoryAtom(
        id="hyp_1",
        text="Dopamine dysregulation drives affect intensity.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
    )
    enr_payload = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-1",
        cluster_id="cluster-c1",
        theory_id="neuro",
        claimant_atom_ids=["hyp_1"],
        projected_parameters={"DopamineDepletion": 0.8},
        local_tenability=0.35,
        edge_tenabilities={},
        equilibrium_strengths={"hyp_1": 0.30},
        aggregated_tenability=0.45,
        admissible_blur_delta=0.65,
        is_tenable=False,
        anomalies=["Low local tenability"],
    )
    enr_env = ArtifactEnvelope[TheoreticalEnrichmentArtifact](
        artifact_id="enr-1",
        kind=ArtifactKind.THEORETICAL_ENRICHMENT,
        run_id="run-v",
        phase_name="Theoretical Enrichment",
        method="te",
        payload=enr_payload,
    )
    deficit = EpistemicDeficit(
        deficit_id="ungrounded_axiom::neuro::cluster-c1",
        deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
        severity=0.8,
        target_atom_ids=["hyp_1"],
    )
    collection = ArtifactCollection(
        [
            build_theory_atom_artifact(
                atom, run_id="run-v", phase_name="P4", method="acc"
            ),
            enr_env,
            build_epistemic_deficit_artifact(
                deficit, run_id="run-v", phase_name="TE", method="det"
            ),
        ]
    )

    state_view = EpistemicStateView.from_collection(collection)
    deficit_view = EpistemicDeficitArtifactsView.from_collection(collection)
    p4_view = Phase4ArtifactsView.from_collection(collection)

    assert len(state_view.theoretical_enrichments) == 1
    assert state_view.theoretical_enrichments[0].enrichment_id == "enr-1"
    assert len(deficit_view.theoretical_enrichments) == 1
    assert deficit_view.to_domain_deficits() == [deficit]
    assert len(p4_view.theoretical_enrichments) == 1


# ---------------------------------------------------------------------------
# 2. ENTHYMEME_GAP Detection
# ---------------------------------------------------------------------------


def test_detect_enthymeme_gap_via_pagerank_and_z1_grounding() -> None:
    """Verify ENTHYMEME_GAP catches unsupported and Z1-disconnected A-atoms."""
    chunks = [
        L1Chunk(
            id="c1",
            text="Obs chunk",
            source_doc_id="doc1",
            sequence_index=0,
            token_count=5,
        ),
        L1Chunk(
            id="c2",
            text="Hub chunk",
            source_doc_id="doc1",
            sequence_index=1,
            token_count=5,
        ),
        L1Chunk(
            id="c3",
            text="Tail chunk",
            source_doc_id="doc1",
            sequence_index=2,
            token_count=5,
        ),
    ]
    ent = L2Entity(
        id="ent_cog", label="Concept", name="Cognition", source_chunk_ids=["c2"]
    )

    obs = TheoryAtom(
        id="obs_1",
        text="Reaction times decrease after consolidation.",
        component_type="ObservationUnit",
        source_chunk_id="c1",
        measurements=[Measurement(dimension="reaction_time", value=0.4, unit="s")],
    )
    hyp_grounded = TheoryAtom(
        id="hyp_grounded",
        text="Consolidation improves retrieval latency.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.8,
        equilibrium_strength=0.85,
    )
    hyp_hub = TheoryAtom(
        id="hyp_hub",
        text="Working memory capacity gates abstract reasoning.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        modal_prior=0.85,
        equilibrium_strength=0.70,
        entity_ids=["ent_cog"],
    )
    hyp_downstream = TheoryAtom(
        id="hyp_downstream",
        text="Therefore syllogistic error scales with load.",
        component_type="CoreExpansion",
        source_chunk_id="c3",
        modal_prior=0.65,
        equilibrium_strength=0.72,
    )
    hyp_reductio = TheoryAtom(
        id="hyp_reductio",
        text="Suppose working memory were infinite.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        intensional_mode="suppositional",
        modal_prior=0.7,
    )

    rels = [
        TheoryRelation(
            source_id="obs_1",
            target_id="hyp_grounded",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="hyp_hub",
            target_id="hyp_downstream",
            relation_type="ENTAILS",
            confidence=0.85,
            scope="global",
        ),
    ]
    enr = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-cog",
        cluster_id="cluster-c2",
        theory_id="cognitive_load_theory",
        claimant_atom_ids=["hyp_hub"],
        projected_parameters={"WorkingMemorySpan": 0.72},
        local_tenability=0.90,
        aggregated_tenability=0.90,
        admissible_blur_delta=0.10,
        is_tenable=True,
    )

    state = EpistemicDeficitArtifactsView(
        chunks=chunks,
        entities=[ent],
        theory_atoms=[obs, hyp_grounded, hyp_hub, hyp_downstream, hyp_reductio],
        theory_relations=rels,
        theoretical_enrichments=[enr],
    )

    detector = TheoryNetDeficitDetector()
    deficits = detector.detect_deficits(state, context=_make_context())
    enthymemes = [
        d for d in deficits if d.deficit_kind == EpistemicDeficitKind.ENTHYMEME_GAP
    ]
    by_atom = {d.target_atom_ids[0]: d for d in enthymemes}

    assert "hyp_grounded" not in by_atom
    assert "hyp_reductio" not in by_atom
    assert "hyp_hub" in by_atom
    assert "hyp_downstream" in by_atom

    hub_def = by_atom["hyp_hub"]
    assert hub_def.metrics["in_support_degree"] == 0.0
    assert hub_def.metrics["z1_grounded"] == 0.0
    assert hub_def.metrics["centrality"] > 0.0
    assert hub_def.metrics["tau_star"] == pytest.approx(0.70)
    assert set(hub_def.target_chunk_ids) == {"c2", "c1", "c3"}
    assert hub_def.theory_id == "cognitive_load_theory"
    assert hub_def.theory_lens["entity_names"] == ["Cognition"]
    assert "WorkingMemorySpan" in hub_def.theory_lens["parameter_names"]
    assert "reaction_time" in hub_def.theory_lens["required_dimensions"]

    # hyp_downstream has incoming ENTAILS (+1) from hyp_hub, but broken Z1 path
    down_def = by_atom["hyp_downstream"]
    assert down_def.metrics["in_support_degree"] == 1.0
    assert down_def.metrics["z1_grounded"] == 0.0
    assert hub_def.severity > down_def.severity

    # High centrality threshold filters out lower-PageRank nodes
    filtered = detector.detect_deficits(
        state,
        config=HermeneuticRefinementConfig(enthymeme_min_centrality=0.25),
    )
    filtered_atoms = {
        d.target_atom_ids[0]
        for d in filtered
        if d.deficit_kind == EpistemicDeficitKind.ENTHYMEME_GAP
    }
    assert "hyp_downstream" in filtered_atoms
    assert "hyp_hub" not in filtered_atoms


# ---------------------------------------------------------------------------
# 3. POLYSEMY_COLLISION Detection
# ---------------------------------------------------------------------------


def test_detect_polysemy_collision_volatility_and_ts_edge() -> None:
    """Verify POLYSEMY_COLLISION flags conflicting hubs by volatility and TS_edge."""
    ent_space = L2Entity(
        id="ent_space",
        label="Concept",
        name="Space",
        source_chunk_ids=["c1", "c2"],
        polysemy_variance=0.41,
        conceptions=[
            EntityConception(
                id="ent_space::c1",
                entity_id="ent_space",
                perspective="Kant",
                description="Pure a priori form of outer intuition.",
                source_chunk_ids=["c1"],
            ),
            EntityConception(
                id="ent_space::c2",
                entity_id="ent_space",
                perspective="Leibniz",
                description="Relational order of coexistences.",
                source_chunk_ids=["c2"],
            ),
        ],
    )
    ent_uncontested = L2Entity(
        id="ent_time",
        label="Concept",
        name="Time",
        source_chunk_ids=["c3"],
    )

    atom_k = TheoryAtom(
        id="atom_kant",
        text="Space is a pure intuition prior to experience.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        entity_ids=["ent_space"],
        controversy_volatility=0.44,
        local_tenability=0.90,
    )
    atom_l = TheoryAtom(
        id="atom_leibniz",
        text="Space reduces to empirical relations between bodies.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        entity_ids=["ent_space"],
        controversy_volatility=0.10,
        local_tenability=0.90,
    )
    obs_k = TheoryAtom(
        id="obs_k",
        text="Geometric axioms hold apodictically.",
        component_type="ObservationUnit",
        source_chunk_id="c1",
    )
    obs_ok = TheoryAtom(
        id="obs_ok",
        text="Temporal succession is monotonic.",
        component_type="ObservationUnit",
        source_chunk_id="c3",
    )
    hyp_ok = TheoryAtom(
        id="hyp_ok",
        text="Time orders sequential appearances.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c3",
        entity_ids=["ent_time"],
        controversy_volatility=0.35,  # High volatility alone without conflict must NOT fire
        local_tenability=0.90,
    )

    rels = [
        TheoryRelation(
            source_id="obs_k",
            target_id="atom_kant",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
            edge_tenability=0.90,
        ),
        TheoryRelation(
            source_id="atom_leibniz",
            target_id="atom_kant",
            relation_type="ATTACKS",
            confidence=0.9,
            scope="global",
            edge_tenability=0.30,
        ),
        TheoryRelation(
            source_id="obs_ok",
            target_id="hyp_ok",
            relation_type="SUPPORTS",
            confidence=0.95,
            scope="local",
            edge_tenability=0.95,
        ),
    ]

    enr_1 = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-kant",
        cluster_id="cluster-c1",
        theory_id="transcendental_idealism",
        claimant_atom_ids=["atom_kant"],
        local_tenability=0.90,
        aggregated_tenability=0.90,
        admissible_blur_delta=0.10,
        is_tenable=True,
    )
    enr_2 = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-leibniz",
        cluster_id="cluster-c2",
        theory_id="relationalism",
        claimant_atom_ids=["atom_leibniz"],
        local_tenability=0.90,
        aggregated_tenability=0.90,
        admissible_blur_delta=0.10,
        is_tenable=True,
    )

    state = EpistemicDeficitArtifactsView(
        entities=[ent_space, ent_uncontested],
        theory_atoms=[atom_k, atom_l, obs_k, obs_ok, hyp_ok],
        theory_relations=rels,
        theoretical_enrichments=[enr_1, enr_2],
    )

    detector = TheoryNetDeficitDetector()
    deficits = detector.detect_deficits(state)
    polysemies = [
        d for d in deficits if d.deficit_kind == EpistemicDeficitKind.POLYSEMY_COLLISION
    ]

    assert len(polysemies) == 1
    poly = polysemies[0]
    assert poly.target_entity_ids == ["ent_space"]
    assert "atom_kant" in poly.target_atom_ids
    assert "atom_leibniz" in poly.target_atom_ids
    assert any("ATTACKS" in rid for rid in poly.target_relation_ids)
    assert set(poly.target_chunk_ids) == {"c1", "c2"}
    assert poly.metrics["controversy_volatility"] == pytest.approx(0.44)
    assert poly.metrics["ts_edge"] == pytest.approx(0.30)
    assert poly.metrics["polysemy_variance"] == pytest.approx(0.41)


def test_detect_polysemy_collision_via_low_ts_edge_without_entities() -> None:
    """Verify atom/relation-level POLYSEMY_COLLISION triggers on TS_edge < 0.5."""
    atom_a = TheoryAtom(
        id="atom_a",
        text="Classical energy scales continuously.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        controversy_volatility=0.05,
        local_tenability=0.95,
    )
    atom_b = TheoryAtom(
        id="atom_b",
        text="Quantum energy is quantized in discrete packets.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        controversy_volatility=0.05,
        local_tenability=0.95,
    )
    obs_a = TheoryAtom(
        id="obs_a", text="Obs A", component_type="ObservationUnit", source_chunk_id="c1"
    )
    obs_b = TheoryAtom(
        id="obs_b", text="Obs B", component_type="ObservationUnit", source_chunk_id="c2"
    )
    rels = [
        TheoryRelation(
            source_id="obs_a",
            target_id="atom_a",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="obs_b",
            target_id="atom_b",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="atom_a",
            target_id="atom_b",
            relation_type="CONSTRAINS",
            confidence=0.85,
            scope="global",
            edge_tenability=0.22,
        ),
    ]
    enr_a = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-a",
        cluster_id="cluster-c1",
        theory_id="classical",
        claimant_atom_ids=["atom_a"],
        local_tenability=0.95,
        edge_tenabilities={"atom_a->CONSTRAINS->atom_b": 0.22},
        aggregated_tenability=0.585,
        admissible_blur_delta=0.05,
        is_tenable=True,
    )
    enr_b = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-b",
        cluster_id="cluster-c2",
        theory_id="quantum",
        claimant_atom_ids=["atom_b"],
        local_tenability=0.95,
        aggregated_tenability=0.95,
        admissible_blur_delta=0.05,
        is_tenable=True,
    )

    state = EpistemicDeficitArtifactsView(
        theory_atoms=[atom_a, atom_b, obs_a, obs_b],
        theory_relations=rels,
        theoretical_enrichments=[enr_a, enr_b],
    )
    deficits = TheoryNetDeficitDetector().detect_deficits(state)
    polysemies = [
        d for d in deficits if d.deficit_kind == EpistemicDeficitKind.POLYSEMY_COLLISION
    ]
    ungrounded = [
        d for d in deficits if d.deficit_kind == EpistemicDeficitKind.UNGROUNDED_AXIOM
    ]
    assert len(polysemies) >= 1
    assert any(p.metrics["ts_edge"] == pytest.approx(0.22) for p in polysemies)
    assert ungrounded == []


# ---------------------------------------------------------------------------
# 4. UNGROUNDED_AXIOM Detection
# ---------------------------------------------------------------------------


def test_detect_ungrounded_axiom_across_enrichment_local_ts_and_missing_b() -> None:
    """Verify UNGROUNDED_AXIOM catches low TS_local, untenable clusters, and missing B-base."""
    obs_c1 = TheoryAtom(
        id="obs_c1",
        text="Partial telemetry measurement.",
        component_type="ObservationUnit",
        source_chunk_id="c1",
        measurements=[Measurement(dimension="dopamine_level", value=0.9)],
    )
    hyp_enr = TheoryAtom(
        id="hyp_enr",
        text="Dopamine and amygdala activity equalize.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.85,
        local_tenability=0.15,
        equilibrium_strength=0.22,
        parameters={
            "DopamineDepletion": 0.9,
            "required_dimensions": ["dopamine_level", "amygdala_hyperactivity"],
        },
    )
    obs_c2 = TheoryAtom(
        id="obs_c2",
        text="Baseline reading.",
        component_type="ObservationUnit",
        source_chunk_id="c2",
    )
    hyp_atom_low = TheoryAtom(
        id="hyp_atom_low",
        text="Standalone hypothesis failing local tenability.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        modal_prior=0.80,
        local_tenability=0.30,
        equilibrium_strength=0.28,
        tenability=TenabilityResult(
            local_score=0.30,
            edge_scores={},
            aggregated_score=0.30,
            is_tenable=False,
            tightest_blur=0.70,
            anomalies=["Law mismatch"],
        ),
    )
    axiom_no_obs = TheoryAtom(
        id="axiom_no_obs",
        text="Purely theoretical postulate without empirical observations in cluster.",
        component_type="CoreExpansion",
        source_chunk_id="c_no_obs",
        modal_prior=0.90,
        equilibrium_strength=0.90,
    )

    rels = [
        TheoryRelation(
            source_id="obs_c1",
            target_id="hyp_enr",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="obs_c2",
            target_id="hyp_atom_low",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
    ]
    enr_bad = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-bad",
        cluster_id="cluster-c1",
        theory_id="neuro_coupling_theory",
        claimant_atom_ids=["hyp_enr"],
        projected_parameters={"DopamineDepletion": 0.9, "AmygdalaHyperactivity": 0.1},
        local_tenability=0.15,
        edge_tenabilities={},
        equilibrium_strengths={"hyp_enr": 0.22},
        aggregated_tenability=0.42,
        admissible_blur_delta=0.85,
        is_tenable=False,
        anomalies=["Law 'neuro_coupling' deviation 0.850 exceeds threshold"],
    )
    # Pure constraint edge anomaly with TS_local >= 0.5 and is_tenable=True must NOT trigger UNGROUNDED_AXIOM
    enr_edge_only = TheoreticalEnrichmentArtifact(
        enrichment_id="enr-edge-only",
        cluster_id="cluster-c2-ok",
        theory_id="ok_theory",
        claimant_atom_ids=[],
        local_tenability=0.95,
        aggregated_tenability=0.62,
        admissible_blur_delta=0.05,
        is_tenable=True,
        anomalies=[
            "Constraint edge 'CONSTRAINS' between a and b is untenable (TS_edge = 0.300, delta_C = 0.700)"
        ],
    )

    state = EpistemicDeficitArtifactsView(
        theory_atoms=[obs_c1, hyp_enr, obs_c2, hyp_atom_low, axiom_no_obs],
        theory_relations=rels,
        theoretical_enrichments=[enr_bad, enr_edge_only],
    )

    deficits = TheoryNetDeficitDetector().detect_deficits(state)
    ungrounded = [
        d for d in deficits if d.deficit_kind == EpistemicDeficitKind.UNGROUNDED_AXIOM
    ]
    by_id = {d.deficit_id: d for d in ungrounded}

    assert "ungrounded_axiom::neuro_coupling_theory::cluster-c1" in by_id
    assert "ungrounded_axiom::atom::hyp_atom_low" in by_id
    assert "ungrounded_axiom::atom::axiom_no_obs" in by_id
    assert "ungrounded_axiom::ok_theory::cluster-c2-ok" not in by_id

    d_enr = by_id["ungrounded_axiom::neuro_coupling_theory::cluster-c1"]
    assert d_enr.theory_id == "neuro_coupling_theory"
    assert d_enr.target_atom_ids == ["hyp_enr"]
    assert d_enr.target_chunk_ids == ["c1"]
    assert "amygdala_hyperactivity" in d_enr.theory_lens["required_dimensions"]
    assert "DopamineDepletion" in d_enr.theory_lens["parameter_names"]
    assert d_enr.theory_lens["claimant_atom_ids"] == ["hyp_enr"]
    assert "amygdala_hyperactivity" in d_enr.theory_lens["missing_dimensions"]
    assert d_enr.metrics["ts_local"] == pytest.approx(0.15)
    assert d_enr.metrics["aggregated_tenability"] == pytest.approx(0.42)
    assert d_enr.metrics["tau_star"] == pytest.approx(0.22)


# ---------------------------------------------------------------------------
# 5. Determinism, Ranking, Capping, Events & Fingerprinting
# ---------------------------------------------------------------------------


def test_detector_determinism_ranking_capping_events_and_fingerprint() -> None:
    """Verify deterministic ordering, capping, pass stamping, events, and fingerprint."""
    atoms = [
        TheoryAtom(
            id="a_low",
            text="Low prior",
            component_type="TheoreticalHypothesis",
            source_chunk_id="c1",
            modal_prior=0.4,
        ),
        TheoryAtom(
            id="a_mid",
            text="Mid prior",
            component_type="TheoreticalHypothesis",
            source_chunk_id="c2",
            local_tenability=0.35,
        ),
        TheoryAtom(
            id="a_high",
            text="High sev",
            component_type="TheoreticalHypothesis",
            source_chunk_id="c3",
            local_tenability=0.05,
        ),
    ]
    state_a = EpistemicDeficitArtifactsView(theory_atoms=atoms)
    state_b = EpistemicDeficitArtifactsView(theory_atoms=list(reversed(atoms)))

    detector = TheoryNetDeficitDetector(
        config=HermeneuticRefinementConfig(max_deficits_per_cycle=2)
    )
    assert isinstance(detector, EpistemicDeficitDetector)
    assert isinstance(detector, Fingerprintable)
    assert ensure_deficit_detector(detector) is detector

    recorder = _RecordingObserver()
    metrics = MetricsObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(recorder)
    emitter.register_observer(metrics)

    ctx = _make_context(run_id="run-rank-cap", refinement_pass=2)
    with use_event_emitter(emitter):
        res_a = detector.detect_deficits(state_a, refinement_pass=2, context=ctx)
        res_b = detector.detect_deficits(state_b, refinement_pass=2, context=None)

    assert len(res_a) == 2
    assert [d.deficit_id for d in res_a] == [d.deficit_id for d in res_b]
    assert [d.severity for d in res_a] == [d.severity for d in res_b]
    assert res_a[0].severity >= res_a[1].severity
    assert all(d.refinement_pass == 2 for d in res_a)

    # 2 events from res_a + 2 events from res_b
    detected_events = [
        e for e in recorder.events if isinstance(e, EpistemicDeficitDetected)
    ]
    assert len(detected_events) == 4
    assert detected_events[0].run_id == "run-rank-cap"
    assert detected_events[0].refinement_pass == 2
    assert detected_events[2].run_id is None
    assert sum(metrics.epistemic_deficits_detected.values()) == 4

    # Fingerprint sensitivity
    detector_alt = TheoryNetDeficitDetector(
        config=HermeneuticRefinementConfig(max_deficits_per_cycle=5)
    )
    assert detector.fingerprint() != detector_alt.fingerprint()


# ---------------------------------------------------------------------------
# 6. Phase6Runner Integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase6_runner_emits_deficit_artifacts_when_detector_configured() -> None:
    """Verify Phase6Runner integrates EpistemicDeficitDetector and find_components()."""
    with pytest.raises(TypeError, match="EpistemicDeficitDetector"):
        Phase6Runner(config=Phase6Config(), deficit_detector=object())

    obs_sup = TheoryAtom(
        id="obs_sup",
        text="Observation supporting claim.",
        component_type="ObservationUnit",
        source_chunk_id="c1",
        modal_prior=0.90,
    )
    obs_att = TheoryAtom(
        id="obs_att",
        text="Counter-observation attacking claim.",
        component_type="ObservationUnit",
        source_chunk_id="c2",
        modal_prior=0.90,
    )
    contested_claim = TheoryAtom(
        id="claim_contested",
        text="Contested hub hypothesis.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.50,
    )
    isolated_claim = TheoryAtom(
        id="claim_enthymeme",
        text="Major claim missing incoming support.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        modal_prior=0.80,
    )
    rels = [
        TheoryRelation(
            source_id="obs_sup",
            target_id="claim_contested",
            relation_type="SUPPORTS",
            confidence=0.95,
            inferential_warrant=1.0,
            scope="local",
        ),
        TheoryRelation(
            source_id="obs_att",
            target_id="claim_contested",
            relation_type="ATTACKS",
            confidence=0.95,
            inferential_warrant=1.0,
            scope="global",
        ),
    ]
    view = Phase4ArtifactsView(
        theory_atoms=[obs_sup, obs_att, contested_claim, isolated_claim],
        theory_relations=rels,
    )
    ctx = _make_context(run_id="run-p6-det", refinement_pass=1)

    # Without detector: zero EpistemicDeficitArtifacts
    runner_plain = Phase6Runner(config=Phase6Config(), schema=DEFAULT_SCHEMA)
    out_plain = await runner_plain.run(view, ctx)
    assert out_plain.of_kind(ArtifactKind.EPISTEMIC_DEFICIT) == []

    # With detector: discovers component & emits EpistemicDeficitArtifacts
    detector = TheoryNetDeficitDetector()
    runner_det = Phase6Runner(
        config=Phase6Config(),
        schema=DEFAULT_SCHEMA,
        deficit_detector=detector,
    )
    discovered = find_components(runner_det)
    assert discovered["deficit_detector"] is detector

    recorder = _RecordingObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(recorder)
    with use_event_emitter(emitter):
        out_det = await runner_det.run(view, ctx)

    deficit_envs = out_det.of_kind(ArtifactKind.EPISTEMIC_DEFICIT)
    assert len(deficit_envs) >= 2
    assert all(env.provenance.refinement_pass == 1 for env in deficit_envs)

    domain_deficits = [env.payload.to_domain() for env in deficit_envs]
    kinds = {d.deficit_kind for d in domain_deficits}
    assert EpistemicDeficitKind.ENTHYMEME_GAP in kinds
    assert EpistemicDeficitKind.POLYSEMY_COLLISION in kinds
    assert any(
        isinstance(ev, EpistemicDeficitDetected) and ev.refinement_pass == 1
        for ev in recorder.events
    )


# ---------------------------------------------------------------------------
# 7. TheoreticalEnrichmentRunner Integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_theoretical_enrichment_runner_emits_deficit_artifacts_after_reconvergence() -> (
    None
):
    """Verify TheoreticalEnrichmentRunner invokes deficit_detector after Step 4.5."""
    with pytest.raises(TypeError, match="EpistemicDeficitDetector"):
        TheoreticalEnrichmentRunner(deficit_detector=object())

    obs_1 = TheoryAtom(
        id="obs_1",
        text="Cluster 1 telemetry.",
        component_type="ObservationUnit",
        source_chunk_id="c1",
        measurements=[
            Measurement(dimension="dim_a", value=0.95),
            Measurement(dimension="dim_b", value=0.05),
        ],
    )
    hyp_1 = TheoryAtom(
        id="hyp_1",
        text="Parameter A equals Parameter B.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.88,
    )
    obs_2 = TheoryAtom(
        id="obs_2",
        text="Cluster 2 telemetry.",
        component_type="ObservationUnit",
        source_chunk_id="c2",
        measurements=[
            Measurement(dimension="dim_a", value=0.10),
            Measurement(dimension="dim_b", value=0.10),
        ],
    )
    hyp_2 = TheoryAtom(
        id="hyp_2",
        text="Second cluster matches first cluster parameter.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c2",
        modal_prior=0.80,
    )
    rels = [
        TheoryRelation(
            source_id="obs_1",
            target_id="hyp_1",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="obs_2",
            target_id="hyp_2",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        TheoryRelation(
            source_id="hyp_1",
            target_id="hyp_2",
            relation_type="CONSTRAINS",
            confidence=0.9,
            scope="global",
        ),
    ]

    strict_law = TheoryLaw(
        law_id="strict_equality",
        description="ParamA == ParamB",
        formula_expression="abs(ParamA - ParamB) * 0.9",
    )
    theory_def = TheoryElementDefinition(
        theory_id="unified_test_theory",
        name="Unified Test Theory",
        required_dimensions=["dim_a", "dim_b"],
        parameter_names=["ParamA", "ParamB"],
        laws=[strict_law],
        max_admissible_blur=1.0,
        claimant_hypothesis_ids=["hyp_1", "hyp_2"],
    )
    registry = TheoryRegistry(seed_theories=[theory_def])
    view = Phase4ArtifactsView(
        theory_atoms=[obs_1, hyp_1, obs_2, hyp_2], theory_relations=rels
    )
    ctx = _make_context(run_id="run-te-det", refinement_pass=1)

    # Without detector: zero EpistemicDeficitArtifacts
    runner_plain = TheoreticalEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(
            enabled=True, induce_theories=False, tenability_threshold=0.5
        ),
        schema=DEFAULT_SCHEMA,
        registry=registry,
        projector=GenericTheoryProjector(),
    )
    out_plain = await runner_plain.run(view, ctx)
    assert out_plain.of_kind(ArtifactKind.EPISTEMIC_DEFICIT) == []

    # With detector: discovers component & emits EpistemicDeficitArtifacts
    detector = TheoryNetDeficitDetector()
    runner_det = TheoreticalEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(
            enabled=True, induce_theories=False, tenability_threshold=0.5
        ),
        schema=DEFAULT_SCHEMA,
        registry=registry,
        projector=GenericTheoryProjector(),
        deficit_detector=detector,
    )
    assert find_components(runner_det)["deficit_detector"] is detector

    recorder = _RecordingObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(recorder)
    with use_event_emitter(emitter):
        out_det = await runner_det.run(view, ctx)

    assert len(out_det.of_kind(ArtifactKind.THEORETICAL_ENRICHMENT)) == 2
    deficit_envs = out_det.of_kind(ArtifactKind.EPISTEMIC_DEFICIT)
    assert len(deficit_envs) >= 2
    assert all(env.provenance.refinement_pass == 1 for env in deficit_envs)

    deficits = [env.payload.to_domain() for env in deficit_envs]
    kinds = {d.deficit_kind for d in deficits}
    assert EpistemicDeficitKind.UNGROUNDED_AXIOM in kinds
    assert EpistemicDeficitKind.POLYSEMY_COLLISION in kinds
    assert any(isinstance(ev, EpistemicDeficitDetected) for ev in recorder.events)


# ---------------------------------------------------------------------------
# 8. Static AST Zero-Reflection Guard & NumPy Docstrings
# ---------------------------------------------------------------------------


def test_step2_zero_reflection_and_docstrings() -> None:
    """Verify zero getattr/hasattr and complete docstrings in all Step 2 files."""
    pkg_root = Path(__file__).resolve().parent.parent / "episteme_pipeline"
    files_to_audit = [
        pkg_root / "artifacts" / "execution.py",
        pkg_root / "refinement" / "__init__.py",
        pkg_root / "refinement" / "detector.py",
        pkg_root / "phases" / "phase6_theorynet" / "runner.py",
        pkg_root / "post_processing" / "theoretical_enrichment" / "runner.py",
        Path(__file__).resolve(),
    ]

    violations: list[str] = []
    for py_file in files_to_audit:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):  # noqa: SIM102 baseline
                if node.func.id in {"getattr", "hasattr"}:
                    violations.append(
                        f"{py_file.name}:{node.lineno} calls {node.func.id}"
                    )

    assert not violations, "Forbidden getattr/hasattr calls:\n" + "\n".join(violations)

    import episteme_pipeline.refinement as refinement_pkg

    documented = [
        refinement_pkg,
        TheoryNetDeficitDetector,
        TheoryNetDeficitDetector.fingerprint,
        TheoryNetDeficitDetector.detect_deficits,
        Phase6Runner,
        Phase6Runner.run,
        TheoreticalEnrichmentRunner,
        TheoreticalEnrichmentRunner.run,
    ]
    missing_docs = [
        sym.__qualname__ if sym is not refinement_pkg else refinement_pkg.__name__
        for sym in documented
        if not (sym.__doc__ and sym.__doc__.strip())
    ]
    assert not missing_docs, f"Missing docstrings on: {missing_docs}"
