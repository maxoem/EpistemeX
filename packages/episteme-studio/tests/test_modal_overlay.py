"""Unit tests verifying Propositional Modal Strength graph overlays, event mapping, and config patching."""

from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.events.models import ModalStrengthResolved
from episteme_studio.adapters.config_adapter import ConfigAdapter
from episteme_studio.adapters.event_mapper import to_studio_event
from episteme_studio.adapters.metrics_adapter import compute_gradual_strength, compute_modal_strength
from episteme_studio.domain.graph import GraphView, Layer, StudioEdge, StudioNode
from episteme_studio.domain.overlays import OverlayKind
from episteme_studio.services.overlay_service import OverlayService


def test_compute_modal_strength_overlay():
    """Verify compute_modal_strength generates continuous [0.0, 1.0] overlay from nodes."""
    node1 = StudioNode(
        id="atom-1",
        layer=Layer.L3,
        type="TheoryAtom",
        label="Observation Atom",
        modal_strength=0.85,
        scope_type="Lokalisierter Existenzsatz",
        epistemic_status="Synthetisch",
    )
    node2 = StudioNode(
        id="atom-2",
        layer=Layer.L3,
        type="TheoryAtom",
        label="Analytic Law",
        modal_strength=1.0,
        scope_type="Essentieller Allsatz",
        epistemic_status="Analytisch",
    )
    node3 = StudioNode(
        id="atom-3",
        layer=Layer.L3,
        type="TheoryAtom",
        label="Indeterminate Atom",
        base_score=0.60,
    )
    graph = GraphView(
        nodes=[node1, node2, node3],
        edges=[],
        source="artifacts",
        graph_version="v-modal-test",
        schema_version="1.0.0",
    )

    overlay = compute_modal_strength(graph)

    assert overlay.kind == OverlayKind.MODAL_STRENGTH
    assert overlay.scale == "continuous"
    assert overlay.domain == [0.0, 1.0]
    assert overlay.node_values["atom-1"] == 0.85
    assert overlay.node_values["atom-2"] == 1.0
    assert overlay.node_values["atom-3"] == 0.60
    assert overlay.incomplete_inputs == 0


def test_compute_gradual_strength_uses_modal_strength_fallback():
    """Verify gradual strength propagation falls back to modal_strength when plausibility is unset."""
    node1 = StudioNode(
        id="atom-1",
        layer=Layer.L3,
        type="TheoryAtom",
        label="Premise",
        modal_strength=0.90,
    )
    node2 = StudioNode(
        id="atom-2",
        layer=Layer.L3,
        type="TheoryAtom",
        label="Conclusion",
        modal_strength=0.50,
    )
    edge = StudioEdge(
        id="rel-1",
        source="atom-1",
        target="atom-2",
        type="SUPPORTS",
        layer=Layer.L3,
        polarity=1,
        weight=0.80,
    )
    graph = GraphView(
        nodes=[node1, node2],
        edges=[edge],
        source="artifacts",
        graph_version="v-gradual-test",
        schema_version="1.0.0",
    )

    overlay = compute_gradual_strength(graph, {"iterations": 5})

    assert overlay.kind == OverlayKind.GRADUAL_STRENGTH
    assert overlay.incomplete_inputs == 0
    assert overlay.node_values["atom-1"] is not None
    assert overlay.node_values["atom-2"] is not None
    # Support increases conclusion score above base 0.50
    assert overlay.node_values["atom-2"] > 0.50


def test_overlay_service_dispatch_modal_strength():
    """Verify OverlayService dispatches and caches modal_strength computation."""
    service = OverlayService()
    node = StudioNode(
        id="atom-1",
        layer=Layer.L3,
        type="TheoryAtom",
        label="Test Atom",
        modal_strength=0.75,
    )
    graph = GraphView(
        nodes=[node],
        edges=[],
        source="artifacts",
        graph_version="v-cache-test",
        schema_version="1.0.0",
    )

    res1 = service.compute_overlay(graph, OverlayKind.MODAL_STRENGTH)
    res2 = service.compute_overlay(graph, OverlayKind.MODAL_STRENGTH)

    assert res1.id == res2.id
    assert res1.node_values["atom-1"] == 0.75


def test_config_adapter_patches_modal_resolver():
    """Verify ConfigAdapter successfully applies patches to modal_resolver configs."""
    base_config = PipelineConfig()

    patch = {
        "modal_resolver.mode": "convex",
        "modal_resolver.fusion_alpha": 0.70,
        "phase4.modal_resolver.mode": "engine_only",
        "phase6.modal_resolver.mode": "structural_only",
    }

    updated = ConfigAdapter.apply_patch(base_config, patch)

    assert updated.modal_resolver.mode == "convex"
    assert updated.modal_resolver.fusion_alpha == 0.70
    assert updated.phase4.modal_resolver.mode == "engine_only"
    assert updated.phase6.modal_resolver.mode == "structural_only"


def test_event_mapper_maps_modal_strength_resolved():
    """Verify event_mapper converts ModalStrengthResolved domain event to StudioEvent."""
    event = ModalStrengthResolved(
        atom_id="comp-42",
        modal_strength=0.85,
        resolver_type="HybridModalResolver",
        scope_type="Lokalisierter Existenzsatz",
        epistemic_status="Synthetisch",
        clamped=True,
    )

    studio_event = to_studio_event(event, seq=10)

    assert studio_event.kind == "modal.resolved"
    assert "comp-42" in (studio_event.message or "")
    assert "0.850" in (studio_event.message or "")
    assert "HybridModalResolver" in (studio_event.message or "")
    assert "(clamped)" in (studio_event.message or "")
