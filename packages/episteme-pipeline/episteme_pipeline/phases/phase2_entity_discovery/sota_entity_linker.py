"""
Dense Entity Linker implementing T x G bi-encoder retrieval
and cross-encoder reranking.

Known limitations, tracked separately and deliberately *not* addressed here:
  - — ``EnvelopeBiEncoder`` pools at a randomly-initialised
    ``[ENT]`` token and ranks by an unnormalised dot product.
  -  — the candidate ("structural") envelope is a flat
    name/description string, not a 1-hop subgraph serialisation.
  -  — mentions without a textual envelope skip linking
    entirely and are minted as new entities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import torch

from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.protocols.extractors import (
    CrossEncoder,
    EmbeddingModel,
    EntityLinker,
    argmax,
    as_tensor,
    normalize_scores,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import EntityLinkingCandidatesRetrieved, EntityLinkingReranked, UnlinkableMentionError
from episteme_pipeline.contracts.domain import SubGraph

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer

logger = logging.getLogger(__name__)


class EnvelopeBiEncoder:
    """
    Custom bi-encoder that pools the hidden state h_j at the `[ENT]` marker
    instead of the standard `[CLS]` token. This ensures the vector represents
    the logical subject bounded by the envelope.

    Implements the :class:`EmbeddingModel` protocol (async ``list[float]``)
    on top of its own synchronous ``encode``.

    Caveat: the ``[ENT]`` marker embedding is randomly initialised and requires
    fine-tuning to be meaningful`.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", trained_checkpoint: bool = False):
        if not trained_checkpoint:
            raise RuntimeError(
                "EnvelopeBiEncoder is an experimental research branch (Option C from issue_l06). "
                "Its special [ENT] markers require fine-tuning to produce meaningful vectors. "
                "Do not use this class in production unless you pass a trained checkpoint path "
                "and set trained_checkpoint=True."
            )
        from transformers import AutoModel, AutoTokenizer

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer: "PreTrainedTokenizer" = AutoTokenizer.from_pretrained(model_name)

        # Add special tokens for epistemic bounding
        special_tokens_dict = {'additional_special_tokens': ['[ENT]', '[\\ENT]']}
        self.tokenizer.add_special_tokens(special_tokens_dict)

        self.model: "PreTrainedModel" = AutoModel.from_pretrained(model_name)
        self.model.resize_token_embeddings(len(self.tokenizer))
        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def encode(self, texts: list[str]) -> torch.Tensor:
        """
        Encode a batch of textual mention context windows or structural neighborhoods.
        For textual mention contexts containing `[ENT]`, pools exactly at that marker.
        For structural neighborhoods without `[ENT]`, falls back to `[CLS]` pooling.
        """
        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        outputs = self.model(**inputs)
        last_hidden_state = outputs.last_hidden_state  # [batch_size, seq_len, hidden_size]

        batch_size = last_hidden_state.size(0)
        pooled_embeddings = []

        ent_token_id = self.tokenizer.convert_tokens_to_ids("[ENT]")

        for i in range(batch_size):
            input_ids = inputs['input_ids'][i]
            # Find index of [ENT] marker
            ent_indices = (input_ids == ent_token_id).nonzero(as_tuple=True)[0]

            if len(ent_indices) > 0:
                # Use the first [ENT] marker's hidden state (h_j)
                idx = ent_indices[0]
                pooled_embeddings.append(last_hidden_state[i, idx, :])
            else:
                # Fallback to [CLS] if no marker (e.g. for structural graphs)
                pooled_embeddings.append(last_hidden_state[i, 0, :])

        return torch.stack(pooled_embeddings)

    async def aget_text_embedding(self, text: str) -> list[float]:
        batch = await self.aget_text_embedding_batch([text])
        return batch[0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import asyncio

        tensor = await asyncio.to_thread(self.encode, list(texts))
        return [[float(x) for x in row] for row in tensor.tolist()]


class DenseEntityLinker(EntityLinker):
    """
    Entity linker using dense retrieval (bi-encoder) and structural reranking (cross-encoder).

    Parameters
    ----------
    embedding_model : EmbeddingModel | str | None, optional
        Bi-encoder used to embed the mention envelope and candidate envelopes.
        Must satisfy :class:`EmbeddingModel`. If None, defaults to :class:`HuggingFaceEmbeddingModel`.
    cross_encoder : CrossEncoder | None, optional
        Reranker scoring ``(mention envelope, candidate structural envelope)`` pairs. Must
        satisfy :class:`CrossEncoder` and return probability-like scores.
    tau : float, default 0.85
        Acceptance threshold on the cross-encoder score in ``[0, 1]``.
    top_k : int, default 10
        Number of bi-encoder candidates forwarded to the cross-encoder.
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel | str | None = None,
        cross_encoder: CrossEncoder | None = None,
        tau: float = 0.85,
        top_k: int = 10,
    ):
        from episteme_pipeline.protocols.extractors import HuggingFaceEmbeddingModel

        if embedding_model is None:
            self.embedding_model: EmbeddingModel = HuggingFaceEmbeddingModel()
        elif isinstance(embedding_model, str):
            self.embedding_model = HuggingFaceEmbeddingModel(model_name=embedding_model)
        else:
            self.embedding_model = ensure_embedding_model(embedding_model)

        self._cross_encoder = cross_encoder
        self.tau = tau
        self.top_k = top_k
        # Candidate envelope cache
        # Key: entity.id
        # Value: (bi-encoder_text, bi-encoder_vector)
        self._candidate_cache: dict[str, tuple[str, list[float]]] = {}

    @property
    def cross_encoder(self) -> CrossEncoder:
        if self._cross_encoder is None:
            from episteme_pipeline.phases.phase3_global_relations.rerankers import SentenceTransformerCrossEncoderReranker
            from episteme_pipeline.config import PipelineConfig

            self._cross_encoder = SentenceTransformerCrossEncoderReranker(
                model_name=PipelineConfig().default_reranker_model
            )
        return self._cross_encoder

    @cross_encoder.setter
    def cross_encoder(self, val: CrossEncoder | None) -> None:
        self._cross_encoder = val

    @property
    def event_emitter(self) -> EventEmitter:
        from episteme_pipeline.events.context import get_event_emitter
        return get_event_emitter()

    @staticmethod
    def _canonical_entity_string(candidate: L2Entity) -> str:
        """Format candidate entity for bi-encoder embedding with explicit type grounding."""
        return f"[{candidate.label}] {candidate.name}: {candidate.description or ''}"

    async def _populate_candidate_cache(self, candidates: list[L2Entity], graph_store: GraphReader) -> None:
        """Pre-fetch basic texts and embeddings for new or stale candidates."""
        stale_candidates = []
        stale_basic_texts = []
        for c in candidates:
            basic_text = self._canonical_entity_string(c)
            cached = self._candidate_cache.get(c.id)
            if not cached or cached[0] != basic_text:
                stale_candidates.append(c)
                stale_basic_texts.append(basic_text)

        if not stale_candidates:
            return

        fresh_vectors = await self.embedding_model.aget_text_embedding_batch(stale_basic_texts)
        for c, b_text, vec in zip(stale_candidates, stale_basic_texts, fresh_vectors):
            self._candidate_cache[c.id] = (b_text, vec)

    async def _candidate_embeddings(self, candidates: list[L2Entity]) -> torch.Tensor:
        """Return vectors from cache as float tensor."""
        embs = [self._candidate_cache[c.id][1] for c in candidates]
        return as_tensor(embs)

    async def link(
        self,
        mention: L2Entity,
        graph_store: GraphReader,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> L2Entity | None:
        effective_top_k = self.top_k if top_k is None else top_k
        tau = self.tau if threshold is None else threshold

        if not mention.textual_envelope:
            logger.warning(f"Mention {mention.name} lacks textual envelope. Raising UnlinkableMentionError.")
            raise UnlinkableMentionError(f"Mention {mention.name} lacks textual envelope.")

        # 1. Bi-Encoder: Cosine Similarity over L2-normalized embeddings
        T_n = f"[{mention.label}] {mention.textual_envelope}"
        raw_T_n_emb = await self.embedding_model.aget_text_embedding_batch([T_n])
        T_n_emb = as_tensor(raw_T_n_emb)[0]
        # L2-normalize mention vector
        T_n_emb = torch.nn.functional.normalize(T_n_emb, p=2, dim=0)

        candidates = await graph_store.get_entities()
        if not candidates:
            return None

        # Pre-fetch and cache vectors
        await self._populate_candidate_cache(candidates, graph_store)
        G_embs = await self._candidate_embeddings(candidates)

        # L2-normalize candidate vectors
        G_embs = torch.nn.functional.normalize(G_embs, p=2, dim=1)

        # Cosine similarity (since both are normalized, dot product = cosine)
        scores = torch.matmul(G_embs, T_n_emb)
        top_k_indices = torch.topk(scores, min(effective_top_k, len(candidates))).indices

        top_candidates = [candidates[i] for i in top_k_indices]
        top_scores = scores[top_k_indices].tolist()

        # Emit candidates retrieved event
        self.event_emitter.emit(
            EntityLinkingCandidatesRetrieved(
                mention_id=mention.id,
                mention_name=mention.name,
                candidate_count=len(top_candidates),
                candidates=[
                    {"id": c.id, "name": c.name, "score": float(s)}
                    for c, s in zip(top_candidates, top_scores)
                ]
            )
        )

        # 2. Cross-Encoder: Structural Evaluation (L07 Option B)
        # Fetch actual 1-hop subgraph ONLY for the top-k candidates
        import asyncio
        from episteme_pipeline.utils import format_envelope
        from episteme_pipeline.prompts.input_formatters import InputFormatStrategy

        tasks = [graph_store.get_neighborhood(c.id, depth=1) for c in top_candidates]
        subgraphs = await asyncio.gather(*tasks, return_exceptions=True)

        empty_subgraph = SubGraph(center_id="", nodes=[], triples=[], depth=0)
        top_G_structs = []
        for c, sg in zip(top_candidates, subgraphs):
            if isinstance(sg, Exception):
                logger.warning(f"Failed to fetch neighborhood for cross-encoder reranking of {c.name}: {sg}")
                sg = SubGraph(center_id=c.id, nodes=[c], triples=[], depth=1)
            top_G_structs.append(format_envelope(sg, empty_subgraph, strategy=InputFormatStrategy.TEXT))

        # [CLS] T_n [SEP] G_k_struct [SEP]
        cross_inputs = [(T_n, G_k_struct) for G_k_struct in top_G_structs]
        cross_scores = normalize_scores(self.cross_encoder.predict(cross_inputs))

        best_idx = argmax(cross_scores)
        best_score = cross_scores[best_idx]
        best_candidate = top_candidates[best_idx]

        accepted = best_score >= tau

        # Emit reranker score event
        self.event_emitter.emit(
            EntityLinkingReranked(
                mention_id=mention.id,
                mention_name=mention.name,
                candidate_id=best_candidate.id,
                candidate_name=best_candidate.name,
                score=best_score,
                accepted=accepted,
                threshold=tau,
            )
        )

        # 3. Resolution Threshold
        if accepted:
            logger.debug(f"DenseLinked {mention.name} -> {best_candidate.name} (Score: {best_score})")
            return best_candidate

        # Pass to LLM Reasoner (returns None to mint novel node)
        logger.debug(f"DenseLinker failed to cross threshold tau={tau} for {mention.name}. Max score: {best_score}")
        return None
