from unittest.mock import AsyncMock, MagicMock

import pytest
import torch
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, SubGraph
from episteme_pipeline.events.models import UnlinkableMentionError
from episteme_pipeline.phases.phase2_entity_discovery.mention_context_injector import (
    DefaultMentionContextInjector,
)
from episteme_pipeline.phases.phase2_entity_discovery.sota_entity_linker import (
    DenseEntityLinker,
    EnvelopeBiEncoder,
)


class DummyStructuredLLM:
    """Minimal dummy structured LLM with valid stable fingerprint."""
    async def acomplete(self, prompt: str, schema=None, **kwargs):
        return {}

    def fingerprint(self) -> dict:
        return {"provider": "dummy", "model": "test-model"}


def test_mention_context_injector_truncation_and_markers():
    injector = DefaultMentionContextInjector()
    chunk_text = "This is a long philosophical text. Immanuel Kant argued that the mind shapes experience. This is the end of the text."
    mention = "Immanuel Kant"
    
    injected = injector.inject(chunk_text, mention, mention_quote=mention, max_chars=30)
    
    assert injected is not None
    assert "[ENT]" in injected
    assert "[\\ENT]" in injected
    assert "[ENT] Immanuel Kant [\\ENT]" in injected
    assert len(injected) <= 30 + len("[ENT] ") + len(" [\\ENT]") + 2


def test_mention_context_injector_normalization():
    injector = DefaultMentionContextInjector()
    chunk_text = "Der Begriff „Freiheit“ – im praktischen Verstande – ist zentral..."
    
    # Quote with standard quotes and hyphens (model output variation)
    quote = '"Freiheit" - im praktischen Verstande -'
    injected = injector.inject(chunk_text, mention_name="Freiheit", mention_quote=quote, max_chars=80)
    
    assert injected is not None
    assert "[ENT] „Freiheit“ – im praktischen Verstande – [\\ENT]" in injected


def test_mention_context_injector_not_found():
    injector = DefaultMentionContextInjector()
    injected = injector.inject("Text without mention.", mention_name="Kant", mention_quote="Kant")
    assert injected is None


def test_envelope_bi_encoder_guard():
    # Calling without trained_checkpoint=True must raise RuntimeError (Issue L06 Option C)
    with pytest.raises(RuntimeError, match="experimental research branch"):
        EnvelopeBiEncoder()


@pytest.mark.asyncio
async def test_envelope_bi_encoder_pooling_with_checkpoint(monkeypatch):
    """Verify EnvelopeBiEncoder pools at [ENT] marker when present and falls back to [CLS]."""
    hidden_dim = 384
    seq_len = 5
    ent_token_id = 999

    mock_tokenizer = MagicMock()
    input_ids = torch.tensor([
        [101, 10, ent_token_id, 20, 102],
        [101, 10, 30, 40, 102],
    ])
    mock_tokenizer.return_value = {"input_ids": input_ids}
    mock_tokenizer.convert_tokens_to_ids.side_effect = lambda t: ent_token_id if t == "[ENT]" else 0
    mock_tokenizer.__len__ = lambda self: 1000
    mock_tokenizer.add_special_tokens.return_value = 2

    mock_model = MagicMock()
    last_hidden = torch.randn(2, seq_len, hidden_dim)
    mock_output = MagicMock()
    mock_output.last_hidden_state = last_hidden
    mock_model.return_value = mock_output
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = mock_model

    from transformers import AutoModel, AutoTokenizer
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", lambda *args, **kwargs: mock_tokenizer)
    monkeypatch.setattr(AutoModel, "from_pretrained", lambda *args, **kwargs: mock_model)

    encoder = EnvelopeBiEncoder(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        trained_checkpoint=True,
    )

    text_with_ent = "The philosopher [ENT] Kant [\\ENT] argued..."
    text_without_ent = "The philosopher Kant argued..."

    embeddings = encoder.encode([text_with_ent, text_without_ent])

    assert embeddings.shape == (2, hidden_dim)
    assert torch.equal(embeddings[0], last_hidden[0, 2, :])
    assert torch.equal(embeddings[1], last_hidden[1, 0, :])


def test_phase2_runner_defaults_to_name_linker_when_no_embedding_model():
    """Verify Phase2Runner defaults to NameEntityLinker when embedding_model is None."""
    from episteme_pipeline.config import Phase2Config
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
    from episteme_pipeline.phases.phase2_entity_discovery.entity_linker import (
        NameEntityLinker,
    )

    runner = Phase2Runner(
        config=Phase2Config(),
        schema=MagicMock(),
        llm=DummyStructuredLLM(),
        embedding_model=None,
        graph_store=AsyncMock(),
    )
    assert isinstance(runner.entity_linker, NameEntityLinker)


@pytest.mark.asyncio
async def test_dense_entity_linker_retrieval_and_cross_encoding():
    # Mock embedding model returning normalized vectors
    class MockEmbeddingModel:
        async def aget_text_embedding(self, text: str) -> list[float]:
            return [1.0, 0.0]

        async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
            results = []
            for t in texts:
                if "Kant" in t:
                    results.append([1.0, 0.0])
                else:
                    results.append([0.0, 1.0])
            return results

    # Mock cross-encoder
    class MockCrossEncoder:
        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            return [0.95 for _ in pairs]

    # Mock graph store
    mock_graph_store = AsyncMock()
    candidate_kant = L2Entity(id="e_kant", name="Immanuel Kant", label="PERSON", description="German philosopher")
    candidate_hegel = L2Entity(id="e_hegel", name="G.W.F. Hegel", label="PERSON", description="German idealist")
    mock_graph_store.get_entities.return_value = [candidate_kant, candidate_hegel]
    mock_graph_store.get_neighborhood.return_value = SubGraph(
        center_id="e_kant",
        nodes=[candidate_kant],
        triples=[L2Triple(subject_id="e_kant", predicate="WROTE", object_id="e_krV", confidence=1.0, scope="local")],
        depth=1,
    )

    linker = DenseEntityLinker(
        embedding_model=MockEmbeddingModel(),
        cross_encoder=MockCrossEncoder(),
        tau=0.8,
        top_k=2,
    )

    mention = L2Entity(
        id="m1",
        name="Kant",
        label="PERSON",
        textual_envelope="The philosopher [ENT] Kant [\\ENT] wrote the critique.",
    )

    result = await linker.link(mention, mock_graph_store)

    assert result is not None
    assert result.id == "e_kant"
    assert "e_kant" in linker._candidate_cache
    # Verify candidate formatting has type grounding
    cached_text, cached_vec = linker._candidate_cache["e_kant"]
    assert "[PERSON] Immanuel Kant: German philosopher" == cached_text


@pytest.mark.asyncio
async def test_dense_entity_linker_missing_envelope_raises():
    linker = DenseEntityLinker(
        embedding_model=AsyncMock(),
        cross_encoder=MagicMock(),
    )
    mention_no_env = L2Entity(id="m2", name="Kant", label="PERSON", textual_envelope=None)
    
    with pytest.raises(UnlinkableMentionError):
        await linker.link(mention_no_env, AsyncMock())


def test_dense_entity_linker_reranker_propagation():
    from episteme_pipeline.config import Phase2Config
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner

    mock_cross_encoder = MagicMock()
    mock_embed = AsyncMock()
    linker = DenseEntityLinker(embedding_model=mock_embed, cross_encoder=mock_cross_encoder)
    assert linker.cross_encoder is mock_cross_encoder

    dummy_llm = DummyStructuredLLM()
    mock_store = AsyncMock()
    
    config = Phase2Config()
    runner = Phase2Runner(
        config=config,
        schema=MagicMock(),
        llm=dummy_llm,
        embedding_model=mock_embed,
        graph_store=mock_store,
        cross_encoder=mock_cross_encoder,
    )

    assert isinstance(runner.entity_linker, DenseEntityLinker)
    assert runner.entity_linker.cross_encoder is mock_cross_encoder


def test_phase4_entity_maturation_bi_encoder_propagation():
    from episteme_pipeline.config import Phase4EntityMaturationConfig
    from episteme_pipeline.phases.phase4_entity_maturation import (
        Phase4EntityMaturationRunner,
    )

    mock_bi_encoder = AsyncMock()
    dummy_llm = DummyStructuredLLM()
    mock_store = AsyncMock()
    config = Phase4EntityMaturationConfig()

    runner = Phase4EntityMaturationRunner(
        config=config,
        llm=dummy_llm,
        graph_store=mock_store,
        embedding_model=mock_bi_encoder,
    )

    assert runner.embedding_model is mock_bi_encoder


@pytest.mark.asyncio
async def test_embedding_model_protocol_adherence():
    """The single embedding contract is async and returns list[float]."""
    from episteme_pipeline.protocols.extractors import CrossEncoder, EmbeddingModel

    class AsyncEmbeddingModel:
        async def aget_text_embedding(self, text: str) -> list[float]:
            return [0.0] * 384

        async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 384 for _ in texts]

    class CustomCrossEncoder:
        def predict(self, pairs: list[tuple[str, str]]):
            return [0.95 for _ in pairs]

    embed = AsyncEmbeddingModel()
    ce = CustomCrossEncoder()

    assert isinstance(embed, EmbeddingModel)
    assert isinstance(ce, CrossEncoder)

    assert len(await embed.aget_text_embedding_batch(["a", "b"])) == 2
    assert ce.predict([("a", "b")]) == [0.95]


@pytest.mark.asyncio
async def test_ensure_embedding_model_normalises_sync_encoders():
    """A sync, tensor-returning encoder is adapted; async models pass through."""
    from episteme_pipeline.protocols.extractors import (
        EmbeddingModel,
        SyncEncoderEmbeddingModel,
        ensure_embedding_model,
    )

    class TorchStyleEncoder:
        def encode(self, texts: list[str]):
            return torch.zeros((len(texts), 384))

    adapted = ensure_embedding_model(TorchStyleEncoder())
    assert isinstance(adapted, EmbeddingModel)
    assert isinstance(getattr(adapted, "inner", adapted), SyncEncoderEmbeddingModel)

    rows = await adapted.aget_text_embedding_batch(["text1", "text2"])
    assert len(rows) == 2
    assert len(rows[0]) == 384
    assert all(isinstance(x, float) for x in rows[0])

    single = await adapted.aget_text_embedding("text1")
    assert len(single) == 384

    class AlreadyAsync:
        async def aget_text_embedding(self, text: str) -> list[float]:
            return [1.0]

        async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
            return [[1.0] for _ in texts]

    passthrough = AlreadyAsync()
    wrapped = ensure_embedding_model(passthrough)
    assert getattr(wrapped, "inner", None) is passthrough
    assert ensure_embedding_model(wrapped) is wrapped
    assert ensure_embedding_model(None) is None


def test_ensure_embedding_model_rejects_incompatible_objects():
    """Configuration-time TypeError beats an AttributeError inside a gather()."""
    from episteme_pipeline.protocols.extractors import ensure_embedding_model

    class NotAnEmbedder:
        pass

    with pytest.raises(TypeError, match="EmbeddingModel protocol"):
        ensure_embedding_model(NotAnEmbedder())


def test_configs_pure_json_serializable():
    """W-05: configs must be purely JSON-serializable and not contain live model slots."""
    import json

    from episteme_pipeline.config import (
        Phase2Config,
        Phase4EntityMaturationConfig,
        PipelineConfig,
    )

    p2 = Phase2Config()
    assert not hasattr(p2, "embedding_model")
    assert not hasattr(p2, "cross_encoder_model")

    p4_mat = Phase4EntityMaturationConfig()
    assert not hasattr(p4_mat, "embedding_model")

    cfg = PipelineConfig()
    dumped = cfg.model_dump(mode="json")
    json_str = cfg.model_dump_json(indent=2)
    assert isinstance(dumped, dict)
    assert json.loads(json_str) == dumped
