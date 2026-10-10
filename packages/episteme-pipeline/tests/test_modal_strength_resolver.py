"""Test suite for Propositional Modal Strength Resolvers.

Verifies:
1. StructuralistModalResolver deterministic syntax mappings (Schurz 2014, Toulmin 1958).
2. DecisionEngineModalResolver System 1 linguistic evaluation with MockJevDecisionEngine.
3. HybridModalResolver neuro-symbolic guardrail clamping and convex fusion modes.
4. Domain event emission (ModalStrengthResolved) with full provenance.
5. Integration with Phase 6 TheoryNet projection and QBAF gradual semantics.
"""

from __future__ import annotations

import pytest
from episteme_pipeline.config import ModalResolverConfig
from episteme_pipeline.contracts.domain import (
    EpistemicStatus,
    ScopeType,
    TheoryAtom,
    TheoryNet,
)
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.decision.modal_resolver import (
    DecisionEngineModalResolver,
    HybridModalResolver,
    StructuralistModalResolver,
)
from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.context import use_event_emitter
from episteme_pipeline.events.models import ModalStrengthResolved
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.protocols.modality import (
    ensure_modal_strength_resolver,
)
from episteme_pipeline.schema.default_schema import SchemaConfig


class TestStructuralistModalResolver:
    """Tests for symbolic structuralist syntax evaluation (Schurz 2014)."""

    def test_scope_type_hierarchy(self) -> None:
        """Verify structuralist scope types map to formal modal necessity."""
        resolver = StructuralistModalResolver()

        # Essentieller Allsatz (analytic vs synthetic)
        essential_analytic = TheoryAtom(
            id="a1",
            text="All triangles have 180 degrees",
            component_type="Law",
            scope_type="Essentieller Allsatz",
            epistemic_status="Analytisch",
            source_chunk_id="c1",
        )
        essential_synthetic = TheoryAtom(
            id="a2",
            text="All massive bodies exert gravity",
            component_type="Law",
            scope_type="Essentieller Allsatz",
            epistemic_status="Synthetisch",
            source_chunk_id="c1",
        )
        assert resolver.resolve_modality_sync(essential_analytic) == 1.00
        assert resolver.resolve_modality_sync(essential_synthetic) == 0.90

        # Lokalisierter Allsatz
        loc_universal = TheoryAtom(
            id="a3",
            text="All birds on this island have blue feet",
            component_type="EmpiricalStatement",
            scope_type="Lokalisierter Allsatz",
            source_chunk_id="c1",
        )
        assert resolver.resolve_modality_sync(loc_universal) == 0.85

        # Lokalisierter Existenzsatz (Observational datum priority)
        loc_existential = TheoryAtom(
            id="a4",
            text="At t_0 in location L, pointer read 4.2V",
            component_type="ObservationUnit",
            scope_type="Lokalisierter Existenzsatz",
            source_chunk_id="c1",
        )
        assert resolver.resolve_modality_sync(loc_existential) == 0.85

        # Statistischer Allsatz
        stat_law = TheoryAtom(
            id="a5",
            text="80% of patients recover under therapy X",
            component_type="StatisticalLaw",
            scope_type="Statistischer/probabilistischer Allsatz",
            source_chunk_id="c1",
        )
        assert resolver.resolve_modality_sync(stat_law) == 0.75

        # Unbounded Existenzsatz (Theoretical postulation)
        hyp_existential = TheoryAtom(
            id="a6",
            text="There exists an unconscious repression mechanism",
            component_type="TheoreticalHypothesis",
            scope_type="Existenzsatz",
            source_chunk_id="c1",
        )
        assert resolver.resolve_modality_sync(hyp_existential) == 0.55

    def test_syntax_bounds_intervals(self) -> None:
        """Verify structural bounds intervals [M_min, M_max] for guardrail clipping."""
        resolver = StructuralistModalResolver()

        axiom = TheoryAtom(
            id="a1",
            text="Definitions",
            component_type="CoreAxiom",
            scope_type="Essentieller Allsatz",
            epistemic_status="Analytisch",
            source_chunk_id="c1",
        )
        bounds = resolver.get_syntax_bounds(axiom)
        assert bounds == (0.85, 1.00)

        conjecture = TheoryAtom(
            id="a2",
            text="Speculative idea",
            component_type="TentativeConjecture",
            source_chunk_id="c1",
        )
        bounds_conj = resolver.get_syntax_bounds(conjecture)
        assert bounds_conj == (0.10, 0.50)

    @pytest.mark.asyncio
    async def test_async_resolve_delegation(self) -> None:
        """Verify async resolve_modality produces identical scores to sync."""
        resolver = StructuralistModalResolver()
        atom = TheoryAtom(
            id="a1",
            text="Datum",
            component_type="ObservationUnit",
            scope_type="Lokalisierter Existenzsatz",
            source_chunk_id="c1",
        )
        sync_val = resolver.resolve_modality_sync(atom)
        async_val = await resolver.resolve_modality(atom)
        assert sync_val == async_val == 0.85


class TestDecisionEngineModalResolver:
    """Tests for empirical linguistic certainty evaluation using DecisionEngine."""

    @pytest.mark.asyncio
    async def test_decision_engine_evaluation(self) -> None:
        """Verify DecisionEngineModalResolver evaluates state and returns expected score."""
        engine = MockJevDecisionEngine(default_confidence_threshold=0.85)
        resolver = DecisionEngineModalResolver(engine)

        atom = TheoryAtom(
            id="a1",
            text="The experimental results demonstrate that the effect is real.",
            component_type="EmpiricalStatement",
            source_chunk_id="c1",
        )
        modality = await resolver.resolve_modality(atom, context="Context sentence.")
        assert 0.0 <= modality <= 1.0

    def test_sync_fallback(self) -> None:
        """Verify synchronous resolve_modality_sync delegates to structuralist syntax."""
        engine = MockJevDecisionEngine()
        resolver = DecisionEngineModalResolver(engine)
        atom = TheoryAtom(
            id="a1",
            text="Law",
            component_type="Axiom",
            source_chunk_id="c1",
        )
        val = resolver.resolve_modality_sync(atom)
        assert val == 1.00


class TestHybridModalResolver:
    """Tests for neuro-symbolic hybrid guardrailing and convex fusion."""

    @pytest.mark.asyncio
    async def test_guardrail_clamping_upper(self) -> None:
        """Verify an overconfident engine score is clamped down by syntactic bounds on a conjecture."""
        class MockOverconfidentEngine:
            async def evaluate_choice(self, state, question, options, alpha=None):
                from episteme_pipeline.protocols.decision import DecisionScore
                # Returns 0.99 certainty
                return DecisionScore(
                    selected_option="Level_4",
                    class_probability=0.99,
                    probabilities={"Level_4": 1.0},
                    empirical_accuracy=0.95,
                    prediction_set=["Level_4"],
                )

        engine = MockOverconfidentEngine()
        structural = StructuralistModalResolver()
        decision_res = DecisionEngineModalResolver(engine)
        hybrid = HybridModalResolver(
            structural_resolver=structural,
            decision_resolver=decision_res,
            mode="guardrail",
        )

        conjecture = TheoryAtom(
            id="conj_1",
            text="Speculative thought",
            component_type="TentativeConjecture",
            source_chunk_id="c1",
        )

        score = await hybrid.resolve_modality(conjecture)
        # Conjecture bounds are (0.10, 0.50); engine returned 1.0; should clamp to 0.50
        assert score == 0.50

    @pytest.mark.asyncio
    async def test_guardrail_clamping_lower(self) -> None:
        """Verify an underconfident engine score is clamped up by syntactic bounds on an axiom."""
        class MockUnderconfidentEngine:
            async def evaluate_choice(self, state, question, options, alpha=None):
                from episteme_pipeline.protocols.decision import DecisionScore
                # Returns 0.20 certainty
                return DecisionScore(
                    selected_option="Level_0",
                    class_probability=0.99,
                    probabilities={"Level_0": 1.0},
                    empirical_accuracy=0.95,
                    prediction_set=["Level_0"],
                )

        engine = MockUnderconfidentEngine()
        structural = StructuralistModalResolver()
        decision_res = DecisionEngineModalResolver(engine)
        hybrid = HybridModalResolver(
            structural_resolver=structural,
            decision_resolver=decision_res,
            mode="guardrail",
        )

        axiom = TheoryAtom(
            id="ax_1",
            text="Mathematical identity",
            component_type="CoreAxiom",
            scope_type="Essentieller Allsatz",
            epistemic_status="Analytisch",
            source_chunk_id="c1",
        )

        score = await hybrid.resolve_modality(axiom)
        # Axiom bounds are (0.85, 1.00); engine returned 0.20; should clamp to 0.85
        assert score == 0.85

    @pytest.mark.asyncio
    async def test_convex_fusion_mode(self) -> None:
        """Verify convex mode computes weighted sum alpha * M_syntax + (1 - alpha) * M_engine."""
        class MockFixedEngine:
            async def evaluate_choice(self, state, question, options, alpha=None):
                from episteme_pipeline.protocols.decision import DecisionScore
                return DecisionScore(
                    selected_option="Level_4",
                    class_probability=1.0,
                    probabilities={"Level_4": 1.0},
                    empirical_accuracy=1.0,
                    prediction_set=["Level_4"],
                )

        engine = MockFixedEngine()
        structural = StructuralistModalResolver()
        decision_res = DecisionEngineModalResolver(engine, levels=[0.2, 0.4, 0.6, 0.8, 1.0])
        hybrid = HybridModalResolver(
            structural_resolver=structural,
            decision_resolver=decision_res,
            mode="convex",
            fusion_alpha=0.60,
        )

        # Observation has syntax = 0.85. Engine returns 1.0.
        obs = TheoryAtom(
            id="obs_1",
            text="Observation data",
            component_type="ObservationUnit",
            source_chunk_id="c1",
        )
        score = await hybrid.resolve_modality(obs)
        # Expected: 0.60 * 0.85 + 0.40 * 1.0 = 0.51 + 0.40 = 0.91
        assert pytest.approx(score, rel=1e-3) == 0.91

    @pytest.mark.asyncio
    async def test_event_emission(self) -> None:
        """Verify ModalStrengthResolved domain event is published to EventEmitter."""
        events: list[ModalStrengthResolved] = []

        class TestObserver:
            def on_event(self, event):
                if isinstance(event, ModalStrengthResolved):
                    events.append(event)

        emitter = SimpleEventEmitter()
        emitter.register_observer(TestObserver())

        structural = StructuralistModalResolver()
        hybrid = HybridModalResolver(structural_resolver=structural, mode="structural_only")

        atom = TheoryAtom(
            id="atom_event_test",
            text="Test claim",
            component_type="ObservationUnit",
            scope_type="Lokalisierter Existenzsatz",
            source_chunk_id="c1",
        )

        with use_event_emitter(emitter):
            val = await hybrid.resolve_modality(atom)

        assert val == 0.85
        assert len(events) == 1
        ev = events[0]
        assert ev.atom_id == "atom_event_test"
        assert ev.modal_strength == 0.85
        assert ev.resolver_type == "structural"
        assert ev.scope_type == "Lokalisierter Existenzsatz"


class TestPhase6TheoryNetProjectorIntegration:
    """Tests for Phase 6 TheoryNetProjector with injected ModalStrengthResolver."""

    def test_projector_with_custom_modal_resolver(self) -> None:
        """Verify TheoryNetProjector uses custom resolver to assign modal strength."""
        class ConstantModalResolver:
            def resolve_modality_sync(self, atom, context=None):
                return 0.777

            async def resolve_modality(self, atom, context=None):
                return 0.777

        projector = TheoryNetProjector(
            schema=SchemaConfig(),
            modal_resolver=ConstantModalResolver(),
        )

        from episteme_pipeline.artifacts.execution import Phase4ArtifactsView
        atom = TheoryAtom(
            id="a1",
            text="Claim without explicit modal strength",
            component_type="TheoreticalHypothesis",
            source_chunk_id="c1",
        )
        view = Phase4ArtifactsView(theory_atoms=[atom], theory_relations=[])
        tnet: TheoryNet = projector.project(view)

        assert len(tnet.atoms) == 1
        assert pytest.approx(tnet.atoms[0].modal_strength) == 0.777
        assert pytest.approx(tnet.atoms[0].base_score) == 0.777


def test_ensure_modal_strength_resolver() -> None:
    """Verify runtime checkability and validation helper."""
    assert ensure_modal_strength_resolver(None) is None
    resolver = StructuralistModalResolver()
    assert ensure_modal_strength_resolver(resolver) is resolver

    class IncompleteResolver:
        pass

    with pytest.raises(TypeError, match="does not satisfy the ModalStrengthResolver protocol"):
        ensure_modal_strength_resolver(IncompleteResolver())


def test_scope_type_and_epistemic_status_enums() -> None:
    """Verify parsing and normalization of ScopeType and EpistemicStatus enums."""
    assert ScopeType.from_str(None) is None
    assert ScopeType.from_str("") is None
    assert ScopeType.from_str("  ") is None
    assert ScopeType.from_str("Essentieller Allsatz") == ScopeType.ESSENTIELLER_ALLSATZ
    assert ScopeType.from_str("essentieller_allsatz") == ScopeType.ESSENTIELLER_ALLSATZ
    assert ScopeType.from_str("ESSENTIELLER-ALLSATZ") == ScopeType.ESSENTIELLER_ALLSATZ
    assert ScopeType.from_str("Lokalisierter Allsatz") == ScopeType.LOKALISIERTER_ALLSATZ
    assert ScopeType.from_str("lokalisierter existenzsatz") == ScopeType.LOKALISIERTER_EXISTENZSATZ
    assert ScopeType.from_str("Statistischer/probabilistischer Allsatz") == ScopeType.STATISTISCHER_ALLSATZ
    assert ScopeType.from_str("statistischer allsatz") == ScopeType.STATISTISCHER_ALLSATZ
    assert ScopeType.from_str("probabilistischer allsatz") == ScopeType.STATISTISCHER_ALLSATZ
    assert ScopeType.from_str("Existenzsatz") == ScopeType.EXISTENZSATZ
    assert ScopeType.from_str("unknown_scope") is None

    assert EpistemicStatus.from_str(None) is None
    assert EpistemicStatus.from_str("") is None
    assert EpistemicStatus.from_str("Analytisch") == EpistemicStatus.ANALYTISCH
    assert EpistemicStatus.from_str("analytisch") == EpistemicStatus.ANALYTISCH
    assert EpistemicStatus.from_str("Synthetisch") == EpistemicStatus.SYNTHETISCH
    assert EpistemicStatus.from_str("synthetisch") == EpistemicStatus.SYNTHETISCH
    assert EpistemicStatus.from_str("unknown_status") is None


def test_atom_boundary_normalization() -> None:
    """Verify TheoryAtom and ExtractedComponent normalize fuzzy strings at boundaries."""
    atom = TheoryAtom(
        id="a1",
        text="A test claim",
        component_type="Law",
        scope_type="essentieller_allsatz",
        epistemic_status="analytisch",
        source_chunk_id="c1",
    )
    assert atom.scope_type == ScopeType.ESSENTIELLER_ALLSATZ.value
    assert atom.epistemic_status == EpistemicStatus.ANALYTISCH.value

    from episteme_pipeline.phases.phase4_argument_mining.models import (
        ExtractedComponent,
    )
    comp = ExtractedComponent(
        id="AC1",
        component_type="ObservationUnit",
        text="Observed fact",
        scope_type="lokalisierter-existenzsatz",
        epistemic_status="SYNTHETISCH",
    )
    assert comp.scope_type == ScopeType.LOKALISIERTER_EXISTENZSATZ.value
    assert comp.epistemic_status == EpistemicStatus.SYNTHETISCH.value


def test_hybrid_modal_resolver_create_factory() -> None:
    """Verify HybridModalResolver.create factory handles various config and dependency states."""
    # 1. Default creation without decision engine defaults to structural_only
    res_default = HybridModalResolver.create()
    assert res_default.mode == "structural_only"
    assert res_default.decision_resolver is None
    assert isinstance(res_default.structural_resolver, StructuralistModalResolver)

    # 2. Creation with config and decision engine defaults to guardrail
    mock_engine = MockJevDecisionEngine()
    cfg = ModalResolverConfig(mode="guardrail", fusion_alpha=0.75, default_base_score=0.55)
    res_hybrid = HybridModalResolver.create(config=cfg, decision_engine=mock_engine)
    assert res_hybrid.mode == "guardrail"
    assert res_hybrid.fusion_alpha == 0.75
    assert res_hybrid.decision_resolver is not None
    assert res_hybrid.structural_resolver.default_base_score == 0.55

    # 3. Creation from dict config
    dict_cfg = {"mode": "convex", "fusion_alpha": 0.40, "default_base_score": 0.65}
    res_dict = HybridModalResolver.create(config=dict_cfg, decision_engine=mock_engine)
    assert res_dict.mode == "convex"
    assert res_dict.fusion_alpha == 0.40
    assert res_dict.structural_resolver.default_base_score == 0.65


def test_schema_config_scope_and_epistemic_fields() -> None:
    """Verify SchemaConfig registers centralized scope_types and epistemic_statuses."""
    schema = SchemaConfig()
    assert "Essentieller Allsatz" in schema.scope_types
    assert "Lokalisierter Existenzsatz" in schema.scope_types
    assert "Analytisch" in schema.epistemic_statuses
    assert "Synthetisch" in schema.epistemic_statuses


def test_structuralist_syntax_profile() -> None:
    """Verify evaluate_syntax_profile derives score and bounds in a single pass."""
    resolver = StructuralistModalResolver(default_base_score=0.60)

    # 1. ScopeType match
    atom = TheoryAtom(
        id="a1",
        text="All humans are mortal",
        scope_type="Essentieller Allsatz",
        epistemic_status="Analytisch",
        component_type="Law",
        source_chunk_id="c1",
    )
    profile = resolver.evaluate_syntax_profile(atom)
    assert profile.score == 1.00
    assert profile.bounds == (0.85, 1.00)
    assert resolver.resolve_modality_sync(atom) == profile.score
    assert resolver.get_syntax_bounds(atom) == profile.bounds

    # 2. Component fallback: Axiomatic
    axiom = TheoryAtom(
        id="a2",
        text="Axiom 1",
        component_type="Axiom",
        source_chunk_id="c1",
    )
    p_axiom = resolver.evaluate_syntax_profile(axiom)
    assert p_axiom.score == 1.00
    assert p_axiom.bounds == (0.85, 1.00)

    # 3. Component fallback: Empirical / Observation
    obs = TheoryAtom(
        id="a3",
        text="Sample reading",
        component_type="ObservationUnit",
        source_chunk_id="c1",
    )
    p_obs = resolver.evaluate_syntax_profile(obs)
    assert p_obs.score == 0.85
    assert p_obs.bounds == (0.70, 0.95)

    # 4. Component fallback: Theoretical with Analytic vs Synthetic
    theo_ana = TheoryAtom(
        id="a4",
        text="Theoretical entity",
        component_type="TheoreticalHypothesis",
        epistemic_status="Analytisch",
        source_chunk_id="c1",
    )
    p_theo_ana = resolver.evaluate_syntax_profile(theo_ana)
    assert p_theo_ana.score == 0.75
    assert p_theo_ana.bounds == (0.60, 0.85)

    theo_syn = TheoryAtom(
        id="a5",
        text="Theoretical hypothesis",
        component_type="TheoreticalHypothesis",
        epistemic_status="Synthetisch",
        source_chunk_id="c1",
    )
    p_theo_syn = resolver.evaluate_syntax_profile(theo_syn)
    assert p_theo_syn.score == 0.60
    assert p_theo_syn.bounds == (0.40, 0.80)

    # 5. Component fallback: Speculation
    spec = TheoryAtom(
        id="a6",
        text="Wild conjecture",
        component_type="Speculation",
        source_chunk_id="c1",
    )
    p_spec = resolver.evaluate_syntax_profile(spec)
    assert p_spec.score == 0.35
    assert p_spec.bounds == (0.10, 0.50)

    # 6. Default fallback
    other = TheoryAtom(
        id="a7",
        text="Unknown",
        component_type="MiscellaneousCommentary",
        source_chunk_id="c1",
    )
    p_other = resolver.evaluate_syntax_profile(other)
    assert p_other.score == 0.60
    assert p_other.bounds == (0.30, 0.85)
