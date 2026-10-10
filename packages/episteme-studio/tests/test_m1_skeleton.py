"""Tests for Milestone 1: Package skeleton, wire models, and architectural boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from episteme_studio.app import create_app
from episteme_studio.security import SecurityConfigurationError, validate_host_and_token
from episteme_studio.settings import StudioSettings


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """GET /api/health must return 200 with status ok."""
    app = create_app(StudioSettings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_capabilities_endpoint() -> None:
    """GET /api/capabilities reports artifacts availability, with neo4j and execution false."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True)
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert data["artifacts"] is True
        assert data["neo4j"] is False
        assert data["execution"] is False
        assert isinstance(data["overlays"], list)


@pytest.mark.asyncio
async def test_frontend_not_built_serves_problem_detail(tmp_path: Path) -> None:
    """Missing static/index.html must return 503 problem detail or friendly HTML."""
    empty_static = tmp_path / "empty_static"
    empty_static.mkdir()
    settings = StudioSettings(static_dir=empty_static)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # JSON request
        resp_json = await client.get("/", headers={"accept": "application/json"})
        assert resp_json.status_code == 503
        body = resp_json.json()
        assert body["type"] == "frontend-not-built"

        # HTML request
        resp_html = await client.get("/", headers={"accept": "text/html"})
        assert resp_html.status_code == 503
        assert "Frontend Not Built" in resp_html.text


@pytest.mark.asyncio
async def test_dev_mode_serves_vite_html() -> None:
    """When dev_mode is set, app serves HTML embedding Vite client and entry script."""
    settings = StudioSettings(dev_mode=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "/@vite/client" in response.text
        assert "/src/main.tsx" in response.text


@pytest.mark.asyncio
async def test_openapi_json_is_valid() -> None:
    """FastAPI must serve a valid OpenAPI spec at /openapi.json."""
    app = create_app(StudioSettings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "openapi" in spec
        assert "/api/health" in spec["paths"]
        assert "/api/capabilities" in spec["paths"]
        assert "/api/schema" in spec["paths"]


def test_domain_never_imports_pipeline_or_epistemetrics() -> None:
    """AST guard: domain/ modules must NOT import episteme_pipeline.* or epistemetrics.* (D-01)."""
    domain_dir = Path(__file__).parent.parent / "src" / "episteme_studio" / "domain"
    py_files = list(domain_dir.glob("*.py"))
    assert len(py_files) > 0, "No domain files found"

    forbidden_roots = {"episteme_pipeline", "pipeline", "epistemetrics"}
    violations = []

    for file_path in py_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in forbidden_roots:
                        violations.append(
                            f"{file_path.name}:{node.lineno} imports '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg in forbidden_roots:
                    violations.append(
                        f"{file_path.name}:{node.lineno} imports from '{node.module}'"
                    )

    assert not violations, f"Domain isolation violated (D-01):\n" + "\n".join(
        violations
    )


def test_settings_is_only_file_touching_environ() -> None:
    """AST guard: settings.py is the ONLY file accessing os.environ or os.getenv (SPEC §3)."""
    src_dir = Path(__file__).parent.parent / "src" / "episteme_studio"
    py_files = [f for f in src_dir.rglob("*.py") if f.name != "settings.py"]
    assert len(py_files) > 0

    violations = []
    for file_path in py_files:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # Look for os.environ or os.getenv
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "os"
                    and node.attr in ("environ", "getenv")
                ):
                    violations.append(
                        f"{file_path.relative_to(src_dir)}:{node.lineno} accesses os.{node.attr}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module == "os":
                for alias in node.names:
                    if alias.name in ("environ", "getenv"):
                        violations.append(
                            f"{file_path.relative_to(src_dir)}:{node.lineno} imports {alias.name} from os"
                        )

    assert not violations, (
        "Direct os.environ / os.getenv access found outside settings.py:\n"
        + "\n".join(violations)
    )


def test_security_loopback_binding_guard() -> None:
    """Non-loopback bind without token must raise SecurityConfigurationError (D-23)."""
    # Allowed: loopback without token
    validate_host_and_token(StudioSettings(host="127.0.0.1", token=None))
    validate_host_and_token(StudioSettings(host="localhost", token=None))

    # Allowed: non-loopback with token
    validate_host_and_token(StudioSettings(host="0.0.0.0", token="secret-token-123"))

    # Forbidden: non-loopback without token
    with pytest.raises(SecurityConfigurationError):
        validate_host_and_token(StudioSettings(host="0.0.0.0", token=None))

    with pytest.raises(SecurityConfigurationError):
        validate_host_and_token(StudioSettings(host="192.168.1.50", token=None))
