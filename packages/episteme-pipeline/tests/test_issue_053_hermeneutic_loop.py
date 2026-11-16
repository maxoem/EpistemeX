"""Deterministic end-to-end tests for ISSUE-053 Step 3b hermeneutic loop.

Covers:
1. ``ArtifactSubgraphReader.vector_search`` fix constructing valid
   ``SearchResult`` models (``node_label="Chunk"``, ``node_name=chunk.id``) and
   integrating cleanly with ``TheoryGuidedAxiomGrounder``.
2. ``ClosedLoopRefinementCoordinator`` protocol conformance, constructor guard
   validation, ``Fingerprintable`` / ``find_components()`` discovery, domain
   event emission, and curation ledger ``cannot_link_entities`` persistence.
3. ``max_refinement_cycles=0`` pure feed-forward parity (zero fingerprint
   drift, zero refinement records/events, and Phase 1..N reuse when toggling
   ``max_refinement_cycles`` from 0 to 1).
4. Full multi-deficit closed-loop execution resolving ``ENTHYMEME_GAP``,
   ``POLYSEMY_COLLISION``, and ``UNGROUNDED_AXIOM``, with D-QBAF TheoryNet
   reconvergence and strict subgraph localization (unaffected Doc B artifacts
   retain exact Pass-0 ``artifact_id`` and ``refinement_pass=0``).
5. Lineage & artifact overlay semantics across ``RunManifest``,
   ``RunPhaseRecord``, ``ArtifactProvenance``, ``ArtifactCollection``
   (``history`` vs ``latest_by_identity``), ``JsonArtifactStore``,
   ``ArtifactGraphProjector``, and ``RunReport``.
6. Bounded termination semantics: early convergence on zero remaining deficits,
   cycle cap enforcement, ``max_deficits_per_cycle`` prioritization, handler
   enable flag filtering, cross-cycle identical-signature suppression,
   localized ``TheoreticalEnrichmentRunner`` re-scoring, and failure handling.
7. Composition root wiring via ``Pipeline.for_task`` / ``PipelineFactory``
   and standalone ``Pipeline`` construction.
8. Static AST verification confirming zero ``getattr`` / ``hasattr`` calls
   and NumPy-style docstrings across all Step 3b files.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_document_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicStateView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.invalidate import ArtifactDependencyGraph
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    EpistemicDeficitArtifact,
    TheoreticalEnrichmentArtifact,
)
from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.config import (
    ExecutionConfig,
    HermeneuticRefinementConfig,
    PipelineConfig,
    TheoreticalEnrichmentConfig,
)
from episteme_pipeline.contracts.domain import (
    EntityConception,
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    Measurement,
    RefinementDelta,
    SearchResult,
    TenabilityResult,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import (
    EpistemicCurationLedger,
    PipelineInput,
)
from episteme_pipeline.events import (
    EpistemicDeficitDetected,
    MetricsObserver,
    RefinementCycleCompleted,
    RefinementCycleStarted,
    RunFailed,
    SimpleEventEmitter,
    use_event_emitter,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.post_processing.theoretical_enrichment.projectors import (
    GenericTheoryProjector,
)
from episteme_pipeline.post_processing.theoretical_enrichment.runner import (
    TheoreticalEnrichmentRunner,
)
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.protocols.extractors import NERExtractor
from episteme_pipeline.protocols.fingerprint import Fingerprintable, find_components
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.prompts import PromptContextual
from episteme_pipeline.protocols.refinement import (
    HermeneuticRefinementCoordinator,
    TargetedRefinementPort,
)
from episteme_pipeline.refinement import (
    ClosedLoopRefinementCoordinator,
    ConceptionConceptSplitter,
    LLMTheoryGuidedPremiseRecoverer,
    TheoryGuidedAxiomGrounder,
    TheoryNetDeficitDetector,
)
from episteme_pipeline.refinement.axiom_grounder import (
    AxiomGroundingOutput,
    RecoveredGroundingEntity,
    RecoveredMeasurement,
    RecoveredObservationAtom,
)
from episteme_pipeline.refinement.premise_recovery import (
    PremiseRecoveryOutput,
    RecoveredImplicitPremise,
)
from episteme_pipeline.runs.models import RunManifest, RunStatus
from episteme_pipeline.runtime.pipeline_factory import PipelineFactory
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

PACKAGE_ROOT = (
    Path(__file__).resolve().parent.parent / "episteme_pipeline"
)


class _ListObserver:
    """Minimal EventObserver appending every emitted event into a list."""

    def __init__(self, target: list[Any]) -> None:
        self._target = target

    def on_event(self, event: Any) -> None:
        self._target.append(event)


class _StubStructuredLLM:
    """Deterministic StructuredLLM stub inspecting prompt kwargs for routing."""

    def __init__(self, resolver: Any | None = None) -> None:
        self._resolver = resolver
        self.calls: list[dict[str, Any]] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubStructuredLLM"}

    async def predict_structured(
        self,
        output_cls: type[Any],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> Any:
        self.calls.append(
            {
                "output_cls": output_cls.__name__,
                "prompt_args": dict(prompt_args),
            }
        )
        if self._resolver is not None:
            return self._resolver(output_cls, prompt_args)
        return output_cls()

    async def predict_text(self, *args: Any, **kwargs: Any) -> str:
        return ""


class _StubEmbeddingModel:
    """Minimal async EmbeddingModel stub producing deterministic unit vectors."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubEmbeddingModel"}

    async def aget_text_embedding(self, text: str) -> list[float]:
        self.calls.append(text)
        lowered = text.lower()
        if (
            "trial" in lowered
            or "empirical" in lowered
            or "laboratory" in lowered
            or "deliberation" in lowered
            or "dopamine" in lowered
        ):
            return [1.0, 0.0, 0.0]
        if "conservation" in lowered or "unrelated" in lowered:
            return [0.0, 0.0, 1.0]
        return [0.7, 0.7, 0.0]

    async def aget_text_embedding_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        return [await self.aget_text_embedding(t) for t in texts]


class _StubReranker:
    """Minimal RelationReranker stub for PipelineFactory wiring tests."""

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubReranker"}

    async def rerank(
        self, query: str, candidates: list[Any], **kwargs: Any
    ) -> list[Any]:
        return candidates


class _StubNERExtractor(NERExtractor):
    """Deterministic NERExtractor subclass recording visited chunks cleanly."""

    def __init__(self, entities_by_chunk: dict[str, list[L2Entity]]) -> None:
        self._entities_by_chunk = entities_by_chunk
        self.called_chunk_ids: list[str] = []
        self.seen_anchors: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_StubNERExtractor"}

    async def extract(
        self,
        chunk_id: str,
        chunk_text: str,
        schema: SchemaConfig,
        memory: Any | None = None,
        anchor: Any | None = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]:
        del chunk_text, schema, memory
        self.called_chunk_ids.append(chunk_id)
        if isinstance(anchor, PromptContextual):
            self.seen_anchors.append(anchor.to_prompt_context())
        return list(self._entities_by_chunk.get(chunk_id, [])), [], None, False, None


class _RecordingProjectionGraph(ProjectionGraph):
    """In-memory ProjectionGraph recording all projected batch writes."""

    def __init__(self) -> None:
        self.atom_batches: list[list[str]] = []
        self.entity_batches: list[list[str]] = []
        self.chunk_batches: list[list[str]] = []
        self.triple_batches: list[list[str]] = []
        self.theory_rel_batches: list[list[str]] = []
        self.upserted_nodes: list[tuple[str, str]] = []
        self.upserted_edges: list[tuple[str, str, str]] = []

    async def verify_connectivity(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def setup_schema(self) -> None:
        return None

    async def upsert_node(
        self,
        label: str,
        node_id: str,
        properties: dict,
        *,
        extra_labels: tuple[str, ...] = (),
        create_only_properties: dict | None = None,
    ) -> None:
        self.upserted_nodes.append((label, node_id))

    async def prune_document_children(
        self,
        document_id: str,
        *,
        keep_chunk_ids: list[str],
        keep_chapter_ids: list[str],
    ) -> dict[str, int]:
        return {"chunks": 0, "chapters": 0}

    async def upsert_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
        properties: dict | None = None,
    ) -> None:
        self.upserted_edges.append((from_id, relation_type, to_id))

    async def upsert_relations(self, relations: list[dict]) -> None:
        for rel in relations:
            self.upserted_edges.append(
                (
                    str(rel.get("from_id", "")),
                    str(rel.get("relation_type", "")),
                    str(rel.get("to_id", "")),
                )
            )

    async def upsert_chunk(self, chunk: L1Chunk) -> None:
        self.chunk_batches.append([chunk.id])

    async def upsert_chunks(self, chunks: list[L1Chunk]) -> None:
        self.chunk_batches.append([c.id for c in chunks])

    async def upsert_entity(self, entity: L2Entity) -> None:
        self.entity_batches.append([entity.id])

    async def upsert_entities(self, entities: list[L2Entity]) -> None:
        self.entity_batches.append([e.id for e in entities])

    async def upsert_triple(self, triple: L2Triple) -> None:
        self.triple_batches.append([f"{triple.subject_id}->{triple.object_id}"])

    async def upsert_triples(self, triples: list[L2Triple]) -> None:
        self.triple_batches.append([f"{t.subject_id}->{t.object_id}" for t in triples])

    async def upsert_argument_component(self, component: TheoryAtom) -> None:
        self.atom_batches.append([component.id])

    async def upsert_argument_components(
        self, components: list[TheoryAtom]
    ) -> None:
        self.atom_batches.append([c.id for c in components])

    async def upsert_theory_relation(self, relation: TheoryRelation) -> None:
        self.theory_rel_batches.append([relation.relation_id])

    async def upsert_theory_relations(
        self, relations: list[TheoryRelation]
    ) -> None:
        self.theory_rel_batches.append([r.relation_id for r in relations])

    async def upsert_community(
        self, community_id: str, level: int, entity_ids: list[str]
    ) -> None:
        return None

    async def upsert_communities(self, communities: list[dict]) -> None:
        return None


class _StaticPhaseRunner(PhaseRunner[EpistemicStateView]):
    """Deterministic stub PhaseRunner emitting fixed envelopes and tracking runs."""

    def __init__(
        self,
        *,
        name: str,
        phase_key: str,
        input_view: type[EpistemicStateView] | None,
        reads_kinds: frozenset[ArtifactKind],
        writes_kinds: frozenset[ArtifactKind],
        dependencies: tuple[str, ...],
        builder: Any,
    ) -> None:
        self.name = name
        self.phase_key = phase_key
        self.input_view = input_view
        self.reads_kinds = reads_kinds
        self.writes_kinds = writes_kinds
        self.dependencies = dependencies
        self._builder = builder
        self.run_count = 0

    def config_fingerprint(self) -> str:
        return f"cfg-{self.phase_key}"

    async def run(
        self, input: Any, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        self.run_count += 1
        envelopes = self._builder(input, context)
        return ArtifactCollection(envelopes)


def _make_config(
    tmp_path: Path,
    *,
    max_cycles: int = 0,
    max_deficits_per_cycle: int = 10,
    allow_phase_reuse: bool = True,
    project_to_graph: bool = True,
    enable_premise: bool = True,
    enable_split: bool = True,
    enable_grounding: bool = True,
) -> PipelineConfig:
    """Construct an isolated temporary-directory ``PipelineConfig``."""
    return PipelineConfig(
        execution=ExecutionConfig(
            runs_dir=str(tmp_path / "runs"),
            artifacts_dir=str(tmp_path / "artifacts"),
            allow_phase_reuse=allow_phase_reuse,
            allow_artifact_hydration=True,
            project_artifacts_to_graph=project_to_graph,
            persist_run_manifests=True,
            persist_refinement_artifacts=True,
        ),
        refinement=HermeneuticRefinementConfig(
            max_refinement_cycles=max_cycles,
            max_deficits_per_cycle=max_deficits_per_cycle,
            enable_theory_guided_premise_recovery=enable_premise,
            enable_targeted_concept_split=enable_split,
            enable_localized_axiom_grounding=enable_grounding,
        ),
    )


def _build_two_subgraph_forward_phases() -> list[PhaseRunner[Any]]:
    """Build deterministic forward PhaseRunner stubs with Doc A deficits and clean Doc B."""

    def build_l1(_input: Any, ctx: ArtifactExecutionContext) -> list[ArtifactEnvelope[Any]]:
        doc_a = L1Document(
            id="doc_a",
            title="Agency and Deliberation",
            source_path="/corpus/doc_a.md",
            chapter_count=1,
            chunk_count=4,
        )
        doc_b = L1Document(
            id="doc_b",
            title="Conservation Laws",
            source_path="/corpus/doc_b.md",
            chapter_count=1,
            chunk_count=1,
        )
        chunk_a1 = L1Chunk(
            id="chunk_a1",
            source_doc_id="doc_a",
            sequence_index=0,
            token_count=10,
            text="Physical action initiates ballistic motion immediately.",
            embedding=[0.2, 0.8, 0.0],
        )
        chunk_a2 = L1Chunk(
            id="chunk_a2",
            source_doc_id="doc_a",
            sequence_index=1,
            token_count=14,
            text=(
                "Moral responsibility presupposes autonomous agentive choice "
                "beyond mere physical impulse."
            ),
            embedding=[0.6, 0.6, 0.0],
        )
        chunk_a_ax = L1Chunk(
            id="chunk_a_ax",
            source_doc_id="doc_a",
            sequence_index=2,
            token_count=10,
            text="Empirical deliberation studies validate agentive control.",
            embedding=[0.9, 0.1, 0.0],
        )
        chunk_a3 = L1Chunk(
            id="chunk_a3",
            source_doc_id="doc_a",
            sequence_index=9,
            token_count=12,
            text=(
                "Empirical trial observations (N=42, p=0.01) corroborate "
                "agentive deliberation."
            ),
            embedding=[1.0, 0.0, 0.0],
        )
        chunk_b1 = L1Chunk(
            id="chunk_b1",
            source_doc_id="doc_b",
            sequence_index=0,
            token_count=8,
            text="Energy conservation strictly constrains closed trajectories.",
            embedding=[0.0, 0.0, 1.0],
        )
        return [
            build_document_artifact(
                doc_a,
                run_id=ctx.run_id,
                phase_name="Phase 1: Ingestion",
                method="stub_doc",
            ),
            build_document_artifact(
                doc_b,
                run_id=ctx.run_id,
                phase_name="Phase 1: Ingestion",
                method="stub_doc",
            ),
            *[
                build_chunk_artifact(
                    chunk,
                    run_id=ctx.run_id,
                    phase_name="Phase 1: Ingestion",
                    method="stub_chunk",
                )
                for chunk in (chunk_a1, chunk_a2, chunk_a_ax, chunk_a3, chunk_b1)
            ],
        ]

    def build_l2(_input: Any, ctx: ArtifactExecutionContext) -> list[ArtifactEnvelope[Any]]:
        ent_action = L2Entity(
            id="ent_action",
            label="Concept",
            name="Action",
            description="Ambiguous causal vs deontic concept.",
            source_chunk_ids=["chunk_a1", "chunk_a2"],
            polysemy_variance=0.45,
            conceptions=[
                EntityConception(
                    id="ent_action::chunk_a1",
                    entity_id="ent_action",
                    perspective="Physicist",
                    description="Bodily causal movement trigger",
                    source_chunk_ids=["chunk_a1"],
                    confidence=0.9,
                ),
                EntityConception(
                    id="ent_action::chunk_a2",
                    entity_id="ent_action",
                    perspective="Ethicist",
                    description="Normative moral agency commitment",
                    source_chunk_ids=["chunk_a2"],
                    confidence=0.9,
                ),
            ],
        )
        ent_conservation = L2Entity(
            id="ent_conservation",
            label="Concept",
            name="Conservation",
            description="Physical conservation invariant.",
            source_chunk_ids=["chunk_b1"],
        )
        triple_causal = L2Triple(
            subject_id="ent_action",
            predicate="INITIATES",
            object_id="ent_action",
            confidence=0.9,
            scope="local",
            source_chunk_id="chunk_a1",
        )
        triple_normative = L2Triple(
            subject_id="ent_action",
            predicate="OBLIGATES",
            object_id="ent_action",
            confidence=0.9,
            scope="local",
            source_chunk_id="chunk_a2",
        )
        return [
            build_linked_entity_artifact(
                ent_action,
                [],
                run_id=ctx.run_id,
                phase_name="Phase 2: Entities",
                method="stub_ner",
            ),
            build_linked_entity_artifact(
                ent_conservation,
                [],
                run_id=ctx.run_id,
                phase_name="Phase 2: Entities",
                method="stub_ner",
            ),
            build_local_relation_artifact(
                triple_causal,
                run_id=ctx.run_id,
                phase_name="Phase 2: Entities",
                method="stub_rel",
            ),
            build_local_relation_artifact(
                triple_normative,
                run_id=ctx.run_id,
                phase_name="Phase 2: Entities",
                method="stub_rel",
            ),
        ]

    def build_l4(_input: Any, ctx: ArtifactExecutionContext) -> list[ArtifactEnvelope[Any]]:
        # 1) ENTHYMEME_GAP: ac_claim_a has outgoing ENTAILS -> ac_downstream_a, 0 incoming SUPPORTS
        ac_claim_a = TheoryAtom(
            id="ac_claim_a",
            text="Autonomous moral responsibility is irreducible to reflex.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_a2",
            entity_ids=["ent_action"],
            confidence=0.85,
            modal_prior=0.80,
            local_tenability=0.90,
            equilibrium_strength=0.60,
        )
        obs_down_a = TheoryAtom(
            id="obs_down_a",
            text="Behavioral agency indicators vary across deliberation conditions.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_a2",
            measurements=[Measurement(dimension="choice_latency", value=0.45, unit="s")],
            local_tenability=0.90,
        )
        ac_downstream_a = TheoryAtom(
            id="ac_downstream_a",
            text="Therefore moral blame presupposes deliberative autonomy.",
            component_type="CoreExpansion",
            source_chunk_id="chunk_a2",
            confidence=0.85,
            modal_prior=0.75,
            local_tenability=0.90,
            equilibrium_strength=0.68,
        )

        # 2) POLYSEMY_COLLISION around ent_action with conflicting causal vs deontic conceptions
        obs_a1 = TheoryAtom(
            id="obs_a1",
            text="Kinematic latency stays constant for reflex arcs.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_a1",
            measurements=[Measurement(dimension="reflex_latency", value=0.12, unit="s")],
            local_tenability=0.90,
        )
        obs_a2 = TheoryAtom(
            id="obs_a2",
            text="Normative culpability tracks reflective endorsement.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_a2",
            measurements=[Measurement(dimension="norm_score", value=0.88)],
            local_tenability=0.90,
        )
        ac_causal_prem = TheoryAtom(
            id="ac_causal_prem",
            text="Action as impulse reduces cleanly to kinematics.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_a1",
            entity_ids=["ent_action"],
            confidence=0.85,
            modal_prior=0.80,
            local_tenability=0.90,
            controversy_volatility=0.44,
            equilibrium_strength=0.80,
        )
        ac_deontic_prem = TheoryAtom(
            id="ac_deontic_prem",
            text="Action as agency resists reduction to kinematics.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_a2",
            entity_ids=["ent_action"],
            confidence=0.85,
            modal_prior=0.80,
            local_tenability=0.90,
            controversy_volatility=0.10,
            equilibrium_strength=0.80,
        )

        # 3) UNGROUNDED_AXIOM: ac_axiom_a in chunk_a_ax has TS_local < 0.5 & untenable status
        obs_a_weak = TheoryAtom(
            id="obs_a_weak",
            text="Preliminary note on deliberation.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_a_ax",
            local_tenability=0.25,
        )
        ac_axiom_a = TheoryAtom(
            id="ac_axiom_a",
            text="Empirical deliberation studies validate agentive control.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_a_ax",
            entity_ids=[],
            measurements=[],
            parameters={"required_dimensions": ["sample_size", "p_value"]},
            confidence=0.80,
            modal_prior=0.75,
            local_tenability=0.25,
            equilibrium_strength=0.25,
            tenability=TenabilityResult(
                local_score=0.25,
                edge_scores={},
                aggregated_score=0.25,
                is_tenable=False,
                tightest_blur=0.75,
                anomalies=["Missing sample_size and p_value observations"],
            ),
        )

        # 4) Clean Doc B subgraph (must remain 100% untouched at refinement_pass=0!)
        obs_b = TheoryAtom(
            id="obs_b",
            text="Closed-system Lagrangians are time-translation invariant.",
            component_type="ObservationUnit",
            source_chunk_id="chunk_b1",
            entity_ids=["ent_conservation"],
            measurements=[
                Measurement(dimension="energy_drift", value=0.0, unit="J")
            ],
            confidence=0.95,
            modal_prior=0.95,
            local_tenability=0.95,
            equilibrium_strength=0.95,
        )
        ac_claim_b = TheoryAtom(
            id="ac_claim_b",
            text="Total mechanical energy is conserved.",
            component_type="TheoreticalHypothesis",
            source_chunk_id="chunk_b1",
            entity_ids=["ent_conservation"],
            confidence=0.95,
            modal_prior=0.90,
            local_tenability=0.95,
            equilibrium_strength=0.95,
            controversy_volatility=0.02,
        )

        rels = [
            TheoryRelation(
                source_id="ac_claim_a",
                target_id="ac_downstream_a",
                relation_type="ENTAILS",
                confidence=0.85,
                scope="global",
                edge_tenability=0.90,
            ),
            TheoryRelation(
                source_id="obs_down_a",
                target_id="ac_downstream_a",
                relation_type="SUPPORTS",
                confidence=0.90,
                scope="local",
                edge_tenability=0.90,
            ),
            TheoryRelation(
                source_id="obs_a1",
                target_id="ac_causal_prem",
                relation_type="SUPPORTS",
                confidence=0.90,
                scope="local",
                edge_tenability=0.90,
            ),
            TheoryRelation(
                source_id="obs_a2",
                target_id="ac_deontic_prem",
                relation_type="SUPPORTS",
                confidence=0.90,
                scope="local",
                edge_tenability=0.90,
            ),
            TheoryRelation(
                source_id="ac_deontic_prem",
                target_id="ac_causal_prem",
                relation_type="ATTACKS",
                confidence=0.90,
                scope="global",
                edge_tenability=0.30,
            ),
            TheoryRelation(
                source_id="obs_a_weak",
                target_id="ac_axiom_a",
                relation_type="SUPPORTS",
                confidence=0.60,
                scope="local",
                edge_tenability=0.90,
            ),
            TheoryRelation(
                source_id="obs_b",
                target_id="ac_claim_b",
                relation_type="SUPPORTS",
                confidence=0.95,
                scope="local",
                edge_tenability=0.95,
            ),
        ]

        atoms = (
            ac_claim_a,
            obs_down_a,
            ac_downstream_a,
            obs_a1,
            obs_a2,
            ac_causal_prem,
            ac_deontic_prem,
            obs_a_weak,
            ac_axiom_a,
            obs_b,
            ac_claim_b,
        )
        envelopes: list[ArtifactEnvelope[Any]] = [
            build_theory_atom_artifact(
                atom,
                run_id=ctx.run_id,
                phase_name="Phase 6: TheoryNet",
                method="stub_theorynet",
            )
            for atom in atoms
        ]
        envelopes.extend(
            build_theory_relation_artifact(
                rel,
                run_id=ctx.run_id,
                phase_name="Phase 6: TheoryNet",
                method="stub_theorynet",
            )
            for rel in rels
        )
        return envelopes

    return [
        _StaticPhaseRunner(
            name="Phase 1: Ingestion",
            phase_key="phase1",
            input_view=None,
            reads_kinds=frozenset(),
            writes_kinds=frozenset({ArtifactKind.DOCUMENT, ArtifactKind.CHUNK}),
            dependencies=(),
            builder=build_l1,
        ),
        _StaticPhaseRunner(
            name="Phase 2: Entities",
            phase_key="phase2",
            input_view=EpistemicStateView,
            reads_kinds=frozenset({ArtifactKind.CHUNK}),
            writes_kinds=frozenset(
                {ArtifactKind.LINKED_ENTITY, ArtifactKind.LOCAL_RELATION}
            ),
            dependencies=("phase1",),
            builder=build_l2,
        ),
        _StaticPhaseRunner(
            name="Phase 6: TheoryNet",
            phase_key="phase6",
            input_view=EpistemicStateView,
            reads_kinds=frozenset({ArtifactKind.CHUNK, ArtifactKind.LINKED_ENTITY}),
            writes_kinds=frozenset(
                {ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION}
            ),
            dependencies=("phase2",),
            builder=build_l4,
        ),
    ]


# ---------------------------------------------------------------------------
# 1. ArtifactSubgraphReader.vector_search + AxiomGrounder integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subgraph_reader_vector_search_returns_valid_search_results() -> None:
    """Ensure ``ArtifactSubgraphReader.vector_search`` emits valid ``SearchResult`` items."""
    chunk_hit = L1Chunk(
        id="c_emp",
        source_doc_id="doc_1",
        sequence_index=0,
        token_count=8,
        text="Empirical trial N=42 yields p=0.01.",
        embedding=[1.0, 0.0, 0.0],
    )
    chunk_miss = L1Chunk(
        id="c_far",
        source_doc_id="doc_1",
        sequence_index=1,
        token_count=7,
        text="Abstract modal postulate without data.",
        embedding=[0.0, 1.0, 0.0],
    )
    collection = ArtifactCollection(
        [
            build_chunk_artifact(
                chunk_hit, run_id="r1", phase_name="p1", method="stub"
            ),
            build_chunk_artifact(
                chunk_miss, run_id="r1", phase_name="p1", method="stub"
            ),
        ]
    )
    reader = ArtifactSubgraphReader.from_view(
        EpistemicStateView.from_collection(collection)
    )

    results = await reader.vector_search([1.0, 0.0, 0.0], top_k=2, node_label="Chunk")
    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].node_id == "c_emp"
    assert results[0].node_label == "Chunk"
    assert results[0].node_name == "c_emp"
    assert results[0].score == pytest.approx(1.0)
    assert results[1].node_id == "c_far"
    assert results[1].score == pytest.approx(0.0)
    assert await reader.vector_search([1.0, 0.0, 0.0], top_k=0) == []
    assert (
        await reader.vector_search([1.0, 0.0, 0.0], top_k=2, node_label="Entity")
        == []
    )


@pytest.mark.asyncio
async def test_axiom_grounder_end_to_end_with_subgraph_reader_vector_search() -> None:
    """Exercise ``TheoryGuidedAxiomGrounder`` via real ``ArtifactSubgraphReader.vector_search``."""
    target_chunk = L1Chunk(
        id="c_main",
        source_doc_id="doc_a",
        sequence_index=0,
        token_count=8,
        text="Empirical claim requires laboratory measurement backing.",
        embedding=[0.7, 0.7, 0.0],
    )
    vec_chunk = L1Chunk(
        id="c_vec_lab",
        source_doc_id="doc_a",
        sequence_index=9,
        token_count=9,
        text="Randomized empirical trial recorded velocity v=9.81 m/s^2.",
        embedding=[1.0, 0.0, 0.0],
    )
    ungrounded = TheoryAtom(
        id="ax_emp",
        text="Empirical claim requires laboratory measurement backing.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="c_main",
        entity_ids=[],
        measurements=[],
        confidence=0.85,
        local_tenability=0.35,
    )
    collection = ArtifactCollection(
        [
            build_chunk_artifact(
                target_chunk, run_id="r1", phase_name="p1", method="stub"
            ),
            build_chunk_artifact(
                vec_chunk, run_id="r1", phase_name="p1", method="stub"
            ),
            build_theory_atom_artifact(
                ungrounded, run_id="r1", phase_name="p6", method="stub"
            ),
        ]
    )
    state = EpistemicStateView.from_collection(collection)

    ner = _StubNERExtractor(
        entities_by_chunk={
            "c_vec_lab": [
                L2Entity(
                    id="ent_trial",
                    label="Concept",
                    name="Randomized Trial",
                    description="Empirical measurement protocol",
                    source_chunk_ids=["c_vec_lab"],
                )
            ]
        }
    )

    def _llm_resolver(output_cls: type[Any], _kwargs: dict[str, Any]) -> Any:
        if output_cls is AxiomGroundingOutput:
            return AxiomGroundingOutput(
                observations=[
                    RecoveredObservationAtom(
                        local_id="OBS_LAB",
                        text="Trial observed velocity v=9.81 m/s^2.",
                        component_type="ObservationUnit",
                        source_chunk_id="c_vec_lab",
                        target_atom_id="ax_emp",
                        relation_type="SUPPORTS",
                        confidence=0.9,
                        measurements=[
                            RecoveredMeasurement(
                                dimension="acceleration",
                                value="9.81",
                                unit="m/s^2",
                            )
                        ],
                    )
                ],
                entities=[
                    RecoveredGroundingEntity(
                        name="Randomized Trial",
                        label="Concept",
                        description="Empirical laboratory measurement.",
                        source_chunk_id="c_vec_lab",
                    )
                ],
            )
        return output_cls()

    grounder = TheoryGuidedAxiomGrounder(
        ner_extractor=ner,
        llm=_StubStructuredLLM(_llm_resolver),
        theory_projector=GenericTheoryProjector(),
        embedding_model=_StubEmbeddingModel(),
        vector_top_k=2,
    )
    deficit = EpistemicDeficit(
        deficit_id="def_vec_ax",
        deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
        severity=0.85,
        target_chunk_ids=["c_main"],
        target_atom_ids=["ax_emp"],
        theory_lens={"required_dimensions": ["acceleration"]},
        refinement_pass=0,
    )
    delta = await grounder.ground_axiom(deficit, state)

    assert not delta.is_empty
    assert "c_vec_lab" in ner.called_chunk_ids
    obs_atoms = [a for a in delta.theory_atoms if a.component_type == "ObservationUnit"]
    assert obs_atoms
    assert any(m.dimension == "acceleration" for m in obs_atoms[0].measurements)
    assert delta.entities


# ---------------------------------------------------------------------------
# 2. Coordinator protocol, validation, discovery & max_refinement_cycles=0 parity
# ---------------------------------------------------------------------------


def test_coordinator_protocol_validation_and_fingerprint_discovery() -> None:
    """Verify protocol compliance, validation TypeErrors, and find_components."""
    detector = TheoryNetDeficitDetector()
    premise = LLMTheoryGuidedPremiseRecoverer()
    splitter = ConceptionConceptSplitter()
    grounder = TheoryGuidedAxiomGrounder()
    projector = TheoryNetProjector(schema=DEFAULT_SCHEMA)

    coordinator = ClosedLoopRefinementCoordinator(
        detector=detector,
        premise_recoverer=premise,
        concept_splitter=splitter,
        axiom_grounder=grounder,
        theorynet_projector=projector,
        config=HermeneuticRefinementConfig(max_refinement_cycles=2),
    )

    assert isinstance(coordinator, HermeneuticRefinementCoordinator)
    assert isinstance(coordinator, TargetedRefinementPort)
    assert isinstance(coordinator, Fingerprintable)

    discovered = find_components(coordinator)
    assert set(discovered.keys()) >= {
        "detector",
        "premise_recoverer",
        "concept_splitter",
        "axiom_grounder",
        "theorynet_projector",
    }
    fp1 = coordinator.fingerprint()
    fp2 = coordinator.fingerprint()
    assert fp1 == fp2
    assert fp1["class"] == "ClosedLoopRefinementCoordinator"

    with pytest.raises(TypeError, match="EpistemicDeficitDetector"):
        ClosedLoopRefinementCoordinator(detector="not-a-detector")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="TheoryGuidedPremiseRecoverer"):
        ClosedLoopRefinementCoordinator(
            detector=detector,
            premise_recoverer="bad-recoverer",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="TargetedConceptSplitter"):
        ClosedLoopRefinementCoordinator(
            detector=detector,
            concept_splitter="bad-splitter",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="LocalizedAxiomGrounder"):
        ClosedLoopRefinementCoordinator(
            detector=detector,
            axiom_grounder="bad-grounder",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_zero_max_cycles_feed_forward_parity_and_phase_reuse(
    tmp_path: Path,
) -> None:
    """Verify ``max_refinement_cycles=0`` preserves identical fingerprints and reuses phases on toggle."""
    phases = _build_two_subgraph_forward_phases()
    observer = MetricsObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(observer)

    cfg_zero = _make_config(tmp_path / "r0", max_cycles=0, project_to_graph=False)
    coordinator = ClosedLoopRefinementCoordinator(
        detector=TheoryNetDeficitDetector(),
        config=HermeneuticRefinementConfig(max_refinement_cycles=0),
    )

    pipe_no_coord = Pipeline(
        phases=_build_two_subgraph_forward_phases(),
        config=cfg_zero,
        event_emitter=emitter,
    )
    pipe_with_coord = Pipeline(
        phases=phases,
        config=cfg_zero,
        event_emitter=emitter,
        refinement_coordinator=coordinator,
    )

    # Active refinement fingerprints are omitted when max_refinement_cycles == 0
    assert pipe_no_coord.fingerprint() == pipe_with_coord.fingerprint()
    assert (
        pipe_no_coord.engine.method_fingerprints()
        == pipe_with_coord.engine.method_fingerprints()
    )
    assert (
        pipe_no_coord.engine.phase_config_fingerprints()
        == pipe_with_coord.engine.phase_config_fingerprints()
    )
    assert "refinement" not in pipe_with_coord.engine.phase_config_fingerprints()

    # Run 1: pure feed-forward (max_refinement_cycles=0)
    shared_dir = tmp_path / "shared_toggle"
    cfg_pass0 = _make_config(shared_dir, max_cycles=0, project_to_graph=False)
    captured_events: list[Any] = []
    toggle_emitter = SimpleEventEmitter()
    toggle_emitter.register_observer(_ListObserver(captured_events))

    phases_run1 = _build_two_subgraph_forward_phases()
    pipe1 = Pipeline(
        phases=phases_run1,
        config=cfg_pass0,
        event_emitter=toggle_emitter,
    )
    res1 = await pipe1.run(PipelineInput(source_paths=[]), run_id="run_zero")

    assert res1.manifest.status == RunStatus.COMPLETED
    assert res1.manifest.refinement_pass == 0
    assert all(r.refinement_pass == 0 for r in res1.manifest.phase_records)
    assert all(r.phase_key != "refinement" for r in res1.manifest.phase_records)
    assert not any(
        isinstance(ev, (RefinementCycleStarted, RefinementCycleCompleted))
        for ev in captured_events
    )
    assert all(p.run_count == 1 for p in phases_run1)

    # Run 2: enable max_refinement_cycles=1 on the same store -> forward phases reused!
    cfg_pass1 = _make_config(shared_dir, max_cycles=1, project_to_graph=False)
    phases_run2 = _build_two_subgraph_forward_phases()
    recovered_llm = _StubStructuredLLM(
        lambda output_cls, _args: PremiseRecoveryOutput(
            recovered_premises=[
                RecoveredImplicitPremise(
                    local_id="P_bridge",
                    text="Autonomous agency is an irreducible normative category.",
                    component_type="ObservationUnit",
                    source_chunk_id="chunk_a2",
                    target_atom_id="ac_claim_a",
                    relation_type="SUPPORTS",
                    confidence=0.9,
                )
            ]
        )
        if output_cls is PremiseRecoveryOutput
        else output_cls()
    )
    coord_active = ClosedLoopRefinementCoordinator(
        detector=TheoryNetDeficitDetector(),
        premise_recoverer=LLMTheoryGuidedPremiseRecoverer(llm=recovered_llm),
        config=cfg_pass1.refinement,
    )
    pipe2 = Pipeline(
        phases=phases_run2,
        config=cfg_pass1,
        event_emitter=toggle_emitter,
        refinement_coordinator=coord_active,
    )
    res2 = await pipe2.run(
        PipelineInput(source_paths=[]), run_id="run_refine_after_zero", parent_run_id="run_zero"
    )

    assert all(p.run_count == 0 for p in phases_run2)
    assert res2.manifest.refinement_pass == 1
    assert any(r.phase_key == "refinement" for r in res2.manifest.phase_records)
    assert any(
        isinstance(ev, RefinementCycleCompleted) for ev in captured_events
    )


# ---------------------------------------------------------------------------
# 3. Full End-to-End Closed-Loop Refinement & Strict Localization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_closed_loop_refinement_and_localization(
    tmp_path: Path,
) -> None:
    """Verify full closed-loop handling of all 3 deficits, TheoryNet reconvergence, and localization."""
    cfg = _make_config(
        tmp_path, max_cycles=1, max_deficits_per_cycle=10, project_to_graph=True
    )
    projection_graph = _RecordingProjectionGraph()
    events: list[Any] = []
    metrics = MetricsObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(metrics)
    emitter.register_observer(_ListObserver(events))

    def _llm_resolver(output_cls: type[Any], _kwargs: dict[str, Any]) -> Any:
        if output_cls is PremiseRecoveryOutput:
            return PremiseRecoveryOutput(
                recovered_premises=[
                    RecoveredImplicitPremise(
                        local_id="P_warrant",
                        text="Moral responsibility requires reasons-responsive autonomous agency.",
                        component_type="ObservationUnit",
                        source_chunk_id="chunk_a2",
                        target_atom_id="ac_claim_a",
                        relation_type="SUPPORTS",
                        confidence=0.92,
                        weight=0.9,
                        entity_ids=["ent_action"],
                    )
                ]
            )
        if output_cls is AxiomGroundingOutput:
            return AxiomGroundingOutput(
                observations=[
                    RecoveredObservationAtom(
                        local_id="OBS_STUDY",
                        text="Trial recorded N=42 with p=0.01 confirming deliberate control.",
                        component_type="ObservationUnit",
                        source_chunk_id="chunk_a3",
                        target_atom_id="ac_axiom_a",
                        relation_type="SUPPORTS",
                        confidence=0.92,
                        measurements=[
                            RecoveredMeasurement(
                                dimension="sample_size", value="42", unit="trials"
                            ),
                            RecoveredMeasurement(
                                dimension="p_value", value="0.01", unit="p"
                            ),
                        ],
                    )
                ],
                entities=[
                    RecoveredGroundingEntity(
                        name="Deliberation Study",
                        label="Method",
                        description="Controlled behavioral trial.",
                        source_chunk_id="chunk_a3",
                    )
                ],
            )
        return output_cls()

    stub_llm = _StubStructuredLLM(_llm_resolver)
    stub_embedder = _StubEmbeddingModel()
    stub_ner = _StubNERExtractor(
        entities_by_chunk={
            "chunk_a3": [
                L2Entity(
                    id="ent_delib_study",
                    label="Method",
                    name="Deliberation Study",
                    description="Empirical study",
                    source_chunk_ids=["chunk_a3"],
                )
            ]
        }
    )
    detector = TheoryNetDeficitDetector(config=cfg.refinement, schema=DEFAULT_SCHEMA)
    theorynet_projector = TheoryNetProjector(schema=DEFAULT_SCHEMA)
    coordinator = ClosedLoopRefinementCoordinator(
        detector=detector,
        premise_recoverer=LLMTheoryGuidedPremiseRecoverer(llm=stub_llm),
        concept_splitter=ConceptionConceptSplitter(
            embedding_model=stub_embedder, schema=DEFAULT_SCHEMA
        ),
        axiom_grounder=TheoryGuidedAxiomGrounder(
            ner_extractor=stub_ner,
            llm=stub_llm,
            theory_projector=GenericTheoryProjector(),
            embedding_model=stub_embedder,
            schema=DEFAULT_SCHEMA,
            vector_top_k=2,
        ),
        theorynet_projector=theorynet_projector,
        config=cfg.refinement,
        schema=DEFAULT_SCHEMA,
    )

    pipeline = Pipeline(
        phases=_build_two_subgraph_forward_phases(),
        config=cfg,
        projection_graph=projection_graph,
        event_emitter=emitter,
        refinement_coordinator=coordinator,
    )
    pipeline_input = PipelineInput(
        source_paths=[], curation_ledger=EpistemicCurationLedger()
    )

    result = await pipeline.run(pipeline_input, run_id="run_loop_full")

    # 1. Manifest & RunReport lineage
    assert result.manifest.status == RunStatus.COMPLETED
    assert result.manifest.refinement_pass == 1
    assert result.report.manifest is not None
    assert result.report.manifest.refinement_pass == 1
    refine_records = [
        r for r in result.manifest.phase_records if r.phase_key == "refinement"
    ]
    assert len(refine_records) == 1
    assert refine_records[0].refinement_pass == 1
    assert refine_records[0].phase_name == "Hermeneutic Refinement (Pass 1)"
    assert any(
        r.phase_key == "refinement" and r.refinement_pass == 1
        for r in result.report.phase_records
    )

    # 2. Curation ledger updated with cannot_link pairs from POLYSEMY_COLLISION split
    ledger = pipeline_input.resolved_curation_ledger()
    assert ledger is not None
    assert len(ledger.cannot_link_entities) >= 1

    # 3. Persisted artifacts preserve Pass 0 history & Pass 1 overlays
    persisted = sorted(
        await pipeline.artifact_store.list_run_artifacts("run_loop_full"),
        key=lambda env: (env.provenance.refinement_pass, env.artifact_id),
    )
    full_collection = ArtifactCollection(persisted)

    # Dependency DAG over persisted Pass-0 + Pass-1 artifacts must stay strictly acyclic
    topsorted = ArtifactDependencyGraph.from_artifacts(persisted).topsort()
    assert len(topsorted) > 0

    deficit_envs = [
        e for e in persisted if e.kind == ArtifactKind.EPISTEMIC_DEFICIT
    ]
    detected_kinds = {
        e.payload.deficit_kind
        for e in deficit_envs
        if isinstance(e.payload, EpistemicDeficitArtifact)
    }
    assert detected_kinds == {
        EpistemicDeficitKind.ENTHYMEME_GAP,
        EpistemicDeficitKind.POLYSEMY_COLLISION,
        EpistemicDeficitKind.UNGROUNDED_AXIOM,
    }
    assert all(e.provenance.refinement_pass == 0 for e in deficit_envs)

    # Refined artifacts exist at pass 1 with deficit_id lineage
    pass1_envs = [e for e in persisted if e.provenance.refinement_pass == 1]
    assert len(pass1_envs) >= 4
    assert any(
        e.kind == ArtifactKind.THEORY_ATOM for e in pass1_envs
    )
    assert any(
        e.kind == ArtifactKind.THEORY_RELATION for e in pass1_envs
    )
    assert any(e.provenance.deficit_id is not None for e in pass1_envs)

    # Verify recovered grounding observation + premise atoms + split entities appear at pass 1
    latest_atom_view = Phase4ArtifactsView.from_collection(full_collection)
    atoms_by_id = {a.id: a for a in latest_atom_view.theory_atoms}
    assert any(
        any(m.dimension == "sample_size" for m in atom.measurements)
        for atom in latest_atom_view.theory_atoms
    )
    # ac_claim_a reconverged in TheoryNet after receiving recovered premise support
    assert (
        full_collection.latest_by_identity["argument_component::ac_claim_a"].provenance.refinement_pass
        == 1
    )
    assert atoms_by_id["ac_claim_a"].equilibrium_strength is not None

    # Pass 0 & Pass 1 versions both preserved in ArtifactCollection.history while latest_by_identity sees Pass 1
    claim_history = [
        e
        for e in full_collection.history
        if e.identity_key == "argument_component::ac_claim_a"
    ]
    assert {e.provenance.refinement_pass for e in claim_history} == {0, 1}
    assert (
        full_collection.latest_by_identity["argument_component::ac_claim_a"].provenance.refinement_pass
        == 1
    )

    # 4. Strict Subgraph Localization: unaffected Doc B NEVER emitted/updated/re-projected in Pass 1!
    for pass1_env in pass1_envs:
        assert "doc_b" not in pass1_env.artifact_id
        assert "chunk_b1" not in pass1_env.artifact_id
        assert "ent_conservation" not in pass1_env.artifact_id
        assert "ac_claim_b" not in pass1_env.artifact_id
        assert "obs_b" not in pass1_env.artifact_id
        assert pass1_env.artifact_id not in refine_records[0].input_artifact_ids

    assert (
        full_collection.latest_by_identity["chunk::chunk_b1"].provenance.refinement_pass
        == 0
    )
    assert (
        full_collection.latest_by_identity[
            "linked_entity::ent_conservation"
        ].provenance.refinement_pass
        == 0
    )
    assert (
        full_collection.latest_by_identity[
            "argument_component::ac_claim_b"
        ].provenance.refinement_pass
        == 0
    )

    # Forward phase projection ran batches with Doc B, then refinement projected ONLY localized Pass-1 batches
    assert len(projection_graph.atom_batches) >= 2
    last_atom_batch = projection_graph.atom_batches[-1]
    assert "ac_claim_b" not in last_atom_batch
    assert "obs_b" not in last_atom_batch
    # Also ensure NER was NOT called on unaffected chunk_b1
    assert "chunk_b1" not in stub_ner.called_chunk_ids

    # 5. Query APIs (get_run_report + get_run_artifacts_raw) reflect refined latest overlay
    loaded_report = await pipeline.engine.get_run_report("run_loop_full")
    assert loaded_report.manifest is not None
    assert loaded_report.manifest.refinement_pass == 1
    assert any(r.phase_key == "refinement" for r in loaded_report.phase_records)
    raw_latest = await pipeline.engine.get_run_artifacts_raw("run_loop_full")
    raw_by_key = {e.identity_key: e for e in raw_latest}
    assert raw_by_key["argument_component::ac_claim_a"].provenance.refinement_pass == 1
    assert raw_by_key["argument_component::ac_claim_b"].provenance.refinement_pass == 0

    # 6. Events & telemetry
    assert any(isinstance(e, RefinementCycleStarted) for e in events)
    completed_evs = [e for e in events if isinstance(e, RefinementCycleCompleted)]
    assert len(completed_evs) == 1
    assert completed_evs[0].refinement_pass == 1
    assert any(isinstance(e, EpistemicDeficitDetected) for e in events)
    assert sum(metrics.epistemic_deficits_detected.values()) >= 3
    assert metrics.refinement_cycles_completed == 1
    assert metrics.refinement_deficits_resolved >= 3


# ---------------------------------------------------------------------------
# 4. Bounded Loop Controls, Convergence, Re-Scoring & Failure Modes
# ---------------------------------------------------------------------------


class _ScriptedDetector:
    """Deterministic scriptable EpistemicDeficitDetector for loop boundary tests."""

    def __init__(self, responder: Any) -> None:
        self._responder = responder
        self.calls: list[int] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_ScriptedDetector"}

    def detect_deficits(
        self,
        state: EpistemicStateView,
        *,
        refinement_pass: int = 0,
        config: HermeneuticRefinementConfig | None = None,
        context: ArtifactExecutionContext | None = None,
    ) -> list[EpistemicDeficit]:
        self.calls.append(refinement_pass)
        return self._responder(state, refinement_pass)


class _ScriptedPremiseHandler:
    """Deterministic scriptable TheoryGuidedPremiseRecoverer."""

    def __init__(self, handler_fn: Any) -> None:
        self._handler_fn = handler_fn
        self.handled_ids: list[str] = []

    def fingerprint(self) -> dict[str, Any]:
        return {"class": "_ScriptedPremiseHandler"}

    async def recover_premises(
        self,
        deficit: EpistemicDeficit,
        state: EpistemicStateView,
        *,
        context: ArtifactExecutionContext | None = None,
    ) -> RefinementDelta:
        self.handled_ids.append(deficit.deficit_id)
        return self._handler_fn(deficit, state, context)


@pytest.mark.asyncio
async def test_early_convergence_cycle_cap_priority_flags_and_signature_guard(
    tmp_path: Path,
) -> None:
    """Test early termination, cycle cap, severity prioritization, enable flags, and duplicate guard."""
    base_claim = TheoryAtom(
        id="c1",
        text="Claim 1",
        component_type="TheoreticalHypothesis",
        source_chunk_id="ch1",
    )
    base_coll = ArtifactCollection(
        [
            build_chunk_artifact(
                L1Chunk(
                    id="ch1",
                    source_doc_id="d1",
                    sequence_index=0,
                    token_count=1,
                    text="Context",
                ),
                run_id="r_ctrl",
                phase_name="p1",
                method="stub",
            ),
            build_theory_atom_artifact(
                base_claim, run_id="r_ctrl", phase_name="p6", method="stub"
            ),
        ]
    )

    # A. Multi-cycle convergence: Cycle 1 fixes d1 -> exposes d2 -> Cycle 2 fixes d2 -> early exit at pass 2 < 4
    def multi_cycle_detect(_state: Any, rpass: int) -> list[EpistemicDeficit]:
        if rpass == 0:
            return [
                EpistemicDeficit(
                    deficit_id="d_first",
                    deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
                    severity=0.9,
                    target_atom_ids=["c1"],
                )
            ]
        if rpass == 1:
            return [
                EpistemicDeficit(
                    deficit_id="d_second",
                    deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
                    severity=0.8,
                    target_atom_ids=["c1"],
                )
            ]
        return []

    def emit_premise(deficit: EpistemicDeficit, _state: Any, _ctx: Any) -> RefinementDelta:
        return RefinementDelta(
            theory_atoms=[
                TheoryAtom(
                    id=f"prem_for_{deficit.deficit_id}",
                    text=f"Premise resolving {deficit.deficit_id}",
                    component_type="ObservationUnit",
                    source_chunk_id="ch1",
                )
            ],
            resolved_deficit_ids=[deficit.deficit_id],
        )

    coord_conv = ClosedLoopRefinementCoordinator(
        detector=_ScriptedDetector(multi_cycle_detect),
        premise_recoverer=_ScriptedPremiseHandler(emit_premise),
        config=HermeneuticRefinementConfig(max_refinement_cycles=4),
    )
    manifest = RunManifest(run_id="r_ctrl")
    ctx = ArtifactExecutionContext(
        run_id="r_ctrl", manifest=manifest, pipeline_input=PipelineInput(source_paths=[])
    )
    events: list[Any] = []
    emitter = SimpleEventEmitter()
    emitter.register_observer(_ListObserver(events))

    with use_event_emitter(emitter):
        out_coll = await coord_conv.refine(base_coll, ctx)

    assert manifest.refinement_pass == 2
    assert len(manifest.phase_records) == 2
    completed = [e for e in events if isinstance(e, RefinementCycleCompleted)]
    assert [c.refinement_pass for c in completed] == [1, 2]
    assert completed[0].converged is False
    assert completed[1].converged is True
    assert "argument_component::prem_for_d_second" in out_coll.latest_by_identity

    # B. Cycle cap & max_deficits_per_cycle=1 priority ordering + disabled flag filtering
    def unbounded_detect(_state: Any, rpass: int) -> list[EpistemicDeficit]:
        return [
            EpistemicDeficit(
                deficit_id=f"low_p{rpass}",
                deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
                severity=0.4,
                target_atom_ids=["c1"],
            ),
            EpistemicDeficit(
                deficit_id=f"high_p{rpass}",
                deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
                severity=0.95,
                target_atom_ids=["c1"],
            ),
            EpistemicDeficit(
                deficit_id=f"split_ignored_p{rpass}",
                deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
                severity=0.99,
            ),
        ]

    premise_cap_handler = _ScriptedPremiseHandler(emit_premise)
    coord_cap = ClosedLoopRefinementCoordinator(
        detector=_ScriptedDetector(unbounded_detect),
        premise_recoverer=premise_cap_handler,
        concept_splitter=ConceptionConceptSplitter(),
        config=HermeneuticRefinementConfig(
            max_refinement_cycles=2,
            max_deficits_per_cycle=1,
            enable_targeted_concept_split=False,
        ),
    )
    manifest_cap = RunManifest(run_id="r_cap")
    ctx_cap = ArtifactExecutionContext(
        run_id="r_cap", manifest=manifest_cap, pipeline_input=PipelineInput(source_paths=[])
    )
    await coord_cap.refine(base_coll, ctx_cap)

    assert manifest_cap.refinement_pass == 2
    assert premise_cap_handler.handled_ids == ["high_p0", "high_p1"]

    # C. Cross-cycle identical deficit signature suppression stops loop after 1st handling
    fixed_deficit = EpistemicDeficit(
        deficit_id="d_persistent",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        severity=0.8,
        target_atom_ids=["c1"],
        theory_lens={"anomalies": ["same_anomaly"]},
    )
    dup_handler = _ScriptedPremiseHandler(emit_premise)
    coord_dup = ClosedLoopRefinementCoordinator(
        detector=_ScriptedDetector(lambda _s, _p: [fixed_deficit]),
        premise_recoverer=dup_handler,
        config=HermeneuticRefinementConfig(max_refinement_cycles=3),
    )
    manifest_dup = RunManifest(run_id="r_dup")
    ctx_dup = ArtifactExecutionContext(
        run_id="r_dup", manifest=manifest_dup, pipeline_input=PipelineInput(source_paths=[])
    )
    await coord_dup.refine(base_coll, ctx_dup)
    assert manifest_dup.refinement_pass == 1
    assert dup_handler.handled_ids == ["d_persistent"]


@pytest.mark.asyncio
async def test_localized_enrichment_rescoring_only_touches_affected_subgraph() -> None:
    """Verify ``enrichment_runner`` receives strictly localized subgraph of affected atoms."""

    class _RecordingEnrichmentRunner(Fingerprintable):
        name = "Theoretical Enrichment"
        phase_key = "theoretical_enrichment"

        def __init__(self) -> None:
            self.seen_atom_ids: list[str] = []
            self.seen_lineage_fingerprint: str | None = None

        def fingerprint(self) -> dict[str, Any]:
            return {"class": "_RecordingEnrichmentRunner"}

        async def run(
            self, input_view: Phase4ArtifactsView, ctx: ArtifactExecutionContext
        ) -> ArtifactCollection:
            self.seen_atom_ids = sorted(a.id for a in input_view.theory_atoms)
            self.seen_lineage_fingerprint = ctx.lineage_fingerprint
            payload = TheoreticalEnrichmentArtifact(
                enrichment_id="enr_t_loc",
                cluster_id="cluster-ch_a",
                theory_id="t_loc",
                local_tenability=0.9,
                edge_tenabilities={},
                aggregated_tenability=0.9,
                admissible_blur_delta=0.05,
                is_tenable=True,
                anomalies=[],
            )
            return ArtifactCollection(
                [
                    ArtifactEnvelope[TheoreticalEnrichmentArtifact](
                        artifact_id="artifact::enr_t_loc",
                        identity_key="theoretical_enrichment::t_loc",
                        kind=ArtifactKind.THEORETICAL_ENRICHMENT,
                        run_id=ctx.run_id,
                        phase_name="Theoretical Enrichment",
                        method="theoretical_enrichment",
                        payload=payload,
                    )
                ]
            )

    enr = _RecordingEnrichmentRunner()
    coll = ArtifactCollection(
        [
            build_chunk_artifact(
                L1Chunk(
                    id="ch_a",
                    source_doc_id="doc_a",
                    sequence_index=0,
                    token_count=1,
                    text="A",
                ),
                run_id="r_enr",
                phase_name="p1",
                method="stub",
            ),
            build_chunk_artifact(
                L1Chunk(
                    id="ch_b",
                    source_doc_id="doc_b",
                    sequence_index=0,
                    token_count=1,
                    text="B",
                ),
                run_id="r_enr",
                phase_name="p1",
                method="stub",
            ),
            build_theory_atom_artifact(
                TheoryAtom(
                    id="atom_a",
                    text="Affected atom A",
                    component_type="TheoreticalHypothesis",
                    source_chunk_id="ch_a",
                ),
                run_id="r_enr",
                phase_name="p6",
                method="stub",
            ),
            build_theory_atom_artifact(
                TheoryAtom(
                    id="atom_b_clean",
                    text="Unaffected atom B",
                    component_type="TheoreticalHypothesis",
                    source_chunk_id="ch_b",
                ),
                run_id="r_enr",
                phase_name="p6",
                method="stub",
            ),
        ]
    )

    deficit = EpistemicDeficit(
        deficit_id="d_enr",
        deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
        severity=0.9,
        target_chunk_ids=["ch_a"],
        target_atom_ids=["atom_a"],
    )
    premise = _ScriptedPremiseHandler(
        lambda d, _s, _c: RefinementDelta(
            theory_atoms=[
                TheoryAtom(
                    id="atom_a_prem",
                    text="Bridge",
                    component_type="ObservationUnit",
                    source_chunk_id="ch_a",
                )
            ],
            resolved_deficit_ids=[d.deficit_id],
        )
    )
    coord = ClosedLoopRefinementCoordinator(
        detector=_ScriptedDetector(lambda _s, p: [deficit] if p == 0 else []),
        premise_recoverer=premise,
        enrichment_runner=enr,  # type: ignore[arg-type]
        config=HermeneuticRefinementConfig(max_refinement_cycles=1),
    )
    manifest = RunManifest(run_id="r_enr")
    ctx = ArtifactExecutionContext(
        run_id="r_enr",
        manifest=manifest,
        pipeline_input=PipelineInput(source_paths=[]),
        lineage_fingerprint="pass0-lineage",
    )
    out = await coord.refine(coll, ctx)

    assert "atom_a" in enr.seen_atom_ids
    assert "atom_a_prem" in enr.seen_atom_ids
    assert "atom_b_clean" not in enr.seen_atom_ids
    assert enr.seen_lineage_fingerprint == "pass0-lineage::refine_pass1"
    assert "theoretical_enrichment::t_loc::cluster-ch_a" in out.latest_by_identity


@pytest.mark.asyncio
async def test_multicycle_two_passes_stabilizes_without_cascading_splits(
    tmp_path: Path,
) -> None:
    """Verify ``max_refinement_cycles=2`` avoids cascading re-splits and preserves DAG acyclicity."""
    cfg = _make_config(
        tmp_path, max_cycles=2, max_deficits_per_cycle=10, project_to_graph=False
    )

    def _llm_resolver(output_cls: type[Any], _kwargs: dict[str, Any]) -> Any:
        if output_cls is PremiseRecoveryOutput:
            return PremiseRecoveryOutput(
                recovered_premises=[
                    RecoveredImplicitPremise(
                        local_id="P_warrant",
                        text="Moral responsibility requires reasons-responsive agency.",
                        component_type="ObservationUnit",
                        source_chunk_id="chunk_a2",
                        target_atom_id="ac_claim_a",
                        relation_type="SUPPORTS",
                        confidence=0.92,
                    )
                ]
            )
        if output_cls is AxiomGroundingOutput:
            return AxiomGroundingOutput(
                observations=[
                    RecoveredObservationAtom(
                        local_id="OBS_STUDY",
                        text="Trial recorded N=42 with p=0.01.",
                        component_type="ObservationUnit",
                        source_chunk_id="chunk_a3",
                        target_atom_id="ac_axiom_a",
                        relation_type="SUPPORTS",
                        confidence=0.92,
                        measurements=[
                            RecoveredMeasurement(dimension="sample_size", value="42"),
                            RecoveredMeasurement(dimension="p_value", value="0.01"),
                        ],
                    )
                ]
            )
        return output_cls()

    stub_llm = _StubStructuredLLM(_llm_resolver)
    stub_embedder = _StubEmbeddingModel()
    coordinator = ClosedLoopRefinementCoordinator(
        detector=TheoryNetDeficitDetector(config=cfg.refinement, schema=DEFAULT_SCHEMA),
        premise_recoverer=LLMTheoryGuidedPremiseRecoverer(llm=stub_llm),
        concept_splitter=ConceptionConceptSplitter(
            embedding_model=stub_embedder, schema=DEFAULT_SCHEMA
        ),
        axiom_grounder=TheoryGuidedAxiomGrounder(
            llm=stub_llm,
            theory_projector=GenericTheoryProjector(),
            embedding_model=stub_embedder,
            schema=DEFAULT_SCHEMA,
            vector_top_k=2,
        ),
        theorynet_projector=TheoryNetProjector(schema=DEFAULT_SCHEMA),
        config=cfg.refinement,
        schema=DEFAULT_SCHEMA,
    )
    pipeline = Pipeline(
        phases=_build_two_subgraph_forward_phases(),
        config=cfg,
        refinement_coordinator=coordinator,
    )
    res = await pipeline.run(
        PipelineInput(source_paths=[], curation_ledger=EpistemicCurationLedger()),
        run_id="run_two_cycles",
    )
    assert res.manifest.status == RunStatus.COMPLETED

    persisted = sorted(
        await pipeline.artifact_store.list_run_artifacts("run_two_cycles"),
        key=lambda env: (env.provenance.refinement_pass, env.artifact_id),
    )
    assert len(ArtifactDependencyGraph.from_artifacts(persisted).topsort()) > 0

    entity_ids = [
        env.payload.entity_id
        for env in persisted
        if env.kind == ArtifactKind.LINKED_ENTITY
    ]
    assert not any("__sense_" in eid.split("__sense_", 1)[1] for eid in entity_ids if "__sense_" in eid)
    assert "ent_action__sense_1" in entity_ids
    assert "ent_action__sense_2" in entity_ids

    # Also verify ConceptionConceptSplitter directly refuses cross-entity chunk pulling
    single_sense_ent = L2Entity(
        id="ent_single__sense_2",
        label="Concept",
        name="Action (Normative)",
        source_chunk_ids=["chunk_a2"],
    )
    atom_own = TheoryAtom(
        id="atom_own",
        text="Normative claim",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_a2",
        entity_ids=["ent_single__sense_2"],
    )
    atom_partner = TheoryAtom(
        id="atom_partner",
        text="Physical partner claim",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk_a1",
        entity_ids=["ent_single__sense_1"],
    )
    direct_state = EpistemicStateView(
        chunks=[
            L1Chunk(id="chunk_a1", source_doc_id="doc_a", sequence_index=0, token_count=3, text="Physical"),
            L1Chunk(id="chunk_a2", source_doc_id="doc_a", sequence_index=1, token_count=3, text="Normative"),
        ],
        entities=[single_sense_ent],
        theory_atoms=[atom_own, atom_partner],
    )
    cross_deficit = EpistemicDeficit(
        deficit_id="polysemy_collision::entity::ent_single__sense_2",
        deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
        severity=0.9,
        target_entity_ids=["ent_single__sense_2"],
        target_chunk_ids=["chunk_a1", "chunk_a2"],
        target_atom_ids=["atom_own", "atom_partner"],
    )
    direct_delta = await ConceptionConceptSplitter(schema=DEFAULT_SCHEMA).split_concept(
        cross_deficit, direct_state
    )
    assert direct_delta.is_empty


@pytest.mark.asyncio
async def test_refinement_failure_emits_run_failed_and_persists_manifest(
    tmp_path: Path,
) -> None:
    """Verify errors inside refinement mark RunManifest FAILED and emit RunFailed."""
    cfg = _make_config(tmp_path, max_cycles=1, project_to_graph=False)
    events: list[Any] = []
    emitter = SimpleEventEmitter()
    emitter.register_observer(_ListObserver(events))

    class _ExplodingDetector:
        def fingerprint(self) -> dict[str, Any]:
            return {"class": "_ExplodingDetector"}

        def detect_deficits(
            self,
            state: EpistemicStateView,
            *,
            refinement_pass: int = 0,
            config: HermeneuticRefinementConfig | None = None,
            context: ArtifactExecutionContext | None = None,
        ) -> list[EpistemicDeficit]:
            raise RuntimeError("boom during top-down scan")

    pipeline = Pipeline(
        phases=_build_two_subgraph_forward_phases(),
        config=cfg,
        event_emitter=emitter,
        refinement_coordinator=ClosedLoopRefinementCoordinator(
            detector=_ExplodingDetector(),
            config=cfg.refinement,
        ),
    )
    with pytest.raises(RuntimeError, match="boom during top-down scan"):
        await pipeline.run(PipelineInput(source_paths=[]), run_id="run_fail_ref")

    persisted_manifest = pipeline.manifest_store.read_manifest("run_fail_ref")
    assert persisted_manifest is not None
    assert persisted_manifest.status == RunStatus.FAILED
    assert any(isinstance(ev, RunFailed) for ev in events)


# ---------------------------------------------------------------------------
# 5. Composition Root Wiring (Pipeline.for_task & PipelineFactory)
# ---------------------------------------------------------------------------


def test_pipeline_factory_and_for_task_wiring(tmp_path: Path) -> None:
    """Verify ``Pipeline.for_task`` and standalone ``Pipeline`` wire refinement cleanly."""
    cfg_on = _make_config(tmp_path / "on", max_cycles=2, project_to_graph=False)
    cfg_on.theoretical_enrichment = TheoreticalEnrichmentConfig(enabled=True)

    llm = _StubStructuredLLM()
    embedder = _StubEmbeddingModel()
    reranker = _StubReranker()

    pipe = Pipeline.for_task(
        llm=llm,
        embedding_model=embedder,
        relation_reranker=reranker,
        config=cfg_on,
    )
    assert isinstance(pipe.refinement_coordinator, ClosedLoopRefinementCoordinator)
    assert isinstance(pipe.refinement_coordinator.detector, TheoryNetDeficitDetector)
    assert isinstance(
        pipe.refinement_coordinator.premise_recoverer,
        LLMTheoryGuidedPremiseRecoverer,
    )
    assert isinstance(
        pipe.refinement_coordinator.concept_splitter,
        ConceptionConceptSplitter,
    )
    assert isinstance(
        pipe.refinement_coordinator.axiom_grounder,
        TheoryGuidedAxiomGrounder,
    )
    assert isinstance(
        pipe.refinement_coordinator.theorynet_projector,
        TheoryNetProjector,
    )
    # Shared TheoreticalEnrichmentRunner instance across forward workflow and coordinator
    enrichment_phases = [
        p for p in pipe.phases if isinstance(p, TheoreticalEnrichmentRunner)
    ]
    assert len(enrichment_phases) == 1
    assert pipe.refinement_coordinator.enrichment_runner is enrichment_phases[0]

    # Standalone Pipeline auto-wires deterministic coordinator when max_refinement_cycles > 0
    standalone = Pipeline(
        phases=_build_two_subgraph_forward_phases(),
        config=_make_config(tmp_path / "standalone", max_cycles=1, project_to_graph=False),
    )
    assert isinstance(standalone.refinement_coordinator, ClosedLoopRefinementCoordinator)

    # Disabled refinement leaves coordinator unset on factory resolution
    cfg_off = _make_config(tmp_path / "off", max_cycles=0, project_to_graph=False)
    pipe_off = Pipeline.for_task(
        llm=llm,
        embedding_model=embedder,
        relation_reranker=reranker,
        config=cfg_off,
    )
    assert pipe_off.refinement_coordinator is None

    # Invalid protocol overrides fail loudly at composition root
    with pytest.raises(TypeError, match="HermeneuticRefinementCoordinator"):
        Pipeline.for_task(
            llm=llm,
            embedding_model=embedder,
            relation_reranker=reranker,
            config=cfg_on,
            refinement_coordinator="invalid-coord",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="EpistemicDeficitDetector"):
        Pipeline.for_task(
            llm=llm,
            embedding_model=embedder,
            relation_reranker=reranker,
            config=cfg_on,
            deficit_detector="invalid-detector",  # type: ignore[arg-type]
        )

    # PipelineFactory.fingerprint responds only when refinement is enabled
    fp_off = PipelineFactory(cfg_off).fingerprint()
    fp_on = PipelineFactory(cfg_on).fingerprint()
    assert "refinement" not in fp_off
    assert "refinement" in fp_on


# ---------------------------------------------------------------------------
# 6. Static AST & Documentation Audit Guards
# ---------------------------------------------------------------------------


def test_step_3b_files_have_no_getattr_or_hasattr_and_have_docstrings() -> None:
    """Enforce zero ``getattr``/``hasattr`` and module/class/method docstrings on Step 3b files."""
    target_paths = [
        PACKAGE_ROOT / "artifacts" / "subgraph_reader.py",
        PACKAGE_ROOT / "refinement" / "concept_splitter.py",
        PACKAGE_ROOT / "refinement" / "coordinator.py",
        PACKAGE_ROOT / "refinement" / "detector.py",
        PACKAGE_ROOT / "refinement" / "__init__.py",
        PACKAGE_ROOT / "runtime" / "execution_engine.py",
        PACKAGE_ROOT / "runtime" / "pipeline_factory.py",
        PACKAGE_ROOT / "pipeline.py",
    ]
    for path in target_paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        assert ast.get_docstring(tree), f"Missing module docstring in {path}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("getattr", "hasattr"), (
                    f"Forbidden reflection call {node.func.id!r} found in "
                    f"{path}:{node.lineno}"
                )
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                if path.name == "coordinator.py" and not node.name.startswith("_"):
                    assert ast.get_docstring(node), (
                        f"Missing docstring on {path.name}:{node.name}"
                    )
