"""Subprocess worker executing the pipeline with attached StudioEventObserver."""

from __future__ import annotations

import asyncio
import math
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from episteme_pipeline.events.bus import ContextualEventEmitter, SimpleEventEmitter
from episteme_pipeline.events.models import (
    ComponentCompleted,
    ComponentStarted,
    DecisionEvaluationCompleted,
    DecisionGatingTriggered,
    EntityProcessed,
    PhaseCompleted,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
    TripleCommitted,
)
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore
from episteme_studio.runtime.observer import StudioEventObserver
from episteme_studio.settings import (
    check_env_var_set,
    get_env_var,
    load_all_dotenv,
    set_env_var,
)


class StreamTee:
    """Tee wrapper for stdout/stderr that forwards lines to an IPC event queue.

    Parameters
    ----------
    original_stream : Any
        The wrapped original stream (sys.stdout or sys.stderr).
    queue : Any
        Multiprocessing queue to push terminal events to.
    run_id : str
        Run identifier to tag events with.
    stream_name : str
        Stream name: 'stdout' or 'stderr'.
    """

    def __init__(
        self,
        original_stream: Any,
        queue: Any,
        run_id: str,
        stream_name: str,
    ) -> None:
        self._orig = original_stream
        self._queue = queue
        self._run_id = run_id
        self._stream_name = stream_name
        self._buffer = ""

    def write(self, data: str) -> int:
        """Write string to the original stream and buffer lines for queue IPC.

        Parameters
        ----------
        data : str
            String data to write.

        Returns
        -------
        int
            Length of written data.
        """
        if not data:
            return 0
        try:
            self._orig.write(data)
            self._orig.flush()
        except Exception:
            pass

        self._buffer += str(data)
        lines_to_send: list[str] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                lines_to_send.append(line)

        if lines_to_send:
            # Batch in chunks of up to 50 lines to prevent queue saturation
            for i in range(0, len(lines_to_send), 50):
                self._send_lines(lines_to_send[i : i + 50])
        return len(data)

    def _send_line(self, line: str) -> None:
        """Forward a discrete line of terminal output over the event queue.

        Parameters
        ----------
        line : str
            Single line of terminal output.
        """
        self._send_lines([line])

    def _send_lines(self, lines: list[str]) -> None:
        """Forward a batch of terminal lines over the event queue.

        Parameters
        ----------
        lines : list of str
            Batch of terminal lines to send.
        """
        if not lines:
            return
        try:
            lvl = "error" if self._stream_name == "stderr" else "info"
            msg = lines[0] if len(lines) == 1 else f"[{len(lines)} lines] {lines[0]}"
            self._queue.put_nowait(
                {
                    "_raw_type": "TerminalOutput",
                    "run_id": self._run_id,
                    "stream": self._stream_name,
                    "level": lvl,
                    "message": msg,
                    "lines": lines,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception:
            pass

    def flush(self) -> None:
        """Flush original stream and any remaining buffered line content."""
        try:
            self._orig.flush()
        except Exception:
            pass
        if self._buffer.strip():
            self._send_lines([self._buffer.strip()])
            self._buffer = ""

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying original stream."""
        return getattr(self._orig, name)


def _run_demo_pipeline(
    run_id: str,
    observer: StudioEventObserver,
    event_queue: Any,
    source_paths: list[str] | None = None,
    config_dict: dict[str, Any] | None = None,
    bib_paths: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    structural_anchor: dict[str, Any] | None = None,
    parent_run_id: str | None = None,
) -> None:
    """Execute a realistic synthetic pipeline run for demonstration and offline testing.

    Parameters
    ----------
    run_id : str
        Pipeline run identifier.
    observer : StudioEventObserver
        Zero-IO event observer.
    event_queue : Any
        IPC queue to parent process.
    source_paths : list of str, optional
        Input document paths.
    config_dict : dict of str to Any, optional
        Serialized PipelineConfig dictionary.
    bib_paths : list of str, optional
        Bibliography references (.bib).
    metadata : dict of str to str, optional
        Execution metadata strings.
    structural_anchor : dict of str to Any or None, optional
        Global structural anchor coordinate system.
    """
    emitter = SimpleEventEmitter()
    emitter.register_observer(observer)
    context_emitter = ContextualEventEmitter(emitter, defaults={"run_id": run_id})

    phases = [
        ("Phase 1: Data Foundation", 1),
        ("Phase 2: Entity & Local Relation Discovery", 2),
        ("Phase 3: Global Relation Extraction", 3),
        ("Phase 3b: Latent Graph Consolidation", 4),
        ("Phase 4: Entity Maturation", 5),
        ("Phase 4: Argument Mining", 6),
        ("Phase 5: Inter-Document Argument Web", 7),
        ("Phase 6: TheoryNet Projection", 8),
    ]

    print(f"=== Starting pipeline run {run_id} (Simulation Mode) ===")
    print(f"Input sources: {source_paths or ['default']}")

    log_dir = Path(".pipeline_runs") / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"
    decisions_file = log_dir / "decisions.jsonl"

    phase_records: list[RunPhaseRecord] = []
    start_time = datetime.now(timezone.utc)
    all_decisions: list[dict[str, Any]] = []

    with log_file.open("w", encoding="utf-8") as lf, decisions_file.open("w", encoding="utf-8") as df:
        import json
        lf.write(f"[{start_time.isoformat()}] [INFO] pipeline: Starting pipeline run {run_id} (Simulation)\n")
        for phase_name, ordinal in phases:
            phase_start = datetime.now(timezone.utc)
            lf.write(f"[{phase_start.isoformat()}] [INFO] pipeline.{phase_name}: Starting runner\n")
            print(f"[{phase_name}] Runner started")
            context_emitter.defaults["phase"] = phase_name
            context_emitter.emit(
                ComponentStarted(
                    component_name=phase_name,
                )
            )
            step_count = 25 if ordinal >= 2 else 5
            context_emitter.emit(
                ProgressStarted(
                    task_name=phase_name,
                    total_items=step_count,
                    description=f"Starting {phase_name}",
                )
            )

            art_ids = []
            for step in range(1, step_count + 1):
                time.sleep(0.005)
                art_id = f"demo_art_{ordinal}_{step}"
                art_ids.append(art_id)
                context_emitter.emit(
                    EntityProcessed(
                        entity_id=f"entity_demo_{ordinal}_{step}",
                        entity_name=f"Concept {step} ({phase_name})",
                        entity_type="TheoreticalConcept",
                    )
                )

                # Simulate System 1 Decision
                is_audit = (step % 20 == 0)
                is_escalated = (step % 6 == 0) and not is_audit
                is_fast_exit = not is_escalated
                action = "stochastic_audit" if is_audit else ("escalated_to_llm" if is_escalated else "fast_exit")
                acc = round(0.95 if is_fast_exit else 0.72, 3)
                dur = 0.013 if is_fast_exit else 2.15
                tok_saved = 480 if is_fast_exit else 0
                prim = "choice" if ordinal in (3, 4) else "noul"
                val = "SUPPORTS" if step % 2 == 0 else "ATTACKS" if prim == "choice" else "true"
                pred_set = [val] if is_fast_exit else [val, "ATTACKS" if val == "SUPPORTS" else "false"]

                context_emitter.emit(
                    DecisionEvaluationCompleted(
                        engine_name="LayaDecisionEngine",
                        primitive=prim,
                        question=f"Evaluate dialectical relation for concept {step} in {phase_name}",
                        prompt_name="decision_pair_gating" if ordinal == 3 else "acc_arc_triage",
                        selected_value=val,
                        class_probability=round(acc - 0.03, 3),
                        empirical_accuracy=acc,
                        probabilities={val: acc, "OTHER": round(1.0 - acc, 3)},
                        prediction_set=pred_set,
                        is_stochastic_audit=is_audit,
                        duration_seconds=dur,
                        tokens_saved_estimate=tok_saved,
                    )
                )
                context_emitter.emit(
                    DecisionGatingTriggered(
                        gate_name=f"gate_{phase_name}",
                        action_taken=action,
                        empirical_accuracy=acc,
                        threshold=0.85,
                        prediction_set_size=len(pred_set),
                    )
                )

                dec_entry = {
                    "decision_id": f"dec_{run_id[:8]}_{ordinal}_{step}",
                    "run_id": run_id,
                    "phase_name": phase_name,
                    "primitive": prim,
                    "question": f"Evaluate dialectical relation for concept {step} in {phase_name}",
                    "state_snippet": f"State context for concept {step} in {phase_name}",
                    "selected_value": val,
                    "system_1_choice": val,
                    "system_2_choice": val if is_audit else ("ATTACKS" if is_escalated else None),
                    "options": ["SUPPORTS", "ATTACKS"] if prim == "choice" else ["true", "false"],
                    "prediction_set": pred_set,
                    "class_probability": round(acc - 0.03, 3),
                    "empirical_accuracy": acc,
                    "is_stochastic_audit": is_audit,
                    "duration_seconds": dur,
                    "tokens_saved_estimate": tok_saved,
                    "action_taken": action,
                    "entropy": 0.32 if is_fast_exit else 0.78,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                all_decisions.append(dec_entry)
                df.write(json.dumps(dec_entry) + "\n")

                if ordinal >= 2:
                    conf = round(
                        min(
                            0.98,
                            max(
                                0.42,
                                0.72 + 0.18 * math.sin(step * 0.45) + (step % 4) * 0.03,
                            ),
                        ),
                        3,
                    )
                    context_emitter.emit(
                        TripleCommitted(
                            subject_id=f"entity_demo_{ordinal}_{step}",
                            predicate="RELATES_TO",
                            object_id=f"entity_demo_{ordinal}_{(step % step_count) + 1}",
                            confidence=conf,
                            scope="global",
                            source_chunk_id=f"chunk_demo_{ordinal}_{step}",
                        )
                    )
                context_emitter.emit(
                    ProgressAdvanced(
                        task_name=phase_name,
                        advance=1,
                    )
                )
                lf.write(f"[{datetime.now(timezone.utc).isoformat()}] [INFO] {phase_name}: Processed concept {step}\n")

            context_emitter.emit(
                ProgressCompleted(
                    task_name=phase_name,
                )
            )
            phase_end = datetime.now(timezone.utc)
            context_emitter.emit(
                PhaseCompleted(
                    phase_name=phase_name,
                    artifact_count=step_count,
                    duration_seconds=0.15,
                    success=True,
                )
            )
            context_emitter.emit(
                ComponentCompleted(
                    component_name=phase_name,
                    duration_seconds=0.15,
                    success=True,
                )
            )
            lf.write(f"[{phase_end.isoformat()}] [INFO] pipeline.{phase_name}: Completed successfully ({step_count} artifacts)\n")
            print(f"[{phase_name}] Completed successfully")

            phase_records.append(
                RunPhaseRecord(
                    phase_name=phase_name,
                    phase_ordinal=ordinal,
                    status=RunStatus.COMPLETED,
                    started_at=phase_start,
                    completed_at=phase_end,
                    artifact_ids=art_ids,
                )
            )

        end_time = datetime.now(timezone.utc)
        lf.write(f"[{end_time.isoformat()}] [INFO] pipeline: Pipeline run {run_id} completed\n")
        print(f"=== Pipeline run {run_id} completed successfully ===")

    # Aggregate DecisionRunMetrics
    tot_dec = len(all_decisions)
    fe_cnt = sum(1 for d in all_decisions if d["action_taken"] in ("fast_exit", "stochastic_audit"))
    esc_cnt = tot_dec - fe_cnt
    aud_cnt = sum(1 for d in all_decisions if d["is_stochastic_audit"])
    tok_saved = sum(d["tokens_saved_estimate"] for d in all_decisions)
    cost_saved = round(tok_saved * 0.000008, 4)
    lats = [d["duration_seconds"] * 1000 for d in all_decisions if d["action_taken"] == "fast_exit"]
    lats.sort()
    p50 = round(lats[len(lats) // 2], 2) if lats else 12.8
    p95 = round(lats[int(len(lats) * 0.95)], 2) if lats else 15.4
    p99 = round(lats[int(len(lats) * 0.99)], 2) if lats else 18.2

    by_phase: dict[str, Any] = {}
    by_prim: dict[str, int] = {}
    for d in all_decisions:
        pname = d["phase_name"]
        ps = by_phase.setdefault(
            pname,
            {
                "phase_name": pname,
                "total_evaluations": 0,
                "fast_exits": 0,
                "escalations_to_llm": 0,
                "stochastic_audits": 0,
                "tokens_saved_estimate": 0,
                "duration_seconds": 0.0,
                "avg_empirical_accuracy": 0.0,
            },
        )
        ps["total_evaluations"] += 1
        if d["action_taken"] in ("fast_exit", "stochastic_audit"):
            ps["fast_exits"] += 1
        else:
            ps["escalations_to_llm"] += 1
        if d["is_stochastic_audit"]:
            ps["stochastic_audits"] += 1
        ps["tokens_saved_estimate"] += d["tokens_saved_estimate"]
        ps["duration_seconds"] += d["duration_seconds"]
        ps["avg_empirical_accuracy"] += d["empirical_accuracy"]
        by_prim[d["primitive"]] = by_prim.get(d["primitive"], 0) + 1

    for ps in by_phase.values():
        if ps["total_evaluations"] > 0:
            ps["avg_empirical_accuracy"] = round(
                ps["avg_empirical_accuracy"] / ps["total_evaluations"], 3
            )

    decision_metrics_dict = {
        "total_decisions": tot_dec,
        "fast_exit_count": fe_cnt,
        "fast_exit_ratio": round(fe_cnt / max(1, tot_dec), 3),
        "llm_escalation_count": esc_cnt,
        "llm_escalation_ratio": round(esc_cnt / max(1, tot_dec), 3),
        "stochastic_audit_count": aud_cnt,
        "tokens_saved_estimate": tok_saved,
        "cost_saved_usd_estimate": cost_saved,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_p99_ms": p99,
        "by_phase": by_phase,
        "by_primitive": by_prim,
    }

    # Persist run manifest to .pipeline_runs/<run_id>.json
    try:
        manifest = RunManifest(
            run_id=run_id,
            status=RunStatus.COMPLETED,
            started_at=start_time,
            completed_at=end_time,
            phase_records=phase_records,
            config_snapshot=config_dict or {},
            input_sources=source_paths or [],
            input_fingerprint_inputs={
                "source_paths": list(source_paths or []),
                "bib_paths": list(bib_paths or []),
                "metadata": dict(metadata or {}),
                "structural_anchor": structural_anchor,
            },
            parent_run_id=parent_run_id,
            decision_metrics=decision_metrics_dict,
        )
        store = JsonRunManifestStore(".pipeline_runs")
        store.write_manifest(manifest)
    except Exception as err:
        print(f"Warning: Failed to persist simulation manifest: {err}", file=sys.stderr)


def run_pipeline_worker(
    run_id: str,
    config_dict: dict[str, Any],
    source_paths: list[str],
    event_queue: Any,
    demo_mode: bool = False,
    bib_paths: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    structural_anchor: dict[str, Any] | None = None,
    parent_run_id: str | None = None,
) -> None:
    """Subprocess entry point running the pipeline or demo execution.

    Parameters
    ----------
    run_id : str
        Pipeline run identifier.
    config_dict : dict of str to Any
        Serialized PipelineConfig dictionary.
    source_paths : list of str
        Input document paths to process.
    event_queue : Any
        Multiprocessing queue to send events to the parent process.
    demo_mode : bool, default False
        Whether to run in demo simulation mode.
    bib_paths : list of str or None, optional
        Bibliography references (.bib).
    metadata : dict of str to str or None, optional
        Execution metadata strings.
    structural_anchor : dict of str to Any or None, optional
        Global structural anchor coordinate system.
    parent_run_id : str or None, optional
        Parent run identifier for cache invalidation and phase reuse.
    """
    load_all_dotenv()

    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    sys.stdout = StreamTee(orig_stdout, event_queue, run_id, "stdout")
    sys.stderr = StreamTee(orig_stderr, event_queue, run_id, "stderr")

    pid_file = Path(".pipeline_runs") / run_id / "process.pid"
    try:
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    try:
        observer = StudioEventObserver(event_queue)
        if config_dict and config_dict.get("_simulate_failure"):
            raise ValueError(
                config_dict.get(
                    "_simulate_failure_message",
                    "Simulated pipeline explosion in Phase 2",
                )
            )

        from episteme_pipeline.runs.observability import run_observability_context

        session_id = get_env_var("LANGFUSE_SESSION_ID") or run_id
        set_env_var("LANGFUSE_SESSION_ID", session_id)

        with run_observability_context(
            name="full_pipeline_run",
            session_id=session_id,
            run_id=session_id,
            tags=["example", "knowledge_graph"],
        ):
            if demo_mode:
                _run_demo_pipeline(
                    session_id,
                    observer,
                    event_queue,
                    source_paths=source_paths,
                    config_dict=config_dict,
                    bib_paths=bib_paths,
                    metadata=metadata,
                    structural_anchor=structural_anchor,
                    parent_run_id=parent_run_id,
                )
            else:
                emitter = SimpleEventEmitter()
                emitter.register_observer(observer)
                if check_env_var_set("LANGFUSE_PUBLIC_KEY"):
                    try:
                        from episteme_pipeline.events.langfuse_observer import LangfuseObserver

                        emitter.register_observer(LangfuseObserver())
                    except Exception as err:
                        print(f"Warning: Could not register LangfuseObserver: {err}", file=sys.stderr)

                print(f"=== Starting real pipeline run {session_id} ===")
                print(f"Input source paths: {source_paths}")
                if bib_paths:
                    print(f"Input bib paths: {bib_paths}")
                if metadata:
                    print(f"Metadata: {metadata}")
                if structural_anchor:
                    print(f"Structural anchor: {structural_anchor}")
                if parent_run_id:
                    print(f"Parent run ID: {parent_run_id}")

                from episteme_pipeline.runtime.runner import run_pipeline

                asyncio.run(
                    run_pipeline(
                        source_paths=source_paths,
                        bib_paths=bib_paths,
                        metadata=metadata,
                        structural_anchor=structural_anchor,
                        config=config_dict,
                        event_emitter=emitter,
                        run_id=session_id,
                        parent_run_id=parent_run_id,
                    )
                )

        # Notify parent process that the run has completed successfully
        event_queue.put({"_type": "RUN_COMPLETED", "run_id": session_id})
        time.sleep(0.1)
    except Exception as err:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        try:
            event_queue.put(
                {
                    "_type": "RUN_FAILED",
                    "run_id": run_id,
                    "error": str(err),
                    "traceback": tb,
                }
            )
            time.sleep(0.2)
        except Exception:
            pass
        sys.exit(1)
    finally:
        try:
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
