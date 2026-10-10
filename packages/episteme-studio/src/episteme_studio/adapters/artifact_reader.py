"""Artifact store reader translating on-disk runs and envelopes to domain models."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from episteme_studio.adapters.schema_mapper import SchemaMapper
from episteme_studio.domain.graph import (
    GraphView,
    Layer,
    StudioEdge,
    StudioNode,
    reify_inferences,
)
from episteme_studio.domain.runs import (
    ArtifactRef,
    DecisionRunMetrics,
    EvidenceChunk,
    EvidenceSpan,
    EvidenceTrail,
    GlobalStructuralAnchor,
    PhaseStatus,
    RunDetail,
    RunStatus,
    RunSummary,
)


class ArtifactStoreError(Exception):
    """Raised when the artifact store is inaccessible or corrupted."""


def redact_secrets(data: Any) -> Any:
    """Recursively mask secrets and credentials in configuration payloads.

    Parameters
    ----------
    data : Any
        Nested dictionary, list, or scalar value.

    Returns
    -------
    Any
        Sanitized structure with sensitive keys masked.
    """
    sensitive_substrings = ("key", "secret", "token", "password", "auth", "credential")
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sub in k_lower for sub in sensitive_substrings):
                sanitized[k] = "***"
            else:
                sanitized[k] = redact_secrets(v)
        return sanitized
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


def _format_yield_summary(counts: dict[str, int], phase_name: str = "") -> str | None:
    """Format artifact kind counts into a human-readable domain yield summary.

    Parameters
    ----------
    counts : dict of str to int
        Artifact kind counts for a phase.
    phase_name : str, optional
        Name of the phase for disambiguation.

    Returns
    -------
    str or None
        Formatted summary like '27 ADUs • 87 Relations' or None if counts empty.
    """
    if not counts:
        return None

    parts: list[str] = []

    # Phase 1: Documents & Chunks
    docs = counts.get("document", 0)
    chunks = counts.get("chunk", 0)
    if docs > 0:
        parts.append(f"{docs} {'Doc' if docs == 1 else 'Docs'}")
    if chunks > 0:
        parts.append(f"{chunks} {'Chunk' if chunks == 1 else 'Chunks'}")

    # Phase 2: Entities and Local Relations
    mentions = counts.get("entity_mention", 0)
    entities = counts.get("linked_entity", 0) or counts.get("entity", 0) or counts.get("mature_entity", 0)
    local_rels = counts.get("local_relation", 0)
    if entities > 0:
        parts.append(f"{entities} Entities")
    elif mentions > 0:
        parts.append(f"{mentions} Mentions")
    if local_rels > 0:
        parts.append(f"{local_rels} Local Rels")

    # Phase 3: Global Relations
    global_rels = counts.get("global_relation", 0)
    if global_rels > 0:
        parts.append(f"{global_rels} Global Relations")

    # Canonicalization / Maturation
    canon = counts.get("canonicalization", 0)
    if canon > 0:
        parts.append(f"{canon} Canonicalized")

    # Phase 4: Argument Mining
    atoms = counts.get("theory_atom", 0) or counts.get("argument_component", 0)
    theory_rels = counts.get("theory_relation", 0) or counts.get("argument_relation", 0)
    if atoms > 0:
        parts.append(f"{atoms} ADUs")
    if theory_rels > 0:
        parts.append(f"{theory_rels} Relations")

    # Phase 5: Fusion decisions
    fusions = counts.get("fusion_decision", 0) or counts.get("fusion_cluster", 0)
    if fusions > 0:
        parts.append(f"{fusions} {'Cluster' if fusions == 1 else 'Clusters'}")

    # Post-processors: Theoretical Enrichment & Tenability
    theories = counts.get("theoretical_enrichment", 0)
    if theories > 0:
        parts.append(f"{theories} {'Theory Model' if theories == 1 else 'Theory Models'}")

    if not parts:
        formatted = [f"{v} {k.replace('_', ' ').title()}" for k, v in counts.items() if v > 0]
        return " • ".join(formatted) if formatted else None

    return " • ".join(parts)


class ArtifactReader:
    """Reads run manifests and artifact envelopes directly from filesystem storage.

    Parameters
    ----------
    runs_dir : Path or str
        Path to directory containing run manifests (*.json).
    artifacts_dir : Path or str
        Path to directory containing artifact run subdirectories.
    """

    def __init__(
        self,
        runs_dir: Path | str,
        artifacts_dir: Path | str,
        langfuse_host: str = "https://cloud.langfuse.com",
        extra_runs_dirs: Sequence[Path | str] | None = None,
        extra_artifacts_dirs: Sequence[Path | str] | None = None,
    ) -> None:
        self.runs_dir = Path(runs_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self.langfuse_host = str(langfuse_host).rstrip("/")

        if extra_runs_dirs is None:
            try:
                from episteme_studio.settings import (
                    _resolve_default_runs_dir,
                    _resolve_extra_dirs,
                )
                default_runs = _resolve_default_runs_dir().resolve()
                if self.runs_dir.resolve() == default_runs or self.runs_dir.name == ".pipeline_runs":
                    e_runs = _resolve_extra_dirs(".pipeline_runs")
                else:
                    e_runs = []
            except Exception:
                e_runs = []
        else:
            e_runs = [Path(d) for d in extra_runs_dirs]

        if extra_artifacts_dirs is None:
            try:
                from episteme_studio.settings import (
                    _resolve_default_artifacts_dir,
                    _resolve_extra_dirs,
                )
                default_arts = _resolve_default_artifacts_dir().resolve()
                if self.artifacts_dir.resolve() == default_arts or self.artifacts_dir.name == ".pipeline_artifacts":
                    e_arts = _resolve_extra_dirs(".pipeline_artifacts")
                else:
                    e_arts = []
            except Exception:
                e_arts = []
        else:
            e_arts = [Path(d) for d in extra_artifacts_dirs]

        self.extra_runs_dirs: list[Path] = []
        for d in e_runs:
            try:
                if d.is_dir() and d.resolve() != self.runs_dir.resolve() and d not in self.extra_runs_dirs:
                    self.extra_runs_dirs.append(d)
            except Exception:
                pass

        self.extra_artifacts_dirs: list[Path] = []
        for d in e_arts:
            try:
                if d.is_dir() and d.resolve() != self.artifacts_dir.resolve() and d not in self.extra_artifacts_dirs:
                    self.extra_artifacts_dirs.append(d)
            except Exception:
                pass

    def _find_manifest_path(self, run_id: str) -> Path | None:
        """Find the on-disk JSON manifest path for a given run ID across search dirs."""
        for r_dir in [self.runs_dir, *self.extra_runs_dirs]:
            p = r_dir / f"{run_id}.json"
            if p.is_file():
                return p
        return None

    def _is_run_alive(self, run_id: str) -> bool:
        """Check if an OS process is actively executing for this run_id."""
        for r_dir in [self.runs_dir, *self.extra_runs_dirs]:
            pid_file = r_dir / run_id / "process.pid"
            if not pid_file.is_file():
                alt_pid = r_dir / f"{run_id}.pid"
                if alt_pid.is_file():
                    pid_file = alt_pid
            if pid_file.is_file():
                try:
                    pid = int(pid_file.read_text(encoding="utf-8").strip())
                    os.kill(pid, 0)
                    return True
                except (OSError, ValueError):
                    pass
        return False

    def get_manifest(self, run_id: str) -> dict[str, Any] | None:
        """Read the raw JSON manifest for a run.

        Parameters
        ----------
        run_id : str
            Unique run identifier.

        Returns
        -------
        dict of str to Any or None
            Parsed manifest dictionary if it exists, None otherwise.
        """
        manifest_path = self._find_manifest_path(run_id)
        if not manifest_path or not manifest_path.is_file():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _get_run_artifacts_dir(self, run_id: str) -> Path:
        primary = self.artifacts_dir / run_id
        if primary.is_dir():
            return primary
        for a_dir in self.extra_artifacts_dirs:
            candidate = a_dir / run_id
            if candidate.is_dir():
                return candidate
        return primary

    def _get_lineage_run_ids(self, run_id: str) -> list[str]:
        """Traverse the ancestor lineage of run_id via parent_run_id pointers.

        Parameters
        ----------
        run_id : str
            Starting run identifier.

        Returns
        -------
        list of str
            List of run identifiers from nearest (run_id) to earliest ancestor without cycles.
        """
        lineage = [run_id]
        visited = {run_id}
        curr = run_id
        while True:
            manifest_path = self._find_manifest_path(curr)
            if not manifest_path or not manifest_path.is_file():
                break
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                break
            parent = data.get("parent_run_id")
            if not parent or parent in visited:
                break
            visited.add(parent)
            lineage.append(parent)
            curr = parent
        return lineage

    def _collect_run_envelopes(self, run_id: str) -> list[tuple[dict[str, Any], Path]]:
        """Collect all artifact envelopes visible to run_id, walking the parent-run chain.

        Walks the lineage nearest-first, with earlier occurrences (closer to current run)
        taking precedence by identity_key or artifact_id.

        Parameters
        ----------
        run_id : str
            Identifier of target run.

        Returns
        -------
        list of tuple of (dict, Path)
            List of parsed envelopes and their source file paths, deduplicated.
        """
        lineage = self._get_lineage_run_ids(run_id)
        seen_keys: set[str] = set()
        envelopes: list[tuple[dict[str, Any], Path]] = []

        for rid in lineage:
            run_art_dirs = [self.artifacts_dir / rid, *[d / rid for d in self.extra_artifacts_dirs]]
            found = False
            for run_art_dir in run_art_dirs:
                if not run_art_dir.is_dir():
                    continue
                found = True
                for p in sorted(run_art_dir.glob("*.json")):
                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    key = data.get("identity_key") or data.get("artifact_id") or p.stem
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    envelopes.append((data, p))
                if found:
                    break

        return envelopes

    def _calculate_run_size_bytes(self, run_id: str, manifest_path: Path | None = None) -> int:
        total = 0
        if manifest_path and manifest_path.is_file():
            total += manifest_path.stat().st_size
        for _, p in self._collect_run_envelopes(run_id):
            try:
                total += p.stat().st_size
            except OSError:
                pass
        return total

    def _count_artifacts_by_kind(self, run_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for data, p in self._collect_run_envelopes(run_id):
            kind = data.get("kind")
            if not kind:
                name = p.name
                if name.startswith("artifact::"):
                    part = name[len("artifact::"):]
                    kind = part.split("-")[0].split("::")[0].split(".")[0]
                else:
                    kind = "unknown"
            counts[kind] = counts.get(kind, 0) + 1
        return counts

    def list_runs(self) -> list[RunSummary]:
        """List all discoverable pipeline runs from manifest files across primary and extra run dirs.

        Returns
        -------
        list of RunSummary
            Summaries sorted by creation time descending.
        """
        candidate_dirs = [self.runs_dir, *self.extra_runs_dirs]
        seen_run_ids: set[str] = set()
        summaries: list[RunSummary] = []

        for r_dir in candidate_dirs:
            if not r_dir.is_dir():
                continue
            for p in sorted(r_dir.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue

                if not isinstance(data, dict) or "run_id" not in data:
                    continue

                run_id = data["run_id"]
                if run_id in seen_run_ids:
                    continue
                seen_run_ids.add(run_id)

                status = RunStatus(data.get("status", "planned"))
                created_at = data.get("created_at")
                completed_at = data.get("completed_at")

                # If marked running but no process is alive, heal status
                if status == RunStatus.RUNNING and not self._is_run_alive(run_id):
                    status = RunStatus.FAILED
                    if not completed_at:
                        completed_at = data.get("started_at") or created_at
                    try:
                        data["status"] = "failed"
                        data["completed_at"] = completed_at
                        if not data.get("failure"):
                            data["failure"] = {
                                "type": "run-interrupted",
                                "title": "Run Interrupted",
                                "status": 500,
                                "detail": "Execution process terminated before completion.",
                            }
                        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    except Exception:
                        pass

                pipeline_version = data.get("pipeline_version", "0.1.0")
                schema_version = data.get("schema_version")
                input_fp_inputs = data.get("input_fingerprint_inputs", {})
                input_sources = (
                    data.get("input_sources")
                    or (input_fp_inputs.get("source_paths") if isinstance(input_fp_inputs, dict) else None)
                    or data.get("source_paths")
                    or []
                )
                tags = data.get("tags", [])
                parent_run_id = data.get("parent_run_id")

                # Resolve models gracefully
                models: dict[str, str] = {}
                cfg_snapshot = data.get("config_snapshot", {})
                if isinstance(cfg_snapshot, dict):
                    raw_models = cfg_snapshot.get("models")
                    if isinstance(raw_models, dict):
                        models = {str(k): str(v) for k, v in raw_models.items() if v is not None}
                    else:
                        if "default_embedding_model" in cfg_snapshot:
                            models["embedding_model"] = str(cfg_snapshot["default_embedding_model"])
                        if "default_reranker_model" in cfg_snapshot:
                            models["reranker_model"] = str(cfg_snapshot["default_reranker_model"])
                    if "llm_model" not in models:
                        models["llm_model"] = str(cfg_snapshot.get("llm_model") or "openai/gpt-4o-mini")

                # Artifact count
                phase_records = data.get("phase_records", [])
                artifact_count = 0
                for pr in phase_records:
                    if isinstance(pr, dict):
                        artifact_count += pr.get("artifact_count", len(pr.get("artifact_ids", [])))

                # If phase records had 0, count on disk
                if artifact_count == 0:
                    run_art_dir = self._get_run_artifacts_dir(run_id)
                    if run_art_dir.is_dir():
                        artifact_count = len(list(run_art_dir.glob("*.json")))

                size_bytes = self._calculate_run_size_bytes(run_id, p)

                primary_input = None
                if input_sources:
                    first_src = str(input_sources[0])
                    base = Path(first_src).name if ("/" in first_src or "\\" in first_src) else first_src
                    if len(input_sources) > 1:
                        primary_input = f"{base} (+{len(input_sources)-1})"
                    else:
                        primary_input = base

                duration_s = None
                if created_at and completed_at:
                    try:
                        c_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                        e_dt = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
                        duration_s = max(0.0, (e_dt - c_dt).total_seconds())
                    except Exception:
                        pass

                reused_phase_count = sum(1 for pr in phase_records if isinstance(pr, dict) and pr.get("reused"))
                total_phase_count = len(phase_records)

                bib_sources = data.get("bib_sources") or (input_fp_inputs.get("bib_paths") if isinstance(input_fp_inputs, dict) else None) or []
                run_meta = data.get("metadata") or (input_fp_inputs.get("metadata") if isinstance(input_fp_inputs, dict) else None) or {}
                anchor_raw = data.get("structural_anchor") or (input_fp_inputs.get("structural_anchor") if isinstance(input_fp_inputs, dict) else None)
                anchor_obj = None
                if anchor_raw and isinstance(anchor_raw, dict):
                    try:
                        anchor_obj = GlobalStructuralAnchor(**anchor_raw)
                    except Exception:
                        anchor_obj = None
                elif isinstance(anchor_raw, GlobalStructuralAnchor):
                    anchor_obj = anchor_raw

                decision_metrics_raw = data.get("decision_metrics")
                decision_metrics_obj = None
                if decision_metrics_raw and isinstance(decision_metrics_raw, dict):
                    try:
                        decision_metrics_obj = DecisionRunMetrics(**decision_metrics_raw)
                    except Exception:
                        decision_metrics_obj = None

                summary = RunSummary(
                    run_id=run_id,
                    status=status,
                    created_at=created_at,
                    completed_at=completed_at,
                    duration_seconds=duration_s,
                    pipeline_version=pipeline_version,
                    schema_version=schema_version,
                    input_sources=input_sources,
                    bib_sources=bib_sources,
                    metadata=run_meta,
                    structural_anchor=anchor_obj,
                    primary_input=primary_input,
                    models=models,
                    artifact_count=artifact_count,
                    size_bytes=size_bytes,
                    reused_phase_count=reused_phase_count,
                    total_phase_count=total_phase_count,
                    tags=tags,
                    parent_run_id=parent_run_id,
                    decision_metrics=decision_metrics_obj,
                )
                summaries.append(summary)

        summaries.sort(key=lambda r: r.created_at, reverse=True)
        return summaries

    def get_run(self, run_id: str) -> RunDetail | None:
        """Load full detail for a run manifest by its identifier.

        Parameters
        ----------
        run_id : str
            Unique run identifier.

        Returns
        -------
        RunDetail or None
            Detail model if manifest was found and parsed, None otherwise.
        """
        manifest_path = self._find_manifest_path(run_id)
        if not manifest_path or not manifest_path.is_file():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            raise ArtifactStoreError(f"Corrupted run manifest for '{run_id}': {err}") from err

        status = RunStatus(data.get("status", "planned"))
        created_at = data.get("created_at")
        completed_at = data.get("completed_at")

        if status == RunStatus.RUNNING and not self._is_run_alive(run_id):
            status = RunStatus.FAILED
            if not completed_at:
                completed_at = data.get("started_at") or created_at
            try:
                data["status"] = "failed"
                data["completed_at"] = completed_at
                manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

        # Group envelopes by phase_name and collect artifact_id kinds
        phase_artifact_counts: dict[str, dict[str, int]] = {}
        artifact_id_to_kind: dict[str, str] = {}
        for art_data, p in self._collect_run_envelopes(run_id):
            art_id = art_data.get("artifact_id", p.stem)
            art_kind = art_data.get("kind", "unknown")
            art_phase = art_data.get("phase_name")
            artifact_id_to_kind[art_id] = art_kind
            artifact_id_to_kind[p.stem] = art_kind
            if art_phase:
                counts_dict = phase_artifact_counts.setdefault(art_phase, {})
                counts_dict[art_kind] = counts_dict.get(art_kind, 0) + 1

        raw_phase_records = data.get("phase_records", [])
        phase_records: list[PhaseStatus] = []
        for pr in raw_phase_records:
            if not isinstance(pr, dict):
                continue
            ordinal = pr.get("ordinal", pr.get("phase_ordinal", 0))
            phase_name = pr.get("phase_name", f"Phase {ordinal}")
            p_status = RunStatus(pr.get("status", "planned"))
            reused = bool(pr.get("reused", False))
            art_count = pr.get("artifact_count", len(pr.get("artifact_ids", [])))

            # Per-phase duration
            phase_duration_s = None
            started_at_str = pr.get("started_at")
            completed_at_str = pr.get("completed_at")
            if started_at_str and completed_at_str:
                try:
                    s_dt = datetime.fromisoformat(str(started_at_str).replace("Z", "+00:00"))
                    c_dt = datetime.fromisoformat(str(completed_at_str).replace("Z", "+00:00"))
                    phase_duration_s = max(0.0, (c_dt - s_dt).total_seconds())
                except Exception:
                    pass

            # Per-phase counts by kind
            counts_for_phase = dict(phase_artifact_counts.get(phase_name, {}))
            if not counts_for_phase and "artifact_ids" in pr:
                for aid in pr["artifact_ids"]:
                    kind = artifact_id_to_kind.get(aid, "unknown")
                    counts_for_phase[kind] = counts_for_phase.get(kind, 0) + 1

            yield_summary = _format_yield_summary(counts_for_phase, phase_name)

            phase_records.append(
                PhaseStatus(
                    phase_name=phase_name,
                    phase_ordinal=ordinal,
                    status=p_status,
                    started_at=started_at_str,
                    completed_at=completed_at_str,
                    duration_seconds=phase_duration_s,
                    reused=reused,
                    artifact_count=art_count,
                    yield_summary=yield_summary,
                    artifact_counts_by_kind=counts_for_phase,
                )
            )

        config_snapshot = data.get("config_snapshot", {})
        graph_schema = config_snapshot.get("graph_schema", {}) if isinstance(config_snapshot, dict) else {}
        sanitized_config = redact_secrets(config_snapshot)

        artifact_counts_by_kind = self._count_artifacts_by_kind(run_id)
        artifact_count = sum(artifact_counts_by_kind.values())
        if artifact_count == 0:
            artifact_count = sum(p.artifact_count for p in phase_records)

        size_bytes = self._calculate_run_size_bytes(run_id, manifest_path)

        # Resolve models
        models: dict[str, str] = {}
        if isinstance(config_snapshot, dict):
            raw_models = config_snapshot.get("models")
            if isinstance(raw_models, dict):
                models = {str(k): str(v) for k, v in raw_models.items() if v is not None}
            else:
                if "default_embedding_model" in config_snapshot:
                    models["embedding_model"] = str(config_snapshot["default_embedding_model"])
                if "default_reranker_model" in config_snapshot:
                    models["reranker_model"] = str(config_snapshot["default_reranker_model"])
            if "llm_model" not in models:
                models["llm_model"] = str(config_snapshot.get("llm_model") or "openai/gpt-4o-mini")
            if "temperature" not in models:
                models["temperature"] = "0.0"
            p4_cfg = config_snapshot.get("phase4")
            if isinstance(p4_cfg, dict) and p4_cfg.get("acc_decoding_strategy"):
                models["decoding_strategy"] = str(p4_cfg["acc_decoding_strategy"])
            p3_cfg = config_snapshot.get("phase3")
            if isinstance(p3_cfg, dict) and p3_cfg.get("reranker_threshold") is not None:
                models["reranker_threshold"] = str(p3_cfg["reranker_threshold"])

        run_duration_s = None
        if created_at and completed_at:
            try:
                c_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                e_dt = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
                run_duration_s = max(0.0, (e_dt - c_dt).total_seconds())
            except Exception:
                pass

        input_fp_inputs = data.get("input_fingerprint_inputs", {})
        input_sources = (
            data.get("input_sources")
            or (input_fp_inputs.get("source_paths") if isinstance(input_fp_inputs, dict) else None)
            or data.get("source_paths")
            or []
        )
        primary_input = None
        if input_sources:
            first_src = str(input_sources[0])
            base = Path(first_src).name if ("/" in first_src or "\\" in first_src) else first_src
            if len(input_sources) > 1:
                primary_input = f"{base} (+{len(input_sources)-1})"
            else:
                primary_input = base

        reused_phase_count = sum(1 for p in phase_records if p.reused)
        total_phase_count = len(phase_records)

        langfuse_url = f"{self.langfuse_host}/traces?search={run_id}"

        bib_sources = data.get("bib_sources") or (input_fp_inputs.get("bib_paths") if isinstance(input_fp_inputs, dict) else None) or []
        run_meta = data.get("metadata") or (input_fp_inputs.get("metadata") if isinstance(input_fp_inputs, dict) else None) or {}
        anchor_raw = data.get("structural_anchor") or (input_fp_inputs.get("structural_anchor") if isinstance(input_fp_inputs, dict) else None)
        anchor_obj = None
        if anchor_raw and isinstance(anchor_raw, dict):
            try:
                anchor_obj = GlobalStructuralAnchor(**anchor_raw)
            except Exception:
                anchor_obj = None
        elif isinstance(anchor_raw, GlobalStructuralAnchor):
            anchor_obj = anchor_raw

        decision_metrics_raw = data.get("decision_metrics")
        decision_metrics_obj = None
        if decision_metrics_raw and isinstance(decision_metrics_raw, dict):
            try:
                decision_metrics_obj = DecisionRunMetrics(**decision_metrics_raw)
            except Exception:
                decision_metrics_obj = None

        phase_config_fps = data.get("phase_config_fingerprints") or {}
        norm_phase_config_fps = (
            {str(k): str(v) for k, v in phase_config_fps.items()}
            if isinstance(phase_config_fps, dict)
            else {}
        )
        raw_method_fps = data.get("method_fingerprints") or {}
        norm_method_fps = (
            {str(k): str(v) for k, v in raw_method_fps.items()}
            if isinstance(raw_method_fps, dict)
            else {}
        )
        raw_fps = data.get("fingerprints") or {}
        norm_fps = (
            {str(k): v for k, v in raw_fps.items()}
            if isinstance(raw_fps, dict)
            else {}
        )
        combined_fps = {
            **norm_phase_config_fps,
            **norm_method_fps,
            **norm_fps,
        }

        return RunDetail(
            run_id=run_id,
            status=status,
            created_at=created_at,
            completed_at=completed_at,
            duration_seconds=run_duration_s,
            pipeline_version=data.get("pipeline_version", "0.1.0"),
            schema_version=data.get("schema_version"),
            input_sources=input_sources,
            bib_sources=bib_sources,
            metadata=run_meta,
            structural_anchor=anchor_obj,
            primary_input=primary_input,
            models=models,
            artifact_count=artifact_count,
            size_bytes=size_bytes,
            reused_phase_count=reused_phase_count,
            total_phase_count=total_phase_count,
            tags=data.get("tags", []),
            parent_run_id=data.get("parent_run_id"),
            phase_records=phase_records,
            artifact_counts_by_kind=artifact_counts_by_kind,
            graph_schema=graph_schema,
            config_snapshot=sanitized_config,
            fingerprints=combined_fps,
            method_fingerprints=norm_method_fps,
            unresolved_count=0,
            failure=data.get("failure"),
            cancellation_reason=data.get("cancellation_reason"),
            langfuse_url=langfuse_url,
            decision_metrics=decision_metrics_obj,
        )

    def abort_run(self, run_id: str, reason: str = "Cancelled by user") -> RunSummary:
        """Mark a run manifest on disk as aborted and record completion timestamp.

        Parameters
        ----------
        run_id : str
            Unique run identifier.
        reason : str, default "Cancelled by user"
            Reason or note explaining why the run was aborted.

        Returns
        -------
        RunSummary
            Updated run summary reflecting the aborted execution status.

        Raises
        ------
        ArtifactStoreError
            If the run manifest cannot be found or aborted on disk.
        """
        manifest_path = self._find_manifest_path(run_id)
        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()

        if manifest_path and manifest_path.is_file():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as err:
                raise ArtifactStoreError(f"Corrupted run manifest for '{run_id}': {err}") from err

            data["status"] = "aborted"
            data["completed_at"] = now_iso
            data["cancellation_reason"] = reason

            phase_records = data.get("phase_records", [])
            for pr in phase_records:
                if isinstance(pr, dict):
                    if pr.get("status") in ("running", "planned"):
                        if pr.get("status") == "running":
                            pr["status"] = "aborted"
                            pr["completed_at"] = now_iso
                        elif pr.get("status") == "planned":
                            pr["status"] = "aborted"

            # Atomically write updated manifest
            tmp = manifest_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(manifest_path)
        else:
            manifest_path = self.runs_dir / f"{run_id}.json"
            run_dir = self.runs_dir / run_id
            if not run_dir.is_dir():
                for r_dir in self.extra_runs_dirs:
                    if (r_dir / run_id).is_dir():
                        run_dir = r_dir / run_id
                        manifest_path = r_dir / f"{run_id}.json"
                        break
            if run_dir.is_dir():
                data = {
                    "run_id": run_id,
                    "pipeline_version": "0.1.0",
                    "schema_version": "v1",
                    "status": "aborted",
                    "created_at": now_iso,
                    "started_at": now_iso,
                    "completed_at": now_iso,
                    "cancellation_reason": reason,
                    "phase_records": [],
                    "config_snapshot": {},
                    "input_sources": [],
                }
                manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                raise ArtifactStoreError(f"Run manifest for '{run_id}' not found on disk.")

        updated = self.get_run(run_id)
        if not updated:
            raise ArtifactStoreError(f"Failed to reload aborted manifest for '{run_id}'.")
        return updated

    def list_artifacts(self, run_id: str, kind: str | None = None) -> list[ArtifactRef]:
        """List individual artifact envelopes for a run, optionally filtered by kind.

        Parameters
        ----------
        run_id : str
            Unique run ID.
        kind : str or None, optional
            Filter by artifact kind (e.g. 'chunk', 'entity', 'theory_atom').

        Returns
        -------
        list of ArtifactRef
            Matching artifact references.
        """
        refs: list[ArtifactRef] = []
        for data, p in self._collect_run_envelopes(run_id):
            art_kind = data.get("kind", "unknown")
            if kind and art_kind != kind:
                continue

            refs.append(
                ArtifactRef(
                    artifact_id=data.get("artifact_id", p.stem),
                    identity_key=data.get("identity_key", p.stem),
                    kind=art_kind,
                    phase_name=data.get("phase_name"),
                    created_at=data.get("created_at"),
                    size_bytes=p.stat().st_size,
                )
            )
        return refs

    def get_graph(
        self,
        run_id: str,
        budget: int = 500,
        use_run_schema: bool = False,
    ) -> GraphView:
        """Construct normalized GraphView from artifact envelopes for a run.

        Parameters
        ----------
        run_id : str
            Identifier of run to materialize.
        budget : int, default 500
            Maximum element budget to prevent overwhelming the client canvas.
        use_run_schema : bool, default False
            If True, uses the run's embedded schema snapshot. If False, evaluates against
            the active pipeline schema (revealing unmapped predicates per D-15).

        Returns
        -------
        GraphView
            Materialized nodes and edges with polarity, partition, and budget metadata.
        """
        run = self.get_run(run_id)
        schema_dict = (run.graph_schema if run else {}) if use_run_schema else {}
        mapper = SchemaMapper()
        if schema_dict:
            try:
                from episteme_pipeline.schema.default_schema import SchemaConfig
                mapper = SchemaMapper(SchemaConfig.model_validate(schema_dict))
            except Exception:
                pass

        nodes_by_id: dict[str, StudioNode] = {}
        edges: list[StudioEdge] = []
        enrichments: list[dict[str, Any]] = []
        unmapped_predicates: dict[str, int] = {}

        for data, p in self._collect_run_envelopes(run_id):
            kind = data.get("kind", "")
            payload = data.get("payload", {})
            art_id = data.get("artifact_id", p.stem)

            if kind == "chunk":
                chunk_id = payload.get("id") or art_id
                # CRITICAL: strip embedding per SPEC §8 point 6
                props = {k: v for k, v in payload.items() if k != "embedding"}
                nodes_by_id[chunk_id] = StudioNode(
                    id=chunk_id,
                    layer=Layer.L1,
                    type="Chunk",
                    label=chunk_id,
                    confidence=payload.get("confidence"),
                    props=props,
                )
            elif kind == "document":
                doc_id = payload.get("id") or art_id
                nodes_by_id[doc_id] = StudioNode(
                    id=doc_id,
                    layer=Layer.L1,
                    type="Document",
                    label=payload.get("title") or doc_id,
                    props=payload,
                )

            # L2: Entities
            elif kind in ("linked_entity", "entity", "mature_entity"):
                entity_id = payload.get("entity_id") or art_id
                node_type = payload.get("entity_type") or payload.get("label") or "Concept"
                label = payload.get("canonical_name") or payload.get("name") or entity_id
                tier = "system_1" if payload.get("decision_tier") == "system_1" or payload.get("is_fast_exit") else ("system_2" if payload.get("decision_tier") == "system_2" else "legacy")
                nodes_by_id[entity_id] = StudioNode(
                    id=entity_id,
                    layer=Layer.L2,
                    type=node_type,
                    label=label,
                    confidence=payload.get("confidence"),
                    empirical_accuracy=payload.get("empirical_accuracy"),
                    decision_tier=tier,
                    conformal_set_size=payload.get("conformal_set_size"),
                    is_out_of_ontology=bool(payload.get("is_out_of_ontology", False)),
                    decision_id=payload.get("decision_id"),
                    props={
                        "description": payload.get("description"),
                        "source_chunk_ids": payload.get("source_chunk_ids", []),
                    },
                )

            # L2: Triples / Relations
            elif kind in ("global_relation", "local_relation"):
                rel_id = payload.get("relation_id") or art_id
                src = payload.get("subject_entity_id") or payload.get("source_id")
                tgt = payload.get("object_entity_id") or payload.get("target_id")
                pred = payload.get("predicate", "RELATED_TO")
                if src and tgt:
                    polarity = mapper.resolve_polarity(pred)
                    if polarity is None:
                        unmapped_predicates[pred] = unmapped_predicates.get(pred, 0) + 1
                    edge_props: dict[str, Any] = {
                        "scope": payload.get("scope", "global" if kind == "global_relation" else "local"),
                    }
                    if payload.get("source_chunk_id"):
                        edge_props["source_chunk_id"] = payload.get("source_chunk_id")
                    if payload.get("supporting_chunk_ids"):
                        edge_props["supporting_chunk_ids"] = payload.get("supporting_chunk_ids")

                    tier = "system_1" if payload.get("decision_tier") == "system_1" or payload.get("is_fast_exit") else ("system_2" if payload.get("decision_tier") == "system_2" else "legacy")
                    edges.append(
                        StudioEdge(
                            id=rel_id,
                            source=src,
                            target=tgt,
                            type=pred,
                            layer=Layer.L2,
                            polarity=polarity,
                            confidence=payload.get("confidence"),
                            empirical_accuracy=payload.get("empirical_accuracy"),
                            model_confidence=payload.get("model_confidence", payload.get("calibrated_confidence")),
                            stance_probability=payload.get("stance_probability", payload.get("class_probability")),
                            inferential_force=payload.get("inferential_force"),
                            active_weight=payload.get("active_weight"),
                            is_admissible=bool(payload.get("is_admissible", True)),
                            modal_strength=payload.get("modal_strength"),
                            decision_tier=tier,
                            conformal_set_size=payload.get("conformal_set_size"),
                            decision_id=payload.get("decision_id"),
                            props=edge_props,
                        )
                    )

            # L3: Theory Atoms
            elif kind in ("theory_atom", "argument_component"):
                comp_id = payload.get("component_id") or art_id
                comp_type = payload.get("component_type") or "TheoryAtom"
                text = payload.get("text", "")
                label = (text[:60] + "...") if len(text) > 60 else (text or comp_id)
                base_sc = payload.get("base_score", payload.get("plausibility"))
                mod_str = payload.get("modal_strength", base_sc)
                tier = "system_1" if payload.get("decision_tier") == "system_1" or payload.get("is_fast_exit") else ("system_2" if payload.get("decision_tier") == "system_2" else "legacy")
                scope_t = payload.get("scope_type")
                epist_s = payload.get("epistemic_status")
                res_type = payload.get("modal_resolver") or payload.get("resolver_type")
                raw_m = payload.get("raw_modal_score") or payload.get("raw_engine_score")
                clamped_m = payload.get("is_modal_clamped") or payload.get("clamped")
                nodes_by_id[comp_id] = StudioNode(
                    id=comp_id,
                    layer=Layer.L3,
                    type=comp_type,
                    label=label,
                    partition=mapper.resolve_partition(comp_type),
                    plausibility=base_sc,
                    confidence=payload.get("confidence"),
                    empirical_accuracy=payload.get("empirical_accuracy"),
                    modal_strength=mod_str,
                    base_score=base_sc,
                    scope_type=scope_t,
                    epistemic_status=epist_s,
                    modal_resolver=res_type,
                    raw_modal_score=raw_m,
                    is_modal_clamped=clamped_m,
                    qbaf_tau=payload.get("qbaf_tau"),
                    total_weight_of_evidence=payload.get("total_weight_of_evidence"),
                    volatility_index=payload.get("volatility_index"),
                    decision_tier=tier,
                    conformal_set_size=payload.get("conformal_set_size"),
                    decision_id=payload.get("decision_id"),
                    props={
                        **payload,
                        "text": text,
                        "source_chunk_id": payload.get("source_chunk_id") or payload.get("chunk_id"),
                        "scope_type": scope_t,
                        "epistemic_status": epist_s,
                        "modal_strength": mod_str,
                        "modal_resolver": res_type,
                    },
                )

            # L3: Theory Relations
            elif kind in ("theory_relation", "argument_relation"):
                rel_id = payload.get("relation_id") or art_id
                src = payload.get("source_component_id") or payload.get("source_id")
                tgt = payload.get("target_component_id") or payload.get("target_id")
                rel_type = payload.get("relation_type", "SUPPORTS")
                if src and tgt:
                    polarity = mapper.resolve_polarity(rel_type)
                    if polarity is None:
                        unmapped_predicates[rel_type] = unmapped_predicates.get(rel_type, 0) + 1
                    tier = "system_1" if payload.get("decision_tier") == "system_1" or payload.get("is_fast_exit") else ("system_2" if payload.get("decision_tier") == "system_2" else "legacy")
                    inf_force = payload.get("inferential_force", payload.get("modal_strength", 0.75))
                    act_weight = payload.get("active_weight", payload.get("weight", inf_force))
                    edges.append(
                        StudioEdge(
                            id=rel_id,
                            source=src,
                            target=tgt,
                            type=rel_type,
                            layer=Layer.L3,
                            polarity=polarity,
                            weight=payload.get("weight", act_weight),
                            confidence=payload.get("confidence"),
                            tenability=payload.get("tenability"),
                            empirical_accuracy=payload.get("empirical_accuracy"),
                            model_confidence=payload.get("model_confidence", payload.get("calibrated_confidence")),
                            stance_probability=payload.get("stance_probability", payload.get("class_probability")),
                            inferential_force=inf_force,
                            active_weight=act_weight,
                            is_admissible=bool(payload.get("is_admissible", True)),
                            modal_strength=payload.get("modal_strength"),
                            qbaf_tau=payload.get("qbaf_tau"),
                            decision_tier=tier,
                            conformal_set_size=payload.get("conformal_set_size"),
                            decision_id=payload.get("decision_id"),
                            props={
                                "scope": payload.get("scope", "local"),
                                "source_chunk_id": payload.get("source_chunk_id") or payload.get("chunk_id"),
                            },
                        )
                    )

            # Post-processors: Theoretical Enrichment & Tenability
            elif kind == "theoretical_enrichment":
                enrichments.append(payload)

        # Hydrate theoretical enrichment artifacts if present
        if enrichments:
            for enr in enrichments:
                cid = enr.get("cluster_id")
                chunk_id = cid[len("cluster-"):] if cid and cid.startswith("cluster-") else cid
                theory_id = enr.get("theory_id")
                proj_params = enr.get("projected_parameters") or {}
                local_ts = enr.get("local_tenability")
                agg_ts = enr.get("aggregated_tenability")
                delta_star = enr.get("admissible_blur_delta")
                is_tenable = enr.get("is_tenable")
                anomalies = enr.get("anomalies") or []
                edge_tenabs = enr.get("edge_tenabilities") or {}

                tenability_info = {
                    "theory_id": theory_id,
                    "cluster_id": cid,
                    "local_score": local_ts,
                    "aggregated_score": agg_ts,
                    "tightest_blur": delta_star,
                    "is_tenable": is_tenable,
                    "anomalies": anomalies,
                }

                # Attach to matching nodes in that cluster/chunk
                for node in nodes_by_id.values():
                    node_chunk = node.props.get("source_chunk_id") or node.props.get("chunk_id")
                    if chunk_id and (node_chunk == chunk_id or node.id == chunk_id):
                        if node.parameters is None:
                            node.parameters = {}
                        node.parameters.update(proj_params)
                        node.tenability = tenability_info
                        node.props["parameters"] = node.parameters
                        node.props["tenability"] = tenability_info
                        node.props["theory_cluster"] = cid
                        node.props["theory_id"] = theory_id

                # Attach edge tenabilities
                for edge in edges:
                    rel_key = f"{edge.source}->{edge.type}->{edge.target}"
                    if rel_key in edge_tenabs:
                        score = edge_tenabs[rel_key]
                        edge.tenability = score
                        edge.props["tenability"] = score
                    elif edge.id in edge_tenabs:
                        score = edge_tenabs[edge.id]
                        edge.tenability = score
                        edge.props["tenability"] = score

        # Reify inference targets (D-21)
        reified_nodes, edges = reify_inferences(list(nodes_by_id.values()), edges)
        for node in reified_nodes:
            nodes_by_id[node.id] = node

        # Handle dangling endpoints (D-16)
        unresolved_count = 0
        for edge in edges:
            if edge.source not in nodes_by_id:
                nodes_by_id[edge.source] = StudioNode(
                    id=edge.source,
                    layer=edge.layer,
                    type="Unresolved",
                    label=edge.source,
                    resolved=False,
                )
                unresolved_count += 1
            if edge.target not in nodes_by_id:
                nodes_by_id[edge.target] = StudioNode(
                    id=edge.target,
                    layer=edge.layer,
                    type="Unresolved",
                    label=edge.target,
                    resolved=False,
                )
                unresolved_count += 1

        # Calculate degrees
        for edge in edges:
            if edge.source in nodes_by_id:
                nodes_by_id[edge.source].degree += 1
            if edge.target in nodes_by_id:
                nodes_by_id[edge.target].degree += 1

        # Layer counts before budgeting
        layer_counts = {
            1: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L1),
            2: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L2),
            3: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L3),
        }

        # Apply budget
        total_nodes = len(nodes_by_id)
        truncated = False
        dropped_count = 0

        if total_nodes > budget:
            truncated = True
            dropped_count = total_nodes - budget
            sorted_nodes = sorted(nodes_by_id.values(), key=lambda n: n.degree, reverse=True)
            active_nodes = sorted_nodes[:budget]
            active_ids = {n.id for n in active_nodes}
            nodes = active_nodes
            edges = [e for e in edges if e.source in active_ids and e.target in active_ids]
        else:
            nodes = list(nodes_by_id.values())

        graph_version = f"{run_id}:{len(nodes)}:{len(edges)}"
        schema_version = schema_dict.get("version", "v1") if isinstance(schema_dict, dict) else "v1"

        return GraphView(
            nodes=nodes,
            edges=edges,
            source="artifacts",
            run_id=run_id,
            graph_version=graph_version,
            schema_version=schema_version,
            truncated=truncated,
            dropped_count=dropped_count,
            unmapped_predicates=unmapped_predicates,
            unresolved_count=unresolved_count,
            layer_counts=layer_counts,
        )

    def get_evidence(self, run_id: str, node_id: str) -> EvidenceTrail:
        """Trace provenance of a graph node back to its source text chunks.

        Parameters
        ----------
        run_id : str
            Identifier of run.
        node_id : str
            Identifier of node (L2 entity or L3 atom).

        Returns
        -------
        EvidenceTrail
            Structured provenance trail with chunks, offsets, and resolution modes (D-19).
        """
        chunks_map: dict[str, str] = {}
        all_envelopes: list[dict[str, Any]] = []

        for data, _ in self._collect_run_envelopes(run_id):
            all_envelopes.append(data)
            if data.get("kind") == "chunk":
                cid = data.get("payload", {}).get("id") or data.get("artifact_id")
                txt = data.get("payload", {}).get("text", "")
                if cid:
                    chunks_map[cid] = txt

        # Locate node envelope
        target_env = None
        for env in all_envelopes:
            payload = env.get("payload", {})
            if (
                payload.get("entity_id") == node_id
                or payload.get("component_id") == node_id
                or payload.get("id") == node_id
                or env.get("artifact_id") == node_id
            ):
                target_env = env
                break

        kind = target_env.get("kind", "") if target_env else ""
        evidence_chunks: list[EvidenceChunk] = []

        # Case 1: L2 Entity -> look for entity_mention envelopes
        if kind in ("linked_entity", "entity", "mature_entity"):
            layer = 2
            entity_name = target_env.get("payload", {}).get("canonical_name", node_id)
            mentions = [
                e for e in all_envelopes
                if e.get("kind") == "entity_mention"
                and (
                    e.get("payload", {}).get("surface_form") == entity_name
                    or node_id in e.get("provenance", {}).get("upstream_artifact_ids", [])
                )
            ]

            # Group spans by chunk_id
            chunk_spans: dict[str, list[EvidenceSpan]] = {}
            for m in mentions:
                mpay = m.get("payload", {})
                cid = mpay.get("chunk_id") or m.get("provenance", {}).get("source_chunk_id")
                if not cid:
                    continue
                start = mpay.get("start_char")
                end = mpay.get("end_char")
                text = mpay.get("surface_form") or entity_name
                chunk_text = chunks_map.get(cid, "")

                if start is not None and end is not None:
                    mode = "exact"
                else:
                    idx = chunk_text.find(text) if text else -1
                    if idx != -1:
                        start = idx
                        end = idx + len(text)
                        mode = "substring"
                    else:
                        start = 0
                        end = len(chunk_text)
                        mode = "whole_chunk"

                span = EvidenceSpan(start_char=start, end_char=end, text=text, mode=mode)
                chunk_spans.setdefault(cid, []).append(span)

            for cid, spans in chunk_spans.items():
                evidence_chunks.append(
                    EvidenceChunk(
                        chunk_id=cid,
                        text=chunks_map.get(cid, ""),
                        spans=spans,
                    )
                )

        # Case 2: L3 Theory Atom
        elif kind in ("theory_atom", "argument_component"):
            layer = 3
            atom_text = target_env.get("payload", {}).get("text", "")
            cid = target_env.get("payload", {}).get("chunk_id") or target_env.get("provenance", {}).get("source_chunk_id")

            if cid and cid in chunks_map:
                chunk_text = chunks_map[cid]
                idx = chunk_text.find(atom_text) if atom_text else -1
                if idx != -1:
                    start = idx
                    end = idx + len(atom_text)
                    mode = "substring"
                else:
                    start = 0
                    end = len(chunk_text)
                    mode = "whole_chunk"

                span = EvidenceSpan(start_char=start, end_char=end, text=atom_text, mode=mode)
                evidence_chunks.append(
                    EvidenceChunk(
                        chunk_id=cid,
                        text=chunk_text,
                        spans=[span],
                    )
                )
        else:
            layer = 1

        return EvidenceTrail(node_id=node_id, layer=layer, chunks=evidence_chunks)
