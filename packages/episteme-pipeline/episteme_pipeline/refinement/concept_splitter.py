"""Targeted polysemy concept splitting handler (ISSUE-053).

Implements :class:`ConceptionConceptSplitter`, satisfying
:class:`~episteme_pipeline.protocols.refinement.TargetedConceptSplitter` and
:class:`~episteme_pipeline.protocols.fingerprint.Fingerprintable`.

Splits conflated hub :class:`~episteme_pipeline.contracts.domain.L2Entity` nodes
flagged by ``POLYSEMY_COLLISION`` deficits into sense-disambiguated entities,
emits ``cannot_link_pairs`` to prevent Phase 3b re-merging, and rewires strictly
the local/global triples and theory atoms grounded in affected chunks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, Field, field_validator

from episteme_pipeline.contracts.domain import (
    CandidatePair,
    EntityConception,
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    L2Triple,
    RefinementDelta,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    ComponentCompleted,
    ComponentStarted,
    EntityProcessed,
)
from episteme_pipeline.llm.structured import StructuredLLM, ensure_structured_llm
from episteme_pipeline.phases.phase4_entity_maturation import ConceptionClusterer
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.entity_maturation import ConceptionClustererProtocol
from episteme_pipeline.protocols.extractors import (
    EmbeddingModel,
    GlobalRelationExtractor,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig
from episteme_pipeline.utils.similarity import l2_normalize

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactExecutionContext,
        EpistemicStateView,
    )

logger = logging.getLogger(__name__)


DEFAULT_CONCEPT_SPLIT_PROMPT = """\
You are an expert in philosophical ontology, lexical semantics, and structuralist metatheory.
A hub entity appears to conflate two or more incompatible theoretical senses across contexts.
Partition ONLY the provided contexts of this entity into distinct conceptual senses.

### Target Entity
ID: {entity_id}
Name: {entity_name}
Type: {entity_label}
Description: {entity_description}

### Deficit Context
Theory ID: {theory_id}
Theory Lens: {theory_lens}
Rationale: {rationale}

### Conflicting Argument Atoms
{entity_atoms}

### Entity Source Chunks
{source_chunks}

### Instructions
1. Identify at least 2 distinct conceptual senses present in the provided chunks: {allowed_chunk_ids}.
2. Assign each sense a concise ``perspective`` label, a ``description``, and the exact subset of
   ``chunk_ids`` from [{allowed_chunk_ids}] that belong to that sense.
3. Do not invent chunk IDs outside [{allowed_chunk_ids}].
4. Output strictly valid JSON matching the schema.
"""


@runtime_checkable
class _StructuredPredictPort(Protocol):
    """Minimal structural port for objects exposing ``predict_structured``."""

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        """Predict a structured Pydantic output."""
        ...


class SplitSenseCandidate(BaseModel):
    """Structured LLM proposal for a single disambiguated entity sense.

    Attributes
    ----------
    perspective : str
        Concise theoretical, authorial, or cluster perspective label.
    description : str
        Sense-scoped conceptual description.
    chunk_ids : list of str, optional
        Source chunk identifiers assigned to this sense.
    confidence : float, default 0.85
        Sense assignment confidence in ``[0.0, 1.0]``.
    """

    perspective: str
    description: str
    chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    @field_validator("perspective", "description")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Sense perspective and description must not be empty.")
        return cleaned


class ConceptSplitOutput(BaseModel):
    """Structured LLM response containing proposed sense partitions.

    Attributes
    ----------
    senses : list of SplitSenseCandidate, optional
        Disambiguated sense partitions for the target entity.
    """

    senses: list[SplitSenseCandidate] = Field(default_factory=list)


@dataclass(slots=True)
class _SenseSpec:
    """Internal specification for one disambiguated entity sense."""

    perspective: str
    description: str
    chunk_ids: list[str]
    atom_ids: list[str]
    envelopes: list[str]
    dispersion: float | None = None
    confidence: float | None = None


def _normalize_structured_llm(llm: Any | None) -> StructuredLLM | _StructuredPredictPort | None:
    """Normalize an optional LLM backend to a structured prediction port."""
    if llm is None:
        return None
    if isinstance(llm, _StructuredPredictPort):
        return llm
    return ensure_structured_llm(llm, use_cache=False)


def _deterministic_text_embeddings(texts: list[str], dim: int = 64) -> np.ndarray:
    """Project texts into deterministic L2-normalized hashed BoW vectors.

    Parameters
    ----------
    texts : list of str
        Input text contexts.
    dim : int, default 64
        Projection dimensionality.

    Returns
    -------
    numpy.ndarray
        Normalized float32 matrix of shape ``(len(texts), dim)``.
    """
    mat = np.zeros((len(texts), dim), dtype=np.float32)
    for row_idx, text in enumerate(texts):
        tokens = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            col = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            mat[row_idx, col] += sign
    return l2_normalize(mat)


def _slugify_perspective(label: str) -> str:
    """Normalize a perspective label into a stable identifier segment."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", label.strip().lower()).strip("_")
    return cleaned or "sense"


class ConceptionConceptSplitter:
    """Targeted concept splitter for ``POLYSEMY_COLLISION`` deficits.

    Splits conflated L2 hub entities deterministically from ``entity.conceptions``
    (ADR-0023), via :class:`ConceptionClusterer` stratification, optional LLM sense
    partitioning, or deterministic chunk/atom conflict partitioning, while leaving
    all unaffected chunks, entities, triples, and atoms completely untouched.

    Parameters
    ----------
    conception_clusterer : ConceptionClustererProtocol or None, optional
        Conception clustering strategy used to stratify multi-modal mention
        contexts. Defaults to :class:`ConceptionClusterer`.
    global_extractor : GlobalRelationExtractor or None, optional
        Optional Phase 3 global relation extractor run strictly on localized pairs
        involving the newly split sense entities.
    llm : StructuredLLM or Any or None, optional
        Optional structured LLM used when conception/deterministic clues are
        insufficient.
    embedding_model : EmbeddingModel or None, optional
        Optional bi-encoder used with ``conception_clusterer`` on mention envelopes.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.
    prompts : StructuredPromptBundle or str or None, optional
        Optional custom prompt bundle for LLM-assisted sense splitting.
    strategy : Any, default "direct_constrained"
        Structured decoding strategy passed to ``llm.predict_structured``.
    """

    def __init__(
        self,
        conception_clusterer: ConceptionClustererProtocol | None = None,
        *,
        global_extractor: GlobalRelationExtractor | None = None,
        llm: StructuredLLM | Any | None = None,
        embedding_model: EmbeddingModel | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = "direct_constrained",
    ) -> None:
        self.conception_clusterer: ConceptionClustererProtocol = (
            conception_clusterer
            if conception_clusterer is not None
            else ConceptionClusterer()
        )
        self.global_extractor = global_extractor
        self.llm = _normalize_structured_llm(llm)
        self.embedding_model = embedding_model
        self.schema = schema
        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        else:
            self.prompts = StructuredPromptBundle(
                direct_template=prompts or DEFAULT_CONCEPT_SPLIT_PROMPT,
                name="refinement_concept_split",
            )
        self.strategy = strategy

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache lineage.

        Returns
        -------
        dict of str to Any
            JSON-serializable configuration snapshot including sub-components.
        """
        strategy_str = (
            self.strategy.value if isinstance(self.strategy, Enum) else str(self.strategy)
        )
        return {
            "class": self.__class__.__name__,
            "schema_version": self.schema.version,
            "strategy": strategy_str,
            "prompts": self.prompts.fingerprint(),
            "conception_clusterer": self.conception_clusterer.fingerprint(),
            "global_extractor": (
                self.global_extractor.fingerprint()
                if isinstance(self.global_extractor, Fingerprintable)
                else fingerprint_method(self.global_extractor)
            ),
            "llm": (
                self.llm.fingerprint()
                if isinstance(self.llm, Fingerprintable)
                else fingerprint_method(self.llm)
            ),
            "embedding_model": (
                self.embedding_model.fingerprint()
                if isinstance(self.embedding_model, Fingerprintable)
                else fingerprint_method(self.embedding_model)
            ),
        }

    def _resolve_target_entities(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        all_atoms: list[TheoryAtom],
        all_relations: list[TheoryRelation],
    ) -> list[L2Entity]:
        """Identify ONLY the L2 entities explicitly implicated by ``deficit``."""
        entities_by_id: dict[str, L2Entity] = {e.id: e for e in state.entities}
        atoms_by_id: dict[str, TheoryAtom] = {a.id: a for a in all_atoms}

        selected_ids: list[str] = []
        seen: set[str] = set()

        def _add_entity_id(eid: str) -> None:
            if eid in entities_by_id and eid not in seen:
                seen.add(eid)
                selected_ids.append(eid)

        for eid in deficit.target_entity_ids:
            _add_entity_id(eid)

        if not selected_ids:
            for aid in deficit.target_atom_ids:
                atom = atoms_by_id.get(aid)
                if atom is not None:
                    for eid in atom.entity_ids:
                        _add_entity_id(eid)

        if not selected_ids and deficit.target_relation_ids:
            rel_id_set = set(deficit.target_relation_ids)
            for rel in all_relations:
                if rel.relation_id in rel_id_set or (
                    rel.id is not None and rel.id in rel_id_set
                ):
                    for aid in (*rel.effective_premise_ids, rel.target_id):
                        atom = atoms_by_id.get(aid)
                        if atom is not None:
                            for eid in atom.entity_ids:
                                _add_entity_id(eid)

        if not selected_ids and deficit.target_chunk_ids:
            chunk_set = set(deficit.target_chunk_ids)
            polysemous_candidates = [
                e
                for e in state.entities
                if any(cid in chunk_set for cid in e.source_chunk_ids)
                and (len(e.conceptions) >= 2 or (e.polysemy_variance or 0.0) > 0.0)
            ]
            candidates = (
                polysemous_candidates
                if polysemous_candidates
                else [
                    e
                    for e in state.entities
                    if any(cid in chunk_set for cid in e.source_chunk_ids)
                ]
            )
            for ent in candidates:
                _add_entity_id(ent.id)

        return [entities_by_id[eid] for eid in selected_ids]

    def _collect_entity_chunks_and_atoms(
        self,
        entity: L2Entity,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        all_atoms: list[TheoryAtom],
    ) -> tuple[list[str], list[TheoryAtom]]:
        """Gather deduplicated chunk IDs and atoms associated with ``entity``."""
        chunk_ids: list[str] = list(entity.source_chunk_ids)
        for rec in state.entity_mentions_by_id.get(entity.id, []):
            cid = rec.get("chunk_id", "")
            if cid:
                chunk_ids.append(cid)
        for conc in entity.conceptions:
            chunk_ids.extend(conc.source_chunk_ids)

        entity_atoms = [a for a in all_atoms if entity.id in a.entity_ids]
        for atom in entity_atoms:
            if atom.source_chunk_id:
                chunk_ids.append(atom.source_chunk_id)

        if deficit.target_chunk_ids:
            target_atom_set = set(deficit.target_atom_ids)
            for atom in all_atoms:
                if atom.id in target_atom_set and atom.source_chunk_id:
                    chunk_ids.append(atom.source_chunk_id)

        deduped_chunks = list(dict.fromkeys(cid for cid in chunk_ids if cid))
        return deduped_chunks, entity_atoms

    def _partition_from_conceptions(
        self,
        entity: L2Entity,
        candidate_chunks: list[str],
        entity_atoms: list[TheoryAtom],
        chunks_by_id: dict[str, L1Chunk],
    ) -> list[_SenseSpec]:
        """Partition an entity into sense specs from its ADR-0023 ``EntityConception``s."""
        if len(entity.conceptions) < 2:
            return []

        assigned_by_idx: list[list[str]] = [
            list(dict.fromkeys(c.source_chunk_ids)) for c in entity.conceptions
        ]
        already_assigned: set[str] = {
            cid for cids in assigned_by_idx for cid in cids
        }
        persp_to_idx: dict[str, int] = {
            c.perspective.strip().lower(): idx
            for idx, c in enumerate(entity.conceptions)
            if c.perspective.strip()
        }

        for cid in candidate_chunks:
            if cid in already_assigned:
                continue
            chunk = chunks_by_id.get(cid)
            matched_idx: int | None = None
            for atom in entity_atoms:
                if atom.source_chunk_id == cid and atom.attributed_to:
                    cand_idx = persp_to_idx.get(atom.attributed_to.strip().lower())
                    if cand_idx is not None:
                        matched_idx = cand_idx
                        break
            if matched_idx is None and chunk is not None:
                matched_idx = persp_to_idx.get(chunk.source_doc_id.strip().lower())
            if matched_idx is not None:
                assigned_by_idx[matched_idx].append(cid)
                already_assigned.add(cid)

        specs: list[_SenseSpec] = []
        for idx, conc in enumerate(entity.conceptions):
            cids = list(dict.fromkeys(assigned_by_idx[idx]))
            if not cids:
                continue
            cid_set = set(cids)
            atom_ids = [a.id for a in entity_atoms if a.source_chunk_id in cid_set]
            envelopes = list(conc.representative_envelopes)
            if not envelopes:
                envelopes = [
                    chunks_by_id[cid].text
                    for cid in cids
                    if cid in chunks_by_id and chunks_by_id[cid].text
                ]
            specs.append(
                _SenseSpec(
                    perspective=conc.perspective,
                    description=conc.description or entity.description or entity.name,
                    chunk_ids=cids,
                    atom_ids=atom_ids,
                    envelopes=envelopes,
                    dispersion=conc.centroid_dispersion,
                    confidence=conc.confidence,
                )
            )
        return specs if len(specs) >= 2 else []

    def _gather_envelopes_for_clustering(
        self,
        entity: L2Entity,
        candidate_chunks: list[str],
        state: EpistemicStateView,
        chunks_by_id: dict[str, L1Chunk],
        entity_atoms: list[TheoryAtom],
    ) -> tuple[list[str], list[str], list[str]]:
        """Collect aligned ``(envelopes, chunk_ids, perspectives)`` for clustering."""
        envelopes: list[str] = []
        chunk_ids: list[str] = []
        perspectives: list[str] = []

        atom_attr_by_chunk: dict[str, str] = {}
        for atom in entity_atoms:
            if atom.source_chunk_id and atom.attributed_to:
                atom_attr_by_chunk.setdefault(
                    atom.source_chunk_id, atom.attributed_to.strip()
                )

        seen_chunks: set[str] = set()
        for rec in state.entity_mentions_by_id.get(entity.id, []):
            cid = rec.get("chunk_id", "")
            env_text = rec.get("textual_envelope", "")
            if not env_text and cid in chunks_by_id:
                env_text = chunks_by_id[cid].text
            if env_text and cid:
                seen_chunks.add(cid)
                chunk = chunks_by_id.get(cid)
                persp = (
                    rec.get("perspective", "")
                    or atom_attr_by_chunk.get(cid, "")
                    or (chunk.source_doc_id if chunk is not None else "")
                )
                envelopes.append(env_text)
                chunk_ids.append(cid)
                perspectives.append(persp)

        for cid in candidate_chunks:
            if cid in seen_chunks:
                continue
            chunk = chunks_by_id.get(cid)
            text = chunk.text if chunk is not None else ""
            if not text:
                atom_texts = [a.text for a in entity_atoms if a.source_chunk_id == cid]
                text = " ".join(atom_texts)
            if text:
                persp = atom_attr_by_chunk.get(cid, "") or (
                    chunk.source_doc_id if chunk is not None else ""
                )
                envelopes.append(text)
                chunk_ids.append(cid)
                perspectives.append(persp)

        return envelopes, chunk_ids, perspectives

    def _clusters_to_specs(
        self,
        entity: L2Entity,
        clusters: list[Any],
        entity_atoms: list[TheoryAtom],
    ) -> list[_SenseSpec]:
        """Convert :class:`ConceptionCluster` outputs into ``_SenseSpec`` objects."""
        specs: list[_SenseSpec] = []
        for idx, cluster in enumerate(clusters, start=1):
            cids = list(dict.fromkeys(cid for cid in cluster.chunk_ids if cid))
            if not cids:
                continue
            cid_set = set(cids)
            atom_ids = [a.id for a in entity_atoms if a.source_chunk_id in cid_set]
            persp = str(cluster.perspective).strip() or f"sense_{idx}"
            envs = list(cluster.envelopes)
            desc = (
                f"{entity.name} in {persp} context: {envs[0]}"
                if envs
                else (entity.description or f"{entity.name} ({persp})")
            )
            specs.append(
                _SenseSpec(
                    perspective=persp,
                    description=desc,
                    chunk_ids=cids,
                    atom_ids=atom_ids,
                    envelopes=envs,
                    dispersion=float(cluster.centroid_dispersion),
                    confidence=float(cluster.confidence),
                )
            )
        return specs if len(specs) >= 2 else []

    def _partition_deterministically(
        self,
        entity: L2Entity,
        deficit: EpistemicDeficit,
        candidate_chunks: list[str],
        entity_atoms: list[TheoryAtom],
        all_relations: list[TheoryRelation],
        chunks_by_id: dict[str, L1Chunk],
    ) -> list[_SenseSpec]:
        """Partition an entity deterministically via perspectives, conflicts, or clusters."""
        # 1. Explicit attribution / document / intensional-mode grouping across chunks
        if len(candidate_chunks) >= 2:
            groups: dict[str, list[str]] = {}
            doc_ids = {
                chunks_by_id[cid].source_doc_id
                for cid in candidate_chunks
                if cid in chunks_by_id and chunks_by_id[cid].source_doc_id
            }
            for cid in candidate_chunks:
                chunk_atoms = [a for a in entity_atoms if a.source_chunk_id == cid]
                attr = next((a.attributed_to.strip() for a in chunk_atoms if a.attributed_to), "")
                if attr:
                    key = attr
                elif cid in chunks_by_id and len(doc_ids) >= 2:
                    key = chunks_by_id[cid].source_doc_id
                elif any(a.intensional_mode != "asserted" for a in chunk_atoms):
                    key = next(
                        a.intensional_mode
                        for a in chunk_atoms
                        if a.intensional_mode != "asserted"
                    )
                else:
                    key = ""
                if key:
                    groups.setdefault(key, []).append(cid)

            if len(groups) >= 2:
                # Assign any ungrouped candidate chunks only if matched; otherwise preserve groups
                specs: list[_SenseSpec] = []
                for persp, cids in sorted(groups.items()):
                    cid_set = set(cids)
                    envs = [
                        chunks_by_id[cid].text
                        for cid in cids
                        if cid in chunks_by_id and chunks_by_id[cid].text
                    ]
                    atom_ids = [a.id for a in entity_atoms if a.source_chunk_id in cid_set]
                    desc = (
                        f"{entity.name} [{persp}]: {envs[0]}"
                        if envs
                        else f"{entity.name} ({persp})"
                    )
                    specs.append(
                        _SenseSpec(
                            perspective=persp,
                            description=desc,
                            chunk_ids=cids,
                            atom_ids=atom_ids,
                            envelopes=envs,
                            confidence=entity.confidence,
                        )
                    )
                if len(specs) >= 2:
                    return specs

        # 2. Dialectical / low-tenability relation conflict partitioning across atoms/chunks
        relevant_atoms = list(entity_atoms)
        if not relevant_atoms:
            relevant_atom_ids = set(deficit.target_atom_ids)
            relevant_atoms = [
                a for a in entity_atoms if a.id in relevant_atom_ids
            ]

        if len(relevant_atoms) >= 2:
            rel_atom_ids = {a.id for a in relevant_atoms}
            support_side: list[TheoryAtom] = []
            conflict_side: list[TheoryAtom] = []
            for rel in all_relations:
                is_conflict = self.schema.is_attack_relation(rel.relation_type) or (
                    rel.edge_tenability is not None and rel.edge_tenability < 0.5
                )
                if is_conflict and (
                    rel.source_id in rel_atom_ids or rel.target_id in rel_atom_ids
                ):
                    for atom in relevant_atoms:
                        if atom.id == rel.source_id and atom not in conflict_side:
                            conflict_side.append(atom)
                        elif atom.id == rel.target_id and atom not in support_side:
                            support_side.append(atom)
            if support_side and conflict_side:
                s1_chunks = list(
                    dict.fromkeys(a.source_chunk_id for a in support_side if a.source_chunk_id)
                )
                s2_chunks = list(
                    dict.fromkeys(a.source_chunk_id for a in conflict_side if a.source_chunk_id)
                )
                return [
                    _SenseSpec(
                        perspective="primary_theory_sense",
                        description=f"{entity.name} [primary]: {support_side[0].text}",
                        chunk_ids=s1_chunks,
                        atom_ids=[a.id for a in support_side],
                        envelopes=[a.text for a in support_side],
                        confidence=entity.confidence,
                    ),
                    _SenseSpec(
                        perspective="conflicting_theory_sense",
                        description=f"{entity.name} [conflicting]: {conflict_side[0].text}",
                        chunk_ids=s2_chunks,
                        atom_ids=[a.id for a in conflict_side],
                        envelopes=[a.text for a in conflict_side],
                        confidence=entity.confidence,
                    ),
                ]

        # 3. Fallback chunk-level split when POLYSEMY_COLLISION spans >= 2 chunks
        if len(candidate_chunks) >= 2:
            lens_perspectives = deficit.theory_lens.get("perspectives")
            labels = (
                [str(p) for p in lens_perspectives]
                if isinstance(lens_perspectives, list)
                else []
            )
            specs = []
            for idx, cid in enumerate(candidate_chunks[:4], start=1):
                chunk = chunks_by_id.get(cid)
                persp = (
                    labels[idx - 1]
                    if idx - 1 < len(labels) and labels[idx - 1].strip()
                    else (chunk.source_doc_id if chunk and chunk.source_doc_id else f"context_{idx}")
                )
                if any(s.perspective == persp for s in specs):
                    persp = f"{persp}_{cid}"
                env = chunk.text if chunk is not None else ""
                atom_ids = [a.id for a in entity_atoms if a.source_chunk_id == cid]
                specs.append(
                    _SenseSpec(
                        perspective=persp,
                        description=f"{entity.name} [{persp}]: {env}" if env else f"{entity.name} ({persp})",
                        chunk_ids=[cid],
                        atom_ids=atom_ids,
                        envelopes=[env] if env else [],
                        confidence=entity.confidence,
                    )
                )
            if len(specs) >= 2:
                return specs

        return []

    async def _partition_entity_senses(
        self,
        entity: L2Entity,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        all_atoms: list[TheoryAtom],
        all_relations: list[TheoryRelation],
        chunks_by_id: dict[str, L1Chunk],
    ) -> list[_SenseSpec]:
        """Select the highest-fidelity sense partition for ``entity``."""
        candidate_chunks, entity_atoms = self._collect_entity_chunks_and_atoms(
            entity, deficit, state, all_atoms
        )

        # Path 1: Existing ADR-0023 EntityConceptions
        specs = self._partition_from_conceptions(
            entity, candidate_chunks, entity_atoms, chunks_by_id
        )
        if specs:
            return specs

        envelopes, env_chunk_ids, env_perspectives = (
            self._gather_envelopes_for_clustering(
                entity, candidate_chunks, state, chunks_by_id, entity_atoms
            )
        )

        # Path 2: ConceptionClusterer with injected EmbeddingModel
        if self.embedding_model is not None and len(envelopes) >= 2:
            raw_embs = await self.embedding_model.aget_text_embedding_batch(envelopes)
            emb_arr = np.asarray(raw_embs, dtype=np.float32)
            _, clusters = self.conception_clusterer.stratify(
                envelopes,
                emb_arr,
                envelope_chunk_ids=env_chunk_ids,
                envelope_perspectives=env_perspectives,
            )
            specs = self._clusters_to_specs(entity, clusters, entity_atoms)
            if specs:
                return specs

        # Path 3: Optional LLM sense clustering strictly over entity's chunks
        if self.llm is not None and candidate_chunks:
            chunk_set = set(candidate_chunks)
            chunks_text = "\n\n".join(
                f"[{cid}] {chunks_by_id[cid].text}"
                for cid in candidate_chunks
                if cid in chunks_by_id
            )
            atoms_text = (
                "\n".join(
                    f"- [{a.id}] (chunk={a.source_chunk_id}, mode={a.intensional_mode}, "
                    f"attributed_to={a.attributed_to}) {a.text}"
                    for a in entity_atoms
                )
                or "None."
            )
            raw_split: ConceptSplitOutput = await self.llm.predict_structured(
                ConceptSplitOutput,
                self.prompts,
                strategy=self.strategy,
                entity_id=entity.id,
                entity_name=entity.name,
                entity_label=entity.label,
                entity_description=entity.description or entity.name,
                theory_id=deficit.theory_id or "unspecified",
                theory_lens=json.dumps(
                    deficit.theory_lens, sort_keys=True, ensure_ascii=False
                ),
                rationale=deficit.rationale or "Polysemy collision detected.",
                entity_atoms=atoms_text,
                source_chunks=chunks_text or "No chunk text available.",
                allowed_chunk_ids=", ".join(candidate_chunks),
            )
            llm_specs: list[_SenseSpec] = []
            for cand in raw_split.senses:
                valid_cids = [cid for cid in cand.chunk_ids if cid in chunk_set]
                if not valid_cids:
                    continue
                vc_set = set(valid_cids)
                llm_specs.append(
                    _SenseSpec(
                        perspective=cand.perspective,
                        description=cand.description,
                        chunk_ids=list(dict.fromkeys(valid_cids)),
                        atom_ids=[a.id for a in entity_atoms if a.source_chunk_id in vc_set],
                        envelopes=[
                            chunks_by_id[cid].text
                            for cid in valid_cids
                            if cid in chunks_by_id and chunks_by_id[cid].text
                        ],
                        confidence=cand.confidence,
                    )
                )
            if len(llm_specs) >= 2:
                return llm_specs

        # Path 4a: ConceptionClusterer on deterministic lexical vectors
        if len(envelopes) >= 2 and len(set(env_chunk_ids)) >= 2:
            lex_vecs = _deterministic_text_embeddings(envelopes)
            _, lex_clusters = self.conception_clusterer.stratify(
                envelopes,
                lex_vecs,
                envelope_chunk_ids=env_chunk_ids,
                envelope_perspectives=env_perspectives,
            )
            specs = self._clusters_to_specs(entity, lex_clusters, entity_atoms)
            if specs:
                return specs

        # Path 4b: Deterministic attribution / document / conflict partitioning
        return self._partition_deterministically(
            entity,
            deficit,
            candidate_chunks,
            entity_atoms,
            all_relations,
            chunks_by_id,
        )

    async def split_concept(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        """Split polysemous hub entity/entities flagged by ``deficit``.

        Parameters
        ----------
        deficit : EpistemicDeficit
            Target ``POLYSEMY_COLLISION`` deficit naming implicated entities,
            atoms, relations, and/or chunks.
        state : EpistemicStateView
            Cumulative epistemic state view providing entities, conceptions,
            triples, and L3 theory atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for event lineage.

        Returns
        -------
        RefinementDelta
            Delta containing split sense ``L2Entity`` instances,
            ``cannot_link_pairs``, and strictly localized rewritten triples and
            theory atoms.

        Raises
        ------
        ValueError
            If ``deficit.deficit_kind`` is not ``POLYSEMY_COLLISION``.
        """
        if deficit.deficit_kind != EpistemicDeficitKind.POLYSEMY_COLLISION:
            raise ValueError(
                f"ConceptionConceptSplitter only handles POLYSEMY_COLLISION deficits "
                f"(got {deficit.deficit_kind})."
            )

        run_id = context.run_id if context is not None else None
        next_pass = deficit.refinement_pass + 1
        emitter = get_event_emitter()
        comp_name = f"{self.__class__.__name__}:{deficit.deficit_id}"
        start_time = time.perf_counter()
        emitter.emit(
            ComponentStarted(
                run_id=run_id,
                phase="refinement",
                component_name=comp_name,
                input_description=(
                    f"entities={len(deficit.target_entity_ids)}, "
                    f"chunks={len(deficit.target_chunk_ids)}"
                ),
            )
        )

        try:
            all_atoms = (
                state.canonical_theory_atoms
                if state.canonical_theory_atoms
                else state.theory_atoms
            )
            all_relations = (
                state.canonical_theory_relations
                if state.canonical_theory_relations
                else state.theory_relations
            )
            chunks_by_id: dict[str, L1Chunk] = {c.id: c for c in state.chunks}
            entities_by_id: dict[str, L2Entity] = {e.id: e for e in state.entities}

            target_entities = self._resolve_target_entities(
                deficit, state, all_atoms, all_relations
            )
            if not target_entities:
                emitter.emit(
                    ComponentCompleted(
                        run_id=run_id,
                        phase="refinement",
                        component_name=comp_name,
                        duration_seconds=time.perf_counter() - start_time,
                        output_description="no_target_entities",
                        success=True,
                    )
                )
                return RefinementDelta(refinement_pass=next_pass)

            new_entities: list[L2Entity] = []
            split_senses_only: list[L2Entity] = []
            cannot_link_pairs: list[tuple[str, str]] = []
            seen_cannot_link: set[tuple[str, str]] = set()
            chunk_to_sense_map: dict[tuple[str, str], str] = {}
            atom_to_sense_map: dict[tuple[str, str], str] = {}
            split_orig_ids: set[str] = set()

            for entity in target_entities:
                specs = await self._partition_entity_senses(
                    entity, deficit, state, all_atoms, all_relations, chunks_by_id
                )
                if len(specs) < 2:
                    continue

                split_orig_ids.add(entity.id)
                senses_for_entity: list[L2Entity] = []
                assigned_chunks: set[str] = set()

                for idx, spec in enumerate(specs, start=1):
                    sense_id = f"{entity.id}__sense_{idx}"
                    sense_name = f"{entity.name} ({spec.perspective})"
                    persp_slug = _slugify_perspective(spec.perspective)
                    conception = EntityConception(
                        id=f"{sense_id}::conception::{persp_slug}",
                        entity_id=sense_id,
                        perspective=spec.perspective,
                        description=spec.description,
                        representative_envelopes=list(spec.envelopes[:5]),
                        source_chunk_ids=list(spec.chunk_ids),
                        centroid_dispersion=spec.dispersion,
                        confidence=spec.confidence,
                    )
                    sense_entity = L2Entity(
                        id=sense_id,
                        label=entity.label,
                        name=sense_name,
                        description=spec.description,
                        textual_envelope=(
                            spec.envelopes[0]
                            if spec.envelopes
                            else entity.textual_envelope
                        ),
                        is_mature=True,
                        confidence=(
                            spec.confidence
                            if spec.confidence is not None
                            else entity.confidence
                        ),
                        text_anchor=entity.text_anchor,
                        source_chunk_ids=list(spec.chunk_ids),
                        conceptions=[conception],
                        polysemy_variance=spec.dispersion,
                    )
                    senses_for_entity.append(sense_entity)
                    new_entities.append(sense_entity)
                    split_senses_only.append(sense_entity)

                    for cid in spec.chunk_ids:
                        assigned_chunks.add(cid)
                        chunk_to_sense_map.setdefault((entity.id, cid), sense_id)
                    for aid in spec.atom_ids:
                        atom_to_sense_map.setdefault((entity.id, aid), sense_id)

                    emitter.emit(
                        EntityProcessed(
                            run_id=run_id,
                            phase="refinement",
                            entity_id=sense_entity.id,
                            entity_name=sense_entity.name,
                            entity_type=sense_entity.label,
                        )
                    )

                # If entity retains chunks outside the split subset, preserve shrunk original
                unassigned_chunks = [
                    cid for cid in entity.source_chunk_ids if cid not in assigned_chunks
                ]
                if unassigned_chunks:
                    new_entities.append(
                        entity.model_copy(
                            update={"source_chunk_ids": unassigned_chunks}
                        )
                    )

                # Emit cannot-link constraints across all split senses & original hub
                for i, s1 in enumerate(senses_for_entity):
                    orig_pair = (
                        min(entity.id, s1.id),
                        max(entity.id, s1.id),
                    )
                    if orig_pair not in seen_cannot_link:
                        seen_cannot_link.add(orig_pair)
                        cannot_link_pairs.append((entity.id, s1.id))
                    for s2 in senses_for_entity[i + 1 :]:
                        sense_pair = (
                            min(s1.id, s2.id),
                            max(s1.id, s2.id),
                        )
                        if sense_pair not in seen_cannot_link:
                            seen_cannot_link.add(sense_pair)
                            cannot_link_pairs.append((s1.id, s2.id))

            if not split_orig_ids:
                emitter.emit(
                    ComponentCompleted(
                        run_id=run_id,
                        phase="refinement",
                        component_name=comp_name,
                        duration_seconds=time.perf_counter() - start_time,
                        output_description="no_splittable_senses",
                        success=True,
                    )
                )
                return RefinementDelta(refinement_pass=next_pass)

            def _rewire_triples(triples: list[L2Triple]) -> list[L2Triple]:
                rewritten: list[L2Triple] = []
                for triple in triples:
                    if triple.source_chunk_id is None:
                        continue
                    new_subj = chunk_to_sense_map.get(
                        (triple.subject_id, triple.source_chunk_id),
                        triple.subject_id,
                    )
                    new_obj = chunk_to_sense_map.get(
                        (triple.object_id, triple.source_chunk_id),
                        triple.object_id,
                    )
                    if new_subj != triple.subject_id or new_obj != triple.object_id:
                        rewritten.append(
                            triple.model_copy(
                                update={"subject_id": new_subj, "object_id": new_obj}
                            )
                        )
                return rewritten

            rewritten_local_triples = _rewire_triples(state.local_triples)
            rewritten_global_triples = _rewire_triples(state.global_triples)

            # Rewire ONLY TheoryAtoms whose chunk/atom maps to a split sense
            rewritten_atoms: list[TheoryAtom] = []
            for atom in all_atoms:
                if not any(eid in split_orig_ids for eid in atom.entity_ids):
                    continue
                new_eids: list[str] = []
                changed = False
                for eid in atom.entity_ids:
                    replacement = atom_to_sense_map.get((eid, atom.id))
                    if replacement is None and atom.source_chunk_id:
                        replacement = chunk_to_sense_map.get(
                            (eid, atom.source_chunk_id)
                        )
                    target_eid = replacement if replacement is not None else eid
                    if target_eid != eid:
                        changed = True
                    if target_eid not in new_eids:
                        new_eids.append(target_eid)
                if changed:
                    rewritten_atoms.append(
                        atom.model_copy(update={"entity_ids": new_eids})
                    )

            # Optionally run GlobalRelationExtractor strictly on pairs involving split senses
            if self.global_extractor is not None and split_senses_only:
                neighbor_ids: set[str] = set()
                for triple in [*state.local_triples, *state.global_triples]:
                    if (
                        triple.subject_id in split_orig_ids
                        and triple.object_id not in split_orig_ids
                    ):
                        neighbor_ids.add(triple.object_id)
                    elif (
                        triple.object_id in split_orig_ids
                        and triple.subject_id not in split_orig_ids
                    ):
                        neighbor_ids.add(triple.subject_id)

                sense_chunk_set = {
                    cid for s in split_senses_only for cid in s.source_chunk_ids
                }
                for ent in state.entities:
                    if ent.id not in split_orig_ids and any(
                        cid in sense_chunk_set for cid in ent.source_chunk_ids
                    ):
                        neighbor_ids.add(ent.id)

                candidate_pairs: list[CandidatePair] = []
                for i, s1 in enumerate(split_senses_only):
                    for s2 in split_senses_only[i + 1 :]:
                        candidate_pairs.append(CandidatePair(entity_a=s1, entity_b=s2))
                    for nid in sorted(neighbor_ids):
                        other = entities_by_id.get(nid)
                        if other is not None:
                            candidate_pairs.append(
                                CandidatePair(entity_a=s1, entity_b=other)
                            )

                if candidate_pairs:
                    reader = state.to_graph_reader()
                    for sense_ent in split_senses_only:
                        reader.register_entity(sense_ent)
                    for triple in [*rewritten_local_triples, *rewritten_global_triples]:
                        reader.register_triple(triple)

                    extracted_global, _ = await self.global_extractor.extract_pairs(
                        candidate_pairs,
                        reader,
                        self.schema,
                    )
                    seen_global_keys = {
                        (t.subject_id, t.predicate, t.object_id, t.scope)
                        for t in rewritten_global_triples
                    }
                    for gt in extracted_global:
                        gkey = (gt.subject_id, gt.predicate, gt.object_id, gt.scope)
                        if gkey not in seen_global_keys:
                            seen_global_keys.add(gkey)
                            rewritten_global_triples.append(gt)

            delta = RefinementDelta(
                entities=new_entities,
                local_triples=rewritten_local_triples,
                global_triples=rewritten_global_triples,
                theory_atoms=rewritten_atoms,
                cannot_link_pairs=cannot_link_pairs,
                resolved_deficit_ids=[deficit.deficit_id],
                refinement_pass=next_pass,
            )
            emitter.emit(
                ComponentCompleted(
                    run_id=run_id,
                    phase="refinement",
                    component_name=comp_name,
                    duration_seconds=time.perf_counter() - start_time,
                    output_description=(
                        f"split_entities={len(split_senses_only)}, "
                        f"cannot_link={len(cannot_link_pairs)}, "
                        f"rewritten_atoms={len(rewritten_atoms)}"
                    ),
                    success=True,
                )
            )
            return delta
        except Exception as exc:
            emitter.emit(
                ComponentCompleted(
                    run_id=run_id,
                    phase="refinement",
                    component_name=comp_name,
                    duration_seconds=time.perf_counter() - start_time,
                    output_description="failed",
                    success=False,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            )
            raise


__all__ = [
    "ConceptSplitOutput",
    "ConceptionConceptSplitter",
    "DEFAULT_CONCEPT_SPLIT_PROMPT",
    "SplitSenseCandidate",
]
