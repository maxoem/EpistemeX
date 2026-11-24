"""Targeted concept splitter resolving ``POLYSEMY_COLLISION`` deficits (ISSUE-053).

Implements :class:`ConceptionConceptSplitter`, satisfying
:class:`~episteme_pipeline.protocols.refinement.TargetedConceptSplitter`.

When Layer 3/4 tenability or controversy signals identify an entity hub
bridging incompatible theoretical clusters, ``ConceptionConceptSplitter``:

1. Applies a System 1 ``DecisionEngine.evaluate_choice`` triage gate (when a
   ``DecisionEngine`` is provided) to distinguish genuine conceptual polysemy
   from univocal dialectical disagreement before splitting.
2. Resolves strictly the entity/entities named or linked by the deficit (never
   pulling unrelated co-occurring entities or cross-entity chunks).
3. Partitions only that entity's chunks into distinct senses via pre-existing
   ``EntityConception`` strata, managed ``StructuredPromptBundle`` LLM sense
   extraction, real ``EmbeddingModel`` + ``ConceptionClusterer`` stratification,
   or explicit perspectival attribution (``attributed_to`` / ``theory_id``).
4. Mints new sense-qualified ``L2Entity`` contracts, records
   ``split_entity_parents`` and retires fully partitioned parent entities via
   ``retired_entity_ids``, emits ``cannot_link_pairs`` constraints, rewrites only
   affected triples and ``TheoryAtom``s, and optionally re-extracts global
   relations via the pipeline's Phase 3 ``GlobalRelationExtractor`` strategies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    EpistemicStateView,
)
from episteme_pipeline.config import (
    HermeneuticRefinementConfig,
)
from episteme_pipeline.contracts.domain import (
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
from episteme_pipeline.decision.cascade import (
    TriageDecision,
    should_audit_deterministically,
)
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import EntityProcessed
from episteme_pipeline.llm.structured import (
    StructuredLLM,
    StructuredPredictable,
    normalize_structured_llm,
)
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.phases.phase4_entity_maturation import ConceptionClusterer
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.entity_maturation import ConceptionClustererProtocol
from episteme_pipeline.protocols.extractors import (
    CandidatePair,
    EmbeddingModel,
    GlobalRelationExtractor,
    ensure_embedding_model,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.refinement._shared import (
    compact_theory_lens,
    refinement_component_scope,
    resolve_refinement_pass,
)
from episteme_pipeline.runs.fingerprints import fingerprint_method
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig
from episteme_pipeline.utils.identifiers import dedup_preserve_order
from episteme_pipeline.utils.similarity import cosine_similarity

logger = logging.getLogger(__name__)


class SplitSenseCandidate(BaseModel):
    """LLM-extracted conceptual sense partition for a polysemous hub entity.

    Parameters
    ----------
    perspective : str
        Concise epistemic perspective, framework, or theoretical sense label.
    description : str
        Clear definition distinguishing this conceptual sense from siblings.
    chunk_ids : list of str
        Exact chunk identifiers belonging exclusively to this conceptual sense.
    confidence : float, default 0.85
        Model confidence in this sense partition (``[0.0, 1.0]``).
    """

    perspective: str
    description: str
    chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class ConceptSplitOutput(BaseModel):
    """Structured output returned by LLM-assisted concept sense splitting.

    Parameters
    ----------
    senses : list of SplitSenseCandidate
        Two or more partitioned senses explaining the colliding usages.
    """

    senses: list[SplitSenseCandidate] = Field(default_factory=list)


@dataclass(slots=True)
class _SenseSpec:
    """Internal specification for one partitioned entity sense."""

    perspective: str
    description: str
    chunk_ids: list[str]
    atom_ids: list[str]
    envelopes: list[str]
    dispersion: float = 0.0
    confidence: float = 0.85


def _slugify_perspective(label: str) -> str:
    """Normalize a perspective label into a deterministic identifier slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", label.strip().lower()).strip("_")
    return cleaned or "sense"


class ConceptionConceptSplitter:
    """Targeted concept splitter for ``POLYSEMY_COLLISION`` deficits.

    Splits conflated L2 hub entities via System 1 ``DecisionEngine`` disambiguation
    gating followed by pre-existing ``EntityConception`` stratification, managed
    LLM sense splitting, real ``EmbeddingModel`` + ``ConceptionClusterer``
    stratification, or explicit scholarly perspective partitioning.

    Parameters
    ----------
    conception_clusterer : ConceptionClustererProtocol or None, optional
        Conception clustering strategy used to stratify mention embeddings.
    global_extractor : GlobalRelationExtractor or None, optional
        Optional Phase 3 extractor run strictly on candidate pairs touching newly
        split sense entities.
    llm : StructuredLLM or StructuredPredictable or Any or None, optional
        Optional LLM facade used for System 2 sense partitioning.
    embedding_model : EmbeddingModel or None, optional
        Optional bi-encoder used for semantic divergence assessment and clustering.
    decision_engine : DecisionEngine or None, optional
        Optional System 1 engine gating genuine polysemy vs univocal disagreement.
    config : HermeneuticRefinementConfig or None, optional
        Configuration holding prompt bundles, decoding strategy, and thresholds.
    schema : SchemaConfig, optional
        Pipeline schema configuration, defaulting to ``DEFAULT_SCHEMA``.
    prompts : StructuredPromptBundle or str or None, optional
        Optional prompt bundle override overriding ``config.concept_split_prompts``.
    strategy : StructuredDecodingStrategy or str or None, optional
        Optional structured decoding override for ``llm.predict_structured``.
    """

    def __init__(
        self,
        conception_clusterer: ConceptionClustererProtocol | None = None,
        *,
        global_extractor: GlobalRelationExtractor | None = None,
        llm: StructuredLLM | Any | None = None,
        embedding_model: EmbeddingModel | None = None,
        decision_engine: DecisionEngine | None = None,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig = DEFAULT_SCHEMA,
        prompts: StructuredPromptBundle | str | None = None,
        strategy: Any = None,
    ) -> None:
        self.conception_clusterer: ConceptionClustererProtocol = (
            conception_clusterer
            if conception_clusterer is not None
            else ConceptionClusterer()
        )
        self.global_extractor = global_extractor
        self.llm: StructuredPredictable | None = normalize_structured_llm(llm)
        self.embedding_model: EmbeddingModel | None = (
            ensure_embedding_model(embedding_model)
            if embedding_model is not None
            else None
        )
        self.decision_engine = decision_engine
        self.config = config or HermeneuticRefinementConfig()
        self.schema = schema

        if isinstance(prompts, StructuredPromptBundle):
            self.prompts: StructuredPromptBundle = prompts
        elif isinstance(prompts, str):
            self.prompts = self.config.concept_split_prompts.model_copy(
                update={"direct_template": prompts}
            )
        else:
            self.prompts = self.config.concept_split_prompts

        self.strategy = (
            strategy
            if strategy is not None
            else self.config.concept_split_decoding_strategy
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            JSON-serializable configuration snapshot across dependencies.
        """
        strategy_str = (
            self.strategy.value
            if isinstance(self.strategy, Enum)
            else str(self.strategy)
        )
        return {
            "class": self.__class__.__name__,
            "schema_version": self.schema.version,
            "strategy": strategy_str,
            "use_decision_engine_gating": self.config.use_decision_engine_gating,
            "decision_confidence_threshold": self.config.decision_confidence_threshold,
            "conformal_alpha": self.config.conformal_alpha,
            "polysemy_ambiguity_similarity_threshold": (
                self.config.polysemy_ambiguity_similarity_threshold
            ),
            "prompts": self.prompts.fingerprint(),
            "conception_clusterer": self.conception_clusterer.fingerprint(),
            "decision_engine": (
                self.decision_engine.fingerprint()
                if isinstance(self.decision_engine, Fingerprintable)
                else fingerprint_method(self.decision_engine)
            ),
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

    @staticmethod
    def _resolve_target_entities(
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        all_atoms: list[TheoryAtom],
        all_relations: list[TheoryRelation],
    ) -> list[L2Entity]:
        """Resolve strictly the entities named or linked by ``deficit``."""
        entities_by_id: dict[str, L2Entity] = {e.id: e for e in state.entities}
        atoms_by_id: dict[str, TheoryAtom] = {a.id: a for a in all_atoms}

        selected_ids: list[str] = []
        seen: set[str] = set()

        def _add_entity_id(eid: str) -> None:
            """Record ``eid`` if present in active entities and not yet seen."""
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

        return [entities_by_id[eid] for eid in selected_ids]

    @staticmethod
    def _collect_entity_chunks_and_atoms(
        entity: L2Entity,
        state: EpistemicStateView,
        all_atoms: list[TheoryAtom],
    ) -> tuple[list[str], list[TheoryAtom]]:
        """Gather deduplicated chunk IDs and atoms bound strictly to ``entity``."""
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

        return dedup_preserve_order(chunk_ids), entity_atoms

    async def _triage_polysemy_split(
        self,
        entity: L2Entity,
        deficit: EpistemicDeficit,
        candidate_chunks: list[str],
        entity_atoms: list[TheoryAtom],
        chunks_by_id: dict[str, L1Chunk],
        run_id: str,
    ) -> TriageDecision[bool]:
        """Gate concept splitting via System 1 ``DecisionEngine.evaluate_choice``."""
        if (
            self.decision_engine is None
            or not self.config.use_decision_engine_gating
            or not self.prompts.decision_template
            or not self.prompts.decision_criteria
        ):
            return TriageDecision(value=True, is_ambiguous=False)

        passages = "\n".join(
            f"- [{cid}] {chunks_by_id[cid].text[:280]}"
            for cid in candidate_chunks
            if cid in chunks_by_id
        )
        claims = "\n".join(
            f"- ({a.attributed_to or a.intensional_mode}) {a.text}"
            for a in entity_atoms
        )
        state_payload = (
            f"Entity: {entity.name} ({entity.label})\n"
            f"Description: {entity.description or 'N/A'}\n"
            f"Deficit Rationale: {deficit.rationale}\n"
            f"Passages:\n{passages or 'None'}\n"
            f"Claims:\n{claims or 'None'}"
        )
        score = await self.decision_engine.evaluate_choice(
            state=state_payload,
            question=self.prompts.decision_template,
            options=self.prompts.decision_criteria,
            alpha=self.config.conformal_alpha,
        )
        pred_set = list(
            score.prediction_set
            or ([] if score.selected_option is None else [score.selected_option])
        )
        probs = score.probabilities or {}
        top_prob = float(
            probs.get(score.selected_option or "", score.class_probability)
        )
        is_singleton = len(pred_set) == 1
        is_ambiguous = (
            not is_singleton
        ) or top_prob < self.config.decision_confidence_threshold

        if score.selected_option == "TRUE_POLYSEMY_SPLIT" or is_ambiguous:
            return TriageDecision(
                value=True,
                decision=score,
                empirical_accuracy=float(score.empirical_accuracy or 1.0),
                prediction_set=pred_set,
                is_ambiguous=is_ambiguous,
            )

        is_audit = should_audit_deterministically(
            run_id,
            "refinement_concept_split",
            f"{deficit.deficit_id}:{entity.id}",
            self.config.stochastic_audit_rate,
        )
        return TriageDecision(
            value=is_audit,
            decision=score,
            empirical_accuracy=float(score.empirical_accuracy or 1.0),
            prediction_set=pred_set,
            is_ambiguous=False,
            is_audit=is_audit,
        )

    def _partition_from_conceptions(
        self,
        entity: L2Entity,
        entity_atoms: list[TheoryAtom],
        chunks_by_id: dict[str, L1Chunk],
    ) -> list[_SenseSpec]:
        """Convert pre-existing ``entity.conceptions`` into distinct sense specs."""
        if len(entity.conceptions) < 2:
            return []
        specs: list[_SenseSpec] = []
        used_chunks: set[str] = set()
        for conc in entity.conceptions:
            cids = [cid for cid in conc.source_chunk_ids if cid not in used_chunks]
            if not cids:
                cids = list(conc.source_chunk_ids)
            if not cids:
                continue
            used_chunks.update(cids)
            cid_set = set(cids)
            atom_ids = [a.id for a in entity_atoms if a.source_chunk_id in cid_set]
            envelopes = list(conc.representative_envelopes)
            if not envelopes:
                envelopes = [
                    chunks_by_id[cid].text for cid in cids if cid in chunks_by_id
                ]
            specs.append(
                _SenseSpec(
                    perspective=conc.perspective,
                    description=conc.description
                    or f"{entity.name} ({conc.perspective})",
                    chunk_ids=dedup_preserve_order(cids),
                    atom_ids=atom_ids,
                    envelopes=envelopes,
                    dispersion=float(conc.centroid_dispersion or 0.0),
                    confidence=float(
                        conc.confidence if conc.confidence is not None else 0.9
                    ),
                )
            )
        return specs if len(specs) >= 2 else []

    def _clusters_to_specs(
        self,
        entity: L2Entity,
        clusters: list[Any],
        entity_atoms: list[TheoryAtom],
    ) -> list[_SenseSpec]:
        """Convert :class:`ConceptionCluster` outputs into ``_SenseSpec`` objects."""
        specs: list[_SenseSpec] = []
        for idx, cluster in enumerate(clusters, start=1):
            cids = dedup_preserve_order(cid for cid in cluster.chunk_ids if cid)
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

    @staticmethod
    def _build_mention_envelopes(
        entity: L2Entity,
        candidate_chunks: list[str],
        state: EpistemicStateView,
        entity_atoms: list[TheoryAtom],
        chunks_by_id: dict[str, L1Chunk],
    ) -> tuple[list[str], list[str], list[str]]:
        """Assemble mention envelope strings, chunk IDs, and perspective tags."""
        mentions_by_chunk: dict[str, list[str]] = {}
        for rec in state.entity_mentions_by_id.get(entity.id, []):
            cid = rec.get("chunk_id", "")
            env = rec.get("textual_envelope", "")
            if cid and env:
                mentions_by_chunk.setdefault(cid, []).append(env)

        persp_by_chunk: dict[str, str] = {}
        for atom in entity_atoms:
            if atom.source_chunk_id not in persp_by_chunk:
                if atom.attributed_to:
                    persp_by_chunk[atom.source_chunk_id] = atom.attributed_to
                elif atom.intensional_mode and atom.intensional_mode != "asserted":
                    persp_by_chunk[atom.source_chunk_id] = atom.intensional_mode

        envelopes: list[str] = []
        env_chunk_ids: list[str] = []
        env_perspectives: list[str] = []
        for cid in candidate_chunks:
            env_list = mentions_by_chunk.get(cid)
            if env_list:
                text_val = env_list[0]
            elif cid in chunks_by_id:
                text_val = chunks_by_id[cid].text
            else:
                atom_texts = [a.text for a in entity_atoms if a.source_chunk_id == cid]
                text_val = " ".join(atom_texts).strip()
            if text_val:
                envelopes.append(text_val)
                env_chunk_ids.append(cid)
                env_perspectives.append(persp_by_chunk.get(cid, ""))
        return envelopes, env_chunk_ids, env_perspectives

    @staticmethod
    def _partition_by_perspectives(
        entity: L2Entity,
        candidate_chunks: list[str],
        entity_atoms: list[TheoryAtom],
        state: EpistemicStateView,
        chunks_by_id: dict[str, L1Chunk],
    ) -> list[_SenseSpec]:
        """Partition strictly when explicit attribution or theory frameworks diverge."""
        if len(candidate_chunks) < 2:
            return []

        groups: dict[str, list[str]] = {}
        enr_theories_by_chunk: dict[str, str] = {
            enr.cluster_id.removeprefix("cluster-"): enr.theory_id
            for enr in state.theoretical_enrichments
            if enr.theory_id
        }

        for cid in candidate_chunks:
            persp: str | None = None
            for atom in entity_atoms:
                if atom.source_chunk_id == cid and atom.attributed_to:
                    persp = atom.attributed_to.strip()
                    break
            if persp is None:
                persp = enr_theories_by_chunk.get(cid)
            if persp is not None:
                groups.setdefault(persp, []).append(cid)

        if len(groups) < 2:
            return []

        specs: list[_SenseSpec] = []
        for persp, cids in groups.items():
            dedup_cids = dedup_preserve_order(cids)
            cid_set = set(dedup_cids)
            atom_ids = [a.id for a in entity_atoms if a.source_chunk_id in cid_set]
            envs = [chunks_by_id[cid].text for cid in dedup_cids if cid in chunks_by_id]
            specs.append(
                _SenseSpec(
                    perspective=persp,
                    description=f"{entity.name} under {persp} perspective",
                    chunk_ids=dedup_cids,
                    atom_ids=atom_ids,
                    envelopes=envs,
                    confidence=0.80,
                )
            )
        return specs if len(specs) >= 2 else []

    async def _partition_entity_senses(
        self,
        entity: L2Entity,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        all_atoms: list[TheoryAtom],
        chunks_by_id: dict[str, L1Chunk],
        run_id: str,
    ) -> list[_SenseSpec]:
        """Partition one target entity's usages into ``>= 2`` disjoint senses."""
        candidate_chunks, entity_atoms = self._collect_entity_chunks_and_atoms(
            entity, state, all_atoms
        )
        triage = await self._triage_polysemy_split(
            entity, deficit, candidate_chunks, entity_atoms, chunks_by_id, run_id
        )
        if not triage.value:
            logger.info(
                "ConceptionConceptSplitter skipped split for entity '%s' (%s) after System 1 triage: %s",
                entity.name,
                entity.id,
                triage.prediction_set,
            )
            return []

        # Path 1: Pre-existing stratified conceptions from Phase 4 maturation.
        specs = self._partition_from_conceptions(entity, entity_atoms, chunks_by_id)
        if specs:
            return specs

        # Path 2: Managed structured LLM sense splitting (System 2).
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
                theory_lens=compact_theory_lens(deficit.theory_lens),
                rationale=deficit.rationale or "Polysemy collision detected.",
                entity_atoms=atoms_text,
                source_chunks=chunks_text or "No chunk text available.",
                allowed_chunk_ids=", ".join(candidate_chunks),
            )
            llm_specs: list[_SenseSpec] = []
            assigned: set[str] = set()
            for cand in raw_split.senses:
                valid_cids = [
                    cid
                    for cid in cand.chunk_ids
                    if cid in chunk_set and cid not in assigned
                ]
                if not valid_cids:
                    continue
                assigned.update(valid_cids)
                cid_set = set(valid_cids)
                llm_specs.append(
                    _SenseSpec(
                        perspective=cand.perspective.strip()
                        or f"sense_{len(llm_specs) + 1}",
                        description=cand.description.strip()
                        or f"{entity.name} ({cand.perspective})",
                        chunk_ids=dedup_preserve_order(valid_cids),
                        atom_ids=[
                            a.id for a in entity_atoms if a.source_chunk_id in cid_set
                        ],
                        envelopes=[
                            chunks_by_id[cid].text
                            for cid in valid_cids
                            if cid in chunks_by_id
                        ],
                        confidence=float(cand.confidence),
                    )
                )
            if len(llm_specs) >= 2:
                return llm_specs

        # Path 3: Real EmbeddingModel semantic divergence + ConceptionClusterer.
        envelopes, env_chunk_ids, env_perspectives = self._build_mention_envelopes(
            entity, candidate_chunks, state, entity_atoms, chunks_by_id
        )
        if self.embedding_model is not None and len(envelopes) >= 2:
            raw_vecs = await self.embedding_model.aget_text_embedding_batch(envelopes)
            emb_arr = np.asarray(raw_vecs, dtype=np.float32)
            _, clusters = self.conception_clusterer.stratify(
                envelopes,
                emb_arr,
                envelope_chunk_ids=env_chunk_ids,
                envelope_perspectives=env_perspectives,
            )
            cluster_specs = self._clusters_to_specs(entity, clusters, entity_atoms)
            if cluster_specs:
                chunk_to_vec = {
                    cid: raw_vecs[idx]
                    for idx, cid in enumerate(env_chunk_ids)
                    if idx < len(raw_vecs)
                }
                centroids: list[np.ndarray] = []
                for sp in cluster_specs:
                    vecs = [
                        np.asarray(chunk_to_vec[c], dtype=np.float32)
                        for c in sp.chunk_ids
                        if c in chunk_to_vec
                    ]
                    if vecs:
                        centroids.append(np.mean(vecs, axis=0))
                min_sim = 1.0
                for i in range(len(centroids)):
                    for j in range(i + 1, len(centroids)):
                        min_sim = min(
                            min_sim, cosine_similarity(centroids[i], centroids[j])
                        )
                if min_sim < self.config.polysemy_ambiguity_similarity_threshold:
                    return cluster_specs

        # Path 4: Explicit perspectival attribution (attributed_to / enrichment theory_id).
        return self._partition_by_perspectives(
            entity, candidate_chunks, entity_atoms, state, chunks_by_id
        )

    async def _reextract_global_relations(
        self,
        *,
        split_senses: list[L2Entity],
        split_orig_ids: set[str],
        state: EpistemicStateView,
        entities_by_id: dict[str, L2Entity],
        rewritten_local_triples: list[L2Triple],
        rewritten_global_triples: list[L2Triple],
    ) -> None:
        """Re-run Phase 3 global relation extraction strictly on split-sense pairs."""
        if self.global_extractor is None or not split_senses:
            return

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

        sense_chunk_set = {cid for s in split_senses for cid in s.source_chunk_ids}
        for ent in state.entities:
            if ent.id not in split_orig_ids and any(
                cid in sense_chunk_set for cid in ent.source_chunk_ids
            ):
                neighbor_ids.add(ent.id)

        scoped_neighbors = [
            entities_by_id[nid] for nid in sorted(neighbor_ids) if nid in entities_by_id
        ]
        scoped_entities = [*split_senses, *scoped_neighbors]
        sense_id_set = {s.id for s in split_senses}

        candidate_pairs: list[CandidatePair]
        if isinstance(self.global_extractor, GlobalRelationExtractor):
            raw_pairs = await self.global_extractor.candidate_pairs(scoped_entities)
            candidate_pairs = [
                p
                for p in raw_pairs
                if p.entity_a.id in sense_id_set or p.entity_b.id in sense_id_set
            ]
            if (
                isinstance(self.global_extractor, DenseRetrievalGlobalRelationExtractor)
                and candidate_pairs
            ):
                candidate_pairs = await self.global_extractor.filter_candidate_pairs(
                    candidate_pairs
                )
        else:
            candidate_pairs = []
            for i, s1 in enumerate(split_senses):
                for s2 in split_senses[i + 1 :]:
                    candidate_pairs.append(CandidatePair(entity_a=s1, entity_b=s2))
                for nbr in scoped_neighbors:
                    candidate_pairs.append(CandidatePair(entity_a=s1, entity_b=nbr))

        if not candidate_pairs:
            return

        reader = state.to_graph_reader()
        for sense_ent in split_senses:
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
            atoms, or relations.
        state : EpistemicStateView
            Cumulative epistemic state view providing entities, conceptions,
            triples, and L3 theory atoms.
        context : ArtifactExecutionContext or None, optional
            Optional active execution context for event and pass lineage.

        Returns
        -------
        RefinementDelta
            Delta containing split sense ``L2Entity`` instances,
            ``retired_entity_ids``, ``split_entity_parents``,
            ``cannot_link_pairs``, and localized rewritten triples and atoms.
        """
        if deficit.deficit_kind != EpistemicDeficitKind.POLYSEMY_COLLISION:
            raise ValueError(
                f"ConceptionConceptSplitter only handles POLYSEMY_COLLISION deficits "
                f"(got {deficit.deficit_kind.value})"
            )

        next_pass = resolve_refinement_pass(context, deficit)
        run_id = context.run_id if context is not None else "unknown"
        comp_name = type(self).__name__
        emitter = get_event_emitter()

        all_atoms = list(state.canonical_theory_atoms or state.theory_atoms)
        all_relations = list(state.canonical_theory_relations or state.theory_relations)
        entities_by_id = {e.id: e for e in state.entities}
        chunks_by_id = {c.id: c for c in state.chunks}

        with refinement_component_scope(
            comp_name,
            context,
            input_description=f"deficit={deficit.deficit_id}",
        ) as outcome:
            target_entities = self._resolve_target_entities(
                deficit, state, all_atoms, all_relations
            )
            if not target_entities:
                outcome.output_description = "no_target_entities"
                return RefinementDelta(refinement_pass=next_pass)

            new_entities: list[L2Entity] = []
            split_senses_only: list[L2Entity] = []
            retired_entity_ids: list[str] = []
            split_entity_parents: dict[str, str] = {}
            cannot_link_pairs: list[tuple[str, str]] = []
            seen_cannot_link: set[tuple[str, str]] = set()
            chunk_to_sense_map: dict[tuple[str, str], str] = {}
            atom_to_sense_map: dict[tuple[str, str], str] = {}
            split_orig_ids: set[str] = set()

            for entity in target_entities:
                specs = await self._partition_entity_senses(
                    entity, deficit, state, all_atoms, chunks_by_id, run_id
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
                    split_entity_parents[sense_id] = entity.id

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

                unassigned_chunks = [
                    cid for cid in entity.source_chunk_ids if cid not in assigned_chunks
                ]
                if unassigned_chunks:
                    new_entities.append(
                        entity.model_copy(
                            update={"source_chunk_ids": unassigned_chunks}
                        )
                    )
                else:
                    retired_entity_ids.append(entity.id)

                for i, s1 in enumerate(senses_for_entity):
                    orig_pair = (min(entity.id, s1.id), max(entity.id, s1.id))
                    if orig_pair not in seen_cannot_link:
                        seen_cannot_link.add(orig_pair)
                        cannot_link_pairs.append((entity.id, s1.id))
                    for s2 in senses_for_entity[i + 1 :]:
                        sense_pair = (min(s1.id, s2.id), max(s1.id, s2.id))
                        if sense_pair not in seen_cannot_link:
                            seen_cannot_link.add(sense_pair)
                            cannot_link_pairs.append((s1.id, s2.id))

            if not split_orig_ids:
                outcome.output_description = "no_splittable_senses"
                return RefinementDelta(refinement_pass=next_pass)

            def _rewire_triples(triples: list[L2Triple]) -> list[L2Triple]:
                """Rewire affected triples in scope chunks to split sense IDs."""
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

            await self._reextract_global_relations(
                split_senses=split_senses_only,
                split_orig_ids=split_orig_ids,
                state=state,
                entities_by_id=entities_by_id,
                rewritten_local_triples=rewritten_local_triples,
                rewritten_global_triples=rewritten_global_triples,
            )

            outcome.output_description = (
                f"split_entities={len(split_senses_only)}, "
                f"retired_entities={len(retired_entity_ids)}, "
                f"cannot_link={len(cannot_link_pairs)}, "
                f"rewritten_atoms={len(rewritten_atoms)}"
            )
            return RefinementDelta(
                entities=new_entities,
                local_triples=rewritten_local_triples,
                global_triples=rewritten_global_triples,
                theory_atoms=rewritten_atoms,
                cannot_link_pairs=cannot_link_pairs,
                retired_entity_ids=retired_entity_ids,
                split_entity_parents=split_entity_parents,
                resolved_deficit_ids=[deficit.deficit_id],
                refinement_pass=next_pass,
            )


__all__ = [
    "ConceptSplitOutput",
    "ConceptionConceptSplitter",
    "SplitSenseCandidate",
]
