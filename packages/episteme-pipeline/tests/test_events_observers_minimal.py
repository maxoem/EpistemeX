from __future__ import annotations

import json
from pathlib import Path

from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.models import (
    DenseCandidatesGenerated,
    RerankerScoreAssigned,
    TripleCommitted,
)
from episteme_pipeline.events.observers import (
    CompositeObserver,
    JsonlRunObserver,
    MetricsObserver,
)


class _Capture:
    def __init__(self) -> None:
        self.events: list[object] = []

    def on_event(self, e: object) -> None:  # EventObserver-compatible
        self.events.append(e)


class _Failing:
    def on_event(self, e: object) -> None:
        raise RuntimeError("boom")


def test_jsonl_and_metrics_and_composite_isolation(tmp_path: Path) -> None:
    out = tmp_path / "runs" / "demo" / "events.jsonl"

    emitter = SimpleEventEmitter()
    cap = _Capture()
    metrics = MetricsObserver()
    failing = _Failing()

    with JsonlRunObserver(out) as jsonl:
        composite = CompositeObserver([jsonl, metrics, failing, cap])
        emitter.register_observer(composite)

        emitter.emit(
            DenseCandidatesGenerated(
                candidate_count=1,
                candidates=[{"entity_a": "e1", "entity_b": "e2", "score": 0.9}],
                entities_count=2,
                run_id="r1",
                phase="p3",
            )
        )
        emitter.emit(
            RerankerScoreAssigned(
                candidate_pair=("e1", "e2"),
                score=0.9,
                accepted=True,
                threshold=0.8,
            )
        )
        emitter.emit(
            TripleCommitted(
                subject_id="e1",
                predicate="REL",
                object_id="e2",
                confidence=0.9,
                scope="global",
                source_chunk_id="global",
            )
        )

    # JSONL wrote two lines after DenseCandidates and Reranker (third also OK)
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first["_event_type"] == "DenseCandidatesGenerated"
    assert first["run_id"] == "r1" and first["phase"] == "p3"

    # Metrics captured acceptance and triple count despite failing observer
    assert metrics.get_candidate_acceptance_rate("e1-e2") == 1.0
    assert metrics.total_triples_committed == 1

    # Capture received all three events
    assert len(cap.events) == 3

