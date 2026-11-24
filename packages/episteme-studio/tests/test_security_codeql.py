"""Unit tests for CodeQL security remediations across studio and pipeline."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest
from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.app import create_app
from episteme_studio.security import (
    resolve_safe_child,
    validate_safe_identifier,
)
from episteme_studio.services.run_service import RunService
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


def test_validate_safe_identifier_accepts_valid_ids() -> None:
    """Verify valid identifiers pass validation unchanged."""
    assert validate_safe_identifier("run_123") == "run_123"
    assert validate_safe_identifier("eval-abc.1") == "eval-abc.1"


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        ".",
        "..",
        "../x",
        "a/b",
        "a\\b",
        "run\x00id",
        "run id",
    ],
)
def test_validate_safe_identifier_rejects_unsafe_ids(bad_id: str) -> None:
    """Verify path-traversal and malformed identifiers raise ValueError."""
    with pytest.raises(ValueError, match="Invalid"):
        validate_safe_identifier(bad_id)


def test_resolve_safe_child_enforces_containment(tmp_path: Path) -> None:
    """Verify resolve_safe_child permits normal children and blocks escapes."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    sibling_dir = tmp_path / "base_evil"
    sibling_dir.mkdir()
    (sibling_dir / "secret.txt").write_text("secret", encoding="utf-8")

    child = resolve_safe_child(base_dir, "nested", "file.json")
    assert child == (base_dir / "nested" / "file.json").resolve()

    with pytest.raises(ValueError, match="escapes allowed directory"):
        resolve_safe_child(base_dir, "../base_evil/secret.txt")

    with pytest.raises(ValueError, match="must be relative"):
        resolve_safe_child(base_dir, str(sibling_dir / "secret.txt"))


@pytest.mark.asyncio
async def test_serve_spa_blocks_path_traversal(tmp_path: Path) -> None:
    """Verify SPA fallback does not read files outside static_dir."""
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    (static_dir / "app.html").write_text("<html>APP</html>", encoding="utf-8")

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP_SECRET", encoding="utf-8")

    symlink_escape = static_dir / "leak.txt"
    symlink_escape.symlink_to(secret_file)

    settings = StudioSettings(static_dir=str(static_dir), dev_mode=False)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ok_resp = await client.get("/app.html")
        assert ok_resp.status_code == 200
        assert "APP" in ok_resp.text

        traversal_resp = await client.get("/..%2fsecret.txt")
        assert traversal_resp.status_code == 404
        assert "TOP_SECRET" not in traversal_resp.text

        symlink_resp = await client.get("/leak.txt")
        assert symlink_resp.status_code == 404
        assert "TOP_SECRET" not in symlink_resp.text


def test_langfuse_stats_hides_raw_exception_details(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify get_run_langfuse_stats logs errors instead of leaking exception strings."""

    class _ExplodingLangfuse:
        def __init__(self, **_kwargs: object) -> None:
            raise RuntimeError("internal secret traceback token-xyz")

    monkeypatch.setitem(
        sys.modules, "langfuse", SimpleNamespace(Langfuse=_ExplodingLangfuse)
    )

    service = RunService(
        reader=ArtifactReader(
            runs_dir=tmp_path / "runs", artifacts_dir=tmp_path / "artifacts"
        )
    )
    res = service.get_run_langfuse_stats(
        "run-123",
        public_key="pk-test",
        secret_key="sk-test",
    )

    assert res["connected"] is False
    assert "token-xyz" not in res["message"]
    assert "internal secret" not in res["message"]


def test_trace_id_uses_sha256_prefix_consistently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify Langfuse trace IDs in pipeline and studio match 32-char SHA-256 prefix."""
    import episteme_pipeline.runs.observability as obs_mod
    from episteme_pipeline.runs.observability import run_observability_context

    run_id = "run-abc-789"
    expected_trace_id = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:32]
    assert len(expected_trace_id) == 32

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    service = RunService(
        reader=ArtifactReader(
            runs_dir=tmp_path / "runs", artifacts_dir=tmp_path / "artifacts"
        )
    )
    studio_res = service.get_run_langfuse_stats(run_id, public_key="", secret_key="")
    assert studio_res["trace_id"] == expected_trace_id

    captured_trace_ids: list[str] = []

    class _DummyObs:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class _DummyClient:
        def start_as_current_observation(
            self, *, trace_context: dict[str, str], **_kwargs: object
        ) -> _DummyObs:
            captured_trace_ids.append(trace_context["trace_id"])
            return _DummyObs()

        def flush(self) -> None:
            return None

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setattr(obs_mod, "get_client", lambda: _DummyClient())
    monkeypatch.setattr(obs_mod, "propagate_attributes", None)

    with run_observability_context(run_id=run_id):
        pass

    assert captured_trace_ids == [expected_trace_id]
