"""Deterministic unit and integration tests for ISSUE-050: Unified Stratified Epistemic Metamodel.

Validates all four acceptance criteria:
1. ADR-0007 header, ADR-0022, and docs/adr/index.md clarify supersession by ADR-0011 Addendum 2
   and ADR-0020 while retaining kappa-structural correspondence and structuralist poset hierarchy.
2. `modal_strength` is completely removed from `TheoryRelation` and `TheoryRelationArtifact`
   and consolidated on `TheoryAtom` / `TheoryAtomArtifact` (`modal_prior` / `modal_strength` /
   `base_score`), preventing M(phi)^2 double-penalization.
3. Empirical tenability (`TS_local`, `TS_edge`) from `TheoreticalEnrichmentRunner` feeds into
   D-QBAF equilibrium justification `tau*` (`equilibrium_strength` / `plausibility`), ensuring
   empirically falsified hypotheses (`TS < 0.5`) reflect degraded justification.
4. `docs/architecture/runtime_analysis.md` accurately documents the closed-form DAG and adaptive
   ODE cyclic complexity of Phase 6.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
)
from episteme_pipeline.artifacts.codecs import TheoryAtomCodec, TheoryRelationCodec
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase4ArtifactsView,
    Phase5ArtifactsView,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.config import Phase6Config, TheoreticalEnrichmentConfig
from episteme_pipeline.contracts.domain import (
    EpistemicStatus,
    Measurement,
    ScopeType,
    TenabilityResult,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.decision.modal_resolver import HybridModalResolver
from episteme_pipeline.graph.theory_graph_mapper import (
    theory_atom_to_graph_properties,
    theory_relation_from_graph_properties,
    theory_relation_to_graph_properties,
)
from episteme_pipeline.phases.phase6_theorynet.runner import Phase6Runner
from episteme_pipeline.post_processing.theoretical_enrichment import (
    TheoreticalEnrichmentRunner,
    TheoryElementDefinition,
    TheoryLaw,
    TheoryRegistry,
)
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


# ---------------------------------------------------------------------------
# 1. Ontological Separation & Removal of Edge-Level `modal_strength`
# ---------------------------------------------------------------------------
def test_modal_strength_removed_from_theory_relation_and_artifact() -> None:
    """Verify legacy aliases are absent and canonical fields round-trip on relations."""
    legacy_attrs = (
        "modal_strength",
        "inferential_force",
        "stance_probability",
        "class_probability",
        "empirical_accuracy",
        "model_confidence",
        "tenability",
    )
    for legacy_attr in legacy_attrs:
        assert legacy_attr not in TheoryRelation.model_fields
        assert legacy_attr not in TheoryRelationArtifact.model_fields

    rel = TheoryRelation(
        source_id="a1",
        target_id="a2",
        relation_type="SUPPORTS",
        confidence=0.90,
        scope="global",
        inferential_warrant=0.80,
        perception_stance_prob=0.90,
        perception_empirical_acc=0.92,
        structural_correspondence=0.88,
        edge_tenability=0.95,
    )
    for legacy_attr in legacy_attrs:
        assert not hasattr(rel, legacy_attr)
    assert rel.inferential_warrant == pytest.approx(0.80)
    assert rel.perception_stance_prob == pytest.approx(0.90)
    assert rel.perception_empirical_acc == pytest.approx(0.92)
    assert rel.structural_correspondence == pytest.approx(0.88)
    assert rel.edge_tenability == pytest.approx(0.95)

    # Verify graph serialization omits legacy keys and preserves orthogonal fields
    props = theory_relation_to_graph_properties(rel, polarity=1)
    assert "modal_strength" not in props
    assert "inferential_force" not in props
    assert props["inferential_warrant"] == pytest.approx(0.80)
    assert props["perception_stance_prob"] == pytest.approx(0.90)
    assert props["perception_empirical_acc"] == pytest.approx(0.92)
    assert props["structural_correspondence"] == pytest.approx(0.88)
    assert props["edge_tenability"] == pytest.approx(0.95)

    # Verify roundtrip from graph properties and artifact codec
    reconstructed = theory_relation_from_graph_properties("a1", "SUPPORTS", "a2", props)
    assert reconstructed.inferential_warrant == pytest.approx(0.80)
    assert reconstructed.structural_correspondence == pytest.approx(0.88)
    assert reconstructed.edge_tenability == pytest.approx(0.95)

    payload = TheoryRelationCodec.to_payload(rel)
    for legacy_attr in legacy_attrs:
        assert not hasattr(payload, legacy_attr)
    hydrated = TheoryRelationCodec.to_domain(payload)
    assert hydrated == rel


def test_theory_relation_compute_effective_weight_gating_and_tenability() -> None:
    """Verify deterministic compute_effective_weight free of node modality M(phi)."""
    rel = TheoryRelation(
        source_id="src",
        target_id="tgt",
        relation_type="CONSTRAINS",
        confidence=0.90,
        scope="global",
        inferential_warrant=0.80,
        perception_stance_prob=0.90,
        perception_empirical_acc=0.85,
        edge_tenability=0.50,
    )

    # Hard gating: W = I * 1.0 * TS_edge = 0.80 * 1.0 * 0.50 = 0.40
    assert rel.compute_effective_weight(gating_mode="hard", tau_p=0.70, tau_c=0.70) == pytest.approx(0.40)

    # Soft gating: W = I * (P * C) * TS_edge = 0.80 * (0.90 * 0.85) * 0.50 = 0.306
    assert rel.compute_effective_weight(gating_mode="soft", tau_p=0.70, tau_c=0.70) == pytest.approx(0.306)

    # Inadmissible threshold: P < tau_p or C < tau_c -> 0.0
    assert rel.compute_effective_weight(gating_mode="hard", tau_p=0.95, tau_c=0.70) == 0.0
    assert rel.compute_effective_weight(gating_mode="soft", tau_p=0.70, tau_c=0.90) == 0.0


def test_stratified_theory_atom_state_tuple_and_codec_roundtrip() -> None:
    """Verify TheoryAtom Stratified Epistemic State Tuple synchronization and lossless codec."""
    tenability = TenabilityResult(
        local_score=0.40,
        edge_scores={"a1->CONSTRAINS->a2": 0.80},
        aggregated_score=0.52,
        tightest_blur=0.60,
        is_tenable=False,
        anomalies=["Blur delta exceeds threshold"],
    )
    atom = TheoryAtom(
        id="atom_stratified",
        text="Es könnte sein, dass die Anschauung empirisch bedingt ist.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_1",
        modal_prior=0.80,
        tenability=tenability,
        equilibrium_strength=0.35,
        controversy_volatility=0.12,
        resolver_type="hybrid_guardrail",
        syntax_bounds=(0.20, 0.85),
    )

    # Layer 1 canonical modal_prior (no legacy alias attributes)
    assert atom.modal_prior == pytest.approx(0.80)
    assert not hasattr(atom, "modal_strength")
    assert not hasattr(atom, "base_score")
    assert not hasattr(atom, "plausibility")

    # Layer 3 synchronization
    assert atom.local_tenability == pytest.approx(0.40)
    # Effective prior = tau_0(a) * TS_local(a) = 0.80 * 0.40 = 0.32
    assert atom.effective_base_prior() == pytest.approx(0.32)

    # Layer 4 canonical equilibrium & metadata
    assert atom.equilibrium_strength == pytest.approx(0.35)
    assert atom.controversy_volatility == pytest.approx(0.12)
    assert atom.resolver_type == "hybrid_guardrail"
    assert atom.syntax_bounds == (0.20, 0.85)

    # Graph property serialization contains canonical keys only
    atom_props = theory_atom_to_graph_properties(atom)
    assert atom_props["modal_prior"] == pytest.approx(0.80)
    assert atom_props["local_tenability"] == pytest.approx(0.40)
    assert atom_props["equilibrium_strength"] == pytest.approx(0.35)
    assert atom_props["controversy_volatility"] == pytest.approx(0.12)
    assert "modal_strength" not in atom_props
    assert "base_score" not in atom_props
    assert "plausibility" not in atom_props

    # Codec roundtrip
    payload = TheoryAtomCodec.to_payload(atom)
    assert payload.modal_prior == pytest.approx(0.80)
    assert payload.local_tenability == pytest.approx(0.40)
    assert payload.equilibrium_strength == pytest.approx(0.35)
    assert payload.controversy_volatility == pytest.approx(0.12)
    assert payload.resolver_type == "hybrid_guardrail"
    assert payload.syntax_bounds == (0.20, 0.85)

    hydrated = TheoryAtomCodec.to_domain(payload)
    assert hydrated == atom

    # JSON round-trip preserves unset modal_prior / inferential_warrant as None
    # so TheoryNetProjector derives them instead of treating defaults as overrides.
    atom_unset = TheoryAtom(
        id="atom_unset",
        text="Perhaps empirical space is emergent.",
        component_type="TentativeConjecture",
        source_chunk_id="chunk_1",
    )
    atom_target = TheoryAtom(
        id="atom_target",
        text="Target claim.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_1",
    )
    rel_unset = TheoryRelation(
        source_id="atom_unset",
        target_id="atom_target",
        relation_type="ENTAILS",
        confidence=0.90,
        scope="local",
    )
    env_atom_json = build_argument_component_artifact(
        atom_unset, run_id="run-json", phase_name="P4", method="m"
    ).model_dump_json()
    env_rel_json = build_argument_relation_artifact(
        rel_unset, run_id="run-json", phase_name="P4", method="m"
    ).model_dump_json()

    reloaded_atom_env = ArtifactEnvelope[TheoryAtomArtifact].model_validate_json(env_atom_json)
    reloaded_rel_env = ArtifactEnvelope[TheoryRelationArtifact].model_validate_json(env_rel_json)
    assert reloaded_atom_env.payload.modal_prior is None
    assert reloaded_rel_env.payload.inferential_warrant is None

    projector = TheoryNetProjector(schema=DEFAULT_SCHEMA)
    projected = projector.project(
        Phase4ArtifactsView(
            theory_atoms=[reloaded_atom_env.payload.to_domain(), atom_target],
            theory_relations=[reloaded_rel_env.payload.to_domain()],
        )
    )
    assert projected.atoms[0].modal_prior == pytest.approx(0.35)
    assert projected.relations[0].inferential_warrant == pytest.approx(1.00)


@pytest.mark.asyncio
async def test_hybrid_modal_resolver_populates_resolver_type_and_syntax_bounds() -> None:
    """Verify HybridModalResolver populates resolver_type, syntax_bounds, and modal_prior on TheoryAtom."""
    resolver = HybridModalResolver.create(config={"mode": "structural_only"}, decision_engine=None)
    atom = TheoryAtom(
        id="atom_kant_axiom",
        text="Der Raum ist notwendig eine Vorstellung a priori.",
        component_type="CoreAxiom",
        source_chunk_id="c1",
        scope_type=ScopeType.ESSENTIELLER_ALLSATZ,
        epistemic_status=EpistemicStatus.ANALYTISCH,
    )
    score = await resolver.resolve_modality(atom)
    assert score > 0.85
    assert atom.modal_prior == pytest.approx(score)
    assert atom.resolver_type == "structural"
    assert atom.syntax_bounds is not None
    assert len(atom.syntax_bounds) == 2
    assert atom.syntax_bounds[0] <= score <= atom.syntax_bounds[1]


def test_projector_idempotency_and_stance_prob_preservation_under_edge_tenability() -> None:
    """Verify TheoryNetProjector does not double-penalize TS_edge^2 or drop perception_stance_prob."""
    projector = TheoryNetProjector(schema=DEFAULT_SCHEMA)
    assert projector.use_continuous is True
    assert projector.solver.use_continuous is True
    assert projector.fingerprint()["use_continuous"] is True

    a1 = TheoryAtom(
        id="a1",
        text="Premise",
        component_type="ObservationUnit",
        source_chunk_id="c1",
        modal_prior=0.80,
    )
    a2 = TheoryAtom(
        id="a2",
        text="Conclusion",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.50,
    )
    rel = TheoryRelation(
        source_id="a1",
        target_id="a2",
        relation_type="SUPPORTS",
        confidence=0.90,
        inferential_warrant=0.80,
        perception_stance_prob=0.50,
        edge_tenability=0.50,
        scope="local",
    )
    # Effective weight = I * P * TS_edge = 0.80 * 0.50 * 0.50 = 0.20 (NOT 0.10 and NOT 0.40)
    assert rel.effective_weight == pytest.approx(0.20)
    edges = projector._to_theory_edges([rel])
    assert edges[0].effective_weight == pytest.approx(0.20)

    # Projecting repeatedly must be strictly idempotent
    net1 = projector.project(Phase4ArtifactsView(theory_atoms=[a1, a2], theory_relations=[rel]))
    net2 = projector.project(Phase4ArtifactsView(theory_atoms=net1.atoms, theory_relations=net1.relations))
    assert net1.atoms[1].equilibrium_strength == pytest.approx(net2.atoms[1].equilibrium_strength)


# ---------------------------------------------------------------------------
# 2. Closed-Loop Coupling: Empirical Tenability -> D-QBAF Equilibrium tau*(a)
# ---------------------------------------------------------------------------


def test_projector_modulates_dqbaf_equilibrium_by_local_and_edge_tenability() -> None:
    """Verify empirically falsified hypotheses (TS_local < 0.5) suffer degraded D-QBAF justification."""
    projector = TheoryNetProjector(schema=DEFAULT_SCHEMA)

    # Case 1: Corroborated hypothesis (modal_prior=0.85, local_tenability=0.95) supporting a conclusion
    hyp_corroborated = TheoryAtom(
        id="hyp_good",
        text="Dopaminergic coupling law holds under fMRI measurements.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.85,
        local_tenability=0.95,
    )
    conclusion_good = TheoryAtom(
        id="claim_good",
        text="Downstream diagnostic claim.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.55,
    )
    rel_good = TheoryRelation(
        source_id="hyp_good",
        target_id="claim_good",
        relation_type="SUPPORTS",
        confidence=0.95,
        inferential_warrant=0.90,
        edge_tenability=0.95,
        scope="local",
    )

    net_good = projector.project(
        Phase4ArtifactsView(
            theory_atoms=[hyp_corroborated, conclusion_good],
            theory_relations=[rel_good],
        )
    )
    atoms_good = {a.id: a for a in net_good.atoms}

    # Case 2: Empirically falsified hypothesis (modal_prior=0.85, local_tenability=0.15 < 0.5)
    hyp_falsified = TheoryAtom(
        id="hyp_bad",
        text="Falsified hypothesis with high authorial certainty.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.85,
        local_tenability=0.15,
    )
    conclusion_bad = TheoryAtom(
        id="claim_bad",
        text="Downstream diagnostic claim.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c1",
        modal_prior=0.55,
    )
    rel_bad = TheoryRelation(
        source_id="hyp_bad",
        target_id="claim_bad",
        relation_type="SUPPORTS",
        confidence=0.95,
        inferential_warrant=0.90,
        edge_tenability=0.20,
        scope="local",
    )

    net_bad = projector.project(
        Phase4ArtifactsView(
            theory_atoms=[hyp_falsified, conclusion_bad],
            theory_relations=[rel_bad],
        )
    )
    atoms_bad = {a.id: a for a in net_bad.atoms}

    # Falsified hypothesis (TS_local = 0.15 < 0.5) MUST have degraded equilibrium justification < 0.5
    assert atoms_good["hyp_good"].equilibrium_strength is not None
    assert atoms_bad["hyp_bad"].equilibrium_strength is not None
    assert atoms_good["hyp_good"].equilibrium_strength > 0.75
    assert atoms_bad["hyp_bad"].equilibrium_strength < 0.50

    # Downstream conclusion supported by falsified hypothesis & low-tenability edge is also degraded
    assert atoms_good["claim_good"].equilibrium_strength > atoms_bad["claim_bad"].equilibrium_strength


@pytest.mark.asyncio
async def test_theoretical_enrichment_runner_reconverges_dqbaf_on_falsified_hypothesis() -> None:
    """Verify TheoreticalEnrichmentRunner feeds TS_local/TS_edge back into D-QBAF equilibrium tau*."""
    # Empirical observation severely violates the theory's law:
    # Law requires DopamineDepletion == AmygdalaHyperactivity, but observation has 1.0 vs 0.0 -> dev = 0.9 -> TS_local = 0.10 < 0.5
    obs_atom = TheoryAtom(
        id="obs_patient_falsifying",
        text="Patient shows 100% dopamine depletion with 0% amygdala hyperactivity.",
        component_type="ObservationUnit",
        source_chunk_id="chunk_falsification",
        confidence=0.95,
        modal_prior=0.90,
        measurements=[
            Measurement(dimension="dopamine_level", value=1.0, unit="ratio"),
            Measurement(dimension="amygdala_hyperactivity", value=0.0, unit="ratio"),
        ],
    )
    hyp_atom = TheoryAtom(
        id="hyp_falsified_claim",
        text="Dopamine depletion is strictly proportional to amygdala hyperactivity.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_falsification",
        confidence=0.92,
        modal_prior=0.88,
    )
    downstream_claim = TheoryAtom(
        id="claim_downstream",
        text="Therefore therapy X targeting amygdala hyperactivity will restore dopamine.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_downstream",
        confidence=0.85,
        modal_prior=0.60,
    )
    rel_support = TheoryRelation(
        source_id="hyp_falsified_claim",
        target_id="claim_downstream",
        relation_type="SUPPORTS",
        confidence=0.90,
        inferential_warrant=0.90,
        scope="global",
    )

    ctx = ArtifactExecutionContext(
        run_id="run-issue-050",
        manifest=RunManifest(run_id="run-issue-050"),
        pipeline_input=PipelineInput(source_paths=[]),
    )

    # Step 1: Run Phase 6 BEFORE Theoretical Enrichment (unmodulated prior = 0.88)
    initial_collection = ArtifactCollection(
        [
            build_argument_component_artifact(obs_atom, run_id="run-issue-050", phase_name="P4", method="m"),
            build_argument_component_artifact(hyp_atom, run_id="run-issue-050", phase_name="P4", method="m"),
            build_argument_component_artifact(downstream_claim, run_id="run-issue-050", phase_name="P4", method="m"),
            build_argument_relation_artifact(rel_support, run_id="run-issue-050", phase_name="P4", method="m"),
        ]
    )
    p5_view = Phase5ArtifactsView.from_collection(initial_collection)
    p6_runner = Phase6Runner(config=Phase6Config(), schema=DEFAULT_SCHEMA, graph_store=None)
    p6_out = await p6_runner.run(p5_view, ctx)

    p6_atoms = {a.payload.component_id: a.payload for a in p6_out.of_kind(ArtifactKind.THEORY_ATOM)}
    pre_enrichment_tau = p6_atoms["hyp_falsified_claim"].equilibrium_strength
    pre_downstream_tau = p6_atoms["claim_downstream"].equilibrium_strength
    assert pre_enrichment_tau == pytest.approx(0.88)
    assert pre_downstream_tau is not None and pre_downstream_tau > 0.60

    # Step 2: Run TheoreticalEnrichmentRunner with a strict coupling law falsified by the measurements
    strict_law = TheoryLaw(
        law_id="strict_coupling",
        description="Strict equality between dopamine and amygdala",
        formula_expression="abs(DopamineDepletion - AmygdalaHyperactivity) * 0.9",
    )
    theory_def = TheoryElementDefinition(
        theory_id="falsified_neuro_theory",
        name="Falsified Neuro Theory",
        required_dimensions=["dopamine_level", "amygdala_hyperactivity"],
        parameter_names=["DopamineDepletion", "AmygdalaHyperactivity"],
        laws=[strict_law],
        max_admissible_blur=1.0,
        claimant_hypothesis_ids=["hyp_falsified_claim"],
    )
    registry = TheoryRegistry(seed_theories=[theory_def])
    mock_store = AsyncMock()

    combined_after_p6 = ArtifactCollection(initial_collection.artifacts + p6_out.artifacts)
    view_for_enrichment = Phase5ArtifactsView.from_collection(combined_after_p6)

    te_runner = TheoreticalEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(enabled=True, induce_theories=False, tenability_threshold=0.5),
        schema=DEFAULT_SCHEMA,
        graph_store=mock_store,
        registry=registry,
    )
    te_out = await te_runner.run(view_for_enrichment, ctx)

    # Verify TheoreticalEnrichmentArtifact records TS_local < 0.5 and re-converged equilibrium_strengths
    te_envelopes = [
        env
        for env in te_out.of_kind(ArtifactKind.THEORETICAL_ENRICHMENT)
        if env.payload.cluster_id == "cluster-chunk_falsification"
    ]
    assert len(te_envelopes) == 1
    te_payload = te_envelopes[0].payload
    assert te_payload.local_tenability < 0.50
    assert te_payload.is_tenable is False
    assert "hyp_falsified_claim" in te_payload.equilibrium_strengths
    assert te_payload.equilibrium_strengths["hyp_falsified_claim"] < 0.50

    # Verify emitted TheoryAtomArtifact envelopes reflect degraded D-QBAF justification tau* < 0.50
    final_collection = ArtifactCollection(combined_after_p6.artifacts + te_out.artifacts)
    final_view = Phase5ArtifactsView.from_collection(final_collection)
    final_atoms = {a.id: a for a in final_view.canonical_theory_atoms}

    falsified_final = final_atoms["hyp_falsified_claim"]
    downstream_final = final_atoms["claim_downstream"]
    assert falsified_final.local_tenability is not None and falsified_final.local_tenability < 0.50
    assert falsified_final.equilibrium_strength is not None and falsified_final.equilibrium_strength < 0.50
    # Modal prior tau_0(a) remains preserved (0.88), while equilibrium tau*(a) is degraded (< 0.50)
    assert falsified_final.modal_prior == pytest.approx(0.88)
    # Downstream claim's justification also dropped relative to pre-enrichment
    assert downstream_final.equilibrium_strength is not None
    assert downstream_final.equilibrium_strength < pre_downstream_tau

    # Verify Reverse Order (TheoreticalEnrichment -> Phase6Runner) produces the exact same equilibrium
    p6_after_te = await p6_runner.run(final_view, ctx)
    p6_re_atoms = {a.payload.component_id: a.payload for a in p6_after_te.of_kind(ArtifactKind.THEORY_ATOM)}
    assert p6_re_atoms["hyp_falsified_claim"].equilibrium_strength == pytest.approx(
        falsified_final.equilibrium_strength
    )


# ---------------------------------------------------------------------------
# 3. ADR & Architecture Documentation Alignment
# ---------------------------------------------------------------------------


def test_adr_and_runtime_analysis_documentation_sync() -> None:
    """Verify ADR-0007, ADR-0022, docs/adr/index.md, and runtime_analysis.md are synchronized."""
    repo_root = Path(__file__).resolve().parents[3]

    adr_0007 = (repo_root / "docs" / "adr" / "0007-tf-structural-correspondence.md").read_text(encoding="utf-8")
    assert "Partially Superseded" in adr_0007
    assert "ADR-0011" in adr_0007
    assert "ADR-0020" in adr_0007
    assert "ADR-0022" in adr_0007

    adr_0022_path = repo_root / "docs" / "adr" / "0022-unified-stratified-epistemic-metamodel.md"
    assert adr_0022_path.exists()
    adr_0022 = adr_0022_path.read_text(encoding="utf-8")
    assert "Stratified Epistemic State Tuple" in adr_0022

    adr_index = (repo_root / "docs" / "adr" / "index.md").read_text(encoding="utf-8")
    assert "0022" in adr_index
    assert "Partially Superseded" in adr_index

    runtime_doc = (repo_root / "docs" / "architecture" / "runtime_analysis.md").read_text(encoding="utf-8")
    assert "I=5" not in runtime_doc
    assert "RK45" in runtime_doc
    assert "Radau" in runtime_doc
    assert "closed-form" in runtime_doc.lower()
