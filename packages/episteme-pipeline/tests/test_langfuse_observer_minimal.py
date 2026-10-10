from __future__ import annotations

from episteme_pipeline.events.langfuse_observer import LangfuseObserver
from episteme_pipeline.events.models import (
    ComponentCompleted,
    ComponentStarted,
    DenseCandidatesGenerated,
    LLMRelationDecoded,
    PhaseCompleted,
    RerankerScoreAssigned,
)


class _RecClient:
    def __init__(self) -> None:
        self.spans: list[dict[str, object]] = []

    def start_observation(self, *, name: str, input=None, output=None, as_type="span", **kwargs):
        rec = {"name": name, "input": input, "output": output, "updates": [], "ended": False, "kwargs": kwargs}
        self.spans.append(rec)

        class _Obs:
            def end(self_inner):
                rec["ended"] = True

            def update(self_inner, **kw):
                if rec["ended"]:
                    return
                rec["updates"].append(kw)
                if "output" in kw:
                    rec["output"] = kw["output"]

        return _Obs()


def test_langfuse_observer_maps_events(monkeypatch) -> None:
    monkeypatch.setattr("episteme_pipeline.events.langfuse_observer.LANGFUSE_AVAILABLE", True)
    client = _RecClient()
    obs = LangfuseObserver(client=client)

    obs.on_event(ComponentStarted(component_name="enc", input_description="x"))
    obs.on_event(ComponentCompleted(component_name="enc", duration_seconds=0.1, success=True))
    obs.on_event(PhaseCompleted(phase_name="p3", duration_seconds=1.2, artifact_count=5, success=True))
    obs.on_event(DenseCandidatesGenerated(candidate_count=2, candidates=[{"k": 1}], entities_count=2))
    obs.on_event(
        RerankerScoreAssigned(
            candidate_pair=("e1", "e2"),
            score=0.9,
            accepted=True,
            threshold=0.8,
            entity_a={"id": "e1", "name": "Theory"},
            entity_b={"id": "e2", "name": "Observation"},
            reranker_input={"pair_byte_count": 128, "max_length": 1024},
            reranker_payload={"query": "Entity: Theory", "document": "Entity: Observation"},
            recovery_attempts=[],
        )
    )
    obs.on_event(LLMRelationDecoded(candidate_pair=("e1", "e2"), relation="REL", direction="A_to_B", confidence=0.7))

    names = [s["name"] for s in client.spans]
    assert {"phase.p3", "phase3.dense.candidates", "phase3.dense.rerank", "phase3.dense.llm_extract"}.issubset(set(names))
    rerank_span = next(s for s in client.spans if s["name"] == "phase3.dense.rerank")
    assert rerank_span["input"]["reranker_payload"]["query"] == "Entity: Theory"
    assert rerank_span["output"]["reranker_input"]["pair_byte_count"] == 128
