"""Tests for cross-cutting concerns (events contextvars, prompt bundles)."""

from episteme_pipeline.config import StructuredPromptBundle
from episteme_pipeline.events import (
    ComponentStarted,
    NoOpEventEmitter,
    SimpleEventEmitter,
    get_event_emitter,
    use_event_emitter,
)
from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import (
    LLMNERExtractor,
)
from episteme_pipeline.prompts import NER_DIRECT_PROMPT, NER_GLEANING_PROMPT


class MockObserver:
    def __init__(self):
        self.events = []

    def on_event(self, event):
        self.events.append(event)


def test_event_emitter_contextvars_default():
    """Verify get_event_emitter returns NoOpEventEmitter when no context is set."""
    emitter = get_event_emitter()
    assert isinstance(emitter, NoOpEventEmitter)


def test_event_emitter_contextvars_binding():
    """Verify set_event_emitter and use_event_emitter bind task-local emitter."""
    emitter = SimpleEventEmitter()
    observer = MockObserver()
    emitter.register_observer(observer)

    assert isinstance(get_event_emitter(), NoOpEventEmitter)

    with use_event_emitter(emitter):
        active = get_event_emitter()
        assert active is emitter
        active.emit(ComponentStarted(component_name="TestComponent", run_id="run-1"))

    # Out of context, should revert to default
    assert isinstance(get_event_emitter(), NoOpEventEmitter)
    assert len(observer.events) == 1
    assert observer.events[0].component_name == "TestComponent"


def test_structured_prompt_bundle_fields():
    """Verify StructuredPromptBundle supports gleaning_template."""
    bundle = StructuredPromptBundle(
        direct_template=NER_DIRECT_PROMPT,
        gleaning_template=NER_GLEANING_PROMPT,
    )
    assert bundle.direct_template == NER_DIRECT_PROMPT
    assert bundle.gleaning_template == NER_GLEANING_PROMPT


def test_ner_extractor_accepts_structured_prompt_bundle():
    """Verify LLMNERExtractor initializes with StructuredPromptBundle."""
    class DummyLLM:
        def predict_structured(self, *args, **kwargs):
            pass

    bundle = StructuredPromptBundle(direct_template="Test direct prompt")
    extractor = LLMNERExtractor(llm=DummyLLM(), prompts=bundle)
    assert extractor.prompts is bundle
    assert extractor.prompts.direct_template == "Test direct prompt"
