from __future__ import annotations

from episteme_pipeline.events.bus import ContextualEventEmitter, SimpleEventEmitter
from episteme_pipeline.events.models import DenseCandidatesGenerated


class _Capture:
    def __init__(self) -> None:
        self.events: list[object] = []

    def on_event(self, e: object) -> None:
        self.events.append(e)


def test_contextual_emitter_injects_defaults() -> None:
    base = SimpleEventEmitter()
    cap = _Capture()
    base.register_observer(cap)

    emitter = ContextualEventEmitter(base, defaults={"run_id": "r42", "phase": "p3"})

    emitter.emit(
        DenseCandidatesGenerated(candidate_count=1, candidates=[{"a": 1}], entities_count=2)
    )

    assert len(cap.events) == 1
    ev = cap.events[0]
    assert getattr(ev, "run_id", None) == "r42"
    assert getattr(ev, "phase", None) == "p3"

