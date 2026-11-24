"""Artifact-native workflow execution engine (ISSUE-058).

Executes a declarative :class:`~episteme_pipeline.runtime.workflow_dag.WorkflowDAG`
with manifest fingerprinting, DAG-based cache invalidation and artifact hydration
(ISSUE-048), inter-phase epistemic quality gate evaluation (ISSUE-058), batched
graph projection (ISSUE-046), and symmetric lifecycle event emission (ISSUE-052).
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel

from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    EpistemicStateView,
)
from episteme_pipeline.artifacts.invalidate import (
    ArtifactDependencyGraph,
    build_prior_fingerprints,
)
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.events import (
    ComponentCompleted,
    ComponentStarted,
    ContextualEventEmitter,
    EventEmitter,
    NoOpEventEmitter,
    PhaseCompleted,
    PhaseFailed,
    PhaseReused,
    QualityGateEvaluated,
    ResettableTelemetry,
    RunCompleted,
    RunFailed,
    RunStarted,
    use_event_emitter,
)
from episteme_pipeline.observability.logging import run_folder_logger
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fingerprint import find_components
from episteme_pipeline.protocols.graph_store import PhaseCheckpointStore
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.protocols.quality_gate import (
    QualityGateResult,
    QualityGateViolationError,
    QualityGateWarning,
)
from episteme_pipeline.protocols.refinement import (
    HermeneuticRefinementCoordinator,
    ensure_refinement_coordinator,
)
from episteme_pipeline.runs.fingerprints import (
    compute_document_fingerprints,
    fingerprint_curation_ledger,
    fingerprint_existing_sources,
    fingerprint_method,
    fingerprint_phase_config,
    fingerprint_structural_anchor,
    stable_fingerprint,
)
from episteme_pipeline.runs.models import (
    ArtifactReportEntry,
    ExecutionResult,
    InvalidationDecision,
    ResumePoint,
    RunManifest,
    RunPhaseRecord,
    RunReport,
    RunStatus,
)
from episteme_pipeline.runs.persistence import JsonRunManifestStore
from episteme_pipeline.runtime.workflow_dag import WorkflowDAG, WorkflowNode

logger = logging.getLogger(__name__)


def _artifact_kind_str(kind: Any) -> str:
    """Format an artifact kind value safely without reflection.

    Parameters
    ----------
    kind : Any
        Enum member or string representation of artifact kind.

    Returns
    -------
    str
        Normalized string name of the artifact kind.
    """
    if isinstance(kind, Enum):
        return str(kind.value)
    return str(kind)


class ArtifactExecutionEngine:
    """Runtime execution engine for a :class:`WorkflowDAG`.

    Encapsulates manifest persistence, artifact storage, DAG-based cache
    invalidation, artifact hydration across parent-run chains, inter-phase
    :class:`~episteme_pipeline.protocols.quality_gate.EpistemicQualityGate`
    circuit breaking, batched graph projection, and symmetric event emission.

    Parameters
    ----------
    workflow : WorkflowDAG
        Declarative workflow topology and bound quality gates.
    config : PipelineConfig
        Pipeline configuration.
    projection_graph : Any, optional
        Target graph store for artifact projection.
    checkpoint_store : Any, optional
        Within-phase checkpoint store.
    event_emitter : EventEmitter or None, optional
        Domain event emitter.
    decision_engine : DecisionEngine or None, optional
        Optional System 1 decision engine for fingerprinting.
    manifest_store : JsonRunManifestStore or None, optional
        Optional pre-constructed run manifest store.
    artifact_store : JsonArtifactStore or None, optional
        Optional pre-constructed artifact store.
    projector : ArtifactGraphProjector or None, optional
        Optional pre-constructed artifact graph projector.
    refinement_coordinator : HermeneuticRefinementCoordinator or None, optional
        Optional bounded top-down refinement coordinator invoked after the
        forward DAG completes when ``config.refinement.max_refinement_cycles > 0``.
    """

    def __init__(
        self,
        *,
        workflow: WorkflowDAG,
        config: PipelineConfig,
        projection_graph: Any = None,
        checkpoint_store: Any = None,
        event_emitter: EventEmitter | None = None,
        decision_engine: DecisionEngine | None = None,
        manifest_store: JsonRunManifestStore | None = None,
        artifact_store: JsonArtifactStore | None = None,
        projector: ArtifactGraphProjector | None = None,
        refinement_coordinator: HermeneuticRefinementCoordinator | None = None,
    ) -> None:
        self.workflow = workflow
        self.config = config
        self.projection_graph = projection_graph
        if checkpoint_store is None:
            checkpoint_store = FileSystemCheckpointStore(
                Path(self.config.execution.artifacts_dir) / "_checkpoints"
            )
        self.checkpoint_store = checkpoint_store
        self.event_emitter: EventEmitter = event_emitter or NoOpEventEmitter()
        self.decision_engine = decision_engine
        self.manifest_store = manifest_store or JsonRunManifestStore(
            self.config.execution.runs_dir
        )
        self.artifact_store = artifact_store or JsonArtifactStore(
            self.config.execution.artifacts_dir
        )
        self.projector = projector or ArtifactGraphProjector(
            projection_graph,
            schema=config.graph_schema,
            t_norm=config.phase6.conjunctive_t_norm,
        )
        self.refinement_coordinator: HermeneuticRefinementCoordinator | None = (
            ensure_refinement_coordinator(refinement_coordinator)
        )

    def _is_refinement_active(self) -> bool:
        """Return whether closed-loop hermeneutic refinement is active.

        Returns
        -------
        bool
            ``True`` when a refinement coordinator is configured and
            ``config.refinement.max_refinement_cycles > 0``.
        """
        return (
            self.refinement_coordinator is not None
            and self.config.refinement.max_refinement_cycles > 0
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic fingerprint dictionary for the execution engine.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of the execution engine and workflow.
        """
        payload: dict[str, Any] = {
            "class": self.__class__.__name__,
            "workflow": self.workflow.fingerprint(),
            "allow_phase_reuse": self.config.execution.allow_phase_reuse,
            "allow_artifact_hydration": self.config.execution.allow_artifact_hydration,
            "project_artifacts_to_graph": self.config.execution.project_artifacts_to_graph,
        }
        if self._is_refinement_active() and self.refinement_coordinator is not None:
            payload["max_refinement_cycles"] = (
                self.config.refinement.max_refinement_cycles
            )
            payload["refinement_coordinator"] = self.refinement_coordinator.fingerprint()
        return payload

    @contextmanager
    def run_observability_scope(self, run_id: str) -> Iterator[None]:
        """Establish contextual event emission and run-scoped folder logging.

        Parameters
        ----------
        run_id : str
            Unique execution run identifier.

        Yields
        ------
        None
            Yields execution context within active event emitter and logger contexts.
        """
        contextual_emitter = ContextualEventEmitter(
            self.event_emitter, defaults={"run_id": run_id}
        )
        with (
            use_event_emitter(contextual_emitter),
            run_folder_logger(self.config.execution.runs_dir, run_id),
        ):
            yield

    def prompt_fingerprints(
        self, nodes: Sequence[WorkflowNode] | None = None
    ) -> dict[str, dict[str, str]]:
        """Discover and fingerprint prompt bundles across all pipeline phases.

        Parameters
        ----------
        nodes : Sequence of WorkflowNode or None, optional
            Explicit phase nodes to inspect; defaults to ``self.workflow.nodes``.

        Returns
        -------
        dict of str to dict of str to str
            Mapping from ``phase_key`` to ``{prompt_name: fingerprint}``.
        """
        active_nodes = self.workflow.nodes if nodes is None else nodes
        fps: dict[str, dict[str, str]] = {}
        for phase_key, cfg in vars(self.config).items():
            if not isinstance(cfg, BaseModel):
                continue
            if (
                phase_key == "refinement"
                and self.config.refinement.max_refinement_cycles <= 0
            ):
                continue
            prompts: dict[str, str] = {}
            for comp_name, comp_obj in find_components(cfg).items():
                if isinstance(comp_obj, StructuredPromptBundle):
                    pname = comp_obj.name or comp_name.split(".")[-1].removesuffix("_prompts")
                    prompts[pname] = stable_fingerprint(comp_obj.fingerprint())
            if prompts:
                fps[phase_key] = prompts

        for entry in active_nodes:
            runner = entry.runner
            comps = (
                runner.components()
                if isinstance(runner, PhaseRunner)
                else find_components(runner)
            )
            runner_prompts: dict[str, str] = {}
            for comp_name, comp_obj in comps.items():
                if isinstance(comp_obj, StructuredPromptBundle):
                    pname = comp_obj.name or comp_name.split(".")[-1].removesuffix("_prompts")
                    runner_prompts[pname] = stable_fingerprint(comp_obj.fingerprint())
            if runner_prompts:
                fps.setdefault(entry.phase_key, {}).update(runner_prompts)

        return fps

    def method_fingerprints(
        self,
        nodes: Sequence[WorkflowNode] | None = None,
        prompt_fps: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, str]:
        """Compute method and component fingerprints across all workflow nodes.

        Parameters
        ----------
        nodes : Sequence of WorkflowNode or None, optional
            Explicit phase nodes to inspect; defaults to ``self.workflow.nodes``.
        prompt_fps : dict of str to dict of str to str or None, optional
            Pre-computed prompt fingerprints; computed via :meth:`prompt_fingerprints`
            when omitted.

        Returns
        -------
        dict of str to str
            Mapping of dotted component paths to deterministic SHA-256 fingerprints.
        """
        active_nodes = self.workflow.nodes if nodes is None else nodes
        fps: dict[str, str] = {}
        resolved_prompt_fps = (
            prompt_fps if prompt_fps is not None else self.prompt_fingerprints(active_nodes)
        )

        for entry in active_nodes:
            runner = entry.runner
            prefix = str(runner.name) if isinstance(runner, PhaseRunner) and runner.name else f"phase{entry.index}"

            comps = (
                runner.components()
                if isinstance(runner, PhaseRunner)
                else find_components(runner)
            )

            for comp_name, comp_obj in comps.items():
                fp = fingerprint_method(comp_obj)
                if fp:
                    fps[f"{prefix}.{comp_name}"] = fp
            for pname, pfp in resolved_prompt_fps.get(entry.phase_key, {}).items():
                fps[f"{prefix}.prompt.{pname}"] = pfp
            for gate in entry.quality_gates:
                gate_fp = fingerprint_method(gate)
                if gate_fp:
                    fps[f"{entry.phase_key}.quality_gate.{gate.name}"] = gate_fp

        if self.decision_engine is not None:
            engine_comps = find_components(self.decision_engine)
            for comp_name, comp_obj in engine_comps.items():
                fp = fingerprint_method(comp_obj)
                if fp:
                    fps[f"decision_engine.{comp_name}"] = fp
            engine_fp = fingerprint_method(self.decision_engine)
            if engine_fp:
                fps["decision_engine"] = engine_fp

        if self._is_refinement_active() and self.refinement_coordinator is not None:
            coord_comps = find_components(self.refinement_coordinator)
            for comp_name, comp_obj in coord_comps.items():
                fp = fingerprint_method(comp_obj)
                if fp:
                    fps[f"refinement.{comp_name}"] = fp
            coord_fp = fingerprint_method(self.refinement_coordinator)
            if coord_fp:
                fps["refinement"] = coord_fp

        return fps

    def phase_config(self, entry: WorkflowNode) -> BaseModel | None:
        """Resolve the configuration block for a workflow node from ``phase_key``.

        Parameters
        ----------
        entry : WorkflowNode
            Workflow node to resolve configuration for.

        Returns
        -------
        BaseModel or None
            Phase configuration model or None.
        """
        return self.config.get_phase_config(entry.phase_key)

    def phase_config_fingerprints(
        self, nodes: Sequence[WorkflowNode] | None = None
    ) -> dict[str, str]:
        """Compute configuration fingerprints keyed by semantic ``phase_key``.

        Parameters
        ----------
        nodes : Sequence of WorkflowNode or None, optional
            Explicit phase nodes to inspect; defaults to ``self.workflow.nodes``.

        Returns
        -------
        dict of str to str
            Mapping from ``phase_key`` to its deterministic configuration fingerprint.
        """
        active_nodes = self.workflow.nodes if nodes is None else nodes
        fps: dict[str, str] = {}
        for entry in active_nodes:
            runner_fp = (
                entry.runner.config_fingerprint()
                if isinstance(entry.runner, PhaseRunner)
                else None
            )
            if runner_fp is not None:
                fps[entry.phase_key] = runner_fp
            else:
                cfg = self.phase_config(entry)
                if cfg is not None:
                    fps[entry.phase_key] = fingerprint_phase_config(cfg)
        if nodes is None and self._is_refinement_active():
            fps["refinement"] = fingerprint_phase_config(self.config.refinement)
        return fps

    def phase_dependencies(self) -> dict[str, set[str]]:
        """Compute direct upstream phase dependencies from the workflow DAG.

        Returns
        -------
        dict of str to set of str
            Mapping of ``phase_key`` to upstream ``phase_key`` dependencies.
        """
        return self.workflow.dependencies()

    def build_manifest(
        self,
        *,
        run_id: str,
        pipeline_input: PipelineInput,
        method_fps: dict[str, str] | None = None,
        phase_cfg_fps: dict[str, str] | None = None,
    ) -> RunManifest:
        """Assemble a :class:`RunManifest` with fingerprints and config snapshot.

        Parameters
        ----------
        run_id : str
            Unique run identifier.
        pipeline_input : PipelineInput
            Input contract for the run.
        method_fps : dict of str to str or None, optional
            Optional pre-computed method fingerprints.
        phase_cfg_fps : dict of str to str or None, optional
            Optional pre-computed phase configuration fingerprints.

        Returns
        -------
        RunManifest
            Constructed run manifest initialized with ``RunStatus.RUNNING``.
        """
        resolved_method_fps = (
            method_fps if method_fps is not None else self.method_fingerprints()
        )
        resolved_phase_cfg_fps = (
            phase_cfg_fps
            if phase_cfg_fps is not None
            else self.phase_config_fingerprints()
        )
        source_fp = fingerprint_existing_sources(
            [str(p) for p in pipeline_input.source_paths],
            [str(p) for p in pipeline_input.bib_paths],
        )
        doc_fps = compute_document_fingerprints(
            [str(p) for p in pipeline_input.source_paths]
        )
        anchor_fp = fingerprint_structural_anchor(pipeline_input.structural_anchor)
        ledger = pipeline_input.resolved_curation_ledger()
        ledger_fp = fingerprint_curation_ledger(ledger)
        fp_payload: dict[str, Any] = {"source": source_fp}
        if anchor_fp is not None:
            fp_payload["anchor"] = anchor_fp
        if ledger_fp is not None:
            fp_payload["ledger"] = ledger_fp
        input_fp = (
            stable_fingerprint(fp_payload) if len(fp_payload) > 1 else source_fp
        )
        cfg_snapshot = self.config.model_dump(mode="json")
        anchor_dump = (
            pipeline_input.structural_anchor.model_dump(mode="json")
            if pipeline_input.structural_anchor
            else None
        )

        return RunManifest(
            run_id=run_id,
            status=RunStatus.RUNNING,
            schema_version=self.config.graph_schema.version,
            source_fingerprint=source_fp,
            document_fingerprints=doc_fps,
            curation_ledger_fingerprint=ledger_fp,
            input_fingerprint=input_fp,
            input_fingerprint_inputs={
                "source_paths": list(pipeline_input.source_paths),
                "bib_paths": list(pipeline_input.bib_paths),
                "metadata": dict(pipeline_input.metadata),
                "structural_anchor": anchor_dump,
                "source_fingerprint": source_fp,
                "structural_anchor_fingerprint": anchor_fp,
                "document_fingerprints": doc_fps,
                "curation_ledger_fingerprint": ledger_fp,
            },
            config_snapshot=cfg_snapshot,
            phase_config_fingerprints=dict(resolved_phase_cfg_fps),
            method_fingerprints=resolved_method_fps,
            input_sources=list(pipeline_input.source_paths),
            phase_records=[
                RunPhaseRecord(
                    phase_name=entry.runner.name,
                    ordinal=entry.index,
                    phase_key=entry.phase_key,
                )
                for entry in self.workflow.nodes
            ],
        )

    async def choose_reuse_source(
        self, current: RunManifest
    ) -> InvalidationDecision:
        """Decide which phases can be reused from the most recent completed run.

        Evaluates reuse along the :class:`WorkflowDAG` dependency graph: a phase
        can be reused if its configuration, method fingerprints, and inputs did
        not change, and all its upstream dependencies in the DAG were also reused.

        Parameters
        ----------
        current : RunManifest
            Current run manifest containing fingerprints for this run.

        Returns
        -------
        InvalidationDecision
            Decision detailing reused and invalidated phase ordinals with reason.
        """
        if not self.config.execution.allow_phase_reuse:
            return InvalidationDecision(
                resume_point=ResumePoint(run_id=None),
                reused_phase_ordinals=[],
                invalidated_phase_ordinals=[e.index for e in self.workflow.nodes],
                reason="no-prior-or-reuse-disabled",
            )

        prior: RunManifest | None = None
        if current.parent_run_id:
            prior = self.manifest_store.read_manifest(current.parent_run_id)
        if prior is None:
            prior = self.manifest_store.latest_manifest()

        if not prior:
            return InvalidationDecision(
                resume_point=ResumePoint(run_id=None),
                reused_phase_ordinals=[],
                invalidated_phase_ordinals=[e.index for e in self.workflow.nodes],
                reason="no-prior-or-reuse-disabled",
            )
        resume_point = ResumePoint(run_id=prior.run_id)

        de_keys = {
            k
            for k in (
                set(current.method_fingerprints) | set(prior.method_fingerprints)
            )
            if k == "decision_engine" or k.startswith("decision_engine.")
        }
        pipeline_wide_invalidation: str | None = None
        if any(
            prior.method_fingerprints.get(k) != current.method_fingerprints.get(k)
            for k in de_keys
        ):
            pipeline_wide_invalidation = "method-changed:decision_engine"

        input_changed = prior.input_fingerprint != current.input_fingerprint
        input_reason: str | None = None
        if input_changed:
            if (
                prior.curation_ledger_fingerprint
                != current.curation_ledger_fingerprint
                and prior.source_fingerprint == current.source_fingerprint
            ):
                input_reason = "curation-ledger-changed"
            elif prior.document_fingerprints and all(
                current.document_fingerprints.get(k) == v
                for k, v in prior.document_fingerprints.items()
            ):
                input_reason = "source-changed:incremental"
            else:
                input_reason = "source-changed"

        prior_by_key: dict[str, RunPhaseRecord] = {
            rec.phase_key: rec for rec in prior.phase_records if rec.phase_key
        }
        prior_by_name: dict[str, RunPhaseRecord] = {
            rec.phase_name: rec for rec in prior.phase_records
        }

        deps = self.phase_dependencies()
        all_method_keys = set(current.method_fingerprints) | set(
            prior.method_fingerprints
        )

        reused_keys: set[str] = set()
        invalidated_keys: set[str] = set()
        invalidation_reasons: dict[str, str] = {}

        for entry in self.workflow.topological_order():
            key = entry.phase_key

            if pipeline_wide_invalidation:
                invalidated_keys.add(key)
                invalidation_reasons[key] = pipeline_wide_invalidation
                continue

            if not deps[key] and input_changed:
                invalidated_keys.add(key)
                invalidation_reasons[key] = input_reason or "source-changed"
                continue

            upstream_invalid = [up for up in deps[key] if up in invalidated_keys]
            if upstream_invalid:
                invalidated_keys.add(key)
                invalidation_reasons[key] = (
                    f"upstream-invalidated:{upstream_invalid[0]}"
                )
                continue

            prior_rec = prior_by_key.get(key) or prior_by_name.get(entry.name)
            if prior_rec is None:
                invalidated_keys.add(key)
                invalidation_reasons[key] = f"phase-not-in-prior:{entry.name}"
                continue
            if prior_rec.status != RunStatus.COMPLETED:
                invalidated_keys.add(key)
                invalidation_reasons[key] = f"prior-phase-incomplete:{entry.name}"
                continue

            if prior.phase_config_fingerprints.get(
                key
            ) != current.phase_config_fingerprints.get(key):
                invalidated_keys.add(key)
                invalidation_reasons[key] = f"config-changed:{entry.name}"
                continue

            method_keys = [
                k
                for k in all_method_keys
                if k.startswith((f"{entry.name}.", f"{key}."))
            ]
            if any(
                prior.method_fingerprints.get(k)
                != current.method_fingerprints.get(k)
                for k in method_keys
            ):
                invalidated_keys.add(key)
                invalidation_reasons[key] = f"method-changed:{entry.name}"
                continue

            reused_keys.add(key)

        reused = [
            e.index for e in self.workflow.nodes if e.phase_key in reused_keys
        ]
        invalidated = [
            e.index for e in self.workflow.nodes if e.phase_key in invalidated_keys
        ]

        if not invalidated:
            reason = "all-reused"
        else:
            first_invalid_key = next(
                e.phase_key
                for e in self.workflow.nodes
                if e.phase_key in invalidated_keys
            )
            reason = invalidation_reasons.get(first_invalid_key, "invalidated")

        return InvalidationDecision(
            resume_point=resume_point,
            reused_phase_ordinals=reused,
            invalidated_phase_ordinals=invalidated,
            reason=reason,
        )

    async def hydrate_previous_collection(
        self,
        phase_number: int = 1,
        source_run_id: str | None = None,
        wanted_phase_names: set[str] | None = None,
    ) -> ArtifactCollection | None:
        """Rebuild the artifact collection expected by ``phase_number``.

        Walks the parent-run chain nearest-first so reused artifacts from
        ancestor runs are recovered without re-persisting them on every hop.

        Parameters
        ----------
        phase_number : int, default 1
            The 1-based index of the phase to hydrate up to.
        source_run_id : str or None, optional
            Specific run ID to hydrate artifacts from; defaults to latest run.
        wanted_phase_names : set of str or None, optional
            Explicit set of phase names to hydrate. If None, defaults to all
            phases strictly preceding ``phase_number``.

        Returns
        -------
        ArtifactCollection or None
            Hydrated artifact collection, or None if no matching artifacts exist.
        """
        if phase_number <= 1 and wanted_phase_names is None:
            return None
        run_id = source_run_id
        if run_id is None:
            latest = self.manifest_store.latest_manifest()
            if latest is None:
                return None
            run_id = latest.run_id

        if wanted_phase_names is None:
            wanted_phase_names = {
                self.workflow.nodes[idx - 1].name for idx in range(1, phase_number)
            }
        chain_artifacts = await self._collect_parent_chain_artifacts(run_id)
        source_manifest = self.manifest_store.read_manifest(run_id)
        all_artifacts = self._dedup_chain_artifacts(
            chain_artifacts,
            allowed_phase_names=wanted_phase_names,
            phase_order=self._phase_order_map(source_manifest),
            preserve_per_phase=True,
        )
        if not all_artifacts:
            return None
        return ArtifactCollection(all_artifacts)

    def evaluate_phase_quality_gates(
        self,
        *,
        entry: WorkflowNode,
        phase_collection: ArtifactCollection,
        cumulative_collection: ArtifactCollection,
        context: ArtifactExecutionContext,
        record: RunPhaseRecord | None = None,
        phase_emitter: EventEmitter | None = None,
    ) -> list[QualityGateResult]:
        """Evaluate all :class:`EpistemicQualityGate` hooks bound to ``entry.phase_key``.

        Parameters
        ----------
        entry : WorkflowNode
            Completed workflow phase node.
        phase_collection : ArtifactCollection
            Artifacts produced by the completed phase.
        cumulative_collection : ArtifactCollection
            Cumulative artifacts across all completed/hydrated phases up to ``entry``.
        context : ArtifactExecutionContext
            Active execution context.
        record : RunPhaseRecord or None, optional
            Phase manifest record to annotate with gate evaluation summaries.
        phase_emitter : EventEmitter or None, optional
            Contextual phase emitter used to publish ``QualityGateEvaluated``
            for custom gates that do not emit the event themselves.

        Returns
        -------
        list of QualityGateResult
            Evaluation outcomes for all gates attached to ``entry.phase_key``.

        Raises
        ------
        QualityGateViolationError
            If any gate fails with ``severity == "halt"``.
        """
        gates = self.workflow.gates_for_phase(entry.phase_key)
        if not gates:
            return []

        results: list[QualityGateResult] = []
        for gate in gates:
            try:
                gate_result = gate.evaluate(
                    entry.phase_key,
                    phase_collection,
                    cumulative_collection,
                    context,
                )
            except QualityGateViolationError as qg_exc:
                if record is not None:
                    record.notes[f"quality_gate.{qg_exc.result.gate_name}"] = (
                        qg_exc.result.message
                    )
                if phase_emitter is not None:
                    phase_emitter.emit(
                        QualityGateEvaluated(
                            gate_name=qg_exc.result.gate_name,
                            phase_key=qg_exc.result.phase_key,
                            passed=False,
                            severity=qg_exc.result.severity,
                            metrics=dict(qg_exc.result.metrics),
                            message=qg_exc.result.message,
                            phase=entry.name,
                            run_id=context.run_id,
                        )
                    )
                raise

            if record is not None:
                record.notes[f"quality_gate.{gate_result.gate_name}"] = (
                    gate_result.message
                )
            if phase_emitter is not None:
                phase_emitter.emit(
                    QualityGateEvaluated(
                        gate_name=gate_result.gate_name,
                        phase_key=gate_result.phase_key,
                        passed=gate_result.passed,
                        severity=gate_result.severity,
                        metrics=dict(gate_result.metrics),
                        message=gate_result.message,
                        phase=entry.name,
                        run_id=context.run_id,
                    )
                )
            if not gate_result.passed:
                if gate_result.severity == "halt":
                    raise QualityGateViolationError(gate_result)
                warnings.warn(
                    gate_result.message,
                    QualityGateWarning,
                    stacklevel=2,
                )
            results.append(gate_result)

        return results

    async def execute(
        self,
        *,
        run_id: str,
        manifest: RunManifest,
        start_index: int,
        pipeline_input: PipelineInput,
        initial_previous_collection: ArtifactCollection | None,
        invalidation_decision: InvalidationDecision,
    ) -> ExecutionResult:
        """Execute workflow phases from ``start_index`` with quality gates and telemetry.

        Parameters
        ----------
        run_id : str
            Unique execution run identifier.
        manifest : RunManifest
            Run manifest tracking phase records and status.
        start_index : int
            1-based phase ordinal to start execution from.
        pipeline_input : PipelineInput
            Input contract for the run.
        initial_previous_collection : ArtifactCollection or None
            Hydrated upstream artifacts from reused phases.
        invalidation_decision : InvalidationDecision
            Cache reuse and invalidation decision.

        Returns
        -------
        ExecutionResult
            Final manifest and run report.
        """
        if isinstance(self.event_emitter, ResettableTelemetry):
            self.event_emitter.reset_observer_telemetry()

        if self.config.execution.persist_run_manifests:
            self.manifest_store.write_manifest(manifest)

        report = RunReport(
            manifest=manifest,
            run_id=manifest.run_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            phase_records=manifest.phase_records,
            reused_phase_ordinals=list(invalidation_decision.reused_phase_ordinals),
            invalidated_phase_ordinals=list(
                invalidation_decision.invalidated_phase_ordinals
            ),
            invalidation_reason=invalidation_decision.reason,
        )

        self.event_emitter.emit(
            RunStarted(
                run_id=run_id,
                parent_run_id=invalidation_decision.resume_point.run_id,
                reused_phase_ordinals=list(
                    invalidation_decision.reused_phase_ordinals
                ),
                invalidated_phase_ordinals=list(
                    invalidation_decision.invalidated_phase_ordinals
                ),
                invalidation_reason=invalidation_decision.reason,
            )
        )

        reused_records = self.reused_phase_records(invalidation_decision)
        reused_by_key: dict[str, RunPhaseRecord] = {
            r.phase_key: r for r in reused_records if r.phase_key
        }
        reused_by_name = {r.phase_name: r for r in reused_records}
        for rec in manifest.phase_records:
            prior_rec = (
                reused_by_key.get(rec.phase_key) if rec.phase_key else None
            ) or reused_by_name.get(rec.phase_name)
            if prior_rec is not None:
                rec.reused = True
                rec.status = prior_rec.status
                rec.started_at = prior_rec.started_at
                rec.completed_at = prior_rec.completed_at
                rec.artifact_ids = prior_rec.artifact_ids
                rec.input_artifact_ids = prior_rec.input_artifact_ids
                rec.output_artifact_ids = prior_rec.output_artifact_ids
                rec.output_fingerprint = prior_rec.output_fingerprint
                rec.config_fingerprint = prior_rec.config_fingerprint
                self.event_emitter.emit(
                    PhaseReused(
                        phase_name=rec.phase_name,
                        source_run_id=invalidation_decision.resume_point.run_id
                        or "",
                        artifact_count=len(prior_rec.artifact_ids or []),
                        run_id=run_id,
                        phase=rec.phase_name,
                    )
                )

        reused_entries = await self.reused_artifact_entries(invalidation_decision)
        report.artifact_entries.extend(reused_entries)
        for entry in reused_entries:
            self._increment_count(report.artifact_counts_by_kind, entry.kind)
            self._increment_count(
                report.artifact_counts_by_phase, entry.phase_name
            )
            self._increment_count(report.reused_artifact_counts_by_kind, entry.kind)
            self._increment_count(
                report.reused_artifact_counts_by_phase, entry.phase_name
            )

        previous = initial_previous_collection
        if (
            self.config.execution.project_artifacts_to_graph
            and initial_previous_collection is not None
            and initial_previous_collection.artifacts
        ):
            await self.projector.project_collection(
                initial_previous_collection, batch_size=500
            )

        records_by_ordinal = {
            rec.phase_ordinal: rec for rec in manifest.phase_records
        }

        can_load_prior = self.config.execution.allow_artifact_hydration and (
            self.config.execution.allow_phase_reuse
            or invalidation_decision.reason == "explicit-resume-boundary"
        )
        prior_run_id = (
            (invalidation_decision.resume_point.run_id or manifest.parent_run_id)
            if can_load_prior
            else None
        )
        prior_manifest: RunManifest | None = None
        prior_artifacts: ArtifactCollection | None = None
        if prior_run_id:
            prior_manifest = self.manifest_store.read_manifest(prior_run_id)
            raw_prior = await self.get_run_artifacts_raw(prior_run_id)
            if raw_prior:
                prior_artifacts = ArtifactCollection(raw_prior)

        ordered_nodes = self.workflow.topological_order()
        transitive_deps = self.workflow.transitive_dependencies()
        key_by_name = {node.name: node.phase_key for node in ordered_nodes}
        artifacts_by_key: dict[str, list[Any]] = {}
        untagged_initial_artifacts: list[Any] = []
        if initial_previous_collection is not None:
            for art in initial_previous_collection.artifacts:
                mapped_key = key_by_name.get(art.phase_name)
                if mapped_key is not None:
                    artifacts_by_key.setdefault(mapped_key, []).append(art)
                else:
                    untagged_initial_artifacts.append(art)

        for entry in ordered_nodes:
            ordinal = entry.index
            if ordinal < start_index:
                continue
            if ordinal in invalidation_decision.reused_phase_ordinals:
                continue
            phase_name = entry.name

            upstream_keys = transitive_deps.get(entry.phase_key, set())
            if upstream_keys:
                scoped_artifacts: list[Any] = list(untagged_initial_artifacts)
                for topo_node in ordered_nodes:
                    if (
                        topo_node.phase_key in upstream_keys
                        and topo_node.phase_key in artifacts_by_key
                    ):
                        scoped_artifacts.extend(
                            artifacts_by_key[topo_node.phase_key]
                        )
                branch_previous: ArtifactCollection | None = (
                    ArtifactCollection(scoped_artifacts)
                    if scoped_artifacts
                    else (
                        initial_previous_collection
                        if not artifacts_by_key
                        else None
                    )
                )
            else:
                branch_previous = (
                    initial_previous_collection
                    if ordinal > 1 and not artifacts_by_key
                    else None
                )

            upstream_artifact_ids = (
                [a.artifact_id for a in branch_previous.artifacts]
                if branch_previous is not None
                else []
            )
            phase_input = self.build_phase_input(
                entry=entry,
                pipeline_input=pipeline_input,
                previous=branch_previous,
            )

            lineage_fp = stable_fingerprint(
                {
                    "phase_key": entry.phase_key,
                    "input_fingerprint": manifest.input_fingerprint,
                    "config_fingerprint": manifest.phase_config_fingerprints.get(
                        entry.phase_key
                    ),
                    "method_fingerprints": {
                        k: v
                        for k, v in sorted(manifest.method_fingerprints.items())
                        if k.startswith(
                            (
                                f"{entry.name}.",
                                f"{entry.phase_key}.",
                                "decision_engine.",
                            )
                        )
                        or k == "decision_engine"
                    },
                    "upstream_fingerprint": (
                        self.fingerprint_collection(branch_previous)
                        if branch_previous is not None
                        else ""
                    ),
                }
            )

            context = ArtifactExecutionContext(
                run_id=run_id,
                manifest=manifest,
                pipeline_input=pipeline_input,
                previous=branch_previous,
                lineage_fingerprint=lineage_fp,
                prior_artifacts=prior_artifacts,
                prior_manifest=prior_manifest,
            )

            if (
                ordinal in invalidation_decision.invalidated_phase_ordinals
                and not (
                    invalidation_decision.reason
                    and invalidation_decision.reason.startswith(
                        "prior-phase-incomplete"
                    )
                )
            ):
                chk_store = (
                    entry.runner.checkpoint_store
                    if isinstance(entry.runner, PhaseRunner)
                    else None
                )
                if isinstance(chk_store, PhaseCheckpointStore):
                    await chk_store.clear_phase_checkpoints(entry.phase_key)
                    await chk_store.clear_phase_checkpoints(
                        f"{entry.phase_key}:{lineage_fp}"
                    )
                    if entry.phase_key == "phase4":
                        await chk_store.clear_phase_checkpoints("phase4_arc")
                        await chk_store.clear_phase_checkpoints(
                            f"phase4_arc:{lineage_fp}"
                        )

            record = records_by_ordinal.get(ordinal)
            if record is not None:
                record.status = RunStatus.RUNNING
                record.started_at = datetime.now(UTC)
                if isinstance(phase_input, EpistemicStateView):
                    record.input_artifact_ids = list(
                        phase_input.consumed_artifact_ids or upstream_artifact_ids
                    )
                elif entry.input_view is None:
                    record.input_artifact_ids = []
                else:
                    record.input_artifact_ids = list(upstream_artifact_ids)

            phase_emitter = ContextualEventEmitter(
                self.event_emitter,
                defaults={"run_id": run_id, "phase": phase_name},
            )
            phase_emitter.emit(
                ComponentStarted(
                    component_name=phase_name,
                    phase=phase_name,
                    run_id=run_id,
                )
            )
            if self.config.execution.persist_run_manifests:
                self.manifest_store.write_manifest(manifest)

            if isinstance(self.decision_engine, ObservableDecisionEngine):
                self.decision_engine.start_phase(entry.phase_key)

            try:
                with use_event_emitter(phase_emitter):
                    collection: ArtifactCollection = await entry.runner.run(
                        phase_input, context
                    )
                    cumulative_collection = (
                        collection
                        if branch_previous is None
                        else ArtifactCollection(
                            branch_previous.artifacts + collection.artifacts
                        )
                    )
                    self.evaluate_phase_quality_gates(
                        entry=entry,
                        phase_collection=collection,
                        cumulative_collection=cumulative_collection,
                        context=context,
                        record=record,
                        phase_emitter=phase_emitter,
                    )
                    if self.config.execution.should_persist_artifacts(
                        entry.phase_key
                    ):
                        for art in collection.artifacts:
                            await self.artifact_store.write_artifact(art)

                    if self.config.execution.project_artifacts_to_graph:
                        await self.projector.project_collection(
                            collection, batch_size=500
                        )
            except Exception as exc:
                logger.exception("Phase %s failed", phase_name)
                fail_time = datetime.now(UTC)
                duration_sec = (
                    (fail_time - record.started_at).total_seconds()
                    if record and record.started_at
                    else 0.0
                )
                if record is not None:
                    record.status = RunStatus.FAILED
                    record.completed_at = fail_time
                    record.notes["error"] = f"{type(exc).__name__}: {exc}"
                manifest.status = RunStatus.FAILED
                manifest.completed_at = fail_time
                report.status = RunStatus.FAILED
                report.completed_at = manifest.completed_at

                total_run_duration = (
                    (manifest.completed_at - report.started_at).total_seconds()
                    if report.started_at and manifest.completed_at
                    else duration_sec
                )

                phase_emitter.emit(
                    ComponentCompleted(
                        component_name=phase_name,
                        duration_seconds=duration_sec,
                        success=False,
                        error_message=str(exc),
                        phase=phase_name,
                        run_id=run_id,
                    )
                )
                phase_emitter.emit(
                    PhaseCompleted(
                        phase_name=phase_name,
                        duration_seconds=duration_sec,
                        artifact_count=0,
                        success=False,
                        error_message=str(exc),
                        phase=phase_name,
                        run_id=run_id,
                    )
                )
                phase_emitter.emit(
                    PhaseFailed(
                        phase_name=phase_name,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        duration_seconds=duration_sec,
                        phase=phase_name,
                        run_id=run_id,
                    )
                )
                self.event_emitter.emit(
                    RunFailed(
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        duration_seconds=total_run_duration,
                        run_id=run_id,
                    )
                )
                self.event_emitter.flush()
                report.observer_telemetry = (
                    self.event_emitter.get_observer_telemetry()
                )
                manifest.observer_telemetry = report.observer_telemetry
                if self.config.execution.persist_run_manifests:
                    self.manifest_store.write_manifest(manifest)
                raise

            produced_ids = [a.artifact_id for a in collection.artifacts]
            if record is not None:
                record.status = RunStatus.COMPLETED
                record.completed_at = datetime.now(UTC)
                record.artifact_ids = produced_ids
                record.output_artifact_ids = produced_ids
                record.config_fingerprint = cast(
                    str,
                    manifest.phase_config_fingerprints.get(entry.phase_key),
                )
                record.output_fingerprint = self.fingerprint_collection(collection)

            duration_sec = (
                (record.completed_at - record.started_at).total_seconds()
                if record and record.started_at and record.completed_at
                else 0.0
            )

            phase_emitter.emit(
                ComponentCompleted(
                    component_name=phase_name,
                    duration_seconds=duration_sec,
                    success=True,
                    phase=phase_name,
                    run_id=run_id,
                )
            )
            phase_emitter.emit(
                PhaseCompleted(
                    phase_name=phase_name,
                    duration_seconds=duration_sec,
                    artifact_count=len(produced_ids),
                    success=True,
                    phase=phase_name,
                    run_id=run_id,
                )
            )

            if self.config.execution.persist_run_manifests:
                self.manifest_store.write_manifest(manifest)

            self._record_new_artifacts_in_report(
                report,
                collection.artifacts,
                phase_name_override=phase_name,
            )

            artifacts_by_key[entry.phase_key] = list(collection.artifacts)
            previous = cumulative_collection

        if self._is_refinement_active() and self.refinement_coordinator is not None:
            forward_artifacts: list[Any] = list(untagged_initial_artifacts)
            for topo_node in ordered_nodes:
                if topo_node.phase_key in artifacts_by_key:
                    forward_artifacts.extend(artifacts_by_key[topo_node.phase_key])
            await self._run_refinement_stage(
                run_id=run_id,
                pipeline_input=pipeline_input,
                forward_collection=ArtifactCollection(forward_artifacts),
                manifest=manifest,
                report=report,
                prior_artifacts=prior_artifacts,
                prior_manifest=prior_manifest,
            )

        manifest.status = RunStatus.COMPLETED
        manifest.completed_at = datetime.now(UTC)
        report.status = RunStatus.COMPLETED
        report.completed_at = manifest.completed_at

        total_run_duration = (
            (manifest.completed_at - report.started_at).total_seconds()
            if report.started_at and manifest.completed_at
            else 0.0
        )
        total_artifacts = len(report.artifact_entries)

        self.event_emitter.emit(
            RunCompleted(
                duration_seconds=total_run_duration,
                total_artifacts=total_artifacts,
                run_id=run_id,
            )
        )
        self.event_emitter.flush()
        report.observer_telemetry = self.event_emitter.get_observer_telemetry()
        manifest.observer_telemetry = report.observer_telemetry

        if self.config.execution.persist_run_manifests:
            self.manifest_store.write_manifest(manifest)

        return ExecutionResult(manifest=manifest, report=report)

    def _record_new_artifacts_in_report(
        self,
        report: RunReport,
        artifacts: Sequence[Any],
        *,
        phase_name_override: str | None = None,
    ) -> None:
        """Append newly produced artifact entries and increment report counters.

        Parameters
        ----------
        report : RunReport
            Mutable run report being populated for the active execution.
        artifacts : Sequence of Any
            Newly emitted artifact envelopes to record.
        phase_name_override : str or None, optional
            Explicit phase label for phase counters when recording a single
            forward phase. When ``None``, uses each artifact's ``phase_name``.
        """
        for art in artifacts:
            kind_str = _artifact_kind_str(art.kind)
            entry_phase = phase_name_override or art.phase_name
            self._increment_count(report.artifact_counts_by_kind, kind_str)
            self._increment_count(report.artifact_counts_by_phase, entry_phase)
            self._increment_count(report.new_artifact_counts_by_kind, kind_str)
            self._increment_count(report.new_artifact_counts_by_phase, entry_phase)
            report.artifact_entries.append(
                ArtifactReportEntry(
                    artifact_id=art.artifact_id,
                    identity_key=art.identity_key or art.artifact_id,
                    kind=kind_str,
                    phase_name=art.phase_name,
                    run_id=art.run_id,
                    reused=False,
                )
            )

    async def _run_refinement_stage(
        self,
        *,
        run_id: str,
        pipeline_input: PipelineInput,
        forward_collection: ArtifactCollection,
        manifest: RunManifest,
        report: RunReport,
        prior_artifacts: ArtifactCollection | None,
        prior_manifest: RunManifest | None,
    ) -> ArtifactCollection:
        """Execute bounded hermeneutic refinement over ``forward_collection``.

        Parameters
        ----------
        run_id : str
            Active execution run identifier.
        pipeline_input : PipelineInput
            Pipeline input carrying sources, metadata, and curation ledger.
        forward_collection : ArtifactCollection
            Cumulative artifact collection produced by the forward workflow DAG.
        manifest : RunManifest
            Active run manifest updated with ``refinement_pass`` and phase records.
        report : RunReport
            Active run report updated with new delta artifacts and phase records.
        prior_artifacts : ArtifactCollection or None
            Optional prior-run artifact collection for resume lineage.
        prior_manifest : RunManifest or None
            Optional prior-run manifest for resume lineage.

        Returns
        -------
        ArtifactCollection
            Updated artifact collection returned by the refinement coordinator.
        """
        if self.refinement_coordinator is None:
            return forward_collection

        refine_lineage_fp = stable_fingerprint(
            {
                "phase_key": "refinement",
                "input_fingerprint": manifest.input_fingerprint,
                "config_fingerprint": manifest.phase_config_fingerprints.get(
                    "refinement"
                ),
                "method_fingerprints": {
                    k: v
                    for k, v in sorted(manifest.method_fingerprints.items())
                    if k == "refinement"
                    or k.startswith(("refinement.", "decision_engine."))
                    or k == "decision_engine"
                },
                "upstream_fingerprint": self.fingerprint_collection(
                    forward_collection
                ),
            }
        )

        if (
            self.config.execution.allow_phase_reuse
            and self.config.execution.allow_artifact_hydration
            and prior_manifest is not None
            and prior_manifest.status == RunStatus.COMPLETED
            and prior_manifest.refinement_lineage_fingerprint == refine_lineage_fp
            and prior_manifest.phase_config_fingerprints.get("refinement")
            == manifest.phase_config_fingerprints.get("refinement")
        ):
            prior_ref_records = [
                rec
                for rec in prior_manifest.phase_records
                if rec.phase_key == "refinement"
            ]
            if all(rec.status == RunStatus.COMPLETED for rec in prior_ref_records):
                reused_ref_artifacts: list[Any] = []
                ref_artifacts_complete = True
                if prior_ref_records:
                    ref_phase_names = {rec.phase_name for rec in prior_ref_records}
                    chain_artifacts = await self._collect_parent_chain_artifacts(
                        prior_manifest.run_id
                    )
                    reused_ref_artifacts = self._dedup_chain_artifacts(
                        chain_artifacts,
                        allowed_phase_names=ref_phase_names,
                        phase_order=self._phase_order_map(prior_manifest),
                        preserve_per_phase=True,
                    )
                    expected_ref_ids = {
                        aid
                        for rec in prior_ref_records
                        for aid in (rec.output_artifact_ids or rec.artifact_ids or [])
                    }
                    loaded_ref_ids = {
                        art.artifact_id for art in reused_ref_artifacts
                    }
                    ref_artifacts_complete = expected_ref_ids.issubset(
                        loaded_ref_ids
                    )

                if ref_artifacts_complete:
                    for rec in prior_ref_records:
                        copied_rec = rec.model_copy(update={"reused": True})
                        manifest.phase_records.append(copied_rec)
                        self.event_emitter.emit(
                            PhaseReused(
                                phase_name=copied_rec.phase_name,
                                source_run_id=prior_manifest.run_id,
                                artifact_count=len(copied_rec.artifact_ids or []),
                                run_id=run_id,
                                phase=copied_rec.phase_name,
                            )
                        )
                    manifest.refinement_pass = prior_manifest.refinement_pass
                    manifest.refinement_lineage_fingerprint = refine_lineage_fp
                    report.phase_records = list(manifest.phase_records)
                    report.manifest = manifest

                    for art in reused_ref_artifacts:
                        kind_str = _artifact_kind_str(art.kind)
                        self._increment_count(
                            report.artifact_counts_by_kind, kind_str
                        )
                        self._increment_count(
                            report.artifact_counts_by_phase, art.phase_name
                        )
                        self._increment_count(
                            report.reused_artifact_counts_by_kind, kind_str
                        )
                        self._increment_count(
                            report.reused_artifact_counts_by_phase, art.phase_name
                        )
                        report.artifact_entries.append(
                            ArtifactReportEntry(
                                artifact_id=art.artifact_id,
                                identity_key=art.identity_key or art.artifact_id,
                                kind=kind_str,
                                phase_name=art.phase_name,
                                run_id=art.run_id,
                                reused=True,
                            )
                        )

                    if (
                        self.config.execution.project_artifacts_to_graph
                        and reused_ref_artifacts
                    ):
                        latest_reused = list(
                            ArtifactCollection(
                                reused_ref_artifacts
                            ).latest_by_identity.values()
                        )
                        if latest_reused:
                            await self.projector.project_collection(
                                ArtifactCollection(latest_reused), batch_size=500
                            )

                    return ArtifactCollection(
                        forward_collection.history + reused_ref_artifacts
                    )

        refine_context = ArtifactExecutionContext(
            run_id=run_id,
            manifest=manifest,
            pipeline_input=pipeline_input,
            previous=forward_collection,
            lineage_fingerprint=refine_lineage_fp,
            prior_artifacts=prior_artifacts,
            prior_manifest=prior_manifest,
        )
        refinement_emitter = ContextualEventEmitter(
            self.event_emitter,
            defaults={"run_id": run_id, "phase": "Hermeneutic Refinement"},
        )
        try:
            with use_event_emitter(refinement_emitter):
                refined_collection = await self.refinement_coordinator.refine(
                    forward_collection,
                    refine_context,
                    config=self.config.refinement,
                )
                forward_ids = {
                    art.artifact_id for art in forward_collection.history
                }
                new_refinement_artifacts = [
                    art
                    for art in refined_collection.history
                    if art.artifact_id not in forward_ids
                ]
                if self.config.execution.should_persist_artifacts("refinement"):
                    for art in new_refinement_artifacts:
                        await self.artifact_store.write_artifact(art)

                latest_new_artifacts = [
                    art
                    for art in refined_collection.latest_by_identity.values()
                    if art.artifact_id not in forward_ids
                ]
                if (
                    self.config.execution.project_artifacts_to_graph
                    and latest_new_artifacts
                ):
                    await self.projector.project_collection(
                        ArtifactCollection(latest_new_artifacts), batch_size=500
                    )
        except Exception as exc:
            logger.exception("Hermeneutic refinement loop failed")
            fail_time = datetime.now(UTC)
            manifest.status = RunStatus.FAILED
            manifest.completed_at = fail_time
            report.status = RunStatus.FAILED
            report.completed_at = fail_time
            report.phase_records = list(manifest.phase_records)
            report.manifest = manifest
            total_run_duration = (
                (manifest.completed_at - report.started_at).total_seconds()
                if report.started_at and manifest.completed_at
                else 0.0
            )
            self.event_emitter.emit(
                RunFailed(
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    duration_seconds=total_run_duration,
                    run_id=run_id,
                )
            )
            self.event_emitter.flush()
            report.observer_telemetry = (
                self.event_emitter.get_observer_telemetry()
            )
            manifest.observer_telemetry = report.observer_telemetry
            if self.config.execution.persist_run_manifests:
                self.manifest_store.write_manifest(manifest)
            raise

        manifest.refinement_lineage_fingerprint = refine_lineage_fp
        for rec in manifest.phase_records:
            if rec.phase_key == "refinement" and rec.input_fingerprint is None:
                rec.input_fingerprint = refine_lineage_fp
        report.phase_records = list(manifest.phase_records)
        report.manifest = manifest

        self._record_new_artifacts_in_report(report, new_refinement_artifacts)
        return refined_collection

    async def run(
        self,
        input: PipelineInput,
        run_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> ExecutionResult:
        """Execute the workflow DAG with persisted-run caching semantics.

        Parameters
        ----------
        input : PipelineInput
            Pipeline input holding source documents, bib paths, and metadata.
        run_id : str or None, optional
            Explicit run identifier; generated as ``run-<uuid4>`` when None.
        parent_run_id : str or None, optional
            Optional parent run identifier to evaluate phase reuse against.

        Returns
        -------
        ExecutionResult
            Execution result containing the run manifest and report.
        """
        resolved_run_id = run_id or f"run-{uuid4()}"
        with self.run_observability_scope(resolved_run_id):
            manifest = self.build_manifest(
                run_id=resolved_run_id, pipeline_input=input
            )
            if parent_run_id:
                manifest.parent_run_id = parent_run_id
            decision = await self.choose_reuse_source(manifest)
            effective_start = (
                decision.invalidated_phase_ordinals[0]
                if decision.invalidated_phase_ordinals
                else len(self.workflow.nodes) + 1
            )
            allow_hydration = self.config.execution.allow_artifact_hydration
            wanted_phases = self.reused_phase_names(decision)
            previous_collection = (
                await self.hydrate_previous_collection(
                    effective_start,
                    source_run_id=decision.resume_point.run_id,
                    wanted_phase_names=wanted_phases,
                )
                if allow_hydration
                and decision.resume_point.run_id
                and wanted_phases
                else None
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = decision.resume_point.run_id
            return await self.execute(
                run_id=resolved_run_id,
                manifest=manifest,
                start_index=effective_start,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
            )

    async def run_from_phase(
        self,
        phase_number: int,
        input: PipelineInput | None = None,
        run_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> ExecutionResult:
        """Execute or resume the workflow starting from a specific phase boundary.

        Parameters
        ----------
        phase_number : int
            The 1-based ordinal of the phase runner to start or resume from.
        input : PipelineInput or None, optional
            Pipeline input; recovered from latest manifest when None.
        run_id : str or None, optional
            Explicit identifier for this execution run.
        parent_run_id : str or None, optional
            Optional identifier of parent run to fork or resume from.

        Returns
        -------
        ExecutionResult
            Execution result containing the run manifest and report.
        """
        valid_ordinals = {entry.index for entry in self.workflow.nodes}
        if phase_number not in valid_ordinals:
            raise ValueError(
                f"Invalid phase boundary {phase_number}. Valid boundaries: {self.workflow.phase_boundaries()}"
            )
        latest = (
            (
                self.manifest_store.read_manifest(parent_run_id)
                if parent_run_id
                else None
            )
            or self.manifest_store.latest_manifest()
            or self.manifest_store.latest_manifest(only_completed=False)
        )
        if input is None:
            if latest is None:
                raise ValueError(
                    "No previous run manifest found and no PipelineInput provided."
                )
            input = PipelineInput(
                source_paths=list(
                    latest.input_fingerprint_inputs.get("source_paths", [])
                ),
                bib_paths=list(
                    latest.input_fingerprint_inputs.get("bib_paths", [])
                ),
            )
        resolved_run_id = run_id or f"run-{uuid4()}"

        with self.run_observability_scope(resolved_run_id):
            manifest = self.build_manifest(
                run_id=resolved_run_id, pipeline_input=input
            )
            if parent_run_id:
                manifest.parent_run_id = parent_run_id
            decision = await self.choose_reuse_source(manifest)
            effective_start = phase_number
            if (
                phase_number in decision.reused_phase_ordinals
                and decision.invalidated_phase_ordinals
            ):
                effective_start = min(
                    phase_number, decision.invalidated_phase_ordinals[0]
                )

            forced_reused = [
                ord for ord in decision.reused_phase_ordinals if ord < phase_number
            ]
            forced_invalidated = sorted(
                set(decision.invalidated_phase_ordinals)
                | set(range(phase_number, len(self.workflow.nodes) + 1))
            )
            decision = InvalidationDecision(
                resume_point=decision.resume_point,
                reused_phase_ordinals=forced_reused,
                invalidated_phase_ordinals=forced_invalidated,
                reason=(
                    decision.reason
                    if forced_invalidated == decision.invalidated_phase_ordinals
                    else f"run-from-phase:{phase_number}"
                ),
            )
            allow_hydration = self.config.execution.allow_artifact_hydration
            wanted_phases = self.reused_phase_names(decision)
            previous_collection = (
                await self.hydrate_previous_collection(
                    effective_start,
                    source_run_id=decision.resume_point.run_id,
                    wanted_phase_names=wanted_phases,
                )
                if allow_hydration
                and decision.resume_point.run_id
                and wanted_phases
                else None
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = decision.resume_point.run_id
            return await self.execute(
                run_id=resolved_run_id,
                manifest=manifest,
                start_index=effective_start,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
            )

    async def resume_from_run(
        self,
        run_id: str,
        input: PipelineInput,
        from_phase: int | None = None,
    ) -> ExecutionResult:
        """Resume workflow execution from a prior run within observability context.

        Parameters
        ----------
        run_id : str
            Source run identifier to resume from.
        input : PipelineInput
            Pipeline input for the resumed execution.
        from_phase : int or None, optional
            1-based phase ordinal to resume from (defaults to 1).

        Returns
        -------
        ExecutionResult
            Execution result containing the run manifest and report.
        """
        target_run_id = f"run-resume-{run_id}"
        with self.run_observability_scope(target_run_id):
            manifest = self.build_manifest(
                run_id=target_run_id, pipeline_input=input
            )
            if from_phase is None:
                from_phase = 1
            decision = InvalidationDecision(
                resume_point=ResumePoint(run_id=run_id),
                reused_phase_ordinals=[i for i in range(1, from_phase)],
                invalidated_phase_ordinals=[
                    i for i in range(from_phase, len(self.workflow.nodes) + 1)
                ],
                reason="explicit-resume-boundary",
            )
            if decision.reused_phase_ordinals:
                manifest.parent_run_id = run_id
            previous_collection = await self.hydrate_previous_collection(
                from_phase, source_run_id=run_id
            )
            return await self.execute(
                run_id=target_run_id,
                manifest=manifest,
                start_index=from_phase,
                pipeline_input=input,
                initial_previous_collection=previous_collection,
                invalidation_decision=decision,
            )

    @staticmethod
    def fingerprint_collection(collection: ArtifactCollection) -> str:
        """Fingerprint a phase's output collection deterministically.

        Parameters
        ----------
        collection : ArtifactCollection
            Phase output artifact collection.

        Returns
        -------
        str
            Deterministic SHA-256 fingerprint of artifact identities and dependencies.
        """
        return stable_fingerprint(
            sorted(
                [
                    a.identity_key or a.artifact_id,
                    a.dependency_fingerprint or "",
                ]
                for a in collection.artifacts
            )
        )

    @staticmethod
    def build_phase_input(
        *,
        entry: WorkflowNode,
        pipeline_input: PipelineInput,
        previous: ArtifactCollection | None,
    ) -> Any:
        """Build the phase-specific input expected by ``entry.runner``.

        Parameters
        ----------
        entry : WorkflowNode
            Phase node to build input for.
        pipeline_input : PipelineInput
            Original pipeline invocation input.
        previous : ArtifactCollection or None
            Artifact collection accumulated by preceding phases.

        Returns
        -------
        Any
            Input payload or artifact view appropriate for the phase.
        """
        if entry.input_view is None:
            return pipeline_input
        return entry.input_view.from_collection(previous or ArtifactCollection([]))

    def reused_phase_names(self, decision: InvalidationDecision) -> set[str]:
        """Resolve names of phases reused under ``decision``.

        Parameters
        ----------
        decision : InvalidationDecision
            Cache invalidation decision.

        Returns
        -------
        set of str
            Set of reused phase display names.
        """
        reused = set(decision.reused_phase_ordinals)
        return {
            entry.name for entry in self.workflow.nodes if entry.index in reused
        }

    def reused_phase_records(
        self, decision: InvalidationDecision
    ) -> list[RunPhaseRecord]:
        """Retrieve phase records for reused phases from the source manifest.

        Parameters
        ----------
        decision : InvalidationDecision
            Cache invalidation decision.

        Returns
        -------
        list of RunPhaseRecord
            Copied phase records marked with ``reused=True``.
        """
        if not decision.resume_point.run_id or not decision.reused_phase_ordinals:
            return []
        source_manifest = self.manifest_store.read_manifest(
            decision.resume_point.run_id
        )
        if source_manifest is None:
            return []
        wanted = self.reused_phase_names(decision)
        return [
            record.model_copy(update={"reused": True})
            for record in source_manifest.phase_records
            if record.phase_name in wanted
        ]

    @staticmethod
    def _increment_count(
        bucket: dict[str, int], key: str, amount: int = 1
    ) -> None:
        """Increment a count in ``bucket`` by ``amount``."""
        bucket[key] = bucket.get(key, 0) + amount

    async def reused_artifact_entries(
        self, decision: InvalidationDecision
    ) -> list[ArtifactReportEntry]:
        """Build report entries for artifacts reused from a prior run.

        Parameters
        ----------
        decision : InvalidationDecision
            Cache invalidation decision.

        Returns
        -------
        list of ArtifactReportEntry
            Report entries for reused artifacts.
        """
        if not decision.resume_point.run_id or not decision.reused_phase_ordinals:
            return []

        source_manifest = self.manifest_store.read_manifest(
            decision.resume_point.run_id
        )
        if source_manifest is None:
            return []

        source_phase_names = {
            record.phase_name for record in source_manifest.phase_records
        }
        reused_phase_names = (
            self.reused_phase_names(decision) & source_phase_names
        )
        if not reused_phase_names:
            return []

        chain_artifacts = await self._collect_parent_chain_artifacts(
            decision.resume_point.run_id
        )
        artifacts = self._dedup_chain_artifacts(
            chain_artifacts,
            allowed_phase_names=reused_phase_names,
            phase_order=self._phase_order_map(source_manifest),
        )

        return [
            ArtifactReportEntry(
                artifact_id=artifact.artifact_id,
                identity_key=artifact.identity_key or artifact.artifact_id,
                kind=_artifact_kind_str(artifact.kind),
                phase_name=artifact.phase_name,
                run_id=artifact.run_id,
                reused=True,
            )
            for artifact in artifacts
        ]

    async def _collect_parent_chain_artifacts(self, run_id: str) -> list[Any]:
        """Load persisted artifact envelopes across ``run_id`` and its parent chain.

        Parameters
        ----------
        run_id : str
            Starting run identifier.

        Returns
        -------
        list of Any
            Raw artifact envelopes ordered from ``run_id`` outward through ancestors.
        """
        all_artifacts = list(await self.artifact_store.list_run_artifacts(run_id))
        visited_runs = {run_id}
        manifest = self.manifest_store.read_manifest(run_id)
        if manifest:
            current_parent = manifest.parent_run_id
            while current_parent and current_parent not in visited_runs:
                visited_runs.add(current_parent)
                all_artifacts.extend(
                    await self.artifact_store.list_run_artifacts(current_parent)
                )
                parent_manifest = self.manifest_store.read_manifest(
                    current_parent
                )
                if parent_manifest is None:
                    break
                current_parent = parent_manifest.parent_run_id
        return all_artifacts

    def _phase_order_map(
        self, manifest: RunManifest | None = None
    ) -> dict[str, int]:
        """Build a mapping from phase display name to workflow execution ordinal.

        Parameters
        ----------
        manifest : RunManifest or None, optional
            Optional run manifest supplying historical or refinement phase records.

        Returns
        -------
        dict of str to int
            Mapping from ``phase_name`` to 1-based execution ordinal.
        """
        order: dict[str, int] = {
            node.name: node.index for node in self.workflow.nodes
        }
        if manifest is not None:
            for rec in manifest.phase_records:
                order.setdefault(rec.phase_name, rec.phase_ordinal)
        return order

    @staticmethod
    def _dedup_chain_artifacts(
        chain_artifacts: Sequence[Any],
        *,
        allowed_phase_names: set[str] | None = None,
        phase_order: dict[str, int] | None = None,
        preserve_per_phase: bool = False,
    ) -> list[Any]:
        """Deduplicate parent-chain artifacts deterministically.

        Preserves child-run precedence over parent runs while preferring higher
        ``provenance.refinement_pass`` and later workflow ordinals when multiple
        forward versions exist within the same ``run_id``.

        Parameters
        ----------
        chain_artifacts : Sequence of Any
            Artifact envelopes collected from child to parent runs.
        allowed_phase_names : set of str or None, optional
            Optional phase-name filter applied prior to identity deduplication.
        phase_order : dict of str to int or None, optional
            Optional mapping from ``phase_name`` to workflow ordinal used to rank
            same-pass forward updates and order per-phase hydration output.
        preserve_per_phase : bool, default False
            When True, retains one latest envelope per ``(phase_name, identity_key)``
            sorted in topological phase and pass order so partial reuse preserves
            each reused phase's own artifacts.

        Returns
        -------
        list of Any
            Deduplicated artifact envelopes ordered deterministically.
        """
        if preserve_per_phase:
            per_phase_unique: dict[tuple[str, str], Any] = {}
            for art in chain_artifacts:
                if (
                    allowed_phase_names is not None
                    and art.phase_name not in allowed_phase_names
                ):
                    continue
                ident = art.identity_key or art.artifact_id
                dedup_key = (art.phase_name, ident)
                existing = per_phase_unique.get(dedup_key)
                if existing is None:
                    per_phase_unique[dedup_key] = art
                    continue
                if art.run_id == existing.run_id and (
                    art.provenance.refinement_pass,
                    art.artifact_id,
                ) > (
                    existing.provenance.refinement_pass,
                    existing.artifact_id,
                ):
                    per_phase_unique[dedup_key] = art
            return sorted(
                per_phase_unique.values(),
                key=lambda a: (
                    a.provenance.refinement_pass,
                    phase_order.get(a.phase_name, 10**9)
                    if phase_order is not None
                    else 0,
                    a.identity_key or a.artifact_id,
                    a.artifact_id,
                ),
            )

        unique_artifacts: dict[str, Any] = {}
        for art in chain_artifacts:
            if (
                allowed_phase_names is not None
                and art.phase_name not in allowed_phase_names
            ):
                continue
            key = art.identity_key or art.artifact_id
            existing = unique_artifacts.get(key)
            if existing is None:
                unique_artifacts[key] = art
                continue
            art_phase_rank = (
                phase_order.get(art.phase_name, -1)
                if phase_order is not None
                else 0
            )
            existing_phase_rank = (
                phase_order.get(existing.phase_name, -1)
                if phase_order is not None
                else 0
            )
            if art.run_id == existing.run_id and (
                art.provenance.refinement_pass,
                art_phase_rank,
                art.artifact_id,
            ) > (
                existing.provenance.refinement_pass,
                existing_phase_rank,
                existing.artifact_id,
            ):
                unique_artifacts[key] = art
        return [unique_artifacts[key] for key in sorted(unique_artifacts)]

    async def get_run_artifacts_raw(self, run_id: str) -> list[Any]:
        """Retrieve all artifacts visible from ``run_id``, walking parent-run chains.

        Parameters
        ----------
        run_id : str
            Starting run identifier.

        Returns
        -------
        list of Any
            Deduplicated artifact envelopes ordered deterministically by identity key.
        """
        chain_artifacts = await self._collect_parent_chain_artifacts(run_id)
        manifest = self.manifest_store.read_manifest(run_id)
        return self._dedup_chain_artifacts(
            chain_artifacts,
            phase_order=self._phase_order_map(manifest),
        )

    async def diff_artifacts(
        self, run_id: str, baseline_run_id: str
    ) -> dict[str, list[str]]:
        """Compare artifacts of ``run_id`` against ``baseline_run_id``.

        Parameters
        ----------
        run_id : str
            Target run identifier.
        baseline_run_id : str
            Baseline run identifier to diff against.

        Returns
        -------
        dict of str to list of str
            Mapping ``{phase_name: [identity_key, ...]}`` of changed artifacts.
        """
        current_artifacts = await self.artifact_store.list_run_artifacts(run_id)
        baseline_artifacts = await self.artifact_store.list_run_artifacts(
            baseline_run_id
        )
        if not current_artifacts:
            return {}
        dag = ArtifactDependencyGraph.from_artifacts(current_artifacts)
        return dag.build_phase_staleness_map(
            build_prior_fingerprints(baseline_artifacts),
            prior_artifacts=baseline_artifacts,
        )

    async def get_run_report(self, run_id: str) -> RunReport:
        """Assemble a complete :class:`RunReport` for a persisted run.

        Parameters
        ----------
        run_id : str
            Run identifier to inspect.

        Returns
        -------
        RunReport
            Aggregated run report.

        Raises
        ------
        ValueError
            If no manifest exists for ``run_id``.
        """
        manifest = self.manifest_store.read_manifest(run_id)
        if manifest is None:
            raise ValueError(f"No manifest found for run_id={run_id}")

        chain_artifacts = await self._collect_parent_chain_artifacts(run_id)
        active_phase_names = {
            rec.phase_name for rec in manifest.phase_records
        }
        artifacts = self._dedup_chain_artifacts(
            chain_artifacts,
            allowed_phase_names=active_phase_names,
            phase_order=self._phase_order_map(manifest),
        )

        by_kind: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        new_by_kind: dict[str, int] = {}
        new_by_phase: dict[str, int] = {}
        reused_by_kind: dict[str, int] = {}
        reused_by_phase: dict[str, int] = {}

        reused_phase_ordinals = [
            rec.phase_ordinal for rec in manifest.phase_records if rec.reused
        ]
        invalidated_phase_ordinals = [
            rec.phase_ordinal
            for rec in manifest.phase_records
            if not rec.reused
        ]

        entries = self.collect_run_artifact_entries(artifacts, manifest, run_id)
        for entry in entries:
            kind_val = entry.kind
            self._increment_count(by_kind, kind_val)
            self._increment_count(by_phase, entry.phase_name)

            if entry.reused:
                self._increment_count(reused_by_kind, kind_val)
                self._increment_count(reused_by_phase, entry.phase_name)
            else:
                self._increment_count(new_by_kind, kind_val)
                self._increment_count(new_by_phase, entry.phase_name)

        return RunReport(
            manifest=manifest,
            run_id=manifest.run_id,
            status=manifest.status,
            started_at=manifest.started_at,
            completed_at=manifest.completed_at,
            phase_records=manifest.phase_records,
            artifact_counts_by_kind=by_kind,
            artifact_counts_by_phase=by_phase,
            new_artifact_counts_by_kind=new_by_kind,
            new_artifact_counts_by_phase=new_by_phase,
            reused_artifact_counts_by_kind=reused_by_kind,
            reused_artifact_counts_by_phase=reused_by_phase,
            reused_phase_ordinals=reused_phase_ordinals,
            invalidated_phase_ordinals=invalidated_phase_ordinals,
            invalidation_reason=manifest.invalidation_reason,
            artifact_entries=entries,
            observer_telemetry=dict(manifest.observer_telemetry),
        )

    @staticmethod
    def collect_run_artifact_entries(
        artifacts: list[Any],
        manifest: RunManifest | None,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Collect and tag :class:`ArtifactReportEntry` items indicating reuse status.

        Parameters
        ----------
        artifacts : list of Any
            Artifact envelopes to process.
        manifest : RunManifest or None
            Associated run manifest containing phase records.
        run_id : str
            Current run identifier.
        phase_name : str or None, optional
            Filter for specific phase name.
        kind : str or None, optional
            Filter for specific artifact kind.

        Returns
        -------
        list of ArtifactReportEntry
            Processed and tagged artifact report entries.
        """
        entries: list[ArtifactReportEntry] = []
        for a in artifacts:
            if phase_name is not None and a.phase_name != phase_name:
                continue

            kind_str = _artifact_kind_str(a.kind)
            if kind is not None and kind_str != kind:
                continue

            is_reused = False
            if a.run_id != run_id:
                is_reused = True
            elif manifest is not None:
                for rec in manifest.phase_records:
                    if rec.reused and a.artifact_id in rec.artifact_ids:
                        is_reused = True
                        break
                else:
                    for rec in manifest.phase_records:
                        if (
                            rec.phase_name == a.phase_name
                            and rec.reused
                            and not rec.artifact_ids
                        ):
                            is_reused = True
                            break

            entries.append(
                ArtifactReportEntry(
                    artifact_id=a.artifact_id,
                    identity_key=a.identity_key or a.artifact_id,
                    kind=kind_str,
                    phase_name=a.phase_name,
                    run_id=a.run_id,
                    reused=is_reused,
                )
            )
        return entries

    async def get_run_artifacts(
        self,
        run_id: str,
        *,
        phase_name: str | None = None,
        kind: str | None = None,
    ) -> list[ArtifactReportEntry]:
        """Retrieve all report-level artifact entries associated with a run.

        Parameters
        ----------
        run_id : str
            Unique run identifier.
        phase_name : str or None, optional
            Optional phase name filter.
        kind : str or None, optional
            Optional artifact kind filter.

        Returns
        -------
        list of ArtifactReportEntry
            Matching artifact report entries.
        """
        manifest = self.manifest_store.read_manifest(run_id)
        artifacts = await self.get_run_artifacts_raw(run_id)
        return self.collect_run_artifact_entries(
            artifacts, manifest, run_id, phase_name=phase_name, kind=kind
        )
