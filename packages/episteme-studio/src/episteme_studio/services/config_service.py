"""Configuration service managing profiles, provenance tracking, and invalidation previews."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.prompts.providers import (
    DefaultPromptProvider,
    FilePromptProvider,
    LangfusePromptProvider,
)

from episteme_studio.adapters.config_adapter import (
    DEFAULT_PHASE_ARTIFACT_ESTIMATES,
    PHASE_INDEX_TO_NAME,
    ConfigAdapter,
)
from episteme_studio.domain.config import (
    AvailableInputDoc,
    ConfigPatch,
    ConfigView,
    FieldProvenance,
    InvalidationPreview,
    LangfuseStatusResponse,
    PromptResolveResponse,
    ResolvedPromptItem,
)
from episteme_studio.settings import check_env_var_set, get_env_var

# Environment variable mappings for pipeline configuration fields
ENV_VAR_MAPPINGS: dict[str, str] = {
    "models.llm_model": "LLM_MODEL",
    "models.embedding_model": "EMBED_MODEL",
    "models.reranker_model": "RERANKER_MODEL",
    "models.llm_api_base": "LITELLM_API_BASE",
    "models.thinking_level": "LLM_THINKING_LEVEL",
}

SECRET_KEY_PATTERN = re.compile(r"(key|secret|password|token|credential)", re.IGNORECASE)

PROFILES: dict[str, dict[str, Any]] = {
    "default": {},
    "eval": {
        "phase5.argument_clustering_enabled": True,
        "execution.allow_phase_reuse": True,
    },
    "fast": {
        "phase2.batch_size": 20,
        "phase3.max_candidates_per_entity_pair": 50,
        "phase3.dense_similarity_threshold": 0.7,
    },
}


class ConfigService:
    """Service providing effective configuration views, secret masking, and cache invalidation previews."""

    def __init__(
        self,
        adapter: ConfigAdapter | None = None,
        reader: ArtifactReader | None = None,
    ) -> None:
        self.adapter = adapter or ConfigAdapter()
        self.reader = reader

    def list_profiles(self) -> list[str]:
        """List available configuration profile identifiers.

        Returns
        -------
        list of str
            Available configuration profile names.
        """
        return list(PROFILES.keys())

    def get_effective_config(
        self,
        profile_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> ConfigView:
        """Resolve effective pipeline configuration with secret redaction and provenance.

        Parameters
        ----------
        profile_id : str or None, optional
            Identifier of base profile to apply before overrides.
        overrides : dict of str to Any, optional
            Explicit dot-notation parameter overrides.

        Returns
        -------
        ConfigView
            Resolved configuration with provenance and masked secrets.
        """
        base_cfg = self.adapter.get_config_from_env()

        # Apply profile if requested
        profile_patch: dict[str, Any] = {}
        if profile_id and profile_id in PROFILES:
            profile_patch = PROFILES[profile_id]
            if profile_patch:
                base_cfg = self.adapter.apply_patch(base_cfg, profile_patch)

        # Apply explicit overrides if provided
        override_patch = overrides or {}
        if override_patch:
            base_cfg = self.adapter.apply_patch(base_cfg, override_patch)

        raw_dict = base_cfg.model_dump(mode="python")
        flattened = self.adapter.flatten_dict(raw_dict)

        values: dict[str, Any] = {}
        provenance: dict[str, FieldProvenance] = {}

        for path, val in flattened.items():
            # Check secret masking
            leaf_key = path.split(".")[-1]
            if SECRET_KEY_PATTERN.search(leaf_key) and isinstance(val, str) and val:
                values[path] = "***"
            else:
                values[path] = val

            # Determine provenance
            if path in override_patch:
                provenance[path] = FieldProvenance.OVERRIDE
            elif path in profile_patch:
                provenance[path] = FieldProvenance.PROFILE
            elif path in ENV_VAR_MAPPINGS and check_env_var_set(ENV_VAR_MAPPINGS[path]):
                provenance[path] = FieldProvenance.ENV
            else:
                provenance[path] = FieldProvenance.DEFAULT

        schema_version = str(getattr(base_cfg.graph_schema, "version", "v1"))

        return ConfigView(
            values=values,
            provenance=provenance,
            profile_id=profile_id,
            schema_version=schema_version,
        )

    def preview_invalidation(
        self,
        patch: dict[str, Any],
        profile_id: str | None = None,
        parent_run_id: str | None = None,
        source_paths: list[str] | None = None,
        bib_paths: list[str] | None = None,
        structural_anchor: Any | None = None,
    ) -> InvalidationPreview:
        """Preview which execution phases will be invalidated by a configuration patch.

        Per D-14, changes to ``models.*`` produce ZERO phase invalidations because
        model configurations are observability metadata not included in phase fingerprints.

        Parameters
        ----------
        patch : dict of str to Any
            Proposed dot-notation configuration updates.
        profile_id : str or None, optional
            Base configuration profile name.
        parent_run_id : str or None, optional
            Parent run identifier to evaluate cache invalidation against.
        source_paths : list of str or None, optional
            Proposed input source paths.
        bib_paths : list of str or None, optional
            Proposed bibliography reference paths.
        structural_anchor : Any or None, optional
            Proposed global structural anchor.

        Returns
        -------
        InvalidationPreview
            Detailed impact analysis of invalidated versus reused phases.
        """
        if isinstance(patch, ConfigPatch):
            if profile_id is None:
                profile_id = patch.profile_id
            if parent_run_id is None:
                parent_run_id = patch.parent_run_id
            if source_paths is None:
                source_paths = patch.source_paths
            if bib_paths is None:
                bib_paths = patch.bib_paths
            if structural_anchor is None:
                structural_anchor = patch.structural_anchor
            patch = patch.patch

        parent_manifest = None
        if parent_run_id and self.reader:
            parent_manifest = self.reader.get_manifest(parent_run_id)

        # Reconstruct base config: use parent config snapshot if available, else env + profile
        if parent_manifest and parent_manifest.get("config_snapshot"):
            try:
                base_cfg = PipelineConfig.model_validate(parent_manifest["config_snapshot"])
            except Exception:
                base_cfg = self.adapter.get_config_from_env()
        else:
            base_cfg = self.adapter.get_config_from_env()
            if profile_id and profile_id in PROFILES:
                base_cfg = self.adapter.apply_patch(base_cfg, PROFILES[profile_id])

        # Validate and apply patch
        patched_cfg = self.adapter.apply_patch(base_cfg, patch)

        fps_before = self.adapter.compute_phase_fingerprints(base_cfg)
        fps_after = self.adapter.compute_phase_fingerprints(patched_cfg)

        if parent_manifest:
            changed_fps: dict[str, tuple[str | None, str | None]] = {}
            earliest_invalid: int | None = None
            reason: str = "all-reused"

            # 1. Check for incomplete phases in parent run
            prior_records = parent_manifest.get("phase_records", [])
            prior_completed = {
                (pr.get("phase_ordinal") or pr.get("ordinal"))
                for pr in prior_records
                if pr.get("status") == "completed"
            }
            for ordinal in range(1, 9):
                if ordinal not in prior_completed:
                    earliest_invalid = ordinal
                    reason = f"prior-phase-incomplete:{PHASE_INDEX_TO_NAME.get(ordinal, f'Phase {ordinal}')}"
                    break

            # 2. Check for input source/anchor changes (Phase 1+)
            if earliest_invalid is None and source_paths is not None:
                from episteme_pipeline.runs.fingerprints import (
                    fingerprint_existing_sources,
                    fingerprint_structural_anchor,
                    stable_fingerprint,
                )

                source_fp = fingerprint_existing_sources(
                    [str(p) for p in (source_paths or [])],
                    [str(p) for p in (bib_paths or [])],
                )
                anchor_fp = fingerprint_structural_anchor(structural_anchor)
                input_fp = (
                    stable_fingerprint({"source": source_fp, "anchor": anchor_fp})
                    if anchor_fp is not None
                    else source_fp
                )
                prior_input_fp = parent_manifest.get("input_fingerprint") or parent_manifest.get("source_fingerprint")
                if prior_input_fp and input_fp != prior_input_fp:
                    earliest_invalid = 1
                    reason = "source-changed"
                    changed_fps["input_sources"] = (prior_input_fp, input_fp)

            # 3. Check for phase config changes
            prior_phase_fps = parent_manifest.get("phase_config_fingerprints", {})
            for ordinal in range(1, 9):
                key = f"phase_{ordinal}"
                prior_fp = prior_phase_fps.get(key) or prior_phase_fps.get(str(ordinal)) or fps_before.get(ordinal)
                after_fp = fps_after.get(ordinal)
                if prior_fp != after_fp:
                    changed_fps[key] = (prior_fp, after_fp)

            has_schema_changes = any(k.startswith("graph_schema.") for k in patch.keys())
            if has_schema_changes and (earliest_invalid is None or earliest_invalid > 2):
                earliest_invalid = 2
                changed_fps["graph_schema"] = (None, "modified")

            if earliest_invalid is None and changed_fps:
                phase_keys = [k for k in changed_fps if k.startswith("phase_")]
                if phase_keys:
                    earliest_invalid = min(int(k.split("_")[1]) for k in phase_keys)
                    phase_name = PHASE_INDEX_TO_NAME.get(earliest_invalid, f"Phase {earliest_invalid}")
                    reason = f"config-changed:{phase_name}"

            if earliest_invalid is None:
                return InvalidationPreview(
                    invalidated_phases=[],
                    reused_phases=list(range(1, 9)),
                    changed_fingerprints={},
                    reason="all-reused",
                    estimated_artifact_loss=0,
                )

            invalidated = [i for i in range(1, 9) if i >= earliest_invalid]
            reused = [i for i in range(1, 9) if i < earliest_invalid]
            estimated_loss = sum(DEFAULT_PHASE_ARTIFACT_ESTIMATES.get(i, 2) for i in invalidated)

            return InvalidationPreview(
                invalidated_phases=invalidated,
                reused_phases=reused,
                changed_fingerprints=changed_fps,
                reason=reason,
                estimated_artifact_loss=estimated_loss,
            )

        changed_fps: dict[str, tuple[str | None, str | None]] = {}
        for ordinal in range(1, 9):
            before = fps_before.get(ordinal)
            after = fps_after.get(ordinal)
            if before != after:
                changed_fps[f"phase_{ordinal}"] = (before, after)

        has_schema_changes = any(k.startswith("graph_schema.") for k in patch.keys())

        if not changed_fps and not has_schema_changes:
            return InvalidationPreview(
                invalidated_phases=[],
                reused_phases=list(range(1, 9)),
                changed_fingerprints={},
                reason="all-reused",
                estimated_artifact_loss=0,
            )

        # Find the earliest invalidated phase (schema changes affect Phase 2 onwards)
        if changed_fps:
            earliest_invalid = min(
                int(key.split("_")[1]) for key in changed_fps.keys()
            )
            if has_schema_changes and earliest_invalid > 2:
                earliest_invalid = 2
        else:
            earliest_invalid = 2
            changed_fps["graph_schema"] = (None, "modified")

        invalidated = [i for i in range(1, 9) if i >= earliest_invalid]
        reused = [i for i in range(1, 9) if i < earliest_invalid]
        phase_name = PHASE_INDEX_TO_NAME.get(earliest_invalid, f"Phase {earliest_invalid}")
        reason = f"config-changed:{phase_name}"
        estimated_loss = sum(DEFAULT_PHASE_ARTIFACT_ESTIMATES.get(i, 2) for i in invalidated)

        return InvalidationPreview(
            invalidated_phases=invalidated,
            reused_phases=reused,
            changed_fingerprints=changed_fps,
            reason=reason,
            estimated_artifact_loss=estimated_loss,
        )

    def resolve_prompts(
        self,
        provider: str = "default",
        label_or_version: str | int = "production",
        prompts_dir: str | None = None,
        host: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
    ) -> PromptResolveResponse:
        """Resolve all structured prompt bundles via the specified provider.

        Parameters
        ----------
        provider : str, default "default"
            Target prompt provider ('default', 'langfuse', or 'file').
        label_or_version : str or int, default "production"
            Target deployment label (e.g. 'production', 'staging') or version.
        prompts_dir : str or None, optional
            Disk directory path if provider is 'file'.
        host : str or None, optional
            Custom Langfuse host URL.
        public_key : str or None, optional
            Custom Langfuse public key.
        secret_key : str or None, optional
            Custom Langfuse secret key.

        Returns
        -------
        PromptResolveResponse
            Dictionary of canonical prompt bundles with templates and version metadata.
        """
        prompt_names = [
            "ner_extraction",
            "entity_linking",
            "global_relation",
            "entity_synthesis",
            "adu_segmentation",
            "acc_classification",
            "arc_classification",
        ]

        warning: str | None = None
        active_provider = provider.lower()

        if active_provider == "langfuse":
            try:
                lf_client = None
                if public_key and secret_key:
                    from langfuse import Langfuse
                    active_host = (
                        host
                        or get_env_var("EPISTEME_STUDIO_LANGFUSE_HOST")
                        or get_env_var("LANGFUSE_HOST")
                        or get_env_var("LANGFUSE_BASE_URL")
                        or "http://localhost:3000"
                    )
                    lf_client = Langfuse(public_key=public_key, secret_key=secret_key, host=active_host)
                lf_provider = LangfusePromptProvider(client=lf_client, auto_create_missing=False)
                # Test connectivity
                if lf_provider.client is None:
                    warning = "Langfuse client unconfigured or unreachable; fell back to default prompt templates."
                    active_provider = "default"
                    provider_instance = DefaultPromptProvider()
                else:
                    provider_instance = lf_provider
            except Exception as exc:
                warning = f"Langfuse connection failed: {exc}; fell back to default prompt templates."
                active_provider = "default"
                provider_instance = DefaultPromptProvider()
        elif active_provider == "file" and prompts_dir:
            provider_instance = FilePromptProvider(prompts_dir=prompts_dir)
        else:
            active_provider = "default"
            provider_instance = DefaultPromptProvider()

        bundles: dict[str, ResolvedPromptItem] = {}
        for name in prompt_names:
            try:
                bundle = provider_instance.get_bundle(name, label_or_version)
                bundles[name] = ResolvedPromptItem(
                    name=bundle.name,
                    version=bundle.version,
                    label=bundle.label,
                    provider=bundle.provider,
                    direct_template=bundle.direct_template,
                    reasoning_template=bundle.reasoning_template,
                    format_template=bundle.format_template,
                    gleaning_template=bundle.gleaning_template,
                    metadata=bundle.metadata or {},
                )
            except Exception:
                # Fallback to default bundle for this specific prompt
                def_bundle = DefaultPromptProvider().get_bundle(name)
                bundles[name] = ResolvedPromptItem(
                    name=def_bundle.name,
                    version=def_bundle.version,
                    label=str(label_or_version),
                    provider="default",
                    direct_template=def_bundle.direct_template,
                    reasoning_template=def_bundle.reasoning_template,
                    format_template=def_bundle.format_template,
                    gleaning_template=def_bundle.gleaning_template,
                    metadata=def_bundle.metadata or {},
                )
                if not warning:
                    warning = f"Failed to resolve {name!r} from {provider}; fell back to default."

        return PromptResolveResponse(
            provider=active_provider,
            label_or_version=str(label_or_version),
            bundles=bundles,
            warning=warning,
        )

    def list_available_inputs(self) -> list[AvailableInputDoc]:
        """Discover available candidate input documents in the repository.

        Returns
        -------
        list of AvailableInputDoc
            Discovered markdown and text files suitable for pipeline execution.
        """
        from pathlib import Path

        discovered: list[AvailableInputDoc] = []
        seen_paths: set[str] = set()

        search_dirs = [
            Path("data/uploads"),
            Path("examples/text"),
            Path("examples"),
            Path("tests/fixtures"),
            Path("data"),
        ]

        for sdir in search_dirs:
            if not sdir.is_dir():
                continue
            for ext in ("*.md", "*.txt", "*.json", "*.tex", "*.bib"):
                for p in sdir.glob(ext):
                    if p.name.startswith((".", "_")) or p.name in ("README.md", "SPEC.md", "CONTRACT.md"):
                        continue
                    rel_str = str(p)
                    if rel_str not in seen_paths:
                        seen_paths.add(rel_str)
                        try:
                            size = p.stat().st_size
                        except OSError:
                            size = 0
                        discovered.append(
                            AvailableInputDoc(
                                path=rel_str,
                                name=p.name,
                                size_bytes=size,
                                description=f"Corpus file in {sdir}",
                            )
                        )

        # Ensure fallback demo input always exists in list
        if not any(d.name == "teachers_expectancies.md" for d in discovered):
            discovered.insert(
                0,
                AvailableInputDoc(
                    path="examples/text/teachers_expectancies.md",
                    name="teachers_expectancies.md",
                    size_bytes=14200,
                    description="Standard social psychology theory text corpus",
                ),
            )

        return sorted(discovered, key=lambda d: d.name)

    def upload_input(self, filename: str, content: bytes) -> AvailableInputDoc:
        """Store an uploaded candidate document in repository data/uploads directory.

        Parameters
        ----------
        filename : str
            Raw filename of the uploaded document.
        content : bytes
            Binary payload of the uploaded document.

        Returns
        -------
        AvailableInputDoc
            Metadata describing the saved input document ready for pipeline execution.
        """
        from pathlib import Path

        safe_name = Path(filename).name
        if not safe_name or safe_name.startswith("."):
            safe_name = f"uploaded_{safe_name.lstrip('.') or 'input.txt'}"

        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / safe_name
        dest.write_bytes(content)

        return AvailableInputDoc(
            path=str(dest),
            name=safe_name,
            size_bytes=len(content),
            description="User-uploaded document in data/uploads",
        )

    def resolve_run_config(
        self,
        profile_id: str | None = None,
        patch: dict[str, Any] | None = None,
        parent_run_id: str | None = None,
    ) -> PipelineConfig:
        """Produce a validated PipelineConfig from environment, profile, and staged patch.

        Parameters
        ----------
        profile_id : str or None, optional
            Configuration profile identifier.
        patch : dict of str to Any or None, optional
            Dot-delimited parameter overrides.
        parent_run_id : str or None, optional
            Parent run identifier to inherit base configuration from.

        Returns
        -------
        PipelineConfig
            Fully resolved and validated pipeline configuration.
        """
        if parent_run_id and self.reader:
            parent_manifest = self.reader.get_manifest(parent_run_id)
            if parent_manifest and parent_manifest.get("config_snapshot"):
                try:
                    base_cfg = PipelineConfig.model_validate(parent_manifest["config_snapshot"])
                except Exception:
                    base_cfg = self.adapter.get_config_from_env()
            else:
                base_cfg = self.adapter.get_config_from_env()
        else:
            base_cfg = self.adapter.get_config_from_env()

        if profile_id and profile_id in PROFILES:
            prof_patch = PROFILES[profile_id]
            if prof_patch:
                base_cfg = self.adapter.apply_patch(base_cfg, prof_patch)

        if patch:
            base_cfg = self.adapter.apply_patch(base_cfg, patch)

        return base_cfg

    def test_langfuse(
        self,
        host: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
    ) -> LangfuseStatusResponse:
        """Test authentication against a specified or configured Langfuse instance.

        Parameters
        ----------
        host : str or None, optional
            Target host URL, defaulting to 'http://localhost:3000'.
        public_key : str or None, optional
            Candidate public key to test.
        secret_key : str or None, optional
            Candidate secret key to test.

        Returns
        -------
        LangfuseStatusResponse
            Result of the authentication probe with connection status.
        """
        active_host = (
            host
            or get_env_var("EPISTEME_STUDIO_LANGFUSE_HOST")
            or get_env_var("LANGFUSE_HOST")
            or get_env_var("LANGFUSE_BASE_URL")
            or "http://localhost:3000"
        )
        active_pk = public_key if public_key is not None else (get_env_var("LANGFUSE_PUBLIC_KEY") or "")
        active_sk = secret_key if secret_key is not None else (get_env_var("LANGFUSE_SECRET_KEY") or "")

        has_pk = bool(active_pk.strip())
        has_sk = bool(active_sk.strip())
        configured = has_pk and has_sk
        pk_preview = f"{active_pk[:7]}...{active_pk[-4:]}" if len(active_pk) > 12 else ("pk-lf-***" if has_pk else None)

        connected = False
        message = None

        if configured:
            try:
                from langfuse import Langfuse
                client = Langfuse(
                    public_key=active_pk,
                    secret_key=active_sk,
                    host=active_host,
                )
                if hasattr(client, "auth_check"):
                    connected = bool(client.auth_check())
                    message = f"Authenticated with {active_host}" if connected else f"Authentication check returned False for {active_host}"
                else:
                    connected = True
                    message = f"Client initialized against {active_host}"
            except Exception as exc:
                connected = False
                message = f"Connection failed to {active_host}: {exc}"
        else:
            message = "LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not configured."

        return LangfuseStatusResponse(
            configured=configured,
            host=active_host,
            has_public_key=has_pk,
            public_key_preview=pk_preview,
            has_secret_key=has_sk,
            telemetry_enabled=has_pk,
            connected=connected,
            message=message,
        )

    def get_langfuse_status(self) -> LangfuseStatusResponse:
        """Query active Langfuse connectivity and telemetry status.

        Returns
        -------
        LangfuseStatusResponse
            Resolved connection status, masked keys, and host details.
        """
        return self.test_langfuse()
