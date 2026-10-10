"""Unit and integration tests for Theoretical Enrichment and Tenability Evaluation.

Tests dynamic LLM-driven Theory-Element induction (Macro Stage), multi-theory lenses
over shared empirical clusters (Micro Stage), safe formula law evaluation, local
tenability optimization (TS_local), intertheoretical consistency (TS_edge), and
dynamic pipeline runner / post-processor plugging with ZERO hardcoded theories.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import PipelineConfig, TheoreticalEnrichmentConfig
from episteme_pipeline.contracts.domain import (
    Measurement,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.context import use_event_emitter
from episteme_pipeline.post_processing.theoretical_enrichment import (
    ClusterProjectionOutput,
    EmpiricalCluster,
    GenericTheoryProjector,
    InducedTheoryElement,
    InducedTheoryLaw,
    LLMTheoryInducer,
    LLMTheoryProjector,
    SafeFormulaEvaluator,
    TenabilityEvaluationCompleted,
    TenabilitySolver,
    TheoreticalClusterIdentified,
    TheoreticalEnrichmentRunner,
    TheoreticalParametersProjected,
    TheoryElementDefinition,
    TheoryInductionOutput,
    TheoryLaw,
    TheoryRegistry,
)
from episteme_pipeline.runs.models import RunManifest


@pytest.fixture
def mixed_empirical_atoms() -> list[TheoryAtom]:
    """Sample empirical cluster containing mixed Neurological and Psychoanalytic data."""
    return [
        TheoryAtom(
            id="obs_neuro_1",
            text="fMRI BOLD scan shows 75% hyperactivity in right amygdala and dopaminergic depletion.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_patient_001",
            confidence=0.95,
            measurements=[
                Measurement(dimension="amygdala_hyperactivity", value=0.75, unit="index"),
                Measurement(dimension="dopamine_level", value=0.70, unit="depletion_ratio"),
            ],
        ),
        TheoryAtom(
            id="obs_freud_1",
            text="Patient exhibits 80% repetition frequency of trauma narrative with intense resistance.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_patient_001",
            confidence=0.92,
            measurements=[
                Measurement(dimension="verbal_repetitions", value=0.80, unit="frequency"),
                Measurement(dimension="affect_intensity", value=0.85, unit="scale"),
            ],
        ),
        TheoryAtom(
            id="hyp_neuro_1",
            text="Patient suffers from severe dopaminergic mesolimbic disinhibition.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_patient_001",
            confidence=0.88,
        ),
        TheoryAtom(
            id="hyp_freud_1",
            text="Patient displays strong unconscious repression with affective displacement.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_patient_001",
            confidence=0.86,
        ),
    ]


@pytest.fixture
def mixed_theory_relations() -> list[TheoryRelation]:
    """Intertheoretical links connecting Psychoanalytic and Neurological hypotheses."""
    return [
        TheoryRelation(
            source_id="hyp_freud_1",
            target_id="hyp_neuro_1",
            relation_type="CONSTRAINS",
            confidence=0.90,
            scope="local",
        ),
        TheoryRelation(
            source_id="hyp_freud_1",
            target_id="hyp_neuro_1",
            relation_type="REDUCES_TO",
            confidence=0.85,
            scope="local",
        ),
    ]


@pytest.fixture
def seeded_theories() -> list[TheoryElementDefinition]:
    """Explicitly seeded Theory-Elements for isolated unit tests."""
    neuro_law = TheoryLaw(
        law_id="neuro_coupling",
        description="Coupling between dopamine and amygdala hyperactivity",
        formula_expression="abs(DopamineDepletion - AmygdalaHyperactivity) * 0.5",
    )
    neuro = TheoryElementDefinition(
        theory_id="neurology",
        name="Neurology",
        required_dimensions=["amygdala_hyperactivity", "dopamine_level"],
        parameter_names=["DopamineDepletion", "AmygdalaHyperactivity"],
        laws=[neuro_law],
        max_admissible_blur=1.0,
    )

    freud_law = TheoryLaw(
        law_id="freud_proportionality",
        description="Proportionality between Repression and Resistance",
        formula_expression="abs(RepressionMagnitude - UnconsciousResistance) * 0.5",
    )
    freud = TheoryElementDefinition(
        theory_id="psychoanalysis",
        name="Psychoanalysis",
        required_dimensions=["verbal_repetitions", "affect_intensity"],
        parameter_names=["RepressionMagnitude", "UnconsciousResistance"],
        laws=[freud_law],
        max_admissible_blur=1.0,
    )
    return [neuro, freud]


def test_safe_formula_evaluator():
    """Verify safe AST formula evaluation on diverse mathematical expressions."""
    # 1. Linear law
    assert SafeFormulaEvaluator.evaluate("abs(a - b) * 0.5", {"a": 0.70, "b": 0.72}) == pytest.approx(0.01)

    # 2. Equality constraint
    assert SafeFormulaEvaluator.evaluate("abs(Force - Mass * Acceleration)", {"Force": 10.0, "Mass": 2.0, "Acceleration": 5.0}) == 0.0

    # 3. Minimum / maximum bounding
    assert SafeFormulaEvaluator.evaluate("max(0.0, a - b)", {"a": 0.8, "b": 0.5}) == pytest.approx(0.3)
    assert SafeFormulaEvaluator.evaluate("max(0.0, a - b)", {"a": 0.3, "b": 0.5}) == 0.0

    # 4. Zero division protection
    assert SafeFormulaEvaluator.evaluate("a / b", {"a": 1.0, "b": 0.0}) == 1.0

    # 5. Missing parameter fallback
    assert SafeFormulaEvaluator.evaluate("abs(MissingParam - 0.5)", {}) == pytest.approx(0.5)

    # 6. Syntax error safety
    assert SafeFormulaEvaluator.evaluate("invalid syntax !!!", {}) == 1.0


def test_theory_law_with_formula_expression():
    """Verify that TheoryLaw evaluates formula_expression correctly."""
    law = TheoryLaw(
        law_id="test_law",
        description="Test formula law",
        formula_expression="abs(P1 - P2) * 0.5",
    )
    dev = law.compute_deviation({"P1": 0.80, "P2": 0.84})
    assert dev == pytest.approx(0.02)


def test_empirical_cluster_identification(mixed_empirical_atoms, mixed_theory_relations):
    """Test Step 1: Identifying empirical clusters as Intended Applications (I)."""
    runner = TheoreticalEnrichmentRunner()
    clusters = runner._identify_empirical_clusters(
        mixed_empirical_atoms, mixed_theory_relations
    )

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.cluster_id == "cluster-chunk_patient_001"
    assert len(cluster.observations) == 4
    assert len(cluster.relations) == 2

    dims = cluster.available_dimensions
    assert "amygdala_hyperactivity" in dims
    assert "dopamine_level" in dims
    assert "verbal_repetitions" in dims
    assert "affect_intensity" in dims


def test_multi_theory_lens_projections(mixed_empirical_atoms, seeded_theories):
    """Test Step 2: Running generic projector over the exact same cluster for distinct theories."""
    cluster = EmpiricalCluster(
        cluster_id="cluster-001",
        observations=mixed_empirical_atoms,
        claimant_theory_ids=["neurology", "psychoanalysis"],
    )

    registry = TheoryRegistry(seed_theories=seeded_theories)
    neuro_def = registry.get("neurology")
    freud_def = registry.get("psychoanalysis")

    # Domain-agnostic generic projector projecting against both theoretical schemas
    projector = GenericTheoryProjector()

    # 1. Neurology theoretical schema
    neuro_params = projector.project(cluster, neuro_def)
    assert neuro_params["DopamineDepletion"] == pytest.approx(0.70, abs=0.05)
    assert neuro_params["AmygdalaHyperactivity"] == pytest.approx(0.75, abs=0.05)

    # 2. Psychoanalysis theoretical schema
    freud_params = projector.project(cluster, freud_def)
    assert freud_params["RepressionMagnitude"] == pytest.approx(0.80, abs=0.05)
    assert freud_params["UnconsciousResistance"] == pytest.approx(0.85, abs=0.05)


def test_generic_projector_text_token_fallback() -> None:
    """Verify that GenericTheoryProjector extracts parameters from textual mentions when measurements are absent."""
    cluster = EmpiricalCluster(
        cluster_id="cluster-text-only",
        observations=[
            TheoryAtom(
                id="obs_text_1",
                text="Patient exhibits high dopamine depletion of 65% in recent scans.",
                component_type="ObservationUnit",
                source_chunk_id="chunk_001",
                confidence=0.9,
                measurements=[],
            )
        ],
        claimant_theory_ids=["neurology"],
    )
    theory = TheoryElementDefinition(
        theory_id="neurology",
        name="Neurology",
        required_dimensions=["unrelated_dim"],
        parameter_names=["DopamineDepletion"],
        laws=[],
    )
    projector = GenericTheoryProjector()
    params = projector.project(cluster, theory)
    assert params["DopamineDepletion"] == pytest.approx(0.65, abs=0.01)


def test_generic_projector_ordinal_positional_fallback() -> None:
    """Verify positional alignment when parameter names and dimension names are disjoint."""
    cluster = EmpiricalCluster(
        cluster_id="cluster-disjoint",
        observations=[
            TheoryAtom(
                id="obs_disjoint_1",
                text="Empirical observation with disjoint vocabulary.",
                component_type="ObservationUnit",
                source_chunk_id="chunk_002",
                confidence=0.9,
                measurements=[
                    Measurement(dimension="x_dim", value=0.42, unit="ratio"),
                ],
            )
        ],
        claimant_theory_ids=["abstract_theory"],
    )
    theory = TheoryElementDefinition(
        theory_id="abstract_theory",
        name="AbstractTheory",
        required_dimensions=["x_dim"],
        parameter_names=["LatentTheta"],
        laws=[],
    )
    projector = GenericTheoryProjector()
    params = projector.project(cluster, theory)
    assert params["LatentTheta"] == pytest.approx(0.42, abs=0.01)


def test_local_tenability_solver(seeded_theories):
    """Test Step 3: Local Tenability optimization (TS_local = sup { 1 - delta })."""
    solver = TenabilitySolver(anomaly_threshold=0.5)
    registry = TheoryRegistry(seed_theories=seeded_theories)
    neuro_def = registry.get("neurology")

    # Coherent parameters (Dopamine and Amygdala align within blur)
    coherent_params = {"DopamineDepletion": 0.70, "AmygdalaHyperactivity": 0.72}
    ts_local, delta_star, anomalies = solver.solve_local_tenability(coherent_params, neuro_def)

    assert ts_local > 0.90
    assert delta_star < 0.10
    assert len(anomalies) == 0

    # Incoherent parameters
    ts_bad, delta_bad, anomalies_bad = solver.solve_local_tenability(
        {"DopamineDepletion": 1.0, "AmygdalaHyperactivity": 0.0}, neuro_def
    )
    assert ts_bad <= 0.60
    assert delta_bad == pytest.approx(0.50)


def test_edge_tenability_and_anomaly_detection():
    """Test Step 4: Intertheoretical Consistency across CONSTRAINS and REDUCES_TO edges."""
    solver = TenabilitySolver(anomaly_threshold=0.5)

    rel = TheoryRelation(
        source_id="hyp_freud_1",
        target_id="hyp_neuro_1",
        relation_type="CONSTRAINS",
        confidence=0.90,
        scope="local",
    )

    # Coherent mixed model
    ts_edge, delta_c, anomalies = solver.solve_edge_tenability(
        {"RepressionMagnitude": 0.80}, {"AmygdalaHyperactivity": 0.75}, rel
    )
    assert ts_edge == pytest.approx(0.95, abs=0.05)
    assert delta_c == pytest.approx(0.05, abs=0.05)
    assert len(anomalies) == 0

    # Incompatible mixed model
    ts_bad, delta_bad, bad_anomalies = solver.solve_edge_tenability(
        {"RepressionMagnitude": 0.90}, {"AmygdalaHyperactivity": 0.10}, rel
    )
    assert ts_bad < 0.5
    assert len(bad_anomalies) > 0


@pytest.mark.asyncio
async def test_llm_theory_inducer(mixed_empirical_atoms, mixed_theory_relations):
    """Test Macro Stage 1: Dynamic LLM Theory-Element induction."""
    mock_llm = MagicMock()
    mock_output = TheoryInductionOutput(
        theories=[
            InducedTheoryElement(
                theory_id="induced_neuropsychoanalysis",
                name="Induced Neuropsychoanalysis",
                description="Integrated model linking affective narrative to mesolimbic circuits.",
                claimant_hypothesis_ids=["hyp_neuro_1", "hyp_freud_1"],
                required_dimensions=["amygdala_hyperactivity", "verbal_repetitions"],
                parameter_names=["AffectDissonance", "NeuralDisinhibition"],
                laws=[
                    InducedTheoryLaw(
                        law_id="dissonance_coupling",
                        description="Coupling between affect dissonance and neural disinhibition",
                        formula_expression="abs(AffectDissonance - NeuralDisinhibition) * 0.5",
                        involved_parameters=["AffectDissonance", "NeuralDisinhibition"],
                    )
                ],
                max_admissible_blur=1.0,
            )
        ]
    )
    mock_llm.predict_structured = AsyncMock(return_value=mock_output)

    inducer = LLMTheoryInducer(llm=mock_llm)
    induced = await inducer.induce_theories(mixed_empirical_atoms, mixed_theory_relations)

    assert len(induced) == 1
    theory = induced[0]
    assert theory.theory_id == "induced_neuropsychoanalysis"
    assert theory.parameter_names == ["AffectDissonance", "NeuralDisinhibition"]
    assert len(theory.laws) == 1
    assert theory.laws[0].formula_expression == "abs(AffectDissonance - NeuralDisinhibition) * 0.5"

    # Verify law evaluation on induced theory
    dev = theory.laws[0].compute_deviation({"AffectDissonance": 0.6, "NeuralDisinhibition": 0.64})
    assert dev == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_llm_cluster_projector(mixed_empirical_atoms, seeded_theories):
    """Test Micro Stage 2: Dynamic LLM cluster parameter projection."""
    mock_llm = MagicMock()
    mock_output = ClusterProjectionOutput(
        cluster_id="cluster-001",
        theory_id="neurology",
        observed_dimensions={"amygdala_hyperactivity": 0.75, "dopamine_level": 0.70},
        projected_parameters={"DopamineDepletion": 0.72, "AmygdalaHyperactivity": 0.74},
        fit_rationale="Observed fMRI and dopamine measurements indicate consistent depletion.",
    )
    mock_llm.predict_structured = AsyncMock(return_value=mock_output)

    projector = LLMTheoryProjector(llm=mock_llm)
    cluster = EmpiricalCluster(
        cluster_id="cluster-001",
        observations=mixed_empirical_atoms,
        claimant_theory_ids=["neurology"],
    )

    theory = seeded_theories[0]
    params = await projector.aproject(cluster, theory)

    assert "DopamineDepletion" in params
    assert "AmygdalaHyperactivity" in params
    assert params["DopamineDepletion"] == pytest.approx(0.70, abs=0.05)


@pytest.mark.asyncio
async def test_theoretical_enrichment_runner_end_to_end_with_dynamic_induction(
    mixed_empirical_atoms, mixed_theory_relations
):
    """End-to-end execution of runner with ZERO hardcoded theories, using LLM induction."""
    class _TestObserver:
        def __init__(self):
            self.events = []
        def on_event(self, e):
            self.events.append(e)

    obs = _TestObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(obs)

    # Setup mock LLM that handles induction first, then cluster projection
    mock_llm = MagicMock()

    induced_theories_output = TheoryInductionOutput(
        theories=[
            InducedTheoryElement(
                theory_id="autonomous_neuro",
                name="Autonomous Neurology",
                description="Model of neural disinhibition",
                claimant_hypothesis_ids=["hyp_neuro_1"],
                required_dimensions=["amygdala_hyperactivity", "dopamine_level"],
                parameter_names=["DopamineDepletion", "AmygdalaHyperactivity"],
                laws=[
                    InducedTheoryLaw(
                        law_id="autonomous_law",
                        description="Coupling law",
                        formula_expression="abs(DopamineDepletion - AmygdalaHyperactivity) * 0.5",
                        involved_parameters=["DopamineDepletion", "AmygdalaHyperactivity"],
                    )
                ],
                max_admissible_blur=1.0,
            )
        ]
    )

    projection_output = ClusterProjectionOutput(
        cluster_id="cluster-chunk_patient_001",
        theory_id="autonomous_neuro",
        observed_dimensions={"amygdala_hyperactivity": 0.75, "dopamine_level": 0.70},
        projected_parameters={"DopamineDepletion": 0.70, "AmygdalaHyperactivity": 0.75},
        fit_rationale="Derived from patient scan data",
    )

    async def mock_predict_structured(output_cls, *args, **kwargs):
        if output_cls == TheoryInductionOutput:
            return induced_theories_output
        elif output_cls == ClusterProjectionOutput:
            return projection_output
        return output_cls()

    mock_llm.predict_structured = AsyncMock(side_effect=mock_predict_structured)

    with use_event_emitter(emitter):
        config = TheoreticalEnrichmentConfig(enabled=True, induce_theories=True, tenability_threshold=0.5)
        # Registry is completely empty! Zero hardcoded theories!
        empty_registry = TheoryRegistry()
        runner = TheoreticalEnrichmentRunner(config=config, registry=empty_registry, llm=mock_llm)

        view = Phase4ArtifactsView(
            theory_atoms=mixed_empirical_atoms,
            theory_relations=mixed_theory_relations,
        )

        manifest = RunManifest(
            run_id="run-test-enrichment-dyn-001",
            input_fingerprint="fp-test",
            schema_fingerprint="fp-schema",
        )

        context = ArtifactExecutionContext(
            run_id="run-test-enrichment-dyn-001",
            manifest=manifest,
            pipeline_input=None,
        )

        collection = await runner.run(view, context)

        # 1. Verify theory was dynamically induced and registered
        assert len(empty_registry.all_theories()) == 1
        assert empty_registry.get("autonomous_neuro") is not None

        # 2. Check emitted artifacts
        assert len(collection.artifacts) >= 1
        enrichment_arts = collection.of_kind(ArtifactKind.THEORETICAL_ENRICHMENT)
        assert len(enrichment_arts) >= 1
        art = enrichment_arts[0]
        assert art.payload.theory_id == "autonomous_neuro"
        assert art.payload.is_tenable is True
        assert art.payload.local_tenability > 0.90

        # 3. Check emitted domain events
        event_types = [type(e) for e in obs.events]
        assert TheoreticalClusterIdentified in event_types
        assert TheoreticalParametersProjected in event_types
        assert TenabilityEvaluationCompleted in event_types


def test_dynamic_pipeline_runner_injection():
    """Verify that TheoreticalEnrichmentRunner can be dynamically plugged into Pipeline."""
    config = PipelineConfig(
        theoretical_enrichment=TheoreticalEnrichmentConfig(enabled=True)
    )

    custom_runner = TheoreticalEnrichmentRunner(config=config.theoretical_enrichment)

    phases = [custom_runner]
    from episteme_pipeline.events.bus import NoOpEventEmitter
    from episteme_pipeline.pipeline import Pipeline

    pipe = Pipeline(
        phases=phases,
        config=config,
        graph_reader=None,
        projection_graph=None,
        checkpoint_store=None,
        event_emitter=NoOpEventEmitter(),
    )

    entries = pipe._phase_entries
    assert len(entries) == 1
    assert entries[0].phase_key == "theoretical_enrichment"
    assert entries[0].name == "Theoretical Enrichment & Tenability Evaluation"
    assert entries[0].input_view == Phase4ArtifactsView


def test_pipeline_for_task_with_post_processors():
    """Verify that Pipeline.for_task accepts and appends post_processors cleanly."""
    from unittest.mock import MagicMock

    from episteme_pipeline.pipeline import Pipeline
    from episteme_pipeline.protocols.phase_runner import PhaseRunner

    config = PipelineConfig(
        theoretical_enrichment=TheoreticalEnrichmentConfig(enabled=False)
    )

    mock_post_proc = MagicMock(spec=PhaseRunner)
    mock_post_proc.name = "Custom Evaluation Post-Processor"
    mock_post_proc.phase_key = "custom_post_processor"
    mock_post_proc.input_view = Phase4ArtifactsView

    pipe = Pipeline.for_task(
        task="knowledge_graph",
        llm=MagicMock(),
        embedding_model=MagicMock(),
        relation_reranker=MagicMock(),
        cross_encoder=None,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        config=config,
        post_processors=[mock_post_proc],
    )

    assert pipe.phases[-1] == mock_post_proc
