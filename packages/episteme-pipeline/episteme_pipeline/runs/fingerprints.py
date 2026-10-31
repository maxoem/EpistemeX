"""Fingerprint helpers for run and phase invalidation decisions."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def stable_fingerprint(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_SimpleTypes = str | int | float | bool | type(None)


def _is_fully_serializable(value: Any) -> bool:
    """Recursively check if a value is JSON-serializable by our constraints."""
    if isinstance(value, _SimpleTypes):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_fully_serializable(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(k, str) and _is_fully_serializable(v) for k, v in value.items()
        )
    return False


def fingerprint_phase_config(config: Any) -> str:
    if hasattr(config, "model_dump"):
        return stable_fingerprint(config.model_dump(mode="json"))
    phase_dict = getattr(config, "__dict__", None)
    if isinstance(phase_dict, dict):
        serializable = {
            key: value
            for key, value in phase_dict.items()
            if _is_fully_serializable(value)
        }
        if serializable:
            return stable_fingerprint(serializable)
    return stable_fingerprint({"class": config.__class__.__name__})


def fingerprint_phase_config_nested(config: Any) -> dict[str, str]:
    """Compute fine-grained nested config fingerprints per leaf field.

    Unlike `fingerprint_phase_config` which serializes the entire config
    as one blob, this computes a separate stable fingerprint for each
    leaf field in the config. This lets invalidation detect which
    specific leaf changed rather than just that "the config changed".
    """
    if hasattr(config, "model_dump"):
        dumped = config.model_dump(mode="json")
    else:
        dumped: dict[str, Any] = {}
        phase_dict = getattr(config, "__dict__", None)
        if isinstance(phase_dict, dict):
            for key, value in phase_dict.items():
                if hasattr(value, "model_dump"):
                    dumped[key] = value.model_dump(mode="json")
                elif _is_fully_serializable(value):
                    dumped[key] = value

    return _fingerprint_nested_leafs(dumped, prefix="")


def _fingerprint_nested_leafs(obj: Any, prefix: str) -> dict[str, str]:
    """Recursively compute a fingerprint for each leaf value."""
    result: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                sub = _fingerprint_nested_leafs(value, new_prefix)
                if sub:
                    result.update(sub)
                else:
                    result[new_prefix] = stable_fingerprint(value)
            elif _is_fully_serializable(value):
                result[new_prefix] = stable_fingerprint(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_key = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                sub = _fingerprint_nested_leafs(item, new_key)
                if sub:
                    result.update(sub)
                else:
                    result[new_key] = stable_fingerprint(item)
            elif _is_fully_serializable(item):
                result[new_key] = stable_fingerprint(item)
    elif _is_fully_serializable(obj) and prefix:
        result[prefix] = stable_fingerprint(obj)
    return result


def fingerprint_method(method_obj: Any) -> str | None:
    """Compute a fingerprint for a method object (e.g., LLM, embedding model, extractor).

    Prefers an explicit contract: if the object exposes ``fingerprint()``
    returning a JSON-serialisable value, that value *is* the fingerprint input.
    Implement it on any component whose behaviour depends on state this module
    cannot see — a SentenceTransformer revision, a quantisation setting, a
    reranker's activation function.

    Otherwise this falls back to probing a fixed list of well-known attributes
    (model name, temperature, max_tokens, dimensions, …). That fallback is
    best-effort and silently incomplete by construction (O-15): anything not on
    the list is invisible to invalidation, so a run can be reused after a change
    that should have invalidated it.

    Returns None if the object is None or exposes nothing recognisable.
    """
    if method_obj is None:
        return None

    explicit = getattr(method_obj, "fingerprint", None)
    if callable(explicit):
        try:
            value = explicit()
            if _is_fully_serializable(value):
                return stable_fingerprint(
                    {"class": method_obj.__class__.__name__, "fingerprint": value}
                )
        except Exception as ex:
            logger.exception(ex)

    fingerprint_data: dict[str, Any] = {"class": method_obj.__class__.__name__}
    model_name = getattr(method_obj, "model_name", None)
    if model_name:
        fingerprint_data["model"] = str(model_name)
    model_name_or_provider = getattr(method_obj, "model_name_or_provider", None)
    if model_name_or_provider:
        fingerprint_data["model_provider"] = str(model_name_or_provider)
    model = getattr(method_obj, "model", None)
    if model is not None:
        fingerprint_data["model_ref"] = str(model)

    # API version detection — important for LLM API changes
    api_version = getattr(method_obj, "api_version", None)
    if api_version is not None and _is_fully_serializable(api_version):
        fingerprint_data["api_version"] = str(api_version)

    # Provider/endpoint configuration
    base_url = getattr(method_obj, "base_url", None)
    if base_url is not None and _is_fully_serializable(base_url):
        fingerprint_data["base_url"] = str(base_url)

    # Runtime parameters that affect model output
    temperature = getattr(method_obj, "temperature", None)
    if temperature is not None and _is_fully_serializable(temperature):
        fingerprint_data["temperature"] = temperature

    max_tokens = getattr(method_obj, "max_tokens", None)
    if max_tokens is not None and _is_fully_serializable(max_tokens):
        fingerprint_data["max_tokens"] = max_tokens

    top_p = getattr(method_obj, "top_p", None)
    if top_p is not None and _is_fully_serializable(top_p):
        fingerprint_data["top_p"] = top_p

    n = getattr(method_obj, "n", None)
    if n is not None and _is_fully_serializable(n):
        fingerprint_data["n"] = n

    # Embedding-specific parameters
    dimensions = getattr(method_obj, "dimensions", None)
    if dimensions is not None and _is_fully_serializable(dimensions):
        fingerprint_data["dimensions"] = dimensions

    embedding_api_version = getattr(method_obj, "embedding_api_version", None)
    if embedding_api_version is not None and _is_fully_serializable(
        embedding_api_version
    ):
        fingerprint_data["embedding_api_version"] = str(embedding_api_version)

    # Catch model_kwargs / kwargs that may contain additional params
    model_kwargs = getattr(method_obj, "model_kwargs", None)
    if (
        model_kwargs
        and isinstance(model_kwargs, dict)
        and _is_fully_serializable(model_kwargs)
    ):
        fingerprint_data["model_kwargs"] = model_kwargs

    return stable_fingerprint(fingerprint_data)


def fingerprint_existing_sources(
    source_paths: list[str], bib_paths: list[str] | None = None
) -> str:
    records: list[dict[str, Any]] = []
    all_paths = [("source", p) for p in sorted(source_paths)]
    if bib_paths:
        all_paths.extend(("bib", p) for p in sorted(bib_paths))

    for kind, source_path in all_paths:
        path = Path(source_path)
        if path.exists():
            stat = path.stat()
            try:
                content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, PermissionError):
                content_hash = None
            records.append(
                {
                    "kind": kind,
                    "path": source_path,
                    "size": stat.st_size,
                    "content_hash": content_hash,
                }
            )
        else:
            records.append({"kind": kind, "path": source_path, "missing": True})
    return stable_fingerprint(records)


def fingerprint_structural_anchor(anchor: Any | None) -> str | None:
    """
    Compute a deterministic SHA-256 fingerprint for a GlobalStructuralAnchor.

    Parameters
    ----------
    anchor : GlobalStructuralAnchor | None
        Target structural anchor instance to hash.

    Returns
    -------
    str | None
        Deterministic hexadecimal SHA-256 fingerprint string, or None if anchor is None.
    """
    if anchor is None:
        return None

    from pydantic import BaseModel

    if isinstance(anchor, BaseModel):
        dumped = anchor.model_dump(mode="json")
    else:
        dumped = str(anchor)
    return stable_fingerprint(dumped)


def compute_document_fingerprints(source_paths: list[str]) -> dict[str, str]:
    """
    Compute individual deterministic SHA-256 content fingerprints per document.

    Parameters
    ----------
    source_paths : list[str]
        File paths to the source documents.

    Returns
    -------
    dict[str, str]
        Mapping from document identifiers and source paths to their
        hexadecimal SHA-256 content hashes.
    """
    from episteme_pipeline.phases.phase1_foundation.provenance import (
        canonical_source,
        doc_id,
    )

    fps: dict[str, str] = {}
    for source_path in sorted(source_paths):
        path = Path(source_path)
        if path.exists():
            try:
                content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, PermissionError):
                content_hash = ""
        else:
            content_hash = "missing"
        d_id = doc_id(path)
        fps[d_id] = content_hash
        canon = canonical_source(path)
        fps[canon] = content_hash
        fps[str(source_path)] = content_hash
    return fps


def fingerprint_curation_ledger(ledger: Any | None) -> str | None:
    """
    Compute a deterministic SHA-256 fingerprint for an EpistemicCurationLedger.

    Parameters
    ----------
    ledger : EpistemicCurationLedger | None
        Target curation ledger instance to hash.

    Returns
    -------
    str | None
        Deterministic hexadecimal SHA-256 fingerprint string, or None if ledger is None.
    """
    if ledger is None:
        return None

    from pydantic import BaseModel

    if isinstance(ledger, BaseModel):
        dumped = ledger.model_dump(mode="json")
    else:
        dumped = str(ledger)
    return stable_fingerprint(dumped)


def is_phase_unchanged(
    manifest: Any,
    prior_manifest: Any,
    phase_key: str,
    phase_name: str,
) -> bool:
    """
    Check if a phase's configuration and method fingerprints are identical to prior run.

    Parameters
    ----------
    manifest : RunManifest
        Current run manifest containing phase config and method fingerprints.
    prior_manifest : RunManifest
        Prior run manifest to compare against.
    phase_key : str
        Unique phase machine key (e.g. 'phase1', 'phase4').
    phase_name : str
        Canonical phase name (e.g. 'Phase 1: Data Foundation').

    Returns
    -------
    bool
        True if the phase's config and all associated method fingerprints are unchanged.
    """
    if manifest.phase_config_fingerprints.get(phase_key) != prior_manifest.phase_config_fingerprints.get(phase_key):
        return False
    for k, v in manifest.method_fingerprints.items():
        if (
            (k.startswith(f"{phase_name}.") or k.startswith(f"{phase_key}."))
            and prior_manifest.method_fingerprints.get(k) != v
        ):
            return False
    for k, v in prior_manifest.method_fingerprints.items():
        if (
            (k.startswith(f"{phase_name}.") or k.startswith(f"{phase_key}."))
            and manifest.method_fingerprints.get(k) != v
        ):
            return False
    return True




