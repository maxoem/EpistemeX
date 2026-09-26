"""FastAPI application factory for GLP Studio."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from episteme_studio.api.config import router as config_router
from episteme_studio.api.diff import router as diff_router
from episteme_studio.api.engine import router as engine_router
from episteme_studio.api.evaluation import router as evaluation_router
from episteme_studio.api.errors import (
    StudioProblemException,
    problem_exception_handler,
    problem_json_response,
)
from episteme_studio.api.graph import router as graph_router
from episteme_studio.api.metrics import router as metrics_router
from episteme_studio.api.overlays import router as overlays_router
from episteme_studio.api.runs import router as runs_router
from episteme_studio.api.system import router as system_router
from episteme_studio.domain.errors import (
    InvalidConfigPatchError,
    Neo4jReadOnlyViolationError,
    Neo4jUnavailableError,
    OverlayNotImplementedError,
    ProblemDetail,
    QueryTimeoutError,
    ResultTooLargeError,
)
from episteme_studio.lifespan import create_lifespan
from episteme_studio.runtime.broker import EventBroker
from episteme_studio.runtime.executor import PipelineExecutor
from episteme_studio.runtime.registry import RunRegistry
from episteme_studio.security import validate_host_and_token
from episteme_studio.services.metric_service import MetricService
from episteme_studio.settings import StudioSettings, get_default_settings


def resolve_static_dir(settings: StudioSettings) -> Path:
    """Resolve the static assets directory.

    Parameters
    ----------
    settings : StudioSettings
        Current runtime settings.

    Returns
    -------
    Path
        Path to directory containing static assets.
    """
    if settings.static_dir:
        return Path(settings.static_dir)
    try:
        ref = importlib.resources.files("episteme_studio") / "static"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent / "static"


def create_app(settings: StudioSettings | None = None) -> FastAPI:
    """Create and configure the GLP Studio FastAPI application.

    Parameters
    ----------
    settings : StudioSettings or None, optional
        Settings instance. If None, default settings are loaded.

    Returns
    -------
    FastAPI
        Configured FastAPI application.
    """
    current_settings = settings or get_default_settings()
    validate_host_and_token(current_settings)

    app = FastAPI(
        title="Episteme Studio API",
        version="0.1.0",
        description="Run-oriented workbench over the Episteme pipeline and artifact store.",
        lifespan=create_lifespan(current_settings),
    )
    app.state.settings = current_settings
    broker = EventBroker()
    registry = RunRegistry()
    executor = PipelineExecutor(registry, broker)
    metric_service = MetricService()
    app.state.broker = broker
    app.state.registry = registry
    app.state.executor = executor
    app.state.metric_service = metric_service

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handlers
    app.add_exception_handler(StudioProblemException, problem_exception_handler)

    @app.exception_handler(Neo4jUnavailableError)
    async def neo4j_unavailable_handler(request: Request, exc: Neo4jUnavailableError):
        return problem_json_response(
            ProblemDetail(
                type="neo4j-unavailable",
                title="Neo4j Unavailable",
                status=503,
                detail=str(exc) or "Neo4j graph store is unavailable.",
            )
        )

    @app.exception_handler(Neo4jReadOnlyViolationError)
    async def read_only_handler(request: Request, exc: Neo4jReadOnlyViolationError):
        return problem_json_response(
            ProblemDetail(
                type="neo4j-read-only-violation",
                title="Neo4j Read-Only Violation",
                status=403,
                detail=str(exc) or "Cypher console operates in read-only access mode.",
            )
        )

    @app.exception_handler(QueryTimeoutError)
    async def timeout_handler(request: Request, exc: QueryTimeoutError):
        return problem_json_response(
            ProblemDetail(
                type="query-timeout",
                title="Query Timeout",
                status=504,
                detail=str(exc) or "Query execution exceeded timeout limit.",
            )
        )

    @app.exception_handler(ResultTooLargeError)
    async def result_too_large_handler(request: Request, exc: ResultTooLargeError):
        return problem_json_response(
            ProblemDetail(
                type="result-too-large",
                title="Result Too Large",
                status=413,
                detail=str(exc) or "Query result exceeded maximum allowed cap.",
            )
        )

    @app.exception_handler(OverlayNotImplementedError)
    async def overlay_not_implemented_handler(
        request: Request, exc: OverlayNotImplementedError
    ):
        return problem_json_response(
            ProblemDetail(
                type="overlay-not-implemented",
                title="Overlay Not Implemented",
                status=501,
                detail=str(exc)
                or "The requested overlay kind is reserved and not yet implemented.",
            )
        )

    @app.exception_handler(InvalidConfigPatchError)
    async def invalid_config_patch_handler(
        request: Request, exc: InvalidConfigPatchError
    ):
        return problem_json_response(
            ProblemDetail(
                type="invalid-config-patch",
                title="Invalid Configuration Patch",
                status=422,
                detail=str(exc)
                or "The configuration patch contains invalid keys or failed validation.",
            )
        )

    # Register API routers
    app.include_router(system_router)
    app.include_router(runs_router)
    app.include_router(graph_router)
    app.include_router(overlays_router)
    app.include_router(metrics_router)
    app.include_router(config_router)
    app.include_router(diff_router)
    app.include_router(engine_router)
    app.include_router(evaluation_router)

    static_dir = resolve_static_dir(current_settings)
    index_html = static_dir / "index.html"

    # Static and SPA route handling
    if current_settings.dev_mode:
        vite_url = (
            current_settings.dev_mode
            if isinstance(current_settings.dev_mode, str)
            and current_settings.dev_mode.startswith("http")
            else "http://127.0.0.1:5173"
        ).rstrip("/")

        @app.get("/{full_path:path}", response_model=None)
        async def serve_vite_dev(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"type": "not-found", "title": "Not Found", "status": 404},
                )
            dev_html = (
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "  <head>\n"
                '    <meta charset="UTF-8" />\n'
                '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
                "    <title>Episteme Studio — Theory Graph Workbench (Dev Mode)</title>\n"
                "    <link rel=\"icon\" type=\"image/svg+xml\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'%3E%3Cpath d='M17.5 8C16.5 5.5 14.2 4 11.8 4C7.5 4 4 7.58 4 12C4 16.42 7.5 20 11.8 20C15.4 20 18.3 17.5 19.3 13.5H12' stroke='%233b82f6' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'/%3E%3Ccircle cx='17.5' cy='8' r='1.5' fill='%233b82f6'/%3E%3Ccircle cx='19.3' cy='13.5' r='1.6' fill='%233b82f6'/%3E%3Ccircle cx='12' cy='13.5' r='1.6' fill='%230d1117' stroke='%233b82f6' stroke-width='1.75'/%3E%3C/svg%3E\" />\n"
                "    <script>\n"
                "      (function() {\n"
                "        try {\n"
                "          var stored = localStorage.getItem('episteme-studio-theme');\n"
                "          var theme = stored || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');\n"
                "          if (theme === 'light') {\n"
                "            document.documentElement.setAttribute('data-theme', 'light');\n"
                "            document.documentElement.classList.add('light');\n"
                "            document.documentElement.style.colorScheme = 'light';\n"
                "          } else {\n"
                "            document.documentElement.setAttribute('data-theme', 'dark');\n"
                "            document.documentElement.classList.add('dark');\n"
                "            document.documentElement.style.colorScheme = 'dark';\n"
                "          }\n"
                "        } catch (e) {}\n"
                "      })();\n"
                "    </script>\n"
                f'    <script type="module" src="{vite_url}/@vite/client"></script>\n'
                f'    <script type="module" src="{vite_url}/src/main.tsx"></script>\n'
                "  </head>\n"
                '  <body class="bg-app-bg text-app-text antialiased overflow-hidden select-none">\n'
                '    <div id="root"></div>\n'
                "  </body>\n"
                "</html>\n"
            )
            return HTMLResponse(content=dev_html)
    elif static_dir.exists() and index_html.exists():
        app.mount(
            "/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets"
        )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> HTMLResponse:
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"type": "not-found", "title": "Not Found", "status": 404},
                )
            target_file = static_dir / full_path
            if full_path and target_file.is_file():
                return HTMLResponse(target_file.read_text(encoding="utf-8"))
            return HTMLResponse(index_html.read_text(encoding="utf-8"))
    else:

        @app.get("/{full_path:path}")
        async def frontend_not_built(request: Request, full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={"type": "not-found", "title": "Not Found", "status": 404},
                    media_type="application/problem+json",
                )
            problem = ProblemDetail(
                type="frontend-not-built",
                title="Frontend Not Built",
                status=503,
                detail="Frontend assets have not been built. Run 'npm run build' inside packages/episteme-studio/frontend.",
            )
            # Render friendly HTML response if browser requested HTML, else problem+json
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                html_content = (
                    "<!DOCTYPE html>"
                    "<html><head><title>Episteme Studio — Frontend Not Built</title></head>"
                    "<body style='font-family: sans-serif; padding: 2rem; max-width: 600px; margin: auto;'>"
                    "<h1>Episteme Studio</h1>"
                    "<h2>Frontend Not Built (HTTP 503)</h2>"
                    "<p>The frontend static assets are not present in <code>episteme_studio/static</code>.</p>"
                    "<p>To build the UI, run:</p>"
                    "<pre style='background: #f0f0f0; padding: 1rem; border-radius: 4px;'>cd packages/episteme-studio/frontend && npm install && npm run build</pre>"
                    "<p>API endpoints remain available under <code>/api</code>.</p>"
                    "</body></html>"
                )
                return HTMLResponse(content=html_content, status_code=503)
            return problem_json_response(problem)

    return app
